# Governance connection and assurance - working draft

Prepared October 27, 2026 for the synthetic course sandbox. This is a governance
mapping and evidence assessment, not a legal compliance certification. The team
must establish territorial scope, actual intended purpose, provider/deployer
roles and any relevant exceptions before deciding which legal duties apply.
RefundGuard's refund scenario alone does not establish an Annex III high-risk
classification. No real banking/customer-service deployment is approved here.

## EU AI Act mapping

| Governance topic | Connection | Evidence and remaining work |
| --- | --- | --- |
| AI literacy | Article 4 concerns staff/provider/deployer AI literacy. | User guide distinguishes local simulation, model proposals and actual execution. Team training and attendance records remain to be agreed. |
| Human-AI transparency | Article 50 addresses transparency for certain AI systems, including direct human interaction in its specified conditions. | UI identifies agent workflow and simulation; mock notices are generated from trusted outcomes. Review customer-facing disclosures for the actual use and applicable role before release. |
| Risk management | Article 9 is a high-risk-system requirement; used here as a governance reference rather than an asserted legal obligation. | Risk register, repeatable scenarios, remediation and residual-risk gates. Classification and owner acceptance remain open. |
| Records and oversight | High-risk-system provisions address logging (Article 12) and human oversight (Article 14). | Decision IDs, event/trace exports, supervisor denial and pause, policy review, restoration of approved versions. Independent log retention remains open. |
| Robustness/security | Article 15 concerns accuracy, robustness and cybersecurity of high-risk AI systems. | Boundary tests, replay/cap controls, MFA, restricted retrieval, patched dependencies, bounded execution and restore checks. A small passing test set is not certification. |

Sources are the European Commission's AI Act overview and AI Act Service Desk,
including the consolidated article pages. High-risk-system references above are
conditional mappings; they do not assert that RefundGuard is high-risk or that
all these articles currently apply to this educational implementation.

- https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-4
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-9
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-12
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14
- https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-15

## Assurance argument (Appendix F)

**Claim:** Within the tested synthetic cases, server controls constrain consequential
agent actions to delegated authority. This is a bounded claim, not invulnerability.

**Architecture:** Browser and model output are untrusted. Authentication, role and
customer scope are server-resolved. The model proposes; the refund tool checks
current caps, eligibility, supervisor state and agent authority under a transactional
ledger. Human-written policies cross a separate publication-review gate.

**Behavioral evidence:** The live campaign records actual recommendations, including
review of a forged $125 approval and handling of a retrieved malicious customer note.
The scenarios do not establish robustness against every phrasing or repeated attack.

**Execution evidence:** Regression tests force malformed/unsafe proposals and exercise
caps, concurrency, duplicate execution, customer isolation and in-flight revocation.
They establish sampled server behavior independently of live-model refusal.

**Evaluation containment:** Campaign databases, accounts, balances and mail are
synthetic/disposable. Live calls use a single separate $0.15 budget ledger and a
fixed provider endpoint. No other team's system was targeted. Raw traces are
retained in local evidence; no secrets or invitation links belong in the report.

**Residual risks:** See risk-register.md. Full host compromise, phished TOTP, broad
administrator access, absent independent log/backup storage, limited attack coverage
and unavailable exact CWEval integration limit the assurance claim.

**Proposed decision:** Continue supervised synthetic course demonstrations with
these limitations. Do not expand to real records, money or external email until
the responsible humans accept risks, complete independent operational controls,
repeat testing and document the actual legal classification and release conditions.
This is a recommendation; no board acceptance has been recorded.

## Contribution record

Emily Wallace requested the implementation/report and shared administrator signup
flow. Code, tests, evidence collection and report drafting were performed with
Codex assistance in this workspace. Silvia, Alex, Rina and Josephine appear in the
initial proposed team plan; their actual contributions and accepted responsibilities
must be supplied by the team. Do not attribute unverified work to them.
