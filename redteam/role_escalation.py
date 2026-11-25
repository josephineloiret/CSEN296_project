"""Red Team scenario A9: a Customer session must get 403 on every privileged route.

The privileged routes are discovered from app/main.py, not hand-listed: any route
whose handler calls ``require_role`` without allowing ``customer``. A route added
later is therefore probed automatically, and ``probes()`` fails until it has a
request body here, so coverage cannot silently fall behind the API.

Each probe sends a schema-valid body so FastAPI validation (422) cannot mask the
role check, and passes only when the response is 403 with the role-check message.
A 403 for a different reason (missing CSRF token, MFA, guest allowlist) does not
count. Probe values are chosen to be harmless if a check were missing: placeholder
IDs, reserved ``.example`` addresses, and ``active: true`` for agent authority.

Run ``python redteam/role_escalation.py`` to print the probe list as JSON, for
replaying it against the hosted site from a signed-in Customer browser session.
"""
import ast
import json
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / 'app' / 'main.py'
ROLE_DENIED = 'Your account does not have permission for this action'
ROLE_GROUPS = {'STAFF': ('admin', 'supervisor', 'member'), 'REVIEWERS': ('admin', 'supervisor')}
METHODS = {'get', 'post', 'put', 'patch', 'delete'}

CASE = 'RG-00000000'
UID = '00000000-0000-0000-0000-000000000000'

# Request for each privileged route: (concrete path, JSON body or None).
# {case} is replaced with a case ID when the caller has one (the customer's own case).
REQUESTS = {
    ('POST', '/api/team/links'): ('/api/team/links', None),
    ('GET', '/api/team/links'): ('/api/team/links', None),
    ('POST', '/api/team/links/{link_id}/revoke'): ('/api/team/links/' + '0' * 64 + '/revoke', None),
    ('GET', '/api/usage'): ('/api/usage', None),
    ('GET', '/api/team'): ('/api/team', None),
    ('POST', '/api/team/invites'): ('/api/team/invites', {
        'email': 'escalation-probe@refundguard.example', 'name': 'Escalation probe', 'role': 'admin'}),
    ('PATCH', '/api/team/{uid}'): ('/api/team/' + UID, {'active': True}),
    ('PATCH', '/api/profiles/{profile_id}'): ('/api/profiles/demo-probe', {'name': 'Probe', 'notes': ''}),
    ('POST', '/api/orders'): ('/api/orders', {
        'customer_id': 'demo-probe', 'product': 'Escalation probe', 'amount_cents': 100, 'age_days': 0}),
    ('PUT', '/api/cases/{cid}/files/assignment'): ('/api/cases/{case}/files/assignment', {'user_id': None}),
    ('POST', '/api/cases/{cid}/files/import'): ('/api/cases/{case}/files/import', {'source': 'escalation-probe'}),
    ('POST', '/api/cases/{cid}/files/search'): ('/api/cases/{case}/files/search', {'query': 'probe'}),
    ('POST', '/api/cases/{cid}/run'): ('/api/cases/{case}/run', None),
    ('POST', '/api/cases/{cid}/supervisor'): ('/api/cases/{case}/supervisor', {'decision': 'approved'}),
    ('POST', '/api/cases/{cid}/messages/{mid}/review'): (
        '/api/cases/{case}/messages/' + UID + '/review', {'body': 'probe', 'reason': 'probe'}),
    ('GET', '/api/messages'): ('/api/messages', None),
    ('GET', '/api/knowledge'): ('/api/knowledge', None),
    ('POST', '/api/knowledge'): ('/api/knowledge', {
        'title': 'Escalation probe', 'content': 'Escalation probe policy text.', 'kind': 'policy'}),
    ('POST', '/api/knowledge/{doc_id}/review'): ('/api/knowledge/DOC-0000000000/review', {'action': 'publish'}),
    ('POST', '/api/knowledge/search'): ('/api/knowledge/search', {'query': 'probe', 'case_id': '{case}'}),
    ('POST', '/api/authority'): ('/api/authority', {'active': True}),
    ('GET', '/api/reports'): ('/api/reports', None),
    ('GET', '/api/reports/export'): ('/api/reports/export', None),
    ('GET', '/api/security/alerts'): ('/api/security/alerts', None),
    ('POST', '/api/security/alerts/{alert_id}/acknowledge'): ('/api/security/alerts/0/acknowledge', None),
    ('GET', '/api/security/export'): ('/api/security/export', None),
    ('POST', '/api/benchmarks/run'): ('/api/benchmarks/run', None),
}


def _roles(call):
    roles = []
    for arg in call.args[1:]:
        if isinstance(arg, ast.Constant):
            roles.append(arg.value)
        elif isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
            roles.extend(ROLE_GROUPS[arg.value.id])
    return tuple(roles)


def privileged_routes(sources=None):
    """{(METHOD, path): allowed roles} for every route a Customer may not use.

    Scans every module in app/. Routes registered on an APIRouter (not ``app``)
    carry a prefix this scan cannot resolve, so a role check on one raises
    instead of being skipped.
    """
    found = {}
    for source in sources or sorted(MAIN.parent.glob('*.py')):
        for node in ast.walk(ast.parse(Path(source).read_text())):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = [d for d in node.decorator_list
                          if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                          and d.func.attr in METHODS and d.args and isinstance(d.args[0], ast.Constant)]
            checks = [_roles(c) for c in ast.walk(node) if isinstance(c, ast.Call)
                      and isinstance(c.func, ast.Name) and c.func.id == 'require_role']
            allowed = tuple(sorted({r for roles in checks for r in roles}))
            if not decorators or not checks or 'customer' in allowed:
                continue
            for d in decorators:
                if not (isinstance(d.func.value, ast.Name) and d.func.value.id == 'app'):
                    raise ValueError(f'{Path(source).name}:{node.name} has a role check on a router; '
                                     'add its full path to the role-escalation probes')
                found[(d.func.attr.upper(), d.args[0].value)] = allowed
    return found


def probes(case_id=CASE):
    """Concrete requests for every discovered privileged route."""
    routes = privileged_routes()
    missing = sorted(set(routes) - set(REQUESTS))
    if missing:
        raise KeyError(f'Add a probe request for new privileged routes: {missing}')
    result = []
    for (method, route), allowed in sorted(routes.items(), key=lambda item: (item[0][1], item[0][0])):
        path, body = REQUESTS[(method, route)]
        if body is None and method != 'GET':
            body = {}  # writes must be JSON (415 otherwise), as the UI sends them
        if body:
            body = {k: (case_id if v == '{case}' else v) for k, v in body.items()}
        result.append({'method': method, 'route': route, 'path': path.replace('{case}', case_id),
                       'body': body, 'allowed_roles': list(allowed)})
    return result


def evaluate(responses):
    """responses: probes() entries plus 'status' and 'detail'. Pass only on the role 403."""
    rows = [{**r, 'pass': r['status'] == 403 and r.get('detail') == ROLE_DENIED} for r in responses]
    return {'probed': len(rows), 'passed': sum(r['pass'] for r in rows),
            'all_pass': bool(rows) and all(r['pass'] for r in rows), 'results': rows}


if __name__ == '__main__':
    print(json.dumps(probes()))
