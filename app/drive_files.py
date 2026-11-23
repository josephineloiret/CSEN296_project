"""Read a single PDF from the configured Google Drive folder."""
import hashlib
from io import BytesIO
import json
import re
import time
from urllib.parse import urlsplit

import httpx
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.urllib3 import Request
from google.oauth2 import service_account
from pypdf import PdfReader
from pypdf.errors import PdfReadError
import urllib3

DRIVE_ID = re.compile(r'[A-Za-z0-9_-]{1,150}')
DRIVE_URL = 'https://www.googleapis.com/drive/v3/files/'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
READ_SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
MAX_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
MAX_TEXT = 40_000


class DriveFileError(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def source_id(source):
    source = source.strip()
    if DRIVE_ID.fullmatch(source):
        return source
    try:
        url = urlsplit(source)
    except ValueError:
        url = None
    if url and url.scheme == 'https' and url.netloc == 'drive.google.com':
        match = re.fullmatch(r'/file/d/([A-Za-z0-9_-]{1,150})(?:/view)?/?', url.path)
        if match:
            return match[1]
    raise DriveFileError('Enter a Google Drive PDF file link or file ID.')


def pdf_text(data):
    if not data.startswith(b'%PDF-'):
        raise DriveFileError('The Drive file is not a readable PDF.')
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise DriveFileError('Upload an unencrypted PDF to the project folder.')
        if len(reader.pages) > MAX_PAGES:
            raise DriveFileError(f'Choose a PDF with at most {MAX_PAGES} pages.')
        pages = []
        length = 0
        for page in reader.pages:
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > 4 * MAX_BYTES:
                raise DriveFileError('This PDF is too complex to import.')
            text = page.extract_text().strip()
            length += len(text) + 2
            if length > MAX_TEXT:
                raise DriveFileError('The PDF contains too much text to import.')
            pages.append(text)
    except (PdfReadError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        raise DriveFileError('The Drive file is not a readable PDF.') from None
    result = '\n\n'.join(pages).strip()
    if len(result) < 10:
        raise DriveFileError('Choose a PDF with selectable text. Scanned pages require OCR before import.')
    return result


class DriveFiles:
    def __init__(self, settings):
        self.settings = settings

    def _token(self):
        info = json.loads(self.settings.drive_service_account_json)
        if not isinstance(info, dict) or info.get('type') != 'service_account' or info.get('token_uri') != TOKEN_URL:
            raise ValueError('Invalid Drive service account configuration')
        credentials = service_account.Credentials.from_service_account_info(info, scopes=[READ_SCOPE])
        pool = urllib3.PoolManager(retries=False)
        try:
            request = Request(pool)
            credentials.refresh(lambda **kwargs: request(**kwargs, timeout=10))
            return credentials.token
        finally:
            pool.clear()

    def read_pdf(self, file_id):
        if not self.settings.drive_import_enabled:
            raise DriveFileError('Drive case file import is unavailable.', 503)
        if not DRIVE_ID.fullmatch(self.settings.drive_folder_id) or not DRIVE_ID.fullmatch(file_id):
            raise DriveFileError('Drive case file import is unavailable.', 503)
        try:
            with httpx.Client(timeout=10, headers={'Authorization': 'Bearer ' + self._token()}) as client:
                title, data = self._download(client, file_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                raise DriveFileError('That file is unavailable in the project Drive folder.', 404) from None
            raise DriveFileError('Drive is unavailable. Try again later.', 503) from None
        except (httpx.HTTPError, GoogleAuthError, urllib3.exceptions.HTTPError, ValueError, TypeError):
            raise DriveFileError('Drive is unavailable. Check the connection and try again.', 503) from None
        return title, pdf_text(data)

    def _metadata(self, client, file_id):
        response = client.get(DRIVE_URL + file_id, params={
            'fields': 'id,name,mimeType,parents,trashed,size,version,md5Checksum,capabilities(canDownload)',
            'supportsAllDrives': 'true',
        })
        response.raise_for_status()
        file = response.json()
        if (file.get('id') != file_id or file.get('trashed') is not False
                or file.get('parents') != [self.settings.drive_folder_id]
                or not file.get('capabilities', {}).get('canDownload')):
            raise DriveFileError('That file is unavailable in the project Drive folder.', 404)
        return file

    def _download(self, client, file_id):
        file = self._metadata(client, file_id)
        if file.get('mimeType') != 'application/pdf':
            raise DriveFileError('Select a PDF in the project Drive folder.')
        size = int(file.get('size') or 0)
        if not 0 < size <= MAX_BYTES:
            raise DriveFileError('Choose a PDF no larger than 2 MiB.')
        deadline = time.monotonic() + 15
        data = bytearray()
        with client.stream('GET', DRIVE_URL + file_id, params={'alt': 'media', 'supportsAllDrives': 'true'}) as response:
            response.raise_for_status()
            for block in response.iter_bytes(chunk_size=64 * 1024):
                if time.monotonic() > deadline:
                    raise DriveFileError('Drive download timed out. Try again later.', 503)
                data.extend(block)
                if len(data) > size:
                    raise DriveFileError('The Drive file changed during import. Try again.', 409)
        checksum = hashlib.md5(data, usedforsecurity=False).hexdigest()
        current = self._metadata(client, file_id)
        if len(data) != size or checksum != file.get('md5Checksum') or current != file:
            raise DriveFileError('The Drive file changed during import. Try again.', 409)
        return file['name'], data
