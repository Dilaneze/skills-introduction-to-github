"""
Short Committee Aggregator — Short position orchestrator

Combines Parabolic + Stage4Rejection + PEAD_Miss with regime context.
Regime favors shorts in RISK-OFF markets (inverse of the long committee).

Total score: 100 pts
- Regime (inverted vs longs): 0-15 pts
- Parabolic (Qullamaggie): 0-30 pts
- Stage 4 Rejection (Weinstein): 0-30 pts
- PEAD Miss: 0-25 pts

SHORT:           >= 55 pts
WATCHLIST_SHORT: 40-54 pts
SKIP:            < 40 pts
"""

from typing import Dict, Optional

from .parabolic import evaluate_parabolic
from .stage4_rejection import evaluate_stage4_rejection
from .pead_miss import evaluate_pead_miss

# Inverted regime: RISK-OFF favors shorts
_REGIME_SHORT = {
    "risk_off": 15,
    "neutral": 10,
    "risk_on": 5,
    "unknown": 8,
}

# eToro overnight cost for short positions (~8.25%/year)
_ETORO_SHORT_DAILY_PCT = 0.0226


def evaluate_short_opportunity(
    ticker: str,
    ticker_data: Dict,
    market_data: Dict,
    catalyst_info: Optional[Dict] = None,
    capital: float = 500.0,
    leverage: int = 5
) -> Dict:
    """
    Evaluate a short selling opportunity.

    For shorts on eToro (CFDs):
    - Stop ABOVE entry (5-8%)
    - Target BELOW entry (15-25%)
    - Minimum R/R 2:1 (short win rate ~45-55%)
    - Max 10 days before fees erode profit
    """
    price = ticker_data.get("price", 0)

    if price <= 0:
        return _error_result(ticker, "No price data")

    # Entry for short slightly above current price
    entry = price * 1.002

    # Stop based on structure: SMA150 (Stage 4) or ATR (parabolic)
    sma_150 = ticker_data.get("sma_150", 0)
    atr = ticker_data.get("atr_14", 0)

    if sma_150 > price and sma_150 > 0:
        # Stage 4: natural stop at SMA150 + 3% margin
        stop = sma_150 * 1.03
    elif atr > 0:
        # Parabolic: stop = 2×ATR above entry
        stop = entry + (atr * 2)
    else:
        stop = entry * 1.065  # 6.5% default stop

    # Target: minimum R/R 2.5:1 AND at least 15% decline
    risk = stop - entry
    target_rr25 = entry - (risk * 2.5)
    target_15pct = entry * 0.85
    target = min(target_rr25, target_15pct)  # The lower of the two

    # Regime (inverted for shorts)
    vix = market_data.get("vix")
    spy_trend = market_data.get("spy_above_200ema", True)

    if vix is None:
        regime_type = "unknown"
    elif vix > 25 or not spy_trend:
        regime_type = "risk_off"
    elif vix < 18 and spy_trend:
        regime_type = "risk_on"
    else:
        regime_type = "neutral"

    regime_score = _REGIME_SHORT.get(regime_type, 8)
    vix_str = f"{vix:.1f}" if vix else "N/A"
    regime_reasoning = [
        f"Regime {regime_type} (VIX: {vix_str}) — "
        + ("favorable for shorts ↓" if regime_score >= 12
           else "bull market, shorts harder ↑" if regime_score <= 5
           else "neutral for shorts")
    ]

    # Evaluate three components
    parabolic = evaluate_parabolic(ticker_data)
    stage4 = evaluate_stage4_rejection(ticker_data)
    pead = evaluate_pead_miss(ticker_data, catalyst_info)

    raw_score = regime_score + parabolic["score"] + stage4["score"] + pead["score"]
    final_score = min(raw_score, 100)

    # R/R for short
    rr_ratio = (entry - target) / (stop - entry) if (stop - entry) > 0 else 0
    stop_pct = (stop - entry) / entry * 100
    target_pct = (entry - target) / entry * 100

    hard_reject = rr_ratio < 2.0

    # Position sizing (more conservative than longs: 1.5% risk per trade)
    max_risk_eur = capital * 0.015
    if (stop - entry) > 0:
        position_eur = min(
            max_risk_eur / ((stop - entry) / entry),
            capital * leverage * 0.10
        )
    else:
        position_eur = 0

    # Max days before fees become material (>3% of target move)
    if target_pct > 0 and _ETORO_SHORT_DAILY_PCT > 0:
        max_hold_days = int((target_pct * 0.15) / (_ETORO_SHORT_DAILY_PCT * leverage))
    else:
        max_hold_days = 10

    if hard_reject:
        decision = "REJECT_SHORT"
        decision_reason = f"R/R {rr_ratio:.1f}:1 — insufficient for short (minimum 2:1)"
    elif final_score >= 55:
        decision = "SHORT"
        decision_reason = f"Score {final_score}/100 — high-conviction short"
    elif final_score >= 40:
        decision = "WATCHLIST_SHORT"
        decision_reason = f"Score {final_score}/100 — monitor for short entry"
    else:
        decision = "SKIP_SHORT"
        decision_reason = f"Score {final_score}/100 — insufficient setup"

    return {
        "ticker": ticker,
        "direction": "SHORT",
        "decision": decision,
        "decision_reason": decision_reason,
        "final_score": final_score,
        "breakdown": {
            "regime": regime_score,
            "parabolic": parabolic["score"],
            "stage4_rejection": stage4["score"],
            "pead_miss": pead["score"],
            "raw_score": raw_score
        },
        "reasoning": {
            "regime": regime_reasoning,
            "parabolic": parabolic["reasoning"],
            "stage4_rejection": stage4["reasoning"],
            "pead_miss": pead["reasoning"]
        },
        "signals": {
            "regime_type": regime_type,
            "parabolic": parabolic["signals"],
            "stage4": stage4["signals"],
            "pead": pead["signals"]
        },
        "trade_params": {
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(target, 2),
            "stop_pct": round(stop_pct, 2),
            "target_pct": round(target_pct, 2),
            "rr_ratio": round(rr_ratio, 2),
            "position_eur": round(position_eur, 0),
            "etoro_overnight_daily_pct": _ETORO_SHORT_DAILY_PCT,
            "max_hold_days_before_fees_material": max_hold_days
        }
    }


def _error_result(ticker: str, msg: str) -> Dict:
    return {
        "ticker": ticker, "direction": "SHORT",
        "decision": "SKIP_SHORT", "decision_reason": msg,
        "final_score": 0,
        "breakdown": {"regime": 0, "parabolic": 0, "stage4_rejection": 0, "pead_miss": 0, "raw_score": 0},
        "reasoning": {"regime": [msg], "parabolic": [], "stage4_rejection": [], "pead_miss": []},
        "signals": {},
        "trade_params": {
            "entry": 0, "stop": 0, "target": 0,
            "stop_pct": 0, "target_pct": 0, "rr_ratio": 0,
            "position_eur": 0, "etoro_overnight_daily_pct": _ETORO_SHORT_DAILY_PCT,
            "max_hold_days_before_fees_material": 0
        }
    }
