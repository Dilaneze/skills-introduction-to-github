"""
Trend Alignment — Ed Seykota's Approach

"The trend is your friend" — Confirms you are not trading against the current.
"Market Wizards" (Schwager) — emotional risk management through trend following.

Score: 0-20 points distributed across:
- Price > EMA 20: 6 pts
- EMA 20 > EMA 50: 6 pts
- EMA 50 > EMA 200: 4 pts (long-term trend)
- Positive momentum (10 days): 4 pts
"""

from typing import Dict


def compute_weinstein_stage(ticker_data: Dict) -> int:
    """
    Classify stock into Weinstein Stage 1-4 using SMA 150 (30-week).

    Stage 1: Basing    — price < SMA150, SMA150 flat/slightly rising
    Stage 2: Advancing — price > SMA150, SMA150 rising  ← LONG
    Stage 3: Topping   — price > SMA150, SMA150 flattening
    Stage 4: Declining — price < SMA150, SMA150 declining ← SHORT

    Reference: Stan Weinstein "Secrets for Profiting in Bull and Bear Markets" (1988)
    """
    price = ticker_data.get("price", 0)
    sma_150 = ticker_data.get("sma_150", 0)
    sma_150_20d_ago = ticker_data.get("sma_150_20d_ago", sma_150)

    if price <= 0 or sma_150 <= 0:
        return 0  # Unknown — insufficient history

    price_above = price > sma_150
    # SMA considered rising if it gained >0.1% over 20 days (noise filter)
    sma_rising = sma_150 > sma_150_20d_ago * 1.001 if sma_150_20d_ago > 0 else True

    if price_above:
        return 2 if sma_rising else 3
    else:
        return 4 if not sma_rising else 1


def evaluate_seykota(ticker_data: Dict) -> Dict:
    """
    Evaluate trend alignment (trend following).

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

    # 1. Price above short EMA (6 points)
    if price > 0 and ema_20 > 0:
        if price > ema_20:
            score += 6
            pct_above = (price - ema_20) / ema_20 * 100
            reasoning.append(f"✓ Price > EMA20 (+{pct_above:.1f}% — short-term uptrend)")
        elif price >= ema_20 * 0.97:  # Very close (3%)
            score += 3
            reasoning.append("~ Price near EMA20 (key support)")
        else:
            pct_below = (ema_20 - price) / ema_20 * 100
            reasoning.append(f"✗ Price < EMA20 (-{pct_below:.1f}% — short-term weakness)")
    else:
        reasoning.append("✗ No EMA20 data")

    # 2. EMAs aligned — golden cross structure (6 points)
    if ema_20 > 0 and ema_50 > 0:
        if ema_20 > ema_50:
            score += 6
            reasoning.append("✓ EMA20 > EMA50 (bullish structure)")
        else:
            reasoning.append("✗ EMA20 < EMA50 (bearish cross)")
    else:
        reasoning.append("✗ No EMA data for structure check")

    # 3. Long-term trend (4 points)
    if ema_50 > 0 and ema_200 > 0:
        if ema_50 > ema_200:
            score += 4
            reasoning.append("✓ EMA50 > EMA200 (major uptrend)")
        else:
            reasoning.append("✗ EMA50 < EMA200 (major downtrend — against the trend)")
    else:
        if ema_50 > 0:
            score += 2
            reasoning.append("~ No EMA200 (assuming neutral long-term trend)")
        else:
            reasoning.append("✗ No long EMA data")

    # 4. Recent momentum (4 points)
    if price > 0 and price_10d_ago > 0:
        momentum = (price - price_10d_ago) / price_10d_ago * 100

        if momentum > 5:
            score += 4
            reasoning.append(f"✓ Strong momentum +{momentum:.1f}% in 10d")
        elif momentum > 2:
            score += 3
            reasoning.append(f"✓ Positive momentum +{momentum:.1f}% in 10d")
        elif momentum > 0:
            score += 2
            reasoning.append(f"~ Mild momentum +{momentum:.1f}% in 10d")
        elif momentum > -3:
            score += 1
            reasoning.append(f"~ Near-flat momentum {momentum:.1f}% in 10d")
        else:
            reasoning.append(f"✗ Negative momentum {momentum:.1f}% in 10d")
    else:
        reasoning.append("✗ No momentum data")

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
