"""Per-request deadline propagated into synchronous provider calls."""
from contextvars import ContextVar
import time
from app.ai import AIError

deadline = ContextVar('refundguard_deadline', default=None)


def remaining():
    end = deadline.get()
    value = end - time.monotonic() if end is not None else 35
    if value <= 0:
        raise AIError('Workflow deadline reached. Review the case before retrying.')
    return value
