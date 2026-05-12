"""
CATALYST-DRIVEN SWING TRADING ANALYZER
Asesor automatizado para mercados US y EU

Versión 2.0 - Sistema de Comité Virtual con scoring trazable
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Importar el comité virtual (longs y shorts)
from committee import evaluate_opportunity, evaluate_short_opportunity

# ============================================================================
# CONFIGURACION
# ============================================================================

@dataclass
class TradingConfig:
    """Parametros de trading configurables - PROFESIONAL SWING TRADING"""
    capital: float = 500.0
    leverage: int = 5
    max_stop_loss_pct: float = 10.0  # 10% = 50% real con x5 (ajustado para small caps volatiles)
    min_risk_reward: float = 3.0  # Minimo 3:1 R:R obligatorio
    position_size_normal: float = 10.0  # 10% del capital (50EUR = 250EUR exposicion)
    position_size_exceptional: float = 15.0  # Para plays de alta conviccion
    max_concurrent_positions: int = 2  # Max 2 posiciones simultaneas (gestion de riesgo)
    min_holding_days: int = 1  # Permitir day trades
    max_holding_days: int = 14  # Swing trades largos

    # Target basado en % realista (no 52w high)
    target_pct_conservative: float = 15.0  # Target minimo 15%
    target_pct_aggressive: float = 20.0  # Target para setups fuertes

    # Filtros de seleccion - EQUILIBRADOS
    min_market_cap: float = 100_000_000  # $100M (micro caps muy arriesgados)
    max_market_cap: float = 100_000_000_000  # $100B
    min_beta: float = 1.5  # Beta minimo 1.5 para volatilidad necesaria
    preferred_beta: float = 2.0  # Beta preferido
    min_price: float = 2.0  # $2 minimo (evitar penny stocks extremos)
    max_price: float = 500.0
    max_spread_pct: float = 1.0

    # Volumen minimo por market cap - REDUCIDO
    volume_thresholds: dict = None

    def __post_init__(self):
        self.volume_thresholds = {
            "small": 1_000_000,   # $100M-$1B: 1M shares minimo
            "mid": 750_000,       # $1B-$10B: 750K shares
            "large": 500_000      # >$10B: 500K shares
        }

config = TradingConfig()

# ============================================================================
# APIs DE DATOS (Gratuitas)
# ============================================================================

class MarketDataAPI:
    """Wrapper para APIs de datos financieros gratuitas"""

    def __init__(self):
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "")
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", "")
        self.fmp_key = os.getenv("FMP_API_KEY", "")

    def get_market_status(self) -> dict:
        """Obtiene estado general del mercado"""
        result = {
            "vix": None,
            "sp500_change": None,
            "nasdaq_change": None,
            "spy_above_200ema": True,  # Para el detector de régimen
            "market_regime": "UNKNOWN",
            "top_sectors": [],
            "premarket_movers": []
        }

        try:
            # VIX via Yahoo Finance (sin API key)
            vix_data = self._fetch_yahoo_quote("^VIX")
            if vix_data:
                result["vix"] = vix_data.get("price")

            # S&P 500 (SPY como proxy)
            spy_data = self._fetch_yahoo_quote("SPY")
            if spy_data:
                result["sp500_change"] = spy_data.get("change_pct")
                # Verificar si SPY está sobre su EMA 200
                spy_price = spy_data.get("price", 0)
                spy_ema_200 = spy_data.get("ema_200", 0)
                if spy_price > 0 and spy_ema_200 > 0:
                    result["spy_above_200ema"] = spy_price > spy_ema_200
                # SPY precio hace 60 días para cálculo de RS relativa
                result["spy_price"] = spy_price
                result["spy_price_60d_ago"] = spy_data.get("price_60d_ago", spy_price)

            # Nasdaq
            nasdaq_data = self._fetch_yahoo_quote("^IXIC")
            if nasdaq_data:
                result["nasdaq_change"] = nasdaq_data.get("change_pct")

            # Determinar regimen de mercado (legacy - ahora lo hace el comité)
            result["market_regime"] = self._determine_regime(result)

        except Exception as e:
            print(f"Error obteniendo estado de mercado: {e}")

        return result

    def _fetch_yahoo_quote(self, symbol: str) -> Optional[dict]:
        """Fetch quote from Yahoo Finance with historical data for technical indicators"""
        try:
            # Obtener datos históricos de 200 días para calcular EMAs y ATR
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1d", "range": "200d"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9"
            }

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

                # Calcular cambio porcentual
                if prev_close and prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close * 100)
                else:
                    change_pct = 0

                # Extraer precios de cierre históricos
                closes = indicators.get("close", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                volumes = indicators.get("volume", [])

                # Filtrar None values
                closes = [c for c in closes if c is not None]
                highs = [h for h in highs if h is not None]
                lows = [l for l in lows if l is not None]
                volumes = [v for v in volumes if v is not None]

                # Calcular indicadores técnicos
                technical_indicators = self._calculate_technical_indicators(closes, highs, lows, volumes)

                quote = {
                    "symbol": symbol,
                    "price": round(price, 2) if price else 0,
                    "prev_close": round(prev_close, 2) if prev_close else 0,
                    "change_pct": round(change_pct, 2),
                    "_closes_raw": closes  # Para cálculos de RS vs SPY
                }

                # Agregar indicadores técnicos
                quote.update(technical_indicators)

                return quote
            else:
                print(f"[WARN] Yahoo API returned {response.status_code} for {symbol}")

        except requests.exceptions.Timeout:
            print(f"[WARN] Timeout fetching {symbol}")
        except Exception as e:
            print(f"[ERROR] Fetching {symbol}: {e}")

        return None

    def _calculate_technical_indicators(self, closes: list, highs: list, lows: list, volumes: list) -> dict:
        """Calcula indicadores técnicos necesarios para el comité"""
        if not closes or len(closes) < 20:
            return {}

        indicators = {}

        # High de 20 días
        if len(highs) >= 20:
            indicators["high_20d"] = max(highs[-20:])

        # Precios históricos para momentum y parabolic detection
        if len(closes) >= 6:
            indicators["price_5d_ago"] = closes[-6]
        if len(closes) >= 11:
            indicators["price_10d_ago"] = closes[-11]
        if len(closes) >= 21:
            indicators["price_20d_ago"] = closes[-21]
        if len(closes) >= 61:
            indicators["price_60d_ago"] = closes[-61]

        # Volumen promedio de 20 días
        if len(volumes) >= 20:
            indicators["avg_volume_20d"] = sum(volumes[-20:]) / 20
            indicators["volume"] = volumes[-1] if volumes else 0

        # EMA 20
        if len(closes) >= 20:
            indicators["ema_20"] = self._calculate_ema(closes, 20)

        # EMA 50
        if len(closes) >= 50:
            indicators["ema_50"] = self._calculate_ema(closes, 50)

        # EMA 200
        if len(closes) >= 200:
            indicators["ema_200"] = self._calculate_ema(closes, 200)

        # SMA 150 (Weinstein 30-week MA) — distingue Stage 2 de Stage 4
        if len(closes) >= 150:
            indicators["sma_150"] = self._calculate_sma(closes, 150)
            # SMA 150 de hace 20 días para detectar dirección (rising/declining)
            if len(closes) >= 170:
                indicators["sma_150_20d_ago"] = self._calculate_sma(closes[:-20], 150)

        # ATR 14
        if len(closes) >= 14 and len(highs) >= 14 and len(lows) >= 14:
            indicators["atr_14"] = self._calculate_atr(closes, highs, lows, 14)

        # RSI 14 — para detección parabólica (RSI > 80 = overbought extremo)
        if len(closes) >= 15:
            indicators["rsi_14"] = self._calculate_rsi(closes, 14)

        return indicators

    def _calculate_sma(self, prices: list, period: int) -> float:
        """Calcula SMA (Simple Moving Average)"""
        if len(prices) < period:
            return 0
        return round(sum(prices[-period:]) / period, 2)

    def _calculate_rsi(self, closes: list, period: int = 14) -> float:
        """Calcula RSI (Relative Strength Index)"""
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
        """Calcula EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return 0

        # Multiplier: 2 / (period + 1)
        multiplier = 2.0 / (period + 1)

        # Inicializar EMA con SMA del primer periodo
        sma = sum(prices[:period]) / period
        ema = sma

        # Calcular EMA para el resto
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return round(ema, 2)

    def _calculate_atr(self, closes: list, highs: list, lows: list, period: int = 14) -> float:
        """Calcula ATR (Average True Range)"""
        if len(closes) < period + 1 or len(highs) < period or len(lows) < period:
            return 0

        true_ranges = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i-1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # ATR es el promedio de los últimos 'period' true ranges
        if len(true_ranges) >= period:
            atr = sum(true_ranges[-period:]) / period
            return round(atr, 2)

        return 0

    def _determine_regime(self, market_data: dict) -> str:
        """Determina el regimen de mercado actual"""
        vix = market_data.get("vix")
        sp500 = market_data.get("sp500_change")

        if vix is None:
            return "UNKNOWN"

        if vix > 25:
            return "RISK-OFF (Alta volatilidad)"
        elif vix < 15 and sp500 and sp500 > 0:
            return "RISK-ON (Baja volatilidad, mercado alcista)"
        elif vix < 20:
            return "NEUTRAL"
        else:
            return "CAUTELA (Volatilidad moderada-alta)"

    def get_stock_data(self, symbol: str, market_status: dict = None) -> Optional[dict]:
        """Obtiene datos completos de una accion"""
        quote = self._fetch_yahoo_quote(symbol)
        if not quote:
            return None

        # Limpiar campo interno de datos raw (solo para cálculos internos)
        quote.pop("_closes_raw", None)

        # Obtener datos adicionales de Yahoo
        yahoo_data_ok = self._fetch_yahoo_details(quote, symbol)

        # Si Yahoo fallo y tenemos Finnhub, usar como fallback
        if not yahoo_data_ok and self.finnhub_key:
            self._fetch_finnhub_details(quote, symbol)

        # Earnings surprise para PEAD (si tenemos Finnhub key)
        if self.finnhub_key:
            earnings_data = self.get_earnings_surprise(symbol)
            quote.update(earnings_data)

        # Propagar datos del mercado para RS vs SPY (turtles Minervini)
        if market_status:
            quote["spy_price_60d_ago"] = market_status.get("spy_price_60d_ago", 0)
            quote["spy_price"] = market_status.get("spy_price", 0)

        return quote

    def _fetch_yahoo_details(self, quote: dict, symbol: str) -> bool:
        """Obtiene datos adicionales de Yahoo Finance. Retorna True si tuvo exito."""
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

                    # Verificar si obtuvimos datos utiles
                    if quote.get("market_cap") or quote.get("52w_high"):
                        return True

        except Exception as e:
            print(f"[WARN] Yahoo details failed for {symbol}: {e}")

        return False

    def _fetch_finnhub_details(self, quote: dict, symbol: str) -> bool:
        """Obtiene datos de Finnhub como fallback. Retorna True si tuvo exito."""
        if not self.finnhub_key:
            return False

        try:
            # Obtener perfil de la empresa (market cap)
            url = f"https://finnhub.io/api/v1/stock/profile2"
            params = {"symbol": symbol, "token": self.finnhub_key}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data:
                    quote["market_cap"] = data.get("marketCapitalization", 0) * 1e6  # Finnhub da en millones
                    quote["beta"] = data.get("beta")

            # Obtener metricas basicas
            url = f"https://finnhub.io/api/v1/stock/metric"
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
                        quote["revenue_growth"] = quote["revenue_growth"] / 100  # Convertir a decimal

            return quote.get("market_cap") is not None

        except Exception as e:
            print(f"[WARN] Finnhub details failed for {symbol}: {e}")

        return False

    def get_earnings_surprise(self, symbol: str) -> dict:
        """
        Obtiene el earnings surprise del último trimestre para PEAD scoring.
        Requiere Finnhub API key.

        Returns dict con: eps_surprise_pct, earnings_reaction_pct, days_since_earnings,
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

            # Usar el último trimestre reportado
            latest = data[0]
            actual = latest.get("actual")
            estimate = latest.get("estimate")
            period = latest.get("period", "")  # "YYYY-MM-DD"

            if actual is None or estimate is None or estimate == 0:
                return result

            # EPS surprise %: positivo = beat, negativo = miss
            result["eps_surprise_pct"] = round((actual - estimate) / abs(estimate) * 100, 1)

            # Días desde earnings
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
        """Obtiene calendario de earnings proximos"""
        earnings = []

        # Usar Finnhub si hay API key
        if self.finnhub_key:
            try:
                today = datetime.now()
                from_date = today.strftime("%Y-%m-%d")
                to_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

                url = "https://finnhub.io/api/v1/calendar/earnings"
                params = {
                    "from": from_date,
                    "to": to_date,
                    "token": self.finnhub_key
                }

                response = requests.get(url, params=params, timeout=10, proxies={'http': None, 'https': None})
                if response.status_code == 200:
                    data = response.json()
                    earnings = data.get("earningsCalendar", [])

            except Exception as e:
                print(f"Error obteniendo calendario de earnings: {e}")

        return earnings

    def get_news_sentiment(self, symbol: str) -> dict:
        """Obtiene sentimiento de noticias recientes"""
        sentiment = {"score": 0, "articles": 0, "positive": 0, "negative": 0}

        if self.finnhub_key:
            try:
                today = datetime.now()
                from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
                to_date = today.strftime("%Y-%m-%d")

                url = "https://finnhub.io/api/v1/company-news"
                params = {
                    "symbol": symbol,
                    "from": from_date,
                    "to": to_date,
                    "token": self.finnhub_key
                }

                response = requests.get(url, params=params, timeout=10, proxies={'http': None, 'https': None})
                if response.status_code == 200:
                    articles = response.json()
                    sentiment["articles"] = len(articles)

            except Exception as e:
                print(f"Error obteniendo noticias de {symbol}: {e}")

        return sentiment


# ============================================================================
# MOTOR DE SCORING - COMITÉ VIRTUAL
# ============================================================================

class OpportunityScorer:
    """Sistema de puntuación de oportunidades de LONG usando el Comité Virtual"""

    def __init__(self, api: MarketDataAPI, market_status: dict):
        self.api = api
        self.market_status = market_status

    def score_opportunity(self, symbol: str, catalyst_info: dict = None, stock_data: dict = None) -> dict:
        """Evalúa y puntúa una oportunidad de LONG usando el comité"""

        if stock_data is None:
            stock_data = self.api.get_stock_data(symbol, self.market_status)
        if not stock_data:
            return {"symbol": symbol, "score": 0, "error": "No se pudo obtener datos"}

        # Verificar filtros de exclusión básicos primero
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

        # Llamar al comité virtual para evaluar
        evaluation = evaluate_opportunity(
            ticker=symbol,
            ticker_data=stock_data,
            market_data=self.market_status,
            catalyst_info=catalyst_info,
            capital=config.capital,
            leverage=config.leverage
        )

        # Adaptar formato para compatibilidad con código existente
        return {
            "symbol": symbol,
            "price": stock_data.get("price"),
            "market_cap": stock_data.get("market_cap"),
            "beta": stock_data.get("beta"),
            "volume": stock_data.get("avg_volume"),
            "total_score": evaluation["final_score"],
            "signal": "COMPRA" if evaluation["decision"] == "BUY" else evaluation["decision"],
            "exclusion_reason": None if evaluation["decision"] in ["BUY", "WATCHLIST"] else evaluation["decision_reason"],
            "trade_setup": evaluation["trade_params"] if evaluation["decision"] == "BUY" else None,
            # Nuevos campos del comité
            "committee_evaluation": evaluation,
            "breakdown": evaluation["breakdown"],
            "reasoning": evaluation["reasoning"]
        }


    def _check_exclusions(self, stock_data: dict, direction: str = "LONG") -> Optional[str]:
        """Verifica criterios de exclusion"""
        price = stock_data.get("price", 0)
        market_cap = stock_data.get("market_cap", 0)
        avg_volume = stock_data.get("avg_volume", 0)
        beta = stock_data.get("beta")

        if price and price < config.min_price:
            return f"Penny stock (${price} < ${config.min_price})"

        if price and price > config.max_price:
            return f"Precio muy alto (${price} > ${config.max_price})"

        if market_cap:
            if market_cap < config.min_market_cap:
                return f"Market cap muy bajo (${market_cap/1e6:.0f}M < ${config.min_market_cap/1e6:.0f}M)"
            if market_cap > config.max_market_cap:
                return f"Mega cap (${market_cap/1e9:.0f}B > ${config.max_market_cap/1e9:.0f}B)"

        if beta and beta < config.min_beta:
            return f"Beta muy bajo ({beta:.2f} < {config.min_beta})"

        # Verificar volumen segun market cap
        if market_cap and avg_volume:
            if market_cap < 1e9:  # Small cap $100M-$1B
                if avg_volume < config.volume_thresholds["small"]:
                    return f"Volumen insuficiente para small cap ({avg_volume/1e6:.1f}M < {config.volume_thresholds['small']/1e6:.1f}M)"
            elif market_cap < 10e9:  # Mid cap $1B-$10B
                if avg_volume < config.volume_thresholds["mid"]:
                    return f"Volumen insuficiente para mid cap"
            else:  # Large cap >$10B
                if avg_volume < config.volume_thresholds["large"]:
                    return f"Volumen insuficiente para large cap"

        return None


class ShortOpportunityScorer:
    """Sistema de puntuación de oportunidades de SHORT usando el Comité de Cortos"""

    def __init__(self, api: MarketDataAPI, market_status: dict):
        self.api = api
        self.market_status = market_status

    def score_short_opportunity(self, symbol: str, stock_data: dict, catalyst_info: dict = None) -> dict:
        """
        Evalúa una oportunidad de SHORT usando el comité de cortos.
        Recibe stock_data ya cargado (compartido con el scorer de longs).
        """
        if not stock_data:
            return {"symbol": symbol, "score": 0, "error": "Sin datos"}

        # Filtros básicos para shorts: no shortear micro caps ilíquidas
        price = stock_data.get("price", 0)
        market_cap = stock_data.get("market_cap", 0)
        avg_volume = stock_data.get("avg_volume", stock_data.get("avg_volume_20d", 0))

        if price and price < 3:
            return {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT",
                    "exclusion_reason": f"Precio muy bajo para short (${price})"}

        if market_cap and market_cap < 50_000_000:
            return {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT",
                    "exclusion_reason": "Market cap demasiado bajo para short seguro"}

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
# SCANNER DE MERCADO
# ============================================================================

class MarketScanner:
    """Escaner de oportunidades en el mercado"""

    # =========================================================================
    # WATCHLIST AMPLIADA - ALTO POTENCIAL DE CRECIMIENTO
    # =========================================================================

    # High-Growth Tech & AI
    WATCHLIST_TECH_AI = [
        "NVDA", "AMD", "SMCI", "ARM", "AVGO", "MRVL", "MU",  # Semiconductores AI
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

    # Small/Mid Caps con Momentum - Limpiado tickers muertos
    WATCHLIST_SMALL_MID_CAPS = [
        "APLD", "BTBT", "WULF", "CIFR", "IREN",  # Bitcoin miners
        "GEVO", "BE", "PLUG", "FCEL", "BLDP",  # Clean energy
        "JOBY", "ACHR", "LILM", "EVTL",  # eVTOL/Air taxis
        "DNA", "CRSP", "BEAM", "EDIT", "NTLA",  # Gene editing
        "RXRX", "SDGR", "ABCL",  # AI Biotech (EXAI delisted)
        "XMTR", "PRNT", "NNDM", "SSYS",  # 3D Printing (VLD, DM delisted)
        "OPEN", "CVNA", "CARG", "CHPT",  # Real estate/auto/EV (RDFN delisted)
        "ASTS", "IRDM", "GSAT",  # Satellite/Space
    ]

    # Biotech Especulativos (alto riesgo/alta recompensa) - Limpiado
    WATCHLIST_BIOTECH_SPECULATIVE = [
        "MRNA", "BNTX", "NVAX",  # Vacunas
        "SAVA", "ACIU", "PRTA",  # Alzheimer
        "SRPT", "VRTX",  # Gene therapy (BLUE delisted)
        "IONS", "ALNY", "ARWR",  # RNA therapeutics
        "AXSM", "CPRX",  # CNS (SAGE issues)
        "PTGX", "KRYS", "IMVT", "MDGL",  # Small cap biotech (KRTX delisted)
    ]

    # High Short Interest (potencial squeeze) - Limpiado tickers muertos
    WATCHLIST_HIGH_SHORT = [
        "GME", "AMC", "KOSS",  # Meme classics (BBBY delisted)
        "BYND", "LMND",  # High short growth (CVNA/UPST ya en otra lista)
        "GOEV", "WKHS",  # EV shorts (FFIE, RIDE delisted)
        "SPCE", "LAZR",  # Tech shorts (VLDR delisted)
    ]

    # IPOs Recientes y Growth Stories
    WATCHLIST_RECENT_IPOS = [
        "RDDT", "DUOL", "CART", "TOST",  # Recent tech IPOs
        "KVYO", "BIRK", "ONON", "CAVA",  # Consumer
        "VRT", "INTA", "IOT",  # Enterprise
        "GRAB", "SE", "BABA", "JD", "PDD",  # Asian growth
    ]

    # Principales europeas en eToro
    WATCHLIST_EU = [
        "ASML", "SAP", "NVO",  # Large caps
        "SPOT", "FVRR", "WIX",  # Tech EU/Israel
    ]

    # =========================================================================
    # COMPILAR WATCHLIST COMPLETA
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
        self.scorer = None  # Se inicializa en scan_market con market_status
        self.earnings_calendar = {}  # Cache de earnings

    def _load_earnings_calendar(self):
        """Carga el calendario de earnings para los proximos 14 dias"""
        print("  Cargando calendario de earnings...")
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
                    except:
                        pass

        print(f"  Earnings encontrados: {len(self.earnings_calendar)} acciones con earnings proximos")

    def scan_market(self, watchlist: list = None) -> dict:
        """Escanea el mercado en busca de oportunidades"""

        if watchlist is None:
            watchlist = self.DEFAULT_WATCHLIST_US + self.DEFAULT_WATCHLIST_EU

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando scan de mercado...")
        print(f"Analizando {len(watchlist)} acciones...")

        # 1. Estado del mercado
        market_status = self.api.get_market_status()
        print(f"\nREGIMEN DE MERCADO: {market_status['market_regime']}")
        print(f"VIX: {market_status.get('vix', 'N/A')}")
        print(f"S&P 500: {market_status.get('sp500_change', 'N/A')}%")
        print(f"Nasdaq: {market_status.get('nasdaq_change', 'N/A')}%")
        print(f"SPY sobre 200 EMA: {market_status.get('spy_above_200ema', 'N/A')}")

        # 2. Inicializar scorers con market status (long y short)
        self.scorer = OpportunityScorer(self.api, market_status)
        self.short_scorer = ShortOpportunityScorer(self.api, market_status)

        # 3. Cargar calendario de earnings (catalizadores)
        self._load_earnings_calendar()

        # 3. Escanear watchlist en paralelo (LONG + SHORT simultáneamente)
        opportunities = []
        watchlist_items = []
        skipped = []
        short_opportunities = []
        short_watchlist = []
        print_lock = threading.Lock()

        def scan_symbol(symbol: str) -> dict:
            catalyst_info = self.earnings_calendar.get(symbol)
            # Cargar datos una sola vez y reutilizarlos para long y short
            stock_data = self.api.get_stock_data(symbol, market_status)
            result_long = self.scorer.score_opportunity(symbol, catalyst_info, stock_data) if stock_data else \
                {"symbol": symbol, "total_score": 0, "signal": "SKIP", "error": "Sin datos"}
            result_short = self.short_scorer.score_short_opportunity(symbol, stock_data, catalyst_info) \
                if stock_data else {"symbol": symbol, "total_score": 0, "signal": "SKIP_SHORT"}
            return {
                "symbol": symbol,
                "catalyst_info": catalyst_info,
                "long": result_long,
                "short": result_short
            }

        # 5 workers: balance velocidad / rate limiting Yahoo Finance + Finnhub
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

                    # Procesar LONG
                    if not result.get("error"):
                        score = result.get("total_score", 0)
                        signal = result.get("signal", "SKIP")
                        catalyst_tag = f"[EARNINGS {catalyst_info['days_ahead']}d] " if catalyst_info else ""
                        short_score = result_short.get("total_score", 0)
                        short_signal = result_short.get("signal", "SKIP_SHORT")
                        short_tag = f"| SHORT:{short_score:.0f}" if short_score >= 40 else ""

                        with print_lock:
                            print(f"  [{completed}/{len(watchlist)}] {symbol} {catalyst_tag}"
                                  f"L:{score:.0f}({signal}) {short_tag}")

                        if signal == "COMPRA":
                            opportunities.append(result)
                        elif signal == "WATCHLIST":
                            watchlist_items.append(result)
                        else:
                            skipped.append(result)

                    # Procesar SHORT
                    short_sig = result_short.get("signal", "SKIP_SHORT")
                    if short_sig == "SHORT":
                        short_opportunities.append(result_short)
                    elif short_sig == "WATCHLIST_SHORT":
                        short_watchlist.append(result_short)

                except Exception as e:
                    sym = futures[future]
                    with print_lock:
                        print(f"  {sym}: EXCEPCION: {e}")

        # Ordenar por score
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
        """Formatea el resultado del scan en un reporte legible"""

        report = []
        report.append("=" * 60)
        report.append("REPORTE DE OPORTUNIDADES DE INVERSION")
        report.append(f"Generado: {scan_result['timestamp']}")
        report.append("=" * 60)

        # Regimen de mercado
        ms = scan_result["market_status"]
        report.append(f"\n## REGIMEN DE MERCADO")
        report.append(f"Estado: {ms.get('market_regime', 'N/A')}")
        report.append(f"VIX: {ms.get('vix', 'N/A')}")
        report.append(f"S&P 500: {ms.get('sp500_change', 'N/A')}%")
        report.append(f"Nasdaq: {ms.get('nasdaq_change', 'N/A')}%")

        # Oportunidades de compra
        opps = scan_result.get("opportunities", [])
        if opps:
            report.append(f"\n## OPORTUNIDADES DE COMPRA ({len(opps)})")
            report.append("-" * 40)

            for opp in opps:
                report.append(self._format_opportunity(opp))
        else:
            report.append("\n## NO HAY OPORTUNIDADES CLARAS HOY")
            report.append("Mejor no operar que forzar un trade mediocre.")

        # Watchlist
        watch = scan_result.get("watchlist", [])
        if watch:
            report.append(f"\n## WATCHLIST ({len(watch)})")
            report.append("-" * 40)
            for item in watch[:5]:
                report.append(f"- {item['symbol']}: Score {item['total_score']:.0f} | ${item.get('price', 'N/A')}")

        # Oportunidades de SHORT
        shorts = scan_result.get("short_opportunities", [])
        if shorts:
            report.append(f"\n## OPORTUNIDADES EN CORTO ({len(shorts)})")
            report.append("-" * 40)
            for s in shorts:
                report.append(self._format_short_opportunity(s))

        short_watch = scan_result.get("short_watchlist", [])
        if short_watch:
            report.append(f"\n## WATCHLIST CORTOS ({len(short_watch)})")
            report.append("-" * 40)
            for item in short_watch[:5]:
                report.append(f"- {item['symbol']}: Score {item['total_score']:.0f} | ${item.get('price', 'N/A')}")

        # Resumen
        report.append(f"\n## RESUMEN")
        report.append(f"Acciones analizadas: {scan_result['total_scanned']}")
        report.append(f"Oportunidades LONG: {scan_result['opportunities_found']}")
        report.append(f"Oportunidades SHORT: {scan_result.get('short_opportunities_found', 0)}")
        report.append(f"En watchlist long: {scan_result['watchlist_count']}")
        report.append(f"En watchlist short: {scan_result.get('short_watchlist_count', 0)}")

        report.append("\n" + "=" * 60)
        report.append("DISCLAIMER: Esto NO es consejo financiero. Opera bajo tu propio riesgo.")
        report.append("=" * 60)

        return "\n".join(report)

    def _format_short_opportunity(self, opp: dict) -> str:
        """Formatea una oportunidad de short individual"""
        lines = []
        lines.append(f"\n### {opp['symbol']} [CORTO]")
        lines.append(f"**Score: {opp['total_score']:.0f}/100** | **Señal: {opp['signal']}**")
        lines.append(f"\nPrecio: ${opp.get('price', 'N/A')}")

        breakdown = opp.get("breakdown", {})
        if breakdown:
            lines.append(f"\n**Desglose del Comité de Cortos:**")
            lines.append(f"  Régimen (inverso): {breakdown.get('regime', 0)}/15")
            lines.append(f"  Parabólico (Qullamaggie): {breakdown.get('parabolic', 0)}/30")
            lines.append(f"  Stage 4 Rejection (Weinstein): {breakdown.get('stage4_rejection', 0)}/30")
            lines.append(f"  PEAD Miss (académico): {breakdown.get('pead_miss', 0)}/25")

        reasoning = opp.get("reasoning", {})
        if reasoning:
            lines.append(f"\n**Razonamiento:**")
            for component, reasons in reasoning.items():
                if reasons:
                    lines.append(f"\n*{component.capitalize()}:*")
                    for r in reasons:
                        lines.append(f"  {r}")

        setup = opp.get("trade_setup")
        if setup:
            lines.append(f"\n**Trade Setup (CORTO):**")
            lines.append(f"  Entry: ${setup.get('entry', 'N/A')}")
            lines.append(f"  Stop Loss: ${setup.get('stop', 'N/A')} (+{setup.get('stop_pct', 'N/A')}% arriba)")
            lines.append(f"  Take Profit: ${setup.get('target', 'N/A')} (-{setup.get('target_pct', 'N/A')}%)")
            lines.append(f"  Risk:Reward: 1:{setup.get('rr_ratio', 'N/A')}")
            lines.append(f"  Position: €{setup.get('position_eur', 0):.0f}")
            max_days = setup.get("max_hold_days_before_fees_material", 10)
            lines.append(f"  Max días recomendado (fees eToro): {max_days}d")

        return "\n".join(lines)

    def _format_opportunity(self, opp: dict) -> str:
        """Formatea una oportunidad individual con reasoning del comité"""
        lines = []

        lines.append(f"\n### {opp['symbol']}")
        lines.append(f"**Score: {opp['total_score']:.0f}/100** | **Señal: {opp['signal']}**")

        # Métricas básicas
        lines.append(f"\nPrecio: ${opp.get('price', 'N/A')}")
        mc = opp.get('market_cap')
        if mc:
            if mc >= 1e9:
                lines.append(f"Market Cap: ${mc/1e9:.1f}B")
            else:
                lines.append(f"Market Cap: ${mc/1e6:.0f}M")
        lines.append(f"Beta: {opp.get('beta', 'N/A')}")

        # Breakdown del Comité
        breakdown = opp.get("breakdown", {})
        if breakdown:
            lines.append(f"\n**Desglose del Comité:**")
            lines.append(f"  Régimen: {breakdown.get('regime', 0)}/15")
            lines.append(f"  Turtles (técnico): {breakdown.get('turtles', 0)}/25")
            lines.append(f"  Seykota (tendencia): {breakdown.get('seykota', 0)}/20")
            lines.append(f"  Catalizador: {breakdown.get('catalyst', 0)}/25")
            lines.append(f"  Risk/Reward: {breakdown.get('risk_reward', 0)}/15")
            if breakdown.get('sector_adjustment', 0) != 0:
                lines.append(f"  Ajuste sector: {breakdown.get('sector_adjustment', 0):+d}")

        # Reasoning detallado
        reasoning = opp.get("reasoning", {})
        if reasoning:
            lines.append(f"\n**Razonamiento detallado:**")

            for component, reasons in reasoning.items():
                if reasons:
                    component_name = component.capitalize()
                    lines.append(f"\n*{component_name}:*")
                    for reason in reasons:
                        lines.append(f"  {reason}")

        # Trade setup
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
# GENERADOR DE ALERTAS PARA GITHUB ISSUES
# ============================================================================

def create_github_issue_body(scan_result: dict) -> tuple:
    """Genera titulo y cuerpo para GitHub Issue de alerta"""

    opps = scan_result.get("opportunities", [])
    ms = scan_result.get("market_status", {})

    shorts = scan_result.get("short_opportunities", [])
    has_any = bool(opps or shorts)

    if not has_any:
        title = f"[MARKET SCAN] {datetime.now().strftime('%Y-%m-%d %H:%M')} - Sin oportunidades"
        body = f"""## Scan de Mercado - {datetime.now().strftime('%Y-%m-%d %H:%M')}

