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

## Deployment

Managed by `playbooks/deploy_pops_bot.yml`. Run from the `ansible-netbox`
directory:

```bash
ansible-playbook -i inventory.ini playbooks/deploy_pops_bot.yml --limit athena
```

### Unit file

`pops-bot/systemd/pops-bot.service` is deployed to
`/etc/systemd/system/pops-bot.service`. It depends on `network-online.target`
and `pops-api.service`, runs as user `will`, and loads secrets from
`/etc/pops-bot/env` via `EnvironmentFile`.

### Environment file

`/etc/pops-bot/env` - owner `root`, group `will`, mode `0640`. Created once
by the playbook (idempotent - not overwritten on re-runs). Contents:

```
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_ALLOWED_USER_IDS=<comma-separated numeric IDs>
POPS_API_URL=http://127.0.0.1:8765
POPS_API_KEY=<copied from /etc/pops-api/env at deploy time>
```

### Held-start behavior

The playbook enables the service but does NOT start it. At deploy time
`TELEGRAM_BOT_TOKEN` is set to the placeholder `REPLACE_ME`. The playbook
detects this and skips the start task, printing instructions instead. The
service remains in state `enabled / inactive` until the operator supplies a
real token.

### Go-live steps

1. Get a bot token from [@BotFather](https://t.me/BotFather) (`/newbot`).
2. Get your numeric Telegram user ID from [@userinfobot](https://t.me/userinfobot).
3. Edit the env file on athena (requires sudo):

   ```bash
   sudo nano /etc/pops-bot/env
   # Set TELEGRAM_BOT_TOKEN to the token from @BotFather
   # Set TELEGRAM_ALLOWED_USER_IDS to your numeric ID (comma-separated for multiple)
   ```

4. Start the service:

   ```bash
   sudo systemctl start pops-bot
   sudo systemctl status pops-bot
   ```

5. Message the bot: `/status` - it should reply with API status and uptime.

## BotFather setup

1. Create the bot with [@BotFather](https://t.me/BotFather) (`/newbot`); copy
   the token it gives you into `TELEGRAM_BOT_TOKEN` in `/etc/pops-bot/env`.
2. Find your numeric Telegram user ID via [@userinfobot](https://t.me/userinfobot)
   and add it to `TELEGRAM_ALLOWED_USER_IDS`.
3. Restart the service: `systemctl restart pops-bot`.
