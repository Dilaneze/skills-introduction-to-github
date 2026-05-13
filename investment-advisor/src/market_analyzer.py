"""
CATALYST-DRIVEN SWING TRADING ANALYZER
Automated investment advisor for US and EU markets

Version 3.0 - Virtual Committee system — bidirectional (Long + Short)
"""

import os
import json
import time
import random
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import virtual committee (longs and shorts)
from committee import evaluate_opportunity, evaluate_short_opportunity

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TradingConfig:
    """Configurable trading parameters — professional swing trading"""
    capital: float = 500.0
    leverage: int = 5
    max_stop_loss_pct: float = 10.0   # 10% = 50% real with x5 (adjusted for volatile small caps)
    min_risk_reward: float = 3.0      # Minimum 3:1 R:R mandatory
    position_size_normal: float = 10.0       # 10% of capital (50 EUR = 250 EUR exposure)
    position_size_exceptional: float = 15.0  # For high-conviction plays
    max_concurrent_positions: int = 2  # Max 2 simultaneous positions (risk management)
    min_holding_days: int = 1          # Allow day trades
    max_holding_days: int = 14         # Long swing trades

    # Target based on realistic % (not 52w high)
    target_pct_conservative: float = 15.0  # Minimum target 15%
    target_pct_aggressive: float = 20.0    # Target for strong setups

    # Selection filters — BALANCED
    min_market_cap: float = 100_000_000      # $100M (micro caps too risky)
    max_market_cap: float = 100_000_000_000  # $100B
    min_beta: float = 1.5       # Minimum beta 1.5 for required volatility
    preferred_beta: float = 2.0  # Preferred beta
    min_price: float = 2.0       # $2 minimum (avoid extreme penny stocks)
    max_price: float = 500.0
    max_spread_pct: float = 1.0

    # Minimum volume by market cap
    volume_thresholds: dict = None

    def __post_init__(self):
        self.volume_thresholds = {
            "small": 1_000_000,   # $100M-$1B: 1M shares minimum
            "mid": 750_000,       # $1B-$10B: 750K shares
            "large": 500_000      # >$10B: 500K shares
        }


