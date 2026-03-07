import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_IDS = {
    "recipients-textarea",
    "recipients-cleanup-btn",
    "recipients-cleanup-undo-btn",
    "recipients-copy-issues-btn",
    "recipients-prev-issue-btn",
    "recipients-next-issue-btn",
    "recipients-submit-btn",
}

REQUIRED_TESTIDS = {
    "recipients-textarea",
    "recipients-cleanup-btn",
    "recipients-cleanup-undo-btn",
    "recipients-copy-issues-btn",
    "recipients-prev-issue-btn",
    "recipients-next-issue-btn",
    "recipients-jump-top-btn",
    "recipients-jump-bottom-btn",
    "recipients-submit-btn",
}

REQUIRED_JUMP_VALUES = {"top", "bottom"}

REQUIRED_HIDDEN_NAMES = {
    "recipients_cleanup_applied",
    "recipients_cleanup_removed_count",
    "recipients_cleanup_undo_used",
    "recipients_issue_copy_used",
    "recipients_issue_jump_count",
}


def _default_template_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "sheetbook"
        / "templates"
        / "sheetbook"
        / "consent_review.html"
    )


def _extract_hidden_names(content: str) -> set[str]:
    names: set[str] = set()
    for tag in re.findall(r"<input\b[^>]*>", content, flags=re.IGNORECASE):
        if 'type="hidden"' not in tag and "type='hidden'" not in tag:
            continue
        match = re.search(r'name="([^"]+)"', tag) or re.search(r"name='([^']+)'", tag)
        if match:
            names.add(match.group(1))
    return names


def _extract_tokens(content: str) -> dict[str, set[str]]:
    return {
        "ids": set(re.findall(r'id="([^"]+)"', content)),
        "testids": set(re.findall(r'data-testid="([^"]+)"', content)),
        "jump_values": set(re.findall(r'data-recipients-jump="([^"]+)"', content)),
        "hidden_names": _extract_hidden_names(content),
    }


def _build_order_check(name: str, content: str, ordered_tokens: list[str]) -> dict[str, Any]:
    positions = []
    for token in ordered_tokens:
        pos = content.find(token)
        if pos < 0:
            return {"name": name, "ok": False, "error": f"missing token: {token}"}
        positions.append(pos)
    is_ordered = positions == sorted(positions)
    return {
        "name": name,
        "ok": is_ordered,
        "error": "" if is_ordered else "order mismatch",
    }


def _build_report(*, content: str, template_path: str, strict_extras: bool) -> dict[str, Any]:
    observed = _extract_tokens(content)
    missing = {
        "ids": sorted(REQUIRED_IDS - observed["ids"]),
        "testids": sorted(REQUIRED_TESTIDS - observed["testids"]),
        "jump_values": sorted(REQUIRED_JUMP_VALUES - observed["jump_values"]),
        "hidden_names": sorted(REQUIRED_HIDDEN_NAMES - observed["hidden_names"]),
    }
    extra = {
        "ids": sorted(observed["ids"] - REQUIRED_IDS),
        "testids": sorted(observed["testids"] - REQUIRED_TESTIDS),
        "jump_values": sorted(observed["jump_values"] - REQUIRED_JUMP_VALUES),
        "hidden_names": sorted(observed["hidden_names"] - REQUIRED_HIDDEN_NAMES),
    }
    order_checks = [
        _build_order_check(
            "cleanup button order",
            content,
            [
                'id="recipients-cleanup-btn"',
                'id="recipients-cleanup-undo-btn"',
            ],
        ),
        _build_order_check(
            "issue navigation order",
            content,
            [
                'id="recipients-prev-issue-btn"',
                'id="recipients-next-issue-btn"',
                'data-recipients-jump="top"',
                'data-recipients-jump="bottom"',
            ],
        ),
    ]

    reasons: list[str] = []
    if any(missing.values()):
        reasons.append("missing_required_tokens")
    if strict_extras and any(extra.values()):
        reasons.append("unexpected_extra_tokens")
    if any(not bool(item.get("ok")) for item in order_checks):
        reasons.append("order_mismatch")

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "PASS" if not reasons else "HOLD",
        "strict_extras": bool(strict_extras),
        "reasons": reasons,
        "template_path": template_path,
        "missing": missing,
        "extra": extra,
        "order_checks": order_checks,
    }


