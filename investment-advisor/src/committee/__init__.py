"""
Virtual Committee v3.0 — Sistema de scoring bidireccional (long + short)

Comité de LONGS (Catalyst-Driven Swing):
- Régimen de mercado (Druckenmiller): Contexto macro
- Setup técnico (Minervini + Turtles): Trend Template + breakout con volumen
- Trend alignment (Seykota + Weinstein): Stage 2 gate + EMAs alineadas
- Catalizador (PEAD + Squeeze): Timing de eventos + short squeeze detection
- Risk/Reward (Simons): Validación estadística

Comité de SHORTS (Multi-strategy):
- Parabolic Short (Qullamaggie): Climax runs y reversión
- Stage 4 Rejection (Weinstein): Rebote fallido en SMA 150 declinante
- PEAD Miss (académico): Post-earnings drift negativo
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
