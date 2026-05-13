"""
Catalyst + Timing — Core of the catalyst-driven system

Asymmetry comes from events with a known date.

Score: 0-25 points distributed across:
- Catalyst type (earnings, FDA, M&A, etc.): 8 pts
- Temporal proximity (days to event): 7 pts
- Historical reaction of the ticker: 5 pts (if available)
- Expectation asymmetry: 5 pts
"""

from typing import Dict, Optional


# Scores by catalyst type
CATALYST_SCORES = {
    "fda_decision": 8,          # Binary, high asymmetry
    "fda_approval": 8,
    "fda": 8,
    "earnings_beat_history": 8, # Consistent beat history
    "m&a_rumor": 7,             # Takeout premium
    "m&a": 7,
    "merger": 7,
    "acquisition": 7,
    "earnings": 6,              # Predictable but with surprises
    "product_launch": 6,        # Visible execution
    "investor_day": 5,          # Guidance updates
    "conference": 4,            # Less specific
    "macro_event": 4,
    "analyst_upgrade": 5,
    "buyback": 5,
    "rumor": 2,
    "speculation": 2,
    "unknown": 2
}


def evaluate_catalyst(ticker_data: Dict, catalyst_info: Optional[Dict]) -> Dict:
    """
    Evaluate catalyst quality and timing.

    Args:
        ticker_data: {
            "symbol": str,
            "historical_earnings_reaction": float  # Avg % move on earnings (optional)
        }
        catalyst_info: {
            "type": str,
            "days_ahead": int,  # Days to event (or "days_to_event")
            "consensus_sentiment": str  # "low", "neutral", "high" (optional)
        }

    Returns:
        {
            "style": "catalyst",
            "score": int (0-25),
            "max_score": 25,
            "reasoning": list[str],
            "signals": dict
        }
    """
    score = 0
    reasoning = []

    # Check additional independent signals regardless of catalyst
    extra_signals = _check_extra_signals(ticker_data)

    # No catalyst: use neutral base score + extra signals
    if not catalyst_info:
        base_score = 14 + extra_signals["score"]
        return {
            "style": "catalyst",
            "score": min(base_score, 25),
            "max_score": 25,
            "reasoning": ["~ No identified catalyst — pure technical scoring"] + extra_signals["reasoning"],
            "signals": {
                "catalyst_type": "none",
                "days_to_event": 999,
                "historical_avg_move": 0,
                **extra_signals["signals"]
            }
        }

    catalyst_type = catalyst_info.get("type", "unknown").lower()
    days_to_event = catalyst_info.get("days_ahead") or catalyst_info.get("days_to_event", 999)
    expectations = catalyst_info.get("consensus_sentiment", "neutral").lower()
    historical_reaction = ticker_data.get("historical_earnings_reaction", 0)

    # 1. Catalyst type (8 points max)
    cat_score = 2  # Default for unknown types
    for key, value in CATALYST_SCORES.items():
        if key in catalyst_type:
            cat_score = value
            break

    score += cat_score
    emoji = "✓" if cat_score >= 6 else "~"
    reasoning.append(f"{emoji} Catalyst: {catalyst_type} ({cat_score}/8 pts)")

    # 2. Temporal proximity (7 points max)
    # Sweet spot: 3-10 days
    if 3 <= days_to_event <= 7:
        score += 7
        reasoning.append(f"✓ Optimal timing: {days_to_event} days to event")
    elif 1 <= days_to_event <= 14:
        score += 4
        reasoning.append(f"~ Acceptable timing: {days_to_event} days to event")
    elif days_to_event > 14 and days_to_event < 30:
        score += 2
        reasoning.append(f"~ Event somewhat distant: {days_to_event} days (capital tied up)")
    elif days_to_event >= 30:
        score += 1
        reasoning.append(f"✗ Event too far out: {days_to_event} days")
    else:
        score += 2
        reasoning.append(f"~ Event imminent or past ({days_to_event} days)")

    # 3. Historical reaction (5 points max)
    if historical_reaction >= 10:
        score += 5
        reasoning.append(f"✓ History: ticker moves ~{historical_reaction:.0f}% on similar events")
    elif historical_reaction >= 5:
        score += 3
        reasoning.append(f"~ History: ticker moves ~{historical_reaction:.0f}% on similar events")
    elif historical_reaction > 0:
        score += 1
        reasoning.append(f"✗ Low historical reactivity ({historical_reaction:.0f}%)")
    else:
        score += 2
        reasoning.append("~ No historical reaction data — assuming neutral")

    # 4. Expectation asymmetry (5 points max)
    if expectations == "low" and catalyst_type in ["earnings", "fda_decision", "fda", "product_launch"]:
        score += 5
        reasoning.append("✓ Low expectations → potential positive surprise")
    elif expectations == "neutral":
        score += 3
        reasoning.append("~ Neutral expectations")
    elif expectations == "high":
        score += 1
        reasoning.append("✗ High expectations → limited upside, downside if disappoints")
    else:
        score += 3
        reasoning.append("~ Unknown expectations (assuming neutral)")

    score += extra_signals["score"]
    reasoning += extra_signals["reasoning"]

    return {
        "style": "catalyst",
        "score": min(score, 25),
        "max_score": 25,
        "reasoning": reasoning,
        "signals": {
            "catalyst_type": catalyst_type,
            "days_to_event": days_to_event,
            "historical_avg_move": historical_reaction,
            "expectations": expectations,
            **extra_signals["signals"]
        }
    }


def _check_extra_signals(ticker_data: dict) -> dict:
    """
    Additional signals independent of the main catalyst:
    1. PEAD Long: recent EPS beat → price continues drifting up
    2. Short Squeeze: high short interest + catalyst = explosive potential

    Extra score: up to +4 pts above the base catalyst score.
    """
    score = 0
    reasoning = []
    signals = {}

    # PEAD Long: recent earnings beat (via Finnhub)
    eps_surprise_pct = ticker_data.get("eps_surprise_pct")
    days_since_earnings = ticker_data.get("days_since_earnings")

    if eps_surprise_pct is not None and eps_surprise_pct > 10 and days_since_earnings is not None:
        if days_since_earnings <= 5:
            score += 4
            reasoning.append(f"✓✓ PEAD Long: EPS beat +{eps_surprise_pct:.1f}% {days_since_earnings}d ago (drift active)")
        elif days_since_earnings <= 15:
            score += 2
            reasoning.append(f"✓ PEAD Long: EPS beat +{eps_surprise_pct:.1f}% {days_since_earnings}d ago")
        signals["pead_long_active"] = True
        signals["eps_beat_pct"] = eps_surprise_pct
    else:
        signals["pead_long_active"] = False

    # Short Squeeze: high short interest + momentum = explosive potential
    short_pct = ticker_data.get("short_pct")   # % of float short
    short_ratio = ticker_data.get("short_ratio")  # days to cover

    if short_pct is not None and short_pct > 0.15:  # >15% of float short
        days_to_cover = short_ratio or 0
        if days_to_cover >= 3:
            score += 3
            reasoning.append(f"✓✓ Short squeeze setup: {short_pct*100:.0f}% float short, {days_to_cover:.1f}d to cover")
        elif short_pct > 0.20:
            score += 2
            reasoning.append(f"✓ High short interest: {short_pct*100:.0f}% of float — squeeze potential")
        signals["squeeze_potential"] = True
        signals["short_float_pct"] = short_pct
    else:
        signals["squeeze_potential"] = False

    return {"score": score, "reasoning": reasoning, "signals": signals}
