# Implementation status — October 27, 2026

## Implemented and locally verified

- Responsive browser frontend served by FastAPI: authentication/setup, dashboard,
  cases and traces, knowledge base/retrieval, inbox, assurance, team and settings.
- Invite-only individual accounts; Argon2id hashing; persistent opaque sessions;
  HttpOnly/SameSite cookies; production Secure cookies; CSRF/origin/host checks;
  idle/absolute expiry; throttling; session revocation; local password recovery.
- Admin, supervisor, member and customer permissions enforced on the server.
- Five explicit specialist-agent classes, structured orchestration and aggregation,
  saved task outcomes, scoped tools and persistent traces.
- Versioned policy/customer documents and chunks; SQLite vector search using
  sqlite-vec; local lexical hash embeddings and an optional learned-embedding adapter.
- Synthetic purchases, profile edits, case intake/assignment, inbound/outbound/draft
  mailboxes, original-purchase eligibility, mock balances and outcome reports.
- Independent transaction/weekly caps, assignment checks, supervisor blocking,
  atomic ledger/balance updates, duplicate suppression and revocation checks.
- Bounded OpenAI Responses API integration with strict schemas, validated citations,
  model-error handling and no automatic fallback to approval.
- Isolated execution-control benchmark UI and authenticated evidence export.
- Locked dependency snapshot, local launcher, Dockerfile and setup/deployment guides.

## Verification limits

Local browser testing used an isolated database and disposable test account on
port 8001, leaving the real workspace administrator setup unclaimed. Sign-in,
case creation, five-agent processing, mock balance updates, evidence inspection
and in-app control checks were exercised in the browser.

The application is deployed on Railway with persistent storage and a server-only
OpenAI key. Live structured generation and 384-dimensional learned embeddings
passed a synthetic in-container smoke test. The network adapter and adversarial
model proposals also have mocked-response coverage. Local mode continues to use
lexical hash vectors. The owner received the one-time hosted setup key; choosing
the first administrator password and exercising a hosted authenticated workflow
remain owner steps. Temporary SSH access was explicitly approved and revoked.

All 77 automated tests plus six subtests and 27 current public HTTPS/security checks passed.
The updated locked dependencies passed a fresh pip-audit with no known vulnerabilities. This is a tested course-project
implementation, not an independently audited security product. TOTP MFA is now required for production privileged roles. SSO/passkeys,
self-service email recovery, background job queues and horizontal scaling remain
future work.

## Course work still requiring the team

- Agree on the working name/roles and create a shared GitHub repository.
- Confirm weekly budget semantics and acceptable mock/cloud integrations.
- Exercise complete live authenticated cases and evaluate semantic retrieval quality.
- Complete the class threat-model/red-team/risk/assurance templates with actual
  findings, evidence, mitigations, retests and owners.
- Confirm and run the assigned CWEval framework. A bounded six-scenario live
  campaign passed; expand it with repetitions and independent Red-team coverage.
  Project/Assurance checks are not a replacement for the assigned framework.
- Research and write the requested EU AI Act governance mapping, residual-risk
  acceptance/deployment decision and incident response plan.
- Complete progress/final reports, contributions, slides and cross-team testing.

## October 27 hardening and evidence

Production now enforces privileged TOTP MFA, independent policy publication/rollback,
sanitation and grouped alerts, signed event snapshots, workflow capacity/deadlines,
and encrypted online backups with safe isolated recovery. A four-use, 48-hour
shared administrator signup supports owner-requested self-selected email/passwords.
The updated Railway deployment is 38453f6c-cc3d-458a-9a57-00392b65f674.
The six-scenario live campaign used $0.003663 of locally accounted provider usage,
within a separate $0.15 ceiling. One iteration per scenario is limited evidence.

Report: ../output/pdf/RefundGuard_Security_Report.pdf. Editable source and reproducible
builder are in project/report. See blue-team-runbook.md, risk-register.md and
governance-assurance.md. Off-site retention, edge controls, actual contribution/owner
acceptance, team repository and CI/container execution remain open.
