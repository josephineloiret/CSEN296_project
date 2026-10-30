# Railway deployment

[Public demo](https://refundguard-production-11cb.up.railway.app/) ·
[Project dashboard](https://railway.com/project/4df6bd60-2948-4ba3-910c-b5c0fe473d19)

The hosted service has its own database and settings. Pushing this repository
does not redeploy it or enable GitHub autodeploy. Check the Railway dashboard
for current deployment status.

## Configuration

Use the repository root as build context and `Dockerfile` as the build file.
The nonsecret settings snapshot lives in [`deploy/`](../deploy/), alongside
[`railway.env.example`](../deploy/railway.env.example), a service-variable template.
Set any API key separately in Railway Variables.

| Setting | Value or requirement |
| --- | --- |
| Runtime | `entrypoint.py`, dynamic `$PORT`, one Uvicorn worker |
| Replicas | One; SQLite and workflow state assume a single instance |
| Persistent volume | Mount at `/data`; database is `/data/refundguard.sqlite3` |
| Process identity | Entrypoint prepares volume ownership, then drops to UID/GID 10001 |
| Public origin | Exact HTTPS domain, or derived from `RAILWAY_PUBLIC_DOMAIN` |
| Health probe | `/health`; the platform probe hostname is allowed only on this route |
| Restart policy | On failure, up to three retries |
| Models | `gpt-5.6-luna`, reasoning `none`, embeddings `text-embedding-3-small` |
| Provider budgets | $1/day and $5/month in conservative application accounting |

The model settings and budgets are configurable. All customer records, financial
activity and email delivery remain synthetic. The app requires no external
banking, mail service or vector database.

## Deploy source

Use an authenticated Railway CLI compatible with the current service API.
From the repository root:

```sh
railway link --project 4df6bd60-2948-4ba3-910c-b5c0fe473d19 --environment production --service refundguard
railway up . --path-as-root --service refundguard --environment production --detach
```

Review deployment status and logs in the dashboard. CLI uploads do not enable
GitHub autodeploy. If configuring autodeploy separately, retain the root build
context, one worker/replica, service variables and `/data` volume.

The persistent volume is attached through service settings. Runtime data and
local secrets are excluded from source uploads. Do not print a full variable
listing into shared logs; it can contain secrets.

## Administrator access

For a fresh database, obtain the first-time setup link inside an authorized
deployment shell:

```sh
python manage.py setup-link
```

Keep the link private and choose your own administrator password in the browser.
Setup becomes unavailable after the first administrator is created. Existing
installations keep their accounts and invite teammates through **Team**.
Production privileged accounts require MFA. See
[setup and configuration](setup-and-deployment.md) for account behavior.

## Public verification and recovery

Run the credential-free public checks from the repository root:

```sh
.venv/bin/python deploy/verify_public.py https://refundguard-production-11cb.up.railway.app --out tmp/railway-public-verification.json
```

These checks do not create accounts, retrieve keys or send model requests.
For key custody, policy review, alerts, signed event exports and encrypted
backup/restore, use the [blue-team runbook](blue-team-runbook.md).
