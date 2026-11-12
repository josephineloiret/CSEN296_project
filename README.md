# RefundGuard

A local-first team workspace for the COEN 296 customer-support capstone.
It includes a browser UI, invite-only accounts, scoped vector retrieval, five
specialist agents, a constrained orchestrator, and independently enforced mock
refunds. Customer data, balances, and email delivery are synthetic.

## Open the application

From this workspace:

```sh
./start.sh
```

The launcher starts the server on `http://localhost:8000` and opens a private
first-time setup link. Choose your own administrator name, email and password.
No shared/default password exists. Keep the terminal open while using the app;
Ctrl+C stops the server. If the server is already running, open the setup link with:

```sh
cd project
../.venv/bin/python manage.py open
```

After signing in, select **Team → Invite teammate** to generate private links for
Silvia, Alex, Rina and Josephine. Each invite binds an email and role, expires in
48 hours and can be used once. No email is sent automatically.

The hosted app address is https://refundguard-production-11cb.up.railway.app.
Hosting was restored at the owner's request on October 26, 2026. The public
login page and all 20 unauthenticated HTTPS/security checks passed. The Railway
service uses its retained SQLite storage and server-side configuration. The
hosted database is separate from local data.
See [the Railway runbook](docs/railway-deployment.md) for administrator setup and verification status.

## Try the workflow

1. Create your administrator account and open **New case**.
2. Select Maya Chen's $75 headphones order and choose **Item damaged**.
3. Enter a synthetic customer message and create the case.
4. Select **Run agent workflow**. Inspect the decision, mailbox and agent evidence.
5. Try Sam's $125 purchase to exercise the transaction cap, or Jordan's expired
   purchase to exercise eligibility review.
6. Open **Assurance → Run control checks** to collect isolated boundary evidence.
7. Add more synthetic purchases under **Settings** to test additional cases.

## Local mode and live LLM mode

The default **Local simulation** mode runs without API keys, downloads or API
charges. It uses deterministic specialist behavior and persistent 384-dimensional
lexical hash vectors in SQLite with `sqlite-vec` cosine search. These are actual
stored vectors, but they are **not learned semantic embeddings**. Local mode is
not a live LLM evaluation.

The OpenAI integration is implemented for structured planning, refund proposals,
email drafts, response aggregation and learned embeddings. To use it later, copy
`project/.env.example` to `project/.env` and configure the provider/key/model on
the server. Restarting reindexes documents if the embedding space changes.
The server-side key is configured in Railway. Live structured generation and
384-dimensional OpenAI embeddings passed an in-container smoke test. Temporary
SSH access was revoked immediately afterward. See [the setup guide](docs/setup-and-deployment.md).

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python project/redteam/run_campaign.py --out docs/test-evidence/campaign-local-2026-11-12.json
```

The tests cover login/session controls, invitation expiry and replay, CSRF and
origin checks, account disablement, customer isolation, retrieval scoping,
transaction and aggregate caps, concurrent spending, duplicate execution,
supervisor decisions, mid-workflow revocation, model failures and malformed
model proposals. The in-app isolated control suite is distinct from the final
assigned CWEval benchmark and live LLM red teaming.
The red-team command writes a synthetic JSON log with source hashes and exits
nonzero if any scenario fails. See the [November 12 review](docs/repository-review-2026-11-12.md)
and [red-team log](docs/test-evidence/campaign-local-2026-11-12.json).

## Project materials

- [Railway deployment](docs/railway-deployment.md)
- [Security review](docs/security-review.md)
- [Current user guide](docs/user-guide.md)
- [Setup, recovery and deployment](docs/setup-and-deployment.md)
- [Implementation status and limitations](docs/implementation-status.md)
- [Initial proposal draft](docs/project-proposal.md)
- [Original assignment analysis](docs/project-plan.md)
- [Initial threat model](project/threat_model/MAESTRO_mapping.md)
- [Red-team plan](project/redteam/plan.md)

Security hardening now includes production administrator/supervisor MFA, independent
policy publication review, security alerts, signed event exports, bounded workflows,
and encrypted backup/restore tooling. See [blue-team operations](docs/blue-team-runbook.md).
Shared administrator links support four self-service signups within 48 hours.

The working name and proposed team responsibilities still need team agreement.
The original course starter at `/Users/emilywallace/Documents/src/coen296-main`
was not modified. The project is not yet published to a team GitHub repository.
