"""
Stage 4 Rejection — Stan Weinstein Methodology

"Secrets for Profiting in Bull and Bear Markets" (Weinstein, 1988)
Stage 4: price below the declining SMA 150 (30-week).
The failed rally toward SMA 150 is the ideal short entry.

References: github.com/bharatsharma1769/StanWeinstein
            github.com/ksanjay/stage-analysis-stocks

Score: 0-30 points
- Stage 4 confirmed (price < declining SMA150, EMA50 < SMA150): 15 pts
- Rejected bounce (price rallied to SMA150 and is now falling): 10 pts
- Declining volume during bounce (no bullish conviction): 5 pts
"""

from typing import Dict


def evaluate_stage4_rejection(ticker_data: Dict) -> Dict:
    """
    Evaluate Stage 4 setup with rejected bounce.

    Suggested stop: 3% above SMA 150 (clear structure-based stop).
    Target: 20% below entry (Stage 4 can last weeks/months).
    """
    price = ticker_data.get("price", 0)
    sma_150 = ticker_data.get("sma_150", 0)
    sma_150_20d_ago = ticker_data.get("sma_150_20d_ago", sma_150)
    price_5d_ago = ticker_data.get("price_5d_ago", price)
    price_10d_ago = ticker_data.get("price_10d_ago", price)
    ema_50 = ticker_data.get("ema_50", 0)
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)

    score = 0
    reasoning = []

    if price <= 0 or sma_150 <= 0:
        return _empty_result("No price or SMA150 data (requires 150 days of history)")

    price_below_sma150 = price < sma_150
    sma_declining = (sma_150 < sma_150_20d_ago * 0.999) if sma_150_20d_ago > 0 else False
    ema50_below_sma150 = (ema_50 < sma_150) if ema_50 > 0 else False

    # 1. Stage 4 confirmed (15 points — primary gate)
    if price_below_sma150 and sma_declining and ema50_below_sma150:
        score += 15
        decline_pct = (sma_150_20d_ago - sma_150) / sma_150_20d_ago * 100 if sma_150_20d_ago > 0 else 0
        reasoning.append(f"✓✓ Full Stage 4: price<SMA150 declining ({decline_pct:.1f}%/20d), EMA50<SMA150")
    elif price_below_sma150 and sma_declining:
        score += 10
        reasoning.append("✓ Partial Stage 4: price<SMA150 declining (EMA50 still above SMA150)")
    elif price_below_sma150:
        score += 5
        reasoning.append("~ Price below SMA150 but decline not confirmed — possible Stage 1/4 transition")
    else:
        pct_above = (price - sma_150) / sma_150 * 100
        reasoning.append(f"✗ Price {pct_above:.1f}% ABOVE SMA150 — not Stage 4, Weinstein short does not apply")
        return {
            "style": "stage4_rejection",
            "score": 0,
            "max_score": 30,
            "reasoning": reasoning,
            "signals": {
                "stage": 2,
                "price_vs_sma150_pct": round(pct_above, 1),
                "sma150_declining": False,
                "bounce_detected": False,
                "stop_suggested": 0,
                "target_suggested": 0
            }
        }

    # 2. Rejected bounce pattern (10 points)
    # Price rallied toward SMA150 recently and is now turning back down
    bounce_high = max(price_5d_ago, price_10d_ago)
    distance_at_closest_pct = abs(bounce_high - sma_150) / sma_150 * 100
    currently_declining = price < price_5d_ago

    if distance_at_closest_pct <= 3 and currently_declining:
        score += 10
        reasoning.append(f"✓✓ Perfect rejected bounce: touched SMA150 ({distance_at_closest_pct:.1f}%) and falling")
    elif distance_at_closest_pct <= 7 and currently_declining:
        score += 7
        reasoning.append(f"✓ Bounce near SMA150 ({distance_at_closest_pct:.1f}%) with price declining")
    elif distance_at_closest_pct <= 12:
        score += 3
        reasoning.append(f"~ Partial bounce at {distance_at_closest_pct:.1f}% from SMA150 — monitor")
    else:
        reasoning.append(f"✗ No bounce toward SMA150 ({distance_at_closest_pct:.1f}% away) — setup not mature")

    # 3. Declining volume on bounce (5 points)
    # Low volume during rally = no bullish conviction
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    if vol_ratio < 0.7:
        score += 5
        reasoning.append(f"✓✓ Very low volume on bounce ({vol_ratio:.1f}x) — bulls without conviction")
    elif vol_ratio < 0.9:
        score += 3
        reasoning.append(f"✓ Low volume ({vol_ratio:.1f}x) — weak rally")
    elif vol_ratio <= 1.1:
        score += 1
        reasoning.append(f"~ Normal volume ({vol_ratio:.1f}x)")
    else:
        reasoning.append(f"✗ Elevated volume ({vol_ratio:.1f}x) on bounce — mixed signal")

    stop_suggested = round(sma_150 * 1.03, 2)
    target_suggested = round(price * 0.80, 2)

    return {
        "style": "stage4_rejection",
        "score": min(score, 30),
        "max_score": 30,
        "reasoning": reasoning,
        "signals": {
            "stage": 4 if price_below_sma150 else 2,
            "price_vs_sma150_pct": round((price - sma_150) / sma_150 * 100, 1),
            "sma150_declining": sma_declining,
            "bounce_detected": distance_at_closest_pct <= 12,
            "stop_suggested": stop_suggested,
            "target_suggested": target_suggested
        }
    }


def _empty_result(reason: str) -> Dict:
    return {
        "style": "stage4_rejection",
        "score": 0,
        "max_score": 30,
        "reasoning": [f"✗ {reason}"],
        "signals": {
            "stage": 0, "price_vs_sma150_pct": 0,
            "sma150_declining": False, "bounce_detected": False,
            "stop_suggested": 0, "target_suggested": 0
        }
    }
