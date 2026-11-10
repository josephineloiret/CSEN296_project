"""Fail CI on likely embedded credentials without printing matched secrets."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA)? ?PRIVATE KEY-----"),
    re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}"),
]
violations = []
for base in ("app", "deploy", ".github", "docs", "examples", "scripts"):
    for path in (ROOT / base).rglob("*"):
        if not path.is_file() or path.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".pdf",
            ".svg",
        ):
            continue
        try:
            content = path.read_text()
        except UnicodeError:
            continue
        if any(pattern.search(content) for pattern in PATTERNS):
            violations.append(str(path.relative_to(ROOT)))
for path in violations:
    print("Possible embedded credential in " + path)
print(f"Secret scan: {len(violations)} flagged files")
sys.exit(bool(violations))
