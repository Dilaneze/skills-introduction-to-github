"""
Setup Técnico — Minervini Trend Template + Turtle Trading

Combina el Trend Template de 8 criterios de Mark Minervini (track record auditado:
334.8% en 2021, 255% en 1997, U.S. Investing Championship) con el sistema de
breakout de volumen de los Turtles (Curtis Faith, CAGR ~20% histórico).

Referencia repos:
- github.com/starboi-63/growth-stock-screener (Minervini Trend Template)
- github.com/icedevil2001/mark_minervini_stock_screener

Puntuación: 0-25 puntos
- Breakout 20 días con volumen: 7 pts  (Turtles — edge cuantificado)
- Confirmación de volumen: 5 pts
- Rango 52 semanas (Minervini criterios 5&6): 5 pts
- Relative Strength vs mercado (Minervini criterio 7): 3 pts
- ATR favorable para stop: 2 pts
- No sobreextendido: 3 pts
"""

from typing import Dict


def evaluate_turtles(ticker_data: Dict) -> Dict:
    """
    Evalúa setup técnico combinando Minervini Trend Template + breakout con volumen.

    Args:
        ticker_data: {
            "price": float,
            "high_20d": float,
            "avg_volume_20d": float,
            "volume": float,
            "atr_14": float,
            "52w_high": float,   ← Minervini criterio 6
            "52w_low": float,    ← Minervini criterio 5
            "price_60d_ago": float,
            "spy_price_60d_ago": float  ← para RS relativa (viene de market_status)
        }
    """
    price = ticker_data.get("price", 0)
    high_20d = ticker_data.get("high_20d", price)
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    current_volume = ticker_data.get("volume", 0)
    atr = ticker_data.get("atr_14", 0)
    high_52w = ticker_data.get("52w_high", 0)
    low_52w = ticker_data.get("52w_low", 0)
    price_60d_ago = ticker_data.get("price_60d_ago", price)
    spy_price_60d_ago = ticker_data.get("spy_price_60d_ago", 0)
    spy_price = ticker_data.get("spy_price", 0)

    score = 0
    reasoning = []

    # 1. Breakout de 20 días (7 puntos) — Turtles core
    if price > high_20d:
        score += 7
        pct_above = (price - high_20d) / high_20d * 100
        reasoning.append(f"✓ Breakout: ${price:.2f} > máximo 20d ${high_20d:.2f} (+{pct_above:.1f}%)")
    elif price >= high_20d * 0.98:
        score += 4
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"~ Cerca del breakout 20d: {pct_below:.1f}% bajo el pivote")
    else:
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"✗ Sin breakout 20d: {pct_below:.1f}% bajo máximo")

    # 2. Confirmación de volumen (5 puntos)
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    if volume_ratio > 1.5:
        score += 5
        reasoning.append(f"✓ Volumen {volume_ratio:.1f}x promedio (confirmación fuerte)")
    elif volume_ratio > 1.2:
        score += 3
        reasoning.append(f"~ Volumen {volume_ratio:.1f}x promedio (confirmación moderada)")
    else:
        reasoning.append(f"✗ Volumen {volume_ratio:.1f}x — insuficiente para confirmar")

    # 3. Minervini criterios 5 & 6: rango de 52 semanas (5 puntos)
    # Crit. 5: precio >= 30% sobre mínimo anual (no está en fondo)
    # Crit. 6: precio dentro del 25% del máximo anual (cerca de highs)
    range_score = 0
    if high_52w > 0 and low_52w > 0:
        pct_above_low = (price - low_52w) / low_52w * 100
        pct_below_high = (high_52w - price) / high_52w * 100

        if pct_above_low >= 30:
            range_score += 3
            reasoning.append(f"✓ {pct_above_low:.0f}% sobre mínimo anual (Minervini crit.5: ≥30%)")
        else:
            reasoning.append(f"✗ Solo {pct_above_low:.0f}% sobre mínimo anual (<30% — posible Stage 1)")

        if pct_below_high <= 25:
            range_score += 2
            reasoning.append(f"✓ Dentro del {pct_below_high:.0f}% del máximo anual (Minervini crit.6: ≤25%)")
        else:
            reasoning.append(f"✗ {pct_below_high:.0f}% bajo máximo anual (>25% — lejos de highs)")
    else:
        range_score += 2  # Puntos parciales si no hay datos de 52w
        reasoning.append("~ Sin datos de rango anual (asumiendo setup válido)")

    score += range_score

    # 4. Relative Strength vs mercado (3 puntos) — Minervini criterio 7
    # RS 60 días: stock vs SPY
    if price_60d_ago > 0 and spy_price_60d_ago > 0 and spy_price > 0:
        stock_return_60d = (price - price_60d_ago) / price_60d_ago
        spy_return_60d = (spy_price - spy_price_60d_ago) / spy_price_60d_ago
        rs_ratio = stock_return_60d / spy_return_60d if spy_return_60d != 0 else 1.0

        if rs_ratio >= 1.5:
            score += 3
            reasoning.append(f"✓ RS {rs_ratio:.1f}x mercado en 60d (líder del mercado)")
        elif rs_ratio >= 1.1:
            score += 2
            reasoning.append(f"✓ RS {rs_ratio:.1f}x mercado (outperforming)")
        elif rs_ratio >= 0.8:
            score += 1
            reasoning.append(f"~ RS {rs_ratio:.1f}x mercado (inline con índice)")
        else:
            reasoning.append(f"✗ RS {rs_ratio:.1f}x mercado — underperforming SPY")
    else:
        score += 1  # Neutro sin datos
        reasoning.append("~ Sin datos de RS vs SPY (asumiendo neutral)")

    # 5. No sobreextendido (3 puntos) — evitar chase
    if price > high_20d:
        extension = (price - high_20d) / high_20d * 100
        if extension < 5:
            score += 3
            reasoning.append(f"✓ Entrada temprana: solo {extension:.1f}% sobre pivote")
        elif extension < 10:
            score += 1
            reasoning.append(f"~ Extensión moderada: {extension:.1f}% sobre pivote")
        else:
            reasoning.append(f"✗ Sobreextendido: {extension:.1f}% sobre pivote (chase risk)")
    else:
        score += 2
        reasoning.append("~ No en breakout, sin sobreextensión")

    # 6. ATR favorable para stop (2 puntos)
    if price > 0 and atr > 0:
        atr_pct = atr / price * 100
        if 2 <= atr_pct <= 6:
            score += 2
            reasoning.append(f"✓ ATR {atr_pct:.1f}% — stop manejable")
        elif 1 <= atr_pct <= 8:
            score += 1
            reasoning.append(f"~ ATR {atr_pct:.1f}% — aceptable")
        else:
            reasoning.append(f"✗ ATR {atr_pct:.1f}% — {'muy volátil' if atr_pct > 8 else 'muy bajo'}")
    else:
        reasoning.append("✗ Sin datos de ATR")

    return {
        "style": "turtles_minervini",
        "score": min(score, 25),
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "breakout": price > high_20d,
            "volume_confirmed": volume_ratio > 1.5,
            "volume_ratio": round(volume_ratio, 2),
            "atr_pct": round(atr / price * 100, 2) if price > 0 and atr > 0 else 0,
            "rs_vs_spy": round(
                ((price - price_60d_ago) / price_60d_ago) / ((spy_price - spy_price_60d_ago) / spy_price_60d_ago), 2
            ) if all(x > 0 for x in [price_60d_ago, spy_price_60d_ago, spy_price]) else None
        }
    }
