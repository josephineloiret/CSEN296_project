from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4
import sqlite_vec
from app.refunds import RefundService

def stamp():
    return datetime.now(timezone.utc).isoformat()

SCHEMA = '''
CREATE TABLE IF NOT EXISTS rg_users (
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','supervisor','member','customer')),
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES rg_users(id),
 csrf TEXT NOT NULL, created REAL NOT NULL, touched REAL NOT NULL, expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_invites (
 token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL,
 expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_rate_limits (key TEXT PRIMARY KEY, hits INTEGER NOT NULL, resets REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rg_profiles (
 id TEXT PRIMARY KEY, user_id TEXT UNIQUE REFERENCES rg_users(id), name TEXT NOT NULL,
 email TEXT NOT NULL, bank_ref TEXT NOT NULL, notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS rg_orders (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES rg_profiles(id),
 product TEXT NOT NULL, amount_cents INTEGER NOT NULL, purchased_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_cases (
 id TEXT PRIMARY KEY REFERENCES cases(id), customer_id TEXT NOT NULL REFERENCES rg_profiles(id),
 order_id TEXT UNIQUE NOT NULL REFERENCES rg_orders(id), reason_code TEXT NOT NULL,
 message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', rationale TEXT NOT NULL DEFAULT '',
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 summary TEXT NOT NULL DEFAULT '', run_id TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rg_documents (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('policy','customer')),
 customer_id TEXT REFERENCES rg_profiles(id), content TEXT NOT NULL, version INTEGER NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_chunks (
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES rg_documents(id),
 chunk_no INTEGER NOT NULL, content TEXT NOT NULL, embedding BLOB NOT NULL, embedding_kind TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_messages (
 id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES rg_cases(id),
 direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound','draft')),
 subject TEXT NOT NULL, body TEXT NOT NULL, recipient TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_events (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
 case_id TEXT, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_traces (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL REFERENCES rg_cases(id),
 agent TEXT NOT NULL, operation TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_benchmarks (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, created_by TEXT NOT NULL, results TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rg_ai_requests (
 id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, endpoint TEXT NOT NULL, model TEXT NOT NULL,
 reserved_micros INTEGER NOT NULL, actual_micros INTEGER, input_tokens INTEGER,
 output_tokens INTEGER, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rg_mfa (
 user_id TEXT PRIMARY KEY REFERENCES rg_users(id), secret TEXT, pending TEXT,
 pending_until REAL NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 0,
 last_counter INTEGER NOT NULL DEFAULT -1, recovery TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS rg_alerts (
 id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, severity TEXT NOT NULL,
 action TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
 occurrences INTEGER NOT NULL DEFAULT 1, acknowledged_by TEXT, acknowledged_at TEXT
);
CREATE TABLE IF NOT EXISTS rg_team_links (
 token_hash TEXT PRIMARY KEY, role TEXT NOT NULL, expires REAL NOT NULL,
 max_uses INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0,
 created_by TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
);
'''

