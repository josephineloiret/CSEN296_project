# Team repository integration

Target: https://github.com/josephineloiret/CSEN296_project
Base: `main` at `275aa70cf3461b96941da1865804b705c1c92e9c`.
Integration branch: `codex/refundguard-integration`.

## Layout and application

The team starter puts `app/`, `redteam/`, requirements and run scripts at the
repository root. This integration uses that layout for the launcher, tests,
security scanner, Docker build and CI workflow.

The application includes a browser UI and authenticated API, five specialist
agents, scoped retrieval, optional model integration, transactional mock refunds,
production privileged MFA, independent policy review and rollback, security alerts,
signed event snapshots, bounded execution, and encrypted backup/restore tooling.

The original `app/agent.py` and `app/retriever.py` remain as starter references.
The active workflow uses the new modules. The starter README is retained in
`docs/starter-readme.md`. Regression tests, campaign tooling and operating
instructions accompany the application.

## Private data and deployment

Environment secrets, runtime databases, MFA/evidence/backup keys, encrypted
archives, virtual environments, runtime logs and private invitation tokens are
excluded. Local and hosted runtime data are independent of this checkout.

The Railway service is configured independently; this integration does not switch
its source or redeploy it. For GitHub autodeploy, use the root build context,
one worker/replica, and the persistent volume plus server-side variables.

## CI

GitHub Actions runs application regression tests, credential scanning, Python
dependency auditing, a Docker build and a HIGH/CRITICAL Trivy container gate.
The gate uses `--ignore-unfixed`, so vulnerabilities without available fixes are
excluded from its results. Those vulnerabilities remain in the image; this scan
policy does not remediate them. Review current workflow annotations before merging.
