#!/usr/bin/env python3
"""
Fail commit when staged source/template files contain high-confidence mojibake signs.

Checks:
1) UTF-8 strict decode for staged blob
2) replacement character (U+FFFD)
3) suspicious mixed pattern like '?<hangul><hangul>' often produced by broken Korean encoding
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


TEXT_EXTENSIONS = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
}


SUSPICIOUS_PATTERNS = (
    re.compile(r"\?[가-힣]{2,}"),
    re.compile(r"[가-힣]{2,}\?[가-힣]{2,}"),
)


def run_git(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def get_staged_files() -> list[str]:
    proc = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if proc.returncode != 0:
        return []
    files = [line.strip() for line in proc.stdout.decode("utf-8", errors="ignore").splitlines()]
    return [f for f in files if Path(f).suffix.lower() in TEXT_EXTENSIONS]


def get_staged_blob(path: str) -> bytes | None:
    proc = run_git(["show", f":{path}"])
    if proc.returncode != 0:
        return None
    return proc.stdout


def find_line_number(text: str, token: str) -> int:
    idx = text.find(token)
    if idx < 0:
        return 1
    return text.count("\n", 0, idx) + 1


def scan_text(path: str, text: str) -> list[str]:
    issues: list[str] = []

    if "\ufffd" in text:
        line_no = find_line_number(text, "\ufffd")
        issues.append(f"{path}:{line_no} contains replacement character U+FFFD")

    for pattern in SUSPICIOUS_PATTERNS:
        match = pattern.search(text)
        if match:
            line_no = text.count("\n", 0, match.start()) + 1
            sample = match.group(0)
            issues.append(f"{path}:{line_no} suspicious mojibake pattern: {sample!r}")
    return issues


def scan_staged() -> int:
    files = get_staged_files()
    all_issues: list[str] = []

    for path in files:
        blob = get_staged_blob(path)
        if blob is None:
            continue
        try:
            text = blob.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            all_issues.append(f"{path}: UTF-8 decode failed at byte {exc.start}")
            continue
        all_issues.extend(scan_text(path, text))

    if not all_issues:
        return 0

    sys.stderr.write("\n[encoding-guard] commit blocked due to possible Korean text corruption:\n")
    for issue in all_issues:
        sys.stderr.write(f" - {issue}\n")
    sys.stderr.write(
        "\nFix text first (UTF-8, no mojibake), then commit again.\n"
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true", help="scan staged files only")
    args = parser.parse_args()
    if args.staged:
        return scan_staged()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
