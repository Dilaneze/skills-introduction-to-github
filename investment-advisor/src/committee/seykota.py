"""
Trend Alignment - Ed Seykota's Approach

"The trend is your friend" - Confirma que no estás contra la corriente.
"Market Wizards" (Schwager) — gestión emocional del riesgo mediante trend following.

Puntuación: 0-20 puntos distribuidos en:
- Precio > EMA 20: 6 pts
- EMA 20 > EMA 50: 6 pts
- EMA 50 > EMA 200: 4 pts (tendencia de largo plazo)
- Momentum positivo (10 días): 4 pts
"""

from typing import Dict


def evaluate_seykota(ticker_data: Dict) -> Dict:
    """
    Evalúa alineación con tendencia (trend following).

    Args:
        ticker_data: {
            "price": float,
            "ema_20": float,
            "ema_50": float,
            "ema_200": float,
            "price_10d_ago": float
        }

    Returns:
        {
            "style": "seykota",
            "score": int (0-20),
            "max_score": 20,
            "reasoning": list[str],
            "signals": dict
        }
    """
    price = ticker_data.get("price", 0)
    ema_20 = ticker_data.get("ema_20", 0)
    ema_50 = ticker_data.get("ema_50", 0)
    ema_200 = ticker_data.get("ema_200", 0)
    price_10d_ago = ticker_data.get("price_10d_ago", price)

    score = 0
    reasoning = []

    # 1. Precio sobre EMA corta (6 puntos)
    if price > 0 and ema_20 > 0:
        if price > ema_20:
            score += 6
            pct_above = (price - ema_20) / ema_20 * 100
            reasoning.append(f"✓ Precio > EMA20 (+{pct_above:.1f}% — tendencia corto plazo alcista)")
        elif price >= ema_20 * 0.97:  # Muy cerca (3%)
            score += 3
            reasoning.append(f"~ Precio cerca de EMA20 (soporte clave)")
        else:
            pct_below = (ema_20 - price) / ema_20 * 100
            reasoning.append(f"✗ Precio < EMA20 (-{pct_below:.1f}% — debilidad corto plazo)")
    else:
        reasoning.append(f"✗ Sin datos de EMA20")

    # 2. EMAs alineadas - golden cross structure (6 puntos)
    if ema_20 > 0 and ema_50 > 0:
        if ema_20 > ema_50:
            score += 6
            reasoning.append(f"✓ EMA20 > EMA50 (estructura alcista)")
        else:
            reasoning.append(f"✗ EMA20 < EMA50 (cruce bajista)")
    else:
        reasoning.append(f"✗ Sin datos de EMAs para estructura")

    # 3. Tendencia de largo plazo (4 puntos)
    if ema_50 > 0 and ema_200 > 0:
        if ema_50 > ema_200:
            score += 4
            reasoning.append(f"✓ EMA50 > EMA200 (tendencia mayor alcista)")
        else:
            reasoning.append(f"✗ EMA50 < EMA200 (tendencia mayor bajista — contracorriente)")
    else:
        # Si no hay EMA200, dar puntos neutros si EMA50 existe
        if ema_50 > 0:
            score += 2
            reasoning.append(f"~ Sin EMA200 (asumiendo tendencia neutral)")
        else:
            reasoning.append(f"✗ Sin datos de EMAs largas")

    # 4. Momentum reciente (4 puntos)
    if price > 0 and price_10d_ago > 0:
        momentum = (price - price_10d_ago) / price_10d_ago * 100

        if momentum > 5:
            score += 4
            reasoning.append(f"✓ Momentum fuerte +{momentum:.1f}% en 10d")
        elif momentum > 2:
            score += 3
            reasoning.append(f"✓ Momentum positivo +{momentum:.1f}% en 10d")
        elif momentum > 0:
            score += 2
            reasoning.append(f"~ Momentum leve +{momentum:.1f}% en 10d")
        elif momentum > -3:
            score += 1
            reasoning.append(f"~ Momentum casi plano {momentum:.1f}% en 10d")
        else:
            reasoning.append(f"✗ Momentum negativo {momentum:.1f}% en 10d")
    else:
        reasoning.append(f"✗ Sin datos de momentum")

    # Señal de tendencia completamente alineada
    trend_aligned = (
        price > ema_20 > ema_50 > ema_200
        if all(x > 0 for x in [price, ema_20, ema_50, ema_200])
        else False
    )

    return {
        "style": "seykota",
        "score": score,
        "max_score": 20,
        "reasoning": reasoning,
        "signals": {
            "trend_aligned": trend_aligned,
            "momentum_10d": (price - price_10d_ago) / price_10d_ago * 100 if price_10d_ago > 0 else 0,
            "above_ema20": price > ema_20 if ema_20 > 0 else False,
            "emas_golden": ema_20 > ema_50 if all(x > 0 for x in [ema_20, ema_50]) else False
        }
    }
