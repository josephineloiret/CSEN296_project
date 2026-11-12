# RefundGuard user guide

Current implementation, October 23, 2026. See the setup guide for account creation.

## Overview and case intake

The dashboard shows case counts, approvals, review holds, recent events, and
organization-wide weekly spend. Use **New case** to select an existing synthetic
purchase, request an amount and choose a reason. The server resolves the purchase
owner and assigns the Refunds agent; the browser cannot supply an agent identity
or authorization flags. Each purchase may have only one refund case, preventing
split/repeated requests against the same order.

Three demo purchases are available to staff: Maya ($75, recent), Sam ($125,
recent), and Jordan ($40, expired). New accounts receive an additional own
synthetic $75 purchase. Staff can add more purchases under **Settings**, including
purchase age for eligibility tests. Nothing charges a real card or bank account.

## Run a case

Open a case and select **Run agent workflow**. Staff roles can run cases; customer
accounts submit requests and view their own outcomes. The workflow:

1. Orchestrator constructs a bounded plan (LLM-based when live mode is enabled).
2. Intake validates the case assignment and records a mock acknowledgement.
3. Records retrieves policy and customer-scoped document chunks from the vector database.
4. Refunds proposes approve, deny or review, including source references.
5. Independent execution controls verify current authority, assignment, supervisor
   state, trusted purchase eligibility, dollar caps and prior execution.
6. Email stores an outcome notice addressed to the verified customer. Live-mode
   model drafts remain separate and are not automatically sent externally.
7. Reporting records the actual outcome; the orchestrator aggregates a summary.

Inspect **Agent activity → Inspect evidence** for sources, recommendations,
decision IDs, executed effects and errors. Traces record operational results,
not private model chain-of-thought. A case stores its outcome and persistent task
history across sessions/restarts.

## Policy and outcomes

Trusted eligibility rules require a verified original purchase, an amount no
greater than the purchase total, a purchase within 30 days, and a covered reason
(damaged, not received or wrong item). Other reasons go to human review.

Autonomous refunds have a $100 transaction cap and a shared $500 weekly cap,
using Monday 00:00 UTC calendar weeks. That week definition and the
organization-wide budget scope remain instructor-confirmation assumptions.
Supervisor approval does not bypass these caps. The mock balance credit and
refund ledger update execute atomically; repeating a case cannot credit it twice.

- **New:** submitted, ready for staff processing.
- **Processing:** a workflow holds the case; another run cannot claim it.
- **Approved:** the mock credit actually executed.
- **Needs review:** eligibility/model uncertainty or an interrupted unexecuted workflow.
- **Blocked:** an independent execution control rejected the action.
- **Denied:** a supervisor or the decision workflow denied the request.

Supervisors/admins can record a review decision. A previously executed refund
cannot be retroactively denied/reversed through this interface. A crashed
processing claim can be retried after five minutes; ledger idempotency still
protects against another credit.

## Knowledge base

Supervisors/admins add text or Markdown documents by paste or text-file import.
Select a workspace policy or a particular customer's document scope. The app
chunks, embeds and versions each source; reusing the title/type/customer creates
a new active version and supersedes the old version. Files are treated as text,
not executed. Trusted dollar/eligibility controls are application rules: changing
a document cannot change those controls.

Profile edits are reindexed. Case submissions are indexed as customer documents.
Use **Test scoped retrieval** with an authorized case ID to inspect returned
chunks, versions and source IDs. Customer-scoped documents cannot be retrieved
for another customer's case. In local mode vectors represent lexical token
similarity; live mode uses learned semantic embeddings.

## Inbox and records

The inbox organizes inbound messages, outbound mock notices, and drafts by
labeled direction. Open a case to add a follow-up inbound message. Subsequent
workflow evaluation includes recent inbound messages, always as untrusted data.
Staff can update customer names/notes under Settings; bank references and account
balances are controlled mock fields. Customer accounts can view only their own
profile, orders, cases, and non-draft messages.

## Authority, assurance and team access

**Settings → Pause agent authority** stops refunds and outbound mock email.
The execution tools check the current persisted authority state, including if a
pause occurs during an in-flight model request. Restore authority to resume
processing eligible cases. This control is reserved for supervisors/admins.

**Assurance → Run control checks** uses disposable data to test seven execution
boundaries. It reports functional and joint pass rates and preserves results.
It does not attack the live LLM or change customer balances. The assigned CWEval
benchmark and live-model adversarial campaign remain separate course work.
Supervisors/admins can export the recorded evidence as JSON.

**Team → Invite teammate** is administrator-only. Use a Member account for normal
support/testing, Supervisor for control management, and Customer for isolation
tests. Each person chooses their own password. The administrator can disable an
account to revoke its sessions; the last active administrator cannot be disabled.
Use **Settings** to change your password or sign out.


## October 27 security update

Production administrators and supervisors must enroll/verify an authenticator.
Save the recovery codes privately. Team -> Shared admin link lets four teammates
choose their own name, email and password within 48 hours; anyone holding it gets
full administrator access. Use individual invitations for narrower roles.
Policy uploads now await a different administrator/supervisor's review in Knowledge
base. Assurance shows grouped security alerts and signed security evidence export.
See [blue-team operations](blue-team-runbook.md) for recovery and limitations.