### Regimen de Mercado
- **Estado**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%
- **Nasdaq**: {ms.get('nasdaq_change', 'N/A')}%

### Resultado
**No se encontraron oportunidades long ni short que cumplan los criterios de calidad.**

> Mejor no operar que forzar un trade mediocre.

---
*Generado automaticamente por Investment Advisor v3.0 (Long+Short)*
"""
    else:
        # Título: mencionar la oportunidad más destacada
        if opps and shorts:
            top_long = opps[0]
            top_short = shorts[0]
            title = f"[ALERTA] LONG:{top_long['symbol']}({top_long['total_score']:.0f}) SHORT:{top_short['symbol']}({top_short['total_score']:.0f})"
        elif opps:
            top_opp = opps[0]
            title = f"[ALERTA COMPRA] {top_opp['symbol']} - Score {top_opp['total_score']:.0f}/100"
        else:
            top_short = shorts[0]
            title = f"[ALERTA CORTO] {top_short['symbol']} - Score {top_short['total_score']:.0f}/100"

        body = f"""## ALERTA DE OPORTUNIDAD — Investment Advisor v3.0

### Regimen de Mercado
- **Estado**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%

---

"""
        # Sección LONG
        if opps:
            body += "## 📈 OPORTUNIDADES LONG\n\n"
            for opp in opps:
                setup = opp.get("trade_setup", {}) or {}
                breakdown = opp.get("breakdown", {})
                reasoning = opp.get("reasoning", {})
                mc = opp.get('market_cap') or 0

                body += f"""### {opp['symbol']} — Score: {opp['total_score']:.0f}/100

