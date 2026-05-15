# Investment Advisor — Learning Log

Este archivo es actualizado automáticamente cada viernes por la Routine 3 (Weekly Learning).
Los routines diarios lo leen antes de cada scan para aplicar ajustes basados en experiencia.

---

## Ajustes activos (aplicar en todos los scans)

- **Umbral BUY**: 75 — mantener (muestra insuficiente para ajustar; 1/1 con ≥77)
- **ATR estimado**: si no hay velas históricas reales, descontar 4 pts del componente R:R
- **Yahoo Finance**: frecuentemente devuelve 403 → usar Finnhub como fuente primaria
- **Mega-caps**: AMD ($500B), MU ($668) correctamente filtrados — mantener filtros actuales
- **REVISIÓN BINARY CATALYST RULE**: la regla "umbral 78 si earnings mañana + Turtles<18" habría bloqueado RKLB (score 77, Turtles 14/25) que ganó +56% en 2 días. Con muestra n=1 no ajustar la regla, pero anotar que earnings de alta calidad (beat history + backlog sólido) pueden justificar entrar a 77 aunque el breakout no esté confirmado. Revisar en semana 4 con más datos.

---

## Semana 06 mayo 2026 (primera semana operativa)

### Recomendaciones emitidas: 1

| Ticker | Score | Catalizador | Precio entrada | Stop | Target | R:R | Outcome | P&L est. |
|--------|-------|-------------|----------------|------|--------|-----|---------|----------|
| RKLB | 77/100 | Earnings Q1 pre-market 7-mayo + backlog $1.85B | $78.25 | $74.53 | $93.90 | 4.2:1 | ✅ ÉXITO | +€50 en target (+20%); si mantenido hasta 15-may: +€140.75 (+56.3%) |

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
**Plays binarios (earnings mañana)**: regla umbral >= 78 bajo revisión — RKLB (77pts) demostró que earnings de calidad excepcional (backlog sólido + analysts BUY consensus) pueden superar la restricción. No cambiar aún (n=1).
**Filtros de precio/market cap**: funcionan bien, no cambiar
**Catalizador tipo earnings pre-market**: el de mayor impacto confirmado (RKLB +56% en 2 días)
**Frecuencia de señales**: 1 señal en 2 semanas (7+ scans sin oportunidad). Sistema conservador. Aceptable si las señales que sí emite tienen alta convicción.

---

## Semana 11-15 mayo 2026

### Resumen semanal

| Métrica | Valor |
|---------|-------|
| Recomendaciones emitidas | 0 |
| Éxitos | — |
| Fallos | — |
| Pendientes | — |
| P&L estimado total semana | €0 (sin nuevas posiciones) |
| Scans realizados | 8 (lun-vie, 09:00 EU / 14:00 pre-US / 15:30 US open) |
| Régimen de mercado | NEUTRAL toda la semana (VIX 17.19–18.41) |

### Esta semana: sin nuevas señales

No se generó ninguna recomendación [COMPRA] durante la semana del 11 al 15 de mayo. Los 8 scans ejecutados detectaron régimen NEUTRAL consistente pero no encontraron setups con score ≥ 75.

**VIX por día:**
| Fecha | Hora | VIX | Régimen | Resultado |
|-------|------|-----|---------|-----------|
| 11-may | 15:30 | 17.19 | NEUTRAL | Sin oportunidades |
| 12-may | 14:00 | 18.41 | NEUTRAL | Sin oportunidades |
| 13-may | 14:00 | 18.11 | NEUTRAL | Sin oportunidades |
| 13-may | 15:30 | 18.11 | NEUTRAL | Sin oportunidades |
| 14-may | 14:00 | 18.01 | NEUTRAL | Sin oportunidades |
| 14-may | 15:30 | 17.92 | NEUTRAL | Sin oportunidades |
| 15-may | 14:00 | 17.90 | NEUTRAL | Sin oportunidades |
| 15-may | 15:30 | 17.90 | NEUTRAL | Sin oportunidades |

### Revisión de operación anterior: RKLB (abierta semana 06-may)

- **Entrada**: $78.25 (6 mayo 2026, VIX 16.73)
- **Catalizador**: Earnings Q1 pre-market 7 mayo — resultado: revenue $200.35M (record), beat sólido
- **Evolución**: +34% el día de earnings (8 mayo), máximo histórico alcanzado
- **Precio actual (15-may)**: $122.33 (+56.3% desde entrada)
- **Target ($93.90)**: superado el 8 de mayo (día 2 de holding)
- **Stop ($74.53)**: nunca amenazado
- **Outcome**: ✅ ÉXITO EXCEPCIONAL
- **P&L si salida en target (+20%)**: €250 exposición × 20% = **+€50** (10% sobre capital total)
- **P&L si mantenido 9 días hasta hoy (+56.3%)**: **+€140.75** (28.2% sobre capital total)
- **Holding óptimo**: 1-2 días (el grueso del movimiento fue el día de earnings)

