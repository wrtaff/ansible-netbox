# Pops KMS Telegram bot (pops-bot)

A Telegram bot that is a pure client of the [Pops KMS REST API](../pops-api)
(parent ticket [#3577](http://trac.home.arpa/ticket/3577)). It owns no
knowledge-base logic of its own: every command maps to an API call. Bot
ticket: [#3576](http://trac.home.arpa/ticket/3576).

Built on `python-telegram-bot` 22.x (async) and `httpx`, installed in the
shared project venv `/opt/venvs/gemini_projects`.

## Commands

| Input | Action |
|---|---|
| plain text | `POST /api/inbox` (source `telegram`); replies `Captured -> <journal file>` |
| `/rfi <question>` | `POST /api/inbox` (source `rfi`) |
| `/todo <text> [*label ...]` | `POST /api/tasks`; `*label` tokens become labels, the rest is the title; replies with the task URL |
| `/trac <summary> \| <description>` | `POST /api/tickets`; description optional (default note referencing #3576); replies with the ticket URL |
| `/search <query>` | `GET /api/search` (max 5); replies `file:line - text` lines (each truncated to 120 chars) or `No matches.` |
| `/status` | `GET /api/health`; replies status / version / uptime |
| `/start`, `/help` | command summary |
| voice / audio / video note | `POST /api/transcribe`, then polls status and replies with the transcript (caption becomes transcription context) |

Only Telegram user IDs in the allow-list may use the bot; all other updates are
logged (user id only) and silently ignored.

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | (empty) | BotFather token. Required at runtime. Secret. |
| `POPS_API_URL` | `http://127.0.0.1:8765` | Base URL of the Pops API. |
| `POPS_API_KEY` | (empty) | Shared `X-API-Key`. Required. Secret. |
| `TELEGRAM_ALLOWED_USER_IDS` | (empty) | Comma-separated user IDs. Empty = nobody allowed. |
| `POPS_BOT_TRANSCRIBE_POLL_SECONDS` | `5` | Seconds between transcription status polls. |
| `POPS_BOT_TRANSCRIBE_TIMEOUT` | `1800` | Max seconds to poll a transcription job. |

In production the two secrets live in `/etc/pops-bot/env` (mode 0640,
root:will), injected by systemd via `EnvironmentFile`.

## Run

Development (from this directory):

```bash
TELEGRAM_BOT_TOKEN=... POPS_API_KEY=... TELEGRAM_ALLOWED_USER_IDS=123456789 \
    /opt/venvs/gemini_projects/bin/python3 -m bot.main
```

Production: systemd unit `pops-bot.service`, deployed by
`playbooks/deploy_pops_bot.yml`.

## BotFather setup

1. Create the bot with [@BotFather](https://t.me/BotFather) (`/newbot`); copy
   the token it gives you into `TELEGRAM_BOT_TOKEN` in `/etc/pops-bot/env`.
2. Find your numeric Telegram user ID via [@userinfobot](https://t.me/userinfobot)
   and add it to `TELEGRAM_ALLOWED_USER_IDS`.
3. Restart the service: `systemctl restart pops-bot`.
