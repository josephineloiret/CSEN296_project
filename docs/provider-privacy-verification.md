# Bucket 3: end-to-end provider privacy verification

Date: November 12, 2026 (America/Los_Angeles).
Branch: `silvias_additions`. Starting checkpoint: pushed Bucket 2 commit `4ada65f`.
Status: included in the local Bucket 3 checkpoint on `silvias_additions`;
GitHub push pending verification. Not merged into main or deployed.

## Outcome

Added **19 transport-level cases** in `tests/test_provider_privacy.py`.
Focused suite: 19 passed in 2.90 seconds. Full suite: **164 tests plus 6 subtests
passed**, no failures/skips, in 17.29 seconds. Existing TestClient/httpx deprecation
warning remains. Secret scan: 0 flagged files. Diff whitespace check passed.

No production defect requiring a fix was demonstrated by these cases. This
bucket changes one test module and documentation only. No application behavior,
permissions, database schema, UI, refund execution, campaign expectation or
monitoring configuration changed.

## Coverage inventory: reuse rather than duplicate

| Requirement | Existing evidence from earlier buckets | Bucket 3 addition |
| --- | --- | --- |
| Profile field allowlist and legacy upgrade | `tests/test_records_privacy.py` checks profile source/chunks and observed embedding inputs | Serialized requests during legacy profile replacement |
| Known references in model-facing text | Existing tests inspect projections and intercepted adapter payloads | Seven parameterized source paths observed at actual HTTP serialization boundary |
| Cross-customer scope and traces | `tests/test_records_access.py` checks reciprocal scope, top-k filtering, lazy indexing, concurrency and provider payloads | Retained existing coverage; no duplicate customer-access suite |
| Recognized attacks and human recovery | `tests/test_records_privacy.py` and `tests/test_input_review.py` check holds, provenance, replacements and preserved controls | Serialized attack-source requests, policy poisoning, prior summary, reviewed-message retry and replay |
| Transport/budget error handling | Existing budget/deployment tests check reservations and provider errors | Recommendation timeout with sensitive source text; safe prepared wire payloads, no credit, safe new traces |

The new helper uses `httpx.MockTransport` at the HTTP transport boundary. The
production `Models.embedding`, `Models.structured`, `_post`, JSON serialization,
budget reservation/settlement and workflow code all execute. It does not replace
`_post` with a direct dictionary-returning mock. The transport captures decoded
serialized JSON requests in process and returns synthetic schema-compliant
responses. No network connection or paid provider call is made; no real API key
is used. Request headers/credentials are not persisted in the evidence artifacts.

## New test cases

| Cases | Path and property |
| ---: | --- |
| 7 | Known non-MOCK database reference placed separately in profile name, profile notes, initial case message, follow-up message, uploaded customer-document content, document title and search query. Serialized embedding/model requests and newly saved traces exclude it; the original bank field remains; valid refunds still credit exactly $75. |
| 1 | Long document with a reference spanning the 1,000-character chunk boundary: both the full value and a boundary-fragment disclosure are checked. Multiple embedding chunks are sent; original source text is retained. |
| 1 | Uploaded JSON with nested `bank_ref`, `routing_number` and `account_number` fields: financial values are removed while permitted factual text survives. Original structured document stays available for humans. |
| 5 | Recognized instruction attack in notes, initial message, follow-up, uploaded document content or title: raw attack never reaches serialized requests; the case enters review without ledger credit; no Refunds/Email/summary request follows the hold. |
| 1 | A human-published poisoned policy remains blocked by model-facing checks: publication does not make its attack text trusted instructions. |
| 1 | Recognized attack in a previously saved summary is caught before the planner sends any HTTP request. |
| 1 | Recommendation-stage transport timeout: request text is still private, no refund executes, new traces remain free of the known reference, and unknown provider cost remains accounted. |
| 1 | Audited message replacement: real serialized request flow uses the factual replacement, preserves the original message and executes once. Replaying the processed case sends no further provider requests or credit. |
| 1 | Older raw profile document containing the bank field is superseded before transport; inactive original document history remains retained. |

A fixed harmless withholding marker may appear in an embedding request. The
requirement is to exclude the original recognized attack text, not the marker.
Ordinary factual request text, numeric refund amount, reason, valid citations and
structured response behavior remain usable in the successful scenarios.

## Reproduce and evidence

From the repository root with the locked environment installed:

```sh
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/provider-privacy-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q tests/test_provider_privacy.py
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/provider-privacy-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q
.venv/bin/python scripts/scan_secrets.py
```

Companion evidence: `bucket-3-focused-tests.txt`, `bucket-3-focused-tests.xml`,
`bucket-3-tests.txt`, `bucket-3-tests.xml`. Pytest reports six subtests separately;
JUnit includes them in its case total.

## Limits and compatibility

- No PDF parser/upload feature was added. Documents in these tests are supported
  text/JSON knowledge documents; text extracted elsewhere follows those paths.
- Known database references and named financial JSON keys are tested. This is
  not comprehensive financial-data detection; unfamiliar account numbers in
  arbitrary free text may pass.
- Heuristic recognized-attack handling is tested, not universal injection
  prevention. Multilingual, encoded and novel attacks require further evaluation.
- Provider responses are synthetic. These tests cannot establish a real model's
  reasoning quality, adversarial robustness or actual provider retention behavior.
- Newly generated retrieval/workflow traces in these controlled scenarios are
  checked. Historical traces/backups and arbitrary malicious provider-output
  redaction are not assessed or retroactively changed.
- No new role restrictions, staff case assignment, customer-volume detector or
  broad monitoring work is included. Those remain separate decisions/buckets.
- No newer main commits were merged. Evidence applies to the checkpoint and local
  tests above. These checks support the Blue Team evidence package but are not
  the assigned CWEval framework integration or final benchmarking report.

Acceptance gate met: coverage inventory recorded, supported-field/transport gaps
covered, focused/full suites pass, no production change required, master log updated.
