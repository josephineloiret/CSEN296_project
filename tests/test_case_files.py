"""Drive import and Records access through the normal case endpoints."""
import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from io import BytesIO
import json
from threading import Barrier
from urllib.parse import parse_qs
from unittest.mock import patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from urllib3.response import HTTPResponse

from app.config import Settings
from app.drive_files import DriveFileError, DriveFiles, READ_SCOPE, TOKEN_URL
from test_application import account, make_case, workspace

FOLDER = 'demo-folder'
SOURCE = 'demo-drive-pdf'
MARKER = 'case_file_marker_713'
CASE_TEXT = f'The synthetic customer attached a damaged headphones receipt. {MARKER}'


def make_pdf(text='', encrypt=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    if text:
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({
                NameObject('/F1'): DictionaryObject({
                    NameObject('/Type'): NameObject('/Font'),
                    NameObject('/Subtype'): NameObject('/Type1'),
                    NameObject('/BaseFont'): NameObject('/Helvetica'),
                }),
            }),
        })
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 10 Tf 10 100 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = stream
    if encrypt:
        writer.encrypt('test-password')
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def drive_body(pdf, **changes):
    return {'id': SOURCE, 'name': 'Synthetic receipt.pdf', 'mimeType': 'application/pdf',
            'parents': [FOLDER], 'trashed': False, 'size': str(len(pdf)), 'version': '10',
            'md5Checksum': md5(pdf, usedforsecurity=False).hexdigest(),
            'capabilities': {'canDownload': True}, **changes}


def mock_drive(pdf, *, metadata=None, after=None):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == 'www.googleapis.com'
        assert request.url.path == f'/drive/v3/files/{SOURCE}'
        assert request.headers['Authorization'] == 'Bearer test-google-token'
        if request.url.params.get('alt') == 'media':
            return httpx.Response(200, content=pdf)
        return httpx.Response(200, json=(after if len(calls) > 2 and after is not None else metadata)
                              or drive_body(pdf))

    return httpx.MockTransport(handler), calls


@pytest.fixture
def configured_drive(workspace, monkeypatch):
    app, admin = workspace
    drive = app.state.case_files.drive
    monkeypatch.setattr(drive.settings, 'drive_folder_id', FOLDER)
    monkeypatch.setattr(drive.settings, 'drive_service_account_json', '{}')
    return app, admin, drive


