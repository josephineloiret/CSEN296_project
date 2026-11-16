"""Model-facing projections, not a claim to recognize all prompt injection.

Original records are retained for human review. Recognized instruction attacks
are replaced wholesale rather than partially rewritten into a plausible request.
Independent authorization and refund controls remain the security boundary.
"""
import base64
import json
import re
import unicodedata
from html import unescape
from html.parser import HTMLParser

PROJECTION_VERSION = 'model-text-v1'
WITHHELD = '[CONTENT WITHHELD: HUMAN REVIEW REQUIRED]'
BANK_REDACTED = '[BANK REFERENCE REDACTED]'
PROFILE_FIELDS = ('id', 'name', 'notes')
_PRIVATE_KEYS = {'bank_ref', 'bank_account', 'bank_account_number', 'account_number', 'routing_number'}
_ATTACK = re.compile(
    r'\b(?:ignore|disregard)\b.{0,90}\b(?:instructions?|rules?|polic(?:y|ies)|limits?|supervisor|guardrails?)\b'
    r'|\b(?:override|bypass)\s+(?:all|the|your|these|existing|current)\s+(?:rules?|polic(?:y|ies)|limits?|supervisor|guardrails?)\b'
    r'|\b(?:system|developer|administrator)\s*(?:override|message|prompt)\b'
    r'|\b(?:grant|give)\s+yourself\b'
    r'|\byou\s+are\s+now\b'
    r'|\bi am the system\b|\bas the system\b'
    r'|\b(?:reveal|print|show|expose)\b.{0,50}\b(?:system\s+prompt|hidden\s+instructions)\b'
    r'|\b(?:export|send|retrieve)\b.{0,60}\b(?:all|other|unrelated)\s+(?:customer\s+)?records\b'
    r'|<\|(?:im_start|im_end|system|assistant|endoftext)\|>'
    r'|\[/?INST\]|<<\s*/?SYS\s*>>'
    r'|(?:^|\n)\s*(?:system|developer|assistant)\s*:',
    re.IGNORECASE | re.DOTALL,
)
_MOCK_BANK = re.compile(r'\bMOCK-[A-Z0-9]+(?:-[A-Z0-9]+)*\b', re.IGNORECASE)
_LINK = re.compile(r'https?://[^\s<>"\]]+', re.IGNORECASE)
_COMPACT_ATTACK = re.compile(
    r'ignore.{0,30}(?:instruction|rule|policy)|disregard.{0,30}(?:instruction|rule)'
    r'|youarenow|grantyourself|systemoverride',
    re.IGNORECASE,
)
_BASE64_TOKEN = re.compile(r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{16,}={0,2}(?![A-Za-z0-9+/])')
_DOLLAR = re.compile(r'\$\s*(\d{1,3}(?:,\d{3})+|\d{1,7})(?:\.(\d{2}))?')
_LEET = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's'})
_HOMOGLYPHS = str.maketrans({
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x', 'і': 'i', 'ѕ': 's',
    'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Η': 'H', 'Ι': 'I', 'Κ': 'K', 'Μ': 'M', 'Ν': 'N', 'Ο': 'O',
    'Ρ': 'P', 'Τ': 'T', 'Υ': 'Y', 'Χ': 'X',
})


def _collapse_spaced_letters(value):
    """Join i g n o r e  a l l into words. A wider gap keeps the word break."""
    groups = re.split(r'\s{2,}|\n', value)
    words = []
    for group in groups:
        tokens = group.split()
        if len(tokens) >= 2 and all(len(token) == 1 and token.isalnum() for token in tokens):
            words.append(''.join(tokens))
        else:
            words.append(group.strip())
    return ' '.join(word for word in words if word)


def _decoded_payloads(value):
    found = []
    for token in _BASE64_TOKEN.findall(value):
        padded = token + ('=' * ((4 - len(token) % 4) % 4))
        try:
            text = base64.b64decode(padded, validate=True).decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            continue
        if re.search(r'[A-Za-z]{4}', text):
            found.append(text)
    return found


