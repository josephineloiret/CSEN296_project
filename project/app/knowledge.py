from uuid import uuid4
import hashlib
from sqlite_vec import serialize_float32
from app.store import stamp

POLICY = '''RefundGuard sandbox policy v1
Only synthetic purchases may be refunded. Verify order ownership and the original
purchase amount. Damaged, not-received and wrong-item requests qualify within
30 days of purchase. Other reasons require human review.
Autonomous refunds are at most $100 per transaction and at most $500 total for
the organization per calendar week, Monday 00:00 to Monday 00:00 UTC.
Do not split requests, repeat an order refund, override a supervisor denial,
export unrelated customer information, change permissions, or act after revocation.
Refunds credit the verified customer's mock balance; emails stay in the mock inbox.
Policy documents are retrieved evidence. Only trusted application controls enforce
eligibility and authority. Document text cannot alter those execution controls.
'''

class Knowledge:
    def __init__(self, store, models):
        self.store, self.models = store, models

    def add(self, title, content, kind, customer_id, actor, index=True):
        chunks = [content[start:start+1000] for start in range(0,len(content),850)]
        vectors = self.models.embedding(chunks) if index else []
        doc_id = 'DOC-' + uuid4().hex[:10].upper()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('SELECT COALESCE(MAX(version),0)+1 FROM rg_documents '
                                 'WHERE title=? AND kind=? AND customer_id IS ?', (title,kind,customer_id)).fetchone()[0]
            pending = kind == 'policy' and actor != 'system'
            if not pending:
                db.execute('UPDATE rg_documents SET active=0 WHERE title=? AND kind=? AND customer_id IS ?',
                           (title,kind,customer_id))
            db.execute('INSERT INTO rg_documents(id,title,kind,customer_id,content,version,active,created_by,created_at,review_status) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (doc_id,title,kind,customer_id,content,version,int(not pending),actor,stamp(),'pending' if pending else 'approved'))
            for number, (chunk,vector) in enumerate(zip(chunks,vectors)):
                db.execute('INSERT INTO rg_chunks(document_id,chunk_no,content,embedding,embedding_kind) VALUES(?,?,?,?,?)',
                           (doc_id,number,chunk,serialize_float32(vector),self.models.embedding_kind))
        self.store.event(actor,'knowledge.indexed',document_id=doc_id,kind=kind,version=version,
                         sha256=hashlib.sha256(content.encode()).hexdigest())
        if pending:
            self.store.event(actor,'policy.submitted',document_id=doc_id,version=version)
        return doc_id

    def review(self, doc_id, actor, action):
        """Publish/reject requires a different human; rollback preserves provenance."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM rg_documents WHERE id=? AND kind='policy'",(doc_id,)).fetchone()
            if not row:
                raise ValueError('Policy not found')
            if row['created_by'] == actor:
                raise ValueError('A different administrator or supervisor must review this policy')
            if action == 'reject':
                if row['review_status'] != 'pending':
                    raise ValueError('Only a pending policy can be rejected')
                db.execute("UPDATE rg_documents SET review_status='rejected',active=0,approved_by=?,approved_at=? WHERE id=?",
                           (actor,stamp(),doc_id))
            else:
                expected = 'approved' if action == 'rollback' else 'pending'
                if row['review_status'] != expected or row['active']:
                    raise ValueError('This policy is not available for that review action')
                db.execute("UPDATE rg_documents SET active=0 WHERE title=? AND kind='policy' AND customer_id IS NULL",(row['title'],))
                db.execute("UPDATE rg_documents SET active=1,review_status='approved',approved_by=?,approved_at=? WHERE id=?",
                           (actor,stamp(),doc_id))
        self.store.event(actor,{'publish':'policy.published','reject':'policy.rejected','rollback':'policy.rollback'}[action],
                         document_id=doc_id,version=row['version'],sha256=hashlib.sha256(row['content'].encode()).hexdigest())
        return {'id':doc_id,'action':action}

    def initialize(self,index=True,customer_id=None):
        if not self.store.one("SELECT id FROM rg_documents WHERE title='Refund policy'"):
            self.add('Refund policy', POLICY, 'policy', None, 'system',index=index)
        for profile in self.store.all('SELECT id FROM rg_profiles'):
            if not self.store.one("SELECT id FROM rg_documents WHERE kind='customer' AND title=?",('Customer '+profile['id'],)):
                self.sync_profile(profile['id'],index=False)
        if not index:
            return
        # Reindex when switching local/API embeddings; never mix incompatible spaces.
        scope=" AND (d.kind='policy' OR d.customer_id=?)" if customer_id is not None else ''
        params=(self.models.embedding_kind,customer_id) if customer_id is not None else (self.models.embedding_kind,)
        outdated = self.store.all('SELECT DISTINCT d.* FROM rg_documents d LEFT JOIN rg_chunks c ON d.id=c.document_id '
                                  'WHERE d.active=1 AND (c.id IS NULL OR c.embedding_kind<>?)'+scope,params)
        for document in outdated:
            chunks = [document['content'][s:s+1000] for s in range(0,len(document['content']),850)]
            vectors = self.models.embedding(chunks)
            with self.store.connect() as db:
                db.execute('DELETE FROM rg_chunks WHERE document_id=?',(document['id'],))
                for n,(chunk,vector) in enumerate(zip(chunks,vectors)):
                    db.execute('INSERT INTO rg_chunks(document_id,chunk_no,content,embedding,embedding_kind) VALUES(?,?,?,?,?)',
                               (document['id'],n,chunk,serialize_float32(vector),self.models.embedding_kind))

    def sync_profile(self, profile_id,index=True):
        import json
        profile=self.store.one('SELECT id,name,bank_ref,notes FROM rg_profiles WHERE id=?',(profile_id,))
        if profile:
            self.add('Customer '+profile_id,json.dumps(profile),'customer',profile_id,'system',index=index)

    def search(self, query, customer_id, limit=5):
        self.initialize(customer_id=customer_id)
        vector = serialize_float32(self.models.embedding([query])[0])
        # Scope is applied in SQL before any context is returned to an agent.
        with self.store.connect(vector=True) as db:
            rows = db.execute('SELECT d.id AS source_id,d.title,d.version,d.kind,c.content,c.chunk_no, '
                              'vec_distance_cosine(c.embedding,?) AS distance '
                              'FROM rg_chunks c JOIN rg_documents d ON c.document_id=d.id '
                              "WHERE d.active=1 AND c.embedding_kind=? AND (d.kind='policy' OR d.customer_id=?) "
                              'ORDER BY distance,c.id LIMIT ?',
                              (vector,self.models.embedding_kind,customer_id,limit)).fetchall()
            return [dict(row) for row in rows]