def test_import_and_search_only_by_assigned_staff_and_reviewers(configured_drive):
    app, admin, drive = configured_drive
    cid = make_case(admin)
    same_customer_order = admin.post('/api/orders', json={
        'customer_id': 'demo-maya', 'product': 'Other item', 'amount_cents': 500, 'age_days': 3,
    }).json()['id']
    same_customer = make_case(admin, same_customer_order, 500)
    assigned, member = account(app, admin, 'member')
    unassigned, other = account(app, admin, 'member')
    supervisor, _ = account(app, admin, 'supervisor')
    customer, _ = account(app, admin, 'customer')
    root = f'/api/cases/{cid}/files'
    query = {'query': 'damaged headphones receipt'}
    imported = {'source': f'https://drive.google.com/file/d/{SOURCE}/view?usp=drive_link'}
    bank_ref = app.state.store.one("SELECT bank_ref FROM rg_profiles WHERE id='demo-maya'")['bank_ref']
    pdf = make_pdf(f'{CASE_TEXT} {bank_ref}')
    transport, calls = mock_drive(pdf)
    client_type = httpx.Client
    with patch.object(drive, '_token', return_value='test-google-token'), \
            patch('app.drive_files.httpx.Client',
                  side_effect=lambda **kwargs: client_type(transport=transport, **kwargs)), \
            patch.object(app.state.workflow.models, '_post') as provider:
        assert assigned.post(root + '/import', json=imported).status_code == 403
        assert customer.post(root + '/search', json=query).status_code == 403
        assert not calls
        assert supervisor.put(root + '/assignment', json={'user_id': member['id']}).status_code == 200
        assert admin.put(f'/api/cases/{same_customer}/files/assignment',
                         json={'user_id': member['id']}).status_code == 200
        response = supervisor.post(root + '/import', json=imported)
        assert response.status_code == 200, response.text
        document_id = response.json()['id']
        assert response.json()['imported'] is True
        retry = admin.post(root + '/import', json=imported)
        assert retry.json() == {'id': document_id, 'imported': False}
        assert admin.post(f'/api/cases/{same_customer}/files/import', json=imported).status_code == 409
        assert len(calls) == 3
        for allowed in (assigned, supervisor, admin):
            result = allowed.post(root + '/search', json=query)
            assert result.status_code == 200, result.text
            assert result.json()[0]['source_id'] == document_id
            assert MARKER in result.text
            assert bank_ref not in result.text
            assert allowed.get(f'/api/cases/{cid}').json()['case_files']['files'][0]['id'] == document_id
        assert unassigned.post(root + '/search', json=query).status_code == 404
        assert 'case_files' not in unassigned.get(f'/api/cases/{cid}').json()
        assert assigned.post(f'/api/cases/{same_customer}/files/search', json=query).json() == []
        for endpoint in ('/api/knowledge', '/api/reports'):
            assert MARKER not in assigned.get(endpoint).text
        result = assigned.post('/api/knowledge/search', json={**query, 'case_id': cid})
        assert result.status_code == 200
        assert MARKER not in result.text
        assert assigned.post(f'/api/cases/{cid}/run', json={}).status_code == 200
        assert MARKER not in assigned.get(f'/api/cases/{cid}').text
        assert MARKER not in admin.get('/api/reports/export').text
        assert admin.put(root + '/assignment', json={'user_id': other['id']}).status_code == 200
        assert assigned.post(root + '/search', json=query).status_code == 404
        assert MARKER in unassigned.post(root + '/search', json=query).text
        assert admin.put(root + '/assignment', json={'user_id': None}).status_code == 200
        assert unassigned.post(root + '/search', json=query).status_code == 404
        provider.assert_not_called()


@pytest.mark.parametrize('changes,status', [
    ({'parents': ['another-folder']}, 404),
    ({'trashed': True}, 404),
    ({'mimeType': 'application/vnd.google-apps.shortcut'}, 422),
    ({'size': str(2 * 1024 * 1024 + 1)}, 422),
    ({'capabilities': {'canDownload': False}}, 404),
])
def test_drive_rejects_out_of_scope_and_unsupported_files_before_download(changes, status):
    drive = DriveFiles(Settings(drive_folder_id=FOLDER))
    pdf = make_pdf(CASE_TEXT)
    transport, calls = mock_drive(pdf, metadata=drive_body(pdf, **changes))
    with httpx.Client(transport=transport, headers={'Authorization': 'Bearer test-google-token'}) as client:
        with pytest.raises(DriveFileError) as exc:
            drive._download(client, SOURCE)
    assert exc.value.status == status
    assert len(calls) == 1


def test_drive_rechecks_revoked_folder_membership_after_download():
    drive = DriveFiles(Settings(drive_folder_id=FOLDER))
    pdf = make_pdf(CASE_TEXT)
    transport, calls = mock_drive(pdf, after=drive_body(pdf, parents=['another-folder']))
    with httpx.Client(transport=transport, headers={'Authorization': 'Bearer test-google-token'}) as client:
        with pytest.raises(DriveFileError) as exc:
            drive._download(client, SOURCE)
    assert exc.value.status == 404
    assert len(calls) == 3


