# Investment Advisor — Learning Log

Este archivo es actualizado automáticamente cada viernes por la Routine 3 (Weekly Learning).
Los routines diarios lo leen antes de cada scan para aplicar ajustes basados en experiencia.

---

## Ajustes activos (aplicar en todos los scans)

- **Umbral BUY**: 75 (78 si el catalizador es earnings mañana y Turtles < 18 → BINARY CATALYST)
- **ATR estimado**: si no hay velas históricas reales, descontar 4 pts del componente R:R
- **Yahoo Finance**: frecuentemente devuelve 403 → usar Finnhub como fuente primaria
- **Mega-caps**: AMD ($500B), MU ($668) correctamente filtrados — mantener filtros actuales
- **Pre-earnings plays**: entrar solo si Turtles >= 18 o exigir score >= 78 (BINARY CATALYST)
- **ATR real vs estimado**: el ATR beta-implied subestima en 3-4x para small caps volátiles — SIEMPRE calcular desde velas históricas reales antes de fijar stop

---

## Semana 04 mayo – 08 mayo 2026 (primera semana operativa)

### Resumen de la semana
- **Recomendaciones emitidas**: 1
- **Éxitos** (target alcanzado o +10% sin stop): 0 (0%) — trade pendiente
- **Fallos** (stop o -8%): 0 (0%)
- **Pendientes**: 1 (100%)
- **P&L estimado a cierre viernes 8 mayo**: +€20.5 no realizado (~+8.2% sobre exposición de €250)

### Trades de esta semana

| Ticker | Score | Catalizador | Precio entrada | Stop | Target | Precio actual (8-may) | Outcome | P&L est. |
|--------|-------|-------------|----------------|------|--------|-----------------------|---------|----------|
| RKLB | 77/100 | Earnings Q1 pre-market 7-may + backlog $1.85B | $78.25 | $74.53 | $93.90 | $84.65 | ⏳ Pendiente (+8.2%) | +€20.5 |

### Desglose RKLB — Post-mortem parcial (día 2)

**Datos del earnings (7 mayo, pre-market):**
- Revenue Q1 2026: $200.3M (+63.5% YoY) — **superó todas las métricas de guidance**
- EPS: -$0.07 vs -$0.08 esperado → **BEAT +12.5%**
- Backlog: $2.2B (+19% desde $1.85B en el momento de la recomendación)
- Q2 2026 guidance: $225M–$240M (nuevo récord proyectado)
- RKLB seleccionado para programa Golden Dome (Space Force interceptors) junto a Raytheon

**Evolución del precio:**
- Entry (6 mayo): $78.25
- Cierre 7 mayo (earnings day): $78.58 (+0.4% — reacción contenida inicial)
- Precio 8 mayo: $84.65 (+8.2% desde entry)
- Stop $74.53: **NO tocado** ✅
- Target $93.90 (+20%): en progreso — 41% del camino recorrido en 2 días

**Lo que funcionó:**
1. El catalizador (earnings beat) fue correctamente identificado y se materializó
2. La alineación de tendencia (EMAs alcistas, backlog record) dio contexto fundamental sólido
3. El score de 77/100 reflejó apropiadamente la oportunidad — el trade está en profit

**Lo que hay que mejorar:**
1. **ATR estimado vs real**: el rango del 7 mayo fue amplio (~$6-8), confirmando que el ATR beta-implied ($1.86) subestimó gravemente la volatilidad real. El stop en $74.53 (2×ATR estimado) quedó ajustado; con ATR real (~$4-5), el stop debería haber estado en ~$70-71, lo que habría mejorado el R:R a ~5:1+
2. **Turtles 14/25 en pre-earnings**: el play se abrió sin breakout técnico confirmado. El precio estaba 5.7% por debajo del high20. En retrospectiva, la entrada habría sido mejor esperando confirmación post-earnings (apertura sobre $83)
3. **Reacción inicial plana**: el cierre del 7 mayo fue prácticamente flat ($78.58) pese al beat fuerte. El gap alcista llegó al día siguiente (8 mayo → $84.65). Esto confirma que en plays de earnings, el movimiento real puede tomar 1-2 sesiones después del reporte

### Incidencias técnicas detectadas (semana 1)
- **Yahoo Finance 403**: bloqueó en el run de las 14:00. El routine cayó correctamente a WebSearch para VIX/SPY y a Finnhub para earnings. Sin embargo, el ATR de RKLB fue beta-implied (2.38%) en vez del ATR real del día anterior (8.2%).
  → FIX aplicado: Finnhub `/stock/candle` ahora es la fuente primaria para datos históricos.
  → FIX aplicado: penalización de -4 pts en R:R cuando ATR es estimado.

### Candidatos watchlist correctamente identificados (semana 1)
| Ticker | Score | Razón del no-BUY | Resultado posterior |
|--------|-------|-----------------|---------------------|
| IONQ | 74/100 | Earnings HOY (binario inmediato), R:R borderline | Pendiente verificación |
| SMCI | 73/100 | Beat confirmado pero death cross EMA | Correcto no entrar |
| NVDA | ~67/100 | Earnings May 20 (14d) — catalizador lejano | Watchlist activo |

### Candidatos correctamente descartados (semana 1)
- AMD: mega-cap ~$500B (filtro correcto)
- MU: precio $668 > $500 (filtro correcto)
- COIN: score 59, trend bajista post-selloff -57% (correcto)

