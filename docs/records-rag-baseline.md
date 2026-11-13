# Records Agent and secure RAG: Segment 1 baseline

Assessment date: November 11, 2026 (America/Los_Angeles).
Baseline: `e5a52296dad3d2d20977ad2f715531aa23b9ca43` on `silvias_additions`, matching the fetched `main`.
Owner: Silvia, Blue Team. Scope: baseline verification and access-rule documentation.

## Outcome and boundaries

The existing regression suite passed: **85 tests and 6 subtests**, no failures or skips, in 8.92 seconds. The JUnit exporter counts the six subtests separately and therefore reports 91 tests. Python 3.12.14 was used with the unchanged `requirements/lock.txt`; `pip check` found no broken requirements.

One dependency warning remains: FastAPI's TestClient reports that its httpx integration is deprecated in favor of httpx2. No dependencies were changed to address this warning.

This segment changes documentation only. No application logic, schemas, tests, dependencies, UI, deployment settings, or refund behavior were modified. Dependencies were installed in the ignored local `.venv`. Tests use synthetic fixtures, temporary databases, and mocked provider transports where applicable. The import-time application database was redirected to a separate local baseline directory. No hosted service was tested and no live LLM campaign was run.

Passing the existing suite establishes a regression baseline; it does not establish complete privacy protection or satisfy the final CWEval requirement.

## Reproducing the baseline

Run from the repository root after installing the locked dependencies into a Python 3.12 virtual environment:

```sh
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/baseline-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q \
  --junitxml=tmp/segment-1-baseline-tests.xml
.venv/bin/python -m pip check
```

The saved run used the same pytest options with an absolute scratch database path and absolute evidence paths outside the checkout. Evidence delivered with this assessment:

- `segment-1-baseline-tests.txt`: original pytest output and warning.
- `segment-1-baseline-tests.xml`: machine-readable test results.

| Existing test module | Tests passed |
| --- | ---: |
| `tests/test_application.py` | 40 |
| `tests/test_deployment_and_budget.py` | 13 |
| `tests/test_hardening.py` | 17 |
| `tests/test_refunds.py` | 15, plus 6 subtests |

## Current access matrix

This table describes implemented behavior, not a proposed least-privilege policy. Staff means member, supervisor, or administrator. Authentication, mutation CSRF checks, and applicable MFA restrictions apply before route access. Production administrators and supervisors must complete MFA; accounts with MFA enabled must satisfy it in local mode as well.

| Resource or operation | Anonymous | Customer | Member | Supervisor / administrator | Enforcement |
| --- | --- | --- | --- | --- | --- |
| Read cases and orders | Denied | Own customer scope | Across customers | Across customers | `main.py`, `Store.case`, order ownership SQL |
| Read profiles and balances | Denied | Own profile | All profiles | All profiles | `/api/profiles` SQL |
| Update profile name / notes | Denied | Denied | Any existing profile | Any existing profile | Staff role gate; validated profile ID |
| List knowledge documents | Denied | Denied | All documents, including content and review metadata | Same | `/api/knowledge`; staff role gate |
| Search knowledge for a case | Denied | Denied, including own case | Any existing case; results scoped to that case's customer plus policies | Same | Staff gate, `get_case`, customer-scoped retrieval |
| Upload customer documents or submit policies | Denied | Denied | Denied | Allowed; customer documents require an existing customer | Upload role gate and scope checks |
| Publish / reject / roll back policies | Denied | Denied | Denied | Allowed for a different author/reviewer | API role gate; `Knowledge.review` author check |
| Run the agent workflow | Denied | Denied | Allowed for existing cases | Allowed | Staff role gate and workflow controls |
| Read global mock inbox / reports | Denied | Denied | Allowed, including raw traces in reports | Allowed | Staff role gate |
| Download full evidence export | Denied | Denied | Denied at export route | Allowed | Administrator/supervisor gate |
| Read customer case detail | Denied | Own case; excludes draft messages, traces, ledger detail, summary, run ID, creator ID | Full case detail | Full case detail | `get_case` and response shaping |

Important distinction: blocking members from the export endpoint does not prevent them from reading report data through `/api/reports`. Similarly, pending policies are excluded from RAG retrieval but remain visible to staff in the knowledge document listing. These are current authorization choices, not demonstrated bypasses.

### Internal Records Agent boundary

`RecordsAgent.retrieve(case_id, query)` is a trusted in-process method, not an authenticated HTTP endpoint. It accepts no caller identity. It looks up the case, derives `customer_id` from stored data, rejects an unknown case with `AIError`, and calls `Knowledge.search` with the derived scope. It relies on the caller to establish permission to use that case.

The workflow checks caller case access and runs Intake assignment validation before Records retrieval. The staff search route independently derives the customer from `get_case`; it calls Knowledge directly. Neither path exposes a client-selectable retrieval customer ID.

`Knowledge.search` is also an internal method, not an authorization boundary for arbitrary callers. Its SQL filters by active document, embedding kind, and `(policy OR matching customer)` before returning the nearest chunks. Default result limit is five. SQL permits any active policy; approval is enforced by document lifecycle rules that keep pending and rejected policies inactive, rather than a separate `review_status` predicate in the search query.

