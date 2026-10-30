# RefundGuard on Railway

Project dashboard: https://railway.com/project/4df6bd60-2948-4ba3-910c-b5c0fe473d19

Public app: https://refundguard-production-11cb.up.railway.app

## Current state: online, restored October 26, 2026

The owner requested bringing the app back online on October 26, 2026 (Pacific
time). Current source was uploaded to the existing service as deployment
`f0908670-56e3-4987-ad6d-3ae22da8c4bc`; Railway reports SUCCESS and stopped=false.
The retained volume remains mounted at `/data`. The browser shows the existing
workspace's sign-in page, and all 20 public HTTPS/security checks passed. No
credentials were changed and no paid OpenAI calls were needed for restoration.

## Previous shutdown

On October 23, 2026 (Pacific time), the active successful deployment was removed
at the owner's request. Railway reports the service stopped, and the public
health route returns 404. The service, variables, domain and persistent volume
were retained. This does not cancel a paid Railway subscription or remove
storage charges. This shutdown was superseded by the owner's October 26 request.

To restore later, upload the current repository source using the redeploy
instructions below. A fresh source upload is appropriate even after Railway's
old deployment image retention period expires. The existing volume retains
account/case data while it remains available under the account's retention policy.

The project has one application service and one persistent volume at `/data`.
Service IDs and nonsecret settings are recorded under `deploy/`. The
OpenAI API key was entered by the owner in Railway Variables; it is not saved
in the repository. The service's `AI_PROVIDER` is `openai`.

## Configuration

- Build context: repository root; Dockerfile path `Dockerfile`.
- Runtime: `entrypoint.py`, dynamic `$PORT` set to 8000, one Uvicorn worker.
- Runtime data: `/data/refundguard.sqlite3` on a Railway persistent volume.
- Non-root application: entrypoint prepares volume permissions as root, then
  permanently drops to UID/GID 10001 before serving HTTP requests.
- HTTPS origin: `https://refundguard-production-11cb.up.railway.app`.
- Health probe: `/health`; Railway's exact probe hostname is allowed only for
  this minimal read-only route, not for account/data endpoints.
- Restart: on failure, at most three retries. One replica. Idle sleeping enabled.
- Model: `gpt-5.6-luna`; reasoning `none`; embeddings `text-embedding-3-small`.
- Application API budget: $1/day and $5/month in conservative local accounting.

No separate paid vector database or external email/banking service is required.
All email/financial activity remains synthetic. The API adapter permits only
fixed OpenAI endpoints, not a public configurable forwarding proxy.

The old globally installed Railway CLI is version 3.21.0 and is incompatible
with the current API. A current CLI (5.71.0) was installed in a temporary directory
for this deployment. For future use, update the CLI or run the official current
`@railway/cli` package through npm. Do not print `railway variable list --json`
into shared logs: it contains secrets, even though the verification in this
session filtered values before showing output.

## Redeploy

From the repository root, with a current authenticated Railway CLI:

```sh
railway link --project 4df6bd60-2948-4ba3-910c-b5c0fe473d19 --environment production --service refundguard
railway up . --path-as-root --service refundguard --environment production --detach
```

Use the Railway dashboard to review deployment status and logs. CLI upload does
not configure GitHub autodeploys; linking a GitHub repository is still future work.
Do not upload the local environment file or data directory. Docker `VOLUME`
instructions are not supported by Railway; the persistent volume is attached
through Railway service settings instead.

## First administrator and live smoke test

The hosted database is separate from the local database. The hosted application
has no preconfigured administrator password. The owner needs the private
one-time setup link before creating the first account.

For future administrator setup diagnostics, execute inside an owner-authorized deployment shell:

```sh
python manage.py setup-link
```

Alternatively, run this yourself in Railway's deployment shell. Keep the link
private, open it, and choose your own password. Do not paste the bootstrap token
or API key in chat or public documentation. Once the first administrator exists,
setup is disabled permanently and teammates join using single-use invitations.

Live structured generation and 384-dimensional OpenAI embeddings passed on
October 23, 2026 (Pacific time), with sqlite-vec v0.1.9 and process UID 10001.
The two synthetic calls accounted for $0.000075 in the application's usage ledger.
The owner explicitly approved temporary SSH access. The private setup key was
retrieved and delivered directly to the owner; it is not recorded here. The
temporary credential was then revoked, Railway confirmed no registered SSH keys,
and the temporary local keypair was deleted. Initial account creation remains
the owner's step, using their own password.

## Verification and security

To run the public checks without credentials or paid calls:

```sh
.venv/bin/python deploy/verify_public.py https://refundguard-production-11cb.up.railway.app --out tmp/railway-public-verification.json
```

The tests do not create a user account, retrieve the API key or send model requests.
The Railway owner controls hosting secrets. Invite teammates to the application,
not to the Railway workspace, unless they need infrastructure administration.


## October 27 hardening deployment

Deployment 38453f6c-cc3d-458a-9a57-00392b65f674 is healthy. All 27 expanded
public checks passed. Privileged production accounts now require TOTP MFA;
policies require a different reviewer; security alerts and signed event export
are under Assurance. The first automatic encrypted backup completed at
2026-10-28 02:35:09 UTC (October 27, 7:35 PM Pacific). See blue-team-runbook.md
for key custody, backup scheduling limits, policy migration and recovery.
The shared administrator invitation was verified without consuming any signup.
Never place its raw token in public documentation.
