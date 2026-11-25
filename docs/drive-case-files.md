# Google Drive case files

RefundGuard can import a PDF from a private Google Drive folder and let authorized
staff find passages in the case view. The original stays in Drive. RefundGuard
stores sanitized, searchable text and local lexical vectors in SQLite.

## Set up the demo

1. In a team-controlled Google Cloud project, enable the Google Drive API and
   provision a dedicated service account. Grant it Viewer access to the private
   project folder. Use synthetic customer data and share only this folder with the
   service account. Leave the folder private.
2. Set `DRIVE_CASE_FILES_FOLDER_ID` to the folder ID from its URL. Set
   `DRIVE_CASE_FILES_SERVICE_ACCOUNT_JSON` to the service account credentials JSON
   as a private environment variable or deployment secret. Keep the key outside
   the repository and out of shared messages.
3. Launch RefundGuard with the locked dependencies. Enable both settings to show
   the import form. Existing indexed files remain available to authorized staff
   if import is disabled later.

## Demo the workflow

1. Place a synthetic PDF with selectable text directly in the configured folder.
   PDFs may be up to 2 MiB and 20 pages. Subfolders, shortcuts, encrypted PDFs,
   scans requiring OCR, and other formats are outside this implementation.
2. Open a case as a supervisor or admin. In **Case files**, select an active
   member to assign, then paste the Google Drive PDF link or file ID and choose
   **Import PDF**. The same file can be imported once and linked to one case.
   A retry on the same case returns the existing record.
3. Sign in as the assigned member and search **Case files** in the case view.
   Compare with an unassigned member and a different case. Supervisors and
   admins can review the file without a member assignment. Clearing or changing
   the assignment revokes the previous member's app access.
4. To resolve a rejected import, check the file and folder in Drive, then retry.
   RefundGuard records successful imports and assignment changes as audit events
   with identifiers. It keeps raw file content and Drive links out of audit logs.

## Scope and retention

Case file assignments apply only to this document feature. Existing customer
records remain governed by the app's current role permissions. Case file text
does not enter the shared Knowledge index or external embeddings. Search uses
local lexical ranking in either model mode. Sanitization redacts known
synthetic bank references and rejects recognized unsafe instructions.

### Case files in the automated workflow

When a staff member runs a case, the Records Agent adds up to three case-file
passages to the refund evidence, if that person may read the case files
(admin, supervisor, or the assigned member). An unassigned member's run uses
the normal evidence only.

- **Untrusted evidence.** Passages are labeled `case_file`. They cannot grant
  eligibility, change the amount or caps, or authorize a refund; application
  controls still decide those. The model may cite a passage by its document ID.
- **Recheck at run time.** Every stored passage for the case is rechecked
  before the model is called. A recognized instruction holds the case for human
  review, even if it was imported before the patterns changed.
- **Amounts.** A dollar figure in a PDF does not become an amount the model
  may state. A recommendation quoting one is held for review.
- **Traces.** Workflow traces are visible to all staff, so they record only the
  passage's document ID, title and chunk number, never its text.
- **Provider.** In OpenAI mode the selected passages, after redaction, are
  sent to the model provider with the rest of the evidence. In local mode no
  model is called and the recommendation cites the case file by ID.
- **Residual risk.** A model rationale can paraphrase passage text. Rationales
  are visible to staff and appear in the sent decision notice (finding RT-F04).
  Detection is pattern-based and misses reworded or other-language instructions
  (finding RT-F01); eligibility and caps remain the real control.

This is a snapshot import. Moving, editing, deleting, or revoking access to the
original in Drive does not change an existing RefundGuard snapshot. Use a new
Drive file for a corrected source. The imported text is subject to the app
database and backup retention policies.

References: [Download Drive files](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
and [Drive folder sharing](https://developers.google.com/workspace/drive/api/guides/manage-sharing).

## Public guest workspace

Other teams test through the public guest login. The guest workspace never
receives the Drive folder ID or service-account key, and it cannot reach the
Drive import or assignment routes. Instead, a guest can upload a PDF (up to the
app's 200 KB request limit, at most five per case) to a guest case. The upload
goes through the same text extraction, sanitization and instruction checks as
a Drive import, assigns the guest to the case files, and is used as evidence
when the case runs. A rejected PDF records a `records.case_file_rejected`
event with a hash of the text, never the text itself.

By default the guest workspace runs local simulation, so a guest upload tests
the import checks and the run-time recheck only. With `GUEST_LIVE_MODEL=true`
(see the Railway guide), passages that pass those checks reach the live model
as evidence, within the guest budget, so testers can see how it responds. All guests share one account and one
workspace, so uploads are visible to other testers.
