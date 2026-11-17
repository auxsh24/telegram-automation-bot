# Telegram Relay Dashboard

Self-hosted dashboard that watches Telegram source channels and forwards their
messages to a converter bot. Runs locally in Docker. Everything is configured
in the browser: no `.env` file needed.

## Run

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and
Telegram API credentials from [my.telegram.org](https://my.telegram.org)
(API Development Tools).

```bash
docker compose up -d --build
```

Open **http://localhost:8000**, then:

1. Enter API ID and API Hash, then save
2. Enter your phone number, then the OTP (and 2FA password if you have one)
3. Set the converter bot and source channels, then save
4. Turn on **Auto-resume after restart**, then click **Start Monitor**

Your Telegram login and settings are saved in `./data`, so restarts and
rebuilds do not ask for the OTP again.

## Security

The dashboard has **no password**. The port is bound to `127.0.0.1` so only
your own machine can open it. Do not change that to `0.0.0.0` or publish the
port: anyone who reaches it can control your Telegram account.

Never share or commit the `data/` folder. `data/telegram_session.session` is a
live Telegram login.

## Everyday commands

```bash
docker compose logs -f --tail=50      # logs
docker compose restart                # restart (monitoring resumes if auto-resume is on)
docker compose down                   # stop
docker compose up -d --build          # update after changing code
```

Backup: copy the `data/` folder while the container is stopped.

## Troubleshooting

| Problem | Fix |
|---|---|
| Nothing happens on `docker compose up` | Start Docker Desktop and wait until it is ready |
| `port is already allocated` | In `docker-compose.yml` change `127.0.0.1:8000:8000` to `127.0.0.1:8080:8000` and open port 8080 |
| Changes to the code do not show | Always run with `--build` |
| `unable to open database file` (Linux) | `sudo chown -R 999:999 data` |
| Asked for OTP again | Telegram invalidated the session; log in again |
| Container `unhealthy` | `docker compose logs --tail=50` |

## Optional settings

Set as environment variables (or in a `.env` next to `docker-compose.yml`,
which Compose reads automatically): `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`,
`RELAY_CONVERTER_BOT`, `RELAY_SOURCE_CHANNELS` (JSON list),
`RELAY_DUPLICATE_TTL_DAYS`, `RELAY_RETRY_ATTEMPTS`,
`RELAY_RETRY_DELAY_SECONDS`, `RELAY_LOG_RETENTION_DAYS`.

## License

MIT, see [LICENSE](LICENSE).
