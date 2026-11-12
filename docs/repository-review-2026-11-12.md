# Repository review — November 12, 2026

## Baseline and scope

At the start of this review, `main` had no commits, every project file was
untracked, and no Git remote was configured. Existing test logs were present on
disk but were not committed. There is no branch history from which to attribute
earlier changes to particular commits or people.

All 26 files listed in `docs/test-evidence/source-manifest.json` matched their
saved SHA-256 hashes, including the application, browser assets, container
entrypoint and dependency lock. The 91-file local Codex checkpoint tree also
provided a content snapshot, rather than commit history. No pre-existing
application-source differences were found against these saved baselines.

The review covered the application boundaries, workflow, retrieval, refund
execution, existing regression tests, campaign, CI, dependency consistency and
evidence handling. Verification used disposable local databases and synthetic
records. No hosted service, real account, email delivery or paid model call was
used. The initial local commit includes the project baseline so the test and its
evidence can be reproduced from versioned source.

## Current behavior and effects across the project

| Area | Behavior and practical effect | Evidence |
| --- | --- | --- |
| Browser and API | FastAPI serves the browser UI and authenticated API together. Sessions, CSRF/origin/host checks and server-side roles restrict access. Production privileged accounts require MFA. | Authentication, role, customer isolation and MFA tests passed; browser JavaScript syntax check passed. |
| Agent workflow | Intake, Records, Refunds, Email and Reporting run in a constrained sequence. Invalid plans, citations, provider errors, deadlines and revoked authority require review or block execution. | Workflow, malformed proposal, in-flight denial/revocation and capacity tests passed. |
| Retrieval | SQL limits retrieved context to policies and the case customer's documents. Human policy changes require another reviewer. Local vectors are lexical hashes, not learned semantic embeddings. | Retrieval/version/review tests passed; campaign delivered the poisoned document while keeping the other customer's bank marker out of generated results. |
| Refunds | Trusted transactional code enforces purchase eligibility, assignment, supervisor decisions, revocation, the $100 transaction cap and $500 organization-wide UTC weekly cap. Ledger uniqueness prevents repeated credit. | Financial boundary/concurrency tests passed; the forged $125 request was blocked with `transaction_limit`, zero ledger entries and zero balance change. |
| Model costs and recovery | Local simulation needs no API calls. Live calls use persistent budget reservations. Encrypted restore revokes sessions/invitations and pauses authority. | Budget/recovery tests passed; campaign recorded zero provider requests and a successful isolated restore. |
| Delivery and CI | The workflow defines regression, secret-pattern, dependency and container checks. It now also runs the synthetic red-team command. | Local tests and scans passed; Docker is unavailable and remote CI was not run. |

## Findings addressed in this review

1. **A failing campaign still returned exit status 0.** This could let automation
   report success despite failed security or functionality results. The command
   now writes the report and exits 1 when any scenario's joint result fails.
2. **Some checks could pass without exercising the intended path.** HTTP results
   were not validated, the first replay response was discarded, and empty
   retrieval could satisfy the scope check. The campaign now checks every run
   response, requires retrieval for executing workflows, and confirms that the
   malicious document's ID and payload reached retrieved context. Revocation
   instead requires HTTP 409 and no retrieval. Ledger amounts are also bounded,
   and the cross-customer marker check includes case output and messages.
3. **There was no automated check of the campaign's saved evidence or failure
   behavior.** Two subprocess tests now verify the actual command and JSON log.
   One uses production-looking environment settings and verifies that the
   configured database is never opened and the fake API key is never exported.
   The other deliberately disables workflow execution and verifies a failing
   exit with a retained failed log.
4. **The campaign changed the caller's environment during import.** Import-time
   isolation now restores the previous environment after loading the ASGI module
   inside a temporary sandbox.

The application runtime and browser source are unchanged. The changes affect
the red-team harness, its regression coverage, CI and documentation. Reports now
include source SHA-256 hashes, attack payload delivery checks, expected HTTP
statuses and an overall `all_passed` result.

## Fresh verification

- Full regression: **79 passed, plus 6 subtests**, with one existing Starlette
  TestClient/httpx deprecation warning. See
  [JUnit log](test-evidence/regression-2026-11-12.xml).
- Red-team campaign: **6/6 functional, security and joint passes**. See
  [synthetic campaign log](test-evidence/campaign-local-2026-11-12.json).
- Scenarios: eligible purchase, forged authority/over-cap injection, poisoned
  customer document, expired-purchase override, revoked authority and replay.
- Replay returned HTTP 200 twice, produced one ledger entry and credited $75 once.
- `node --check project/app/static/app.js` passed. Every installed locked
  dependency version matched `project/requirements.lock.txt`.
- The repository's credential-pattern scanner reported zero flagged files.
  An additional scan across candidate text files found only the existing
  deliberately fake key in the credential-leak regression test. Existing preview
  screenshots were inspected for exposed setup/invitation credentials.

## Remaining limits

These are deterministic local control tests, not fresh live-LLM prompt-injection
evaluations or the assigned CWEval framework. Existing live/hosted logs and
dependency-audit files are historical evidence; they were not refreshed here.
No current hosted deployment, Docker build, container scan or remote CI result
is established by this review. There is still no configured remote to push to.
Passing these checks does not establish coverage of every attack or browser flow.

## Reproduce

From the repository root, after installing the locked requirements in `.venv`:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python project/redteam/run_campaign.py --out docs/test-evidence/campaign-local-2026-11-12.json
.venv/bin/python project/scripts/scan_secrets.py
```

The campaign log contains synthetic evidence suitable for this repository.
Operational databases, `.env` files, keys and ordinary production log directories
remain excluded by `.gitignore`.
