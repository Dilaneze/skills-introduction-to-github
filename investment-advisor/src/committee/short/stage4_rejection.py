"""
Stage 4 Rejection — Stan Weinstein Methodology

"Secrets for Profiting in Bull and Bear Markets" (Weinstein, 1988)
Stage 4: precio bajo la SMA 150 (30-week) declinante.
El rebote fallido hacia la SMA 150 es el entry ideal para corto.

Referencia: github.com/bharatsharma1769/StanWeinstein
            github.com/ksanjay/stage-analysis-stocks

Puntuación: 0-30 puntos
- Stage 4 confirmado (precio < SMA150 declinante, EMA50 < SMA150): 15 pts
- Rebote rechazado (precio subió a SMA150 y está cayendo de nuevo): 10 pts
- Volume decreciente en el rebote (sin convicción alcista): 5 pts
"""

from typing import Dict


def evaluate_stage4_rejection(ticker_data: Dict) -> Dict:
    """
    Evalúa setup de Stage 4 con rebote rechazado.

    Stop sugerido: 3% sobre SMA 150 (stop claro basado en estructura).
    Target: 20% bajo entry (Stage 4 puede durar semanas/meses).
    """
    price = ticker_data.get("price", 0)
    sma_150 = ticker_data.get("sma_150", 0)
    sma_150_20d_ago = ticker_data.get("sma_150_20d_ago", sma_150)
    price_5d_ago = ticker_data.get("price_5d_ago", price)
    price_10d_ago = ticker_data.get("price_10d_ago", price)
    ema_50 = ticker_data.get("ema_50", 0)
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)

    score = 0
    reasoning = []

    if price <= 0 or sma_150 <= 0:
        return _empty_result("Sin datos de precio o SMA150 (requiere 150 días de historia)")

    price_below_sma150 = price < sma_150
    sma_declining = (sma_150 < sma_150_20d_ago * 0.999) if sma_150_20d_ago > 0 else False
    ema50_below_sma150 = (ema_50 < sma_150) if ema_50 > 0 else False

    # 1. Stage 4 confirmado (15 puntos — gate principal)
    if price_below_sma150 and sma_declining and ema50_below_sma150:
        score += 15
        decline_pct = (sma_150_20d_ago - sma_150) / sma_150_20d_ago * 100 if sma_150_20d_ago > 0 else 0
        reasoning.append(f"✓✓ Stage 4 pleno: precio<SMA150 declinante ({decline_pct:.1f}%/20d), EMA50<SMA150")
    elif price_below_sma150 and sma_declining:
        score += 10
        reasoning.append(f"✓ Stage 4 parcial: precio<SMA150 declinante (EMA50 aún sobre SMA150)")
    elif price_below_sma150:
        score += 5
        reasoning.append(f"~ Precio bajo SMA150 pero sin confirmar declive — posible Stage 1/4 transición")
    else:
        pct_above = (price - sma_150) / sma_150 * 100
        reasoning.append(f"✗ Precio {pct_above:.1f}% SOBRE SMA150 — no es Stage 4, no aplica short Weinstein")
        return {
            "style": "stage4_rejection",
            "score": 0,
            "max_score": 30,
            "reasoning": reasoning,
            "signals": {
                "stage": 2,
                "price_vs_sma150_pct": round(pct_above, 1),
                "sma150_declining": False,
                "bounce_detected": False,
                "stop_suggested": 0,
                "target_suggested": 0
            }
        }

    # 2. Patrón de rebote rechazado (10 puntos)
    # El precio subió hacia la SMA150 recientemente y está volviendo a bajar
    bounce_high = max(price_5d_ago, price_10d_ago)
    distance_at_closest_pct = abs(bounce_high - sma_150) / sma_150 * 100
    currently_declining = price < price_5d_ago

    if distance_at_closest_pct <= 3 and currently_declining:
        score += 10
        reasoning.append(f"✓✓ Rebote rechazado perfecto: tocó SMA150 ({distance_at_closest_pct:.1f}%) y está cayendo")
    elif distance_at_closest_pct <= 7 and currently_declining:
        score += 7
        reasoning.append(f"✓ Rebote próximo a SMA150 ({distance_at_closest_pct:.1f}%) con precio bajando")
    elif distance_at_closest_pct <= 12:
        score += 3
        reasoning.append(f"~ Rebote parcial a {distance_at_closest_pct:.1f}% de SMA150 — monitorear")
    else:
        reasoning.append(f"✗ Sin rebote hacia SMA150 ({distance_at_closest_pct:.1f}% lejos) — setup no maduro")

    # 3. Volume decreciente en rebote (5 puntos)
    # Volume bajo durante el rebote = alcistas sin convicción
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    if vol_ratio < 0.7:
        score += 5
        reasoning.append(f"✓✓ Volume muy bajo en rebote ({vol_ratio:.1f}x) — alcistas sin convicción")
    elif vol_ratio < 0.9:
        score += 3
        reasoning.append(f"✓ Volume bajo ({vol_ratio:.1f}x) — rebote débil")
    elif vol_ratio <= 1.1:
        score += 1
        reasoning.append(f"~ Volume normal ({vol_ratio:.1f}x)")
    else:
        reasoning.append(f"✗ Volume elevado ({vol_ratio:.1f}x) en rebote — señal mixta")

    stop_suggested = round(sma_150 * 1.03, 2)
    target_suggested = round(price * 0.80, 2)

    return {
        "style": "stage4_rejection",
        "score": min(score, 30),
        "max_score": 30,
        "reasoning": reasoning,
        "signals": {
            "stage": 4 if price_below_sma150 else 2,
            "price_vs_sma150_pct": round((price - sma_150) / sma_150 * 100, 1),
            "sma150_declining": sma_declining,
            "bounce_detected": distance_at_closest_pct <= 12,
            "stop_suggested": stop_suggested,
            "target_suggested": target_suggested
        }
    }


def _empty_result(reason: str) -> Dict:
    return {
        "style": "stage4_rejection",
        "score": 0,
        "max_score": 30,
        "reasoning": [f"✗ {reason}"],
        "signals": {
            "stage": 0, "price_vs_sma150_pct": 0,
            "sma150_declining": False, "bounce_detected": False,
            "stop_suggested": 0, "target_suggested": 0
        }
    }
