# Bucket 2: Records/RAG dedicated data-access tests

Date: November 12, 2026 (America/Los_Angeles).
Branch: `silvias_additions`. Base commit: `0c36520` (Bucket 1 checkpoint).
Status: included in the local Bucket 2 checkpoint on `silvias_additions`;
GitHub push pending verification. Not merged into main or deployed.

## Result and scope

Added **22 test cases** in `tests/test_records_access.py`. All passed in the
focused run (3.24 seconds). The full suite passed **145 tests plus 6 subtests**,
with no failures/skips, in 15.28 seconds. The existing TestClient/httpx deprecation
warning remains. Secret scan: 0 flagged files. `git diff --check` passed.

This bucket changes tests and documentation only. No production-code change was
needed to pass the selected access-boundary scenarios. Existing role rules,
RecordsAgent interfaces, database schema, UI, provider adapter, workflow,
monitoring, refund execution and Red Team campaign are unchanged.

## Before this bucket

Bucket 1 established model-facing privacy handling and an audited review recovery
flow. Existing tests covered some role/customer restrictions and policy lifecycle
behavior, but did not provide a dedicated suite demonstrating positive retrieval
alongside exclusion of foreign content/metadata, filtering before top-k selection,
lazy-embedding scope, concurrent scopes and provider-input scope in one place.

## Added tests and evidence

| Boundary | Concrete verification |
| --- | --- |
| Authorized retrieval, both customers | RecordsAgent returns the customer's own identifiable evidence and source ID; the other customer's marker/title/source ID is absent. Empty responses cannot pass the positive checks. |
| Filter before top-k | Synthetic vectors make the unrelated document the globally closest match. A scoped search with limit 1 must still return the legitimate customer's document. Actual SQLite vector-distance ranking and SQL retrieval execute; only the query embedding is controlled. |
| Query cannot select identity | A query naming Sam and his evidence is run against Maya's case. Records derives Maya's stored customer scope and excludes Sam's content. |
| Internal unknown/forged cases | Unknown, malformed, empty and SQL-shaped IDs fail before the internal search helper or provider transport is invoked. |
| HTTP case validation | Valid-shaped unknown case returns 404; malformed/SQL-shaped cases return 422, without retrieval or embedding calls. |
| Nonstaff caller restrictions | Anonymous/customer search is denied for own, another customer's and unknown case IDs before retrieval/provider calls. |
| Existing staff permissions | Member, supervisor and admin can search a case under the current policy; returned results remain scoped to its customer. This deliberately does not invent assignment restrictions. |
| Client-supplied scope | Supplying an extra `customer_id` in a search request is rejected before retrieval. |
| Policy lifecycle | Pending/rejected text is absent; a different reviewer can publish; a pending replacement leaves the current version visible; publication excludes the superseded text; rollback restores the prior source/version and excludes the later text. |
| Customer-document versions | Superseding Maya's document excludes its old text without deactivating Sam's same-title document. Each customer's results remain isolated. |
| Lazy indexing | A Maya search indexes her deferred content without sending Sam's deferred document or new private notes to embedding calls. Sam's deferred document remains unindexed. |
| Concurrent scopes | Six interleaved searches across two workers return each customer's own sources without the other customer's marker. |
| Workflow integration | Mocked live-provider mode captures embedding/model request payloads and saved retrieval traces: Maya's evidence is present, Sam's text/source ID is absent, and a legitimate refund still executes. |

Fixtures use temporary databases, existing authenticated test helpers and synthetic
markers that are not bank references. This prevents Bucket 1 redaction from
making cross-customer exclusion appear to pass. No paid requests, live model
robustness evaluation, hosted-app calls or real customer data were used.

## Reproduce

From the repository root with the locked dependencies installed:

```sh
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/access-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q tests/test_records_access.py
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/access-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q
.venv/bin/python scripts/scan_secrets.py
```

Saved evidence: `bucket-2-focused-tests.txt`, `bucket-2-focused-tests.xml`,
`bucket-2-tests.txt`, `bucket-2-tests.xml`. JUnit counts the six subtests as
separate cases; the pytest console summary distinguishes them.

## Compatibility and limits

- New test module imports the same workspace/account helpers used by existing
  hardening tests; no shared fixture refactor was introduced.
- The tests establish the selected scenarios on Bucket 1 commit `0c36520` plus
  these local additions. They do not assess newer, unmerged commits on main.
- RecordsAgent is still a trusted internal helper without a user-identity argument.
  HTTP/workflow callers remain responsible for caller authorization. Its scope is
  customer-wide, not restricted to a single case's documents.
- Members still have broad staff access across cases; this bucket verifies scoped
  results for the selected case, not staff-to-case assignment policy.
- Two-worker interleaving is a regression check, not load testing or proof against
  every possible concurrency failure.
- Policy approval relies on the established lifecycle that controls active flags;
  this is not a database-tampering test or a claim that approved text is harmless.
- These tests are evidence for the course's Records Agent, secure RAG and data-access
  deliverables. They are not the final CWEval framework integration or report.

Bucket 2's acceptance gate is met: focused and full suites pass, positive allowed
behavior is preserved, tested unauthorized data paths are excluded, production
code is unchanged, and the master change log is updated. New permission design,
broader monitoring and CWEval integration remain separate work.
