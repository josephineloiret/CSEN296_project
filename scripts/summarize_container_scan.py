"""Expose actionable vulnerability metadata in the GitHub job summary."""

import json
import os
from pathlib import Path
import sys

report = Path(sys.argv[1])
lines = ["## Container vulnerability scan", ""]
if not report.exists():
    lines.append(
        "The scanner failed without producing a JSON report. Check the authenticated job logs for the scanner or registry error."
    )
    print(
        "::error title=Container scan::Scanner failed without producing a JSON report"
    )
    failed = True
else:
    data = json.loads(report.read_text())
    rows = []
    for result in data.get("Results", []):
        for finding in result.get("Vulnerabilities") or []:
            if finding.get("Severity") in ("HIGH", "CRITICAL"):
                rows.append(
                    [
                        result.get("Target", ""),
                        finding.get("VulnerabilityID", ""),
                        finding.get("PkgName", ""),
                        finding.get("InstalledVersion", ""),
                        finding.get("FixedVersion") or "No published fix",
                        finding["Severity"],
                    ]
                )
    lines.append(
        f"High/critical findings: **{len(rows)}**. The scan gate remains enabled."
    )
    if rows:
        lines += [
            "",
            "| Target | Advisory | Package | Installed | Fixed | Severity |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    str(v)
                    .replace("|", "/")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", " ")
                    for v in row
                )
                + " |"
            )
    for row in rows[:20]:
        message = (
            "; ".join(str(v) for v in row)
            .replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
        )
        print("::error title=Container vulnerability::" + message)
    failed = bool(rows)
summary = "\n".join(lines) + "\n"
if os.getenv("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
        out.write(summary)
print(summary)
raise SystemExit(1 if failed else 0)
