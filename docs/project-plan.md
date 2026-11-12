# Assignment summary and implementation plan

This is the original October 21 planning snapshot. For the application now
implemented, see [current implementation status](implementation-status.md) and
the [current user guide](user-guide.md). The assignment requirements below still apply.

Source: supplied `CSEN-296-ProjectSpec.pdf`, COEN 296, Fall 2026.

## What the assignment is asking for

Build a browser-based enterprise customer support agent for synthetic refunds,
then produce evidence showing how it behaves under attacks and whether its
independent controls enforce the organization's delegated authority. The project
combines application engineering, threat modeling, red teaming, remediation,
functional/security benchmarking, and governance assurance.

The system needs an orchestrator and five specialist agents: Intake, Email,
Records, Refunds, and Reporting. It must support case submission/assignment;
mock email drafting, sending, receiving and organization; case/profile storage,
retrieval and updates; refund submission, decision and mock processing; and
approved/denied/reason reports. It also needs short-term and persistent memory,
LLM-based decomposition/routing/aggregation, tool integrations, a browser UI,
and vector-database-supported retrieval for policies and customer records.

Autonomous refunds are capped at $100 per transaction and $500 per week. Agents
must not access/export unrelated records, grant themselves privileges, override
supervisors, or continue consequential actions after revocation. Refunds update
synthetic account balances rather than moving real money.

Red and Blue work from one shared system definition and contribute to one threat
model. Blue builds and monitors controls; Red develops and runs reproducible
adversarial tests and challenges fixes. At the end, the team presents evidence
and a proposed deployment decision to the Governance and Assurance Board.

## Deliverables and points

| Submission | Points | Required contents |
| --- | --- | --- |
| Proposal | 25 | Application name; initial architecture diagram; initial system user guide; starter GitHub URL; team responsibilities |
| Progress report | 25 | Updated project GitHub repo and architecture; final user guide; red-team suite outline; threat-model outline; interim individual contributions |
| Final report | 100 | Final repo and architecture; final red-team suite and threat model; risk report; benchmarking results; governance connection; assurance audit report; final individual contributions |
| Presentation | 50 | Slides and project demo, including team-specific activity |

Total: **200 points**. One submission per team in CAMINO; individual scaling may
apply. Due dates and submission details are in CAMINO, not this PDF.

The later team-specific activity runs after reports and before presentations:
test other teams' applications with the authorized suite, detect/log attacks
against your own application, and preserve evidence. Successful outcomes can
earn bonuses.

## What later reports must establish

- **Threat model:** use the class template, assignment LLM and ASI risk categories,
  and the seven MAESTRO layers. Iterate over trust boundaries, plausible attacks,
  guardrails, attack chains, and findings.
- **Red-team suite:** use the class template and evaluate model, implementation,
  system, and runtime/human-agent behavior. Plan, evaluate, reproduce, remediate,
  retest, and monitor.
- **Risk report:** map each finding to risk categories and MAESTRO layers;
  include severity/rationale, safe reproduction, control assessment, evidence,
  root cause, likelihood/impact, treatment, retest criteria and model updates.
- **Benchmarking:** use the assigned CWEval framework and Appendix H format.
  Record functional and security outcomes separately; joint success requires
  both. Repeat both after fixes. Local control tests alone are not a completed
  CWEval integration or benchmarking report.
- **Governance connection:** prepare the requested EU AI Act mapping, risk
  register with owners, and incident response plan covering classification,
  severity, detection, kill switch, containment and recovery. Substantive legal
  applicability and article mapping still need authoritative research.
- **Assurance audit:** connect categories, architecture-specific threats,
  evidence, residual risks, owners and acceptance/monitoring decisions. Distinguish
  an agent's attempted action from a tool's authorization decision and the action
  that actually executed. Verify the evaluation remains inside its sandbox.

The PDF's threat-model/red-team text refers to LLM risks as Appendix A and ASI
risks as Appendix B; the actual tables are **Appendix B (LLM)** and **Appendix C
(ASI)**. Use the tables and the class materials to avoid the cross-reference
error. Reporting appears in the minimum requirements even though Section 3.3
does not give it a separate detailed row.

## Starter assessment

Inspected source: `/Users/emilywallace/Documents/src/coen296-main/project`.
The folder has no Git metadata. A working copy now lives in this workspace's
`project/`, preserving the requested starter layout.

