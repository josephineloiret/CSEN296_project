"""Run the initial refund-control slice using synthetic data and a temporary DB."""
from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.refunds import RefundService


def main():
    with TemporaryDirectory() as directory:
        service = RefundService(Path(directory) / 'demo.sqlite3')
        service.set_authority('refund-agent', True)
        for case_id, amount in [('case-75', 7500), ('case-101', 10100), ('case-revoked', 2500)]:
            service.register_case(case_id, 'synthetic-customer', 'refund-agent', amount)
        decisions = [service.process('refund-agent', 'case-75'),
                     service.process('refund-agent', 'case-101')]
        service.set_authority('refund-agent', False)
        decisions.append(service.process('refund-agent', 'case-revoked'))
        print(json.dumps({'decisions': [asdict(d) for d in decisions],
                          'mock_balance_cents': service.balance('synthetic-customer')}, indent=2))


if __name__ == '__main__':
    main()