def load_trading_config() -> TradingConfig:
    """Load parameters from trading_config.json; fallback to defaults if not found."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "trading_config.json")
    try:
        with open(config_path) as f:
            data = json.load(f)
        risk = data.get("risk_parameters", {})
        filters = data.get("filters", {})
        vol = filters.get("volume_thresholds", {})
        cfg = TradingConfig(
            capital=float(data.get("capital", 500)),
            leverage=int(data.get("leverage", 5)),
            max_stop_loss_pct=float(risk.get("max_stop_loss_pct", 10.0)),
            min_risk_reward=float(risk.get("min_risk_reward", 3.0)),
            position_size_normal=float(risk.get("position_size_normal_pct", 10.0)),
            position_size_exceptional=float(risk.get("position_size_exceptional_pct", 15.0)),
            max_concurrent_positions=int(risk.get("max_concurrent_positions", 2)),
            min_holding_days=int(risk.get("min_holding_days", 1)),
            max_holding_days=int(risk.get("max_holding_days", 14)),
            min_market_cap=float(filters.get("min_market_cap_usd", 100_000_000)),
            max_market_cap=float(filters.get("max_market_cap_usd", 100_000_000_000)),
            min_beta=float(filters.get("min_beta", 1.5)),
            preferred_beta=float(filters.get("preferred_beta", 2.0)),
            min_price=float(filters.get("min_price_usd", 2.0)),
            max_price=float(filters.get("max_price_usd", 500.0)),
            max_spread_pct=float(filters.get("max_spread_pct", 1.0)),
        )
        if vol:
            cfg.volume_thresholds = {
                "small": int(vol.get("small_cap_300M_1B", 1_000_000)),
                "mid": int(vol.get("mid_cap_1B_5B", 750_000)),
                "large": int(vol.get("large_cap_above_5B", 500_000)),
            }
        print(f"[CONFIG] Loaded trading_config.json — stop_loss={cfg.max_stop_loss_pct}%, "
              f"min_price=${cfg.min_price}, min_cap=${cfg.min_market_cap/1e6:.0f}M")
        return cfg
    except FileNotFoundError:
        print("[CONFIG] trading_config.json not found, using defaults")
        return TradingConfig()


config = load_trading_config()

# ============================================================================
# DATA APIs
# ============================================================================

class MarketDataAPI:
    """Wrapper for financial data APIs. Primary: Finnhub. Fallback: Yahoo Finance."""

    def __init__(self):
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", "")
        self.fmp_key = os.getenv("FMP_API_KEY", "")

    def get_market_status(self) -> dict:
        """Fetch general market status (VIX, SPY, Nasdaq) via Yahoo Finance (no key required)."""
        result = {
            "vix": None,
            "sp500_change": None,
            "nasdaq_change": None,
            "spy_above_200ema": True,
            "market_regime": "UNKNOWN",
            "top_sectors": [],
            "premarket_movers": []
        }

        try:
            vix_data = self._fetch_yahoo_quote("^VIX")
            if vix_data:
                result["vix"] = vix_data.get("price")

            spy_data = self._fetch_yahoo_quote("SPY")
            if spy_data:
                result["sp500_change"] = spy_data.get("change_pct")
                spy_price = spy_data.get("price", 0)
                spy_ema_200 = spy_data.get("ema_200", 0)
                if spy_price > 0 and spy_ema_200 > 0:
                    result["spy_above_200ema"] = spy_price > spy_ema_200
                result["spy_price"] = spy_price
                result["spy_price_60d_ago"] = spy_data.get("price_60d_ago", spy_price)

            nasdaq_data = self._fetch_yahoo_quote("^IXIC")
            if nasdaq_data:
                result["nasdaq_change"] = nasdaq_data.get("change_pct")

            result["market_regime"] = self._determine_regime(result)

        except Exception as e:
            print(f"[ERROR] Market status: {e}")

        return result

    def _fetch_finnhub_quote(self, symbol: str) -> Optional[dict]:
        """Fetch 200-day OHLCV candles from Finnhub (primary data source when key available)."""
        if not self.finnhub_key:
            return None

        to_ts = int(time.time())
        from_ts = int((datetime.now() - timedelta(days=280)).timestamp())  # extra buffer for 200d

        url = "https://finnhub.io/api/v1/stock/candles"
        params = {
            "symbol": symbol, "resolution": "D",
            "from": from_ts, "to": to_ts, "token": self.finnhub_key
        }

        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("s") != "ok" or not data.get("c"):
                        return None

                    closes = [c for c in data["c"] if c is not None]
                    highs = [h for h in data["h"] if h is not None]
                    lows = [l for l in data["l"] if l is not None]
                    volumes = [v for v in data["v"] if v is not None]

                    if not closes:
                        return None

                    price = closes[-1]
                    prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
                    change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0

                    technical_indicators = self._calculate_technical_indicators(closes, highs, lows, volumes)

                    quote = {
                        "symbol": symbol,
                        "price": round(price, 2),
                        "prev_close": round(prev_close, 2),
                        "change_pct": change_pct,
                        "_closes_raw": closes
                    }
                    quote.update(technical_indicators)
                    return quote

                elif response.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"[WARN] Finnhub rate limited on {symbol}, waiting {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                elif response.status_code == 403:
                    print(f"[WARN] Finnhub API key invalid or quota exceeded")
                    return None
                else:
                    return None

            except requests.exceptions.Timeout:
                wait = 2 ** attempt
                print(f"[WARN] Finnhub timeout for {symbol} (attempt {attempt+1}/3), retrying in {wait}s")
                if attempt < 2:
                    time.sleep(wait)
            except Exception as e:
                print(f"[ERROR] Finnhub candles for {symbol}: {e}")
                return None

        return None

    def _fetch_yahoo_quote(self, symbol: str) -> Optional[dict]:
        """Fetch quote from Yahoo Finance (fallback / used for market indices)."""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {"interval": "1d", "range": "200d"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9"
        }

        for attempt in range(3):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=15, proxies={'http': None, 'https': None})

                if response.status_code == 200:
                    data = response.json()
                    chart_result = data.get("chart", {}).get("result")

                    if not chart_result or len(chart_result) == 0:
                        print(f"[WARN] No data for {symbol}")
                        return None

                    result = chart_result[0]
                    meta = result.get("meta", {})
                    indicators = result.get("indicators", {}).get("quote", [{}])[0]

                    price = meta.get("regularMarketPrice", 0)
                    prev_close = meta.get("previousClose", 0) or meta.get("chartPreviousClose", 0)

                    if prev_close and prev_close > 0:
                        change_pct = ((price - prev_close) / prev_close * 100)
                    else:
                        change_pct = 0

                    closes = [c for c in indicators.get("close", []) if c is not None]
                    highs = [h for h in indicators.get("high", []) if h is not None]
                    lows = [l for l in indicators.get("low", []) if l is not None]
                    volumes = [v for v in indicators.get("volume", []) if v is not None]

                    technical_indicators = self._calculate_technical_indicators(closes, highs, lows, volumes)

                    quote = {
                        "symbol": symbol,
                        "price": round(price, 2) if price else 0,
                        "prev_close": round(prev_close, 2) if prev_close else 0,
                        "change_pct": round(change_pct, 2),
                        "_closes_raw": closes
                    }
                    quote.update(technical_indicators)
                    return quote

                elif response.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"[WARN] Yahoo rate limited on {symbol}, waiting {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                else:
                    print(f"[WARN] Yahoo API returned {response.status_code} for {symbol}")
                    return None

            except requests.exceptions.Timeout:
                wait = 2 ** attempt
                print(f"[WARN] Yahoo timeout for {symbol} (attempt {attempt+1}/3), retrying in {wait}s")
                if attempt < 2:
                    time.sleep(wait)
            except Exception as e:
                print(f"[ERROR] Yahoo fetch for {symbol}: {e}")
                return None

        return None

    def _calculate_technical_indicators(self, closes: list, highs: list, lows: list, volumes: list) -> dict:
        """Calculate technical indicators required by the committee."""
        if not closes or len(closes) < 20:
            return {}

        indicators = {}

        if len(highs) >= 20:
            indicators["high_20d"] = max(highs[-20:])

        if len(closes) >= 6:
            indicators["price_5d_ago"] = closes[-6]
        if len(closes) >= 11:
            indicators["price_10d_ago"] = closes[-11]
        if len(closes) >= 21:
            indicators["price_20d_ago"] = closes[-21]
        if len(closes) >= 61:
            indicators["price_60d_ago"] = closes[-61]

        if len(volumes) >= 20:
            indicators["avg_volume_20d"] = sum(volumes[-20:]) / 20
            indicators["volume"] = volumes[-1] if volumes else 0

        if len(closes) >= 20:
            indicators["ema_20"] = self._calculate_ema(closes, 20)

        if len(closes) >= 50:
            indicators["ema_50"] = self._calculate_ema(closes, 50)

        if len(closes) >= 200:
            indicators["ema_200"] = self._calculate_ema(closes, 200)

        # SMA 150 (Weinstein 30-week MA) — distinguishes Stage 2 from Stage 4
        if len(closes) >= 150:
            indicators["sma_150"] = self._calculate_sma(closes, 150)
            if len(closes) >= 170:
                indicators["sma_150_20d_ago"] = self._calculate_sma(closes[:-20], 150)

        if len(closes) >= 14 and len(highs) >= 14 and len(lows) >= 14:
            indicators["atr_14"] = self._calculate_atr(closes, highs, lows, 14)

        if len(closes) >= 15:
            indicators["rsi_14"] = self._calculate_rsi(closes, 14)

        return indicators

    def _calculate_sma(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0
        return round(sum(prices[-period:]) / period, 2)

    def _calculate_rsi(self, closes: list, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        recent = deltas[-(period + 1):]
        gains = [max(d, 0) for d in recent]
        losses = [max(-d, 0) for d in recent]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def _calculate_ema(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0
        multiplier = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 2)

    def _calculate_atr(self, closes: list, highs: list, lows: list, period: int = 14) -> float:
        if len(closes) < period + 1 or len(highs) < period or len(lows) < period:
            return 0
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            true_ranges.append(tr)
        if len(true_ranges) >= period:
            return round(sum(true_ranges[-period:]) / period, 2)
        return 0

    def _determine_regime(self, market_data: dict) -> str:
        vix = market_data.get("vix")
        sp500 = market_data.get("sp500_change")
        if vix is None:
            return "UNKNOWN"
        if vix > 25:
            return "RISK-OFF (high volatility)"
        elif vix < 15 and sp500 and sp500 > 0:
            return "RISK-ON (low volatility, bull market)"
        elif vix < 20:
            return "NEUTRAL"
        else:
            return "CAUTION (moderate-high volatility)"

    def get_stock_data(self, symbol: str, market_status: dict = None) -> Optional[dict]:
        """
        Fetch complete stock data. Primary: Finnhub candles. Fallback: Yahoo Finance.
        Always enriches with Finnhub fundamentals (market cap, beta, 52w range) when key available.
        """
        quote = None

        # Primary: Finnhub candles (when API key available)
        if self.finnhub_key:
            quote = self._fetch_finnhub_quote(symbol)
            if quote:
                self._fetch_finnhub_details(quote, symbol)

        # Fallback: Yahoo Finance
        if not quote:
            quote = self._fetch_yahoo_quote(symbol)
            if not quote:
                return None
            yahoo_ok = self._fetch_yahoo_details(quote, symbol)
            # If Yahoo details failed and we have Finnhub, use for fundamentals
            if not yahoo_ok and self.finnhub_key:
                self._fetch_finnhub_details(quote, symbol)

        quote.pop("_closes_raw", None)

        # Earnings surprise for PEAD scoring (Finnhub only)
        if self.finnhub_key:
            earnings_data = self.get_earnings_surprise(symbol)
            quote.update(earnings_data)

        # Propagate SPY data for relative strength calculation
        if market_status:
            quote["spy_price_60d_ago"] = market_status.get("spy_price_60d_ago", 0)
            quote["spy_price"] = market_status.get("spy_price", 0)

        return quote

    def _fetch_yahoo_details(self, quote: dict, symbol: str) -> bool:
        """Fetch additional fundamentals from Yahoo Finance quoteSummary. Returns True on success."""
        try:
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
            params = {"modules": "summaryDetail,defaultKeyStatistics,financialData"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }

            response = requests.get(url, params=params, headers=headers, timeout=15, proxies={'http': None, 'https': None})
            if response.status_code == 200:
                data = response.json()
                quote_result = data.get("quoteSummary", {}).get("result")

                if quote_result and len(quote_result) > 0:
                    result = quote_result[0]
                    summary = result.get("summaryDetail", {})
                    stats = result.get("defaultKeyStatistics", {})
                    financials = result.get("financialData", {})

                    def safe_get(d, key):
                        val = d.get(key, {})
                        if isinstance(val, dict):
                            return val.get("raw")
                        return val

                    quote.update({
                        "market_cap": safe_get(summary, "marketCap"),
                        "beta": safe_get(summary, "beta"),
                        "volume": safe_get(summary, "volume"),
                        "avg_volume": safe_get(summary, "averageVolume"),
                        "52w_high": safe_get(summary, "fiftyTwoWeekHigh"),
                        "52w_low": safe_get(summary, "fiftyTwoWeekLow"),
                        "pe_ratio": safe_get(summary, "trailingPE"),
                        "short_ratio": safe_get(stats, "shortRatio"),
                        "short_pct": safe_get(stats, "shortPercentOfFloat"),
                        "revenue_growth": safe_get(financials, "revenueGrowth"),
                        "profit_margin": safe_get(financials, "profitMargins"),
                    })

                    if quote.get("market_cap") or quote.get("52w_high"):
                        return True

        except Exception as e:
            print(f"[WARN] Yahoo details failed for {symbol}: {e}")

        return False

    def _fetch_finnhub_details(self, quote: dict, symbol: str) -> bool:
        """Fetch fundamentals from Finnhub (profile2 + metrics). Returns True on success."""
        if not self.finnhub_key:
            return False

        try:
            # Company profile (market cap)
            url = "https://finnhub.io/api/v1/stock/profile2"
            params = {"symbol": symbol, "token": self.finnhub_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data:
                    quote["market_cap"] = data.get("marketCapitalization", 0) * 1e6  # Finnhub returns millions
                    if not quote.get("beta"):
                        quote["beta"] = data.get("beta")

            # Key metrics (52w high/low, beta, revenue growth)
            url = "https://finnhub.io/api/v1/stock/metric"
            params = {"symbol": symbol, "metric": "all", "token": self.finnhub_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                metrics = data.get("metric", {})
                if metrics:
                    quote["52w_high"] = metrics.get("52WeekHigh")
                    quote["52w_low"] = metrics.get("52WeekLow")
                    quote["beta"] = quote.get("beta") or metrics.get("beta")
                    quote["pe_ratio"] = metrics.get("peBasicExclExtraTTM")
                    quote["revenue_growth"] = metrics.get("revenueGrowthTTMYoy")
                    quote["profit_margin"] = metrics.get("netProfitMarginTTM")
                    if quote.get("revenue_growth"):
                        quote["revenue_growth"] = quote["revenue_growth"] / 100  # Convert to decimal

            return quote.get("market_cap") is not None

        except Exception as e:
            print(f"[WARN] Finnhub details failed for {symbol}: {e}")

        return False

    def get_earnings_surprise(self, symbol: str) -> dict:
        """
        Fetch last quarter EPS surprise for PEAD scoring. Requires Finnhub API key.

        Returns dict with: eps_surprise_pct, earnings_reaction_pct, days_since_earnings,
        earnings_day_volume_ratio
        """
        result = {
            "eps_surprise_pct": None,
            "earnings_reaction_pct": None,
            "days_since_earnings": None,
            "earnings_day_volume_ratio": None
        }

        if not self.finnhub_key:
            return result

        try:
            url = "https://finnhub.io/api/v1/stock/earnings"
            params = {"symbol": symbol, "limit": 4, "token": self.finnhub_key}
            response = requests.get(url, params=params, timeout=10, proxies={"http": None, "https": None})

            if response.status_code != 200:
                return result

            data = response.json()
            if not data:
                return result

            latest = data[0]
            actual = latest.get("actual")
            estimate = latest.get("estimate")
            period = latest.get("period", "")

            if actual is None or estimate is None or estimate == 0:
                return result

            result["eps_surprise_pct"] = round((actual - estimate) / abs(estimate) * 100, 1)

            if period:
                try:
                    earnings_date = datetime.strptime(period, "%Y-%m-%d")
                    result["days_since_earnings"] = max(0, (datetime.now() - earnings_date).days)
                except Exception:
                    pass

        except Exception as e:
            print(f"[WARN] Finnhub earnings surprise failed for {symbol}: {e}")

        return result

    def get_earnings_calendar(self, days_ahead: int = 7) -> list:
        """Fetch upcoming earnings calendar via Finnhub."""
        earnings = []

        if self.finnhub_key:
            try:
                today = datetime.now()
                from_date = today.strftime("%Y-%m-%d")
                to_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

                url = "https://finnhub.io/api/v1/calendar/earnings"
                params = {"from": from_date, "to": to_date, "token": self.finnhub_key}

                response = requests.get(url, params=params, timeout=10, proxies={'http': None, 'https': None})
                if response.status_code == 200:
                    data = response.json()
                    earnings = data.get("earningsCalendar", [])

            except Exception as e:
                print(f"[ERROR] Earnings calendar: {e}")

        return earnings

    def get_news_sentiment(self, symbol: str) -> dict:
        """Fetch recent news sentiment via Finnhub."""
        sentiment = {"score": 0, "articles": 0, "positive": 0, "negative": 0}

        if self.finnhub_key:
            try:
                today = datetime.now()
                from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                to_date = today.strftime("%Y-%m-%d")

                url = "https://finnhub.io/api/v1/company-news"
                params = {"symbol": symbol, "from": from_date, "to": to_date, "token": self.finnhub_key}

                response = requests.get(url, params=params, timeout=10, proxies={'http': None, 'https': None})
                if response.status_code == 200:
                    articles = response.json()
                    sentiment["articles"] = len(articles)

            except Exception as e:
                print(f"[WARN] News sentiment for {symbol}: {e}")

        return sentiment


# ============================================================================
# SCORING ENGINE — VIRTUAL COMMITTEE
# ============================================================================

class OpportunityScorer:
    """LONG opportunity scoring system using the Virtual Committee."""

    def __init__(self, api: MarketDataAPI, market_status: dict):
        self.api = api
        self.market_status = market_status

    def score_opportunity(self, symbol: str, catalyst_info: dict = None, stock_data: dict = None) -> dict:
        """Evaluate and score a LONG opportunity using the committee."""

        if stock_data is None:
            stock_data = self.api.get_stock_data(symbol, self.market_status)
        if not stock_data:
            return {"symbol": symbol, "score": 0, "error": "Could not fetch data"}

        exclusion_reason = self._check_exclusions(stock_data)
        if exclusion_reason:
            return {
                "symbol": symbol,
                "price": stock_data.get("price"),
                "market_cap": stock_data.get("market_cap"),
                "beta": stock_data.get("beta"),
                "volume": stock_data.get("avg_volume"),
                "total_score": 0,
                "signal": "SKIP",
                "exclusion_reason": exclusion_reason,
                "trade_setup": None
            }

        evaluation = evaluate_opportunity(
            ticker=symbol,
            ticker_data=stock_data,
            market_data=self.market_status,
            catalyst_info=catalyst_info,
            capital=config.capital,
            leverage=config.leverage
        )

        return {
            "symbol": symbol,
            "price": stock_data.get("price"),
            "market_cap": stock_data.get("market_cap"),
            "beta": stock_data.get("beta"),
            "volume": stock_data.get("avg_volume"),
            "total_score": evaluation["final_score"],
            "signal": evaluation["decision"],
            "exclusion_reason": None if evaluation["decision"] in ["BUY", "WATCHLIST"] else evaluation["decision_reason"],
            "trade_setup": evaluation["trade_params"] if evaluation["decision"] == "BUY" else None,
            "committee_evaluation": evaluation,
            "breakdown": evaluation["breakdown"],
            "reasoning": evaluation["reasoning"]
        }

    def _check_exclusions(self, stock_data: dict, direction: str = "LONG") -> Optional[str]:
        """Check basic exclusion criteria."""
        price = stock_data.get("price", 0)
        market_cap = stock_data.get("market_cap", 0)
        avg_volume = stock_data.get("avg_volume", 0)
        beta = stock_data.get("beta")

        if price and price < config.min_price:
            return f"Penny stock (${price} < ${config.min_price})"

        if price and price > config.max_price:
            return f"Price too high (${price} > ${config.max_price})"

        if market_cap:
            if market_cap < config.min_market_cap:
                return f"Market cap too low (${market_cap/1e6:.0f}M < ${config.min_market_cap/1e6:.0f}M)"
            if market_cap > config.max_market_cap:
                return f"Mega cap (${market_cap/1e9:.0f}B > ${config.max_market_cap/1e9:.0f}B)"

        if beta and beta < config.min_beta:
            return f"Beta too low ({beta:.2f} < {config.min_beta})"

        if market_cap and avg_volume:
            if market_cap < 1e9:  # Small cap $100M-$1B
                if avg_volume < config.volume_thresholds["small"]:
                    return f"Insufficient volume for small cap ({avg_volume/1e6:.1f}M < {config.volume_thresholds['small']/1e6:.1f}M)"
            elif market_cap < 10e9:  # Mid cap $1B-$10B
                if avg_volume < config.volume_thresholds["mid"]:
                    return "Insufficient volume for mid cap"
            else:  # Large cap >$10B
                if avg_volume < config.volume_thresholds["large"]:
                    return "Insufficient volume for large cap"

        return None


class ShortOpportunityScorer:
    """SHORT opportunity scoring system using the Short Committee."""

    def __init__(self, api: MarketDataAPI, market_status: dict):
        self.api = api
        self.market_status = market_status

    def score_short_opportunity(self, symbol: str, stock_data: dict, catalyst_info: dict = None) -> dict:
        """
        Evaluate a SHORT opportunity using the short committee.
        Receives pre-loaded stock_data (shared with long scorer for efficiency).
        """
        if not stock_data:
            return {"symbol": symbol, "score": 0, "error": "No data"}

        price = stock_data.get("price", 0)
        market_cap = stock_data.get("market_cap", 0)

        if price and price < 3:
            return {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT",
                    "exclusion_reason": f"Price too low for short (${price})"}

        if market_cap and market_cap < 50_000_000:
            return {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT",
                    "exclusion_reason": "Market cap too low for safe short"}

        evaluation = evaluate_short_opportunity(
            ticker=symbol,
            ticker_data=stock_data,
            market_data=self.market_status,
            catalyst_info=catalyst_info,
            capital=config.capital,
            leverage=config.leverage
        )

        return {
            "symbol": symbol,
            "price": stock_data.get("price"),
            "market_cap": stock_data.get("market_cap"),
            "beta": stock_data.get("beta"),
            "total_score": evaluation["final_score"],
            "signal": evaluation["decision"],
            "exclusion_reason": None if evaluation["decision"] in ["SHORT", "WATCHLIST_SHORT"] else evaluation["decision_reason"],
            "trade_setup": evaluation["trade_params"] if evaluation["decision"] == "SHORT" else None,
            "committee_evaluation": evaluation,
            "breakdown": evaluation["breakdown"],
            "reasoning": evaluation["reasoning"]
        }


# ============================================================================
# MARKET SCANNER
# ============================================================================

class MarketScanner:
    """Market opportunity scanner with parallel processing."""

    # =========================================================================
    # WATCHLIST — HIGH GROWTH POTENTIAL
    # =========================================================================

    # High-Growth Tech & AI
    WATCHLIST_TECH_AI = [
        "NVDA", "AMD", "SMCI", "ARM", "AVGO", "MRVL", "MU",  # AI semiconductors
        "PLTR", "AI", "BBAI", "SOUN", "UPST",  # AI pure plays
        "PATH", "SNOW", "DDOG", "NET", "CRWD", "ZS",  # Cloud/Cyber
        "IONQ", "RGTI", "QUBT",  # Quantum computing
        "RKLB", "LUNR", "RDW",  # Space tech
    ]

    # High-Beta Growth Stocks
    WATCHLIST_HIGH_BETA = [
        "TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI",  # EV
        "COIN", "MSTR", "MARA", "RIOT", "CLSK", "HUT",  # Crypto-related
        "SHOP", "SQ", "AFRM", "SOFI", "HOOD", "NU",  # Fintech
        "ROKU", "TTD", "MGNI", "PUBM",  # AdTech
        "RBLX", "U", "TTWO", "EA",  # Gaming
    ]

    # Small/Mid Caps with Momentum
    WATCHLIST_SMALL_MID_CAPS = [
        "APLD", "BTBT", "WULF", "CIFR", "IREN",  # Bitcoin miners
        "GEVO", "BE", "PLUG", "FCEL", "BLDP",  # Clean energy
        "JOBY", "ACHR", "LILM", "EVTL",  # eVTOL/Air taxis
        "DNA", "CRSP", "BEAM", "EDIT", "NTLA",  # Gene editing
        "RXRX", "SDGR", "ABCL",  # AI Biotech
        "XMTR", "PRNT", "NNDM", "SSYS",  # 3D Printing
        "OPEN", "CVNA", "CARG", "CHPT",  # Real estate/auto/EV
        "ASTS", "IRDM", "GSAT",  # Satellite/Space
    ]

    # Speculative Biotech (high risk/reward)
    WATCHLIST_BIOTECH_SPECULATIVE = [
        "MRNA", "BNTX", "NVAX",  # Vaccines
        "SAVA", "ACIU", "PRTA",  # Alzheimer
        "SRPT", "VRTX",  # Gene therapy
        "IONS", "ALNY", "ARWR",  # RNA therapeutics
        "AXSM", "CPRX",  # CNS
        "PTGX", "KRYS", "IMVT", "MDGL",  # Small cap biotech
    ]

    # High Short Interest (squeeze potential)
    WATCHLIST_HIGH_SHORT = [
        "GME", "AMC", "KOSS",  # Meme classics
        "BYND", "LMND",  # High short growth
        "GOEV", "WKHS",  # EV shorts
        "SPCE", "LAZR",  # Tech shorts
    ]

    # Recent IPOs and Growth Stories
    WATCHLIST_RECENT_IPOS = [
        "RDDT", "DUOL", "CART", "TOST",  # Recent tech IPOs
        "KVYO", "BIRK", "ONON", "CAVA",  # Consumer
        "VRT", "INTA", "IOT",  # Enterprise
        "GRAB", "SE", "BABA", "JD", "PDD",  # Asian growth
    ]

    # EU stocks available on eToro
    WATCHLIST_EU = [
        "ASML", "SAP", "NVO",  # Large caps
        "SPOT", "FVRR", "WIX",  # Tech EU/Israel
    ]

    # =========================================================================
    # COMPILE FULL WATCHLIST
    # =========================================================================

    DEFAULT_WATCHLIST_US = (
        WATCHLIST_TECH_AI +
        WATCHLIST_HIGH_BETA +
        WATCHLIST_SMALL_MID_CAPS +
        WATCHLIST_BIOTECH_SPECULATIVE +
        WATCHLIST_HIGH_SHORT +
        WATCHLIST_RECENT_IPOS
    )

    DEFAULT_WATCHLIST_EU = WATCHLIST_EU

    def __init__(self):
        self.api = MarketDataAPI()
        self.scorer = None
        self.earnings_calendar = {}

    def _load_earnings_calendar(self):
        """Load earnings calendar for the next 14 days."""
        print("  Loading earnings calendar...")
        earnings_list = self.api.get_earnings_calendar(days_ahead=14)

        for earning in earnings_list:
            symbol = earning.get("symbol", "")
            if symbol:
                date_str = earning.get("date", "")
                if date_str:
                    try:
                        earning_date = datetime.strptime(date_str, "%Y-%m-%d")
                        days_ahead = (earning_date - datetime.now()).days
                        self.earnings_calendar[symbol] = {
                            "date": date_str,
                            "days_ahead": max(0, days_ahead),
                            "type": "earnings",
                            "eps_estimate": earning.get("epsEstimate"),
                            "revenue_estimate": earning.get("revenueEstimate")
                        }
                    except Exception:
                        pass

        print(f"  Earnings found: {len(self.earnings_calendar)} stocks with upcoming earnings")

    def scan_market(self, watchlist: list = None) -> dict:
        """Scan the market for long and short opportunities."""

        if watchlist is None:
            watchlist = self.DEFAULT_WATCHLIST_US + self.DEFAULT_WATCHLIST_EU

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting market scan...")
        print(f"Analyzing {len(watchlist)} stocks...")

        # 1. Market status
        market_status = self.api.get_market_status()
        print(f"\nMARKET REGIME: {market_status['market_regime']}")
        print(f"VIX: {market_status.get('vix', 'N/A')}")
        print(f"S&P 500: {market_status.get('sp500_change', 'N/A')}%")
        print(f"Nasdaq: {market_status.get('nasdaq_change', 'N/A')}%")
        print(f"SPY above 200 EMA: {market_status.get('spy_above_200ema', 'N/A')}")

        # 2. Initialize scorers with market status
        self.scorer = OpportunityScorer(self.api, market_status)
        self.short_scorer = ShortOpportunityScorer(self.api, market_status)

        # 3. Load earnings calendar (catalysts)
        self._load_earnings_calendar()

        # 4. Parallel scan (LONG + SHORT simultaneously)
        opportunities = []
        watchlist_items = []
        skipped = []
        short_opportunities = []
        short_watchlist = []
        print_lock = threading.Lock()

        def scan_symbol(symbol: str) -> dict:
            time.sleep(random.uniform(0.3, 0.7))  # Stagger requests to avoid rate limiting
            catalyst_info = self.earnings_calendar.get(symbol)
            stock_data = self.api.get_stock_data(symbol, market_status)
            result_long = self.scorer.score_opportunity(symbol, catalyst_info, stock_data) if stock_data else \
                {"symbol": symbol, "total_score": 0, "signal": "SKIP", "error": "No data"}
            result_short = self.short_scorer.score_short_opportunity(symbol, stock_data, catalyst_info) \
                if stock_data else {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT"}
            return {
                "symbol": symbol,
                "catalyst_info": catalyst_info,
                "long": result_long,
                "short": result_short
            }

        # 5 workers: balance speed / rate limiting
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(scan_symbol, sym): sym for sym in watchlist}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    item = future.result()
                    symbol = item["symbol"]
                    catalyst_info = item["catalyst_info"]
                    result = item["long"]
                    result_short = item["short"]

                    # Process LONG
                    if not result.get("error"):
                        score = result.get("total_score", 0)
                        signal = result.get("signal", "SKIP")
                        catalyst_tag = f"[EARNINGS {catalyst_info['days_ahead']}d] " if catalyst_info else ""
                        short_score = result_short.get("total_score", 0)
                        short_tag = f"| SHORT:{short_score:.0f}" if short_score >= 40 else ""

                        with print_lock:
                            print(f"  [{completed}/{len(watchlist)}] {symbol} {catalyst_tag}"
                                  f"L:{score:.0f}({signal}) {short_tag}")

                        if signal == "BUY":
                            opportunities.append(result)
                        elif signal == "WATCHLIST":
                            watchlist_items.append(result)
                        else:
                            skipped.append(result)

                    # Process SHORT
                    short_sig = result_short.get("signal", "SKIP_SHORT")
                    if short_sig == "SHORT":
                        short_opportunities.append(result_short)
                    elif short_sig == "WATCHLIST_SHORT":
                        short_watchlist.append(result_short)

                except Exception as e:
                    sym = futures[future]
                    with print_lock:
                        print(f"  {sym}: EXCEPTION: {e}")

        # Sort by score
        opportunities.sort(key=lambda x: x["total_score"], reverse=True)
        watchlist_items.sort(key=lambda x: x["total_score"], reverse=True)
        short_opportunities.sort(key=lambda x: x["total_score"], reverse=True)
        short_watchlist.sort(key=lambda x: x["total_score"], reverse=True)

        return {
            "timestamp": datetime.now().isoformat(),
            "market_status": market_status,
            "opportunities": opportunities[:5],
            "watchlist": watchlist_items[:10],
            "short_opportunities": short_opportunities[:5],
            "short_watchlist": short_watchlist[:10],
            "total_scanned": len(watchlist),
            "opportunities_found": len(opportunities),
            "watchlist_count": len(watchlist_items),
            "short_opportunities_found": len(short_opportunities),
            "short_watchlist_count": len(short_watchlist),
            "earnings_detected": len(self.earnings_calendar)
        }

    def format_report(self, scan_result: dict) -> str:
        """Format scan result as a readable report."""

        report = []
        report.append("=" * 60)
        report.append("INVESTMENT OPPORTUNITY REPORT")
        report.append(f"Generated: {scan_result['timestamp']}")
        report.append("=" * 60)

        ms = scan_result["market_status"]
        report.append(f"\n## MARKET REGIME")
        report.append(f"Status: {ms.get('market_regime', 'N/A')}")
        report.append(f"VIX: {ms.get('vix', 'N/A')}")
        report.append(f"S&P 500: {ms.get('sp500_change', 'N/A')}%")
        report.append(f"Nasdaq: {ms.get('nasdaq_change', 'N/A')}%")

        opps = scan_result.get("opportunities", [])
        if opps:
            report.append(f"\n## BUY OPPORTUNITIES ({len(opps)})")
            report.append("-" * 40)
            for opp in opps:
                report.append(self._format_opportunity(opp))
        else:
            report.append("\n## NO CLEAR OPPORTUNITIES TODAY")
            report.append("Better to stand aside than force a mediocre trade.")

        watch = scan_result.get("watchlist", [])
        if watch:
            report.append(f"\n## WATCHLIST ({len(watch)})")
            report.append("-" * 40)
            for item in watch[:5]:
                report.append(f"- {item['symbol']}: Score {item['total_score']:.0f} | ${item.get('price', 'N/A')}")

        shorts = scan_result.get("short_opportunities", [])
        if shorts:
            report.append(f"\n## SHORT OPPORTUNITIES ({len(shorts)})")
            report.append("-" * 40)
            for s in shorts:
                report.append(self._format_short_opportunity(s))

        short_watch = scan_result.get("short_watchlist", [])
        if short_watch:
            report.append(f"\n## SHORT WATCHLIST ({len(short_watch)})")
            report.append("-" * 40)
            for item in short_watch[:5]:
                report.append(f"- {item['symbol']}: Score {item['total_score']:.0f} | ${item.get('price', 'N/A')}")

        report.append(f"\n## SUMMARY")
        report.append(f"Stocks scanned: {scan_result['total_scanned']}")
        report.append(f"LONG opportunities: {scan_result['opportunities_found']}")
        report.append(f"SHORT opportunities: {scan_result.get('short_opportunities_found', 0)}")
        report.append(f"Long watchlist: {scan_result['watchlist_count']}")
        report.append(f"Short watchlist: {scan_result.get('short_watchlist_count', 0)}")

        report.append("\n" + "=" * 60)
        report.append("DISCLAIMER: NOT financial advice. Trade at your own risk.")
        report.append("=" * 60)

        return "\n".join(report)

    def _format_short_opportunity(self, opp: dict) -> str:
        lines = []
        lines.append(f"\n### {opp['symbol']} [SHORT]")
        lines.append(f"**Score: {opp['total_score']:.0f}/100** | **Signal: {opp['signal']}**")
        lines.append(f"\nPrice: ${opp.get('price', 'N/A')}")

        breakdown = opp.get("breakdown", {})
        if breakdown:
            lines.append(f"\n**Short Committee Breakdown:**")
            lines.append(f"  Regime (inverted): {breakdown.get('regime', 0)}/15")
            lines.append(f"  Parabolic (Qullamaggie): {breakdown.get('parabolic', 0)}/30")
            lines.append(f"  Stage 4 Rejection (Weinstein): {breakdown.get('stage4_rejection', 0)}/30")
            lines.append(f"  PEAD Miss: {breakdown.get('pead_miss', 0)}/25")

        reasoning = opp.get("reasoning", {})
        if reasoning:
            lines.append(f"\n**Reasoning:**")
            for component, reasons in reasoning.items():
                if reasons:
                    lines.append(f"\n*{component.capitalize()}:*")
                    for r in reasons:
                        lines.append(f"  {r}")

        setup = opp.get("trade_setup")
        if setup:
            lines.append(f"\n**Trade Setup (SHORT):**")
            lines.append(f"  Entry: ${setup.get('entry', 'N/A')}")
            lines.append(f"  Stop Loss: ${setup.get('stop', 'N/A')} (+{setup.get('stop_pct', 'N/A')}% above)")
            lines.append(f"  Take Profit: ${setup.get('target', 'N/A')} (-{setup.get('target_pct', 'N/A')}%)")
            lines.append(f"  Risk:Reward: 1:{setup.get('rr_ratio', 'N/A')}")
            lines.append(f"  Position: €{setup.get('position_eur', 0):.0f}")
            max_days = setup.get("max_hold_days_before_fees_material", 10)
            lines.append(f"  Max recommended hold (eToro fees): {max_days}d")

        return "\n".join(lines)

    def _format_opportunity(self, opp: dict) -> str:
        lines = []

        lines.append(f"\n### {opp['symbol']}")
        lines.append(f"**Score: {opp['total_score']:.0f}/100** | **Signal: {opp['signal']}**")

        lines.append(f"\nPrice: ${opp.get('price', 'N/A')}")
        mc = opp.get('market_cap')
        if mc:
            if mc >= 1e9:
                lines.append(f"Market Cap: ${mc/1e9:.1f}B")
            else:
                lines.append(f"Market Cap: ${mc/1e6:.0f}M")
        lines.append(f"Beta: {opp.get('beta', 'N/A')}")

        breakdown = opp.get("breakdown", {})
        if breakdown:
            lines.append(f"\n**Committee Breakdown:**")
            lines.append(f"  Regime: {breakdown.get('regime', 0)}/15")
            lines.append(f"  Turtles (technical): {breakdown.get('turtles', 0)}/25")
            lines.append(f"  Seykota (trend): {breakdown.get('seykota', 0)}/20")
            lines.append(f"  Catalyst: {breakdown.get('catalyst', 0)}/25")
            lines.append(f"  Risk/Reward: {breakdown.get('risk_reward', 0)}/15")
            if breakdown.get('sector_adjustment', 0) != 0:
                lines.append(f"  Sector adjustment: {breakdown.get('sector_adjustment', 0):+d}")

        reasoning = opp.get("reasoning", {})
        if reasoning:
            lines.append(f"\n**Detailed Reasoning:**")
            for component, reasons in reasoning.items():
                if reasons:
                    lines.append(f"\n*{component.capitalize()}:*")
                    for reason in reasons:
                        lines.append(f"  {reason}")

        setup = opp.get("trade_setup")
        if setup:
            lines.append(f"\n**Trade Setup:**")
            lines.append(f"  Entry: ${setup.get('entry', 'N/A')}")
            lines.append(f"  Stop Loss: ${setup.get('stop', 'N/A')} (-{setup.get('stop_pct', 'N/A')}%)")
            lines.append(f"  Take Profit: ${setup.get('target', 'N/A')} (+{setup.get('target_pct', 'N/A')}%)")
            lines.append(f"  Risk:Reward: 1:{setup.get('rr_ratio', 'N/A')}")
            lines.append(f"  Position: €{setup.get('position_eur', 0):.0f}")

        return "\n".join(lines)


# ============================================================================
# GITHUB ISSUE ALERT GENERATOR
# ============================================================================

def create_github_issue_body(scan_result: dict) -> tuple:
    """Generate title and body for GitHub Issue alert."""

    opps = scan_result.get("opportunities", [])
    ms = scan_result.get("market_status", {})
    shorts = scan_result.get("short_opportunities", [])
    has_any = bool(opps or shorts)

    if not has_any:
        title = f"[MARKET SCAN] {datetime.now().strftime('%Y-%m-%d %H:%M')} - No opportunities"
        body = f"""## Market Scan — {datetime.now().strftime('%Y-%m-%d %H:%M')}

