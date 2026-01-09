"""
CATALYST-DRIVEN SWING TRADING ANALYZER
Asesor automatizado para mercados US y EU
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import sys

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
            "market_regime": "UNKNOWN",
            "top_sectors": [],
            "premarket_movers": []
        }

        try:
            # VIX via Yahoo Finance (sin API key)
            vix_data = self._fetch_yahoo_quote("^VIX")
            if vix_data:
                result["vix"] = vix_data.get("price")

            # S&P 500
            sp500_data = self._fetch_yahoo_quote("^GSPC")
            if sp500_data:
                result["sp500_change"] = sp500_data.get("change_pct")

            # Nasdaq
            nasdaq_data = self._fetch_yahoo_quote("^IXIC")
            if nasdaq_data:
                result["nasdaq_change"] = nasdaq_data.get("change_pct")

            # Determinar regimen de mercado
            result["market_regime"] = self._determine_regime(result)

        except Exception as e:
            print(f"Error obteniendo estado de mercado: {e}")

        return result

    def _fetch_yahoo_quote(self, symbol: str) -> Optional[dict]:
        """Fetch quote from Yahoo Finance"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": "1d", "range": "5d"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9"
            }

            response = requests.get(url, params=params, headers=headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                chart_result = data.get("chart", {}).get("result")

                if not chart_result or len(chart_result) == 0:
                    print(f"[WARN] No data for {symbol}")
                    return None

                result = chart_result[0]
                meta = result.get("meta", {})

                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("previousClose", 0) or meta.get("chartPreviousClose", 0)

                # Calcular cambio porcentual
                if prev_close and prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close * 100)
                else:
                    change_pct = 0

                return {
                    "symbol": symbol,
                    "price": round(price, 2) if price else 0,
                    "prev_close": round(prev_close, 2) if prev_close else 0,
                    "change_pct": round(change_pct, 2)
                }
            else:
                print(f"[WARN] Yahoo API returned {response.status_code} for {symbol}")

        except requests.exceptions.Timeout:
            print(f"[WARN] Timeout fetching {symbol}")
        except Exception as e:
            print(f"[ERROR] Fetching {symbol}: {e}")

        return None

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

    def get_stock_data(self, symbol: str) -> Optional[dict]:
        """Obtiene datos completos de una accion"""
        quote = self._fetch_yahoo_quote(symbol)
        if not quote:
            return None

        # Intentar obtener datos adicionales de Yahoo
        yahoo_data_ok = self._fetch_yahoo_details(quote, symbol)

        # Si Yahoo fallo y tenemos Finnhub, usar como fallback
        if not yahoo_data_ok and self.finnhub_key:
            self._fetch_finnhub_details(quote, symbol)

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

            response = requests.get(url, params=params, headers=headers, timeout=15)
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

                response = requests.get(url, params=params, timeout=10)
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

                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    articles = response.json()
                    sentiment["articles"] = len(articles)

            except Exception as e:
                print(f"Error obteniendo noticias de {symbol}: {e}")

        return sentiment


# ============================================================================
# MOTOR DE SCORING
# ============================================================================

