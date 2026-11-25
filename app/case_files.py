"""Case-specific evidence from Drive PDFs, for staff search and the Records agent.

Passages reach the automated workflow only when the staff member running it may
read the case files. They are untrusted evidence: they cannot grant eligibility,
change amounts or caps, or authorize a refund. Those stay with application code.
"""
import hashlib
from uuid import uuid4

from sqlite_vec import serialize_float32

from app.ai import InputReview, local_embeddings
from app.drive_files import MAX_BYTES, DriveFileError, pdf_text, source_id
from app.privacy import WITHHELD, bank_references, disguised_instruction, model_text
from app.store import stamp

REVIEWERS = ('admin', 'supervisor')
WORKFLOW_PASSAGES = 3
MAX_UPLOADS_PER_CASE = 5


class CaseFiles:
    def __init__(self, store, drive):
        self.store = store
        self.drive = drive

    def _assignment(self, db, case_id):
        return db.execute(
            'SELECT a.user_id FROM rg_case_file_assignments a JOIN rg_users u ON u.id=a.user_id '
            "WHERE a.case_id=? AND u.active=1 AND u.role='member'", (case_id,),
        ).fetchone()

    def _allowed(self, db, case_id, actor):
        if actor['role'] in REVIEWERS:
            return True
        row = self._assignment(db, case_id)
        return actor['role'] == 'member' and row is not None and row['user_id'] == actor['id']

    def details(self, case_id, actor):
        if self.store.settings.guest_workspace:
            # All public testers share one guest account: show the files and the upload form.
            files = self.store.all('SELECT id,title,imported_at FROM rg_case_files WHERE case_id=? '
                                   'ORDER BY imported_at,id', (case_id,))
            return {'files': files, 'can_upload': True}
        with self.store.connect() as db:
            db.execute('BEGIN')
            if not self._allowed(db, case_id, actor):
                return None
            files = db.execute('SELECT id,title,imported_at FROM rg_case_files WHERE case_id=? ORDER BY imported_at,id',
                               (case_id,)).fetchall()
            assignment = self._assignment(db, case_id)
        if actor['role'] in REVIEWERS:
            enabled = self.drive.settings.drive_import_enabled
            if enabled or files or assignment:
                return {'files': [dict(file) for file in files], 'can_import': enabled,
                        'assigned_user_id': assignment['user_id'] if assignment else None}
        elif files:
            return {'files': [dict(file) for file in files]}
        return None

    def assign(self, case_id, user_id, actor):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if user_id is None:
                db.execute('DELETE FROM rg_case_file_assignments WHERE case_id=?', (case_id,))
            else:
                if not db.execute("SELECT id FROM rg_users WHERE id=? AND active=1 AND role='member'",
                                  (user_id,)).fetchone():
                    raise DriveFileError('Select an active staff member.')
                db.execute('INSERT INTO rg_case_file_assignments(case_id,user_id) VALUES(?,?) '
                           'ON CONFLICT(case_id) DO UPDATE SET user_id=excluded.user_id', (case_id, user_id))
        self.store.event(actor['id'], 'records.case_files_assignment', case_id, target=user_id)

    def import_pdf(self, case_id, source, actor):
        file_id = source_id(source)
        existing = self.store.one('SELECT id,case_id FROM rg_case_files WHERE drive_file_id=?', (file_id,))
        if existing:
            return self._existing(existing, case_id)
        name, content = self.drive.read_pdf(file_id)
        return self._index(case_id, file_id, name, content, actor, 'drive')

    def upload_pdf(self, case_id, filename, data, actor):
        """Guest-workspace upload: the same checks as a Drive import, then assign the uploader.

        Lets public testers attempt instructions hidden in a case PDF without access
        to the team's private Drive folder.
        """
        if len(data) > MAX_BYTES:
            raise DriveFileError(f'Choose a PDF up to {MAX_BYTES // 1024} KB.', 413)
        file_id = 'upload-' + hashlib.sha256(data).hexdigest()
        existing = self.store.one('SELECT id,case_id FROM rg_case_files WHERE drive_file_id=?', (file_id,))
        if existing:
            result = self._existing(existing, case_id)
        else:
            count = self.store.one('SELECT COUNT(*) AS n FROM rg_case_files WHERE case_id=?', (case_id,))['n']
            if count >= MAX_UPLOADS_PER_CASE:
                raise DriveFileError(f'A case can hold at most {MAX_UPLOADS_PER_CASE} uploaded PDFs.', 409)
            result = self._index(case_id, file_id, filename, pdf_text(data), actor, 'upload')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO rg_case_file_assignments(case_id,user_id) VALUES(?,?) '
                       'ON CONFLICT(case_id) DO UPDATE SET user_id=excluded.user_id', (case_id, actor['id']))
        return result

    def _index(self, case_id, file_id, name, raw, actor, kind):
        references = bank_references(self.store)
        title = ' '.join(model_text(name, references, limit=160).split())
        content = model_text(raw, references)
        if WITHHELD in (title, content) or disguised_instruction(name) or disguised_instruction(raw):
            # Record the attempt without its text, so testers' attacks are visible in the logs.
            self.store.event(actor['id'], 'records.case_file_rejected', case_id, kind=kind, reason='instructions',
                             sha256=hashlib.sha256(raw.encode()).hexdigest())
            raise DriveFileError('This PDF contains instructions that need review before import.')
        if len(content) < 10:
            raise DriveFileError('This PDF does not contain enough usable text to import.')
        chunks = [content[start:start + 1000] for start in range(0, len(content), 850)]
        vectors = local_embeddings(chunks)
        document_id = 'DOC-' + uuid4().hex[:10].upper()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,case_id FROM rg_case_files WHERE drive_file_id=?', (file_id,)).fetchone()
            if existing:
                return self._existing(existing, case_id)
            db.execute('INSERT INTO rg_case_files VALUES (?,?,?,?,?,?)',
                       (document_id, case_id, file_id, title or 'Case PDF', actor['id'], stamp()))
            db.executemany('INSERT INTO rg_case_file_chunks VALUES (?,?,?,?)',
                           [(document_id, number, chunk, serialize_float32(vector))
                            for number, (chunk, vector) in enumerate(zip(chunks, vectors))])
        self.store.event(actor['id'], 'records.case_file_imported', case_id, document_id=document_id, kind=kind)
        return {'id': document_id, 'imported': True}

    @staticmethod
    def _existing(file, case_id):
        if file['case_id'] != case_id:
            raise DriveFileError('This Drive file has already been linked to a case.', 409)
        return {'id': file['id'], 'imported': False}

    def search(self, case_id, query, actor):
        with self.store.connect(vector=True) as db:
            db.execute('BEGIN')
            if not self._allowed(db, case_id, actor):
                raise DriveFileError('Case files not found.', 404)
            references = [row['bank_ref'] for row in db.execute('SELECT bank_ref FROM rg_profiles')
                          if len(row['bank_ref']) >= 4]
            query = model_text(query, references)
            if query == WITHHELD:
                raise DriveFileError('Enter a factual search query.')
            vector = serialize_float32(local_embeddings([query])[0])
            rows = db.execute(
                'SELECT f.id AS source_id,f.title,c.chunk_no,c.content,'
                'vec_distance_cosine(c.embedding,?) AS distance FROM rg_case_file_chunks c '
                'JOIN rg_case_files f ON f.id=c.file_id WHERE f.case_id=? '
                'ORDER BY distance,c.file_id,c.chunk_no LIMIT 5', (vector, case_id),
            ).fetchall()
            return [{**dict(row), 'title': model_text(row['title'], references),
                     'content': model_text(row['content'], references)} for row in rows]

    def workflow_passages(self, case_id, query, actor, limit=WORKFLOW_PASSAGES):
        """Top passages for the Records agent, or [] when the actor may not read them.

        Every stored passage for the case is rechecked, not only the top-ranked
        ones: a recognized attack must not become safe by ranking lower, and the
        attack patterns may have changed since import.
        """
        with self.store.connect(vector=True) as db:
            db.execute('BEGIN')
            if not self._allowed(db, case_id, actor):
                return []
            stored = db.execute(
                'SELECT f.title,c.content FROM rg_case_file_chunks c JOIN rg_case_files f '
                'ON f.id=c.file_id WHERE f.case_id=?', (case_id,)).fetchall()
            if not stored:
                return []
            references = [row['bank_ref'] for row in db.execute('SELECT bank_ref FROM rg_profiles')
                          if len(row['bank_ref']) >= 4]
            if any(WITHHELD in model_text(row[field], references) or disguised_instruction(row[field])
                   for row in stored for field in ('title', 'content')):
                raise InputReview('Case file evidence requires human review. No automatic refund was authorized.')
            query = model_text(query, references, limit=14000)
            if WITHHELD in query:
                raise InputReview('Customer input requires human review. No automatic refund was authorized.')
            vector = serialize_float32(local_embeddings([query])[0])
            rows = db.execute(
                'SELECT f.id AS source_id,f.title,c.chunk_no,c.content,'
                'vec_distance_cosine(c.embedding,?) AS distance FROM rg_case_file_chunks c '
                'JOIN rg_case_files f ON f.id=c.file_id WHERE f.case_id=? '
                'ORDER BY distance,c.file_id,c.chunk_no LIMIT ?', (vector, case_id, limit),
            ).fetchall()
        return [{'source_id': row['source_id'], 'kind': 'case_file', 'chunk_no': row['chunk_no'],
                 'title': model_text(row['title'], references, limit=160),
                 'content': model_text(row['content'], references), 'distance': row['distance']}
                for row in rows]
