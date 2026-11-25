"""Red Team A9: a Customer session cannot use any Admin, Supervisor or staff route."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'redteam'))
import role_escalation  # noqa: E402
from test_application import account, workspace  # noqa: E402,F401


def _customer_case(app, admin, customer):
    profile = customer.get('/api/profiles').json()[0]['id']
    order = admin.post('/api/orders', json={'customer_id': profile, 'product': 'Escalation fixture',
                                            'amount_cents': 4000, 'age_days': 1})
    assert order.status_code == 200, order.text
    case = customer.post('/api/cases', json={'order_id': order.json()['id'], 'amount_cents': 4000,
                                             'reason_code': 'damaged', 'message': 'My lamp arrived damaged.'})
    assert case.status_code == 200, case.text
    return case.json()['id']


def _send(client, probe):
    method = getattr(client, probe['method'].lower())
    response = method(probe['path'], json=probe['body']) if probe['body'] is not None else method(probe['path'])
    body = response.json() if response.headers.get('content-type', '').startswith('application/json') else None
    return {**probe, 'status': response.status_code, 'detail': body.get('detail') if isinstance(body, dict) else None}


def _state(app):
    store = app.state.store
    one = lambda sql: store.one(sql)['n']
    return {
        'team_links': one('SELECT COUNT(*) AS n FROM rg_team_links'),
        'invites': one('SELECT COUNT(*) AS n FROM rg_invites'),
        'users': one("SELECT COUNT(*) AS n FROM rg_users WHERE active=1"),
        'documents': one('SELECT COUNT(*) AS n FROM rg_documents'),
        'ledger': one('SELECT COUNT(*) AS n FROM ledger'),
        'orders': one('SELECT COUNT(*) AS n FROM rg_orders'),
        'benchmarks': one('SELECT COUNT(*) AS n FROM rg_benchmarks'),
        'acknowledged': one('SELECT COUNT(*) AS n FROM rg_alerts WHERE acknowledged_by IS NOT NULL'),
        'case_states': store.all('SELECT id,status FROM rg_cases ORDER BY id'),
        'supervisor': store.all('SELECT id,supervisor FROM cases ORDER BY id'),
        'authority': store.authority_active(),
    }


def test_probe_list_matches_every_privileged_route():
    routes = role_escalation.privileged_routes()
    assert set(role_escalation.REQUESTS) == set(routes), 'stale or missing probe requests'
    assert len(role_escalation.probes()) == len(routes) >= 27
    # Spot-check the boundaries the threat model names.
    assert routes[('POST', '/api/team/invites')] == ('admin',)
    assert routes[('POST', '/api/authority')] == ('admin', 'supervisor')
    assert routes[('POST', '/api/cases/{cid}/supervisor')] == ('admin', 'supervisor')
    assert ('POST', '/api/cases/{cid}/messages') not in routes  # customers may write to their own case


def test_new_privileged_route_without_probe_is_reported(tmp_path, monkeypatch):
    extra = tmp_path / 'extra.py'
    extra.write_text("@app.post('/api/new-admin-tool')\ndef tool(user):\n    require_role(user, 'admin')\n")
    routes = role_escalation.privileged_routes([role_escalation.MAIN, extra])
    monkeypatch.setattr(role_escalation, 'privileged_routes', lambda: routes)
    with pytest.raises(KeyError, match='new-admin-tool'):
        role_escalation.probes()


def test_router_role_check_is_not_silently_skipped(tmp_path):
    router = tmp_path / 'router.py'
    router.write_text("@routes.post('/x')\ndef x(user):\n    require_role(user, 'admin')\n")
    with pytest.raises(ValueError, match='router'):
        role_escalation.privileged_routes([router])


def test_customer_session_gets_role_403_on_every_privileged_route(workspace):
    app, admin = workspace
    customer, _ = account(app, admin, 'customer')
    cid = _customer_case(app, admin, customer)
    before = _state(app)

    report = role_escalation.evaluate([_send(customer, p) for p in role_escalation.probes(cid)])

    failures = [(r['method'], r['route'], r['status'], r['detail']) for r in report['results'] if not r['pass']]
    assert report['all_pass'], failures
    assert report['probed'] == len(role_escalation.privileged_routes())
    assert _state(app) == before, 'a denied request changed state'
    # The customer's own routes still work, so the 403s are role decisions, not a broken session.
    assert customer.get('/api/cases/' + cid).status_code == 200
    assert customer.post('/api/cases/' + cid + '/messages',
                         json={'subject': 'Update', 'body': 'Any news?'}).status_code == 200


def test_staff_sessions_pass_the_role_check(workspace):
    """The same probes as an admin are not role-denied, so each one really reaches the check."""
    app, admin = workspace
    customer, _ = account(app, admin, 'customer')
    cid = _customer_case(app, admin, customer)
    safe = [p for p in role_escalation.probes(cid) if p['method'] == 'GET']
    for probe in safe:
        result = _send(admin, probe)
        assert result['detail'] != role_escalation.ROLE_DENIED, probe['route']


def test_only_the_role_message_counts_as_a_pass(workspace):
    app, admin = workspace
    customer, _ = account(app, admin, 'customer')
    customer.headers.pop('X-CSRF-Token')
    probe = next(p for p in role_escalation.probes() if p['route'] == '/api/authority')
    result = role_escalation.evaluate([_send(customer, probe)])
    assert result['results'][0]['status'] == 403
    assert not result['all_pass'], 'a CSRF 403 must not be scored as a role-check pass'
