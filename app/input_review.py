"""Audited model-facing message corrections; original mailbox evidence is immutable here.

Only the supervisor/admin HTTP route calls save_review. Reviews are bound to a
specific case/message and source hash; they cannot change financial case fields.
"""
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException

from app.privacy import WITHHELD, bank_references, model_text
from app.store import stamp


def source_hash(message):
    payload = [message['case_id'], message['id'], message['subject'], message['body']]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def message_review(store, message):
    row = store.one('SELECT value FROM rg_meta WHERE key=?',
                    ('input-review:'+message['case_id']+':'+message['id'],))
    if not row:
        return None
    review = json.loads(row['value'])
    return review if review['source_sha256'] == source_hash(message) else None


def message_for_model(store, message):
    review = message_review(store, message)
    return review['body'] if review else message['body']


def case_document_for_model(store, document):
    """Apply an initial-message correction to its generated case document too."""
    try:
        content = json.loads(document['content'])
    except (ValueError, TypeError):
        return document['content']
    if not isinstance(content, dict) or not isinstance(content.get('request'), dict):
        return document['content']
    cid = content.get('case_id')
    if document['kind'] != 'customer' or document['title'] != 'Case '+str(cid):
        return document['content']
    case = store.one('SELECT customer_id,message FROM rg_cases WHERE id=?',(cid,))
    if not case or case['customer_id'] != document['customer_id']:
        return document['content']
    if content['request'].get('message') != case['message']:
        return document['content']
    for message in store.all("SELECT * FROM rg_messages WHERE case_id=? AND direction='inbound' AND body=?",
                             (cid,case['message'])):
        review = message_review(store,message)
        if review:
            content['request']['message'] = review['body']
            return json.dumps(content,ensure_ascii=False)
    return document['content']


def save_review(store, cid, mid, user, body, reason):
    prepared = model_text(body, bank_references(store), limit=6000)
    if not prepared or WITHHELD in prepared:
        raise HTTPException(422,'Enter a factual replacement without instruction overrides.')
    review = {'case_id':cid, 'message_id':mid, 'body':prepared, 'reason':reason,
              'reviewed_by':user['id'], 'reviewed_at':stamp()}
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        case = db.execute('SELECT customer_id,status FROM rg_cases WHERE id=?',(cid,)).fetchone()
        if not case:
            raise HTTPException(404,'Case not found')
        if case['status']=='processing' or db.execute('SELECT 1 FROM ledger WHERE case_id=?',(cid,)).fetchone():
            raise HTTPException(409,'Input cannot be reviewed during processing or after refund execution.')
        message = db.execute("SELECT * FROM rg_messages WHERE id=? AND case_id=? AND direction='inbound'",(mid,cid)).fetchone()
        if not message:
            raise HTTPException(404,'Incoming message not found')
        review['source_sha256'] = source_hash(message)
        encoded = json.dumps(review,ensure_ascii=False)
        db.execute('INSERT OR REPLACE INTO rg_meta(key,value) VALUES(?,?)',('input-review:'+cid+':'+mid,encoded))
        # Preserve revisions as well as the current pointer.
        db.execute('INSERT INTO rg_meta(key,value) VALUES(?,?)',('input-review-history:'+uuid4().hex,encoded))
        db.execute('DELETE FROM rg_chunks WHERE document_id IN '
                   "(SELECT id FROM rg_documents WHERE title=? AND kind='customer' AND customer_id=? AND active=1)",
                   ('Case '+cid,case['customer_id']))
        # Same transaction as the review: no raw correction text in the event.
        db.execute('INSERT INTO rg_events(timestamp,actor,action,case_id,details) VALUES(?,?,?,?,?)',
                   (review['reviewed_at'],user['id'],'input.reviewed',cid,
                    json.dumps({'customer_id':case['customer_id'],'source_id':mid,'sha256':review['source_sha256']})))
    from app.monitoring import emit_event
    emit_event(store,user['id'],'input.reviewed',cid,
               {'customer_id':case['customer_id'],'source_id':mid,'sha256':review['source_sha256']})
    return review