def _format_items(items: list[str], *, prefix: str) -> list[str]:
    return [f"- {prefix}{item}" for item in items]


def _build_markdown(*, report: dict[str, Any], json_output_path: Path) -> str:
    missing = report.get("missing") or {}
    extra = report.get("extra") or {}
    order_checks = report.get("order_checks") or []

    lines = [
        "# Sheetbook Consent Freeze Snapshot",
        "",
        f"- Generated at: {report.get('generated_at', '-')}",
        f"- Status: `{report.get('status', '-')}`",
        f"- Template: `{report.get('template_path', '-')}`",
        f"- Strict extras: {'YES' if report.get('strict_extras') else 'NO'}",
        f"- JSON output: `{json_output_path}`",
        "",
        "## Reasons",
    ]
    reasons = report.get("reasons") or []
    if reasons:
        lines.extend([f"- {reason}" for reason in reasons])
    else:
        lines.append("- none")

    lines.extend(["", "## Missing Tokens"])
    missing_lines = []
    missing_lines.extend(_format_items(missing.get("ids") or [], prefix='id="'))
    if missing_lines:
        missing_lines = [line + '"' if line.startswith('- id="') else line for line in missing_lines]
    missing_lines.extend(_format_items(missing.get("testids") or [], prefix='data-testid="'))
    if missing.get("testids"):
        missing_lines.extend([])
    lines.extend(missing_lines if missing_lines else ["- none"])
    if missing.get("testids"):
        for item in missing.get("testids") or []:
            lines.append(f'- data-testid="{item}"')
    if missing.get("jump_values"):
        for item in missing.get("jump_values") or []:
            lines.append(f'- data-recipients-jump="{item}"')
    if missing.get("hidden_names"):
        for item in missing.get("hidden_names") or []:
            lines.append(f'- hidden name="{item}"')

    lines.extend(["", "## Extra Tokens"])
    extra_lines = []
    for item in extra.get("ids") or []:
        extra_lines.append(f'- id="{item}"')
    for item in extra.get("testids") or []:
        extra_lines.append(f'- data-testid="{item}"')
    for item in extra.get("jump_values") or []:
        extra_lines.append(f'- data-recipients-jump="{item}"')
    for item in extra.get("hidden_names") or []:
        extra_lines.append(f'- hidden name="{item}"')
    lines.extend(extra_lines if extra_lines else ["- none"])

    lines.extend(["", "## Order Checks"])
    for item in order_checks:
        status = "PASS" if item.get("ok") else "FAIL"
        error = item.get("error") or ""
        if error:
            lines.append(f"- [{status}] {item.get('name')}: {error}")
        else:
            lines.append(f"- [{status}] {item.get('name')}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sheetbook consent freeze snapshot.")
    parser.add_argument("--template-path", default="", help="점검할 consent_review template 경로")
    parser.add_argument(
        "--strict-extras",
        action="store_true",
        help="허용되지 않은 extra token도 HOLD로 처리합니다.",
    )
    parser.add_argument(
        "--json-output",
        default="docs/handoff/sheetbook_consent_freeze_snapshot_latest.json",
        help="JSON 출력 경로",
    )
    parser.add_argument(
        "--md-output",
        default="docs/handoff/sheetbook_consent_freeze_snapshot_latest.md",
        help="Markdown 출력 경로",
    )
    args = parser.parse_args()

    template_path = Path(args.template_path) if args.template_path else _default_template_path()
    content = template_path.read_text(encoding="utf-8")
    report = _build_report(
        content=content,
        template_path=str(template_path),
        strict_extras=bool(args.strict_extras),
    )

    root = Path(__file__).resolve().parents[1]
    json_output_path = Path(args.json_output)
    md_output_path = Path(args.md_output)
    if not json_output_path.is_absolute():
        json_output_path = root / json_output_path
    if not md_output_path.is_absolute():
        md_output_path = root / md_output_path

    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_output_path.write_text(
        _build_markdown(report=report, json_output_path=json_output_path),
        encoding="utf-8",
    )
    print(json.dumps({"report": report, "json_output": str(json_output_path), "md_output": str(md_output_path)}, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
