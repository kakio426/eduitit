#!/usr/bin/env python
"""Refresh HANDOFF_sheetbook_branch_latest.md metadata lines.

Updates:
- Status timestamp line
- latest backup commit line
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _replace_line(lines: list[str], prefix: str, new_line: str) -> bool:
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = new_line
            return True
    return False


def run(args: argparse.Namespace) -> int:
    root = _repo_root()
    current_branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    expected_branch = str(args.expected_branch or "").strip()
    if expected_branch and current_branch != expected_branch:
        print(
            f"[sheetbook-refresh-handoff] blocked: current branch '{current_branch}' "
            f"!= expected '{expected_branch}'",
            file=sys.stderr,
        )
        return 2

    commit_line = _run_git(root, "log", "-1", "--pretty=format:%h%x09%s")
    commit_hash, _, commit_subject = commit_line.partition("\t")
    if not commit_hash.strip() or not commit_subject.strip():
        print(
            "[sheetbook-refresh-handoff] failed to parse latest commit metadata",
            file=sys.stderr,
        )
        return 2

    timestamp = str(args.timestamp or "").strip()
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    handoff_path = Path(args.handoff)
    if not handoff_path.is_absolute():
        handoff_path = root / handoff_path
    if not handoff_path.exists():
        print(f"[sheetbook-refresh-handoff] file not found: {handoff_path}", file=sys.stderr)
        return 2

    lines = handoff_path.read_text(encoding="utf-8").splitlines()
    updated_status = _replace_line(
        lines,
        "Status: Working branch handoff (",
        f"Status: Working branch handoff ({timestamp})",
    )
    updated_commit = _replace_line(
        lines,
        "- latest backup commit: ",
        f"- latest backup commit: `{commit_hash.strip()}` (`{commit_subject.strip()}`)",
    )
    if not updated_status or not updated_commit:
        print(
            "[sheetbook-refresh-handoff] target lines not found "
            "(status/latest backup commit)",
            file=sys.stderr,
        )
        return 2

    handoff_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "handoff": str(handoff_path),
                "branch": current_branch,
                "latest_backup_commit": commit_hash.strip(),
                "latest_backup_subject": commit_subject.strip(),
                "timestamp": timestamp,
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh sheetbook branch latest handoff metadata lines."
    )
    parser.add_argument(
        "--handoff",
        default="docs/handoff/HANDOFF_sheetbook_branch_latest.md",
        help="handoff markdown path",
    )
    parser.add_argument(
        "--timestamp",
        default="",
        help="status timestamp text (default: now, format YYYY-MM-DD HH:MM)",
    )
    parser.add_argument(
        "--expected-branch",
        default="feature/sheetbook",
        help="block execution when current branch differs (default: feature/sheetbook)",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
