"""
Short Selling Committee — Sistema de scoring para posiciones en corto

El comité evalúa setups de short selling desde tres perspectivas independientes:
- Parabolic Short (Qullamaggie): Climax runs y agotamiento de momentum
- Stage 4 Rejection (Weinstein): Rebotes rechazados en SMA 150 declinante
- PEAD Miss (académico): Post-Earnings Announcement Drift negativo
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
