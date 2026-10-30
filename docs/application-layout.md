# Application layout

## Request flow

The browser calls the same-origin API in `app/main.py`. Authentication and role
checks establish who can act. The workflow gathers scoped context, runs specialist
agents, and sends refund proposals through independent execution controls before
writing a ledger outcome. Model output cannot bypass those controls.

## Active modules

| Area | Files | Responsibility |
| --- | --- | --- |
| HTTP and UI | `app/main.py`, `app/schemas.py`, `app/static/` | API routes, request validation and browser workspace |
| Identity | `app/security.py`, `app/mfa.py` | Passwords, sessions, CSRF, throttling, MFA and recovery codes |
| Agents | `app/workflow.py`, `app/agents.py` | Orchestration and the Intake, Email, Records, Refunds and Reporting specialists |
| Models and retrieval | `app/ai.py`, `app/knowledge.py`, `app/budget.py` | Model adapter, scoped document retrieval and provider budgets |
| Trusted execution | `app/refunds.py`, `app/execution.py` | Eligibility, refund limits, authority checks and bounded execution |
| Storage and configuration | `app/store.py`, `app/config.py` | SQLite records, runtime settings and environment validation |
| Operations | `app/monitoring.py`, `app/recovery.py` | Alerts, signed security snapshots and encrypted backup/restore |
| Isolated evaluation | `app/benchmarks.py`, `redteam/run_campaign.py` | Disposable control checks and synthetic attack scenarios |

## Entry points and supporting files

- `start.sh`: starts the local server and opens setup or the existing workspace.
- `manage.py`: trusted local setup, account recovery, usage and backup operations.
- `entrypoint.py`: prepares container volume ownership and starts one worker as UID 10001.
- `scripts/`: evidence export, a standalone refund demo and security CI helpers.
- `deploy/`: nonsecret hosting configuration and credential-free public checks.
- `tests/`: regression coverage for application behavior and security boundaries.
- `examples/starter/`: original demonstration modules, separate from the active app.

Local runtime state belongs in the ignored `data/` directory. Test fixtures and
campaigns use temporary databases; generated campaign results belong under the
ignored `redteam/results/` directory.

See [local development](local-development.md) for commands and the
[documentation index](README.md) for operating guides.