### Patrones identificados (semana 2)

**1. Régimen NEUTRAL (VIX 17–18) no garantiza señales frecuentes**
VIX en rango óptimo histórico (15–20) toda la semana, pero 0 señales. Conclusión: el régimen es condición necesaria pero no suficiente. Sin catalizadores claros en el universo, no hay setup aunque el mercado sea favorable.

**2. RKLB confirmó: la calidad del catalizador importa más que el breakout técnico**
Turtles 14/25 (sin breakout confirmado) pero catalizador 19/25 (earnings + backlog + analysts). El sistema emitió señal correctamente con score 77. La acción respondió con +56%. Este dato pesa: **en plays de earnings, priorizar calidad del catalizador sobre setup técnico**.

**3. Frecuencia de señales consistente con swing trading profesional**
1 señal en ~2 semanas / 7+ scans = frecuencia baja pero aceptable. Un sistema profesional de swing trading no busca estar siempre en el mercado. La inactividad esta semana no es una señal de fallo del sistema.

**4. El sistema post-RKLB está correcto siendo conservador**
Después de un earnings play exitoso, el mercado entra en pausa de catalizadores hasta el próximo ciclo. No forzar señales.

### Sesgos detectados

- **Sesgo de confirmación temprana**: con sólo 1 operación (RKLB), cualquier patrón identificado es anecdótico. No cambiar parámetros del scoring hasta tener n≥5.
- **Earnings pre-market**: único tipo de catalizador probado hasta la fecha. Sesgo muestral — no generalizar.
- **Sin datos EU**: todos los scans de 09:00 (mercado EU) no aparecen en los issues — posible fallo del workflow para esa franja. Investigar.

### Ajustes recomendados para próxima semana

| Parámetro | Decisión | Razón |
|-----------|----------|-------|
| Umbral BUY | Mantener 75 | n=1, no ajustar |
| Binary catalyst rule (78) | Mantener con nota | RKLB habría sido bloqueado — vigilar |
| Sectores a sobreponderar | Space, Defense, AI infra | Tailwinds sectoriales confirmados (RKLB +sector) |
| Sectores a infraponderar | Biotech (sin beats recientes) | Sin datos propios — precaución |
| Tipo catalizador mejor hit rate | Earnings pre-market con backlog sólido | Confirmado RKLB |
| Tipo catalizador a evitar | Earnings sin historial de beats (< 30%) | RKLB tenía 27% beat history pero backlog compensó — no ignorar, pero penalizar |

### Métricas acumuladas del sistema (2 semanas)

| Métrica | Valor | Benchmark |
|---------|-------|-----------|
| Win rate | 1/1 = 100% | 38–52% profesional |
| Profit factor | ∞ (0 pérdidas) | ≥ 1.5 |
| P&L total estimado | +€50 a +€140.75 | — |
| Scans sin señal | 7+ | Normal en swing trading |
| Drawdown máximo | 0% | Max sostenible: 15% capital real |

> ⚠️ Muestra insuficiente (n=1). Los ratios de 100% win rate y ∞ profit factor son estadísticamente insignificantes. Revisar con n≥5 operaciones.

### Aprendizaje acumulado (actualizado 15-may-2026)
**Fiabilidad de fuentes**: Finnhub > WebSearch > Yahoo Finance (Yahoo bloquea con 403)
**ATR**: siempre calcular desde velas históricas reales; beta-implied subestima en 3-4x
**Plays binarios (earnings mañana)**: regla umbral >= 78 bajo revisión — RKLB (77) ganó +56%
**Filtros de precio/market cap**: funcionan bien, no cambiar
**Catalizador earnings pre-market + backlog sólido**: el de mayor potencial confirmado
**Breakout no confirmado + catalizador excepcional**: puede ser válido (RKLB: Turtles 14/25 pero +56%)
**Frecuencia de señales**: ~1 por semana o menos es normal y deseable (disciplina > cantidad)
**Régimen NEUTRAL (VIX 17-18)**: condición necesaria pero no suficiente sin catalizadores activos
**Salida óptima en earnings plays**: considerar salida parcial el día de earnings (+20-25%) para asegurar beneficio; dejar runner si momentum confirma
