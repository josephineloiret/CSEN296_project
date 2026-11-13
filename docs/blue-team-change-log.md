# Blue Team master change log

Owner: Silvia. Project: RefundGuard / CSEN 296.
Working branch: `silvias_additions`.
Starting code baseline: `e5a5229` (main fetched November 11, 2026).

This is the running record of the work completed in this collaboration, ordered
by implementation. Update it after every completed bucket. Distinguish completed
changes, recommendations, limitations and outstanding work. Do not describe a
change as merged, deployed or verified beyond the evidence recorded here.

## Current checkpoint status

Bucket 1 (`0c36520`) and Bucket 2 (`4ada65f`) were committed and verified pushed
to `origin/silvias_additions`. Local/remote heads matched at `4ada65f` with a clean
working tree before Bucket 3. Bucket 3 is included in the local checkpoint
commit containing this version of the log on `silvias_additions`; GitHub push
verification is recorded separately after success. No merge into main or deployment.
Earlier entries retain their status at the time recorded.

## 1. Repository preparation — update Silvia's branch

Completed November 11, 2026.

### What was in the codebase before our changes

- `silvias_additions` pointed to `e97b063`, 10 commits behind `main`, with no unique commits.
- The integration branch linked at the beginning of the collaboration had already been incorporated into `main`.

### What we changed

- Fast-forwarded local `silvias_additions` to `e5a5229` without rewriting history.
- Silvia restored GitHub write access and successfully pushed this branch update from her authenticated terminal.
- This incorporated existing teammates' changes; those changes are not credited here as Silvia's new implementation.

### Verification and impact

- Silvia's successful push output reported `e97b063..e5a5229 silvias_additions -> silvias_additions`.
- No changes to remote `main` or hosted deployment were made by this step.

## 2. Records Agent and secure RAG — baseline assessment

Completed November 11, 2026. Documentation-only segment.

### What was in the codebase before our changes

- A Records Agent derived the retrieval customer scope from the stored case ID.
- RAG used SQLite/sqlite-vec and returned active policies plus matching-customer documents.
- Existing tests covered some customer isolation, role restrictions and policy review/version behavior.
- Staff had broad access to customer profiles, documents, cases and raw reports/traces.
- Generated profile documents included `id`, `name`, `bank_ref`, and `notes`.
- The existing benchmark module explicitly identified itself as execution-control checks, not the final CWEval evaluation.

### What we changed

- Created `docs/records-rag-baseline.md` with the current access matrix, data flows, protections, coverage gaps and team policy questions.
- Established the regression baseline using Python 3.12.14 and the unchanged locked dependencies in a local ignored virtual environment.
- Created an updated architecture image reflecting the early cap gate, sequential specialists, execution controls and email safeguards. This diagram documents the existing architecture; it is not an architectural code change.

### Verification

- 85 tests plus 6 subtests passed; no failures/skips; 8.92 seconds.
- `pip check`: no broken requirements.
- One existing TestClient/httpx deprecation warning.

### Impact and limitations

- No production-code, test, schema, permission or deployment changes in this segment.
- Results describe the existing suite, not complete privacy assurance or a CWEval benchmark.

## 3. Records/RAG and Refund Agent inputs — field allowlist and sanitization

Completed locally November 12, 2026. Expanded Bucket 1.
Status at initial recording: implemented and tested; uncommitted, not pushed, not merged, not deployed.

### What was in the codebase before our changes

- `Knowledge.sync_profile()` copied `id`, `name`, `bank_ref`, and `notes` into generated profile documents.
- Those documents could enter embedding requests and retrieved evidence sent to the Refunds model; retrieval evidence was also saved in workflow traces.
- The API already validated field shapes, lengths, blank input and prohibited controls. Prompts treated customer/document data as untrusted, and trusted code independently enforced refund limits and authority.
- There was no shared model-facing field projection/text sanitizer at the RAG and provider boundaries.
- Existing profile copies/chunks could contain bank references.
- An existing local injection regression expected a capped legitimate refund to execute despite an obvious instruction attack.
- Mock refunds credited balances by customer ID; they did not transfer money using `bank_ref`.

### Goal

Minimize data sent to the model and add bounded preparation of notes/messages and
other model-facing text, while retaining original records for human review and
preserving the independent refund execution controls.

### What we changed

1. Added an explicit generated-profile allowlist: `id`, `name`, `notes`.
   Structured bank references, email and account linkage are excluded from this projection.
2. Added shared model-facing text preparation: Unicode/line-ending normalization,
   control/format character removal, HTML presentation removal, HTTP(S) URL
   removal, and redaction of synthetic MOCK references and exact bank references
   known to the database.
3. Added recursive financial-key removal for structured model-facing JSON.
4. Added heuristic recognition of instruction-override and role-spoofing patterns.
   Recognized content is withheld wholesale; affected automated workflows enter review.
