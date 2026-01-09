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

    # Si no hay catalizador, dar puntos base neutros
    if not catalyst_info:
        return {
            "style": "catalyst",
            "score": 12,  # Score neutro (casi la mitad)
            "max_score": 25,
            "reasoning": ["~ Sin catalizador identificado — scoring basado en setup técnico"],
            "signals": {
                "catalyst_type": "none",
                "days_to_event": 999,
                "historical_avg_move": 0
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

    return {
        "style": "catalyst",
        "score": score,
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "catalyst_type": catalyst_type,
            "days_to_event": days_to_event,
            "historical_avg_move": historical_reaction,
            "expectations": expectations
        }
    }
