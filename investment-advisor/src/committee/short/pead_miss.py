"""
PEAD Miss Short — Post-Earnings Announcement Drift (Short Side)

Documented anomaly since 1968 (Ball & Brown). Persists to this day.
Earnings miss > 10% → price continues falling 10-20 days post-announcement.
Drift strongest in small/mid caps and when day-0 volume is high.

References:
- Ball & Brown (1968), Bernard & Thomas (1989)
- QuantPedia: quantpedia.com/strategies/post-earnings-announcement-effect/
- github.com/aniketnmishra/PEAD
- github.com/gen-li/Replicate_PEAD

Score: 0-25 points
- EPS miss magnitude: 8 pts
- Day-0 market reaction (EAR): 7 pts
- Timing (sweet spot 2-10 days post-announcement): 5 pts
- Volume on earnings day (higher = stronger drift): 5 pts
"""

from typing import Dict, Optional


def evaluate_pead_miss(ticker_data: Dict, catalyst_info: Optional[Dict] = None) -> Dict:
    """
    Evaluate PEAD Miss setup for short.

    Requires recent earnings data (via Finnhub).
    Entry: day 2 post-earnings (avoid day-0 spike).
    Stop: above the post-earnings day high.
    Target: 10-20% down in 10-20 days.
    """
    eps_surprise_pct = ticker_data.get("eps_surprise_pct")
    earnings_reaction_pct = ticker_data.get("earnings_reaction_pct")
    days_since_earnings = ticker_data.get("days_since_earnings")
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    earnings_day_volume_ratio = ticker_data.get("earnings_day_volume_ratio")

    # No earnings data: score 0 (does not penalize other signals)
    if eps_surprise_pct is None or days_since_earnings is None:
        return {
            "style": "pead_miss",
            "score": 0,
            "max_score": 25,
            "reasoning": ["~ No recent earnings data (PEAD requires active Finnhub key)"],
            "signals": {
                "eps_surprise_pct": None,
                "earnings_reaction_pct": None,
                "days_since_earnings": None,
                "pead_active": False
            }
        }

    # No significant miss: PEAD short does not apply
    if eps_surprise_pct >= -5:
        return {
            "style": "pead_miss",
            "score": 0,
            "max_score": 25,
            "reasoning": [f"✗ No earnings miss (surprise: {eps_surprise_pct:+.1f}%) — PEAD short does not apply"],
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

    # 1. Miss magnitude (8 points)
    if miss_pct >= 25:
        score += 8
        reasoning.append(f"✓✓ Severe EPS miss {eps_surprise_pct:+.1f}% — shock the market takes time to digest")
    elif miss_pct >= 15:
        score += 6
        reasoning.append(f"✓ Significant EPS miss {eps_surprise_pct:+.1f}%")
    elif miss_pct >= 10:
        score += 4
        reasoning.append(f"~ Moderate EPS miss {eps_surprise_pct:+.1f}%")
    else:
        score += 2
        reasoning.append(f"~ Mild EPS miss {eps_surprise_pct:+.1f}% (limited drift expected)")

    # 2. Day-0 market reaction EAR (7 points)
    if earnings_reaction_pct is not None:
        if earnings_reaction_pct <= -5:
            score += 7
            reasoning.append(f"✓✓ Strong downside gap {earnings_reaction_pct:+.1f}% — market confirming the miss")
        elif earnings_reaction_pct <= -3:
            score += 5
            reasoning.append(f"✓ Downside gap {earnings_reaction_pct:+.1f}%")
        elif earnings_reaction_pct <= -1:
            score += 3
            reasoning.append(f"~ Mild bearish reaction {earnings_reaction_pct:+.1f}%")
        elif earnings_reaction_pct <= 2:
            score += 1
            reasoning.append("~ Market ignored the miss (flat reaction) — drift may activate later")
        else:
            reasoning.append(f"✗ Market rallied +{earnings_reaction_pct:.1f}% despite miss — contradictory signal")
    else:
        score += 2
        reasoning.append("~ No day-0 reaction data — assuming neutral")

    # 3. Post-earnings timing (5 points)
    if 2 <= days_since_earnings <= 5:
        score += 5
        reasoning.append(f"✓✓ {days_since_earnings}d post-earnings — drift sweet spot (highest probability)")
    elif 1 <= days_since_earnings <= 10:
        score += 3
        reasoning.append(f"✓ {days_since_earnings}d post-earnings — drift active")
    elif days_since_earnings == 0:
        score += 1
        reasoning.append("~ Announcement day — wait for day 1-2 to enter")
    elif days_since_earnings <= 20:
        score += 1
        reasoning.append(f"~ {days_since_earnings}d post-earnings — drift may be weakening")
    else:
        reasoning.append(f"✗ {days_since_earnings}d post-earnings — drift academically exhausted")

    # 4. Earnings day volume (5 points)
    ev_ratio = earnings_day_volume_ratio or (volume / avg_volume if avg_volume > 0 else 1.0)
    if ev_ratio >= 3.0:
        score += 5
        reasoning.append(f"✓✓ Volume {ev_ratio:.1f}x on earnings day — high conviction, faster drift")
    elif ev_ratio >= 2.0:
        score += 3
        reasoning.append(f"✓ Volume {ev_ratio:.1f}x on earnings day")
    elif ev_ratio >= 1.5:
        score += 1
        reasoning.append(f"~ Volume {ev_ratio:.1f}x on earnings day (moderate)")
    else:
        reasoning.append(f"✗ Low earnings day volume ({ev_ratio:.1f}x) — drift may be slow")

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
