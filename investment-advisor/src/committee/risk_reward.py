"""
Risk/Reward + Sizing — Medallion-lite (Jim Simons approach)

"The Man Who Solved the Market" (Zuckerman) — without a validated statistical edge, there is no trade.

Score: 0-15 points distributed across:
- R/R ratio >= 3:1: 8 pts (mandatory for BUY)
- Stop based on structure (not arbitrary): 4 pts
- Position size coherent with ATR: 3 pts
"""

from typing import Dict, Optional


def evaluate_risk_reward(
    ticker_data: Dict,
    entry_price: float,
    stop_price: float,
    target_price: float,
    capital: float = 500.0,
    leverage: int = 5
) -> Dict:
    """
    Evaluate whether the trade has a favorable statistical edge.

    Args:
        ticker_data: {
            "atr_14": float,
            "price": float
        }
        entry_price: Proposed entry price
        stop_price: Proposed stop loss
        target_price: Proposed take profit
        capital: Available capital in EUR
        leverage: Leverage (default 5x)

    Returns:
        {
            "style": "risk_reward",
            "score": int (0-15),
            "max_score": 15,
            "reasoning": list[str],
            "signals": dict,
            "hard_reject": bool  # True if R/R < 3 (reject even if score >= 75)
        }
    """
    atr = ticker_data.get("atr_14", 0)
    price = ticker_data.get("price", entry_price)

    score = 0
    reasoning = []

    # Input validation
    if entry_price <= 0 or stop_price <= 0 or target_price <= 0:
        return {
            "style": "risk_reward",
            "score": 0,
            "max_score": 15,
            "reasoning": ["✗ Invalid prices for R/R calculation"],
            "signals": {
                "rr_ratio": 0, "stop_atr_multiple": 0,
                "suggested_position_eur": 0, "risk_eur": 0, "stop_pct": 0
            },
            "hard_reject": True
        }

    risk = entry_price - stop_price
    reward = target_price - entry_price

    if risk <= 0:
        return {
            "style": "risk_reward",
            "score": 0,
            "max_score": 15,
            "reasoning": ["✗ Invalid stop loss (must be below entry)"],
            "signals": {
                "rr_ratio": 0, "stop_atr_multiple": 0,
                "suggested_position_eur": 0, "risk_eur": capital * 0.02, "stop_pct": 0
            },
            "hard_reject": True
        }

    rr_ratio = reward / risk

    # 1. R/R ratio — core edge (8 points max)
    if rr_ratio >= 4:
        score += 8
        reasoning.append(f"✓ Excellent R/R: {rr_ratio:.1f}:1")
    elif rr_ratio >= 3:
        score += 6
        reasoning.append(f"✓ Acceptable R/R: {rr_ratio:.1f}:1 (minimum required)")
    elif rr_ratio >= 2:
        score += 3
        reasoning.append(f"~ Marginal R/R: {rr_ratio:.1f}:1 (below recommended minimum)")
    else:
        reasoning.append(f"✗ Insufficient R/R: {rr_ratio:.1f}:1 — DO NOT TRADE")

    # 2. ATR-based stop — structure vs arbitrary (4 points)
    if atr > 0 and price > 0:
        stop_in_atr = risk / atr

        if 1.5 <= stop_in_atr <= 2.5:
            score += 4
            reasoning.append(f"✓ Stop = {stop_in_atr:.1f}× ATR (well-structured)")
        elif 1 <= stop_in_atr <= 3:
            score += 2
            reasoning.append(f"~ Stop = {stop_in_atr:.1f}× ATR (acceptable)")
        else:
            if stop_in_atr < 1:
                reasoning.append(f"✗ Stop = {stop_in_atr:.1f}× ATR (too tight — noise may stop you out)")
            else:
                reasoning.append(f"✗ Stop = {stop_in_atr:.1f}× ATR (too wide — excessive risk)")
    else:
        stop_pct = risk / entry_price * 100
        if stop_pct <= 7:
            score += 2
            reasoning.append(f"~ Stop {stop_pct:.1f}% without ATR data (assuming reasonable)")
        else:
            reasoning.append(f"✗ Stop {stop_pct:.1f}% without ATR data to validate")

    # 3. Sizing validation (3 points)
    # With 500 EUR and x5 leverage, max exposure = 2500 EUR
    # Max risk 2% of capital = 10 EUR per trade
    max_risk_eur = capital * 0.02
    exposure_total = capital * leverage

    if risk > 0:
        shares_by_risk = max_risk_eur / risk
        position_value = shares_by_risk * entry_price

        if position_value <= exposure_total:
            score += 3
            reasoning.append(f"✓ Viable sizing: €{position_value:.0f} exposure for €{max_risk_eur:.0f} risk")
        elif position_value <= exposure_total * 1.2:
            score += 1
            reasoning.append(f"~ Tight sizing: €{position_value:.0f} (limit €{exposure_total:.0f})")
        else:
            reasoning.append(f"✗ Sizing exceeds capacity: needs €{position_value:.0f} (limit €{exposure_total:.0f})")
    else:
        reasoning.append("✗ Cannot calculate sizing (invalid risk)")
        position_value = 0

    # Hard reject: R/R < 3 is a knockout condition
    hard_reject = rr_ratio < 3.0

    return {
        "style": "risk_reward",
        "score": score,
        "max_score": 15,
        "reasoning": reasoning,
        "signals": {
            "rr_ratio": round(rr_ratio, 2),
            "stop_atr_multiple": round(risk / atr, 2) if atr > 0 else 0,
            "suggested_position_eur": min(position_value, exposure_total) if position_value > 0 else 0,
            "risk_eur": max_risk_eur,
            "stop_pct": round(risk / entry_price * 100, 2)
        },
        "hard_reject": hard_reject
    }
