"""
Short Selling Committee — Scoring system for short positions

The committee evaluates short selling setups from three independent perspectives:
- Parabolic Short (Qullamaggie): Climax runs and momentum exhaustion
- Stage 4 Rejection (Weinstein): Failed bounces at declining SMA 150
- PEAD Miss (academic): Post-Earnings Announcement Drift (negative)
"""

from .parabolic import evaluate_parabolic
from .stage4_rejection import evaluate_stage4_rejection
from .pead_miss import evaluate_pead_miss
from .aggregator import evaluate_short_opportunity

__all__ = [
    "evaluate_parabolic",
    "evaluate_stage4_rejection",
    "evaluate_pead_miss",
    "evaluate_short_opportunity"
]
