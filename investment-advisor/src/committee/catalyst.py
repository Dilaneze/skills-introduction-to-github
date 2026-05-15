"""
Catalizador + Timing - Core del sistema catalyst-driven

Asimetría viene de eventos con fecha conocida.

Puntuación: 0-25 puntos distribuidos en:
- Tipo de catalizador (earnings, FDA, M&A, etc.): 8 pts
- Proximidad temporal (días hasta evento): 7 pts
- Historial de reacción del ticker: 5 pts (si disponible)
- Asimetría de expectativas: 5 pts
"""

from typing import Dict, Optional


# Puntuaciones por tipo de catalizador
CATALYST_SCORES = {
    "fda_decision": 8,          # Binario, alta asimetría
    "fda_approval": 8,
    "fda": 8,
    "earnings_beat_history": 8, # Historial de beats
    "m&a_rumor": 7,             # Takeout premium
    "m&a": 7,
    "merger": 7,
    "acquisition": 7,
    "earnings": 6,              # Predecible pero con sorpresas
    "product_launch": 6,        # Ejecución visible
    "investor_day": 5,          # Guidance updates
    "conference": 4,            # Menos específico
    "macro_event": 4,
    "analyst_upgrade": 5,
    "buyback": 5,
    "rumor": 2,
    "speculation": 2,
    "unknown": 2
}


def evaluate_catalyst(ticker_data: Dict, catalyst_info: Optional[Dict]) -> Dict:
    """
    Evalúa calidad y timing del catalizador.

    Args:
        ticker_data: {
            "symbol": str,
            "historical_earnings_reaction": float  # Avg % move en earnings (opcional)
        }
        catalyst_info: {
            "type": str,
            "days_ahead": int,  # Días hasta el evento (o "days_to_event")
            "consensus_sentiment": str  # "low", "neutral", "high" (opcional)
        }

    Returns:
        {
            "style": "catalyst",
            "score": int (0-25),
            "max_score": 25,
            "reasoning": list[str],
            "signals": dict
        }
    """
    score = 0
    reasoning = []

    # Verificar señales adicionales independientes del catalizador
    extra_signals = _check_extra_signals(ticker_data)

    # Si no hay catalizador, usar score neutro + señales extra
    if not catalyst_info:
        base_score = 14 + extra_signals["score"]
        return {
            "style": "catalyst",
            "score": min(base_score, 25),
            "max_score": 25,
            "reasoning": ["~ Sin catalizador identificado — scoring técnico puro"] + extra_signals["reasoning"],
            "signals": {
                "catalyst_type": "none",
                "days_to_event": 999,
                "historical_avg_move": 0,
                **extra_signals["signals"]
            }
        }

    catalyst_type = catalyst_info.get("type", "unknown").lower()
    days_to_event = catalyst_info.get("days_ahead") or catalyst_info.get("days_to_event", 999)
    expectations = catalyst_info.get("consensus_sentiment", "neutral").lower()
    historical_reaction = ticker_data.get("historical_earnings_reaction", 0)

    # 1. Tipo de catalizador (8 puntos máximo)
    cat_score = 2  # Default para tipos desconocidos

    for key, value in CATALYST_SCORES.items():
        if key in catalyst_type:
            cat_score = value
            break

    score += cat_score
    emoji = "✓" if cat_score >= 6 else "~"
    reasoning.append(f"{emoji} Catalizador: {catalyst_type} ({cat_score}/8 pts)")

    # 2. Proximidad temporal (7 puntos máximo)
    # Sweet spot: 3-10 días
    if 3 <= days_to_event <= 7:
        score += 7
        reasoning.append(f"✓ Timing óptimo: {days_to_event} días hasta evento")
    elif 1 <= days_to_event <= 14:
        score += 4
        reasoning.append(f"~ Timing aceptable: {days_to_event} días hasta evento")
    elif days_to_event > 14 and days_to_event < 30:
        score += 2
        reasoning.append(f"~ Evento algo lejano: {days_to_event} días (capital inmovilizado)")
    elif days_to_event >= 30:
        score += 1
        reasoning.append(f"✗ Evento muy lejano: {days_to_event} días")
    else:
        # Evento inminente (< 1 día) o ya pasó
        score += 2
        reasoning.append(f"~ Evento inminente o pasado ({days_to_event} días)")

    # 3. Historial de reacción (5 puntos máximo)
    # Si no hay dato histórico, dar puntos neutros
    if historical_reaction >= 10:
        score += 5
        reasoning.append(f"✓ Historial: ticker mueve ~{historical_reaction:.0f}% en eventos similares")
    elif historical_reaction >= 5:
        score += 3
        reasoning.append(f"~ Historial: ticker mueve ~{historical_reaction:.0f}% en eventos similares")
    elif historical_reaction > 0:
        score += 1
        reasoning.append(f"✗ Historial de baja reactividad ({historical_reaction:.0f}%)")
    else:
        # Sin dato histórico - asumir neutral
        score += 2
        reasoning.append(f"~ Sin datos históricos de reacción a eventos")

    # 4. Asimetría de expectativas (5 puntos máximo)
    if expectations == "low" and catalyst_type in ["earnings", "fda_decision", "fda", "product_launch"]:
        score += 5
        reasoning.append(f"✓ Expectativas bajas → potencial sorpresa positiva")
    elif expectations == "neutral":
        score += 3
        reasoning.append(f"~ Expectativas neutrales")
    elif expectations == "high":
        score += 1
        reasoning.append(f"✗ Expectativas altas → upside limitado, downside si decepciona")
    else:
        # Sin dato de expectations, asumir neutral
        score += 3
        reasoning.append(f"~ Expectativas desconocidas (asumiendo neutral)")

    score += extra_signals["score"]
    reasoning += extra_signals["reasoning"]

    return {
        "style": "catalyst",
        "score": min(score, 25),
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "catalyst_type": catalyst_type,
            "days_to_event": days_to_event,
            "historical_avg_move": historical_reaction,
            "expectations": expectations,
            **extra_signals["signals"]
        }
    }


