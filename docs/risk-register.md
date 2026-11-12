# RefundGuard risk register - October 27, 2026

Draft for team/governance acceptance. Owners below are proposed role owners, not
claims that individual students accepted responsibility. Ratings use likelihood
1-3 x impact 1-3: 1-2 Low, 3-4 Medium, 6-9 High. Ratings describe this synthetic
sandbox; real-money deployment requires a new impact assessment.

| ID | Threat and class mapping | Initial L x I | Treatment and evidence | Residual L x I | Proposed owner / acceptance |
| --- | --- | --- | --- | --- | --- |
| R1 | Prompt injection or forged supervisor authority; assignment LLM01/LLM03, ASI01/ASI02; MAESTRO 1/3/6 | 3 x 3 High | Independent caps, typed tools, eligibility/revocation checks; local forced-proposal tests and bounded live campaign. | 2 x 2 Medium: small attack sample; model mistakes remain possible. | Blue execution lead + Red test lead; synthetic-only use pending board acceptance. |
| R2 | Poisoned policy or persistent customer context; LLM05/LLM09, ASI06; MAESTRO 2 | 3 x 2 High | Pending policy versions require another reviewer; provenance, scoped retrieval, rollback; poisoned-note live scenario. | 2 x 2 Medium: colluding/compromised reviewers and novel poisoning remain. | Records/policy owner; review every publication. |
| R3 | Administrator credential or invitation compromise; LLM02, ASI03; MAESTRO 4/7 | 3 x 3 High | Encrypted TOTP seeds, one-use recovery, replay checks, required production privileged MFA, four-use 48h links, revocation. | 2 x 3 High: all-admin team links are bearer capabilities; no email verification; TOTP can be phished. | Workspace owner; explicitly accept shared-admin scope or use narrower invitations. |
| R4 | Evidence alteration or monitoring loss; ASI09; MAESTRO 5 | 3 x 2 High | Sanitized structured stdout, in-app grouped alerts, signed snapshots, file permissions. | 2 x 2 Medium: same-host admin can alter DB before signing or compromise keys; no independent collector configured. | Monitoring owner; off-host collection required before real data. |
| R5 | Resource exhaustion/provider spending; LLM06, ASI08; MAESTRO 4/6 | 3 x 2 High | Existing atomic provider budgets plus two workflow slots, cooperative deadlines, upload limits and connection limits. | 2 x 2 Medium: edge DDoS/WAF still external; same-instance availability. | Hosting owner; synthetic demo only; monitor quota and hosting bill. |
| R6 | Data loss or unsafe recovery; ASI08; MAESTRO 4/5 | 2 x 3 High | Authenticated encrypted online backups; isolated restore checks ledger/balances, revokes sessions/invitations, pauses authority. | 2 x 2 Medium: automatic backups share volume; sleeping defers schedule; off-host storage/key custody missing. | Recovery owner; perform independent restore drill and set RPO/RTO. |
| R7 | Vulnerable dependency/build supply chain; LLM04, ASI04; MAESTRO 3/4 | 2 x 3 High | Patched cryptography to 50.0.2 after scan; exact lock, dependency audit, pinned CI actions and scanner version. | 2 x 2 Medium: vulnerability scans are point-in-time; no local Docker/container scan or team CI run yet. | Build/release owner; publish private team repo and execute CI. |

R3 remains high after controls because the owner expressly requested full-admin
self-service links for teammates. Do not claim risk acceptance by the team or
Governance and Assurance Board until a human records it. No real customer data,
external mail delivery or real financial processing is approved by this report.

## Required risk-record fields

For each new finding, capture: title/scenario; red-team phase; assignment LLM and
ASI identifiers; MAESTRO layers; severity and rationale; safe reproduction;
preventive/detective controls; sanitized evidence and decision IDs; root cause;
likelihood x impact; treatment; functionality/security retest; residual risk;
owner; and threat-model update. This follows Appendix G of the supplied spec.
