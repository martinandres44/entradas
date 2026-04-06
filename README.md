# FIFA Ticket Monitor 🇦🇷

Monitor automático de entradas para los partidos de Argentina en el Mundial 2026.

## Partidos monitoreados
- 🇦🇷 Argentina vs. 🇩🇿 Argelia — 16 jun · Arrowhead Stadium, Kansas City
- 🇦🇷 Argentina vs. 🇦🇹 Austria — 22 jun · AT&T Stadium, Dallas

## Setup (5 minutos)

### 1. Crear el repositorio en GitHub
Creá un repo nuevo (puede ser privado) y subí estos archivos respetando la estructura:

```
tu-repo/
├── .github/
│   └── workflows/
│       └── monitor.yml
├── check_tickets.py
├── ticket_state.json    ← se crea solo en el primer run
└── README.md
```

### 2. Configurar los Secrets en GitHub
En tu repo: **Settings → Secrets and variables → Actions → New repository secret**

Agregá estos dos secrets:

| Nombre | Valor |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | El token de tu bot (ej: `123456:ABC-...`) |
| `TELEGRAM_CHAT_ID` | Tu chat ID de Telegram (ej: `-100123456789`) |

### 3. Habilitar permisos de escritura
En **Settings → Actions → General → Workflow permissions** → elegir **"Read and write permissions"**

Esto permite que el script guarde `ticket_state.json` entre runs.

### 4. Primer run manual
En **Actions → FIFA Ticket Monitor → Run workflow** para verificar que todo funciona.

## Frecuencia
El workflow corre cada **15 minutos** automáticamente.
Cada **6 horas** recibís un ping de "estoy vivo" aunque no haya cambios.

## Cómo obtener tu Chat ID de Telegram
1. Escribile a `@userinfobot` en Telegram
2. Te responde con tu ID

## Link directo a los tickets
- [FIFA.com/tickets (venta oficial)](https://www.fifa.com/en/tickets)
- [Mercado de Reventa FIFA](https://www.marketplace.fifa.com)