### Market Regime
- **Status**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%
- **Nasdaq**: {ms.get('nasdaq_change', 'N/A')}%

### Result
**No long or short opportunities meeting quality criteria were found.**

> Better to stand aside than force a mediocre trade.

---
*Auto-generated by Investment Advisor v3.0 (Long+Short)*
"""
    else:
        if opps and shorts:
            top_long = opps[0]
            top_short = shorts[0]
            title = f"[ALERT] LONG:{top_long['symbol']}({top_long['total_score']:.0f}) SHORT:{top_short['symbol']}({top_short['total_score']:.0f})"
        elif opps:
            top_opp = opps[0]
            title = f"[BUY ALERT] {top_opp['symbol']} — Score {top_opp['total_score']:.0f}/100"
        else:
            top_short = shorts[0]
            title = f"[SHORT ALERT] {top_short['symbol']} — Score {top_short['total_score']:.0f}/100"

        body = f"""## OPPORTUNITY ALERT — Investment Advisor v3.0

### Market Regime
- **Status**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%

---

"""
        # LONG section
        if opps:
            body += "## 📈 LONG OPPORTUNITIES\n\n"
            for opp in opps:
                setup = opp.get("trade_setup", {}) or {}
                breakdown = opp.get("breakdown", {})
                reasoning = opp.get("reasoning", {})
                mc = opp.get('market_cap') or 0

                body += f"""### {opp['symbol']} — Score: {opp['total_score']:.0f}/100

