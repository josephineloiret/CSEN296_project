# RefundGuard blue-team operations

Updated October 27, 2026 (America/Los_Angeles). Scope: synthetic course sandbox.

## Sign-in and invitations

Production administrators and supervisors must enroll an authenticator app before
accessing cases, exports, invitations or other privileged application functions.
Sign in, confirm your current password, enter the displayed setup key in a TOTP
app, and confirm its current code. Save the eight recovery codes privately; each
works once. Codes and enrollment secrets are never written to event logs.
Existing enabled MFA also applies in local mode. Enrollment revokes earlier
sessions. Codes are checked transactionally to prevent replay. This is TOTP,
not phishing-resistant passkey authentication; hosting and provider account MFA
must also be enabled by their owners.

**Team -> Shared admin link** creates a private link for up to four people, valid
for 48 hours. Each chooses a name, email and password; all four receive full
administrator rights. No identity/email ownership verification is performed.
Use individual email-bound member invitations when full admin access is not
necessary. Do not put the shared link in public channels, source files or reports.
An administrator can list links with `GET /api/team/links` and revoke one with
`POST /api/team/links/{id}/revoke` using their authenticated session and CSRF token.
Signup count and account creation commit together. Duplicate emails do not
consume a signup. A used, expired or revoked link cannot create another account.

A hosting operator may provision a link by setting TEAM_INVITE_TOKEN_HASH to the
SHA-256 of a random 32-byte token and TEAM_INVITE_EXPIRES to a fixed Unix timestamp,
then deploying. The raw token belongs only in the private URL fragment. Startup
uses INSERT OR IGNORE so restarts never reset usage or revocation. Delete the
provisioning variables with skip-deploys after verifying successful provisioning;
the database record remains. There is no public link-creation or password-reset
backdoor.

## Policy publication and rollback

Uploaded policy versions are pending and excluded from retrieval. A different
administrator or supervisor must read the source, verify provenance and publish
it in Knowledge base. Rejection keeps it out of retrieval. Publishing atomically
supersedes the active version of the same title. To roll back, another eligible
reviewer selects Restore this version on an approved inactive version. Versions,
reviewer, timestamps and content hashes remain recorded. Existing human-uploaded
policies migrate to pending; the built-in system policy remains active.

This review gate does not establish that an approved document is harmless. Two
compromised administrators can collude. Customer notes remain untrusted, and
server controls enforce caps, eligibility, recipients and authority independently.

## Detection and evidence

Assurance -> Security alerts groups relevant events into 15-minute windows.
Review login/MFA failures, denied access, throttling, policy changes, blocked
refunds, authority changes, workflow saturation/timeouts, budget exhaustion and
backup/audit-delivery failures. Acknowledge after investigation; another occurrence
reopens an acknowledged alert. Alerts are in-app; no email/SMS/PagerDuty recipient
has been configured.

Sanitized events are emitted as `refundguard.security` JSON in hosting stdout.
Optional AUDIT_DIRECTORY writes a mode-0600 JSONL file. Never expose that directory
as static files. Configure a hosting log drain to an independently administered
collector for off-host retention. Local files/SQLite are not immutable storage.

Export signed security evidence from Assurance. The HMAC signature detects changes
after capture using the separate evidence-key file; it is not an independently
verifiable public signature and does not detect database edits made before capture.
Retain snapshots and the trusted signing-key copy away from the app. Raw model
traces are in the separate full evidence export and can contain customer content;
use only synthetic data and redact before sharing.

```sh
.venv/bin/python manage.py verify-evidence --archive /secure/refundguard-security.json
```

## Availability and costs

One instance and one worker are supported. WORKFLOW_CONCURRENCY defaults to 2;
additional runs receive 429 with Retry-After instead of building a queue. The
120-second workflow deadline is cooperative and checked before consequential
steps; provider requests have bounded IO timeouts. This does not forcibly kill a
blocked native call. Uploads have a 200 KB body limit and a 10-second read deadline.
The container limits concurrent connections to 64 and keep-alive to five seconds.
A managed edge/WAF and upstream traffic controls are still operator tasks. Avoid
bypassing Railway's edge by exposing another public port. Keep existing $1/day
and $5/month provider accounting limits; the test campaign has its own shared
$0.15 ledger. These controls are not provider/hosting invoice guarantees.

## Backups and recovery

Production starts an encrypted online SQLite backup after 60 seconds, then daily
while the instance is awake, retaining seven archives under data/backups. Sleeping
or restarts defer this schedule. The independent backup-key is stored mode 0600
outside the archive; copy that key and encrypted archives to separate protected
storage. Same-volume backups alone do not survive volume loss or host compromise.
A hosting-level off-site schedule/retention policy remains to be configured.

Manual backup (never put a real key in the repository):

```sh
.venv/bin/python manage.py backup --output /secure/backup.rgbackup --key-file /separate-secure-store/backup-key
.venv/bin/python manage.py restore --archive /secure/backup.rgbackup --key-file /separate-secure-store/backup-key --destination /secure/restore-exercise
```

Restore refuses an existing destination. It verifies authenticated encryption,
SQLite integrity, foreign keys, record counts and ledger/balance consistency.
It revokes sessions/invitations and pauses agents before writing the restored DB.
The MFA/evidence sidecar keys are included inside the encrypted archive. If MFA
uses the server MFA_ENCRYPTION_KEY variable, preserve it separately; API and other
hosting variables are intentionally not backed up. Test sign-in, retrieval and a
synthetic case before a hosting operator promotes restored data to service.

## Incident response

| Severity | Trigger | Immediate action |
| --- | --- | --- |
| Critical | Unauthorized execution, cross-customer disclosure or hosting/key compromise | Pause agent authority; restrict public access at hosting; revoke compromised sessions/accounts/keys; preserve logs and ledger. |
| High | Lost admin invitation, suspicious policy publication, repeated MFA failures | Revoke the link, disable affected accounts, review policy versions, export evidence and investigate. |
| Medium | Saturation, denied requests, provider-budget exhaustion, backup failure | Review event context and cost ledger; tune limits or restore service after identifying cause. |

Assign a human incident lead and recorder. Record UTC timeline, category, affected
assets, decision IDs, model/config versions and evidence hashes. Separate model
attempts from tool decisions and actual ledger effects. Do not delete evidence or
retry a consequential action without checking the ledger. Contain first, remediate
and retest, restore into an isolated location, then obtain an owner decision to
resume authority. Record impact, notification decisions, recovery time and lessons.

Local MFA recovery is a trusted hosting operation, not a web endpoint:
`python manage.py reset-mfa --email ACCOUNT_EMAIL`. It requires an interactive
RESET confirmation, revokes all sessions and creates a high-severity event. Verify
the person's identity through an agreed independent process before using it.

## Continuous checks

The repository includes .github/workflows/security.yml for tests, credential-pattern
checks, dependency auditing, a Docker build and a Trivy container scan. Actions
are pinned to commits; the scanner version is pinned. CI starts once the team
publishes the repository. Docker is not installed on this workstation, so the
container scan has not been executed locally. The credential scan is heuristic,
not a complete secret detector or a scan of old Git history.
