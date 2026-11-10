"""Sanitized alerts and signed evidence. Remote retention requires an operator."""
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import time

from app.store import stamp

LOGGER = logging.getLogger('uvicorn.error')
ALLOWED = {'document_id','kind','version','sha256','run_id','mode','executed','status','reason',
           'target','role','active','customer_id','order_id','decision','benchmark_id','code','route',
           'peer_hash','source_id','path','count','deadline_seconds'}
ALERT_ACTIONS = {'auth.login_failed','auth.mfa_failed','auth.mfa_enabled','auth.mfa_reset',
                 'security.denied','security.throttled','policy.submitted','policy.published',
                 'policy.rejected','policy.rollback','refund.blocked','authority.revoked',
                 'workflow.busy','workflow.timeout','budget.exhausted','audit.delivery_failed',
                 'team.admin_link_created','team.admin_link_revoked','auth.team_invite_accepted',
                 'recovery.backup_failed'}


def sanitized(details):
    return {k: (v[:200] if isinstance(v, str) else v) for k,v in details.items()
            if k in ALLOWED and isinstance(v,(str,int,float,bool,type(None)))}


def record_alert(store, actor, action):
    if action not in ALERT_ACTIONS:
        return
    bucket = int(time.time()) // 900
    fingerprint = hashlib.sha256(f'{actor}:{action}:{bucket}'.encode()).hexdigest()
    severity = 'high' if action in {'auth.mfa_reset','authority.revoked','audit.delivery_failed'} else 'medium'
    now = stamp()
    store.execute('INSERT INTO rg_alerts(fingerprint,severity,action,first_seen,last_seen) VALUES(?,?,?,?,?) '
                  'ON CONFLICT(fingerprint) DO UPDATE SET last_seen=excluded.last_seen,occurrences=occurrences+1,acknowledged_by=NULL,acknowledged_at=NULL',
                  (fingerprint,severity,action,now,now))


def emit_event(store, actor, action, case_id, details):
    record = {'timestamp':stamp(),'actor':actor,'action':action,'case_id':case_id,'details':details}
    encoded = json.dumps(record, separators=(',', ':'))
    LOGGER.info('refundguard.security %s', encoded)
    if store.settings.audit_directory:
        # Only trusted server configuration selects the destination; never a browser input.
        directory = Path(store.settings.audit_directory)
        try:
            directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            if directory.is_symlink():
                raise OSError('Audit directory must not be a symlink')
            fd = os.open(directory/'security.jsonl', os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd,'a') as output:
                output.write(encoded+'\n')
        except OSError:
            record_alert(store, 'system', 'audit.delivery_failed')
            LOGGER.error('refundguard.security audit.delivery_failed')


def signed_evidence(store):
    from app.mfa import private_key
    payload = {'created_at':stamp(), 'scope':'Sanitized events and alert register; excludes credentials and raw customer/model content',
               'events':store.all('SELECT * FROM rg_events ORDER BY id'),
               'alerts':store.all('SELECT * FROM rg_alerts ORDER BY id')}
    encoded = json.dumps(payload,sort_keys=True,separators=(',', ':')).encode()
    key = private_key(store.path.parent/'evidence-key')
    return {'payload':payload,'algorithm':'HMAC-SHA256',
            'signature':hmac.new(key,encoded,hashlib.sha256).hexdigest()}
