"""Authenticated evidence collector; no default credentials or hidden public endpoints."""

import argparse
from datetime import datetime, timezone
import getpass
import json
from pathlib import Path
from urllib.parse import urlsplit
import httpx


def main():
    parser = argparse.ArgumentParser(
        description="Collect RefundGuard evidence from an authenticated sandbox"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--case-id",
        help="Optionally run this synthetic case before collecting evidence",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    origin = args.base_url.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path:
        parser.error("Use an HTTP(S) origin without a path")
    print("Signing in to", origin)
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    with httpx.Client(
        base_url=origin, headers={"Origin": origin}, timeout=120
    ) as client:
        login = client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        password = None
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        me = client.get("/api/auth/me")
        me.raise_for_status()
        if me.json().get("mfa_required"):
            if not me.json().get("mfa_enabled"):
                parser.error(
                    "Complete MFA enrollment in the browser before collecting hosted evidence"
                )
            verified = client.post(
                "/api/auth/mfa/verify",
                json={"code": getpass.getpass("Authenticator or recovery code: ")},
            )
            verified.raise_for_status()
            client.headers["X-CSRF-Token"] = verified.json()["csrf"]
        try:
            if args.case_id:
                result = client.post("/api/cases/" + args.case_id + "/run", json={})
                result.raise_for_status()
            report = client.get("/api/reports/export")
            report.raise_for_status()
            output = args.out or Path("redteam/results") / (
                "evidence-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + ".json"
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.json(), indent=2))
            print("Evidence saved to", output)
        finally:
            client.post("/api/auth/logout", json={})


if __name__ == "__main__":
    main()
