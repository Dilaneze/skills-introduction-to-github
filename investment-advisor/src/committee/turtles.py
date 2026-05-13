"""
Technical Setup — Minervini Trend Template + Turtle Trading

Combines Mark Minervini's 8-criteria Trend Template (audited track record:
334.8% in 2021, 255% in 1997, U.S. Investing Championship) with the
Turtles volume-confirmed breakout system (Curtis Faith, ~20% CAGR historically).

Reference repos:
- github.com/starboi-63/growth-stock-screener (Minervini Trend Template)
- github.com/icedevil2001/mark_minervini_stock_screener

Score: 0-25 points
- 20-day breakout with volume: 7 pts  (Turtles — quantified edge)
- Volume confirmation: 5 pts
- 52-week range (Minervini criteria 5 & 6): 5 pts
- Relative Strength vs market (Minervini criterion 7): 3 pts
- ATR favorable for stop: 2 pts
- Not overextended: 3 pts
"""

from typing import Dict


def evaluate_turtles(ticker_data: Dict) -> Dict:
    """
    Evaluate technical setup combining Minervini Trend Template + volume breakout.

    Args:
        ticker_data: {
            "price": float,
            "high_20d": float,
            "avg_volume_20d": float,
            "volume": float,
            "atr_14": float,
            "52w_high": float,   ← Minervini criterion 6
            "52w_low": float,    ← Minervini criterion 5
            "price_60d_ago": float,
            "spy_price_60d_ago": float  ← for relative strength (from market_status)
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

    # 1. 20-day breakout (7 points) — Turtles core
    if price > high_20d:
        score += 7
        pct_above = (price - high_20d) / high_20d * 100
        reasoning.append(f"✓ Breakout: ${price:.2f} > 20d high ${high_20d:.2f} (+{pct_above:.1f}%)")
    elif price >= high_20d * 0.98:
        score += 4
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"~ Near 20d breakout pivot: {pct_below:.1f}% below")
    else:
        pct_below = (high_20d - price) / high_20d * 100
        reasoning.append(f"✗ No 20d breakout: {pct_below:.1f}% below high")

    # 2. Volume confirmation (5 points)
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    if volume_ratio > 1.5:
        score += 5
        reasoning.append(f"✓ Volume {volume_ratio:.1f}x average (strong confirmation)")
    elif volume_ratio > 1.2:
        score += 3
        reasoning.append(f"~ Volume {volume_ratio:.1f}x average (moderate confirmation)")
    else:
        reasoning.append(f"✗ Volume {volume_ratio:.1f}x — insufficient to confirm")

    # 3. Minervini criteria 5 & 6: 52-week range (5 points)
    # Crit. 5: price >= 30% above annual low (not at the bottom)
    # Crit. 6: price within 25% of annual high (near highs)
    range_score = 0
    if high_52w > 0 and low_52w > 0:
        pct_above_low = (price - low_52w) / low_52w * 100
        pct_below_high = (high_52w - price) / high_52w * 100

        if pct_above_low >= 30:
            range_score += 3
            reasoning.append(f"✓ {pct_above_low:.0f}% above annual low (Minervini crit.5: ≥30%)")
        else:
            reasoning.append(f"✗ Only {pct_above_low:.0f}% above annual low (<30% — possible Stage 1)")

        if pct_below_high <= 25:
            range_score += 2
            reasoning.append(f"✓ Within {pct_below_high:.0f}% of annual high (Minervini crit.6: ≤25%)")
        else:
            reasoning.append(f"✗ {pct_below_high:.0f}% below annual high (>25% — far from highs)")
    else:
        range_score += 2  # Partial points if no 52w data
        reasoning.append("~ No 52-week range data (assuming valid setup)")

    score += range_score

    # 4. Relative Strength vs market (3 points) — Minervini criterion 7
    # RS 60 days: stock vs SPY
    if price_60d_ago > 0 and spy_price_60d_ago > 0 and spy_price > 0:
        stock_return_60d = (price - price_60d_ago) / price_60d_ago
        spy_return_60d = (spy_price - spy_price_60d_ago) / spy_price_60d_ago
        rs_ratio = stock_return_60d / spy_return_60d if spy_return_60d != 0 else 1.0

        if rs_ratio >= 1.5:
            score += 3
            reasoning.append(f"✓ RS {rs_ratio:.1f}x market in 60d (market leader)")
        elif rs_ratio >= 1.1:
            score += 2
            reasoning.append(f"✓ RS {rs_ratio:.1f}x market (outperforming)")
        elif rs_ratio >= 0.8:
            score += 1
            reasoning.append(f"~ RS {rs_ratio:.1f}x market (in line with index)")
        else:
            reasoning.append(f"✗ RS {rs_ratio:.1f}x market — underperforming SPY")
    else:
        score += 1  # Neutral without data
        reasoning.append("~ No RS vs SPY data (assuming neutral)")

    # 5. Not overextended (3 points) — avoid chasing
    if price > high_20d:
        extension = (price - high_20d) / high_20d * 100
        if extension < 5:
            score += 3
            reasoning.append(f"✓ Early entry: only {extension:.1f}% above pivot")
        elif extension < 10:
            score += 1
            reasoning.append(f"~ Moderate extension: {extension:.1f}% above pivot")
        else:
            reasoning.append(f"✗ Overextended: {extension:.1f}% above pivot (chase risk)")
    else:
        score += 2
        reasoning.append("~ Not at breakout, no overextension")

    # 6. ATR favorable for stop (2 points)
    if price > 0 and atr > 0:
        atr_pct = atr / price * 100
        if 2 <= atr_pct <= 6:
            score += 2
            reasoning.append(f"✓ ATR {atr_pct:.1f}% — manageable stop")
        elif 1 <= atr_pct <= 8:
            score += 1
            reasoning.append(f"~ ATR {atr_pct:.1f}% — acceptable")
        else:
            reasoning.append(f"✗ ATR {atr_pct:.1f}% — {'too volatile' if atr_pct > 8 else 'too low'}")
    else:
        reasoning.append("✗ No ATR data")

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
