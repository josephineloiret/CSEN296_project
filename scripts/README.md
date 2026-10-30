# Repository utilities

Run commands from the repository root with the project's virtual environment.

| Command | Purpose |
| --- | --- |
| `.venv/bin/python -m scripts.refund_demo` | Exercise refund limits and authority revocation with a temporary database |
| `.venv/bin/python -m scripts.export_evidence` | Sign in interactively and export evidence from a running sandbox |
| `.venv/bin/python scripts/scan_secrets.py` | Check source and documentation for credential patterns |
| `.venv/bin/python scripts/summarize_container_scan.py PATH` | Render Trivy JSON as CI annotations and a job summary; fail on HIGH/CRITICAL findings |

Evidence exports default to the ignored `redteam/results/` directory. Use
`--help` on the export command for the origin, optional case and output options.
Container scanning itself runs in [GitHub Actions](../.github/workflows/security.yml).
The public deployment checker lives under [`deploy/`](../deploy/).
