"""
Detector de Régimen de Mercado - Inspirado en Stanley Druckenmiller

"Don't fight the tape" - El contexto macro determina si el entorno favorece la operación.

Puntuación: 0-15 puntos
"""

from typing import Dict, Optional


def detect_regime(market_data: Dict) -> Dict:
    """
    Analiza condiciones macro y retorna régimen + score parcial.

    Args:
        market_data: {
            "vix": float,
            "vix_change_5d": float,  # % cambio en 5 días (opcional)
            "spy_above_200ema": bool,
            "sp500_change": float,  # % change del día
            "advance_decline_ratio": float,  # breadth (opcional)
            "put_call_ratio": float  # (opcional)
        }

    Returns:
        {
            "regime": str,
            "score": int (0-15),
            "reasoning": str,
            "sector_bias": dict
        }
    """
    vix = market_data.get("vix")
    sp500_change = market_data.get("sp500_change", 0)
    spy_trend = market_data.get("spy_above_200ema", True)  # Asumimos alcista si no hay dato
    breadth = market_data.get("advance_decline_ratio", 1.0)

    # Si no hay VIX, asumir régimen neutral
    if vix is None:
        return {
            "regime": "unknown",
            "score": 10,
            "reasoning": "Sin datos de VIX - asumiendo condiciones neutras",
            "sector_bias": {"boost": [], "penalize": []}
        }

    # Régimen: RISK-ON (favorable para longs)
    if vix < 18 and spy_trend and breadth >= 1.2:
        return {
            "regime": "risk_on",
            "score": 15,
            "reasoning": f"VIX bajo ({vix:.1f}), SPY sobre 200 EMA, breadth expansiva ({breadth:.2f}). Entorno óptimo para breakouts.",
            "sector_bias": {
                "boost": ["tech", "consumer_discretionary", "semiconductors"],
                "penalize": []
            }
        }

    # Régimen: RISK-ON moderado (solo VIX bajo)
    if vix < 18 and spy_trend:
        return {
            "regime": "risk_on",
            "score": 15,
            "reasoning": f"VIX bajo ({vix:.1f}), mercado en tendencia alcista. Buen entorno para longs.",
            "sector_bias": {
                "boost": ["tech", "consumer_discretionary", "semiconductors"],
                "penalize": []
            }
        }

    # Régimen: RISK-OFF (defensivo)
    if vix > 25 or (vix > 20 and not spy_trend):
        score = 5 if vix < 30 else 0  # Pánico extremo = no operar
        severity = "extremo" if vix >= 30 else "alto"
        return {
            "regime": "risk_off",
            "score": score,
            "reasoning": f"VIX {severity} ({vix:.1f}), mercado en modo defensivo. Solo trend following en activos refugio.",
            "sector_bias": {
                "boost": ["utilities", "healthcare", "staples"],
                "penalize": ["tech", "growth", "small_caps"]
            }
        }

    # Régimen: NEUTRAL (selectivo)
    return {
        "regime": "neutral",
        "score": 10,
        "reasoning": f"VIX moderado ({vix:.1f}), condiciones mixtas. Operar solo setups de alta convicción.",
        "sector_bias": {
            "boost": [],
            "penalize": []
        }
    }


def apply_sector_adjustment(base_score: int, sector: Optional[str], regime_info: Dict) -> int:
    """
    Ajusta score según sector y régimen.

    Args:
        base_score: Score base antes del ajuste
        sector: Sector del ticker (puede ser None)
        regime_info: Dict retornado por detect_regime()

    Returns:
        Score ajustado (+5 boost o -10 penalización)
    """
    if not sector:
        return base_score

    sector_bias = regime_info.get("sector_bias", {})
    boost = sector_bias.get("boost", [])
    penalize = sector_bias.get("penalize", [])

    # Normalizar sector a lowercase para comparar
    sector_lower = sector.lower()

    # Boost (+5 puntos)
    if any(b.lower() in sector_lower for b in boost):
        return min(base_score + 5, 100)

    # Penalización (-10 puntos)
    if any(p.lower() in sector_lower for p in penalize):
        return max(base_score - 10, 0)

    return base_score
