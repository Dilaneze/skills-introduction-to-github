"""
Aggregator - Orquestador del Comité Virtual

Ejecuta todos los evaluadores y genera score final con reasoning completo.
"""

from typing import Dict, Optional
from .regime_detector import detect_regime, apply_sector_adjustment
from .turtles import evaluate_turtles
from .seykota import evaluate_seykota
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
    Ejecuta todos los evaluadores y genera score final con reasoning completo.

    Args:
        ticker: Symbol del ticker
        ticker_data: Datos del ticker (precios, indicadores técnicos, etc.)
        market_data: Datos del mercado general (VIX, S&P 500, etc.)
        catalyst_info: Info del catalizador (opcional)
        entry: Precio de entrada propuesto (si None, usa precio actual)
        stop: Stop loss propuesto (si None, lo calcula automáticamente)
        target: Take profit propuesto (si None, lo calcula automáticamente)
        capital: Capital disponible
        leverage: Apalancamiento

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

    # Si no hay precio, no se puede evaluar
    if price <= 0:
        return _error_result(ticker, "No hay datos de precio")

    # Calcular entry, stop y target si no se proporcionan
    if entry is None:
        entry = price * 0.995  # Pequeño descuento para limit order

    if stop is None:
        # Stop loss adaptativo basado en ATR y beta
        atr = ticker_data.get("atr_14", 0)
        beta = ticker_data.get("beta", 1.5)

        if atr > 0:
            # Stop = 2× ATR (típico para Turtles)
            stop = price - (atr * 2)
        else:
            # Sin ATR, usar % fijo basado en beta
            if beta >= 2.0:
                stop_pct = 10.0
            elif beta >= 1.5:
                stop_pct = 8.0
            else:
                stop_pct = 6.0
            stop = price * (1 - stop_pct / 100)

    if target is None:
        # Target conservador: 15% o agresivo: 20%
        change_pct = ticker_data.get("change_pct", 0)
        if change_pct and change_pct > 2:
            target_pct = 20.0  # Momentum fuerte
        else:
            target_pct = 15.0  # Conservador
        target = price * (1 + target_pct / 100)

    # 1. Detectar régimen
    regime = detect_regime(market_data)

    # 2. Evaluar cada componente
    turtles = evaluate_turtles(ticker_data)
    seykota = evaluate_seykota(ticker_data)
    catalyst = evaluate_catalyst(ticker_data, catalyst_info)
    risk_reward = evaluate_risk_reward(ticker_data, entry, stop, target, capital, leverage)

    # 3. Sumar scores
    raw_score = (
        regime["score"] +
        turtles["score"] +
        seykota["score"] +
        catalyst["score"] +
        risk_reward["score"]
    )

    # 4. Ajuste por sector/régimen
    sector = ticker_data.get("sector")
    final_score = apply_sector_adjustment(raw_score, sector, regime)
    sector_adjustment = final_score - raw_score

    # 5. Check hard rejects
    hard_reject = risk_reward.get("hard_reject", False)

    if hard_reject:
        decision = "REJECT"
        decision_reason = "R/R < 3:1 — no cumple mínimo obligatorio"
    elif final_score >= 75:
        decision = "BUY"
        decision_reason = f"Score {final_score}/100 — oportunidad de alta convicción"
    elif final_score >= 60:
        decision = "WATCHLIST"
        decision_reason = f"Score {final_score}/100 — monitorear para mejor entrada"
    else:
        decision = "SKIP"
        decision_reason = f"Score {final_score}/100 — insuficiente convicción"

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
            "raw_score": raw_score
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


def _error_result(ticker: str, error_msg: str) -> Dict:
    """Retorna resultado de error cuando no se puede evaluar."""
    return {
        "ticker": ticker,
        "decision": "SKIP",
        "decision_reason": error_msg,
        "final_score": 0,
        "regime": {"regime": "unknown", "score": 0, "reasoning": error_msg},
        "breakdown": {
            "regime": 0,
            "turtles": 0,
            "seykota": 0,
            "catalyst": 0,
            "risk_reward": 0,
            "sector_adjustment": 0,
            "raw_score": 0
        },
        "reasoning": {
            "regime": [error_msg],
            "turtles": [],
            "seykota": [],
            "catalyst": [],
            "risk_reward": []
        },
        "trade_params": {
            "entry": 0,
            "stop": 0,
            "target": 0,
            "rr_ratio": 0,
            "position_eur": 0,
            "stop_pct": 0,
            "target_pct": 0
        },
        "signals": {}
    }
