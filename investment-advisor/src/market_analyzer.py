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
    """Parametros de trading configurables - MODO AGRESIVO"""
    capital: float = 500.0
    leverage: int = 5
    max_stop_loss_pct: float = 8.0  # 8% = 40% real con x5 (mas agresivo)
    min_risk_reward: float = 2.5  # Bajado de 3.0 para mas oportunidades
    position_size_normal: float = 5.0  # % del capital
    position_size_exceptional: float = 15.0  # Subido para plays de alta conviccion
    max_concurrent_positions: int = 3  # Mas posiciones simultaneas
    min_holding_days: int = 1  # Permitir day trades
    max_holding_days: int = 14  # Extendido para swing trades largos

    # Filtros de seleccion - MAS PERMISIVOS PARA SMALL CAPS
    min_market_cap: float = 50_000_000  # $50M (antes $300M) - permite micro caps
    max_market_cap: float = 100_000_000_000  # $100B (antes $50B) - permite mega caps con momentum
    min_beta: float = 1.0  # Bajado de 1.5
    preferred_beta: float = 2.0  # Subido - queremos volatilidad
    min_price: float = 1.0  # Bajado de $5 - permite penny stocks de calidad
    max_price: float = 500.0  # Subido de $200
    max_spread_pct: float = 1.0  # Mas permisivo con spread

    # Volumen minimo por market cap - REDUCIDO
    volume_thresholds: dict = None

    def __post_init__(self):
        self.volume_thresholds = {
            "micro": 500_000,    # <$100M: 500K shares
            "small": 750_000,    # $100M-$1B: 750K shares (antes 2M)
            "mid": 500_000,      # $1B-$10B: 500K shares (antes 1.5M)
            "large": 300_000     # >$10B: 300K shares (antes 1M)
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

        # Obtener datos adicionales
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

                    # Helper para extraer valores de forma segura
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

        except Exception as e:
            print(f"[WARN] Error datos adicionales {symbol}: {e}")
            # Continuar con datos basicos si falla

        return quote

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

        return {
            "symbol": symbol,
            "price": stock_data.get("price"),
            "market_cap": stock_data.get("market_cap"),
            "beta": stock_data.get("beta"),
            "volume": stock_data.get("avg_volume"),
            "scores": scores,
            "total_score": round(final_score, 1),
            "signal": "COMPRA" if final_score >= 72 and not exclusion_reason else "WATCHLIST" if final_score >= 56 else "SKIP",
            "exclusion_reason": exclusion_reason,
            "trade_setup": self._calculate_trade_setup(stock_data) if final_score >= 72 else None
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

        # Verificar volumen segun market cap (thresholds reducidos para modo agresivo)
        if market_cap and avg_volume:
            if market_cap < 100e6:  # Micro cap <$100M
                if avg_volume < config.volume_thresholds["micro"]:
                    return f"Volumen insuficiente para micro cap ({avg_volume/1e6:.1f}M < {config.volume_thresholds['micro']/1e6:.1f}M)"
            elif market_cap < 1e9:  # Small cap $100M-$1B
                if avg_volume < config.volume_thresholds["small"]:
                    return f"Volumen insuficiente para small cap"
            elif market_cap < 10e9:  # Mid cap $1B-$10B
                if avg_volume < config.volume_thresholds["mid"]:
                    return f"Volumen insuficiente para mid cap"
            else:  # Large cap >$10B
                if avg_volume < config.volume_thresholds["large"]:
                    return f"Volumen insuficiente para large cap"

        return None

    def _calculate_trade_setup(self, stock_data: dict) -> dict:
        """Calcula el setup de trade concreto"""
        price = stock_data.get("price", 0)
        low_52w = stock_data.get("52w_low", price * 0.9)
        high_52w = stock_data.get("52w_high", price * 1.2)

        # Entry: precio actual con pequeno descuento
        entry = round(price * 0.995, 2)

        # Stop Loss: maximo 5% o swing low reciente
        stop_distance = min(price * 0.05, (price - low_52w) * 0.3)
        stop_loss = round(price - stop_distance, 2)
        stop_pct = round(((price - stop_loss) / price) * 100, 2)

        # Take Profit: minimo 3x el stop loss distance
        min_target = price + (stop_distance * 3)
        resistance_target = high_52w * 0.95
        take_profit = round(max(min_target, resistance_target), 2)
        target_pct = round(((take_profit - price) / price) * 100, 2)

        # Risk:Reward ratio
        rr_ratio = round(target_pct / stop_pct, 1) if stop_pct > 0 else 0

        # Position size
        position_pct = config.position_size_normal
        position_value = config.capital * (position_pct / 100)
        exposure_with_leverage = position_value * config.leverage

        return {
            "entry": entry,
            "stop_loss": stop_loss,
            "stop_pct": stop_pct,
            "take_profit": take_profit,
            "target_pct": target_pct,
            "risk_reward": rr_ratio,
            "position_pct": position_pct,
            "position_eur": round(position_value, 2),
            "exposure_eur": round(exposure_with_leverage, 2),
            "max_loss_eur": round(exposure_with_leverage * (stop_pct / 100), 2),
            "potential_gain_eur": round(exposure_with_leverage * (target_pct / 100), 2)
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
