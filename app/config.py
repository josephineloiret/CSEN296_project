from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

@dataclass
class Settings:
    database: Path = ROOT / 'data' / 'refundguard.sqlite3'
    origin: str = 'http://localhost:8000'
    production: bool = False
    provider: str = 'local'
    api_key: str = field(default='',repr=False)
    model: str = 'gpt-5.6-luna'
    embedding_model: str = 'text-embedding-3-small'
    reasoning_effort: str = 'none'
    daily_budget_usd: str = '1.00'
    monthly_budget_usd: str = '5.00'
    railway: bool = False
    workflow_concurrency: int = 2
    workflow_timeout_seconds: int = 120
    audit_directory: str = ''
    mfa_encryption_key: str = field(default='',repr=False)
    team_invite_hash: str = field(default='',repr=False)
    team_invite_expires: float = 0

    @classmethod
    def from_env(cls):
        railway=bool(os.getenv('RAILWAY_PROJECT_ID'))
        public_domain=os.getenv('RAILWAY_PUBLIC_DOMAIN','')
        default_origin='https://'+public_domain if railway and public_domain else 'http://localhost:8000'
        return cls(database=Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'refundguard.sqlite3'))),
                   origin=os.getenv('APP_ORIGIN', default_origin).rstrip('/'),
                   production=os.getenv('APP_ENV', 'production' if railway else 'development') == 'production',
                   provider=os.getenv('AI_PROVIDER', 'local'), api_key=os.getenv('OPENAI_API_KEY', ''),
                   model=os.getenv('OPENAI_MODEL', 'gpt-5.6-luna'),
                   embedding_model=os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'),
                   reasoning_effort=os.getenv('OPENAI_REASONING_EFFORT','none'),
                   daily_budget_usd=os.getenv('OPENAI_DAILY_BUDGET_USD','1.00'),
                   monthly_budget_usd=os.getenv('OPENAI_MONTHLY_BUDGET_USD','5.00'),
                   railway=railway,
                   workflow_concurrency=int(os.getenv('WORKFLOW_CONCURRENCY','2')),
                   workflow_timeout_seconds=int(os.getenv('WORKFLOW_TIMEOUT_SECONDS','120')),
                   audit_directory=os.getenv('AUDIT_DIRECTORY',''),
                   mfa_encryption_key=os.getenv('MFA_ENCRYPTION_KEY',''),
                   team_invite_hash=os.getenv('TEAM_INVITE_TOKEN_HASH',''),
                   team_invite_expires=float(os.getenv('TEAM_INVITE_EXPIRES','0')))

    def validate(self):
        if self.team_invite_hash:
            import re
            import math
            if not re.fullmatch('[a-f0-9]{64}',self.team_invite_hash) or not math.isfinite(self.team_invite_expires) or self.team_invite_expires <= 0:
                raise ValueError('Invalid trusted team invitation provisioning settings')
        if not 1 <= self.workflow_concurrency <= 8:
            raise ValueError('WORKFLOW_CONCURRENCY must be between 1 and 8')
        if not 10 <= self.workflow_timeout_seconds <= 240:
            raise ValueError('WORKFLOW_TIMEOUT_SECONDS must be between 10 and 240')
        parsed = urlsplit(self.origin)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.path:
            raise ValueError('APP_ORIGIN must be an origin, without a path')
        if self.production and parsed.scheme != 'https':
            raise ValueError('Production requires an HTTPS APP_ORIGIN')
        if not self.production and parsed.hostname not in ('localhost', '127.0.0.1', '::1', 'testserver'):
            raise ValueError('Non-local origins require APP_ENV=production and HTTPS')
        if self.provider not in ('local', 'openai'):
            raise ValueError('AI_PROVIDER must be local or openai')
        if self.provider == 'openai' and not self.api_key:
            raise ValueError('OPENAI_API_KEY is required for AI_PROVIDER=openai')
        if self.reasoning_effort not in ('none','low','medium'):
            raise ValueError('OPENAI_REASONING_EFFORT must be none, low or medium')
        for name in ('daily_budget_usd','monthly_budget_usd'):
            try:
                value=Decimal(getattr(self,name))
                if not value.is_finite() or value < 0:
                    raise ValueError('Budget must be finite and nonnegative')
            except (InvalidOperation, ValueError):
                raise ValueError(f'{name} must be a finite nonnegative dollar amount') from None

    @property
    def cookie_name(self):
        return '__Host-refundguard' if self.production else 'refundguard_local'