5. Prepared document chunks, query text, retrieved content/titles, embeddings and
   structured provider input. Original notes, messages and uploaded source documents remain stored.
6. Superseded older active generated profile copies. Added the `model-text-v1`
   embedding label so old active chunks must be rebuilt before matching retrieval.
7. Added 26 privacy test cases and deliberately updated two existing tests to reflect
   the new behavior without deleting their coverage.

### Code blocks touched

| File | Blocks / responsibility |
| --- | --- |
| `app/privacy.py` — new | `model_text`, `model_payload`, `document_text`, `profile_document`, bank-reference collection, detection patterns and projection constants |
| `app/knowledge.py` | `add`, `initialize`, `sync_profile`, `search`: model-facing chunks, profile upgrade, scoped evidence inspection and prepared results |
| `app/ai.py` | `embedding_kind`, `embedding`, `structured`: versioned projection and final provider-boundary handling |
| `tests/test_records_privacy.py` — new | Synthetic privacy, legacy upgrade, provider-payload, workflow and member-permission regression tests |
| `tests/test_application.py` | Existing obvious-injection test now expects review/no ledger credit |
| `tests/test_hardening.py` | Rejected-policy test now searches with neutral `refund limits`, separating exclusion testing from attack-query refusal |
| `docs/records-rag-privacy.md` — new | Implementation, validation, operating behavior, compatibility limits and permission recommendation |

The Refunds Agent class and orchestrator workflow implementation were not edited.
Their inputs are protected through the RAG and model-adapter boundaries.

### Verification

- Full suite: **111 tests plus 6 subtests passed**, no failures/skips; 9.91 seconds.
- Secret scan: **0 flagged files**.
- Isolated default campaign: **6/6 security checks passed; 4/6 functional checks passed**.
- Normal refund and replay behavior remain functional.
- Two campaign expectations differ: indirect poisoning is now held rather than
  executed; expired-purchase injection is also held, but the existing generic
  interruption trace fails the harness's functional criterion.
- Provider payloads were inspected with mocks. No paid model calls or hosted-service tests.
- Evidence: `bucket-1-tests.txt`, `bucket-1-tests.xml`, `bucket-1-campaign.json`;
  detailed assessment: `docs/records-rag-privacy.md`.

### Impact on teammates and other code

- Existing function signatures and retrieval response fields are preserved.
- No UI, database-schema, refund-cap, balance-execution, authentication or role-permission changes.
- Search ranking can change. First live reindex can incur budgeted embedding calls.
- Recognized suspicious input now halts automated processing. Supervisor approval
  alone does not bypass the filter; source remediation/human review is necessary.
- The Red Team must review the two campaign expectation differences. Its harness was not changed.
- Existing workflow handling records these refusals as interruptions/errors;
  direct search uses the existing AIError HTTP 503 response.

### Limits and remaining work

- Heuristic sanitization cannot guarantee prevention of all prompt injection;
  obfuscated, multilingual and novel attacks remain possible, and quoted examples
  may cause false positives. Independent controls remain essential.
- Unknown financial numbers in free text may remain; known-reference removal is
  not comprehensive sensitive-data detection.
- Historical raw traces, inactive documents and backups are not retroactively scrubbed.
- Active poison can stall customer processing; a poisoned active global policy
  can affect multiple customers.
- This change does not complete dedicated data-access testing or CWEval benchmarking.

## 4. Bucket 1 close-out — audited recovery, hold events and campaign expectations

Completed locally November 12, 2026. Uncommitted; not pushed, merged or deployed.
This entry supersedes the initial Bucket 1 operational limitations and campaign
status where explicitly noted; the original results remain preserved above.

### What was in the codebase before this close-out

- Recognized input holds used the generic AIError/workflow-error path, causing an
  expired-purchase campaign scenario to fail functional scoring despite no refund.
- The poisoned-document campaign still expected execution of an otherwise eligible
  refund; this contradicted Bucket 1's deliberate review-hold policy.
- Profile corrections and customer-document supersession were available, but no
  supported model-facing correction existed for an incoming message. Supervisor
  approval alone could not clear it; the raw case document also retained the attack.
- General event logging, throttling, concurrency controls and security alerts
  existed, but there was no distinct customer-linked input-hold alert.

### What we changed

- Introduced typed `InputReview` holds, separate from provider/system errors.
- Added a supervisor/admin-only message-review API and case-mailbox form. A human
  saves a factual model-facing replacement plus reason; originals remain intact.
- Bound each review to case/message IDs and a source hash, with reviewer, timestamp,
  current/historical revisions, atomic SQLite audit insertion and sanitized log emission.
- Applied the review to both incoming message input and generated case-document
  projection. Invalidated affected chunks for reindexing. Reviews do not execute
  refunds and do not change amounts, reasons, eligibility or supervisor decisions.
