https://telegramrelay.vercel.app/

# Telegram Relay Dashboard

A self-hosted dashboard that watches Telegram channels and automatically forwards new posts to a converter bot. Everything is set up from the browser — no `.env` needed.

## Features

- Live monitoring of source channels
- "Analyze Today" to forward missed posts from today
- Duplicate protection, retries and auto-reconnect
- Live activity log and daily stats

## Tech Stack

Python 3.12 · FastAPI · Telethon · SQLite · Docker

## Quick Start

You need Docker and Telegram API credentials (`api_id`, `api_hash`) from [my.telegram.org](https://my.telegram.org).

```bash
git clone https://github.com/auxsh24/telegram-automation-bot.git
cd .\telegram-automation-bot\mainfile\
docker compose up -d --build

```

Open **http://localhost:8000**, then:

1. Enter your API ID and hash
2. Log in with your phone number and code
3. Set the converter bot and source channels
4. Click **Analyze Today** or **Start Monitor**

## Security

The dashboard has no password, so it is bound to `127.0.0.1`. Do not expose it publicly. The `data/` folder holds your Telegram session — never commit it.

## License

Use-only license — see [LICENSE](LICENSE). Not affiliated with Telegram.