Scope is per customer, not per case. Other active case documents for the same customer can be retrieved. No staff-to-customer assignment restriction exists in the inspected access paths.

## Data flow and privacy observations

1. Profile indexing includes `id`, `name`, `bank_ref`, and `notes`. It does not directly index the profile's email field in `sync_profile`.
2. Case documents include the case ID and submitted request fields, including customer message text.
3. Retrieval returns document IDs, titles, versions, kind, chunk content, chunk number, and distance.
4. In live mode, embedding input is sent to the provider. Retrieved evidence is also supplied to the Refunds model. Local mode computes hash vectors and does not call the provider.
5. The workflow saves retrieved context in Records traces. Staff can read traces via case detail and reports; administrator/supervisor exports include them. Sanitized security evidence is a separate export and excludes raw customer/model content.
6. Retrieval initialization can create missing customer profile documents across profiles locally; scoped reindexing and search restrict the customer documents selected for that search. This distinction warrants a focused provider-payload test.
7. Policy review reduces unreviewed-policy exposure but does not make approved text trustworthy instructions. Execution controls remain independent.

Including a bank reference in retrieval is a confirmed data flow, not yet a finding that violates an agreed field policy. The specification requires financial information to be stored and retrieved for issuing mock refunds; that does not establish that the LLM needs the field. Confirm the minimal context required before removing it.

## Existing evidence and remaining coverage

| Property | Existing coverage | Segment 2 addition |
| --- | --- | --- |
| Anonymous/customer access restrictions | `test_private_api_and_static_security_headers`, `test_customer_cannot_access_another_case_or_admin_controls`, `test_anonymous_requests_cannot_reach_model_tools` | Explicit role-by-operation matrix, including allowed staff actions |
| Cross-customer retrieval isolation | `test_rag_never_returns_unrelated_customer_and_versions_sources` excludes another customer's document ID | Two-customer fixtures with content markers; prove own data is returned and other data is absent under normal and adversarial queries |
| Policy lifecycle | Policy review, rejection, rollback and version tests in `test_hardening.py` | Assert inactive/superseded content never appears in retrieval after each transition |
| Case identifier handling | Input-shape rejection and customer case access tests | Valid-shaped unknown case; direct RecordsAgent unknown-case path; confirm denied searches do not invoke embeddings |
| Data minimization | No dedicated field-level retrieval/provider-payload test identified | Inspect synthetic embedding and model inputs for agreed allowed/forbidden fields using mocked transports |
| Scope propagation | Workflow and isolation tests provide partial coverage | Direct agent test proving scope comes from stored case despite instructions embedded in the query |
| Evidence privacy | Sanitized security evidence tests; role gates for reports/exports | Check raw trace versus sanitized export content and intended role visibility explicitly |

These are coverage gaps from code/test inspection. They are not confirmed exploitable vulnerabilities, and this segment adds no new adversarial tests or exploit claims.

## Team decisions to record before behavior changes

- May every staff member access every customer, or should access depend on assignment? Existing UI/workflows assume broad staff access.
- Which fields belong in model context? In particular, should mock bank references remain available only to trusted execution code?
- Is customer-wide case history intended retrieval context, or should retrieval narrow further to the current case?
- Should members see raw traces and full document content, including pending policy versions, or do those require a narrower role?

These decisions do not block Segment 2 tests documenting current controls. Any test of a proposed stricter policy should be labeled as a requirement decision rather than treated as an existing implementation regression.

## Mapping to the course specification

| Specification area | Relevance to Silvia's deliverables |
| --- | --- |
| Pages 1–2: assigned cases, unrelated-record restrictions, customer records and RAG workflows | Define privacy boundaries while preserving legitimate retrieval and profile/case operations |
| Pages 3–4: orchestration and specialized document/records capabilities | Verify the existing Records specialist and retrieval integration; do not rewrite other specialists |
| Page 5: threat modeling, red teaming and evidence | Add reproducible Blue Team access tests and contribute findings to the shared threat model |
| Page 6, section 8; page 13, Appendix H: system benchmarking | Evaluate functional and security outcomes separately, then joint success and retests |
| Page 7: report deliverables | Preserve test evidence and implementation details for the final benchmarking/report package |

The current `app/benchmarks.py` explicitly identifies itself as execution-boundary regression checks, not the final CWEval benchmark. Segment 4 must establish the actual CWEval framework integration and any course-specific expectations before presenting results as CWEval. Local deterministic checks and mocked model tests cannot establish live-model robustness.

## Next segment and completion gate

Segment 2 should add a focused Records/RAG access test module using temporary databases and synthetic markers. Reuse existing fixtures where practical without broadly refactoring the suite. Begin with positive scoped retrieval, cross-customer exclusion, stored-case scope derivation, unknown cases, and policy lifecycle filtering. Capture field exposure with mocked provider input; defer any field-removal change until the desired policy is recorded.

Completion gate: focused tests pass; full suite remains green; any failure is reported with reproduction and expected behavior; no unrelated module changes. Segment 3 should implement only fixes supported by these tests or an explicit team policy decision.