| Metric | Value |
|--------|-------|
| Price | ${opp.get('price', 'N/A')} |
| Market Cap | ${mc/1e9:.1f}B |
| Beta | {opp.get('beta', 'N/A')} |
| Weinstein Stage | {breakdown.get('weinstein_stage', '?')} |

**Committee Breakdown:**
| Component | Score | Max |
|-----------|-------|-----|
| Regime | {breakdown.get('regime', 0)} | 15 |
| Technical (Minervini+Turtles) | {breakdown.get('turtles', 0)} | 25 |
| Trend (Seykota) | {breakdown.get('seykota', 0)} | 20 |
| Catalyst+PEAD+Squeeze | {breakdown.get('catalyst', 0)} | 25 |
| Risk/Reward | {breakdown.get('risk_reward', 0)} | 15 |
"""
                if breakdown.get('sector_adjustment', 0) != 0:
                    body += f"| Sector adjustment | {breakdown.get('sector_adjustment', 0):+d} | — |\n"

                body += "\n**Reasoning:**\n\n"
                for component, reasons in reasoning.items():
                    if reasons:
                        body += f"**{component.capitalize()}:**\n"
                        for reason in reasons:
                            body += f"- {reason}\n"
                        body += "\n"

                body += f"""
**Trade Setup (LONG):**
- **Entry**: ${setup.get('entry', 'N/A')}
- **Stop Loss**: ${setup.get('stop', 'N/A')} (-{setup.get('stop_pct', 'N/A')}%)
- **Take Profit**: ${setup.get('target', 'N/A')} (+{setup.get('target_pct', 'N/A')}%)
- **Risk:Reward**: 1:{setup.get('rr_ratio', 'N/A')}
- **Position**: €{setup.get('position_eur', 0):.0f}