@pytest.mark.parametrize('pdf,error', [
    (make_pdf(), 'selectable text'),
    (make_pdf(CASE_TEXT, encrypt=True), 'unencrypted PDF'),
    (b'%PDF-1.3\ninvalid', 'readable PDF'),
])
def test_unreadable_pdf_leaves_no_case_file(configured_drive, pdf, error):
    app, admin, drive = configured_drive
    cid = make_case(admin)
    with patch.object(drive, '_token', return_value='test-google-token'), \
            patch.object(drive, '_download', return_value=('Synthetic PDF', pdf)):
        result = admin.post(f'/api/cases/{cid}/files/import', json={'source': SOURCE})
    assert result.status_code == 422 and error in result.text
    assert app.state.store.all('SELECT * FROM rg_case_files') == []
    assert app.state.store.all('SELECT * FROM rg_case_file_chunks') == []


def test_import_disabled_and_arbitrary_url_never_contacts_drive(configured_drive, monkeypatch):
    app, admin, drive = configured_drive
    cid = make_case(admin)
    with patch.object(drive, '_token') as token:
        result = admin.post(f'/api/cases/{cid}/files/import', json={'source': 'https://example.test/file.pdf'})
        assert result.status_code == 422
        monkeypatch.setattr(drive.settings, 'drive_folder_id', '')
        result = admin.post(f'/api/cases/{cid}/files/import', json={'source': SOURCE})
        assert result.status_code == 503
    token.assert_not_called()


def test_drive_uses_service_account_token_endpoint_with_read_only_scope():
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_text = signing_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()).decode()
    settings = Settings(drive_folder_id=FOLDER, drive_service_account_json=json.dumps({
        'type': 'service_account', 'client_email': 'test@project.iam.gserviceaccount.com',
        'token_uri': TOKEN_URL, 'private_key': key_text,
    }))
    with patch('app.drive_files.urllib3.PoolManager') as pool:
        pool.return_value.request.return_value = HTTPResponse(
            status=200, body=b'{"access_token":"test-google-token","expires_in":3600}')
        assert DriveFiles(settings)._token() == 'test-google-token'
    call = pool.return_value.request.call_args
    assert call.args == ('POST', TOKEN_URL)
    claims = parse_qs(call.kwargs['body'].decode())['assertion'][0].split('.')[1]
    assert json.loads(base64.urlsafe_b64decode(claims + '==='))['scope'] == READ_SCOPE



def test_concurrent_import_retries_share_one_snapshot(configured_drive):
    app, admin, drive = configured_drive
    cid = make_case(admin)
    barrier = Barrier(2, timeout=5)

    def pdf(_):
        barrier.wait()
        return 'Synthetic receipt.pdf', CASE_TEXT

    def import_pdf():
        return admin.post(f'/api/cases/{cid}/files/import', json={'source': SOURCE})

    with patch.object(drive, 'read_pdf', side_effect=pdf), ThreadPoolExecutor(max_workers=2) as pool:
        results = [result.result() for result in (pool.submit(import_pdf), pool.submit(import_pdf))]
    assert all(result.status_code == 200 for result in results)
    assert {result.json()['imported'] for result in results} == {True, False}
    ids = {result.json()['id'] for result in results}
    assert len(ids) == 1
    rows = app.state.store.all('SELECT id FROM rg_case_files WHERE case_id=?', (cid,))
    assert {row['id'] for row in rows} == ids


def test_case_file_indexing_and_search_stay_local_in_live_mode(configured_drive, monkeypatch):
    app, admin, drive = configured_drive
    cid = make_case(admin)
    monkeypatch.setattr(drive.settings, 'provider', 'openai')
    with patch.object(app.state.workflow.models, '_post') as provider, \
            patch.object(drive, 'read_pdf', return_value=('Synthetic receipt.pdf', CASE_TEXT)):
        assert admin.post(f'/api/cases/{cid}/files/import', json={'source': SOURCE}).status_code == 200
        response = admin.post(f'/api/cases/{cid}/files/search', json={'query': 'receipt'})
        assert response.status_code == 200
        assert MARKER in response.text
    provider.assert_not_called()
