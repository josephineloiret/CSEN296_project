# RefundGuard - Initial System User Guide

Historical proposal-stage snapshot. The implemented application is documented
in the [current user guide](user-guide.md), updated October 23, 2026.

**Version:** proposal draft, October 21, 2026.

This guide distinguishes the planned application from the control demo that is
implemented now. The browser workflows below are design commitments for team
review, not features currently available to users.

## Roles and data

- **Customer:** submits and views only their own synthetic support cases.
- **Administrator:** uploads/retrieves versioned refund policies and manages
  synthetic case/profile data through trusted operations.
- **Supervisor:** reviews escalated requests, records decisions, and revokes
  delegated agent authority.
- **Assigned agents:** read only the records needed for an assigned case and use
  explicitly permitted tools.
- **Red/Blue testers:** run approved synthetic scenarios and inspect sanitized
  evidence in the local sandbox.

Only synthetic identities, bank-account references, emails, and balances will be
used. A refund means crediting a mock account balance. No actual bank transfer or
external email is part of the intended course demo.

## Proposed policy

An autonomous refund must be positive, use whole cents, be at most $100, and not
push total autonomous refunds above $500 in a week. The initial implementation
uses one organization-wide budget and Monday-to-Sunday UTC weeks. This is an
explicit assumption pending instructor confirmation.

Policy eligibility checks, such as whether an order qualifies for a damaged-item
refund, will be defined in the team-authored refund policy. The current control
demo checks authority and financial limits only; it does not establish refund
eligibility from purchase records or retrieved policy documents.

An unresolved supervisor review or supervisor denial blocks autonomous execution.
Revocation blocks further consequential actions. The system cannot change its
own permissions or export unrelated customer records. Supervisor approval alone
does not override the autonomous tool's dollar caps.

## Planned customer workflow

1. Sign in as a synthetic customer and select **New refund case**.
2. Supply an order ID, requested amount, and reason. The proposed request format is:

   ```json
   {"order_id": "ORDER-DEMO-001", "amount_cents": 7500, "reason": "Item arrived damaged"}
   ```

3. The server attaches authenticated identity, creates a case ID, and assigns
   permitted agents. The Email agent records a mock acknowledgement.
4. The Records agent retrieves the relevant policy and authorized case/profile
   context. The Refunds agent proposes a decision with a reason and references.
5. An independent tool checks current authority, assignment, policy eligibility,
   supervisor state, transaction cap, remaining weekly budget, and duplicate
   execution before updating a mock balance.
6. View the approved, denied, or pending-review status and reason. The Email
   agent stores a mock decision notification; the Reporting agent includes the
   outcome in its report.

Customer requests and emails are case data. Instructions inside them do not
change application policies or authorize additional access.

## Planned administrator and supervisor workflow

1. Upload a refund policy with a version and effective date, then verify it can
   be retrieved with its source metadata.
2. Create/retrieve/update synthetic customer profiles and cases with access
   restrictions. Store only mock bank-account references.
3. Inspect pending reviews and record a supervisor decision through a trusted
   interface. A denied request cannot be reauthorized by an agent prompt.
4. Revoke an agent's authority and verify its next consequential tool action is
   blocked. Review attempted versus executed actions using decision IDs.
5. Review approved/denied/referral counts and reasons without exposing unrelated
   customer data.

Authentication, the browser views, RAG, and these admin interfaces remain to be
implemented. The current Python module's administration methods assume a trusted
caller and are not suitable for direct public exposure.

## What runs today

The original starter API simulates task planning and a canned hallucination
check. The new refund-control slice can be run without installing dependencies:

```sh
cd /Users/emilywallace/Documents/ChatGPT/AIGovProj/project
python3 -m unittest discover -s tests -v
python3 run_refund_demo.py
```

Expected demo results:

| Case | Expected result | Mock balance effect |
| --- | --- | --- |
| $75 request, active assigned agent | `processed / within_limits` | +$75 |
| $101 request | `blocked / transaction_limit` | $0 |
| $25 request after revocation | `blocked / authority_inactive` | $0 |

The final mock balance is 7,500 cents. Decision IDs vary each run. The database
is temporary and removed when the demo exits. The service itself supports a
persistent file when a trusted caller supplies a durable database path.

The tests additionally cover exact limits, aggregate weekly spend, week rollover,
supervisor denial, assignment, missing authority, repeat processing, concurrent
refunds, audit entries, and persistence of revocation after a service restart.

These are tool-level checks; they do not yet demonstrate adversarial robustness
of an LLM, an authenticated UI, or the complete multi-agent application.
