# Investment Advisor — Learning Log

Este archivo es actualizado automáticamente cada viernes por la Routine 3 (Weekly Learning).
Los routines diarios lo leen antes de cada scan para aplicar ajustes basados en experiencia.

---

## Ajustes activos (aplicar en todos los scans)

- **Umbral BUY**: 75 (78 si el catalizador es earnings mañana y Turtles < 18 → BINARY CATALYST)
- **ATR estimado**: si no hay velas históricas reales, descontar 4 pts del componente R:R
- **Yahoo Finance**: frecuentemente devuelve 403 → usar Finnhub como fuente primaria
- **Mega-caps**: AMD ($500B), MU ($668) correctamente filtrados — mantener filtros actuales

---

## Semana 06 mayo 2026 (primera semana operativa)

### Recomendaciones emitidas: 1

| Ticker | Score | Catalizador | Precio entrada | Stop | Target | R:R | Outcome | P&L est. |
|--------|-------|-------------|----------------|------|--------|-----|---------|----------|
| RKLB | 77/100 | Earnings Q1 pre-market 7-mayo + backlog $1.85B | $78.25 | $74.53 | $93.90 | 4.2:1 | ⏳ Pendiente | — |

### Desglose RKLB
- Régimen: 12/15 (VIX 16.73 neutral, SPY +0.88% sobre EMA200)
- Turtles: 14/25 (sin breakout confirmado — play pre-earnings, no breakout)
- Seykota: 17/20 (buena alineación de EMAs)
- Catalizador: 19/25 (earnings mañana, backlog $1.85B, sector defensa)
- R:R: 15/15 (4.2:1 — ATR parcialmente estimado ⚠️)

### Incidencias técnicas detectadas
- **Yahoo Finance 403**: bloqueó en el run de las 14:00. El routine cayó correctamente a
  WebSearch para VIX/SPY y a Finnhub para earnings. Sin embargo, el ATR de RKLB fue
  beta-implied (2.38%) en vez del ATR real del día anterior (8.2%).
  → FIX aplicado: Finnhub `/stock/candle` ahora es la fuente primaria para datos históricos.
  → FIX aplicado: penalización de -4 pts en R:R cuando ATR es estimado.

### Candidatos watchlist correctamente identificados
- IONQ 74/100 — Earnings HOY after-close (binario puro, correcto no entrar)
- SMCI 73/100 — Beat confirmado pero death cross EMA (correcto no entrar)
- NVDA ~67/100 — Catalizador May 20 (demasiado lejos, correcto watchlist)

### Candidatos correctamente descartados
- AMD: mega-cap ~$500B (filtro correcto)
- MU: precio $668 > $500 (filtro correcto)
- COIN: score 59, trend bajista post-selloff -57% (correcto)

### Patrones identificados (semana 1)
- Pre-earnings plays con Turtles bajo (<18) son binarios puros: subir umbral a 78
- ATR beta-implied subestima volatilidad real (~3-4x en small caps como RKLB)
- WebSearch funciona bien para régimen de mercado (VIX, SPY) cuando APIs fallan
- Finnhub earnings calendar es fiable y suficiente para detectar catalizadores

### Aprendizaje acumulado (histórico)
**Fiabilidad de fuentes**: Finnhub > WebSearch > Yahoo Finance (Yahoo bloquea con 403)
**ATR**: siempre calcular desde velas históricas reales; beta-implied subestima en 3-4x
**Plays binarios (earnings mañana)**: requieren score >= 78, no 75; indicar ⚠️ BINARY
**Filtros de precio/market cap**: funcionan bien, no cambiar