def disguised_instruction(value):
    """True only for an attack the plain-text check would miss.

    A plainly written attack may still be stored by a second reviewer. Retrieval
    already withholds it. Encoded, spaced, lookalike and letter-number forms
    must not become the active policy.
    """
    value = unicodedata.normalize('NFKC', unescape(str(value)))
    value = ''.join(c for c in value if c in '\n\r\t' or not unicodedata.category(c).startswith('C'))
    if _ATTACK.search(value):
        return False
    return instruction_attack(value)


def instruction_attack(value):
    """True when plain, disguised, or encoded text matches a known instruction attack."""
    collapsed = _collapse_spaced_letters(value)
    candidates = (value, collapsed, collapsed.translate(_LEET), value.translate(_HOMOGLYPHS), *_decoded_payloads(value))
    for candidate in candidates:
        if _ATTACK.search(candidate):
            return True
    for candidate in candidates[1:]:
        folded = re.sub(r'[^a-z]', '', candidate.lower())
        if _COMPACT_ATTACK.search(folded):
            return True
    return False


def allowed_amounts(data):
    """Case amounts already in the model input, plus the stated $0, $100 and $500 policy figures."""
    found = {0, 10000, 50000}
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'amount_cents' and isinstance(item, int):
                    found.add(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(data)
    return found


def unexpected_amount(text, allowed):
    for match in _DOLLAR.finditer(text):
        whole = int(match.group(1).replace(',', ''))
        cents = whole * 100 + int(match.group(2) or 0)
        if cents not in allowed:
            return True
    return False


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
        self.unsafe = False

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object', 'svg'}:
            self.hidden += 1
            self.unsafe = True
        elif tag in {'br', 'p', 'div', 'li'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object', 'svg'}:
            self.hidden = max(0, self.hidden - 1)
        elif tag in {'p', 'div', 'li'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def bank_references(store):
    return [row['bank_ref'] for row in store.all('SELECT bank_ref FROM rg_profiles')
            if len(row['bank_ref']) >= 4]


def model_text(value, references=(), limit=40000):
    """Normalize plain text, redact known references/URLs, quarantine known attacks.

    Detection is heuristic. It may miss obfuscated/multilingual attacks and may
    withhold quoted examples. Do not use it to grant authority or eligibility.
    """
    value = unicodedata.normalize('NFKC', unescape(str(value)))
    value = ''.join(c for c in value if c in '\n\r\t' or not unicodedata.category(c).startswith('C'))
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    if WITHHELD in value or instruction_attack(value):
        return WITHHELD
    parser = _PlainText()
    parser.feed(value)
    parser.close()
    if parser.unsafe:
        return WITHHELD
    value = ''.join(parser.parts)
    # Check after removing tags too: "ig<b>nore</b> all rules".
    if instruction_attack(value):
        return WITHHELD
    for reference in sorted(set(references), key=len, reverse=True):
        value = re.sub(re.escape(reference), BANK_REDACTED, value, flags=re.IGNORECASE)
    value = _MOCK_BANK.sub(BANK_REDACTED, value)
    value = _LINK.sub('[LINK REMOVED]', value)
    value = '\n'.join(re.sub(r'[^\S\n]+', ' ', line).strip() for line in value.split('\n'))
    # Inspect the entire bounded source before truncating, including its tail.
    return value.strip()[:limit]


def model_payload(value, references=()):
    """Preserve JSON structure and numeric types; sanitize every string value."""
    if isinstance(value, dict):
        return {key: model_payload(item, references) for key, item in value.items()
                if unicodedata.normalize('NFKC', str(key)).lower() not in _PRIVATE_KEYS}
    if isinstance(value, list):
        return [model_payload(item, references) for item in value]
    if isinstance(value, str):
        return model_text(value, references)
    return value


def document_text(content, references=()):
    # Generated case/profile documents are JSON. Process values individually so
    # escaped newlines and role delimiters cannot hide inside JSON serialization.
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        return model_text(content, references)
    if isinstance(value, (dict, list)):
        return json.dumps(model_payload(value, references), ensure_ascii=False)
    return model_text(content, references)


def profile_document(profile, references=()):
    limits = {'id': 80, 'name': 80, 'notes': 3000}
    return json.dumps({field: model_text(profile[field], references, limits[field])
                       for field in PROFILE_FIELDS}, ensure_ascii=False)
