"""Trusted, transactional mock refund execution.

The application authenticates callers and resolves case ownership before calling
this tool. The optional trusted eligibility callback is rechecked under the same
write lock as authority, supervisor state, ledger and balance mutation.
Money is integer cents. The provisional budget is organization-wide and uses
Monday 00:00 UTC calendar weeks; confirm that interpretation with the instructor.
"""

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import uuid4


@dataclass(frozen=True)
class Decision:
    decision_id: str
    status: str
    reason: str
    case_id: str
    amount_cents: int


class RefundService:
    def __init__(self, database, clock=None, eligibility_check=None):
        self.database = str(database)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.eligibility_check = eligibility_check
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS authority (
                    agent_id TEXT PRIMARY KEY, active INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL REFERENCES customers(id),
                    agent_id TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    supervisor TEXT NOT NULL DEFAULT 'none'
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    case_id TEXT PRIMARY KEY REFERENCES cases(id),
                    amount_cents INTEGER NOT NULL,
                    processed_at TEXT NOT NULL,
                    decision_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    decision_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    decision_json TEXT NOT NULL
                );
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys = ON')
            with db:
                yield db
        finally:
            db.close()

    def set_authority(self, agent_id, active):
        """Trusted supervisor operation; never expose as an agent tool."""
        if type(active) is not bool:
            raise ValueError('active must be a boolean')
        with self._connect() as db:
            db.execute('INSERT OR REPLACE INTO authority VALUES (?, ?)',
                       (agent_id, int(active)))

    def register_case(self, case_id, customer_id, agent_id, amount_cents):
        """Trusted intake operation; assignment/identity checks belong upstream."""
        if type(amount_cents) is not int or amount_cents <= 0:
            raise ValueError('amount must be positive integer cents')
        if not all(isinstance(v, str) and v.strip()
                   for v in (case_id, customer_id, agent_id)):
            raise ValueError('case, customer and agent IDs must be nonempty strings')
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO customers(id) VALUES (?)', (customer_id,))
            db.execute('INSERT INTO cases(id, customer_id, agent_id, amount_cents) '
                       'VALUES (?, ?, ?, ?)', (case_id, customer_id, agent_id, amount_cents))

    def set_supervisor_decision(self, case_id, decision):
        """Trusted supervisor operation; approval does not bypass autonomous caps."""
        if decision not in ('none', 'pending', 'approved', 'denied'):
            raise ValueError('invalid supervisor decision')
        with self._connect() as db:
            if db.execute('UPDATE cases SET supervisor = ? WHERE id = ?',
                          (decision, case_id)).rowcount != 1:
                raise ValueError('unknown case')

    def process(self, agent_id, case_id):
        """Enforce current authority and assignment at the execution boundary.

        BEGIN IMMEDIATE serializes ledger reads and balance writes across workers,
        preventing concurrent requests from spending the same remaining budget.
        Repeated case execution returns its original result without another credit.
        """
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('clock must return a timezone-aware datetime')
        now = now.astimezone(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            case = db.execute('SELECT * FROM cases WHERE id = ?', (case_id,)).fetchone()
            auth = db.execute('SELECT active FROM authority WHERE agent_id = ?',
                              (agent_id,)).fetchone()
            # Do not return case details to an unassigned or revoked caller.
            if not auth or not auth['active']:
                reason = 'authority_inactive'
            elif not case or case['agent_id'] != agent_id:
                reason = 'case_not_assigned'
            elif case['supervisor'] in ('pending', 'denied'):
                reason = 'supervisor_' + case['supervisor']
            elif self.eligibility_check and not self.eligibility_check(case_id)[0]:
                reason = 'eligibility_failed'
            else:
                existing = db.execute('SELECT decision_json FROM ledger WHERE case_id = ?',
                                      (case_id,)).fetchone()
                if existing:
                    return Decision(**json.loads(existing['decision_json']))
                spent = db.execute('SELECT COALESCE(SUM(amount_cents), 0) FROM ledger '
                                   'WHERE processed_at >= ? AND processed_at < ?',
                                   (week_start.isoformat(),
                                    (week_start + timedelta(days=7)).isoformat())).fetchone()[0]
                if case['amount_cents'] > 10000:
                    reason = 'transaction_limit'
                elif spent + case['amount_cents'] > 50000:
                    reason = 'weekly_limit'
                else:
                    reason = 'within_limits'
            amount = case['amount_cents'] if reason not in (
                'authority_inactive', 'case_not_assigned') else 0
            result = Decision(str(uuid4()), 'processed' if reason == 'within_limits'
                              else 'blocked', reason, case_id, amount)
            serialized = json.dumps(asdict(result))
            if result.status == 'processed':
                db.execute('INSERT INTO ledger VALUES (?, ?, ?, ?)',
                           (case_id, amount, now.isoformat(), serialized))
                db.execute('UPDATE customers SET balance_cents = balance_cents + ? '
                           'WHERE id = ?', (amount, case['customer_id']))
            db.execute('INSERT INTO audit VALUES (?, ?, ?, ?)',
                       (result.decision_id, now.isoformat(), agent_id, serialized))
            return result

    def balance(self, customer_id):
        """Trusted test/admin inspection, not a public customer lookup endpoint."""
        with self._connect() as db:
            row = db.execute('SELECT balance_cents FROM customers WHERE id = ?',
                             (customer_id,)).fetchone()
            return row['balance_cents'] if row else None
