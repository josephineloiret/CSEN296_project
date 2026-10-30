# Local development

Python 3.12 is the tested runtime. Start from the repository root:

```sh
./start.sh
```

The launcher installs the locked dependencies into `.venv` if the environment is
missing, starts on loopback port 8000, then opens the workspace with the one-time
setup key in the URL fragment. The fragment is removed by the page and is not
sent in HTTP requests. Choose an administrator password of 15–128 characters.

For manual setup:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, open the private setup link:

```sh
.venv/bin/python manage.py open
```

The app is at `http://localhost:8000`. Use that hostname consistently; cookies
and origin checks intentionally distinguish `localhost` from `127.0.0.1`.

## Checks and demos

The lock file includes the development test dependencies. From the repository root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/scan_secrets.py
.venv/bin/python -m scripts.refund_demo
.venv/bin/python redteam/run_campaign.py --out redteam/results/campaign-local.json
```

The refund demo and local campaign use disposable databases. Campaign output is
ignored by Git. Live campaign mode requires explicit `--live` and provider setup;
see [configuration](setup-and-deployment.md) before enabling paid requests.

## Local state and evidence

All accounts, sessions, records, vectors, balances and evidence are persisted in
`data/refundguard.sqlite3`. That directory is ignored by Git.

To collect evidence from a running app, use the `scripts.export_evidence` module with your own account.
Passwords are entered interactively and never placed in command arguments:

```sh
.venv/bin/python -m scripts.export_evidence
# Optionally process an existing synthetic case before collecting evidence:
.venv/bin/python -m scripts.export_evidence --case-id RG-YOURCASE
```

## API usage

For API usage: log in at `/api/auth/login` with JSON and the configured `Origin`.
Keep the returned HttpOnly session cookie; include the returned `csrf` as
`X-CSRF-Token` on every authenticated mutation. No browser tokens are stored in
localStorage. The browser UI handles these details automatically.
