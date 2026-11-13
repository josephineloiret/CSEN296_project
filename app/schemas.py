import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

CASE_ID = re.compile(r'^RG-[0-9A-F]{8}$')
ORDER_ID = re.compile(r'^(?:ORDER-[0-9A-F]{8}|DEMO-[A-Z][A-Z-]{0,40})$')
CUSTOMER_ID = re.compile(r'^(?:cust-[0-9a-f]{12}|demo-[a-z][a-z-]{0,40})$')
DOCUMENT_ID = re.compile(r'^DOC-[0-9A-F]{10}$')
USER_ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
LINK_ID = re.compile(r'^[0-9a-f]{64}$')

def _reject_controls(value, allow_line_breaks):
    allowed = {'\n', '\r', '\t'} if allow_line_breaks else set()
    for char in value:
        if char in allowed:
            continue
        if char in '\u2028\u2029\x7f' or unicodedata.category(char).startswith('C'):
            raise ValueError('Remove control characters')
    return value

def one_line(value):
    """Reject blank space and line breaks in a name, subject, or other single-line field."""
    _reject_controls(value, allow_line_breaks=False)
    value = value.strip()
    if not value:
        raise ValueError('Enter text, not blank space')
    return value

def several_lines(value, required=True):
    """Allow a real paragraph, and still reject blank space and other control characters."""
    _reject_controls(value, allow_line_breaks=True)
    value = value.strip()
    if required and not value:
        raise ValueError('Enter text, not blank space')
    return value

def shaped_id(value, pattern, label):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f'Enter a valid {label}')
    return value

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)

class Login(Input):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1,max_length=128,repr=False)
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        _reject_controls(value, allow_line_breaks=False)
        value=value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise ValueError('Enter a valid email address')
        return value

class Setup(Login):
    name: str = Field(min_length=1,max_length=80)
    token: str = Field(min_length=20,max_length=200,repr=False)
    @field_validator('name')
    @classmethod
    def name_text(cls,value):
        return one_line(value)

class AcceptInvite(Input):
    token: str = Field(min_length=20,max_length=200,repr=False)
    password: str = Field(min_length=1,max_length=128,repr=False)

class AcceptTeamInvite(Login):
    name: str = Field(min_length=1,max_length=80)
    token: str = Field(min_length=20,max_length=200,repr=False)
    @field_validator('name')
    @classmethod
    def name_text(cls,value):
        return one_line(value)

class InviteToken(Input):
    token: str = Field(min_length=20,max_length=200,repr=False)

class Invitation(Input):
    email: str = Field(min_length=3,max_length=254)
    name: str = Field(min_length=1,max_length=80)
    role: Literal['admin','supervisor','member','customer'] = 'member'
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        return Login.email_format(value)
    @field_validator('name')
    @classmethod
    def name_text(cls,value):
        return one_line(value)

class CaseInput(Input):
    order_id: str = Field(min_length=1,max_length=80)
    amount_cents: int = Field(strict=True,gt=0,le=10000000)
    reason_code: Literal['damaged','not_received','wrong_item','other']
    message: str = Field(min_length=1,max_length=6000)
    @field_validator('order_id')
    @classmethod
    def order(cls,value):
        return shaped_id(value, ORDER_ID, 'order id')
    @field_validator('message')
    @classmethod
    def message_text(cls,value):
        value = several_lines(value)
        if len(value) > 6000:
            raise ValueError('Message is too long')
        return value

class DocumentInput(Input):
    title: str = Field(min_length=1,max_length=160)
    content: str = Field(min_length=10,max_length=40000)
    kind: Literal['policy','customer'] = 'policy'
    customer_id: str | None = Field(default=None,max_length=80)
    @field_validator('title')
    @classmethod
    def title_text(cls,value):
        return one_line(value)
    @field_validator('content')
    @classmethod
    def content_text(cls,value):
        value = several_lines(value)
        if len(value) < 10:
            raise ValueError('Enter at least 10 characters')
        return value
    @field_validator('customer_id')
    @classmethod
    def customer(cls,value):
        if value is None:
            return None
        return shaped_id(value, CUSTOMER_ID, 'customer id')

class SearchInput(Input):
    query: str = Field(min_length=1,max_length=2000)
    case_id: str = Field(min_length=1,max_length=80)
    @field_validator('query')
    @classmethod
    def query_text(cls,value):
        return one_line(value)
    @field_validator('case_id')
    @classmethod
    def case(cls,value):
        return shaped_id(value, CASE_ID, 'case id')

class PolicyReview(Input):
    action: Literal['publish','reject','rollback']

class SupervisorInput(Input):
    decision: Literal['pending','approved','denied']

class ActiveInput(Input):
    active: bool = Field(strict=True)

class PasswordInput(Input):
    current_password: str = Field(min_length=1,max_length=128,repr=False)
    new_password: str = Field(min_length=1,max_length=128,repr=False)

class ProfileInput(Input):
    name: str = Field(min_length=1,max_length=80)
    notes: str = Field(max_length=3000)
    @field_validator('name')
    @classmethod
    def name_text(cls,value):
        return one_line(value)
    @field_validator('notes')
    @classmethod
    def notes_text(cls,value):
        return several_lines(value, required=False)

class MessageInput(Input):
    subject: str = Field(min_length=1,max_length=200)
    body: str = Field(min_length=1,max_length=6000)
    @field_validator('subject')
    @classmethod
    def subject_text(cls,value):
        return one_line(value)
    @field_validator('body')
    @classmethod
    def body_text(cls,value):
        return several_lines(value)

class OrderInput(Input):
    customer_id: str = Field(min_length=1,max_length=80)
    product: str = Field(min_length=1,max_length=120)
    amount_cents: int = Field(strict=True,gt=0,le=10000000)
    age_days: int = Field(default=0,strict=True,ge=0,le=365)
    @field_validator('customer_id')
    @classmethod
    def customer(cls,value):
        return shaped_id(value, CUSTOMER_ID, 'customer id')
    @field_validator('product')
    @classmethod
    def product_text(cls,value):
        return one_line(value)


class MessageReviewInput(Input):
    body: str = Field(min_length=1,max_length=6000)
    reason: str = Field(min_length=1,max_length=240)

    @field_validator('body')
    @classmethod
    def reviewed_body(cls,value):
        return several_lines(value)

    @field_validator('reason')
    @classmethod
    def review_reason(cls,value):
        return one_line(value)
