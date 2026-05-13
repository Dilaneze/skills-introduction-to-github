"""
Parabolic Short — Qullamaggie Methodology

"My 3 Timeless Setups" — qullamaggie.com
Stocks that run 100-500% in months and then accelerate always revert.
The edge: identify exhaustion BEFORE the market discounts it.

Score: 0-30 points
- Extension above SMA 50 (distance from equilibrium): 10 pts
- Prior 60-day run (the run that precedes the parabolic): 8 pts
- Extreme overbought RSI (buyer exhaustion): 7 pts
- Recent volume climax (institutional distribution disguised as euphoria): 5 pts
"""

from typing import Dict


def evaluate_parabolic(ticker_data: Dict) -> Dict:
    """
    Evaluate parabolic short setup. Higher score = more overextended
    and higher probability of mean-reversion.

    Ideal entry: first crack (close below EMA 20 after parabolic run).
    Stop: 5-8% above entry.
    Target: reversion to SMA 50 (20-40% below).
    """
    price = ticker_data.get("price", 0)
    ema_50 = ticker_data.get("ema_50", 0)
    price_60d_ago = ticker_data.get("price_60d_ago", price)
    rsi_14 = ticker_data.get("rsi_14", 50)
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    ema_20 = ticker_data.get("ema_20", 0)
    price_5d_ago = ticker_data.get("price_5d_ago", price)

    score = 0
    reasoning = []

    if price <= 0:
        return _empty_result("No price data")

    # 1. Extension above SMA 50 (10 points)
    if ema_50 > 0:
        extension_pct = (price - ema_50) / ema_50 * 100
        if extension_pct >= 50:
            score += 10
            reasoning.append(f"✓✓ {extension_pct:.0f}% above SMA50 — extreme parabolic, reversion near-certain")
        elif extension_pct >= 30:
            score += 7
            reasoning.append(f"✓ {extension_pct:.0f}% above SMA50 — very extended, setup maturing")
        elif extension_pct >= 15:
            score += 4
            reasoning.append(f"~ {extension_pct:.0f}% above SMA50 — extended but not extreme")
        elif extension_pct >= 5:
            score += 1
            reasoning.append(f"✗ Only {extension_pct:.0f}% above SMA50 — insufficient extension for parabolic")
        else:
            reasoning.append("✗ Price near or below SMA50 — no parabolic setup")
    else:
        reasoning.append("✗ No SMA50 data")

    # 2. Prior 60-day run (8 points) — the run that creates the parabolic
    if price_60d_ago > 0 and price_60d_ago != price:
        run_60d = (price - price_60d_ago) / price_60d_ago * 100
        if run_60d >= 100:
            score += 8
            reasoning.append(f"✓✓ +{run_60d:.0f}% in 60 days — parabolic run confirmed (>100%)")
        elif run_60d >= 50:
            score += 6
            reasoning.append(f"✓ +{run_60d:.0f}% in 60 days — strong run")
        elif run_60d >= 30:
            score += 4
            reasoning.append(f"~ +{run_60d:.0f}% in 60 days — moderate momentum")
        elif run_60d >= 15:
            score += 1
            reasoning.append(f"✗ Only +{run_60d:.0f}% in 60d — insufficient for parabolic short")
        else:
            reasoning.append(f"✗ No significant prior run ({run_60d:.0f}% in 60d)")
    else:
        reasoning.append("✗ No 60-day historical data")

    # 3. Extreme RSI (7 points) — buyer exhaustion
    if rsi_14 >= 85:
        score += 7
        reasoning.append(f"✓✓ RSI {rsi_14:.0f} — extreme exhaustion (bears loading up)")
    elif rsi_14 >= 80:
        score += 5
        reasoning.append(f"✓ RSI {rsi_14:.0f} — overbought")
    elif rsi_14 >= 75:
        score += 2
        reasoning.append(f"~ RSI {rsi_14:.0f} — elevated but not extreme")
    else:
        reasoning.append(f"✗ RSI {rsi_14:.0f} — no exhaustion signal")

    # 4. Volume climax (5 points) — institutional distribution disguised as euphoria
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    if vol_ratio >= 2.5:
        score += 5
        reasoning.append(f"✓✓ Volume climax {vol_ratio:.1f}x — likely institutional distribution")
    elif vol_ratio >= 1.5:
        score += 3
        reasoning.append(f"✓ Elevated volume {vol_ratio:.1f}x")
    elif vol_ratio >= 1.1:
        score += 1
        reasoning.append(f"~ Slightly elevated volume {vol_ratio:.1f}x")
    else:
        reasoning.append(f"✗ Normal volume {vol_ratio:.1f}x — no climax")

    # Entry trigger: has the first crack started?
    entry_trigger = "PENDING"
    if ema_20 > 0:
        if price < ema_20 and price_5d_ago > ema_20:
            entry_trigger = "ACTIVE"
            reasoning.append("🎯 ENTRY ACTIVE: first crack below EMA20 confirmed")
        elif price < ema_20:
            entry_trigger = "PAST_ENTRY"
            reasoning.append("~ Already below EMA20 (optimal entry was a few days ago)")
        else:
            reasoning.append("⏳ Still above EMA20 — wait for first crack to enter short")

    return {
        "style": "parabolic",
        "score": min(score, 30),
        "max_score": 30,
        "reasoning": reasoning,
        "signals": {
            "extension_vs_sma50_pct": round((price - ema_50) / ema_50 * 100, 1) if ema_50 > 0 else 0,
            "run_60d_pct": round((price - price_60d_ago) / price_60d_ago * 100, 1) if price_60d_ago > 0 else 0,
            "rsi_14": rsi_14,
            "volume_ratio": round(vol_ratio, 2),
            "entry_trigger": entry_trigger
        }
    }


def _empty_result(reason: str) -> Dict:
    return {
        "style": "parabolic",
        "score": 0,
        "max_score": 30,
        "reasoning": [f"✗ {reason}"],
        "signals": {
            "extension_vs_sma50_pct": 0, "run_60d_pct": 0,
            "rsi_14": 0, "volume_ratio": 0, "entry_trigger": "NONE"
        }
    }
