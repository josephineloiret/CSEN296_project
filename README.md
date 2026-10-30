# RefundGuard

A customer-support sandbox with five specialist agents, scoped policy retrieval,
and independently enforced mock refunds. Customer records, balances and email
are synthetic. Local simulation runs without an API key or provider charges.

## Quick start

Use Python 3.12 and run these commands from the repository root:

```sh
./scripts/start.sh
```

The launcher installs locked dependencies into `.venv`, starts the app at
`http://localhost:8000`, and opens first-time administrator setup. Choose your own
name, email and password. Keep the terminal running; Ctrl+C stops the server.
To reopen an existing workspace, run `.venv/bin/python -m scripts.manage open`.

Invite teammates under **Team**. Individual invitations bind an email and role;
a shared admin link permits four signups within 48 hours. Share links privately.
Production administrators and supervisors must enroll an authenticator.

## Try a refund

1. Open **New case** and select Maya's recent $75 headphones purchase.
2. Choose the damaged-item reason, create the case, and run the agent workflow.
3. Inspect the recommendation, trusted control decision, ledger outcome and inbox.
4. Try an over-limit case or pause authority, then compare the result.

Trusted controls limit autonomous refunds to $100 per transaction and $500 per
organization per UTC week. Policy uploads require a different reviewer's approval.

## Repository map

| Location | Purpose |
| --- | --- |
| [`app/`](app/) | API, agent workflow, trusted controls, persistence and browser UI |
| [`tests/`](tests/) | Application, refund, hardening and deployment regression tests |
| [`scripts/`](scripts/) | Local launcher, administration, evidence export, demos and CI utilities |
| [`redteam/`](redteam/) | Isolated synthetic attack campaign and ignored local results |
| [`deploy/`](deploy/) | Docker build, container entrypoint, Railway settings and public checks |
| [`docs/`](docs/) | Development, usage, configuration and operating instructions |
| [`examples/starter/`](examples/starter/) | Archived starter modules for reference |
| [`config/`](config/) | Local environment template |
| [`requirements/`](requirements/) | Runtime, development and locked Python dependencies |

## Development and checks

```sh
.venv/bin/python -m pytest -c tests/pytest.ini -q
.venv/bin/python scripts/scan_secrets.py
.venv/bin/python -m scripts.refund_demo
.venv/bin/python redteam/run_campaign.py --out redteam/results/campaign-local.json
```

The refund demo and default campaign use disposable synthetic data. Campaign
output is ignored by Git. See [local development](docs/local-development.md) for
manual startup, authenticated evidence export and API usage.

GitHub Actions runs tests, secret scans, dependency auditing, a Docker build and
Trivy. The container gate fails on HIGH/CRITICAL findings with available fixes;
`--ignore-unfixed` excludes other findings without patching those vulnerabilities.

## Guides

Start with the [documentation index](docs/README.md), or go directly to:

- [Using the workspace](docs/user-guide.md)
- [Configuration and account management](docs/setup-and-deployment.md)
- [Application modules and request flow](docs/application-layout.md)
- [Security operations and recovery](docs/blue-team-runbook.md)
- [Railway deployment](docs/railway-deployment.md)

For optional live models, copy `config/local.env.example` to `.env`, configure
the server-side key and budgets, and restart. See the configuration guide for data handling and
usage limits.

The existing [Railway demo](https://refundguard-production-11cb.up.railway.app/)
uses separate runtime data. Source changes in this branch do not redeploy it.
