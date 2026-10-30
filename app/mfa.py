"""TOTP enrollment, replay prevention and single-use recovery codes."""
import json
import os
from pathlib import Path
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
import pyotp

from app.schemas import Input
from app.security import current_user, digest, new_session, throttle, verify_password


class Enrollment(Input):
    password: str = Field(min_length=1, max_length=128, repr=False)


class Factor(Input):
    code: str = Field(min_length=6, max_length=80, repr=False)


def private_key(path):
    """Create once; never silently replace an existing encryption/signing key."""
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError('Key file must not be a symlink')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as out:
            out.write(Fernet.generate_key())
    os.chmod(path, 0o600)
    return path.read_bytes().strip()


class MFA:
    def __init__(self, store):
        self.store = store
        key = store.settings.mfa_encryption_key or private_key(store.path.parent / 'mfa-key')
        self.cipher = Fernet(key)

    def enabled(self, uid):
        row = self.store.one('SELECT enabled FROM rg_mfa WHERE user_id=?', (uid,))
        return bool(row and row['enabled'])

    def required(self, user):
        return self.enabled(user['id']) or (
            self.store.settings.production and user['role'] in ('admin', 'supervisor'))

    def decrypt(self, value):
        try:
            return self.cipher.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError, AttributeError):
            raise HTTPException(503, 'MFA key unavailable. Contact the hosting administrator.') from None

    def counter(self, secret, code, last=-1):
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            return None
        now = int(time.time()) // 30
        generator = pyotp.TOTP(secret)
        for step in (now - 1, now, now + 1):
            if step > last and secrets.compare_digest(generator.at(step * 30), code):
                return step
        return None

    def verify(self, uid, code):
        throttle(self.store, 'mfa:' + uid, 8)
        accepted = False
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM rg_mfa WHERE user_id=? AND enabled=1', (uid,)).fetchone()
            if row:
                step = self.counter(self.decrypt(row['secret']), code, row['last_counter'])
                recovery = json.loads(row['recovery'])
                hashed = digest(code.strip().replace('-', '').upper())
                if step is not None:
                    db.execute('UPDATE rg_mfa SET last_counter=? WHERE user_id=?', (step, uid))
                    accepted = True
                elif hashed in recovery:
                    recovery.remove(hashed)
                    db.execute('UPDATE rg_mfa SET recovery=? WHERE user_id=?', (json.dumps(recovery), uid))
                    accepted = True
        if not accepted:
            self.store.event(uid, 'auth.mfa_failed')
            raise HTTPException(401, 'Invalid, expired or already used verification code')
        return True


def router(mfa):
    routes = APIRouter(prefix='/api/auth/mfa')
    store = mfa.store

    @routes.get('/status')
    def status(user=Depends(current_user)):
        return {'enabled': mfa.enabled(user['id']), 'required': mfa.required(user),
                'verified': bool(user['mfa_verified'])}

    @routes.post('/enroll')
    def enroll(body: Enrollment, user=Depends(current_user)):
        throttle(store, 'mfa-enroll:' + user['id'], 5)
        if mfa.enabled(user['id']):
            raise HTTPException(409, 'MFA is already enabled. Use a recovery code if needed.')
        if not verify_password(user['password_hash'], body.password):
            raise HTTPException(403, 'Password verification failed')
        secret = pyotp.random_base32()
        encrypted = mfa.cipher.encrypt(secret.encode()).decode()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT enabled FROM rg_mfa WHERE user_id=?', (user['id'],)).fetchone()
            if row and row['enabled']:
                raise HTTPException(409, 'MFA is already enabled')
            db.execute('INSERT INTO rg_mfa(user_id,pending,pending_until) VALUES(?,?,?) '
                       'ON CONFLICT(user_id) DO UPDATE SET pending=excluded.pending,pending_until=excluded.pending_until',
                       (user['id'], encrypted, time.time() + 600))
        store.event(user['id'], 'auth.mfa_enrollment_started')
        return {'secret': secret, 'uri': pyotp.TOTP(secret).provisioning_uri(user['email'], issuer_name='RefundGuard'),
                'expires_in': 600}

    @routes.post('/confirm')
    def confirm(body: Factor, request: Request, response: Response, user=Depends(current_user)):
        throttle(store, 'mfa-confirm:' + user['id'], 8)
        codes = [secrets.token_hex(16).upper() for _ in range(8)]
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM rg_mfa WHERE user_id=?', (user['id'],)).fetchone()
            if not row or row['enabled'] or row['pending_until'] < time.time() or not row['pending']:
                raise HTTPException(409, 'Start a new MFA enrollment')
            step = mfa.counter(mfa.decrypt(row['pending']), body.code)
            if step is None:
                raise HTTPException(400, 'Enter the current code from your authenticator')
            db.execute('UPDATE rg_mfa SET secret=pending,pending=NULL,pending_until=0,enabled=1,last_counter=?,recovery=? WHERE user_id=?',
                       (step, json.dumps([digest(c) for c in codes]), user['id']))
            db.execute('DELETE FROM rg_sessions WHERE user_id=?', (user['id'],))
        csrf = new_session(store, user['id'], response, mfa_verified=True)
        store.event(user['id'], 'auth.mfa_enabled')
        return {'csrf': csrf, 'recovery_codes': codes}

    @routes.post('/verify')
    def verify(body: Factor, request: Request, response: Response, user=Depends(current_user)):
        mfa.verify(user['id'], body.code)
        csrf = new_session(store, user['id'], response,
                           request.cookies.get(store.settings.cookie_name), mfa_verified=True)
        store.event(user['id'], 'auth.mfa_verified')
        return {'csrf': csrf, 'verified': True}

    return routes
