# Contributing

Thanks for looking at this. It is a small self-hosted project and contributions
are genuinely welcome — including bug reports and "the deploy didn't work for me".

## Reporting bugs

Open an issue and include:

- What you did, what you expected, what happened instead
- Your OS, whether you used Docker or ran it directly, and the Python version
- Relevant output from `docker compose logs --tail=50` (redact credentials and
  never paste `data/telegram_session` or `.env`)

## Setting up for development

```bash
git clone <your-fork-url>
cd telegram-relay-dashboard
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install fastapi[standard]    # TestClient, used by the tests

export RELAY_USERNAME=operator
export RELAY_PASSWORD=dev-password
uvicorn app:app --reload --port 8000
```

Use a throwaway Telegram account while developing. Development runs against
your real `data/` directory, so a bug in the forwarding path can send messages
to your converter bot.

## Tests

The tests need no test runner — each is a plain script that exits non-zero on
failure:

```bash
python -m tests.test_smoke
python -m tests.test_auto_resume
python -m tests.test_throttle
python -m tests.test_maintenance

# all four
for t in smoke auto_resume throttle maintenance; do
  python -m tests.test_$t || echo "FAILED: $t"
done
```

Each test redirects `RELAY_DATA_DIR` to a temp directory, so your real
database and Telegram session are never touched.

**Please run all four before opening a pull request.** A change to
`telegram_service.py` or `database.py` should not break the others.

## Style

- Python: PEP 8, four spaces, no type annotations where the surrounding code
  has none.
- Comments explain *why*, not what. The existing code aims for this — match it.
  `# increment i` is noise; `# Telegram returns newest -> oldest, so reverse
  before sending to keep publication order` is useful.
- Frontend is plain JavaScript, no build step and no framework. Keep it that
  way: someone should be able to edit `static/app.js` and hit reload.
- Every value that reaches `innerHTML` from Telegram or the database goes
  through `escapeHtml()`. Please keep it that way.

## Commits and pull requests

- One logical change per commit, with a message explaining the reason.
- Reference the issue it fixes (`Fixes #12`).
- Say in the description how you tested it.

## Security

Do not open a public issue for a vulnerability — see [SECURITY.md](SECURITY.md).
Never commit `.env` or `data/telegram_session`.

## License

Contributions are accepted under the [MIT License](LICENSE).
