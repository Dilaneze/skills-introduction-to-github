"""
Virtual Committee - Sistema de scoring basado en estrategias de traders legendarios

El comité evalúa oportunidades desde múltiples perspectivas independientes:
- Régimen de mercado (Druckenmiller): Contexto macro
- Setup técnico (Turtles): Breakouts con volumen
- Trend alignment (Seykota): Seguimiento de tendencia
- Catalizador + timing: Core del sistema catalyst-driven
- Risk/Reward (Simons): Validación estadística
"""

from .regime_detector import detect_regime
from .turtles import evaluate_turtles
from .seykota import evaluate_seykota
from .catalyst import evaluate_catalyst
from .risk_reward import evaluate_risk_reward
from .aggregator import evaluate_opportunity

__all__ = [
    "detect_regime",
    "evaluate_turtles",
    "evaluate_seykota",
    "evaluate_catalyst",
    "evaluate_risk_reward",
    "evaluate_opportunity"
]
