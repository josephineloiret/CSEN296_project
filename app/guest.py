"""Intentionally public demo credentials, isolated from the private workspace."""
from dataclasses import replace
from pathlib import Path

EMAIL = 'guest@refundguard.example'
PASSWORD = 'RefundGuard-Guest-2026!'


def settings_for_guest(settings):
    return replace(settings, database=Path(settings.database).parent/'public-guest'/'refundguard.sqlite3',
                   provider='local', api_key='', daily_budget_usd='0', monthly_budget_usd='0',
                   audit_directory='', mfa_encryption_key='', team_invite_hash='',
                   team_invite_expires=0, public_guest_enabled=False, guest_workspace=True,
                   railway=False)


def seed_guest(store):
    from app.security import create_user
    user = store.one('SELECT * FROM rg_users WHERE email=?', (EMAIL,))
    if not user:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM rg_users WHERE email=?', (EMAIL,)).fetchone():
                create_user(db, EMAIL, 'Public Guest', PASSWORD, 'member')
        user = store.one('SELECT * FROM rg_users WHERE email=?', (EMAIL,))
    store.profile_for_user(user)


def relative_path(request):
    path = request.url.path
    root = request.scope.get('root_path', '')
    return path[len(root):] if root and path.startswith(root) else path


def permitted(request):
    """Guests can exercise mock support tools, but cannot change access or policy."""
    import re
    path = relative_path(request)
    if request.method == 'GET':
        return path in {'/api/auth/me', '/api/dashboard', '/api/profiles', '/api/orders',
                        '/api/cases', '/api/messages', '/api/knowledge', '/api/reports',
                        '/api/reports/export', '/api/usage'} or bool(
                            re.fullmatch(r'/api/cases/RG-[0-9A-F]{8}', path))
    if request.method == 'POST':
        return path in {'/api/auth/logout', '/api/orders', '/api/cases',
                        '/api/knowledge/search', '/api/benchmarks/run'} or bool(
                            re.fullmatch(r'/api/cases/RG-[0-9A-F]{8}/(?:run|messages)', path))
    return False