class OpportunityScorer:
    """Sistema de puntuacion de oportunidades"""

    def __init__(self, api: MarketDataAPI):
        self.api = api

    def score_opportunity(self, symbol: str, catalyst_info: dict = None) -> dict:
        """Evalua y puntua una oportunidad de trading"""

        stock_data = self.api.get_stock_data(symbol)
        if not stock_data:
            return {"symbol": symbol, "score": 0, "error": "No se pudo obtener datos"}

        scores = {
            "timing": self._score_timing(catalyst_info),
            "technical": self._score_technical(stock_data),
            "risk_reward": self._score_risk_reward(stock_data),
            "fundamental": self._score_fundamental(stock_data),
            "catalyst": self._score_catalyst(catalyst_info)
        }

        total_score = sum(scores.values())
        final_score = (total_score / 25) * 100

        # Verificar filtros de exclusion
        exclusion_reason = self._check_exclusions(stock_data)

        # Calcular trade setup solo para candidatos de alta puntuacion
        trade_setup = None
        if final_score >= 72 and not exclusion_reason:
            trade_setup = self._calculate_trade_setup(stock_data)

        # Determinar senal: COMPRA requiere score alto + sin exclusion + R:R valido
        if final_score >= 72 and not exclusion_reason and trade_setup:
            signal = "COMPRA"
        elif final_score >= 72 and not exclusion_reason and not trade_setup:
            signal = "WATCHLIST"  # Score alto pero R:R insuficiente
            exclusion_reason = "R:R insuficiente (< 3:1)"
        elif final_score >= 56:
            signal = "WATCHLIST"
        else:
            signal = "SKIP"

        return {
            "symbol": symbol,
            "price": stock_data.get("price"),
            "market_cap": stock_data.get("market_cap"),
            "beta": stock_data.get("beta"),
            "volume": stock_data.get("avg_volume"),
            "scores": scores,
            "total_score": round(final_score, 1),
            "signal": signal,
            "exclusion_reason": exclusion_reason,
            "trade_setup": trade_setup
        }

    def _score_timing(self, catalyst_info: dict) -> int:
        """Puntua el timing del catalizador (1-5)"""
        if not catalyst_info:
            return 3  # Neutral sin catalizador (antes era 2)

        days_to_catalyst = catalyst_info.get("days_ahead", 30)

        if days_to_catalyst <= 3:
            return 5
        elif days_to_catalyst <= 7:
            return 5
        elif days_to_catalyst <= 14:
            return 4
        elif days_to_catalyst <= 21:
            return 3
        else:
            return 3

    def _score_technical(self, stock_data: dict) -> int:
        """Puntua el setup tecnico (1-5)"""
        score = 3  # Base neutral

        price = stock_data.get("price", 0)
        high_52w = stock_data.get("52w_high", 0)
        low_52w = stock_data.get("52w_low", 0)
        change_pct = stock_data.get("change_pct", 0)

        if high_52w and low_52w and price:
            # Posicion en rango 52 semanas
            range_52w = high_52w - low_52w
            if range_52w > 0:
                position = (price - low_52w) / range_52w

                if position > 0.85:  # Muy cerca de maximos - breakout potential
                    score = 5
                elif position > 0.7:  # Zona alta con momentum
                    score = 5
                elif position > 0.5:  # Zona media-alta
                    score = 4
                elif position > 0.3:  # Zona media
                    score = 3
                else:  # Cerca de minimos
                    score = 2

        # Bonus por momentum del dia (cambio positivo)
        if change_pct:
            if change_pct > 3:
                score = min(5, score + 1)
            elif change_pct > 1:
                score = min(5, score + 0)  # Mantener
            elif change_pct < -3:
                score = max(1, score - 1)

        # Ajustar por volumen inusual
        volume = stock_data.get("volume", 0)
        avg_volume = stock_data.get("avg_volume", 1)
        if avg_volume and volume > avg_volume * 1.5:
            score = min(5, score + 1)

        return score

    def _score_risk_reward(self, stock_data: dict) -> int:
        """Puntua el ratio riesgo/recompensa potencial (1-5)"""
        price = stock_data.get("price", 0)
        high_52w = stock_data.get("52w_high", 0)
        low_52w = stock_data.get("52w_low", 0)

        if not price or not high_52w:
            return 3

        # Potencial de subida hasta 52w high
        upside_pct = ((high_52w - price) / price) * 100 if price else 0

        # Stop loss estimado (5% maximo)
        stop_loss_pct = min(5, max(2, (price - low_52w) / price * 100 * 0.3)) if low_52w else 5

        # Calcular R:R
        if stop_loss_pct > 0:
            rr_ratio = upside_pct / stop_loss_pct

            if rr_ratio >= 4:
                return 5
            elif rr_ratio >= 3:
                return 4
            elif rr_ratio >= 2:
                return 3
            elif rr_ratio >= 1:
                return 2
            else:
                return 1

        return 3

    def _score_fundamental(self, stock_data: dict) -> int:
        """Puntua la calidad fundamental (1-5)"""
        score = 3

        revenue_growth = stock_data.get("revenue_growth")
        profit_margin = stock_data.get("profit_margin")

        if revenue_growth:
            if revenue_growth > 0.20:  # >20% growth
                score += 1
            elif revenue_growth < 0:
                score -= 1

        if profit_margin:
            if profit_margin > 0.15:  # >15% margin
                score += 1
            elif profit_margin < 0:
                score -= 1

        return max(1, min(5, score))

    def _score_catalyst(self, catalyst_info: dict) -> int:
        """Puntua la calidad/probabilidad del catalizador (1-5)"""
        if not catalyst_info:
            return 3  # Neutral sin catalizador (antes era 2)

        catalyst_type = catalyst_info.get("type", "")

        # Catalizadores de alta probabilidad
        high_prob = ["earnings_beat_history", "fda_approval", "analyst_upgrade", "buyback"]
        medium_prob = ["earnings", "conference", "product_launch"]
        low_prob = ["rumor", "speculation"]

        if any(c in catalyst_type.lower() for c in high_prob):
            return 5
        elif any(c in catalyst_type.lower() for c in medium_prob):
            return 4  # Earnings subio de 3 a 4
        elif any(c in catalyst_type.lower() for c in low_prob):
            return 2

        return 3

    def _check_exclusions(self, stock_data: dict) -> Optional[str]:
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

    def _calculate_trade_setup(self, stock_data: dict) -> Optional[dict]:
        """Calcula el setup de trade concreto con validacion R:R"""
        price = stock_data.get("price", 0)
        if not price:
            return None

        # Entry: precio actual con pequeno descuento para limit order
        entry = round(price * 0.995, 2)

        # Stop Loss: usar % fijo basado en volatilidad del activo
        beta = stock_data.get("beta", 1.5)

        # Stop loss adaptativo: 8% para beta normal, hasta 10% para alta volatilidad
        if beta and beta >= 2.0:
            stop_pct = config.max_stop_loss_pct  # 10% para alta volatilidad
        elif beta and beta >= 1.5:
            stop_pct = 8.0  # 8% para volatilidad media-alta
        else:
            stop_pct = 6.0  # 6% para baja volatilidad

        stop_loss = round(price * (1 - stop_pct / 100), 2)

        # Target: % realista basado en scoring y momentum (NO 52w high)
        # Usar target conservador (15%) o agresivo (20%) segun momentum
        change_pct = stock_data.get("change_pct", 0)

        if change_pct and change_pct > 2:  # Momentum fuerte
            target_pct = config.target_pct_aggressive  # 20%
        else:
            target_pct = config.target_pct_conservative  # 15%

        take_profit = round(price * (1 + target_pct / 100), 2)

        # VALIDACION CRITICA: R:R minimo 3:1
        rr_ratio = round(target_pct / stop_pct, 2) if stop_pct > 0 else 0

        if rr_ratio < config.min_risk_reward:
            # R:R insuficiente - rechazar trade
            return None

        # Position size (10% del capital)
        position_pct = config.position_size_normal
        position_value = config.capital * (position_pct / 100)
        exposure_with_leverage = position_value * config.leverage

        # Calcular perdida/ganancia en EUR
        max_loss_eur = round(exposure_with_leverage * (stop_pct / 100), 2)
        potential_gain_eur = round(exposure_with_leverage * (target_pct / 100), 2)

        return {
            "entry": entry,
            "stop_loss": stop_loss,
            "stop_pct": round(stop_pct, 2),
            "take_profit": take_profit,
            "target_pct": round(target_pct, 2),
            "risk_reward": rr_ratio,
            "position_pct": position_pct,
            "position_eur": round(position_value, 2),
            "exposure_eur": round(exposure_with_leverage, 2),
            "max_loss_eur": max_loss_eur,
            "potential_gain_eur": potential_gain_eur
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
        self.scorer = OpportunityScorer(self.api)
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

        # 2. Cargar calendario de earnings (catalizadores)
        self._load_earnings_calendar()

        # 3. Escanear watchlist
        opportunities = []
        watchlist_items = []
        skipped = []

        for symbol in watchlist:
            print(f"  Analizando {symbol}...", end=" ")

            # Obtener info de catalizador si existe
            catalyst_info = self.earnings_calendar.get(symbol)
            if catalyst_info:
                print(f"[EARNINGS en {catalyst_info['days_ahead']}d] ", end="")

            result = self.scorer.score_opportunity(symbol, catalyst_info)

            if result.get("error"):
                print(f"ERROR: {result['error']}")
                continue

            score = result.get("total_score", 0)
            signal = result.get("signal", "SKIP")

            print(f"Score: {score:.0f} - {signal}")

            if signal == "COMPRA":
                opportunities.append(result)
            elif signal == "WATCHLIST":
                watchlist_items.append(result)
            else:
                skipped.append(result)

        # Ordenar por score
        opportunities.sort(key=lambda x: x["total_score"], reverse=True)
        watchlist_items.sort(key=lambda x: x["total_score"], reverse=True)

        return {
            "timestamp": datetime.now().isoformat(),
            "market_status": market_status,
            "opportunities": opportunities[:5],  # Top 5
            "watchlist": watchlist_items[:10],   # Top 10 watchlist
            "total_scanned": len(watchlist),
            "opportunities_found": len(opportunities),
            "watchlist_count": len(watchlist_items),
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

        # Resumen
        report.append(f"\n## RESUMEN")
        report.append(f"Acciones analizadas: {scan_result['total_scanned']}")
        report.append(f"Oportunidades encontradas: {scan_result['opportunities_found']}")
        report.append(f"En watchlist: {scan_result['watchlist_count']}")

        report.append("\n" + "=" * 60)
        report.append("DISCLAIMER: Esto NO es consejo financiero. Opera bajo tu propio riesgo.")
        report.append("=" * 60)

        return "\n".join(report)

    def _format_opportunity(self, opp: dict) -> str:
        """Formatea una oportunidad individual"""
        lines = []

        lines.append(f"\n### {opp['symbol']}")
        lines.append(f"**Score: {opp['total_score']:.0f}/100** | **Senal: {opp['signal']}**")

        # Metricas basicas
        lines.append(f"\nPrecio: ${opp.get('price', 'N/A')}")
        mc = opp.get('market_cap')
        if mc:
            if mc >= 1e9:
                lines.append(f"Market Cap: ${mc/1e9:.1f}B")
            else:
                lines.append(f"Market Cap: ${mc/1e6:.0f}M")
        lines.append(f"Beta: {opp.get('beta', 'N/A')}")

        # Scores breakdown
        scores = opp.get("scores", {})
        lines.append(f"\nScoring:")
        lines.append(f"  Timing: {scores.get('timing', 0)}/5")
        lines.append(f"  Tecnico: {scores.get('technical', 0)}/5")
        lines.append(f"  R:R: {scores.get('risk_reward', 0)}/5")
        lines.append(f"  Fundamental: {scores.get('fundamental', 0)}/5")
        lines.append(f"  Catalizador: {scores.get('catalyst', 0)}/5")

        # Trade setup
        setup = opp.get("trade_setup")
        if setup:
            lines.append(f"\nTrade Setup:")
            lines.append(f"  Entry: ${setup['entry']}")
            lines.append(f"  Stop Loss: ${setup['stop_loss']} (-{setup['stop_pct']}%)")
            lines.append(f"  Take Profit: ${setup['take_profit']} (+{setup['target_pct']}%)")
            lines.append(f"  Risk:Reward: 1:{setup['risk_reward']}")
            lines.append(f"  Position: {setup['position_pct']}% = {setup['position_eur']}EUR")
            lines.append(f"  Exposicion (x5): {setup['exposure_eur']}EUR")
            lines.append(f"  Perdida max: {setup['max_loss_eur']}EUR")
            lines.append(f"  Ganancia potencial: {setup['potential_gain_eur']}EUR")

        return "\n".join(lines)


# ============================================================================
# GENERADOR DE ALERTAS PARA GITHUB ISSUES
# ============================================================================

def create_github_issue_body(scan_result: dict) -> tuple:
    """Genera titulo y cuerpo para GitHub Issue de alerta"""

    opps = scan_result.get("opportunities", [])
    ms = scan_result.get("market_status", {})

    if not opps:
        title = f"[MARKET SCAN] {datetime.now().strftime('%Y-%m-%d %H:%M')} - Sin oportunidades claras"
        body = f"""## Scan de Mercado - {datetime.now().strftime('%Y-%m-%d %H:%M')}

### Regimen de Mercado
- **Estado**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%
- **Nasdaq**: {ms.get('nasdaq_change', 'N/A')}%

### Resultado
**No se encontraron oportunidades que cumplan los criterios de calidad.**

> Mejor no operar que forzar un trade mediocre.

---
*Generado automaticamente por Investment Advisor*
"""
    else:
        top_opp = opps[0]
        title = f"[ALERTA COMPRA] {top_opp['symbol']} - Score {top_opp['total_score']:.0f}/100"

        body = f"""## ALERTA DE OPORTUNIDAD DE INVERSION

### Regimen de Mercado
- **Estado**: {ms.get('market_regime', 'N/A')}
- **VIX**: {ms.get('vix', 'N/A')}
- **S&P 500**: {ms.get('sp500_change', 'N/A')}%

---

"""
        for opp in opps:
            setup = opp.get("trade_setup", {})
            scores = opp.get("scores", {})

            body += f"""### {opp['symbol']} - Score: {opp['total_score']:.0f}/100

| Metrica | Valor |
|---------|-------|
| Precio | ${opp.get('price', 'N/A')} |
| Market Cap | ${opp.get('market_cap', 0)/1e9:.1f}B |
| Beta | {opp.get('beta', 'N/A')} |

**Scoring Breakdown:**
| Dimension | Score |
|-----------|-------|
| Timing | {scores.get('timing', 0)}/5 |
| Tecnico | {scores.get('technical', 0)}/5 |
| Risk/Reward | {scores.get('risk_reward', 0)}/5 |
| Fundamental | {scores.get('fundamental', 0)}/5 |
| Catalizador | {scores.get('catalyst', 0)}/5 |

**Trade Setup:**
- **Entry**: ${setup.get('entry', 'N/A')}
- **Stop Loss**: ${setup.get('stop_loss', 'N/A')} (-{setup.get('stop_pct', 'N/A')}%)
- **Take Profit**: ${setup.get('take_profit', 'N/A')} (+{setup.get('target_pct', 'N/A')}%)
- **Risk:Reward**: 1:{setup.get('risk_reward', 'N/A')}
- **Position**: {setup.get('position_eur', 0)}EUR ({setup.get('position_pct', 0)}%)
- **Exposicion (x5)**: {setup.get('exposure_eur', 0)}EUR
- **Perdida maxima**: {setup.get('max_loss_eur', 0)}EUR
- **Ganancia potencial**: {setup.get('potential_gain_eur', 0)}EUR

---

"""

        body += """
> **DISCLAIMER**: Esto NO es consejo financiero. Opera bajo tu propio riesgo.

---
*Generado automaticamente por Investment Advisor*
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
    output = {
        "scan_result": result,
        "issue_title": title,
        "issue_body": body,
        "has_opportunities": len(result.get("opportunities", [])) > 0
    }

    # Escribir a archivo para que el workflow lo use
    with open("scan_output.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResultado guardado en scan_output.json")
    print(f"Oportunidades encontradas: {len(result.get('opportunities', []))}")

    # Exit code basado en si hay oportunidades
    if result.get("opportunities"):
        print("\n** HAY OPORTUNIDADES - SE CREARA ALERTA **")
        return 0
    else:
        print("\n** SIN OPORTUNIDADES CLARAS HOY **")
        return 0


if __name__ == "__main__":
    sys.exit(main())