- Rejected review writes during processing/after execution, unauthorized callers,
  unknown/wrong-case/outbound messages and recognized unsafe replacements.
- Added `workflow.input_review_required` events/alerts identifying initiator,
  customer ID, case and run; recorded human review separately as `input.reviewed`.
- Direct blocked searches now return HTTP 409, not a misleading provider-outage 503.
- Updated only the poisoned-document campaign expectation to require an audited
  review hold with zero ledger entries/balance. Genuine errors still fail scoring.
- Added 12 recovery/integration test cases, including mocked live-provider payload
  inspection and preserved denial/revocation/expiry/cap/replay protections.

### Exact code areas

- New `app/input_review.py`: review persistence, provenance and model-facing overlays.
- `app/schemas.py`: `MessageReviewInput`.
- `app/main.py`: review endpoint, staff case-detail metadata, InputReview handler.
- `app/knowledge.py`: reviewed case-document projection for indexing/source checks.
- `app/workflow.py`: reviewed incoming text; hold/error classification and attribution.
- `app/ai.py`: typed hold at final provider boundary.
- `app/monitoring.py`: register the hold in existing security alerts.
- `app/static/app.js`: mailbox review form/button and original/reviewed display.
- `redteam/run_campaign.py`: explicit poisoned-document expectation and output label.
- New `tests/test_input_review.py`; `docs/input-review-recovery.md`.

### Validation and evidence

- **123 tests plus 6 subtests passed**, no failures/skips; 12.04 seconds.
- Default synthetic campaign: **6/6 functional, 6/6 security, 6/6 joint** under the
  explicitly documented expectation change. No claim of improved live-model robustness.
- Secret scan: **0 flagged files**. Browser JavaScript syntax check passed.
- Browser-tested the held-message → factual review → workflow retry → single mock
  refund flow. Both original and reviewed text remain visible. No hosted changes.
- Evidence: `bucket-1-closeout-tests.txt`, `bucket-1-closeout-tests.xml`,
  `bucket-1-closeout-campaign.json`, `bucket-1-review-recovery.png`.
- Detailed guide: `docs/input-review-recovery.md`.

### Compatibility and remaining boundaries

- This is a separately recorded close-out integration across API/workflow/UI;
  it expands beyond the first three production files to make review actionable.
- No database schema migration, role assignment changes, RefundService changes or
  refund-cap changes. Review uses the existing metadata table. Staff case-detail
  messages gain optional review metadata; original fields remain intact.
- Reviewed replacement text still passes sanitization. Changed source text or a
  new attack requires another review. No blanket sanitizer bypass was introduced.
- Campaign expectation changes should be reviewed by the Red Team before merging.
- Heuristic limitations, historical-data retention and broad member case visibility
  remain as recorded in the initial Bucket 1 entry.

### Proposed separate monitoring bucket — not implemented

The user proposed detecting overload and suspicious customer refund activity.
The new input-hold event belongs to Bucket 1 because it records this protection.
Broader detection remains a separate observability bucket: customer-level request
counts, initiator/customer attribution, repeated holds/denials, duplicate attempts,
workload saturation and configurable alert thresholds. Use pseudonymous IDs and
sanitized metadata rather than bank references or raw messages. Existing case
creation logs actor/case/order and can be joined to the customer; volume/fraud
aggregation is not yet implemented. No recurring automation or external alert
recipient was configured.

## 5. Bucket 2 — dedicated Records/RAG data-access tests

Completed locally November 12, 2026. Base: pushed Bucket 1 commit `0c36520`.
Status: included in this local Bucket 2 checkpoint; GitHub push pending verification.
Not merged or deployed.

### What was in the codebase before our changes

- Records derived customer scope from the stored case and RAG applied a scoped SQL filter.
- Prior tests covered some isolation and policy transitions, but did not provide
  focused positive/negative evidence for top-k filtering, provider-input scope,
  deferred embedding, concurrent customers and complete source/text exclusion.
- Staff had broad case access; customers could not directly call RAG search.

### What we changed

- Added `tests/test_records_access.py` with 22 cases covering reciprocal customer
  isolation; a foreign nearest neighbor excluded before LIMIT; query scope
  manipulation; internal/HTTP unknown and forged case IDs; nonstaff denial;
  allowed staff search; client-supplied scope rejection; policy publication,
  rejection, supersession and rollback; customer-document versions; lazy indexing;
  concurrent scopes; provider payloads and workflow traces.
- Every positive retrieval scenario requires authorized data, avoiding a vacuous
  pass from denying everything. Synthetic nonfinancial markers distinguish access
  filtering from Bucket 1 bank-reference redaction.
- Added `docs/records-access-tests.md` with reproduction, outcomes and limitations.
- Updated this master log and carried forward the verified Bucket 1 push status.

