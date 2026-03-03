#!/usr/bin/env python
"""Guarded commit helper for sheetbook branch.

This script runs branch_path_guard on staged files before committing.
It is intended as a reliable fallback when Git pre-commit hooks are unavailable.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(root: Path, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )


def _echo(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def _current_branch(root: Path) -> str:
    result = _run(root, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        _echo(result)
        raise RuntimeError("failed to detect current branch")
    return result.stdout.strip()


def _staged_files(root: Path) -> list[str]:
    result = _run(root, ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"])
    if result.returncode != 0:
        _echo(result)
        raise RuntimeError("failed to inspect staged files")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _run_guard(root: Path, branch: str) -> int:
    guard_cmd = [
        sys.executable,
        "scripts/branch_path_guard.py",
        "--branch",
        branch,
        "--staged",
    ]
    result = _run(root, guard_cmd)
    _echo(result)
    return int(result.returncode)


def run(args: argparse.Namespace) -> int:
    root = _repo_root()
    current_branch = _current_branch(root)
    branch_override = str(args.branch or "").strip()
    if branch_override and branch_override != current_branch:
        print(
            f"[sheetbook-guarded-commit] blocked: --branch '{branch_override}' "
            f"!= current '{current_branch}'",
            file=sys.stderr,
        )
        return 2
    branch = current_branch
    expected_branch = str(args.expected_branch or "").strip()

    if expected_branch and branch != expected_branch:
        print(
            f"[sheetbook-guarded-commit] blocked: current branch '{branch}' "
            f"!= expected '{expected_branch}'",
            file=sys.stderr,
        )
        return 2

    try:
        staged = _staged_files(root)
    except RuntimeError:
        return 2

    if not staged:
        print("[sheetbook-guarded-commit] no staged files to commit", file=sys.stderr)
        return 2

    guard_code = _run_guard(root, branch)
    if guard_code != 0:
        return guard_code

    if args.guard_only:
        print("[sheetbook-guarded-commit] guard-only mode: passed")
        return 0

    message = str(args.message or "").strip()
    if not message:
        print("[sheetbook-guarded-commit] --message is required unless --guard-only", file=sys.stderr)
        return 2

    commit_cmd = ["git", "commit", "-m", message]
    if bool(args.allow_empty):
        commit_cmd.append("--allow-empty")
    commit_result = _run(root, commit_cmd)
    _echo(commit_result)
    if commit_result.returncode != 0:
        return int(commit_result.returncode)

    if bool(args.push):
        push_cmd = ["git", "push", str(args.remote).strip() or "origin", branch]
        push_retries = max(0, int(getattr(args, "push_retries", 2) or 0))
        push_retry_delay = max(0.0, float(getattr(args, "push_retry_delay", 1.0) or 0.0))
        attempts = 1 + push_retries
        last_code = 1
        for attempt in range(1, attempts + 1):
            push_result = _run(root, push_cmd)
            _echo(push_result)
            last_code = int(push_result.returncode)
            if last_code == 0:
                return 0
            if attempt < attempts:
                print(
                    f"[sheetbook-guarded-commit] push failed "
                    f"(attempt {attempt}/{attempts}), retrying in {push_retry_delay:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(push_retry_delay)
        return last_code

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run branch path guard on staged files, then commit (and optionally push)."
    )
    parser.add_argument(
        "--branch",
        default="",
        help="optional current-branch assertion (must match current branch when set)",
    )
    parser.add_argument(
        "--expected-branch",
        default="feature/sheetbook",
        help="block execution when current branch differs (default: feature/sheetbook)",
    )
    parser.add_argument(
        "-m",
        "--message",
        default="",
        help="git commit message (required unless --guard-only)",
    )
    parser.add_argument("--allow-empty", action="store_true", help="pass --allow-empty to git commit")
    parser.add_argument("--guard-only", action="store_true", help="run guard only without committing")
    parser.add_argument("--push", action="store_true", help="push after successful commit")
    parser.add_argument("--remote", default="origin", help="push remote name (default: origin)")
    parser.add_argument(
        "--push-retries",
        type=int,
        default=2,
        help="additional push retries on failure (default: 2, total attempts: 3)",
    )
    parser.add_argument(
        "--push-retry-delay",
        type=float,
        default=1.0,
        help="seconds to wait between push retries (default: 1.0)",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
