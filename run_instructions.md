# Local run instructions

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

From the repository root, run all tests with `.venv/bin/python -m pytest -q`.
The lock file includes the development test dependencies used in verification.
All accounts, sessions, records, vectors, balances and evidence are persisted in
`data/refundguard.sqlite3`. That directory is ignored by Git.

To collect evidence from a running app, use `run_demo.py` with your own account.
Passwords are entered interactively and never placed in command arguments:

```sh
.venv/bin/python run_demo.py
# Optionally process an existing synthetic case before collecting evidence:
.venv/bin/python run_demo.py --case-id RG-YOURCASE
```

For API usage: log in at `/api/auth/login` with JSON and the configured `Origin`.
Keep the returned HttpOnly session cookie; include the returned `csrf` as
`X-CSRF-Token` on every authenticated mutation. No browser tokens are stored in
localStorage. The browser UI handles these details automatically.
