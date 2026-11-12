"""RefundGuard browser application. Run with uvicorn app.main:app from project/."""
from datetime import datetime, timezone, timedelta
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.ai import AIError, Models
from app.config import Settings
from app.knowledge import Knowledge
from app.schemas import (AcceptInvite, ActiveInput, CaseInput, DocumentInput, Invitation,
                         Login, MessageInput, OrderInput, PasswordInput, ProfileInput,
                         SearchInput, Setup, SupervisorInput, PolicyReview, AcceptTeamInvite, InviteToken)
from app.mfa import MFA, router as mfa_router
from app.monitoring import signed_evidence
from app.security import (DUMMY_HASH, PASSWORDS, create_user, current_user, digest,
                          new_session, public_user, require_role, throttle,
                          validate_password, verify_password, hash_password)
from app.store import Store, stamp
from app.workflow import Workflow
from app.budget import Budget

STATIC = Path(__file__).parent / 'static'
STAFF = ('admin','supervisor','member')


def create_app(settings=None):
    settings = settings or Settings.from_env()
    settings.validate()
    store = Store(settings)
    budget=Budget(store)
    models = Models(settings,budget)
    knowledge = Knowledge(store, models)
    store.seed()
    knowledge.initialize(index=settings.provider=='local')
    store.bootstrap_token()
    workflow = Workflow(store,knowledge,models)
    @asynccontextmanager
    async def lifespan(application):
        task = None
        if settings.production:
            async def daily_backup():
                from app.recovery import backup
                # First run after startup, then daily while the instance is awake.
                # Sleeping/restarts defer the schedule; off-host scheduling is an operator task.
                await asyncio.sleep(60)
                while True:
                    try:
                        directory=store.path.parent/'backups'
                        output=directory/('refundguard-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.rgbackup')
                        await asyncio.to_thread(backup,store,output,store.path.parent/'backup-key')
                        files=sorted(directory.glob('refundguard-*.rgbackup'),reverse=True)
                        for old in files[7:]:
                            old.unlink()
                    except Exception:
                        store.event('system','recovery.backup_failed')
                    await asyncio.sleep(86400)
            task=asyncio.create_task(daily_backup())
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    app = FastAPI(title='RefundGuard', docs_url=None, redoc_url=None, openapi_url=None,lifespan=lifespan)
    app.state.store, app.state.workflow, app.state.knowledge = store,workflow,knowledge
    app.state.budget=budget
    app.state.mfa = MFA(store)
    app.include_router(mfa_router(app.state.mfa))
    allowed_hosts = [urlsplit(settings.origin).hostname]
    if not settings.production:
        allowed_hosts += ['localhost','127.0.0.1','testserver']
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts)

    @app.middleware('http')
    async def boundary(request, call_next):
        # Railway probes use HTTP and a platform hostname. This narrow exception
        # serves only liveness; it never reaches account/data routes.
        if settings.railway and request.method=='GET' and request.url.path=='/health' and request.url.hostname=='healthcheck.railway.app':
            return JSONResponse({'status':'ok','application':'refundguard'},headers={'Cache-Control':'no-store'})
        if request.method not in ('GET','HEAD','OPTIONS') and request.url.path.startswith('/api/'):
            if request.headers.get('origin') != settings.origin:
                return JSONResponse({'detail':'Request origin was not accepted'},403)
            if not request.headers.get('content-type','').lower().startswith('application/json'):
                return JSONResponse({'detail':'JSON requests are required'},415)
        if settings.production and request.url.scheme != 'https':
            return JSONResponse({'detail':'HTTPS is required'},400)
        # Bound JSON uploads before parsing; no unbounded multipart/file uploads.
        if request.method in ('POST','PUT','PATCH'):
            async def read_body():
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body)>200000:
                        return None
                return bytes(body)
            try:
                body=await asyncio.wait_for(read_body(),timeout=10)
            except TimeoutError:
                return JSONResponse({'detail':'Upload timed out'},408)
            if body is None:
                return JSONResponse({'detail':'Request is too large'},413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update({
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'",
            'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Cache-Control':'no-store'
        })
        if settings.production:
            response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic errors can echo secrets and bodies; return only safe field locations/messages.
        return JSONResponse({'detail':[{'loc':list(e['loc']), 'msg':e['msg']} for e in exc.errors()]},422)

    @app.exception_handler(AIError)
    async def model_error(request, exc):
        return JSONResponse({'detail':str(exc)},503)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({'detail':'That record already exists or references an unavailable record'},409)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if exc.status_code in (401,403,429) and request.url.path.startswith('/api/'):
            route = getattr(request.scope.get('route'), 'path', '/api/unknown')
            store.event(getattr(request.state,'audit_actor','anonymous'),
                        'security.throttled' if exc.status_code==429 else 'security.denied',
                        code=exc.status_code,route=route)
        return JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers=exc.headers)

    def get_case(cid,user):
        row=store.case(cid,user)
        if not row:
            raise HTTPException(404,'Case not found')
        return row

    def peer(request):
        return request.client.host if request.client else 'unknown'

    @app.get('/health')
    @app.get('/api/health')
    def health():
        return {'status':'ok','application':'refundguard'}

    @app.get('/api/auth/status')
    def auth_status():
        return {'setup_required':not bool(store.one('SELECT id FROM rg_users LIMIT 1'))}

    @app.post('/api/auth/setup')
    def setup(body:Setup,request:Request,response:Response):
        throttle(store,'setup:'+peer(request),8)
        expected=store.bootstrap_token()
        if not expected or not hmac.compare_digest(expected,body.token):
            raise HTTPException(403,'Setup is unavailable or the setup key is invalid')
        validate_password(body.password)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT id FROM rg_users LIMIT 1').fetchone():
                raise HTTPException(409,'Workspace setup has already been completed')
            uid=create_user(db,body.email,body.name,body.password,'admin')
        (store.path.parent/'setup-token').unlink(missing_ok=True)
        user=store.one('SELECT * FROM rg_users WHERE id=?',(uid,))
        profile=store.profile_for_user(user)
        knowledge.sync_profile(profile['id'],index=False)
        csrf=new_session(store,uid,response,request.cookies.get(settings.cookie_name))
        store.event(uid,'auth.workspace_created')
        return {'user':public_user(user),'csrf':csrf}

    @app.post('/api/auth/login')
    def login(body:Login,request:Request,response:Response):
        throttle(store,'login-ip:'+peer(request),40)
        throttle(store,'login-account:'+body.email,8)
        user=store.one('SELECT * FROM rg_users WHERE email=?',(body.email,))
        valid=verify_password(user['password_hash'] if user else DUMMY_HASH,body.password)
        if not user or not valid or not user['active']:
            store.event('anonymous','auth.login_failed')
            raise HTTPException(401,'Email or password is incorrect')
        if PASSWORDS.check_needs_rehash(user['password_hash']):
            store.execute('UPDATE rg_users SET password_hash=? WHERE id=?',(hash_password(body.password),user['id']))
        csrf=new_session(store,user['id'],response,request.cookies.get(settings.cookie_name))
        store.event(user['id'],'auth.login')
        return {'user':public_user(user),'csrf':csrf}

    @app.post('/api/auth/accept-invite')
    def accept_invite(body:AcceptInvite,request:Request,response:Response):
        throttle(store,'invite:'+peer(request),12)
        validate_password(body.password)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            invite=db.execute('SELECT * FROM rg_invites WHERE token_hash=? AND used=0 AND expires>?',
                              (digest(body.token),time.time())).fetchone()
            if not invite:
                raise HTTPException(400,'This invitation has expired or has already been used')
            uid=create_user(db,invite['email'],invite['name'],body.password,invite['role'])
            db.execute('UPDATE rg_invites SET used=1 WHERE token_hash=?',(digest(body.token),))
        user=store.one('SELECT * FROM rg_users WHERE id=?',(uid,))
        profile=store.profile_for_user(user)
        knowledge.sync_profile(profile['id'],index=False)
        csrf=new_session(store,uid,response,request.cookies.get(settings.cookie_name))
        store.event(uid,'auth.invite_accepted')
        return {'user':public_user(user),'csrf':csrf}

    @app.post('/api/auth/team-invite-status')
    def team_invite_status(body:InviteToken,request:Request):
        throttle(store,'team-status:'+peer(request),30)
        invite=store.one('SELECT role,expires,max_uses,uses FROM rg_team_links WHERE token_hash=? AND revoked=0 AND expires>? AND uses<max_uses',
                         (digest(body.token),time.time()))
        if not invite:
            raise HTTPException(400,'This team invitation is expired, revoked or fully used')
        return {'valid':True,'role':invite['role'],'expires':invite['expires'],
                'remaining_signups':invite['max_uses']-invite['uses']}

    @app.post('/api/auth/accept-team-invite')
    def accept_team_invite(body:AcceptTeamInvite,request:Request,response:Response):
        throttle(store,'team-signup-ip:'+peer(request),12)
        throttle(store,'team-signup-token:'+digest(body.token),20)
        validate_password(body.password)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = db.execute('SELECT * FROM rg_team_links WHERE token_hash=? AND revoked=0 AND expires>? AND uses<max_uses',
                                (digest(body.token),time.time())).fetchone()
            if not invite:
                raise HTTPException(400,'This team invitation is expired, revoked or fully used')
            uid=create_user(db,body.email,body.name,body.password,invite['role'])
            db.execute('UPDATE rg_team_links SET uses=uses+1 WHERE token_hash=?',(digest(body.token),))
        user=store.one('SELECT * FROM rg_users WHERE id=?',(uid,))
        profile=store.profile_for_user(user)
        knowledge.sync_profile(profile['id'],index=False)
        csrf=new_session(store,uid,response,request.cookies.get(settings.cookie_name))
        store.event(uid,'auth.team_invite_accepted',role=invite['role'])
        return {'user':public_user(user),'csrf':csrf}

    @app.post('/api/team/links')
    def create_team_link(user=Depends(current_user)):
        require_role(user,'admin')
        throttle(store,'team-link-create:'+user['id'],4,3600)
        token=secrets.token_urlsafe(32)
        expires=time.time()+172800
        store.execute('INSERT INTO rg_team_links(token_hash,role,expires,max_uses,created_by) VALUES(?,?,?,?,?)',
                      (digest(token),'admin',expires,4,user['id']))
        store.event(user['id'],'team.admin_link_created',count=4)
        return {'url':settings.origin+'/#team-invite='+token,'expires':expires,'max_uses':4,'role':'admin'}

    @app.get('/api/team/links')
    def team_links(user=Depends(current_user)):
        require_role(user,'admin')
        return store.all('SELECT token_hash AS id,role,expires,max_uses,uses,revoked FROM rg_team_links ORDER BY expires DESC')

    @app.post('/api/team/links/{link_id}/revoke')
    def revoke_team_link(link_id:str,user=Depends(current_user)):
        require_role(user,'admin')
        store.execute('UPDATE rg_team_links SET revoked=1 WHERE token_hash=?',(link_id,))
        store.event(user['id'],'team.admin_link_revoked')
        return {'ok':True}

    @app.get('/api/auth/me')
    def me(user=Depends(current_user)):
        return {'user':public_user(user),'csrf':user['csrf'],'mode':models.mode,
                'embeddings':models.embedding_kind,'authority_active':store.authority_active(),
                'mfa_enabled':app.state.mfa.enabled(user['id']),
                'mfa_required':app.state.mfa.required(user) and not user['mfa_verified']}

    @app.get('/api/usage')
    def usage(user=Depends(current_user)):
        require_role(user,*STAFF)
        return {'provider':settings.provider,'model':settings.model,
                'reasoning_effort':settings.reasoning_effort,**budget.summary()}

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response,user=Depends(current_user)):
        store.execute('DELETE FROM rg_sessions WHERE token_hash=?',(digest(request.cookies.get(settings.cookie_name,'')),))
        response.delete_cookie(settings.cookie_name,path='/')
        store.event(user['id'],'auth.logout')
        return {'ok':True}

    @app.post('/api/auth/password')
    def password(body:PasswordInput,response:Response,user=Depends(current_user)):
        throttle(store,'password:'+user['id'],6)
        if not verify_password(user['password_hash'],body.current_password):
            raise HTTPException(400,'Current password is incorrect')
        validate_password(body.new_password)
        with store.connect() as db:
            db.execute('UPDATE rg_users SET password_hash=? WHERE id=?',(hash_password(body.new_password),user['id']))
            db.execute('DELETE FROM rg_sessions WHERE user_id=?',(user['id'],))
        csrf=new_session(store,user['id'],response)
        store.event(user['id'],'auth.password_changed')
        return {'csrf':csrf}

    @app.get('/api/team')
    def team(user=Depends(current_user)):
        require_role(user,*STAFF)
        return {'users':store.all('SELECT id,email,name,role,active,created_at FROM rg_users ORDER BY created_at'),
                'invites':store.all('SELECT email,name,role,expires,used FROM rg_invites ORDER BY expires DESC') if user['role']=='admin' else []}

    @app.post('/api/team/invites')
    def invite(body:Invitation,user=Depends(current_user)):
        require_role(user,'admin')
        throttle(store,'create-invite:'+user['id'],20,3600)
        if store.one('SELECT id FROM rg_users WHERE email=?',(body.email,)):
            raise HTTPException(409,'An account already exists for that email')
        token=secrets.token_urlsafe(32)
        expires=time.time()+172800
        with store.connect() as db:
            db.execute('UPDATE rg_invites SET used=1 WHERE email=?',(body.email,))
            db.execute('INSERT INTO rg_invites VALUES(?,?,?,?,?,?,?)',
                       (digest(token),body.email,body.name,body.role,expires,0,user['id']))
        store.event(user['id'],'team.invited',email=body.email,role=body.role)
        return {'url':settings.origin+'/#invite='+token,'expires':expires}

    @app.patch('/api/team/{uid}')
    def account_state(uid:str,body:ActiveInput,user=Depends(current_user)):
        require_role(user,'admin')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            target=db.execute('SELECT * FROM rg_users WHERE id=?',(uid,)).fetchone()
            if not target:
                raise HTTPException(404,'Account not found')
            if not body.active and target['role']=='admin' and db.execute("SELECT COUNT(*) FROM rg_users WHERE active=1 AND role='admin'").fetchone()[0]<=1:
                raise HTTPException(400,'The last active administrator cannot be disabled')
            db.execute('UPDATE rg_users SET active=? WHERE id=?',(int(body.active),uid))
            if not body.active:
                db.execute('DELETE FROM rg_sessions WHERE user_id=?',(uid,))
        store.event(user['id'],'team.account_state',target=uid,active=body.active)
        return {'ok':True}

    @app.get('/api/dashboard')
    def dashboard(user=Depends(current_user)):
        scope,params='',()
        if user['role']=='customer':
            profile=store.profile_for_user(user)
            scope,params=' WHERE customer_id=?',(profile['id'],)
        counts=store.all('SELECT status,COUNT(*) AS count FROM rg_cases'+scope+' GROUP BY status',params)
        now=datetime.now(timezone.utc)
        week=(now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        spent=store.one('SELECT COALESCE(SUM(amount_cents),0) AS amount FROM ledger WHERE processed_at>=?',(week.isoformat(),))['amount']
        events=store.all('SELECT * FROM rg_events ORDER BY id DESC LIMIT 7') if user['role']!='customer' else []
        return {'counts':{r['status']:r['count'] for r in counts},'weekly_spent_cents':spent if user['role']!='customer' else None,
                'weekly_limit_cents':50000,'transaction_limit_cents':10000,'authority_active':store.authority_active(),
                'mode':models.mode,'events':events,'embeddings':models.embedding_kind}

    @app.get('/api/profiles')
    def profiles(user=Depends(current_user)):
        if user['role']=='customer':
            store.profile_for_user(user)
            return store.all('SELECT p.*,c.balance_cents FROM rg_profiles p JOIN customers c ON c.id=p.id WHERE p.user_id=?',(user['id'],))
        return store.all('SELECT p.*,c.balance_cents FROM rg_profiles p JOIN customers c ON c.id=p.id ORDER BY p.name')

    @app.patch('/api/profiles/{profile_id}')
    def update_profile(profile_id:str,body:ProfileInput,user=Depends(current_user)):
        require_role(user,*STAFF)
        if not store.execute('UPDATE rg_profiles SET name=?,notes=? WHERE id=?',(body.name,body.notes,profile_id)):
            raise HTTPException(404,'Profile not found')
        store.event(user['id'],'profile.updated',customer_id=profile_id)
        knowledge.sync_profile(profile_id,index=False)
        return {'ok':True}

    @app.get('/api/orders')
    def orders(user=Depends(current_user)):
        scope,params='',()
        if user['role']=='customer':
            scope,params=' WHERE p.user_id=?',(user['id'],)
        return store.all('SELECT o.*,p.name AS customer_name,r.id AS case_id FROM rg_orders o JOIN rg_profiles p ON p.id=o.customer_id '
                         'LEFT JOIN rg_cases r ON r.order_id=o.id'+scope+' ORDER BY o.purchased_at DESC',params)

    @app.post('/api/orders')
    def add_order(body:OrderInput,user=Depends(current_user)):
        require_role(user,*STAFF)
        if not store.one('SELECT id FROM rg_profiles WHERE id=?',(body.customer_id,)):
            raise HTTPException(404,'Customer not found')
        oid='ORDER-'+uuid4().hex[:8].upper()
        store.execute('INSERT INTO rg_orders VALUES(?,?,?,?,?)',(oid,body.customer_id,body.product,body.amount_cents,
                      (datetime.now(timezone.utc)-timedelta(days=body.age_days)).isoformat()))
        store.event(user['id'],'sandbox.order_created',order_id=oid)
        return {'id':oid}

    @app.get('/api/cases')
    def list_cases(user=Depends(current_user)):
        rows=store.all('SELECT id FROM rg_cases ORDER BY created_at DESC')
        return [case for row in rows if (case:=store.case(row['id'],user))]

    @app.post('/api/cases')
    def add_case(body:CaseInput,user=Depends(current_user)):
        throttle(store,'case-create:'+user['id'],40,3600)
        try:
            case=store.create_case(user,body.order_id,body.amount_cents,body.reason_code,body.message)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None
        try:
            knowledge.add('Case '+case['id'],json.dumps({'case_id':case['id'],'request':body.model_dump()}),
                          'customer',case['customer_id'],user['id'],index=user['role'] in STAFF)
        except AIError:
            store.event(user['id'],'knowledge.index_failed',case['id'])
        return case

    @app.get('/api/cases/{cid}')
    def case_detail(cid:str,user=Depends(current_user)):
        case=get_case(cid,user)
        result={'case':case,'messages':store.all('SELECT * FROM rg_messages WHERE case_id=? ORDER BY created_at',(cid,))}
        if user['role']!='customer':
            result['traces']=store.all('SELECT * FROM rg_traces WHERE case_id=? ORDER BY id',(cid,))
            result['execution']=store.one('SELECT decision_json FROM ledger WHERE case_id=?',(cid,))
        else:
            result['messages']=[m for m in result['messages'] if m['direction']!='draft']
            result['case']={k:v for k,v in case.items() if k not in ('summary','run_id','created_by')}
        return result

    @app.post('/api/cases/{cid}/run')
    def run_case(cid:str,user=Depends(current_user)):
        require_role(user,*STAFF)
        get_case(cid,user)
        throttle(store,'run:'+user['id'],30,3600)
        try:
            return workflow.run(cid,user)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from None

    @app.post('/api/cases/{cid}/supervisor')
    def supervisor(cid:str,body:SupervisorInput,user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        case=get_case(cid,user)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT case_id FROM ledger WHERE case_id=?',(cid,)).fetchone():
                raise HTTPException(409,'This refund already executed. A later decision cannot reverse it.')
            db.execute('UPDATE cases SET supervisor=? WHERE id=?',(body.decision,cid))
            # Keep an active worker claim. It rechecks supervisor state at execution.
            status='denied' if body.decision=='denied' else 'review'
            db.execute("UPDATE rg_cases SET status=CASE WHEN status='processing' THEN status ELSE ? END,updated_at=? WHERE id=?",
                       (status,stamp(),cid))
        store.event(user['id'],'supervisor.decision',cid,decision=body.decision)
        return store.case(cid,user)

    @app.post('/api/cases/{cid}/messages')
    def receive_message(cid:str,body:MessageInput,user=Depends(current_user)):
        get_case(cid,user)
        throttle(store,'mail:'+user['id'],40,3600)
        store.execute('INSERT INTO rg_messages VALUES(?,?,?,?,?,?,?)',
                      (str(uuid4()),cid,'inbound',body.subject,body.body,'support@example.test',stamp()))
        store.event(user['id'],'email.received',cid)
        return {'ok':True}

    @app.get('/api/messages')
    def messages(user=Depends(current_user)):
        require_role(user,*STAFF)
        return store.all('SELECT m.*,p.name AS customer_name FROM rg_messages m JOIN rg_cases r ON r.id=m.case_id '
                         'JOIN rg_profiles p ON p.id=r.customer_id ORDER BY m.created_at DESC LIMIT 200')

    @app.get('/api/knowledge')
    def documents(user=Depends(current_user)):
        require_role(user,*STAFF)
        return store.all('SELECT d.id,d.title,d.kind,d.customer_id,d.version,d.active,d.created_at,d.content,d.created_by,d.review_status,d.approved_by,d.approved_at,'
                         '(SELECT COUNT(*) FROM rg_chunks c WHERE c.document_id=d.id) AS chunks '
                         'FROM rg_documents d ORDER BY d.created_at DESC')

    @app.post('/api/knowledge')
    def document(body:DocumentInput,user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        throttle(store,'document:'+user['id'],15,3600)
        if body.kind=='policy' and body.customer_id is not None:
            raise HTTPException(422,'Policy documents cannot have a customer scope')
        if body.kind=='customer' and not store.one('SELECT id FROM rg_profiles WHERE id=?',(body.customer_id,)):
            raise HTTPException(422,'Select an existing customer for customer documents')
        return {'id':knowledge.add(body.title,body.content,body.kind,body.customer_id,user['id'])}

    @app.post('/api/knowledge/{doc_id}/review')
    def review_policy(doc_id:str,body:PolicyReview,user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        throttle(store,'policy-review:'+user['id'],30,3600)
        try:
            return knowledge.review(doc_id,user['id'],body.action)
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from None

    @app.post('/api/knowledge/search')
    def search(body:SearchInput,user=Depends(current_user)):
        require_role(user,*STAFF)
        case=get_case(body.case_id,user)
        throttle(store,'search:'+user['id'],50,3600)
        return knowledge.search(body.query,case['customer_id'])

    @app.post('/api/authority')
    def authority(body:ActiveInput,user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        store.refunds.set_authority('refund-agent',body.active)
        store.event(user['id'],'authority.restored' if body.active else 'authority.revoked')
        return {'active':body.active}

    @app.get('/api/reports')
    def reports(user=Depends(current_user)):
        require_role(user,*STAFF)
        return {'cases':store.all('SELECT r.id,r.status,r.rationale,c.amount_cents,r.created_at FROM rg_cases r '
                                  'JOIN cases c ON c.id=r.id ORDER BY r.created_at DESC'),
                'decisions':store.all('SELECT * FROM audit ORDER BY timestamp DESC LIMIT 200'),
                'traces':store.all('SELECT * FROM rg_traces ORDER BY id DESC LIMIT 500'),
                'events':store.all('SELECT * FROM rg_events ORDER BY id DESC LIMIT 200'),
                'benchmarks':store.all('SELECT * FROM rg_benchmarks ORDER BY created_at DESC LIMIT 10')}

    @app.get('/api/reports/export')
    def export(user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        store.event(user['id'],'report.exported')
        return JSONResponse(reports(user),headers={'Content-Disposition':'attachment; filename="refundguard-evidence.json"'})

    @app.get('/api/security/alerts')
    def alerts(user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        return store.all('SELECT * FROM rg_alerts ORDER BY last_seen DESC LIMIT 200')

    @app.post('/api/security/alerts/{alert_id}/acknowledge')
    def acknowledge(alert_id:int,user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        if not store.execute('UPDATE rg_alerts SET acknowledged_by=?,acknowledged_at=? WHERE id=?',
                             (user['id'],stamp(),alert_id)):
            raise HTTPException(404,'Alert not found')
        return {'ok':True}

    @app.get('/api/security/export')
    def security_export(user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        throttle(store,'security-export:'+user['id'],6,3600)
        store.event(user['id'],'security.exported')
        return JSONResponse(signed_evidence(store),headers={'Content-Disposition':'attachment; filename="refundguard-security.json"'})

    @app.post('/api/benchmarks/run')
    def benchmark(user=Depends(current_user)):
        require_role(user,'admin','supervisor')
        throttle(store,'benchmark:'+user['id'],6,3600)
        from app.benchmarks import run_benchmarks
        result=run_benchmarks()
        bid=str(uuid4())
        store.execute('INSERT INTO rg_benchmarks VALUES(?,?,?,?)',(bid,stamp(),user['id'],json.dumps(result)))
        store.event(user['id'],'benchmark.completed',benchmark_id=bid)
        return result

    if STATIC.exists():
        app.mount('/static',StaticFiles(directory=STATIC),name='static')

    @app.get('/')
    def index():
        return FileResponse(STATIC/'index.html')

    return app

app=create_app()
