# RefundGuard website user guide

[Download the PDF](RefundGuard_User_Guide.pdf)

REFUNDGUARD / WEBSITE USER GUIDE

RefundGuard

Website user guide

A practical guide to signing in, creating a support case, following a refund decision and using the shared guest demo.

November 12, 2026  |  Version 1.2

> Public guest demo
https://refundguard-production-11cb.up.railway.app
Email: guest@refundguard.example
Password: RefundGuard-Guest-2026!
These credentials are intentionally public. Sign in on the main website; no invitation is needed for guest access. The /guest/ address redirects to the same sign-in page.

Start here

1. Open the website. Use the main website link above and enter the public guest login. Individual team accounts use the same sign-in page.

2. Create a case. Choose an available synthetic purchase, enter a refund amount and reason, and select Create case.

3. Run the workflow. Open the case and select Run agent workflow. Read the decision and its reason.

4. Review the result. Use the Case mailbox, Agent activity and Settings to inspect messages and the mock balance.

> Shared demonstration workspace: all guest visitors can see the synthetic demo cases. Use a team or group prefix for your purchases and messages. Enter synthetic information only; money and email delivery are simulated.

| PAGE | IN THIS GUIDE |
| --- | --- |
| 02 | Sign in and understand your access |
| 03 | Create and process a refund case |
| 04 | Navigate the website and read case statuses |
| 05 | Use purchases, the inbox, knowledge and reports |
| 06 | Use invited staff and customer accounts |
| 07 | Resolve common sign-in and workflow problems |

REFUNDGUARD / 02


# 02. Sign in and understand access

Choose the guest demo for public access, or the team workspace if you have an individual invitation.

Public guest access

Open https://refundguard-production-11cb.up.railway.app. Enter guest@refundguard.example and RefundGuard-Guest-2026!, then select Sign in.

The guest demo uses a separate synthetic workspace and local simulation. You can create purchases and cases, run the workflow, view mock messages and balances, search demo documents, and export demo evidence. All visitors share this demo.

Guest access does not include team administration, password/MFA changes, policy publication, profile editing, supervisor decisions or the authority switch. The public guest password is fixed.

Guest sign-in. The public credentials are also displayed on this screen.

Individual accounts

The private team workspace is https://refundguard-production-11cb.up.railway.app. An Administrator creates your invitation under Team > Invite teammate. Open the private link once and choose a 15-128 character passphrase. Individual invitations normally expire after 48 hours and can be used once.

Hosted Supervisors and Administrators must complete authenticator setup or verification when prompted. Keep recovery codes private. The application generates invitation links but does not send real invitation emails.

Guest and individual team accounts use the same website address, with separate data and sessions. Sign out before switching accounts.

REFUNDGUARD / 03


# 03. Create and process a refund

Follow this example to submit a normal $75 damaged-item request.

1. Select New case. Open Overview or Cases. Choose an available synthetic purchase. A purchase can have only one case.

2. Add a purchase if needed. Open Settings > Add purchase. Choose a synthetic customer, enter a product such as GROUP-A-Headphones, amount 75.00 and purchase age 5 days. Select Create purchase.

3. Complete the case form. Choose your purchase, enter refund amount 75.00, choose Item damaged, and write a short description such as My headphones arrived damaged. Please refund the purchase.

4. Select Create case. The case opens with a unique case ID and New status. Save the case ID so you can find it later.

5. Select Run agent workflow. The application checks eligibility and records the result. An eligible $75 request normally becomes Approved.

6. Read the outcome. Inspect Decision reason, Case mailbox and Agent activity > Inspect evidence. Settings shows the updated synthetic customer balance.

An approved case shows the requested amount, decision reason and recorded workflow activity.

Customer accounts can submit their own requests but cannot run agents. An invited Member or other authorized staff account runs those requests.

REFUNDGUARD / 04


# 04. Navigate and read outcomes

The left navigation brings together cases, messages, documents and synthetic records.

| SCREEN | WHAT TO USE IT FOR |
| --- | --- |
| Overview | See case counts, recent cases, review holds, recent activity and weekly refund spend. |
| Cases | Create, search, filter and open cases. Read the decision, mailbox and workflow evidence. |
| Knowledge base | Read available policy/customer documents and search in the context of a case. |
| Inbox | Read incoming requests, outbound mock notices and drafts, organized by direction. |
| Assurance | Review outcomes and workflow events. Guest visitors can run isolated control checks and export guest evidence. |
| Settings | Add synthetic purchases and view mock customer balances. Other controls depend on your role. |
| Team | Available to individually invited staff. Administrators use it to invite people and manage account access. |

| STATUS | WHAT IT MEANS |
| --- | --- |
| New | The case was created and is waiting for staff or a guest user to run it. |
| Processing | The workflow is running. Wait rather than repeatedly selecting Run. |
| Approved | A mock refund was executed and recorded. |
| Needs review | The request needs review because of eligibility, a refund limit or a workflow/model interruption. |
| Blocked / Denied | A control prevented execution / the request was denied by a decision or supervisor. |

> Refund rules: autonomous refunds are limited to $100 per transaction and $500 per workspace per UTC calendar week, Monday to Monday. The request must match the purchase owner, not exceed the original purchase amount, be within 30 days, and use a covered reason: damaged, not received or wrong item. Other reasons require review.

REFUNDGUARD / 05


# 05. Use the everyday tools