### Code blocks touched and compatibility

- New test module and documentation only. **No production-code changes.**
- Existing test helpers are reused; no broad test-fixture refactor.
- No permission redesign, UI/API interface changes, schema migration, refund
  changes, monitoring expansion or Red Team campaign changes.
- No defect requiring a production fix was demonstrated by these scenarios.
- Bucket 2 checks the current role policy; it does not establish that broad member
  access is the desired least-privilege policy or add human case assignment.

### Verification and evidence

- Focused suite: **22 passed**, 3.24 seconds.
- Full suite: **145 tests plus 6 subtests passed**, no failures/skips; 15.28 seconds.
- Existing TestClient/httpx deprecation warning remains.
- Secret scan: **0 flagged files**; diff whitespace check passed.
- Evidence: `bucket-2-focused-tests.txt`, `bucket-2-focused-tests.xml`,
  `bucket-2-tests.txt`, `bucket-2-tests.xml`.
- Temporary synthetic databases and mocked provider transport; no paid model
  calls or hosted-service changes. No claim of final CWEval evaluation.

### Remaining work

Verify the GitHub push of this checkpoint before the next implementation bucket.
Assignment-based permissions, broad customer-activity monitoring and CWEval
integration remain separate decisions/work. Newer main commits are not merged
or assessed by this checkpoint.

## 6. Bucket 3 — end-to-end provider privacy verification

Completed locally November 12, 2026. Base: pushed Bucket 2 commit `4ada65f`.
Status: included in this local Bucket 3 checkpoint; GitHub push pending verification.
Not merged or deployed.

### What was in the codebase before our changes

- Buckets 1/2 already tested profile projection, recognized attacks, review
  recovery, customer isolation and intercepted model-adapter payloads.
- Transport/budget tests existed but did not cover the combined privacy boundary
  for all supported free-text paths through real request serialization.
- Structured bank fields were already excluded from generated profile documents;
  other text paths still needed end-to-end verification, not another removal change.

### What we changed

- Added `tests/test_provider_privacy.py` with 19 transport-level cases.
- Ran real adapters, JSON serialization and budget accounting against an
  in-process HTTP mock transport; no actual provider/network calls.
- Covered known references in names, notes, initial/follow-up messages, document
  content/titles and queries; nested financial JSON; chunk-boundary fragments;
  recognized attacks in supported sources; published policy poisoning; prior
  summary input; timeouts; audited message recovery/replay; legacy profile replacement.
- Required useful factual data and correct refund behavior in allowed scenarios,
  not only absence of forbidden values. Confirmed harmless withholding markers
  may be embedded while original recognized attack text stays out.
- Added `docs/provider-privacy-verification.md` with a map of prior coverage,
  new gaps addressed, reproduction commands and precise limitations.

### Files touched / compatibility

- New `tests/test_provider_privacy.py` and `docs/provider-privacy-verification.md`;
  updated this master log. **No production-code changes.**
- No new application dependencies, schema, UI/API, role, refund, campaign or
  monitoring changes. Existing helper fixtures are reused without refactoring.
- No production defect requiring a fix was demonstrated by these scenarios.

### Verification and evidence

- Focused suite: **19 passed**, 2.90 seconds.
- Full suite: **164 tests plus 6 subtests passed**, no failures/skips; 17.29 seconds.
- Existing TestClient/httpx deprecation warning remains.
- Secret scan: **0 flagged files**; diff whitespace check passed.
- Evidence: `bucket-3-focused-tests.txt`, `bucket-3-focused-tests.xml`,
  `bucket-3-tests.txt`, `bucket-3-tests.xml`.
- Synthetic records, temporary databases, in-process transport and fake provider
  key only. No paid requests, hosted-service changes or claim of final CWEval evaluation.

### Limits and remaining work

Unknown financial numbers and unrecognized/obfuscated injections remain limitations;
this is regression evidence for the covered paths, not comprehensive detection.
PDF upload/parsing and arbitrary model-output redaction were not introduced.
Verify the GitHub push of this checkpoint before the next bucket. Broader monitoring, an
agreed staff access redesign and CWEval integration/report remain separate work.

## Decisions proposed but not implemented

- Keep members able to initiate a constrained refund workflow when support
  processing is their job; retain supervisor/admin-only decisions and authority changes.
- Consider assignment-based staff access and narrower visibility of raw traces,
  profiles and knowledge documents in separate agreed buckets.
- No new permission policy has been implemented in this collaboration.

## Format for subsequent entries

For each completed bucket, append:

1. Component and concrete change; date and status.
2. What was in the codebase before our changes.
3. Goal and resulting behavior.
4. Exact files/functions changed.
5. Tests/evidence and results, including failures and limitations.
6. Compatibility impact and coordination needed.
7. Commit/PR/merge/deployment references when they actually exist.