---

## Patrones identificados

### Catalizador
- **Earnings con beat histórico mejorado + backlog record**: catalizador de alta calidad, funcionó
- **EPS beat modesto (+12.5%) con revenue beat masivo (+63.5% YoY)**: el mercado premia más el revenue beat y el guidance raise que el EPS beat solo
- **Reacción post-earnings puede tardar 1-2 sesiones**: no cerrar posición prematuramente el día del reporte si el beat es claro — el movimiento llega con follow-through en sesiones posteriores

### Técnico
- **Turtles bajo (<18) en pre-earnings = BINARY CATALYST**: confirmado que entrar sin breakout técnico reduce convicción; el trade funcionó pero por el catalizador, no por el setup técnico
- **ATR beta-implied es inútil para small caps volátiles**: siempre requiere velas históricas reales (Finnhub `/stock/candle`). La diferencia puede ser 3-4x

### Régimen de mercado
- **VIX 15-20 (NEUTRAL-BULLISH) + SPY sobre EMA200**: régimen correcto para catalyst-driven plays. Tono risk-on validado
- **Contexto geopolítico favorable** (end-of-war hopes en mayo 2026): amplificó el movimiento de small/mid-cap tech y espacio

---

## Sesgos detectados

1. **ATR subestimación sistemática**: el ATR beta-implied ($1.86) fue ~2-4x inferior al rango real del día del earnings. Para cualquier play pre-earnings, usar ATR real o asumir que la volatilidad implícita será 2-3x la volatilidad histórica reciente. Ajuste: si ATR no está calculado de velas reales, el stop debe ser al menos 5% del precio (no 2×ATR estimado)

2. **Sesgo de entrada prematura en pre-earnings**: entrar 1 día antes del catalizador es arriesgado (exposición a gap bajista si la acción cae antes del reporte). Considerar entrada en la apertura del día del earnings si el pre-market muestra movimiento positivo, o entrada post-earnings en la primera vela de confirmación

3. **No hay sesgo sectorial aún** (semana 1, solo 1 trade): insuficientes datos. A revisar en semanas posteriores

---

## Ajustes recomendados para próxima semana

- **Umbral BUY**: **mantener 75** — el score de 77 en RKLB fue apropiado; el trade está funcionando
- **ATR mínimo**: si ATR estimado, asumir stop mínimo de 5% del precio (no 2×ATR beta-implied)
- **Sectores a sobre-ponderar**: Espacio/Defensa (RKLB, sector en momentum), Semiconductores (AMD earnings beat esta semana, tailwind sectorial), AI infrastructure
- **Sectores a sub-ponderar**: ninguno identificado aún (datos insuficientes)
- **Tipo de catalizador con mejor hit rate**: Earnings beat con revenue record + guidance raise + backlog creciente
- **Tipo de catalizador a evitar**: Earnings con historial beat < 30% SIN acompañamiento de revenue beat masivo confirmado previamente

### Nota sobre RKLB pendiente
El trade sigue abierto (día 2). Si el precio alcanza $93.90 (target +20%), se convierte en ✅ ÉXITO pleno. Si retrocede al stop $74.53, revisar si el ATR real habría sugerido un stop más amplio. **Actualizar este log el lunes 11 de mayo o cuando se cierre el trade.**

---

## Aprendizaje acumulado (histórico — actualizar cada semana)

**Fiabilidad de fuentes de datos**:
- Finnhub > WebSearch > Yahoo Finance (Yahoo bloquea con 403 frecuentemente)
- Finnhub `/stock/candle` es imprescindible para ATR real; sin él, el scoring de R:R es impreciso

**ATR y stops**:
- Beta-implied ATR subestima la volatilidad real en 3-4x para small caps (<$10B)
- En plays de earnings, la volatilidad implícita del día del reporte es 2-3x la volatilidad histórica reciente
- Stop mínimo recomendado en ausencia de ATR real: 5% del precio de entrada

**Catalizadores**:
- Earnings con revenue beat masivo + guidance raise + backlog creciente = catalizador de máxima calidad
- Pre-earnings plays sin breakout técnico (Turtles < 18) requieren score >= 78 y exigen el mismo calidad de catalizador
- La reacción post-earnings puede tardar 1-2 sesiones: mantener posición si el beat es claro y no hay deterioro técnico

**Filtros de exclusión**:
- Precio > $500 y market cap > $100B: correctos, filtran correctamente mega-caps
- Beta < 1.5: correcto — las acciones filtradas no moverían lo suficiente para justificar el riesgo con x5

**Régimen de mercado**:
- VIX 15-20 + SPY sobre EMA200 = régimen óptimo para catalyst-driven swing trading
- En este régimen, los plays de earnings con catalizadores sólidos tienden a funcionar bien

**Benchmarks del sistema** (a comparar con datos acumulados):
- Win rate objetivo: 38-52% (con R:R 3:1, rentable con solo 35% de éxito)
- Profit factor objetivo: >= 1.5
- Max drawdown tolerable: 15% del capital real (€75 de €500)
- Semana 1: 0 trades cerrados, 1 pendiente con +8.2% no realizado — datos insuficientes para métricas

---

*Última actualización: 2026-05-08 | Routine 3 — Weekly Post-mortem*
