#!/usr/bin/env python
"""Branch-specific file path guard.

Usage examples:
  python scripts/branch_path_guard.py --staged
  python scripts/branch_path_guard.py --branch feature/sheetbook --files-file changed_files.txt
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES_FILE = REPO_ROOT / "scripts" / "branch_path_rules.json"


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _current_branch() -> str:
    return _run_git("rev-parse", "--abbrev-ref", "HEAD")


def _normalize_path(path: str) -> str:
    normalized = (path or "").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _path_matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _branch_matches(branch: str, patterns: list[str]) -> bool:
    branch = (branch or "").strip()
    short = branch.replace("refs/heads/", "", 1)
    candidates = {branch, short}
    return any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates for pattern in patterns)


def _load_rules(rules_file: Path) -> list[dict[str, Any]]:
    payload = json.loads(rules_file.read_text(encoding="utf-8"))
    rules = payload.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("rules must be a list")
    return [rule for rule in rules if isinstance(rule, dict)]


def _collect_files(args: argparse.Namespace) -> list[str]:
    if args.staged:
        raw = _run_git("diff", "--cached", "--name-only", "--diff-filter=ACMRD")
        return [_normalize_path(line) for line in raw.splitlines() if _normalize_path(line)]

    if args.files_file:
        file_path = Path(args.files_file)
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return [_normalize_path(line) for line in lines if _normalize_path(line)]

    if args.files:
        return [_normalize_path(line) for line in args.files if _normalize_path(line)]

    return []


def _validate_rule(rule: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    branch_patterns = rule.get("branch_patterns") or []
    allow_patterns = rule.get("allow") or []
    deny_patterns = rule.get("deny") or []

    if not isinstance(branch_patterns, list):
        raise ValueError("branch_patterns must be a list")
    if not isinstance(allow_patterns, list):
        raise ValueError("allow must be a list")
    if not isinstance(deny_patterns, list):
        raise ValueError("deny must be a list")
    return branch_patterns, allow_patterns, deny_patterns


def run(args: argparse.Namespace) -> int:
    rules_file = Path(args.rules_file).resolve()
    if not rules_file.exists():
        print(f"[branch-guard] rules file not found: {rules_file}", file=sys.stderr)
        return 2

    rules = _load_rules(rules_file)
    branch = args.branch or _current_branch()
    files = _collect_files(args)

    if not files:
        print(f"[branch-guard] no files to check (branch={branch})")
        return 0

    matched_rules: list[dict[str, Any]] = []
    for rule in rules:
        branch_patterns, _, _ = _validate_rule(rule)
        if _branch_matches(branch, [str(pattern) for pattern in branch_patterns]):
            matched_rules.append(rule)

    if not matched_rules:
        print(f"[branch-guard] no branch policy matched for '{branch}', skipping")
        return 0

    violations: list[tuple[str, str, str]] = []
    for rule in matched_rules:
        name = str(rule.get("name") or "unnamed-rule")
        _, allow_patterns, deny_patterns = _validate_rule(rule)
        allow_patterns = [str(pattern) for pattern in allow_patterns]
        deny_patterns = [str(pattern) for pattern in deny_patterns]

        for file_path in files:
            if deny_patterns and _path_matches(file_path, deny_patterns):
                violations.append((name, file_path, "matches deny pattern"))
                continue
            if allow_patterns and not _path_matches(file_path, allow_patterns):
                violations.append((name, file_path, "outside allowed paths"))

    if not violations:
        print(
            f"[branch-guard] passed ({len(files)} files, branch={branch}, rules={len(matched_rules)})"
        )
        return 0

    print(f"[branch-guard] blocked: {len(violations)} violation(s) on branch '{branch}'")
    grouped: dict[str, list[tuple[str, str]]] = {}
    for rule_name, file_path, reason in violations:
        grouped.setdefault(rule_name, []).append((file_path, reason))

    for rule_name, items in grouped.items():
        print(f"\nRule: {rule_name}")
        for file_path, reason in sorted(items):
            print(f"  - {file_path} ({reason})")

    print("\nAllowed paths can be adjusted in scripts/branch_path_rules.json when truly needed.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Branch-specific file path guard")
    parser.add_argument("--branch", default="", help="branch name override")
    parser.add_argument("--staged", action="store_true", help="check staged files")
    parser.add_argument("--files-file", default="", help="newline-delimited files list")
    parser.add_argument("--files", nargs="*", default=[], help="explicit file paths")
    parser.add_argument(
        "--rules-file",
        default=str(DEFAULT_RULES_FILE),
        help="path to JSON rules file",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    raise SystemExit(run(parser.parse_args()))
