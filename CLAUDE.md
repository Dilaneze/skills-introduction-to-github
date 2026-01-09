# Investment Advisor - Context for Claude

## Project Overview

Automated investment advisor que escanea mercados US/EU usando **Catalyst-Driven Swing Trading** strategy. Detecta oportunidades de inversión y envía notificaciones móviles vía GitHub Issues.

**Capital**: 500€ | **Leverage**: x5 | **Platform**: eToro | **Holding**: 1-14 días

## Architecture

### Workflow Automation
- **File**: `.github/workflows/investment-advisor.yml`
- **Schedule** (hora España):
  - 09:00 - Apertura mercado EU
  - 14:00 - Pre-market US
  - 15:30 - Apertura mercado US
- **Trigger**: Cron automático (lunes-viernes) + manual via `workflow_dispatch`

### Core Components
```
investment-advisor/
├── src/market_analyzer.py    # Motor de análisis (Python 3.11)
├── config/trading_config.json # Parámetros de trading
├── SETUP.md                   # Documentación de configuración
└── requirements.txt           # Dependencies: requests
```

### Data Sources (with fallback chain)
1. **Yahoo Finance** (primary, no API key)
2. **Finnhub** (fallback, API key required)
3. **Alpha Vantage** (optional)
4. **FMP** (optional)

**Decisión clave**: Yahoo Finance primero por no requerir API key, Finnhub como fallback robusto.

## Trading Parameters (Professional Swing Trading)

```python
Capital: 500 EUR
Leverage: x5 (2,500 EUR exposición)
Stop Loss máximo: 10% (50% real con leverage)
Risk/Reward mínimo: 3:1 obligatorio
Posiciones concurrentes: Max 2
Position size: 10% normal, 15% high-conviction
```

### Filtros de Selección
- **Market cap**: $100M - $100B
- **Beta**: >= 1.5 (preferido >= 2.0 para volatilidad)
- **Precio**: $2 - $500
- **Volumen mínimo**: 1M shares (small caps), 750K (mid), 500K (large)
- **Target**: 15-20% ganancia mínima

### Sistema de Scoring (5 dimensiones, 1-5 pts cada una)
1. **Timing del catalizador** - Proximidad del evento
2. **Setup técnico** - Rango, volumen, momentum
3. **Risk/Reward** - Ratio potencial
4. **Calidad fundamental** - Crecimiento, márgenes
5. **Convicción del catalizador** - Probabilidad

**Score >= 75**: COMPRA | **60-74**: WATCHLIST | **< 60**: SKIP

## Notification System

**Primary**: GitHub Issues (notificaciones push móviles vía GitHub Mobile app)
**Optional**: Telegram bot, Email (via secrets)

### Issue Creation Logic
```yaml
if has_opportunities == true || force_notification == true:
  gh issue create --title "$TITLE" --body "$BODY"
```

**No labels required** (decisión: los labels no existen en el repo, removed en commit 577ba89)

## Key Implementation Decisions

1. **Professional parameters** (commit 5744fbe): Implementados parámetros equilibrados para swing trading real (no aggressive filters anteriores)

2. **Finnhub fallback** (commit 569f0b7): Cuando Yahoo Finance falla, usar Finnhub para robustez

3. **No label requirement** (commit 577ba89): Issues sin labels para evitar errores

4. **Watchlist expansion**: 100+ acciones de alto crecimiento (tech, biotech, EV, semiconductors)

5. **eToro costs awareness**: Fee overnight ~9% anual, movimiento mínimo rentable 1.5-2%

## Git Workflow

- **Main branch**: Default (no especificado en gitStatus)
- **Feature branches**: Pattern `claude/investment-advisor-notifications-{sessionId}`
- **Current branch**: `claude/investment-advisor-notifications-VUcNj`

## Common Commands

### Manual execution
```bash
# Via GitHub UI
Actions > "Investment Advisor - Market Scanner" > Run workflow

# Con watchlist personalizada
Custom watchlist: NVDA,AMD,TSLA,PLTR
Force notification: true
```

### Local testing
```bash
cd investment-advisor/src
export FINNHUB_API_KEY="your_key"
python market_analyzer.py
```

### Debugging
```bash
# Ver artifacts de scans anteriores
Actions > Workflow run > Artifacts > market-scan-{run_number}

# Revisar scan output
cat investment-advisor/src/scan_output.json
```

## Secrets Configuration (GitHub Secrets)

**Required**:
- `FINNHUB_API_KEY` (Recomendado)

**Optional**:
- `ALPHA_VANTAGE_KEY`
- `FMP_API_KEY`
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- SMTP secrets (para email notifications)

**Variables**:
- `TELEGRAM_ENABLED=true/false`
- `EMAIL_ENABLED=true/false`

## Important Notes

- **No crear documentación adicional** sin solicitud explícita
- **Commits descriptivos**: Seguir patrón "feat:", "fix:", "Merge pull request"
- **Push branch pattern**: Debe empezar con `claude/` y terminar con session ID
- **Retry logic**: Network failures en git operations: 4 retries con exponential backoff
- **Disclaimer**: Esto NO es consejo financiero. Trading con apalancamiento conlleva riesgos significativos.

## Recent Development History

```
5ecf619 - Merge PR #7 (swing trading parameters)
5744fbe - feat: Implement professional swing trading parameters
577ba89 - fix: Remove label requirement from issue creation
569f0b7 - feat: Add Finnhub as fallback data source
```

## Reference Files

- Trading strategy details: `investment-advisor/SETUP.md`
- Workflow config: `.github/workflows/investment-advisor.yml`
- Core logic: `investment-advisor/src/market_analyzer.py`
