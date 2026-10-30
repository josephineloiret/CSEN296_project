# RefundGuard

RefundGuard is the team's COEN/CSEN 296 customer-support and AI-assurance project.
It extends this repository's original starter with a browser workspace, five
specialist agents, scoped retrieval, and independently enforced mock refunds.
All customer records, balances, and email delivery are synthetic.

## Run locally

Python 3.12 is the tested runtime. From the repository root:

```sh
./start.sh
```

The launcher installs the locked dependencies if needed, starts the server at
`http://localhost:8000`, and opens a private first-time setup link. Choose your own
administrator name, email, and password. Keep the terminal running; Ctrl+C stops
the server. To reopen setup or the existing workspace:

```sh
.venv/bin/python manage.py open
```

No default/shared password exists. Invite teammates under **Team**. Individual
invitations bind an email and role. A **Shared admin link** permits four people
to choose their own name, email, and password within 48 hours; anyone holding it
gets full admin access. Share it privately. Production administrators/supervisors
must enroll an authenticator and save their single-use recovery codes.

See [run instructions](run_instructions.md) and the [user guide](docs/user-guide.md).

## Try the workflow

1. Create your administrator account and open **New case**.
2. Select Maya's recent $75 headphones purchase and the damaged-item reason.
3. Create the case, then select **Run agent workflow**.
4. Inspect the recommendation, independent control decision, ledger outcome,
   mailbox, and agent evidence.
5. Try an over-limit/expired case, pause authority, or run the isolated checks
   under **Assurance**.

The autonomous limits are $100 per transaction and $500 organization-wide per
UTC calendar week. Policies and customer messages cannot change trusted code
controls. Uploaded policy versions need a different administrator/supervisor's
approval before retrieval; approved prior versions can be restored.

## Local simulation and live models

Default local simulation requires no API key, downloads, or provider charges.
It uses deterministic specialists and persistent 384-dimensional lexical hash
vectors in SQLite; these are not learned semantic embeddings or a live LLM test.

For live structured generation and learned embeddings, copy `.env.example` to
`.env`, configure your server-side key/model/budgets, and restart. Secrets,
databases, keys, and backups are ignored by Git. See the
[setup guide](docs/setup-and-deployment.md).

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/scan_secrets.py
.venv/bin/python redteam/run_campaign.py --out redteam/results/campaign-local.json
```

Campaign output is written to the ignored `redteam/results/` directory.

GitHub Actions runs tests, credential-pattern checks, dependency auditing, a
Docker build, and a Trivy image scan. Review its results before merging.

## Operating instructions

- [Blue-team operations and recovery](docs/blue-team-runbook.md)
- [Setup and configuration](docs/setup-and-deployment.md)
- [Application layout](docs/application-layout.md)
- [Repository integration notes](docs/repository-integration.md)

Team repository: https://github.com/josephineloiret/CSEN296_project.
The original [starter README](docs/starter-readme.md) and starter agent/retriever
reference modules are retained. The active application uses `workflow.py` and
`knowledge.py`; the unauthenticated starter `/tasks`, `/logs`, and canned attack
endpoints have been replaced by authenticated workflows and isolated evaluation.

## Deployment

The existing demonstration is hosted on Railway:
https://refundguard-production-11cb.up.railway.app/.
Its database and settings are independent of a local checkout. This integration
adds code to the team repository; it does not switch the existing Railway service
to GitHub autodeploy. Build this repository from its root `Dockerfile` with one
worker/replica and a persistent `/data` volume. Read
[the deployment runbook](docs/railway-deployment.md) before changing hosting.

Off-site log/backup retention, hosting/provider-owner MFA, and review of
outstanding container advisories remain operator work. Do not place private invitation URLs in this repository.
