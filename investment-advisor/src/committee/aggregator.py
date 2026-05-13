"""
Aggregator — Virtual Committee Orchestrator

Runs all evaluators and generates final score with complete reasoning.
"""

from typing import Dict, Optional
from .regime_detector import detect_regime, apply_sector_adjustment
from .turtles import evaluate_turtles
from .seykota import evaluate_seykota, compute_weinstein_stage
from .catalyst import evaluate_catalyst
from .risk_reward import evaluate_risk_reward


def evaluate_opportunity(
    ticker: str,
    ticker_data: Dict,
    market_data: Dict,
    catalyst_info: Optional[Dict] = None,
    entry: Optional[float] = None,
    stop: Optional[float] = None,
    target: Optional[float] = None,
    capital: float = 500.0,
    leverage: int = 5
) -> Dict:
    """
    Run all evaluators and produce a final score with complete reasoning.

    Args:
        ticker: Stock symbol
        ticker_data: Price data and technical indicators
        market_data: General market data (VIX, S&P 500, etc.)
        catalyst_info: Catalyst information (optional)
        entry: Proposed entry price (if None, uses current price)
        stop: Proposed stop loss (if None, calculated automatically)
        target: Proposed take profit (if None, calculated automatically)
        capital: Available capital
        leverage: Leverage multiplier

    Returns:
        {
            "ticker": str,
            "decision": str,  # "BUY", "WATCHLIST", "SKIP", "REJECT"
            "decision_reason": str,
            "final_score": int (0-100),
            "regime": dict,
            "breakdown": dict,
            "reasoning": dict,
            "trade_params": dict
        }
    """
    price = ticker_data.get("price", 0)

    if price <= 0:
        return _error_result(ticker, "No price data available")

    # Weinstein gate: do not buy in Stage 4 (confirmed decline)
    # Stage 4 = price < declining SMA150 → short territory, not long
    stage = compute_weinstein_stage(ticker_data)
    if stage == 4:
        return _skip_stage4_result(ticker, price)

    if entry is None:
        entry = price * 0.995  # Small discount for limit order

    if stop is None:
        atr = ticker_data.get("atr_14", 0)
        beta = ticker_data.get("beta", 1.5)

        if atr > 0:
            stop = price - (atr * 2)  # Turtles-style stop: 2× ATR
        else:
            if beta >= 2.0:
                stop_pct = 10.0
            elif beta >= 1.5:
                stop_pct = 8.0
            else:
                stop_pct = 6.0
            stop = price * (1 - stop_pct / 100)

    if target is None:
        change_pct = ticker_data.get("change_pct", 0)
        if change_pct and change_pct > 2:
            target_pct = 20.0  # Strong momentum
        else:
            target_pct = 15.0  # Conservative
        target_fixed = price * (1 + target_pct / 100)
        risk = entry - stop
        target_rr3 = entry + (risk * 3)  # Minimum 3:1 R/R
        target = max(target_fixed, target_rr3)

    # 1. Detect regime
    regime = detect_regime(market_data)

    # 2. Evaluate each component
    turtles = evaluate_turtles(ticker_data)
    seykota = evaluate_seykota(ticker_data)
    catalyst = evaluate_catalyst(ticker_data, catalyst_info)
    risk_reward = evaluate_risk_reward(ticker_data, entry, stop, target, capital, leverage)

    # 3. Sum scores
    raw_score = (
        regime["score"] +
        turtles["score"] +
        seykota["score"] +
        catalyst["score"] +
        risk_reward["score"]
    )

    # 4. Sector/regime adjustment
    sector = ticker_data.get("sector")
    final_score = apply_sector_adjustment(raw_score, sector, regime)
    sector_adjustment = final_score - raw_score

    # 5. Hard reject check
    hard_reject = risk_reward.get("hard_reject", False)

    if hard_reject:
        decision = "REJECT"
        decision_reason = "R/R < 3:1 — does not meet mandatory minimum"
    elif final_score >= 70:
        decision = "BUY"
        decision_reason = f"Score {final_score}/100 — high-conviction opportunity"
    elif final_score >= 58:
        decision = "WATCHLIST"
        decision_reason = f"Score {final_score}/100 — monitor for better entry"
    else:
        decision = "SKIP"
        decision_reason = f"Score {final_score}/100 — insufficient conviction"

    return {
        "ticker": ticker,
        "decision": decision,
        "decision_reason": decision_reason,
        "final_score": final_score,
        "regime": regime,
        "breakdown": {
            "regime": regime["score"],
            "turtles": turtles["score"],
            "seykota": seykota["score"],
            "catalyst": catalyst["score"],
            "risk_reward": risk_reward["score"],
            "sector_adjustment": sector_adjustment,
            "raw_score": raw_score,
            "weinstein_stage": stage
        },
        "reasoning": {
            "regime": regime["reasoning"],
            "turtles": turtles["reasoning"],
            "seykota": seykota["reasoning"],
            "catalyst": catalyst["reasoning"],
            "risk_reward": risk_reward["reasoning"]
        },
        "trade_params": {
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "rr_ratio": risk_reward["signals"]["rr_ratio"],
            "position_eur": risk_reward["signals"]["suggested_position_eur"],
            "stop_pct": risk_reward["signals"]["stop_pct"],
            "target_pct": round((target - entry) / entry * 100, 2)
        },
        "signals": {
            "regime_type": regime["regime"],
            "turtles": turtles["signals"],
            "seykota": seykota["signals"],
            "catalyst": catalyst["signals"],
            "risk_reward": risk_reward["signals"]
        }
    }


def _skip_stage4_result(ticker: str, price: float) -> Dict:
    """Result when stock is in Weinstein Stage 4 (confirmed decline)."""
    return {
        "ticker": ticker,
        "decision": "SKIP",
        "decision_reason": "Weinstein Stage 4 — stock in decline (price < declining SMA150). Check short scanner.",
        "final_score": 0,
        "regime": {"regime": "stage4_blocked", "score": 0, "reasoning": "Stage 4 gate"},
        "breakdown": {"regime": 0, "turtles": 0, "seykota": 0, "catalyst": 0, "risk_reward": 0,
                       "sector_adjustment": 0, "raw_score": 0, "weinstein_stage": 4},
        "reasoning": {
            "regime": ["✗ Weinstein Stage 4: stock in confirmed decline — not suitable for long"],
            "turtles": [], "seykota": [], "catalyst": [], "risk_reward": []
        },
        "trade_params": {"entry": price, "stop": 0, "target": 0, "rr_ratio": 0,
                          "position_eur": 0, "stop_pct": 0, "target_pct": 0}
    }


def _error_result(ticker: str, error_msg: str) -> Dict:
    """Return error result when stock cannot be evaluated."""
    return {
        "ticker": ticker,
        "decision": "SKIP",
        "decision_reason": error_msg,
        "final_score": 0,
        "regime": {"regime": "unknown", "score": 0, "reasoning": error_msg},
        "breakdown": {
            "regime": 0, "turtles": 0, "seykota": 0, "catalyst": 0, "risk_reward": 0,
            "sector_adjustment": 0, "raw_score": 0
        },
        "reasoning": {
            "regime": [error_msg], "turtles": [], "seykota": [], "catalyst": [], "risk_reward": []
        },
        "trade_params": {
            "entry": 0, "stop": 0, "target": 0, "rr_ratio": 0,
            "position_eur": 0, "stop_pct": 0, "target_pct": 0
        },
        "signals": {}
    }
