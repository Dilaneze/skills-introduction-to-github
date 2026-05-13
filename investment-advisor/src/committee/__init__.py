"""
Virtual Committee v3.0 — Bidirectional scoring system (long + short)

LONG Committee (Catalyst-Driven Swing):
- Market regime (Druckenmiller): Macro context
- Technical setup (Minervini + Turtles): Trend Template + volume breakout
- Trend alignment (Seykota + Weinstein): Stage 2 gate + aligned EMAs
- Catalyst (PEAD + Squeeze): Event timing + short squeeze detection
- Risk/Reward (Simons): Statistical validation

SHORT Committee (Multi-strategy):
- Parabolic Short (Qullamaggie): Climax runs and reversal
- Stage 4 Rejection (Weinstein): Failed bounce at declining SMA 150
- PEAD Miss (academic): Post-earnings negative drift
"""

from .regime_detector import detect_regime
from .turtles import evaluate_turtles
from .seykota import evaluate_seykota, compute_weinstein_stage
from .catalyst import evaluate_catalyst
from .risk_reward import evaluate_risk_reward
from .aggregator import evaluate_opportunity
from .short import evaluate_short_opportunity

__all__ = [
    "detect_regime",
    "evaluate_turtles",
    "evaluate_seykota",
    "compute_weinstein_stage",
    "evaluate_catalyst",
    "evaluate_risk_reward",
    "evaluate_opportunity",
    "evaluate_short_opportunity"
]