| Métrica | Valor |
|---------|-------|
| Precio | ${opp.get('price', 'N/A')} |
| Market Cap | ${mc/1e9:.1f}B |
| Beta | {opp.get('beta', 'N/A')} |
| Weinstein Stage | {breakdown.get('weinstein_stage', '?')} |

**Desglose del Comité:**
| Componente | Score | Max |
|------------|-------|-----|
| Régimen | {breakdown.get('regime', 0)} | 15 |
| Técnico (Minervini+Turtles) | {breakdown.get('turtles', 0)} | 25 |
| Tendencia (Seykota) | {breakdown.get('seykota', 0)} | 20 |
| Catalizador+PEAD+Squeeze | {breakdown.get('catalyst', 0)} | 25 |
| Risk/Reward | {breakdown.get('risk_reward', 0)} | 15 |
"""
                if breakdown.get('sector_adjustment', 0) != 0:
                    body += f"| Ajuste sector | {breakdown.get('sector_adjustment', 0):+d} | — |\n"

                body += "\n**Razonamiento:**\n\n"
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

        # Sección SHORT
        if shorts:
            body += "## 📉 OPORTUNIDADES SHORT\n\n"
            for s in shorts:
                setup = s.get("trade_setup") or {}
                breakdown = s.get("breakdown", {})
                reasoning = s.get("reasoning", {})

                body += f"""### {s['symbol']} [CORTO] — Score: {s['total_score']:.0f}/100

