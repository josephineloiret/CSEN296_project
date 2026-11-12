# RefundGuard — initial application threat model

This is an implementation-specific starting point. Transfer findings into the
class template and complete residual-risk ratings, owners and evidence links.

## Assets and boundaries

Assets: team credentials/sessions, invitation tokens, synthetic profiles and bank
references, policies/vectors, refund authority, weekly budget, mock balances,
customer messages, model inputs/outputs and audit evidence.

Boundaries: browser → authenticated API; customer → own records; staff → shared
support sandbox; LLM proposals → trusted tools; retrieved documents → instruction
context; supervisor controls → delegated agent execution; application → optional
model provider; evaluation suite → disposable data.

## Initial mapping

| MAESTRO layer | Attack scenario | Existing treatment | Evidence / remaining work |
| --- | --- | --- | --- |
| 1 Foundation models | Prompt injection, fabricated approval/citations | Strict outputs, constrained plan, citation validation, independent execution gate | Mocked adversarial model tests; live LLM tests pending |
| 2 Data operations | Cross-customer retrieval, poisoned policy/case content | Server-resolved customer scope, parameterized SQL, versioned sources, active-version filter | Customer isolation and vector-scope tests; poisoning campaign pending |
| 3 Agent frameworks | Unsafe routing or agent self-authorization | Five narrow specialist interfaces; fixed permitted dependencies; no model permission tool | Malformed-plan and authority-boundary tests |
| 4 Deployment and infrastructure | Session theft, credential guessing, insecure exposure | Argon2id, hashed sessions, host/origin/CSRF checks, throttling, production HTTPS and secure cookies | Auth regression tests; recorded public HTTPS checks passed; see current report for retest |
| 5 Evaluation and observability | Model recommendation mistaken for execution; hidden late failure | Separate recommendation/control traces, decision IDs, persisted ledger, post-failure reconciliation | Late-model-failure test; sanitized signed event snapshots and hosting stdout added; independent off-host retention still required |
| 6 Security and compliance | Revocation ignored, supervisor bypass, budget races | Execution-time authority/eligibility/supervisor checks, serialized ledger updates, unique case/order IDs | Concurrency, duplicate, denial and in-flight revocation tests |
| 7 Agent ecosystem / use case | Forged customer identity, exfiltration recipient, refund splitting | Authenticated ownership, one case per purchase, trusted recipient resolution, local-only mock delivery | Assignment/recipient tests; authorized cross-team testing pending |

## Initial residual risks / decisions

- Local simulation cannot establish a model's robustness. Enable a funded API
  account and collect attempted-versus-executed evidence for real LLM attacks.
- Authorized supervisors can upload policy evidence; text cannot change trusted
  caps, but model behavior still requires poisoning tests and human review.
- The team administrator controls invitations and the local DB administrator
  controls recovery/data. Protect those accounts and the data volume.
- Production privileged roles now require TOTP MFA; SSO/passkeys and an independent security audit remain future work.
- SQLite and in-process orchestration target one small-team instance. A background
  queue, distributed controls and stronger audit storage would be needed at scale.
- Calendar week/organization-wide budget semantics are provisional.

Risk owners, severity/rationale, EU AI Act mapping and final deployment conditions
must be agreed by the team, supported by the course materials and authoritative research.


## October 27 trust-boundary updates

Policy prose -> active retrieval now crosses an independent human publication gate.
Legacy human-uploaded policies migrate to pending; the system baseline stays active.
Password -> privileged production session now crosses a TOTP/recovery verification
gate. Shared admin invitation -> account creation is a deliberately broad bearer
capability requested by the owner: four uses, 48 hours, atomic signup accounting,
revocable, and followed by mandatory MFA. Email ownership is not verified.
Workflow -> execution includes capacity and cooperative deadline checks.
Backups are authenticated/encrypted, and restored state revokes invitations/sessions
and pauses authority. Same-host keys and all-admin team membership remain residual
risks. Human owners must approve the risk register and classification in the report.
