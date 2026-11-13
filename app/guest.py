"""Intentionally public demo credentials, isolated from the private workspace."""
from dataclasses import replace
from pathlib import Path

EMAIL = 'guest@refundguard.example'
PASSWORD = 'RefundGuard-Guest-2026!'


class GuestRoutingMiddleware:
    """Use the main URL for both accounts while keeping their apps/data separate."""

    def __init__(self, app, guest_app, origin, guest_cookie, private_cookie):
        self.app, self.guest_app = app, guest_app
        self.origin = origin
        self.guest_cookie, self.private_cookie = guest_cookie, private_cookie

    async def __call__(self, scope, receive, send):
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        import asyncio
        import json
        path = scope.get('path', '')
        if scope['type'] != 'http' or not path.startswith('/api/'):
            return await self.app(scope, receive, send)
        request = Request(scope)
        forwarded_receive = receive
        guest = False
        if path == '/api/auth/login' and scope['method'] == 'POST':
            if request.headers.get('origin') != self.origin:
                return await JSONResponse({'detail':'Request origin was not accepted'},403)(scope,receive,send)
            if not request.headers.get('content-type','').lower().startswith('application/json'):
                return await JSONResponse({'detail':'JSON requests are required'},415)(scope,receive,send)
            async def bounded_body():
                body = bytearray()
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return None
                    body.extend(message.get('body',b''))
                    if len(body) > 200000:
                        return None
                    if not message.get('more_body',False):
                        return bytes(body)
            try:
                body = await asyncio.wait_for(bounded_body(),timeout=10)
            except TimeoutError:
                return await JSONResponse({'detail':'Upload timed out'},408)(scope,receive,send)
            if body is None:
                return await JSONResponse({'detail':'Request is too large or disconnected'},413)(scope,receive,send)
            try:
                data = json.loads(body)
                guest = isinstance(data,dict) and str(data.get('email','')).strip().lower() == EMAIL
            except (ValueError,TypeError):
                pass
            replayed = False
            async def replay_body():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {'type':'http.request','body':body,'more_body':False}
                return await receive()
            forwarded_receive = replay_body
        elif path not in {'/api/auth/status','/api/auth/setup','/api/auth/accept-invite',
                          '/api/auth/accept-team-invite','/api/auth/team-invite-status'}:
            guest = bool(request.cookies.get(self.guest_cookie)) and not request.cookies.get(self.private_cookie)
        target = self.guest_app if guest else self.app
        return await target(scope,forwarded_receive,send)


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
