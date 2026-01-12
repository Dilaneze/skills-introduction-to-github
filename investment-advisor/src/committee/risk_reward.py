"""
Risk/Reward + Sizing - Medallion-lite (Jim Simons approach)

"The Man Who Solved the Market" (Zuckerman) — sin edge estadístico validado, no hay trade.

Puntuación: 0-15 puntos distribuidos en:
- R/R ratio >= 3:1: 8 pts (obligatorio para >= 75 total)
- Stop basado en estructura (no arbitrario): 4 pts
- Position size coherente con ATR: 3 pts
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
    Evalúa si el trade tiene edge estadístico favorable.

    Args:
        ticker_data: {
            "atr_14": float,
            "price": float
        }
        entry_price: Precio de entrada propuesto
        stop_price: Stop loss propuesto
        target_price: Take profit propuesto
        capital: Capital disponible en EUR
        leverage: Apalancamiento (default 5x)

    Returns:
        {
            "style": "risk_reward",
            "score": int (0-15),
            "max_score": 15,
            "reasoning": list[str],
            "signals": dict,
            "hard_reject": bool  # True si R/R < 3 (rechazar aunque score >= 75)
        }
    """
    atr = ticker_data.get("atr_14", 0)
    price = ticker_data.get("price", entry_price)

    score = 0
    reasoning = []

    # Validación de inputs
    if entry_price <= 0 or stop_price <= 0 or target_price <= 0:
        return {
            "style": "risk_reward",
            "score": 0,
            "max_score": 15,
            "reasoning": ["✗ Precios inválidos para cálculo de R/R"],
            "signals": {
                "rr_ratio": 0,
                "stop_atr_multiple": 0,
                "suggested_position_eur": 0,
                "risk_eur": 0,
                "stop_pct": 0
            },
            "hard_reject": True
        }

    # Calcular riesgo y recompensa
    risk = entry_price - stop_price
    reward = target_price - entry_price

    if risk <= 0:
        return {
            "style": "risk_reward",
            "score": 0,
            "max_score": 15,
            "reasoning": ["✗ Stop loss inválido (debe estar por debajo del entry)"],
            "signals": {
                "rr_ratio": 0,
                "stop_atr_multiple": 0,
                "suggested_position_eur": 0,
                "risk_eur": capital * 0.02,
                "stop_pct": 0
            },
            "hard_reject": True
        }

    rr_ratio = reward / risk

    # 1. R/R ratio - core del edge (8 puntos máximo)
    if rr_ratio >= 4:
        score += 8
        reasoning.append(f"✓ R/R excelente: {rr_ratio:.1f}:1")
    elif rr_ratio >= 3:
        score += 6
        reasoning.append(f"✓ R/R aceptable: {rr_ratio:.1f}:1 (mínimo requerido)")
    elif rr_ratio >= 2:
        score += 3
        reasoning.append(f"~ R/R marginal: {rr_ratio:.1f}:1 (bajo mínimo recomendado)")
    else:
        reasoning.append(f"✗ R/R insuficiente: {rr_ratio:.1f}:1 — NO OPERAR")

    # 2. Stop basado en ATR - estructura vs arbitrario (4 puntos)
    if atr > 0 and price > 0:
        stop_in_atr = risk / atr

        if 1.5 <= stop_in_atr <= 2.5:
            score += 4
            reasoning.append(f"✓ Stop = {stop_in_atr:.1f}× ATR (bien estructurado)")
        elif 1 <= stop_in_atr <= 3:
            score += 2
            reasoning.append(f"~ Stop = {stop_in_atr:.1f}× ATR (aceptable)")
        else:
            if stop_in_atr < 1:
                reasoning.append(f"✗ Stop = {stop_in_atr:.1f}× ATR (muy ajustado — ruido puede sacarte)")
            else:
                reasoning.append(f"✗ Stop = {stop_in_atr:.1f}× ATR (muy amplio — riesgo excesivo)")
    else:
        # Sin ATR, dar puntos parciales si el stop es razonable (< 10%)
        stop_pct = risk / entry_price * 100
        if stop_pct <= 7:
            score += 2
            reasoning.append(f"~ Stop {stop_pct:.1f}% sin datos de ATR (asumiendo razonable)")
        else:
            reasoning.append(f"✗ Stop {stop_pct:.1f}% sin datos de ATR para validar")

    # 3. Validación de sizing (3 puntos)
    # Con 500€ y x5 leverage, exposición max = 2500€
    # Riesgo máximo 2% del capital = 10€ por trade
    max_risk_eur = capital * 0.02
    exposure_total = capital * leverage

    if risk > 0:
        # Cuántas shares podemos comprar para arriesgar max 10€
        shares_by_risk = max_risk_eur / risk
        position_value = shares_by_risk * entry_price

        # ¿Cabe en nuestra capacidad de apalancamiento?
        if position_value <= exposure_total:
            score += 3
            reasoning.append(f"✓ Sizing viable: €{position_value:.0f} exposición para €{max_risk_eur:.0f} riesgo")
        elif position_value <= exposure_total * 1.2:
            score += 1
            reasoning.append(f"~ Sizing ajustado: €{position_value:.0f} (límite €{exposure_total:.0f})")
        else:
            reasoning.append(f"✗ Sizing excede capacidad: necesitaría €{position_value:.0f} (límite €{exposure_total:.0f})")
    else:
        reasoning.append(f"✗ No se puede calcular sizing (riesgo inválido)")
        position_value = 0

    # Hard reject: R/R < 3 es condición eliminatoria
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