---

"""

        # SHORT section
        if shorts:
            body += "## 📉 SHORT OPPORTUNITIES\n\n"
            for s in shorts:
                setup = s.get("trade_setup") or {}
                breakdown = s.get("breakdown", {})
                reasoning = s.get("reasoning", {})

                body += f"""### {s['symbol']} [SHORT] — Score: {s['total_score']:.0f}/100

**Short Committee Breakdown:**
| Component | Score | Max |
|-----------|-------|-----|
| Regime (inverted) | {breakdown.get('regime', 0)} | 15 |
| Parabolic (Qullamaggie) | {breakdown.get('parabolic', 0)} | 30 |
| Stage 4 Rejection (Weinstein) | {breakdown.get('stage4_rejection', 0)} | 30 |
| PEAD Miss | {breakdown.get('pead_miss', 0)} | 25 |

**Reasoning:**
"""
                for component, reasons in reasoning.items():
                    if reasons:
                        body += f"\n**{component.capitalize()}:**\n"
                        for reason in reasons:
                            body += f"- {reason}\n"

                body += f"""
**Trade Setup (SHORT):**
- **Entry**: ${setup.get('entry', 'N/A')}
- **Stop Loss**: ${setup.get('stop', 'N/A')} (+{setup.get('stop_pct', 'N/A')}% above)
- **Take Profit**: ${setup.get('target', 'N/A')} (-{setup.get('target_pct', 'N/A')}%)
- **Risk:Reward**: 1:{setup.get('rr_ratio', 'N/A')}
- **Position**: €{setup.get('position_eur', 0):.0f}
- **Max hold (eToro fees)**: {setup.get('max_hold_days_before_fees_material', 10)}d

