# Investment Advisor - Guia de Configuracion

## Como Funciona

Este sistema escanea automaticamente los mercados US y EU en busca de oportunidades de inversion basadas en la estrategia **Catalyst-Driven Swing Trading**.

### Ejecucion Automatica

El sistema se ejecuta automaticamente en los siguientes horarios (hora Espana):

| Hora | Mercado | Descripcion |
|------|---------|-------------|
| 09:00 | EU | Apertura mercado europeo |
| 14:00 | US | Pre-market US |
| 15:30 | US | Apertura mercado US |

Solo se ejecuta de **lunes a viernes** (dias de mercado).

---

## Configurar Notificaciones Push en Movil

### Opcion 1: GitHub Mobile (Recomendado)

1. **Instala GitHub Mobile** en tu telefono:
   - [iOS App Store](https://apps.apple.com/app/github/id1477376905)
   - [Google Play Store](https://play.google.com/store/apps/details?id=com.github.android)

2. **Inicia sesion** con tu cuenta de GitHub

3. **Habilita notificaciones**:
   - Ve a Settings > Notifications
   - Activa "Push Notifications"
   - Activa "Issues" y "Workflows"

4. **Suscribete a este repositorio**:
   - Ve al repositorio en GitHub
   - Click en "Watch" > "All Activity" o "Custom" > selecciona "Issues"

Ahora recibiras **notificaciones push instantaneas** cuando el sistema detecte una oportunidad de inversion.

### Opcion 2: Telegram Bot

Para notificaciones via Telegram:

1. Crea un bot en Telegram hablando con [@BotFather](https://t.me/botfather)
2. Obtiene el `TELEGRAM_BOT_TOKEN`
3. Obtiene tu `TELEGRAM_CHAT_ID`
4. Configura los secrets en GitHub (ver seccion Secrets)
5. Activa la variable `TELEGRAM_ENABLED=true`

### Opcion 3: Email

Para notificaciones por email, configura los secrets SMTP (ver seccion Secrets).

---

## Configurar Secrets de GitHub

Ve a tu repositorio > Settings > Secrets and variables > Actions

### Secrets Requeridos

| Secret | Descripcion | Obligatorio |
|--------|-------------|-------------|
| `FINNHUB_API_KEY` | API key de [Finnhub](https://finnhub.io/) para datos de mercado | Recomendado |
| `ALPHA_VANTAGE_KEY` | API key de [Alpha Vantage](https://www.alphavantage.co/) | Opcional |

### Secrets para Telegram (Opcional)

| Secret | Descripcion |
|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_CHAT_ID` | ID del chat donde enviar mensajes |

### Secrets para Email (Opcional)

| Secret | Descripcion |
|--------|-------------|
| `SMTP_SERVER` | Servidor SMTP (ej: smtp.gmail.com) |
| `SMTP_PORT` | Puerto SMTP (ej: 587) |
| `SMTP_USERNAME` | Usuario SMTP |
| `SMTP_PASSWORD` | Password SMTP |
| `NOTIFICATION_EMAIL` | Email destino |

### Variables de Configuracion

Ve a Settings > Secrets and variables > Actions > Variables

| Variable | Valor | Descripcion |
|----------|-------|-------------|
| `TELEGRAM_ENABLED` | `true` / `false` | Activar notificaciones Telegram |
| `EMAIL_ENABLED` | `true` / `false` | Activar notificaciones Email |

---

## Obtener API Keys Gratuitas

### Finnhub (Recomendado)

1. Ve a [finnhub.io](https://finnhub.io/)
2. Registrate gratis
3. Copia tu API key desde el dashboard
4. El plan gratuito permite 60 llamadas/minuto

### Alpha Vantage

1. Ve a [alphavantage.co](https://www.alphavantage.co/)
2. Click en "Get Free API Key"
3. El plan gratuito permite 5 llamadas/minuto, 500/dia

---

## Ejecucion Manual

Puedes ejecutar el scan manualmente en cualquier momento:

1. Ve a Actions > "Investment Advisor - Market Scanner"
2. Click en "Run workflow"
3. Opcionalmente, introduce una watchlist personalizada
4. Click en "Run workflow"

### Watchlist Personalizada

Puedes especificar acciones especificas separadas por comas:

```
NVDA,AMD,TSLA,PLTR
```

---

## Estructura del Proyecto

```
investment-advisor/
├── src/
│   └── market_analyzer.py    # Script principal de analisis
├── config/
│   └── trading_config.json   # Parametros de trading
├── requirements.txt          # Dependencias Python
└── SETUP.md                  # Esta guia
```

---

## Parametros de Trading

Los parametros estan configurados para tu perfil:

| Parametro | Valor |
|-----------|-------|
| Capital | 500 EUR |
| Apalancamiento | x5 (exposicion 2,500 EUR) |
| Stop Loss maximo | 5% (25% real con apalancamiento) |
| Risk/Reward minimo | 1:3 |
| Posiciones concurrentes | Max 2 |
| Holding period | 3-10 dias |

### Filtros de Seleccion

- Market cap: $300M - $50B
- Beta: >= 1.5 (preferido >= 1.8)
- Precio: $5 - $200
- Volumen minimo segun market cap

### Sistema de Scoring

Cada oportunidad se puntua en 5 dimensiones (1-5 puntos cada una):

1. **Timing del catalizador** - Proximidad del evento
2. **Setup tecnico** - Posicion en rango, volumen, momentum
3. **Risk/Reward** - Ratio potencial ganancia/perdida
4. **Calidad fundamental** - Crecimiento, margenes
5. **Conviccion del catalizador** - Probabilidad del evento

**Score >= 75**: Senal de COMPRA
**Score 60-74**: WATCHLIST
**Score < 60**: SKIP

---

## Costes eToro

Ten en cuenta estos costes al operar:

| Concepto | Coste |
|----------|-------|
| Fee overnight | ~9% anual sobre exposicion |
| Hold 7 dias (x5) | ~0.5% |
| Hold 14 dias (x5) | ~1% |
| Fines de semana | 3x fee normal |
| Spread por lado | ~0.15% |

**Movimiento minimo rentable**: 1.5-2% despues de costes

---

## Disclaimer

**ESTO NO ES CONSEJO FINANCIERO**

- El trading con apalancamiento conlleva riesgos significativos
- Puedes perder todo tu capital
- Los rendimientos pasados no garantizan rendimientos futuros
- Opera solo con dinero que puedas permitirte perder
- Este sistema es una herramienta de analisis, no un consejo de inversion

---

## Soporte

Si tienes problemas:

1. Revisa los logs en Actions > Workflow runs
2. Verifica que los secrets estan configurados correctamente
3. Comprueba que las API keys son validas
