"""
PEAD Miss Short — Post-Earnings Announcement Drift (Short Side)

Anomalía documentada desde 1968 (Ball & Brown). Persiste hasta hoy.
Earnings miss > 10% → el precio continúa cayendo 10-20 días post-anuncio.
Drift más fuerte en small/mid caps y cuando el volumen del día 0 es alto.

Referencias:
- Ball & Brown (1968), Bernard & Thomas (1989)
- QuantPedia: quantpedia.com/strategies/post-earnings-announcement-effect/
- github.com/aniketnmishra/PEAD
- github.com/gen-li/Replicate_PEAD

Puntuación: 0-25 puntos
- Magnitud del miss EPS: 8 pts
- Reacción del mercado el día 0 (EAR): 7 pts
- Timing (sweet spot 2-10 días post-anuncio): 5 pts
- Volume el día de earnings (mayor = drift más fuerte): 5 pts
"""

from typing import Dict, Optional


def evaluate_pead_miss(ticker_data: Dict, catalyst_info: Optional[Dict] = None) -> Dict:
    """
    Evalúa setup PEAD Miss para short.

    Requiere datos de earnings recientes (via Finnhub).
    Entry: día 2 post-earnings (evitar el spike del día 0).
    Stop: sobre el máximo del día post-earnings.
    Target: 10-20% abajo en 10-20 días.
    """
    eps_surprise_pct = ticker_data.get("eps_surprise_pct")
    earnings_reaction_pct = ticker_data.get("earnings_reaction_pct")
    days_since_earnings = ticker_data.get("days_since_earnings")
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    earnings_day_volume_ratio = ticker_data.get("earnings_day_volume_ratio")

    # Sin datos de earnings, score 0 (no perjudica al setup si hay otros signals)
    if eps_surprise_pct is None or days_since_earnings is None:
        return {
            "style": "pead_miss",
            "score": 0,
            "max_score": 25,
            "reasoning": ["~ Sin datos de earnings recientes (PEAD requiere Finnhub key activa)"],
            "signals": {
                "eps_surprise_pct": None,
                "earnings_reaction_pct": None,
                "days_since_earnings": None,
                "pead_active": False
            }
        }

    # Sin miss significativo, PEAD short no aplica
    if eps_surprise_pct >= -5:
        return {
            "style": "pead_miss",
            "score": 0,
            "max_score": 25,
            "reasoning": [f"✗ Sin earnings miss (surprise: {eps_surprise_pct:+.1f}%) — PEAD short no aplica"],
            "signals": {
                "eps_surprise_pct": eps_surprise_pct,
                "earnings_reaction_pct": earnings_reaction_pct,
                "days_since_earnings": days_since_earnings,
                "pead_active": False
            }
        }

    score = 0
    reasoning = []
    miss_pct = abs(eps_surprise_pct)

    # 1. Magnitud del miss (8 puntos)
    if miss_pct >= 25:
        score += 8
        reasoning.append(f"✓✓ EPS miss severo {eps_surprise_pct:+.1f}% — shock que el mercado tarda en digerir")
    elif miss_pct >= 15:
        score += 6
        reasoning.append(f"✓ EPS miss significativo {eps_surprise_pct:+.1f}%")
    elif miss_pct >= 10:
        score += 4
        reasoning.append(f"~ EPS miss moderado {eps_surprise_pct:+.1f}%")
    else:
        score += 2
        reasoning.append(f"~ EPS miss leve {eps_surprise_pct:+.1f}% (drift limitado esperado)")

    # 2. Reacción del mercado EAR (7 puntos)
    if earnings_reaction_pct is not None:
        if earnings_reaction_pct <= -5:
            score += 7
            reasoning.append(f"✓✓ Gap bajista fuerte {earnings_reaction_pct:+.1f}% — mercado confirmando el miss")
        elif earnings_reaction_pct <= -3:
            score += 5
            reasoning.append(f"✓ Gap bajista {earnings_reaction_pct:+.1f}%")
        elif earnings_reaction_pct <= -1:
            score += 3
            reasoning.append(f"~ Reacción bajista leve {earnings_reaction_pct:+.1f}%")
        elif earnings_reaction_pct <= 2:
            score += 1
            reasoning.append(f"~ Mercado ignoró el miss (reacción flat) — drift puede activarse tarde")
        else:
            reasoning.append(f"✗ Mercado subió +{earnings_reaction_pct:.1f}% pese al miss — señal contradictoria")
    else:
        score += 2
        reasoning.append("~ Sin datos de reacción día 0 — asumiendo neutral")

    # 3. Timing post-earnings (5 puntos)
    if 2 <= days_since_earnings <= 5:
        score += 5
        reasoning.append(f"✓✓ {days_since_earnings}d post-earnings — sweet spot del drift (mayor probabilidad)")
    elif 1 <= days_since_earnings <= 10:
        score += 3
        reasoning.append(f"✓ {days_since_earnings}d post-earnings — drift activo")
    elif days_since_earnings == 0:
        score += 1
        reasoning.append(f"~ Día del anuncio — esperar al día 1-2 para entrada")
    elif days_since_earnings <= 20:
        score += 1
        reasoning.append(f"~ {days_since_earnings}d post-earnings — drift puede debilitarse")
    else:
        reasoning.append(f"✗ {days_since_earnings}d post-earnings — drift académicamente agotado")

    # 4. Volume en día de earnings (5 puntos)
    ev_ratio = earnings_day_volume_ratio or (volume / avg_volume if avg_volume > 0 else 1.0)
    if ev_ratio >= 3.0:
        score += 5
        reasoning.append(f"✓✓ Volume {ev_ratio:.1f}x en earnings — convicción alta, drift más rápido")
    elif ev_ratio >= 2.0:
        score += 3
        reasoning.append(f"✓ Volume {ev_ratio:.1f}x en earnings")
    elif ev_ratio >= 1.5:
        score += 1
        reasoning.append(f"~ Volume {ev_ratio:.1f}x en earnings (moderado)")
    else:
        reasoning.append(f"✗ Volume bajo en earnings ({ev_ratio:.1f}x) — drift puede ser lento")

    pead_active = score >= 10 and days_since_earnings is not None and days_since_earnings <= 20

    return {
        "style": "pead_miss",
        "score": min(score, 25),
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "eps_surprise_pct": eps_surprise_pct,
            "earnings_reaction_pct": earnings_reaction_pct,
            "days_since_earnings": days_since_earnings,
            "pead_active": pead_active
        }
    }
