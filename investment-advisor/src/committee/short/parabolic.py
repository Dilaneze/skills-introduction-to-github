"""
Parabolic Short — Qullamaggie Methodology

"My 3 Timeless Setups" — qullamaggie.com
Stocks que suben 100-500% en meses y luego se aceleran siempre revierten.
El edge: identificar el agotamiento ANTES de que el mercado lo descuente.

Referencia repo: github.com/tradermonty/claude-trading-skills

Puntuación: 0-30 puntos
- Extensión sobre SMA 50 (cuán lejos está del equilibrio): 10 pts
- Run previo 60 días (la carrera que precede el parabólico): 8 pts
- RSI extremo overbought (agotamiento de compradores): 7 pts
- Volume climax reciente (distribución disfrazada de euforia): 5 pts
"""

from typing import Dict


def evaluate_parabolic(ticker_data: Dict) -> Dict:
    """
    Evalúa setup de parabolic short. Mayor score = más sobreextendido
    y más probable la reversión hacia la media.

    Entry ideal: primera crack (cierre bajo EMA 20 tras run parabólico).
    Stop: 5-8% arriba del entry.
    Target: regreso a SMA 50 (20-40% abajo).
    """
    price = ticker_data.get("price", 0)
    ema_50 = ticker_data.get("ema_50", 0)
    price_60d_ago = ticker_data.get("price_60d_ago", price)
    rsi_14 = ticker_data.get("rsi_14", 50)
    volume = ticker_data.get("volume", 0)
    avg_volume = ticker_data.get("avg_volume_20d", 1)
    ema_20 = ticker_data.get("ema_20", 0)
    price_5d_ago = ticker_data.get("price_5d_ago", price)

    score = 0
    reasoning = []

    if price <= 0:
        return _empty_result("Sin datos de precio")

    # 1. Extensión sobre SMA 50 (10 puntos)
    if ema_50 > 0:
        extension_pct = (price - ema_50) / ema_50 * 100
        if extension_pct >= 50:
            score += 10
            reasoning.append(f"✓✓ {extension_pct:.0f}% sobre SMA50 — extremo parabólico, reversión casi segura")
        elif extension_pct >= 30:
            score += 7
            reasoning.append(f"✓ {extension_pct:.0f}% sobre SMA50 — muy extendido, setup madurando")
        elif extension_pct >= 15:
            score += 4
            reasoning.append(f"~ {extension_pct:.0f}% sobre SMA50 — extendido pero no extremo")
        elif extension_pct >= 5:
            score += 1
            reasoning.append(f"✗ Solo {extension_pct:.0f}% sobre SMA50 — extensión insuficiente para parabólico")
        else:
            reasoning.append(f"✗ Precio cercano o bajo SMA50 — no hay setup parabólico")
    else:
        reasoning.append("✗ Sin datos de SMA50")

    # 2. Run previo 60 días (8 puntos) — la carrera que crea el parabólico
    if price_60d_ago > 0 and price_60d_ago != price:
        run_60d = (price - price_60d_ago) / price_60d_ago * 100
        if run_60d >= 100:
            score += 8
            reasoning.append(f"✓✓ +{run_60d:.0f}% en 60 días — carrera parabólica confirmada (>100%)")
        elif run_60d >= 50:
            score += 6
            reasoning.append(f"✓ +{run_60d:.0f}% en 60 días — run fuerte")
        elif run_60d >= 30:
            score += 4
            reasoning.append(f"~ +{run_60d:.0f}% en 60 días — momentum moderado")
        elif run_60d >= 15:
            score += 1
            reasoning.append(f"✗ Solo +{run_60d:.0f}% en 60d — insuficiente para short parabólico")
        else:
            reasoning.append(f"✗ Sin run previo significativo ({run_60d:.0f}% en 60d)")
    else:
        reasoning.append("✗ Sin datos históricos de 60 días")

    # 3. RSI extremo (7 puntos) — agotamiento de compradores
    if rsi_14 >= 85:
        score += 7
        reasoning.append(f"✓✓ RSI {rsi_14:.0f} — agotamiento extremo (bears preparándose)")
    elif rsi_14 >= 80:
        score += 5
        reasoning.append(f"✓ RSI {rsi_14:.0f} — overbought")
    elif rsi_14 >= 75:
        score += 2
        reasoning.append(f"~ RSI {rsi_14:.0f} — elevado, no extremo")
    else:
        reasoning.append(f"✗ RSI {rsi_14:.0f} — sin señal de agotamiento")

    # 4. Volume climax (5 puntos) — distribución institucional disfrazada
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    if vol_ratio >= 2.5:
        score += 5
        reasoning.append(f"✓✓ Volume climax {vol_ratio:.1f}x — probable distribución institucional")
    elif vol_ratio >= 1.5:
        score += 3
        reasoning.append(f"✓ Volume elevado {vol_ratio:.1f}x")
    elif vol_ratio >= 1.1:
        score += 1
        reasoning.append(f"~ Volume ligeramente elevado {vol_ratio:.1f}x")
    else:
        reasoning.append(f"✗ Volume normal {vol_ratio:.1f}x — sin climax")

    # Entry trigger: ¿ya comenzó la primera crack?
    entry_trigger = "PENDING"
    if ema_20 > 0:
        if price < ema_20 and price_5d_ago > ema_20:
            entry_trigger = "ACTIVE"
            reasoning.append("🎯 ENTRADA ACTIVA: primera crack bajo EMA20 confirmada")
        elif price < ema_20:
            entry_trigger = "PAST_ENTRY"
            reasoning.append("~ Ya bajo EMA20 (entrada óptima fue hace unos días)")
        else:
            reasoning.append("⏳ Aún sobre EMA20 — esperar primera crack para entrada en corto")

    return {
        "style": "parabolic",
        "score": min(score, 30),
        "max_score": 30,
        "reasoning": reasoning,
        "signals": {
            "extension_vs_sma50_pct": round((price - ema_50) / ema_50 * 100, 1) if ema_50 > 0 else 0,
            "run_60d_pct": round((price - price_60d_ago) / price_60d_ago * 100, 1) if price_60d_ago > 0 else 0,
            "rsi_14": rsi_14,
            "volume_ratio": round(vol_ratio, 2),
            "entry_trigger": entry_trigger
        }
    }


def _empty_result(reason: str) -> Dict:
    return {
        "style": "parabolic",
        "score": 0,
        "max_score": 30,
        "reasoning": [f"✗ {reason}"],
        "signals": {
            "extension_vs_sma50_pct": 0, "run_60d_pct": 0,
            "rsi_14": 0, "volume_ratio": 0, "entry_trigger": "NONE"
        }
    }
