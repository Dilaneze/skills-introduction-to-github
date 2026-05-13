"""
Market Regime Detector — Inspired by Stanley Druckenmiller

"Don't fight the tape" — Macro context determines whether the environment favors trading.

Score: 0-15 points
"""

from typing import Dict, Optional


def detect_regime(market_data: Dict) -> Dict:
    """
    Analyze macro conditions and return regime + partial score.

    Args:
        market_data: {
            "vix": float,
            "vix_change_5d": float,  # % change over 5 days (optional)
            "spy_above_200ema": bool,
            "sp500_change": float,   # day % change
            "advance_decline_ratio": float,  # breadth (optional)
            "put_call_ratio": float  # (optional)
        }

    Returns:
        {
            "regime": str,
            "score": int (0-15),
            "reasoning": str,
            "sector_bias": dict
        }
    """
    vix = market_data.get("vix")
    sp500_change = market_data.get("sp500_change", 0)
    spy_trend = market_data.get("spy_above_200ema", True)  # Assume bullish if no data
    breadth = market_data.get("advance_decline_ratio", 1.0)

    if vix is None:
        return {
            "regime": "unknown",
            "score": 10,
            "reasoning": "No VIX data — assuming neutral conditions",
            "sector_bias": {"boost": [], "penalize": []}
        }

    # RISK-ON (favorable for longs)
    if vix < 18 and spy_trend and breadth >= 1.2:
        return {
            "regime": "risk_on",
            "score": 15,
            "reasoning": f"VIX low ({vix:.1f}), SPY above 200 EMA, expanding breadth ({breadth:.2f}). Optimal breakout environment.",
            "sector_bias": {
                "boost": ["tech", "consumer_discretionary", "semiconductors"],
                "penalize": []
            }
        }

    # RISK-ON moderate (VIX low only)
    if vix < 18 and spy_trend:
        return {
            "regime": "risk_on",
            "score": 15,
            "reasoning": f"VIX low ({vix:.1f}), market in uptrend. Good environment for longs.",
            "sector_bias": {
                "boost": ["tech", "consumer_discretionary", "semiconductors"],
                "penalize": []
            }
        }

    # RISK-OFF (defensive)
    if vix > 25 or (vix > 20 and not spy_trend):
        score = 5 if vix < 30 else 0  # Extreme panic = do not trade
        severity = "extreme" if vix >= 30 else "high"
        return {
            "regime": "risk_off",
            "score": score,
            "reasoning": f"VIX {severity} ({vix:.1f}), market in defensive mode. Trend-follow only in safe-haven assets.",
            "sector_bias": {
                "boost": ["utilities", "healthcare", "staples"],
                "penalize": ["tech", "growth", "small_caps"]
            }
        }

    # NEUTRAL (selective)
    return {
        "regime": "neutral",
        "score": 10,
        "reasoning": f"VIX moderate ({vix:.1f}), mixed conditions. Trade only high-conviction setups.",
        "sector_bias": {
            "boost": [],
            "penalize": []
        }
    }


def apply_sector_adjustment(base_score: int, sector: Optional[str], regime_info: Dict) -> int:
    """
    Adjust score by sector and regime.

    Args:
        base_score: Base score before adjustment
        sector: Stock sector (can be None)
        regime_info: Dict returned by detect_regime()

    Returns:
        Adjusted score (+5 boost or -10 penalty)
    """
    if not sector:
        return base_score

    sector_bias = regime_info.get("sector_bias", {})
    boost = sector_bias.get("boost", [])
    penalize = sector_bias.get("penalize", [])

    sector_lower = sector.lower()

    if any(b.lower() in sector_lower for b in boost):
        return min(base_score + 5, 100)

    if any(p.lower() in sector_lower for p in penalize):
        return max(base_score - 10, 0)

    return base_score