def _check_extra_signals(ticker_data: dict) -> dict:
    """
    Señales adicionales independientes del catalizador principal:
    1. PEAD Long: EPS beat reciente → drift alcista activo
    2. Short Squeeze: alto short interest + catalizador = potencial explosivo
    3. Insider Buying: compras de insiders (Finnhub) o cluster (EDGAR Form 4)
    4. News Sentiment: NLP bullish/bearish % de Finnhub /news-sentiment

    Puntuación extra: hasta +7 pts sobre el score base de catalyst.
    """
    score = 0
    reasoning = []
    signals = {}

    # 1. PEAD Long: si hubo earnings beat reciente (vía Finnhub)
    eps_surprise_pct = ticker_data.get("eps_surprise_pct")
    days_since_earnings = ticker_data.get("days_since_earnings")

    if eps_surprise_pct is not None and eps_surprise_pct > 10 and days_since_earnings is not None:
        if days_since_earnings <= 5:
            score += 4
            reasoning.append(f"✓✓ PEAD Long: EPS beat +{eps_surprise_pct:.1f}% hace {days_since_earnings}d (drift alcista activo)")
        elif days_since_earnings <= 15:
            score += 2
            reasoning.append(f"✓ PEAD Long: EPS beat +{eps_surprise_pct:.1f}% hace {days_since_earnings}d")
        signals["pead_long_active"] = True
        signals["eps_beat_pct"] = eps_surprise_pct
    else:
        signals["pead_long_active"] = False

    # 2. Short Squeeze: alto short interest + momentum = potencial explosivo
    short_pct = ticker_data.get("short_pct")  # % del float en corto
    short_ratio = ticker_data.get("short_ratio")  # días para cubrir

    if short_pct is not None and short_pct > 0.15:  # >15% del float en corto
        days_to_cover = short_ratio or 0
        if days_to_cover >= 3:
            score += 3
            reasoning.append(f"✓✓ Short Squeeze setup: {short_pct*100:.0f}% float short, {days_to_cover:.1f}d to cover")
        elif short_pct > 0.20:
            score += 2
            reasoning.append(f"✓ Alto short interest: {short_pct*100:.0f}% del float — potencial squeeze")
        signals["squeeze_potential"] = True
        signals["short_float_pct"] = short_pct
    else:
        signals["squeeze_potential"] = False

    # 3. Insider Buying (Finnhub /stock/insider-transactions + MSPR)
    insider_buys = ticker_data.get("insider_buys_30d", 0) or 0
    insider_unique = ticker_data.get("insider_unique_buyers_30d", 0) or 0
    insider_sells = ticker_data.get("insider_sells_30d", 0) or 0
    insider_mspr = ticker_data.get("insider_mspr")
    # EDGAR Form 4 cluster buy (post-scan enrichment, si disponible)
    edgar_buys = ticker_data.get("edgar_insider_buys_30d", 0) or 0
    edgar_cluster = ticker_data.get("edgar_insider_cluster_buy", False)

    total_buys = max(insider_buys, edgar_buys)
    total_unique = max(insider_unique, ticker_data.get("edgar_unique_buyers_30d", 0) or 0)
    net_positive = total_buys > insider_sells

    if (edgar_cluster or total_unique >= 3) and net_positive:
        score += 4
        source = "EDGAR Form 4 + Finnhub" if edgar_cluster else "Finnhub"
        reasoning.append(f"✓✓ CLUSTER BUY insider: {total_unique} insiders compraron en 30d ({source})")
        signals["insider_cluster_buy"] = True
    elif total_buys >= 2 and net_positive:
        score += 2
        reasoning.append(f"✓ Insider buying: {total_buys} compras en 30d (Finnhub)")
        signals["insider_cluster_buy"] = False
    elif total_buys == 1 and net_positive:
        score += 1
        reasoning.append(f"~ Insider buy individual en 30d")
        signals["insider_cluster_buy"] = False
    else:
        signals["insider_cluster_buy"] = False

    if insider_mspr is not None:
        signals["insider_mspr"] = round(insider_mspr, 3)
        # MSPR > 0.5 refuerza la señal alcista de insiders
        if insider_mspr > 0.5 and total_buys > 0:
            reasoning.append(f"  MSPR={insider_mspr:.2f} (>0.5 confirma presión compradora de insiders)")

    # 4. News Sentiment NLP (Finnhub /news-sentiment)
    news_score = ticker_data.get("news_sentiment_score")
    news_articles = ticker_data.get("news_articles_week", 0) or 0

    if news_score is not None and news_articles >= 3:
        if news_score > 0.3:
            score += 1
            reasoning.append(f"✓ Sentimiento NLP alcista: {news_score:+.2f} ({news_articles} artículos/semana)")
        elif news_score < -0.3:
            # Penalización: noticias negativas reducen la convicción
            score -= 1
            reasoning.append(f"✗ Sentimiento NLP bajista: {news_score:+.2f} — riesgo de presión vendedora")
        signals["news_sentiment"] = round(news_score, 3)

    return {"score": score, "reasoning": reasoning, "signals": signals}