class Store:
    def __init__(self, settings):
        self.settings = settings
        self.path = Path(settings.database)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.refunds = RefundService(self.path)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
            if 'mfa_verified' not in {r['name'] for r in db.execute('PRAGMA table_info(rg_sessions)')}:
                db.execute('ALTER TABLE rg_sessions ADD COLUMN mfa_verified INTEGER NOT NULL DEFAULT 0')
            if 'review_status' not in {r['name'] for r in db.execute('PRAGMA table_info(rg_documents)')}:
                db.execute("ALTER TABLE rg_documents ADD COLUMN review_status TEXT NOT NULL DEFAULT 'approved'")
                db.execute('ALTER TABLE rg_documents ADD COLUMN approved_by TEXT')
                db.execute('ALTER TABLE rg_documents ADD COLUMN approved_at TEXT')
                # Existing human-uploaded policies must pass the new review gate.
                db.execute("UPDATE rg_documents SET active=0,review_status='pending' WHERE kind='policy' AND created_by<>'system'")
        os.chmod(self.path, 0o600)
        self.refunds.set_authority('refund-agent', self.authority_active())
        self.refunds.eligibility_check = self.eligibility
        if settings.team_invite_hash:
            self.execute('INSERT OR IGNORE INTO rg_team_links(token_hash,role,expires,max_uses,created_by) VALUES(?,?,?,?,?)',
                         (settings.team_invite_hash,'admin',settings.team_invite_expires,4,'hosting-operator'))

    @contextmanager
    def connect(self, vector=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            if vector:
                db.enable_load_extension(True)
                sqlite_vec.load(db)
                db.enable_load_extension(False)
            with db:
                yield db
        finally:
            db.close()

    def one(self, sql, params=()):
        with self.connect() as db:
            row = db.execute(sql, params).fetchone()
            return dict(row) if row else None

    def all(self, sql, params=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, params).fetchall()]

    def execute(self, sql, params=()):
        with self.connect() as db:
            return db.execute(sql, params).rowcount

    def event(self, actor, action, case_id=None, **details):
        from app.monitoring import sanitized, record_alert, emit_event
        details = sanitized(details)
        self.execute('INSERT INTO rg_events(timestamp,actor,action,case_id,details) VALUES(?,?,?,?,?)',
                     (stamp(), actor, action, case_id, json.dumps(details)))
        record_alert(self, actor, action)
        emit_event(self, actor, action, case_id, details)

    def trace(self, run_id, case_id, agent, operation, result):
        self.execute('INSERT INTO rg_traces(run_id,case_id,agent,operation,result,created_at) VALUES(?,?,?,?,?,?)',
                     (run_id, case_id, agent, operation, json.dumps(result), stamp()))

    def authority_active(self):
        row = self.one('SELECT active FROM authority WHERE agent_id=?', ('refund-agent',))
        return bool(row['active']) if row else True

    def bootstrap_token(self):
        path = self.path.parent / 'setup-token'
        if self.one('SELECT id FROM rg_users LIMIT 1'):
            return None
        if not path.exists():
            import secrets
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as f:
                f.write(secrets.token_urlsafe(32))
        return path.read_text().strip()

    def profile_for_user(self, user):
        existing = self.one('SELECT * FROM rg_profiles WHERE user_id=?', (user['id'],))
        if existing:
            return existing
        profile_id = 'cust-' + uuid4().hex[:12]
        with self.connect() as db:
            db.execute('INSERT INTO rg_profiles VALUES(?,?,?,?,?,?)',
                       (profile_id, user['id'], user['name'], user['email'], 'MOCK-' + uuid4().hex[:8], 'Synthetic customer profile'))
            db.execute('INSERT OR IGNORE INTO customers(id) VALUES(?)', (profile_id,))
            db.execute('INSERT INTO rg_orders VALUES(?,?,?,?,?)',
                       ('ORDER-' + uuid4().hex[:8].upper(), profile_id, 'Demo headphones', 7500, stamp()))
        return self.one('SELECT * FROM rg_profiles WHERE id=?', (profile_id,))

    def seed(self):
        with self.connect() as db:
            if db.execute("SELECT value FROM rg_meta WHERE key='fixtures'").fetchone():
                return
            for name, product, amount, days in [('Maya Chen','Wireless headphones',7500,5),
                                               ('Sam Rivera','Mechanical keyboard',12500,7),
                                               ('Jordan Park','USB-C hub',4000,40)]:
                profile_id = 'demo-' + name.split()[0].lower()
                db.execute('INSERT INTO rg_profiles VALUES(?,?,?,?,?,?)',
                           (profile_id, None, name, name.split()[0].lower() + '@example.test',
                            'MOCK-' + profile_id.upper(), 'Synthetic demo customer'))
                db.execute('INSERT OR IGNORE INTO customers(id) VALUES(?)', (profile_id,))
                db.execute('INSERT INTO rg_orders VALUES(?,?,?,?,?)',
                           ('DEMO-' + name.split()[0].upper(), profile_id, product, amount,
                            (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()))
            db.execute("INSERT INTO rg_meta VALUES('fixtures','1')")

    def case(self, case_id, user):
        row = self.one('SELECT r.*, c.amount_cents, c.supervisor, p.name AS customer_name, '
                       'p.email AS customer_email, o.product FROM rg_cases r '
                       'JOIN cases c ON c.id=r.id JOIN rg_profiles p ON p.id=r.customer_id '
                       'JOIN rg_orders o ON o.id=r.order_id WHERE r.id=?', (case_id,))
        if row and user['role'] == 'customer':
            profile = self.one('SELECT id FROM rg_profiles WHERE user_id=?', (user['id'],))
            if not profile or row['customer_id'] != profile['id']:
                return None
        return row

    def create_case(self, user, order_id, amount_cents, reason_code, message):
        case_id = 'RG-' + uuid4().hex[:8].upper()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            order = db.execute('SELECT o.*, p.user_id FROM rg_orders o JOIN rg_profiles p '
                               'ON p.id=o.customer_id WHERE o.id=?', (order_id,)).fetchone()
            if not order or (user['role']=='customer' and order['user_id'] != user['id']):
                raise ValueError('Order not found')
            if amount_cents > order['amount_cents']:
                raise ValueError('Requested amount exceeds the order total')
            if db.execute('SELECT id FROM rg_cases WHERE order_id=?', (order_id,)).fetchone():
                raise ValueError('A case already exists for this order')
            db.execute('INSERT INTO cases(id,customer_id,agent_id,amount_cents) VALUES(?,?,?,?)',
                       (case_id, order['customer_id'], 'refund-agent', amount_cents))
            db.execute('INSERT INTO rg_cases(id,customer_id,order_id,reason_code,message,created_by,created_at,updated_at) '
                       'VALUES(?,?,?,?,?,?,?,?)', (case_id, order['customer_id'], order_id, reason_code,
                                                  message, user['id'], stamp(), stamp()))
            db.execute('INSERT INTO rg_messages VALUES(?,?,?,?,?,?,?)',
                       (str(uuid4()), case_id, 'inbound', 'Refund request ' + case_id, message,
                        'support@example.test', stamp()))
        self.event(user['id'], 'case.created', case_id, order_id=order_id)
        return self.case(case_id, user)

    def eligibility(self, case_id):
        row = self.one('SELECT r.reason_code,r.customer_id,r.order_id,c.amount_cents,o.amount_cents AS paid, '
                       'o.purchased_at,o.customer_id AS order_owner FROM rg_cases r JOIN cases c ON c.id=r.id '
                       'JOIN rg_orders o ON o.id=r.order_id WHERE r.id=?', (case_id,))
        if not row or row['customer_id'] != row['order_owner']:
            return False, 'Order ownership could not be verified'
        if row['amount_cents'] > row['paid']:
            return False, 'Requested amount exceeds the original purchase'
        age = datetime.now(timezone.utc)-datetime.fromisoformat(row['purchased_at'])
        if age > timedelta(days=30) or age < timedelta(0):
            return False, 'Purchase is outside the 30-day refund window'
        if row['reason_code'] not in ('damaged','not_received','wrong_item'):
            return False, 'This reason requires supervisor review'
        return True, 'Verified purchase, covered reason and within the 30-day window'