Use the case ID to connect a request with its messages, documents and recorded result.

Add a fresh synthetic purchase

In the guest demo or as authorized staff, open Settings > Add purchase. Choose a customer, give the product a recognizable group-prefixed name, enter the original purchase amount and age, then select Create purchase. Return to New case to use it.

Read or add a case message

Open a case and look under Case mailbox. Incoming messages, outbound outcome notices and drafts are labeled separately. Select Add incoming email to record a synthetic follow-up with a subject and body. The workflow uses recent incoming messages when a case is eligible to run again.

Email is simulated: nothing is sent to an external mailbox. A draft is a proposed message, and an outbound notice is a recorded mock notification.

Find supporting documents

Open Knowledge base to read source titles, versions and customer scope. Under Test scoped retrieval, enter a real case ID and a question such as What is the refund policy?, then select Search documents. Results show the source and version.

The guest demo uses local lexical vector retrieval. Uploaded workspace policies in the individual-account workspace require a different authorized reviewer before they become active.

Inspect and export outcomes

Open Assurance to review Refund outcomes and the Audit timeline. Run control checks runs an isolated check suite and leaves customer balances unchanged. Its results describe those checks, not the outcome of every request.

In the guest demo, Export evidence downloads the synthetic guest report as JSON. In the private workspace, exports require Supervisor or Administrator access. Keep any report limited to the records your group needs.

Use the shared guest demo considerately

Guest cases and weekly spend are shared. Keep your group prefix in purchase names and messages. Do not enter personal information. If the demo reaches its weekly limit, the application holds additional refunds for review; ask the hosting team about the next demonstration window.

> Remember: a case being created does not authorize a refund. Read its final status, decision reason, recorded execution and mock balance.

REFUNDGUARD / 06


# 06. Individual customer and staff accounts

These features apply to invited accounts in the private workspace. They are not available through the public guest login.

| ROLE | AVAILABLE FEATURES |
| --- | --- |
| Customer | Submit and view your own cases; view your own purchases and non-draft messages. |
| Member | Run support workflows, inspect cases and messages, edit synthetic profiles and add purchases. |
| Supervisor | Member tools plus review decisions, document publication/review, authority controls and report exports. |
| Administrator | Supervisor tools plus invitations and account enable/disable controls. |

Join and manage your session

Accept the Administrator's individual invitation, create your own passphrase and sign in. If prompted, enroll or verify an authenticator. Use Settings to change your own password, and Sign out when finished. Password changes end other sessions.

Invite a teammate - Administrators

Open Team > Invite teammate. Enter the intended name and email, choose the appropriate role, and generate the invitation. Share that private link with the intended person. Avoid publishing shared Administrator links.

Review a case - Supervisors and Administrators

Open the case and use Approve review or Deny. Approval preserves the autonomous refund limits; it does not raise the $100 transaction cap or $500 weekly cap. An already-executed refund cannot be retroactively reversed through these controls.

Upload and review a policy

Open Knowledge base > Add document. Select Workspace policy, enter the title and content, and submit it. It appears as Awaiting review. A different Supervisor or Administrator opens it and chooses Approve and publish or Reject. The author cannot publish their own policy.

Pause or restore authority

Supervisors and Administrators use Settings > Pause agent authority to stop refund execution and outbound mock notices. Coordinate this workspace-wide control with other users. Restore authority when the pause is no longer needed.

Documents, profile edits and account controls affect the shared private workspace. Use only synthetic records assigned for the demonstration.

REFUNDGUARD / 07


# 07. Troubleshooting

Keep the case ID and the displayed error when asking the RefundGuard hosting team for help.

| WHAT YOU SEE | WHAT TO DO |
| --- | --- |
| Guest login does not work | Use the main website, guest@refundguard.example and the exact public password on page 1. The /guest/ address redirects to that same sign-in page. |
| Private invitation expired | Ask an Administrator for a fresh individual invitation. This does not affect the public guest login. |
| No unused purchase | Open Settings > Add purchase, create a fresh synthetic purchase and return to New case. |
| No Run agent workflow button | A Customer account cannot run agents. An Approved or Denied case also has no Run button. |
| Needs review / refund limit | Check the amount, original purchase age/reason and current weekly spend. Supervisor approval does not bypass the refund limits. |
| No acknowledgement on a held case | An over-limit request may be held before the normal mailbox steps. Use the recorded case status and reason. |
| Permission denied | The public guest has restricted access. Use an individually invited account for team administration, policy review or authority controls. |
| Validation error | Enter nonblank text and use an existing purchase/case ID. Browser refund amounts are in dollars. Single-line names and subjects must not contain line breaks. |
| Signed out / session error | Sign in again and use the same hostname. Individual sessions expire after 30 idle minutes or eight hours total. |
| Busy / too many requests | Wait for the interval shown by the app and avoid repeated retries. Ask the hosting team if the problem persists. |

Useful links

Public guest demo: https://refundguard-production-11cb.up.railway.app
Private team workspace: https://refundguard-production-11cb.up.railway.app
Project repository: https://github.com/josephineloiret/CSEN296_project

The hosted website is deployed separately from the repository. If a screen differs from this guide, give the hosting team the URL, your access type, case ID and a screenshot. Do not send individual passwords, invitation links, recovery codes or provider keys.

RefundGuard website user guide | Version 1.2 | November 12, 2026
