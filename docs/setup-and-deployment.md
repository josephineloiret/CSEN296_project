# Setup and configuration

## First administrator

Run `./scripts/start.sh` from the repository root. It opens a browser setup link carrying
an unguessable one-time token from `data/setup-token`. Only the token
holder can create the initial administrator; creation is serialized and disables
setup permanently. The setup file is deleted after success. No administrator
password is preconfigured, logged or stored in plaintext.

If a server is already running, use:

```sh
.venv/bin/python -m scripts.manage open
```

`python -m scripts.manage setup-link` prints the link instead of opening it. Treat it as a
private, temporary credential. Do not commit or share the data directory.

## Team accounts

Use **Team → Invite teammate** while signed in as an administrator. Enter the
actual teammate's email and select a role:

| Role | Permissions |
| --- | --- |
| Customer | Own synthetic profile, purchases, cases, incoming case messages and outcome notices |
| Member | All sandbox support cases, workflow runs, mock inbox, customer record edits, reports and evidence |
| Supervisor | Member permissions plus policy indexing, supervisor decisions, authority pause/restore and evidence export |
| Administrator | Supervisor permissions plus invitations and account enable/disable |

Invitations are generated in the app; it does not send real email. Share each
private link through your chosen channel. Individual invitations bind the
intended email and role, expire after 48 hours, and become invalid after use or
replacement. Shared administrator links allow four people to choose their own
name, email and password within 48 hours. Anyone holding an active shared link
can claim administrator access, so keep it private and revoke it after use.

Each person chooses their own passphrase. Session identifiers are random,
server-side, stored as hashes in SQLite, sent in HttpOnly/SameSite=Strict cookies,
and expire after 30 idle minutes or 8 hours total. Login and other expensive
operations are rate-limited persistently. Production cookies are Secure and use
a `__Host-` prefix. Disabling an account immediately revokes its sessions.
Password changes require the current password and invalidate all prior sessions.

Production administrators and supervisors must enroll and verify TOTP MFA.
Email ownership verification, self-service password-reset email and enterprise
SSO are not implemented. See the [blue-team runbook](blue-team-runbook.md) for MFA and recovery details.

## Local password recovery

The machine/database administrator can run:

```sh
.venv/bin/python -m scripts.manage reset-password --email person@example.com
```

The new password is entered interactively with hidden input. All sessions for
that account are revoked. This is a privileged local operation, not a public
password-reset endpoint.

## Enable real model calls later

Copy `config/local.env.example` to `.env` and edit it locally:

```dotenv
APP_ENV=development
APP_ORIGIN=http://localhost:8000
AI_PROVIDER=openai
OPENAI_API_KEY=your-private-key
OPENAI_MODEL=gpt-5.6-luna
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_REASONING_EFFORT=none
OPENAI_DAILY_BUDGET_USD=1.00
OPENAI_MONTHLY_BUDGET_USD=5.00
```

Restart the server. The adapter calls the Responses API with strict JSON schemas
and `store=false`. The embedding API supplies learned 384-dimensional vectors;
document chunks are lazily reindexed to the configured embedding space on retrieval. Startup never calls OpenAI. Model
calls have timeouts and bounded input/output. API errors and malformed output
hold unexecuted cases for review; there is no silent fallback to local approval.
An already-executed refund remains recorded even if a later model call fails.

Use only synthetic case/profile content: the live mode sends selected request
text and authorized retrieved evidence to the configured provider. The API key
stays on the server and is never included in frontend settings or evidence.
Enabling live mode will incur provider usage. The app reserves a conservative
request estimate before each provider call, enforcing the configured daily and
monthly limits across concurrent requests and restarts. Provider-reported token
usage reconciles successful calls; unknown/failed calls retain reservations.
These controls use documented rates and are not a provider billing guarantee.
Inspect usage with the authenticated `/api/usage` endpoint or `python -m scripts.manage usage`.
The key is never returned in those responses. Only staff can trigger paid tools;
customer intake and account creation do not call OpenAI.

Official implementation references:

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

## Remote team access

The current local URL is accessible only on this computer. To share the app,
deploy one application instance behind a trusted HTTPS reverse proxy, use a
persistent data volume, and set the exact public origin:

```dotenv
APP_ENV=production
APP_ORIGIN=https://refundguard.your-domain.example
AI_PROVIDER=local
DATABASE_PATH=/data/refundguard.sqlite3
```

Railway has been selected and a RefundGuard service and persistent
volume were created. See [the Railway runbook](railway-deployment.md) for the
actual service IDs, public URL, configuration and verification status.

Build context is the repository root. Mount a persistent
volume at `/data`. The container starts briefly as root to fix mounted-volume
ownership, then permanently drops to UID/GID 10001 before serving requests. Run a single app instance and
one worker; the SQLite-backed rate limiter and workflow state are intended for
a small team, not a replicated deployment. Terminate TLS at your proxy and pass
HTTPS scheme headers only from trusted proxy addresses, e.g. Uvicorn
`--proxy-headers --forwarded-allow-ips=THE_PROXY_IP`. Production rejects HTTP
requests, sets Secure cookies and HSTS, and requires the configured host/origin.
Use the same origin for frontend/API and do not open permissive CORS.

Generate/open the bootstrap link with `python -m scripts.manage open` inside the deployed environment;
it uses the configured public origin. Invite links generated before changing the
origin must be regenerated for the new deployment.

Back up the SQLite database using its backup API or with the service stopped;
include the data volume and protect access to backups. Do not copy only the main
SQLite file while writes are active, because WAL transactions may be omitted.
There is no independent security audit or penetration-test certification. Before
remote deployment, verify the target proxy/TLS/storage configuration with the
actual hosting environment.