---

"""

        body += """
> **DISCLAIMER**: NOT financial advice. Leveraged trading carries risk of total capital loss.

---
*Auto-generated by Investment Advisor v3.0 (Long+Short)*
"""

    return title, body


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution function."""

    print("\n" + "=" * 60)
    print("INVESTMENT ADVISOR - CATALYST-DRIVEN SWING TRADING")
    print("=" * 60 + "\n")

    scanner = MarketScanner()
    result = scanner.scan_market()

    report = scanner.format_report(result)
    print("\n" + report)

    title, body = create_github_issue_body(result)

    n_longs = len(result.get("opportunities", []))
    n_shorts = len(result.get("short_opportunities", []))
    output = {
        "scan_result": result,
        "issue_title": title,
        "issue_body": body,
        "has_opportunities": n_longs > 0 or n_shorts > 0
    }

    with open("scan_output.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResult saved to scan_output.json")
    print(f"LONG opportunities: {n_longs} | SHORT opportunities: {n_shorts}")

    if n_longs > 0 or n_shorts > 0:
        print("\n** OPPORTUNITIES FOUND - ALERT WILL BE CREATED **")
    else:
        print("\n** NO CLEAR OPPORTUNITIES TODAY **")

    return 0


if __name__ == "__main__":
    sys.exit(main())
