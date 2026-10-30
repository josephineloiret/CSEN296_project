"""Encrypted SQLite online backups and restore into a new, isolated directory."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet
from app.store import stamp
from app.mfa import private_key


def inspect_database(path):
    with closing(sqlite3.connect(path)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database foreign-key check failed')
        mismatch = db.execute('SELECT c.id FROM customers c LEFT JOIN '
                              '(SELECT k.customer_id,SUM(l.amount_cents) total FROM ledger l '
                              'JOIN cases k ON k.id=l.case_id GROUP BY k.customer_id) p ON c.id=p.customer_id '
                              'WHERE c.balance_cents<>COALESCE(p.total,0)').fetchall()
        if mismatch:
            raise ValueError('Refund ledger and balances disagree')
        return {table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                for table in ('rg_users','rg_cases','ledger','rg_events','rg_documents')}


def backup(store, output, key_file):
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    cipher = Fernet(private_key(key_file))
    with TemporaryDirectory() as directory:
        snapshot = Path(directory)/'refundguard.sqlite3'
        with store.connect() as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        counts = inspect_database(snapshot)
        files = {'refundguard.sqlite3':base64.b64encode(snapshot.read_bytes()).decode()}
        for name in ('mfa-key','evidence-key'):
            path = store.path.parent/name
            if path.exists():
                if path.is_symlink():
                    raise ValueError('Key files must not be symlinks')
                files[name] = base64.b64encode(path.read_bytes()).decode()
        payload = {'format':'refundguard-backup-v1','created_at':stamp(),'counts':counts,'files':files}
        encrypted = cipher.encrypt(json.dumps(payload).encode())
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(encrypted)
    store.event('local-admin','recovery.backup_created')
    return {'created_at':payload['created_at'],'counts':counts,'sha256':hashlib.sha256(encrypted).hexdigest()}


def restore(archive, destination, key_file):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Restore destination must be a new directory; live data is never overwritten')
    # Read only: a wrong/missing key must not silently create a replacement.
    cipher=Fernet(Path(key_file).read_bytes().strip())
    payload=json.loads(cipher.decrypt(Path(archive).read_bytes()))
    if payload.get('format')!='refundguard-backup-v1' or set(payload['files'])-{'refundguard.sqlite3','mfa-key','evidence-key'}:
        raise ValueError('Unsupported backup contents')
    with TemporaryDirectory() as directory:
        candidate=Path(directory)/'refundguard.sqlite3'
        candidate.write_bytes(base64.b64decode(payload['files']['refundguard.sqlite3'],validate=True))
        counts=inspect_database(candidate)
        if counts!=payload['counts']:
            raise ValueError('Backup record counts disagree')
        # Sessions and invitations never become valid again after a restore.
        with closing(sqlite3.connect(candidate)) as db:
            with db:
                db.execute('DELETE FROM rg_sessions')
                db.execute('UPDATE rg_invites SET used=1')
                db.execute('UPDATE rg_team_links SET revoked=1')
                db.execute('UPDATE authority SET active=0')
        destination.mkdir(mode=0o700)
        for name,value in payload['files'].items():
            content=candidate.read_bytes() if name=='refundguard.sqlite3' else base64.b64decode(value,validate=True)
            fd=os.open(destination/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:
                stream.write(content)
    return {'integrity':'ok','ledger_balances':'consistent','counts':counts,
            'sessions_revoked':True,'invitations_revoked':True,'authority_paused':True}
