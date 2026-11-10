from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from app.refunds import RefundService


class RefundTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        self.path = Path(self.directory.name) / 'refunds.sqlite3'
        self.service = RefundService(self.path, clock=lambda: self.now)
        self.service.set_authority('agent', True)

    def case(self, name, amount=10000, customer='customer'):
        self.service.register_case(name, customer, 'agent', amount)

    def test_exact_transaction_cap_is_allowed(self):
        self.case('a')
        self.assertEqual(self.service.process('agent', 'a').status, 'processed')
        self.assertEqual(self.service.balance('customer'), 10000)

    def test_over_transaction_cap_has_no_balance_effect(self):
        self.case('a', 10001)
        self.assertEqual(self.service.process('agent', 'a').reason, 'transaction_limit')
        self.assertEqual(self.service.balance('customer'), 0)

    def test_weekly_cap_is_global_across_customers_and_agents(self):
        self.service.set_authority('agent2', True)
        for i in range(5):
            self.case(str(i), customer=str(i))
            self.assertEqual(self.service.process('agent', str(i)).status, 'processed')
        self.service.register_case('extra', 'other', 'agent2', 1)
        self.assertEqual(self.service.process('agent2', 'extra').reason, 'weekly_limit')
        self.assertEqual(self.service.balance('other'), 0)

    def test_week_rollover(self):
        for i in range(5):
            self.case(str(i))
            self.service.process('agent', str(i))
        self.now = datetime(2026, 10, 26, tzinfo=timezone.utc) - timedelta(microseconds=1)
        self.case('next', 1)
        self.assertEqual(self.service.process('agent', 'next').reason, 'weekly_limit')
        self.now += timedelta(microseconds=1)
        self.assertEqual(self.service.process('agent', 'next').status, 'processed')

    def test_revocation_survives_service_restart(self):
        self.case('a')
        self.service.set_authority('agent', False)
        restarted = RefundService(self.path)
        self.assertEqual(restarted.process('agent', 'a').reason, 'authority_inactive')
        self.assertEqual(restarted.balance('customer'), 0)

    def test_missing_authority_fails_closed(self):
        self.case('a')
        self.assertEqual(self.service.process('unknown-agent', 'a').reason, 'authority_inactive')

    def test_supervisor_denial_and_pending_block_execution(self):
        for decision in ('denied', 'pending'):
            self.case(decision)
            self.service.set_supervisor_decision(decision, decision)
            self.assertEqual(self.service.process('agent', decision).reason, 'supervisor_' + decision)
        self.assertEqual(self.service.balance('customer'), 0)

    def test_supervisor_approval_cannot_bypass_autonomous_cap(self):
        self.case('a', 10001)
        self.service.set_supervisor_decision('a', 'approved')
        self.assertEqual(self.service.process('agent', 'a').reason, 'transaction_limit')

    def test_assignment_is_enforced(self):
        self.case('a')
        self.service.set_authority('other', True)
        result = self.service.process('other', 'a')
        self.assertEqual(result.reason, 'case_not_assigned')
        self.assertEqual(result.amount_cents, 0)
        self.assertEqual(self.service.balance('customer'), 0)

    def test_unknown_case_fails_closed(self):
        self.assertEqual(self.service.process('agent', 'missing').reason, 'case_not_assigned')

    def test_duplicate_case_is_credited_once(self):
        self.case('a', 2500)
        first = self.service.process('agent', 'a')
        self.assertEqual(first, self.service.process('agent', 'a'))
        self.assertEqual(self.service.balance('customer'), 2500)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0], 1)

    def test_duplicate_after_revocation_is_blocked(self):
        self.case('a')
        self.service.process('agent', 'a')
        self.service.set_authority('agent', False)
        self.assertEqual(self.service.process('agent', 'a').reason, 'authority_inactive')
        self.assertEqual(self.service.balance('customer'), 10000)

    def test_invalid_amounts_rejected_at_intake(self):
        for amount in (0, -1, 1.1, True, '100', float('nan')):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.case('a', amount)

    def test_concurrent_refunds_cannot_exceed_budget(self):
        for i in range(6):
            self.case(str(i))
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda i: self.service.process('agent', str(i)), range(6)))
        self.assertEqual(sum(r.status == 'processed' for r in results), 5)
        self.assertEqual(sum(r.reason == 'weekly_limit' for r in results), 1)
        self.assertEqual(self.service.balance('customer'), 50000)

    def test_audit_explains_executed_and_blocked_decisions(self):
        self.case('a')
        self.case('b', 10001)
        approved = self.service.process('agent', 'a')
        blocked = self.service.process('agent', 'b')
        with sqlite3.connect(self.path) as db:
            ids = {r[0] for r in db.execute('SELECT decision_id FROM audit')}
        self.assertEqual(ids, {approved.decision_id, blocked.decision_id})


if __name__ == '__main__':
    unittest.main()
