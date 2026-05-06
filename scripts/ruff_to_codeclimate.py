#!/usr/bin/env python3
"""Convert Ruff JSON output to GitLab Code Quality (CodeClimate) format."""

import hashlib
import json
import sys

SEVERITY_MAP = {
    "C9": "minor",
    "E": "major",
    "W": "minor",
    "F": "major",
    "I": "info",
    "N": "info",
    "S": "major",
    "B": "major",
    "ANN": "minor",
    "SIM": "minor",
    "RUF": "minor",
}

CATEGORY_MAP = {
    "C9": "Complexity",
    "E": "Style",
    "W": "Style",
    "F": "Bug Risk",
    "I": "Style",
    "N": "Style",
    "S": "Security",
    "B": "Bug Risk",
}


def get_severity(code: str) -> str:
    for prefix, severity in SEVERITY_MAP.items():
        if code.startswith(prefix):
            return severity
    return "minor"


def get_categories(code: str) -> list[str]:
    for prefix, category in CATEGORY_MAP.items():
        if code.startswith(prefix):
            return [category]
    return ["Style"]


def fingerprint(filename: str, code: str, row: int) -> str:
    return hashlib.md5(f"{filename}:{code}:{row}".encode()).hexdigest()


def convert(input_path: str, output_path: str) -> None:
    with open(input_path) as f:
        ruff_issues = json.load(f)

    codeclimate = []
    for issue in ruff_issues:
        code = issue.get("code", "UNKNOWN")
        filename = issue.get("filename", "")
        row = issue.get("location", {}).get("row", 1)

        codeclimate.append(
            {
                "type": "issue",
                "check_name": code,
                "description": issue.get("message", ""),
                "categories": get_categories(code),
                "location": {
                    "path": filename,
                    "lines": {"begin": row},
                },
                "severity": get_severity(code),
                "fingerprint": fingerprint(filename, code, row),
            }
        )

    with open(output_path, "w") as f:
        json.dump(codeclimate, f, indent=2)

    print(f"Converted {len(codeclimate)} issues -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: ruff_to_codeclimate.py <ruff-output.json> <gl-code-quality-report.json>"
        )
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
