"""
Setup Técnico - Turtle Trading System

"Way of the Turtle" (Curtis Faith) - Breakouts con volumen son el edge más replicable.
Sistema probado con CAGR ~20% histórico.

Puntuación: 0-25 puntos distribuidos en:
- Breakout 20 días: 10 pts
- Volumen > 150% promedio: 8 pts
- No sobreextendido (< 10% sobre breakout): 4 pts
- ATR favorable para stop: 3 pts
"""

from typing import Dict


def evaluate_turtles(ticker_data: Dict) -> Dict:
    """
    Evalúa setup tipo Turtle: breakout de rango con confirmación de volumen.

    Args:
        ticker_data: {
            "price": float,
            "high_20d": float,  # Máximo de 20 días
            "avg_volume_20d": float,  # Volumen promedio 20 días
            "volume": float,  # Volumen actual
            "atr_14": float  # ATR de 14 periodos
        }

    Returns:
        {
            "style": "turtles",
            "score": int (0-25),
            "max_score": 25,
            "reasoning": list[str],
            "signals": dict
        }
    """
    price = ticker_data.get("price", 0)
    high_20d = ticker_data.get("high_20d", price)  # Si no hay dato, asumir que no hay breakout
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    current_volume = ticker_data.get("volume", 0)
    atr = ticker_data.get("atr_14", 0)

    score = 0
    reasoning = []

    # 1. Breakout de 20 días (10 puntos)
    if price > high_20d:
        score += 10
        pct_above = (price - high_20d) / high_20d * 100
        reasoning.append(f"✓ Breakout: precio ${price:.2f} > máximo 20d ${high_20d:.2f} (+{pct_above:.1f}%)")
    elif price >= high_20d * 0.98:  # Cerca del breakout (2% de distancia)
        score += 5
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"~ Cerca del breakout: solo {pct_below:.1f}% bajo máximo 20d")
    else:
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"✗ Sin breakout: {pct_below:.1f}% bajo máximo 20d")

    # 2. Confirmación de volumen (8 puntos)
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

    if volume_ratio > 1.5:
        score += 8
        reasoning.append(f"✓ Volumen {volume_ratio:.1f}x promedio (confirmación fuerte)")
    elif volume_ratio > 1.2:
        score += 4
        reasoning.append(f"~ Volumen {volume_ratio:.1f}x promedio (confirmación débil)")
    else:
        reasoning.append(f"✗ Volumen insuficiente ({volume_ratio:.1f}x)")

    # 3. No sobreextendido - evitar chase (4 puntos)
    if price > high_20d:
        extension = (price - high_20d) / high_20d * 100
        if extension < 5:
            score += 4
            reasoning.append(f"✓ Entrada temprana: solo {extension:.1f}% sobre breakout")
        elif extension < 10:
            score += 2
            reasoning.append(f"~ Extensión moderada: {extension:.1f}% sobre breakout")
        else:
            reasoning.append(f"✗ Sobreextendido: {extension:.1f}% sobre breakout (chase risk)")
    else:
        # No está en breakout, no penalizar por extensión
        score += 2
        reasoning.append(f"~ Sin sobreextensión (no hay breakout activo)")

    # 4. ATR favorable - stop manejable (3 puntos)
    if price > 0 and atr > 0:
        atr_pct = atr / price * 100

        if 2 <= atr_pct <= 6:
            score += 3
            reasoning.append(f"✓ ATR {atr_pct:.1f}% — stop manejable")
        elif 1 <= atr_pct < 2:
            score += 1
            reasoning.append(f"~ ATR {atr_pct:.1f}% — poco movimiento")
        elif 6 < atr_pct <= 8:
            score += 1
            reasoning.append(f"~ ATR {atr_pct:.1f}% — volátil pero manejable")
        else:
            if atr_pct > 8:
                reasoning.append(f"✗ ATR {atr_pct:.1f}% — muy volátil")
            else:
                reasoning.append(f"✗ ATR {atr_pct:.1f}% — muy bajo")
    else:
        reasoning.append(f"✗ Sin datos de ATR")

    return {
        "style": "turtles",
        "score": score,
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "breakout": price > high_20d,
            "volume_confirmed": volume_ratio > 1.5,
            "atr_pct": atr / price * 100 if price > 0 and atr > 0 else 0,
            "volume_ratio": volume_ratio
        }
    }
