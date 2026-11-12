# RefundGuard security review - October 27, 2026

The evidence-backed report is at ../output/pdf/RefundGuard_Security_Report.pdf.
The application changes are deployed to the existing Railway service.

## Current verification

- 77 regression tests passed, plus six subtests; one test-client deprecation warning.
- 27 current public HTTPS/auth/private-file checks passed.
- Six synthetic scenarios passed functional and security expectations in local
  simulation and in one live-model campaign. Live usage: $0.003663 accounted,
  42 requests, no unreconciled reservations, one shared $0.15 test ceiling.
- Updated locked dependencies passed pip-audit with no known vulnerabilities.
  cryptography was updated to 50.0.2 after advisories were identified in 46.0.7.
- The credential-pattern scan flagged zero files; it is a heuristic scan.
- A hosted log confirms the first automatic encrypted online backup completed.
- An isolated restore exercise verified integrity, foreign keys, balances/ledger,
  session and invitation revocation, and paused authority. Tampering was rejected.

## Deployed controls

Existing authentication/CSRF/host/origin/cookie controls, scoped retrieval,
independent refund caps/eligibility/revocation and conservative provider budgets
remain. New controls include mandatory production admin/supervisor TOTP,
encrypted MFA seeds, recovery/replay/session controls, independent policy review,
rollback, sanitized event output, in-app alert aggregation/acknowledgement,
signed event snapshots, global workflow capacity and cooperative deadlines,
upload deadlines and connection limits, encrypted retained online backups,
and safe restore tooling.

The owner-requested shared admin invitation permits four signups in 48 hours,
each choosing their own name/email/password. Only hashes are persisted; creation
and signup accounting are server-controlled. Links can be revoked. The bearer
link grants full admin rights and does not verify email ownership; keep it private.

## Limits and remaining work

This is a course sandbox, not an independent penetration-test or compliance
certification. Passing sampled scenarios does not establish invulnerability.
The campaign is an Appendix H-style project harness, not the unconfirmed assigned
CWEval framework. Docker is unavailable locally; CI/container checks are prepared
but await team-repository publication/execution. No other team was tested.

Off-host immutable/independent log retention and backup/key custody, hosting/provider
owner MFA, managed edge protection, named risk acceptance and final team
contributions still require their respective owners. In-app alerts do not send
external notifications. Same-host HMAC keys cannot protect against full host
compromise or database editing before capture. Daily backups run while awake;
sleep/restarts defer scheduling. See blue-team-runbook.md and risk-register.md.

## Evidence

- test-evidence/regression.xml
- test-evidence/campaign-live.json
- test-evidence/campaign-local.json
- railway-public-verification.json
- dependency-audit-current.json
- test-evidence/hosted-backup-verification.json
- test-evidence/shared-invite-verification.json (metadata only; no private token)
- test-evidence/source-manifest.json