**Desglose del Comité de Cortos:**
| Componente | Score | Max |
|------------|-------|-----|
| Régimen (inverso) | {breakdown.get('regime', 0)} | 15 |
| Parabólico (Qullamaggie) | {breakdown.get('parabolic', 0)} | 30 |
| Stage 4 Rejection (Weinstein) | {breakdown.get('stage4_rejection', 0)} | 30 |
| PEAD Miss (académico) | {breakdown.get('pead_miss', 0)} | 25 |

**Razonamiento:**
"""
                for component, reasons in reasoning.items():
                    if reasons:
                        body += f"\n**{component.capitalize()}:**\n"
                        for reason in reasons:
                            body += f"- {reason}\n"

                body += f"""
**Trade Setup (CORTO):**
- **Entry**: ${setup.get('entry', 'N/A')}
- **Stop Loss**: ${setup.get('stop', 'N/A')} (+{setup.get('stop_pct', 'N/A')}% arriba)
- **Take Profit**: ${setup.get('target', 'N/A')} (-{setup.get('target_pct', 'N/A')}%)
- **Risk:Reward**: 1:{setup.get('rr_ratio', 'N/A')}
- **Position**: €{setup.get('position_eur', 0):.0f}
- **Max días (fees eToro)**: {setup.get('max_hold_days_before_fees_material', 10)}d

