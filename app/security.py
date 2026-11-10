import hashlib
import hmac
import secrets
import time
from threading import BoundedSemaphore
from uuid import uuid4
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from app.store import stamp

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
PASSWORD_WORKERS=BoundedSemaphore(2)

def hash_password(password):
    if not PASSWORD_WORKERS.acquire(blocking=False):
        raise HTTPException(429,'Authentication is busy. Please try again shortly.',headers={'Retry-After':'2'})
    try:
        return PASSWORDS.hash(password)
    finally:
        PASSWORD_WORKERS.release()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def validate_password(password):
    if not 15 <= len(password) <= 128:
        raise HTTPException(422, 'Use a password or passphrase with 15–128 characters')

def verify_password(encoded, password):
    if not PASSWORD_WORKERS.acquire(blocking=False):
        raise HTTPException(429,'Authentication is busy. Please try again shortly.',headers={'Retry-After':'2'})
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
    finally:
        PASSWORD_WORKERS.release()

def throttle(store, key, limit=8, window=900):
    now = time.time()
    key = digest(key)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM rg_rate_limits WHERE key=?', (key,)).fetchone()
        if row and row['resets'] > now and row['hits'] >= limit:
            raise HTTPException(429, 'Too many attempts. Please try again later.', headers={'Retry-After':str(int(row['resets']-now)+1)})
        if not row or row['resets'] <= now:
            db.execute('INSERT OR REPLACE INTO rg_rate_limits VALUES(?,?,?)', (key, 1, now+window))
        else:
            db.execute('UPDATE rg_rate_limits SET hits=hits+1 WHERE key=?', (key,))

def public_user(row):
    return {k:row[k] for k in ('id','email','name','role')}

def new_session(store, user_id, response, old_token=None, mfa_verified=False):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = time.time()
    with store.connect() as db:
        db.execute('DELETE FROM rg_sessions WHERE expires < ? OR touched < ?', (now, now-1800))
        if old_token:
            db.execute('DELETE FROM rg_sessions WHERE token_hash=?', (digest(old_token),))
        db.execute('INSERT INTO rg_sessions(token_hash,user_id,csrf,created,touched,expires,mfa_verified) VALUES(?,?,?,?,?,?,?)',
                   (digest(token), user_id, csrf, now, now, now+28800,int(mfa_verified)))
    response.set_cookie(store.settings.cookie_name, token, max_age=28800, httponly=True,
                        secure=store.settings.production, samesite='strict', path='/')
    return csrf

def current_user(request: Request):
    store = request.app.state.store
    token = request.cookies.get(store.settings.cookie_name, '')
    now = time.time()
    row = store.one('SELECT u.*,s.csrf,s.mfa_verified,s.created AS session_created FROM rg_sessions s '
                    'JOIN rg_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? '
                    'AND s.touched>? AND u.active=1', (digest(token), now, now-1800))
    if not row:
        raise HTTPException(401, 'Please sign in to continue')
    request.state.audit_actor = row['id']
    if request.method not in ('GET','HEAD','OPTIONS'):
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''), row['csrf']):
            raise HTTPException(403, 'Session verification failed. Refresh and try again.')
    mfa = request.app.state.mfa
    if mfa.required(row) and not row['mfa_verified'] and request.url.path not in (
        '/api/auth/me','/api/auth/logout','/api/auth/mfa/status',
        '/api/auth/mfa/enroll','/api/auth/mfa/confirm','/api/auth/mfa/verify'
    ):
        raise HTTPException(403, 'Complete multi-factor authentication before continuing')
    store.execute('UPDATE rg_sessions SET touched=? WHERE token_hash=?', (now,digest(token)))
    return row

def require_role(user, *roles):
    if user['role'] not in roles:
        raise HTTPException(403, 'Your account does not have permission for this action')

def create_user(db, email, name, password, role):
    user_id = str(uuid4())
    db.execute('INSERT INTO rg_users VALUES(?,?,?,?,?,?,?)',
               (user_id, email.lower().strip(), name, hash_password(password), role, 1, stamp()))
    return user_id