| Area | What existed in the starter | Work remaining |
| --- | --- | --- |
| API | FastAPI `/tasks`, `/logs`, `/tests/rt-01` | Browser UI, identity and access controls, refund/case APIs |
| Agent | Fixed three-step planner, simulated decisions | Real LLM decomposition, routing, aggregation and five agents |
| Retrieval | Keyword lookup in three canned strings | Vector DB, embeddings, provenance and scoped retrieval |
| Refunds | No case, ledger, or balance workflow | Connect first control slice to authorized workflow and eligibility checks |
| Email / records / reports | No specialist implementations | Mock integrations, CRUD, profile access and outcome reports |
| State / controls | JSON log file; no permission enforcement | Session/task memory, trusted control paths and broader audit coverage |
| Red teaming | Canned keyword-based hallucination check | Actual agent attacks, control outcomes, reproducible evidence and retests |
| Deliverable materials | Placeholder red-team/threat-model/report folders | Use class templates and populate final evidence package |

The starter's demo calls `/health`, which the original API does not implement,
and reports HTTP request completion as `ok` without checking status codes. Treat
its output as a walkthrough, not proof that the application passed. The README
also mentions `demo.py` and a red-team template not present in this starter.

## Work completed in this workspace

- Drafted the five proposal sections and an initial user guide using the five
  team members provided; name and roles remain proposed.
- Copied the course `project/` without changing the original source.
- Added `app/refunds.py`: a SQLite-backed mock refund tool with integer cents,
  current authority/assignment checks, supervisor blocking, caps, atomic balance
  updates, duplicate suppression, and decision IDs/audit records.
- Added a dependency-free synthetic demo and 15 passing unit tests, including
  concurrent spending against the shared weekly budget.

This is the first trusted execution slice, not a complete course application.
The old FastAPI dependencies have not been installed or validated; the original
API remains separate from the new tool. No LLM/API credentials were read or used.

## Next milestones, in order

1. **Finalize and submit the proposal.** Confirm member names/roles, working name,
   diagram and user guide; check CAMINO format/deadline. Clarify weekly budget
   scope/window and cloud/mock integration expectations with the instructor.
2. **Establish a shared development baseline.** Create a team GitHub repo; record
   the starter source; choose a supported Python environment and verify dependency
   installation. Obtain the class threat-model, red-team, risk and assurance
   templates and the assigned CWEval setup. Arrange an LLM API subscription/key
   and team spending limit; the spec says this is outside the starter setup.
3. **Deliver one end-to-end happy path.** Add authenticated synthetic identities,
   browser case form, trusted intake/assignment, synthetic profiles and purchase
   records, and a mock inbox/outbox. Connect the orchestrator and all five agents
   so a legitimate $75 case can produce an eligibility decision, tool execution,
   updated balance, notification and report entry.
4. **Add actual retrieval and policy eligibility.** Choose the LLM/embedding/vector
   providers; ingest versioned policies and synthetic customer documents. Enforce
   retrieval scope before returning documents, preserve provenance, and handle
   case/profile updates without stale unauthorized context. Record the selected
   inter-agent protocol and short-term/persistent memory design.
5. **Run the adversarial loop.** Add indirect prompt injection via emails and RAG,
   cross-customer access/export attempts, unauthorized tool use, forged supervisor
   approval, revocation, duplicate/concurrent refunds and memory poisoning.
   Preserve attempted actions, independent control decisions and actual state
   effects, then fix and retest. Ensure mock sending is gated after revocation too.
6. **Finish progress-report materials.** Finalize the user guide, architecture,
   threat-model and test-suite outlines, updated repo and contribution records.
7. **Build the final evidence package.** Complete functional/security benchmarks,
   risks and owners, governance mapping, incident response and audit report.
   Prepare slides, deployment conditions and cross-team test/demo evidence.

## Initial test backlog

| Scenario | Expected independent control result | Current evidence |
| --- | --- | --- |
| Valid assigned $100 case | Credit once; record a decision | Unit test passes |
| $100.01 request | Block; no balance change | Unit test passes |
| Spend above $500 across customers/agents | Block; no overspend | Unit test passes |
| Six concurrent $100 requests | At most five execute | Unit test passes |
| Duplicate case execution | One ledger entry and one credit | Unit test passes |
| Revoked agent or supervisor denial | No further execution | Unit tests pass at refund boundary |
| Cross-customer document access | Filter/deny before retrieval | Not implemented |
| Instructions embedded in email/policy | No policy/permission change | Not implemented |
| Agent tries to grant itself authority | No permitted route/tool | Trusted API/tool exposure not implemented |
| Corrupted memory or forged inter-agent message | Reject unauthorized actions; log evidence | Not implemented |

Do not count the currently passing tool tests as proof that the LLM never tries
an unsafe action. Later behavioral and execution-boundary tests must record both.
