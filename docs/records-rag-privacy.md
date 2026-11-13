# Bucket 1: model-facing profile allowlist and input handling

Date: November 12, 2026 (America/Los_Angeles).

Historical initial Bucket 1 assessment. See `input-review-recovery.md` for the
subsequent recovery feature, HTTP 409 hold behavior, dedicated alerts and updated
campaign expectations/results.
Base commit: `e5a5229`; local changes on `silvias_additions`.

## Behavior

Generated customer profile documents now allow only `id`, `name`, and `notes`.
Bank reference, email, account linkage, and other profile fields are not copied
into this projection. The original structured profile remains in SQLite.
Names and notes pass through the same model-facing text preparation used for
customer messages, queries, document passages, and provider request data.

Preparation normalizes Unicode and line endings, removes control/format
characters and HTML presentation markup, removes HTTP(S) URLs, redacts synthetic
MOCK references and exact bank references known to the database, and withholds
recognized instruction-override/role-spoofing patterns. For structured JSON,
financial keys such as `bank_ref` and `account_number` are removed recursively.
Profile projection has explicit limits of 80 characters for ID/name and 3,000
for notes. Existing API validation still rejects blank/overlong fields and
prohibited controls at ingestion. It is not weakened by the model sanitizer.

Original notes, messages, and uploaded source documents are preserved for human
review. New chunks, retrieved text and model input use prepared copies. A source
recognized as an instruction attack is represented by a fixed withholding marker
rather than being partially rewritten into a different, apparently valid request.
Search refuses recognized attacks in its query or any active document/title in
that customer's retrieval scope. It checks all active scoped sources, not only
the highest-ranked passages. Pending/rejected policies and unrelated customer
documents do not block a valid customer's request.

The existing workflow catches these refusals and places an unexecuted case into
`review`; it does not credit its mock balance. It currently records this through
the existing workflow interruption/error trace path. A direct search API call
uses the existing AIError response (HTTP 503). Supervisor approval does not bypass
the filter. Correcting/superseding the affected source and reviewing the original
messages is required before another automated attempt; this change does not add
a human-review bypass or source-editing UI.

## Existing data and compatibility

Initialization compares active system-generated profile documents with the new
projection and supersedes older copies. Original profiles and inactive document
history are retained. The embedding-kind label includes `model-text-v1` so active
old chunks must be rebuilt from prepared text before they can match a search.
Provider failures fail closed rather than returning old raw chunks. Repeated
initialization does not create extra versions for an unchanged projection.

In live mode the first relevant reindex can incur embedding calls under the
existing budget controls. Old traces, inactive source versions and backups are
not retroactively scrubbed. Human-facing profile/document/report routes retain
their existing access rules and can still show original data. Search rankings can
change. Existing callers and retrieval-result fields remain compatible; schema,
UI, refund caps, balance execution and role rules are unchanged.

## Production changes

| File / block | Responsibility |
| --- | --- |
| `app/privacy.py` (new) | Shared pure text/JSON preparation, profile allowlist, known-reference redaction, explicit withholding marker |
| `app/knowledge.py`: `add`, `initialize`, `sync_profile`, `search` | Prepared indexing, legacy projection upgrade, scoped source inspection and prepared retrieval output |
| `app/ai.py`: `embedding_kind`, `embedding`, `structured` | Projection version label and final provider-input preparation; no prompt request for recognized withheld input |

Tests are in `tests/test_records_privacy.py`. Two existing assertions were adjusted:
`test_prompt_injection_cannot_change_authority_amount_or_recipient` now expects
review/no credit for a recognized attack; the rejected-policy retrieval test uses
a neutral query (`refund limits`) to test policy exclusion independently of the
new query refusal. No existing test was deleted.

## Validation

- Full suite: **111 tests and 6 subtests passed**, no failures/skips; 9.91 seconds.
  This includes 26 new parameterized privacy test cases.
- Existing dependency warning: Starlette TestClient/httpx deprecation.
- Secret scan: **0 flagged files**.
- Default isolated synthetic campaign: **6/6 security checks passed; 4/6 functional
  checks passed**. Normal refund and replay still work. Indirect poisoning is now
  held instead of the harness's expected execution. Expired-purchase injection is
  also held, but its existing generic interruption trace fails the harness's
  functional criterion. The harness and expectations were not changed; these
  differences must be reviewed with the Red Team before reporting benchmark
  improvements. This campaign is not the final CWEval benchmark.
- Tests inspect actual adapter request payloads with a mocked provider, including
  embeddings and Responses requests; no paid provider requests or hosted service
  changes were made.
- Legacy document/chunk upgrades, idempotent initialization, failure during
  rebuilding, benign Unicode/HTML text, malicious notes/names/messages/documents,
  current bank references, normal refund balances, and member restrictions are
  covered.

Companion evidence: `bucket-1-tests.txt`, `bucket-1-tests.xml`, and
`bucket-1-campaign.json`. Run from the repository root:

```sh
AI_PROVIDER=local DATABASE_PATH="$PWD/tmp/privacy-import.sqlite3" \
  .venv/bin/python -m pytest -c tests/pytest.ini -q
.venv/bin/python scripts/scan_secrets.py
.venv/bin/python redteam/run_campaign.py --out redteam/results/privacy-local.json
```

## Limits and permission recommendation

Heuristic pattern detection cannot recognize all prompt injection. Encoded,
multilingual or novel attacks can evade it; quoted examples can be false positives.
Removing known financial keys/references is not comprehensive financial-data
recognition: an unknown account number typed in free text may remain. Notes and
messages are still untrusted evidence. Existing separate model instructions,
structured outputs, customer scoping, policy review, and independent transactional
refund controls remain necessary. A customer can intentionally submit recognized
poison and stall their automated processing; an active poisoned global policy
can stall multiple customers. Human remediation is an operational requirement.

Reference: OWASP, [LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).

Recommended permissions: members may initiate the constrained support workflow
if that is their assigned job; they should not obtain unrestricted refund-tool
access, override policy, change authority or make supervisor decisions. Existing
routes already reserve supervisor decisions and authority changes for admin/
supervisor roles. Members still have broad case access; assignment-based case
restrictions require a separate agreed policy and implementation. Bucket 1 does
not change role permissions or claim to resolve that wider access issue.