---

"""

        body += """
> **DISCLAIMER**: Esto NO es consejo financiero. Trading con apalancamiento conlleva riesgo de pérdida total del capital.

---
*Generado automaticamente por Investment Advisor v3.0 (Long+Short)*
"""

    return title, body


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Funcion principal de ejecucion"""

    print("\n" + "=" * 60)
    print("INVESTMENT ADVISOR - CATALYST-DRIVEN SWING TRADING")
    print("=" * 60 + "\n")

    # Crear scanner y ejecutar analisis
    scanner = MarketScanner()
    result = scanner.scan_market()

    # Generar reporte
    report = scanner.format_report(result)
    print("\n" + report)

    # Generar contenido para GitHub Issue
    title, body = create_github_issue_body(result)

    # Guardar resultado como JSON para el workflow
    n_longs = len(result.get("opportunities", []))
    n_shorts = len(result.get("short_opportunities", []))
    output = {
        "scan_result": result,
        "issue_title": title,
        "issue_body": body,
        "has_opportunities": n_longs > 0 or n_shorts > 0
    }

    # Escribir a archivo para que el workflow lo use
    with open("scan_output.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResultado guardado en scan_output.json")
    print(f"Oportunidades LONG: {n_longs} | Oportunidades SHORT: {n_shorts}")

    # Exit code basado en si hay oportunidades (long o short)
    if n_longs > 0 or n_shorts > 0:
        print("\n** HAY OPORTUNIDADES - SE CREARA ALERTA **")
        return 0
    else:
        print("\n** SIN OPORTUNIDADES CLARAS HOY **")
        return 0


if __name__ == "__main__":
    sys.exit(main())
