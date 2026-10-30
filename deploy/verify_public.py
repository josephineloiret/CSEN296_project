"""Read-only/unauthenticated production checks: no credentials or model calls."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origin")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    if urlsplit(origin).scheme != "https":
        raise SystemExit("An HTTPS origin is required")
    checks = []

    def check(name, passed, **details):
        checks.append({"name": name, "pass": bool(passed), **details})

    with httpx.Client(base_url=origin, timeout=30, follow_redirects=False) as client:
        root = client.get("/")
        check(
            "Browser page over verified TLS",
            root.status_code == 200,
            status=root.status_code,
        )
        for header, fragment in [
            ("strict-transport-security", "max-age="),
            ("content-security-policy", "script-src 'self'"),
            ("x-frame-options", "DENY"),
            ("x-content-type-options", "nosniff"),
            ("cache-control", "no-store"),
        ]:
            check(header, fragment in root.headers.get(header, ""))
        health = client.get("/health")
        check(
            "Public health",
            health.status_code == 200
            and health.json().get("application") == "refundguard",
        )
        for path in [
            "/api/auth/me",
            "/api/usage",
            "/api/cases",
            "/api/knowledge",
            "/api/team",
            "/api/reports/export",
            "/api/team/links",
            "/api/security/alerts",
            "/api/security/export",
        ]:
            r = client.get(path)
            check("Login required: " + path, r.status_code == 401, status=r.status_code)
        for path in [
            "/.env",
            "/app/config.py",
            "/data/setup-token",
            "/static/%2e%2e/config.py",
            "/data/mfa-key",
            "/data/evidence-key",
            "/data/backup-key",
            "/data/backups",
        ]:
            r = client.get(path)
            check(
                "Private file unavailable: " + path,
                r.status_code == 404,
                status=r.status_code,
            )
        r = client.post(
            "/api/auth/login",
            headers={"Origin": "https://untrusted.example.test"},
            json={
                "email": "security-probe@example.test",
                "password": "not-an-account-password",
            },
        )
        check("Cross-origin login rejected", r.status_code == 403, status=r.status_code)
        r = client.post(
            "/api/cases/RG-SECURITY-PROBE/run", headers={"Origin": origin}, json={}
        )
        check(
            "Anonymous paid tool rejected", r.status_code == 401, status=r.status_code
        )
        r = client.get("http://" + urlsplit(origin).netloc + "/")
        check(
            "HTTP upgrades to HTTPS",
            r.status_code in (301, 302, 307, 308)
            and r.headers.get("location", "").startswith(origin),
            status=r.status_code,
        )
    result = {
        "origin": origin,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(c["pass"] for c in checks),
        "checks": checks,
        "scope": "Unauthenticated HTTPS, headers, private-file and paid-tool access checks. No OpenAI calls.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": len(checks),
                "failures": [c for c in checks if not c["pass"]],
            }
        )
    )
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
