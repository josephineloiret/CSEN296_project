import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)

class Login(Input):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1,max_length=128,repr=False)
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
            raise ValueError('Enter a valid email address')
        return value

class Setup(Login):
    name: str = Field(min_length=1,max_length=80)
    token: str = Field(min_length=20,max_length=200,repr=False)

class AcceptInvite(Input):
    token: str = Field(min_length=20,max_length=200,repr=False)
    password: str = Field(min_length=1,max_length=128,repr=False)

class AcceptTeamInvite(Login):
    name: str = Field(min_length=1,max_length=80)
    token: str = Field(min_length=20,max_length=200,repr=False)

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

class CaseInput(Input):
    order_id: str = Field(min_length=1,max_length=80)
    amount_cents: int = Field(strict=True,gt=0,le=10000000)
    reason_code: Literal['damaged','not_received','wrong_item','other']
    message: str = Field(min_length=1,max_length=6000)

class DocumentInput(Input):
    title: str = Field(min_length=1,max_length=160)
    content: str = Field(min_length=10,max_length=40000)
    kind: Literal['policy','customer'] = 'policy'
    customer_id: str | None = Field(default=None,max_length=80)

class SearchInput(Input):
    query: str = Field(min_length=1,max_length=2000)
    case_id: str = Field(min_length=1,max_length=80)

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

class MessageInput(Input):
    subject: str = Field(min_length=1,max_length=200)
    body: str = Field(min_length=1,max_length=6000)

class OrderInput(Input):
    customer_id: str = Field(min_length=1,max_length=80)
    product: str = Field(min_length=1,max_length=120)
    amount_cents: int = Field(strict=True,gt=0,le=10000000)
    age_days: int = Field(default=0,strict=True,ge=0,le=365)
