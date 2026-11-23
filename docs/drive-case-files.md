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
does not enter the shared Knowledge index, external embeddings, or automated
refund, email, and reporting workflows. The staff-facing Records Agent search
uses local lexical ranking in either model mode. Sanitization redacts known
synthetic bank references and rejects recognized unsafe instructions.

This is a snapshot import. Moving, editing, deleting, or revoking access to the
original in Drive does not change an existing RefundGuard snapshot. Use a new
Drive file for a corrected source. The imported text is subject to the app
database and backup retention policies.

References: [Download Drive files](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
and [Drive folder sharing](https://developers.google.com/workspace/drive/api/guides/manage-sharing).
