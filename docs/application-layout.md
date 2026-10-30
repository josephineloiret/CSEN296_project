# RefundGuard application

Run `./start.sh` from the repository root, or follow
[the local run instructions](../run_instructions.md).

- `app/main.py`: authenticated HTTP API and browser entry point.
- `app/security.py`: Argon2id passwords, opaque sessions, CSRF, throttling.
- `app/agents.py`, `workflow.py`, `ai.py`: five specialists, orchestration and model adapter.
- `app/knowledge.py`: document versioning and scoped vector retrieval.
- `app/store.py`, `refunds.py`: persistent records, mock tools and execution controls.
- `app/static/`: browser UI, served on the same origin as the API.
- `tests/`: tool and application regression tests.
- `manage.py`: first-run setup link and trusted local password recovery.

The old unauthenticated `/tasks`, `/logs`, and canned red-team endpoint were
removed. The original `agent.py` and `retriever.py` are retained as course-starter
reference code; the web application uses the new workflow and knowledge modules.
