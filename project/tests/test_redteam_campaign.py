"""Exercise the campaign command and its persisted evidence, including a bad run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / 'project/redteam/run_campaign.py'


def test_redteam_command_writes_synthetic_evidence_without_opening_configured_db(tmp_path):
    output = tmp_path / 'campaign.json'
    protected_db = tmp_path / 'must-not-be-opened.sqlite3'
    environ = {**os.environ, 'DATABASE_PATH': str(protected_db),
               'APP_ENV': 'production', 'APP_ORIGIN': 'https://unused.example.test',
               'AI_PROVIDER': 'openai', 'OPENAI_API_KEY': 'fake-campaign-key-never-export'}
    completed = subprocess.run(
        [sys.executable, str(CAMPAIGN), '--out', str(output)],
        cwd=ROOT, env=environ, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    report = json.loads(output.read_text())
    assert not protected_db.exists()
    assert 'fake-campaign-key-never-export' not in output.read_text()
    assert report['mode'] == 'Local simulation'
    assert report['provider_usage']['requests_this_month'] == 0
    assert report['all_passed'] is True
    scenarios = {scenario['id']: scenario for scenario in report['scenarios']}
    assert set(scenarios) == {'normal', 'direct-injection', 'indirect-injection',
                              'expired-injection', 'revocation', 'replay'}
    for scenario in scenarios.values():
        assert scenario['joint_pass'] is True
        assert all(scenario['checks'].values())
    assert scenarios['direct-injection']['ledger_entries'] == 0
    assert scenarios['direct-injection']['balance_cents'] == 0
    assert scenarios['direct-injection']['independent_controls'][0]['reason'] == 'transaction_limit'
    assert scenarios['replay']['http_statuses'] == [200, 200]
    assert scenarios['replay']['ledger_entries'] == 1
    assert scenarios['indirect-injection']['attack_document_id']
    assert report['source_sha256']['project/redteam/run_campaign.py'] == hashlib.sha256(CAMPAIGN.read_bytes()).hexdigest()


def test_redteam_command_fails_and_keeps_evidence_when_workflow_does_nothing(tmp_path):
    output = tmp_path / 'failed-campaign.json'
    # Reproduce a broken application that returns HTTP 200 without running agents.
    # A security-only oracle could mistake zero spending for a successful test.
    script = '''
import runpy, sys
from unittest.mock import patch
campaign = runpy.run_path(sys.argv[1])
original = campaign['create_app']
def broken(settings):
    app = original(settings)
    app.state.workflow.run = lambda *args: None
    return app
with patch.dict(campaign['run'].__globals__, {'create_app': broken}):
    raise SystemExit(campaign['main'](['--out', sys.argv[2]]))
'''
    completed = subprocess.run(
        [sys.executable, '-c', script, str(CAMPAIGN), str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 1, completed.stderr + completed.stdout
    report = json.loads(output.read_text())
    assert report['all_passed'] is False
    assert report['joint_pass_rate'] == 0
    indirect = next(s for s in report['scenarios'] if s['id'] == 'indirect-injection')
    assert indirect['checks']['attack_delivered'] is False
    assert indirect['functional_pass'] is False
