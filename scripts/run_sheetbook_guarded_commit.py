#!/usr/bin/env python
"""Guarded commit helper for sheetbook branch.

This script runs branch_path_guard on staged files before committing.
It is intended as a reliable fallback when Git pre-commit hooks are unavailable.
"""

from __future__ import annotations

import argparse
import json
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


def _head_commit(root: Path) -> str:
    result = _run(root, ["git", "rev-parse", "--short", "HEAD"])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _repo_relative_path(root: Path, path_text: str) -> str:
    raw = str(path_text or "").strip()
    if not raw:
        return ""
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(root.resolve())
            return str(rel).replace("\\", "/")
        except Exception:
            return raw.replace("\\", "/")
    return raw.replace("\\", "/")


def _parse_last_json_object(text: str) -> dict:
    content = str(text or "").strip()
    if not content:
        return {}
    for line in reversed(content.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _is_retryable_push_failure(result: subprocess.CompletedProcess[str]) -> bool:
    if int(result.returncode) == 0:
        return False
    combined = f"{result.stdout}\n{result.stderr}".lower()
    non_retryable_tokens = (
        "authentication failed",
        "repository not found",
        "could not read username",
        "permission denied",
        "access denied",
        "remote rejected",
    )
    return not any(token in combined for token in non_retryable_tokens)


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


def _push_with_retry(
    *,
    root: Path,
    push_cmd: list[str],
    push_retries: int,
    push_retry_delay: float,
    committed_sha: str,
) -> int:
    attempts = 1 + max(0, int(push_retries))
    delay = max(0.0, float(push_retry_delay))
    last_code = 1
    push_succeeded = False
    for attempt in range(1, attempts + 1):
        push_result = _run(root, push_cmd)
        _echo(push_result)
        last_code = int(push_result.returncode)
        if last_code == 0:
            push_succeeded = True
            break
        retryable = _is_retryable_push_failure(push_result)
        if not retryable:
            print(
                "[sheetbook-guarded-commit] non-retryable push failure detected; "
                "skip retries.",
                file=sys.stderr,
            )
            break
        if attempt < attempts:
            print(
                f"[sheetbook-guarded-commit] push failed "
                f"(attempt {attempt}/{attempts}), retrying in {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)

    if push_succeeded:
        return 0
    push_command_text = " ".join(push_cmd)
    commit_hint = f" (local commit: {committed_sha})" if committed_sha else ""
    print(
        "[sheetbook-guarded-commit] push failed after "
        f"{attempts} attempt(s){commit_hint}. "
        f"retry manually: `{push_command_text}`",
        file=sys.stderr,
    )
    return int(last_code)


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
    if bool(getattr(args, "commit_handoff_refresh", False)) and not bool(
        getattr(args, "refresh_handoff_latest", False)
    ):
        print(
            "[sheetbook-guarded-commit] blocked: --commit-handoff-refresh requires "
            "--refresh-handoff-latest",
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
    committed_sha = _head_commit(root)

    if bool(args.push):
        push_cmd = ["git", "push", str(args.remote).strip() or "origin", branch]
        push_retries = max(0, int(getattr(args, "push_retries", 2) or 0))
        push_retry_delay = max(0.0, float(getattr(args, "push_retry_delay", 1.0) or 0.0))
        push_code = _push_with_retry(
            root=root,
            push_cmd=push_cmd,
            push_retries=push_retries,
            push_retry_delay=push_retry_delay,
            committed_sha=committed_sha,
        )
        if push_code != 0:
            return push_code

    if bool(getattr(args, "refresh_handoff_latest", False)):
        refresh_script = str(getattr(args, "refresh_handoff_script", "") or "").strip()
        if not refresh_script:
            refresh_script = "scripts/run_sheetbook_refresh_handoff_latest.py"
        refresh_cmd = [
            sys.executable,
            refresh_script,
            "--expected-branch",
            branch,
        ]
        refresh_timestamp = str(getattr(args, "refresh_handoff_timestamp", "") or "").strip()
        if refresh_timestamp:
            refresh_cmd.extend(["--timestamp", refresh_timestamp])
        refresh_result = _run(root, refresh_cmd)
        _echo(refresh_result)
        if refresh_result.returncode != 0:
            print(
                "[sheetbook-guarded-commit] handoff refresh failed after commit/push. "
                "run manually: `python scripts/run_sheetbook_refresh_handoff_latest.py`",
                file=sys.stderr,
            )
            return int(refresh_result.returncode)
        if bool(getattr(args, "commit_handoff_refresh", False)):
            payload = _parse_last_json_object(refresh_result.stdout)
            refresh_target = str(payload.get("handoff") or "").strip()
            if not refresh_target:
                refresh_target = str(getattr(args, "refresh_handoff_target", "") or "").strip()
            refresh_target_rel = _repo_relative_path(root, refresh_target)
            if not refresh_target_rel:
                print(
                    "[sheetbook-guarded-commit] handoff refresh target not found in output. "
                    "run manual commit for refreshed handoff file.",
                    file=sys.stderr,
                )
                return 2

            add_result = _run(root, ["git", "add", "--", refresh_target_rel])
            _echo(add_result)
            if add_result.returncode != 0:
                return int(add_result.returncode)

            staged_check = _run(root, ["git", "diff", "--cached", "--name-only", "--", refresh_target_rel])
            _echo(staged_check)
            if staged_check.returncode != 0:
                return int(staged_check.returncode)
            if not staged_check.stdout.strip():
                print("[sheetbook-guarded-commit] no handoff refresh changes to commit")
                return 0
            refresh_guard_code = _run_guard(root, branch)
            if refresh_guard_code != 0:
                print(
                    "[sheetbook-guarded-commit] blocked: refreshed handoff file failed branch guard.",
                    file=sys.stderr,
                )
                return int(refresh_guard_code)

            refresh_commit_message = str(
                getattr(args, "refresh_handoff_commit_message", "")
                or "docs(sheetbook): refresh handoff latest metadata"
            ).strip()
            refresh_commit_result = _run(root, ["git", "commit", "-m", refresh_commit_message])
            _echo(refresh_commit_result)
            if refresh_commit_result.returncode != 0:
                return int(refresh_commit_result.returncode)
            refresh_commit_sha = _head_commit(root)
            if bool(args.push):
                push_cmd = ["git", "push", str(args.remote).strip() or "origin", branch]
                push_retries = max(0, int(getattr(args, "push_retries", 2) or 0))
                push_retry_delay = max(0.0, float(getattr(args, "push_retry_delay", 1.0) or 0.0))
                push_code = _push_with_retry(
                    root=root,
                    push_cmd=push_cmd,
                    push_retries=push_retries,
                    push_retry_delay=push_retry_delay,
                    committed_sha=refresh_commit_sha,
                )
                if push_code != 0:
                    return push_code

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
    parser.add_argument(
        "--refresh-handoff-latest",
        action="store_true",
        help="run handoff latest refresh script after successful commit/push",
    )
    parser.add_argument(
        "--refresh-handoff-script",
        default="scripts/run_sheetbook_refresh_handoff_latest.py",
        help="handoff refresh script path (default: scripts/run_sheetbook_refresh_handoff_latest.py)",
    )
    parser.add_argument(
        "--refresh-handoff-timestamp",
        default="",
        help="optional timestamp text forwarded to handoff refresh script",
    )
    parser.add_argument(
        "--refresh-handoff-target",
        default="docs/handoff/HANDOFF_sheetbook_branch_latest.md",
        help="handoff file path to stage/commit after refresh when --commit-handoff-refresh is set",
    )
    parser.add_argument(
        "--commit-handoff-refresh",
        action="store_true",
        help="commit refreshed handoff file after --refresh-handoff-latest succeeds",
    )
    parser.add_argument(
        "--refresh-handoff-commit-message",
        default="docs(sheetbook): refresh handoff latest metadata",
        help="commit message used by --commit-handoff-refresh",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
