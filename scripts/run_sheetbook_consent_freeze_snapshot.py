import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


REQUIRED_IDS = [
    "recipients-textarea",
    "recipients-cleanup-btn",
    "recipients-cleanup-undo-btn",
    "recipients-copy-issues-btn",
    "recipients-prev-issue-btn",
    "recipients-next-issue-btn",
    "recipients-submit-btn",
]

REQUIRED_TESTIDS = [
    "recipients-textarea",
    "recipients-cleanup-btn",
    "recipients-cleanup-undo-btn",
    "recipients-copy-issues-btn",
    "recipients-prev-issue-btn",
    "recipients-next-issue-btn",
    "recipients-jump-top-btn",
    "recipients-jump-bottom-btn",
    "recipients-submit-btn",
]

REQUIRED_JUMP_VALUES = ["top", "bottom"]

REQUIRED_HIDDEN_NAMES = [
    "recipients_cleanup_applied",
    "recipients_cleanup_removed_count",
    "recipients_cleanup_undo_used",
    "recipients_issue_copy_used",
    "recipients_issue_jump_count",
]

ORDER_RULES = [
    {
        "name": "cleanup button order",
        "tokens": [
            'id="recipients-cleanup-btn"',
            'id="recipients-cleanup-undo-btn"',
            'id="recipients-copy-issues-btn"',
        ],
    },
    {
        "name": "issue navigation order",
        "tokens": [
            'id="recipients-prev-issue-btn"',
            'id="recipients-next-issue-btn"',
            'data-testid="recipients-jump-top-btn"',
            'data-testid="recipients-jump-bottom-btn"',
        ],
    },
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(root: Path, raw: str, *, default_rel_path: str) -> Path:
    if not raw:
        return root / default_rel_path
    path = Path(str(raw))
    if not path.is_absolute():
        path = root / path
    return path


def _extract_hidden_input_names(content: str) -> list[str]:
    names = set()
    for match in re.finditer(r"<input\b[^>]*>", content, flags=re.IGNORECASE):
        tag = match.group(0)
        if not re.search(r'type\s*=\s*"hidden"', tag, flags=re.IGNORECASE):
            continue
        name_match = re.search(r'name\s*=\s*"([^"]+)"', tag, flags=re.IGNORECASE)
        if name_match:
            names.add(name_match.group(1).strip())
    return sorted(name for name in names if name)


def _extract_snapshot(content: str) -> dict[str, list[str]]:
    ids = sorted(set(re.findall(r'id\s*=\s*"([^"]+)"', content)))
    testids = sorted(set(re.findall(r'data-testid\s*=\s*"([^"]+)"', content)))
    jump_values = sorted(set(re.findall(r'data-recipients-jump\s*=\s*"([^"]+)"', content)))
    hidden_names = _extract_hidden_input_names(content)
    return {
        "ids": ids,
        "testids": testids,
        "jump_values": jump_values,
        "hidden_names": hidden_names,
    }


def _validate_order(content: str, rule: dict[str, Any]) -> dict[str, Any]:
    tokens = [str(token) for token in (rule.get("tokens") or [])]
    name = str(rule.get("name") or "order")
    indices = [content.find(token) for token in tokens]

    missing_tokens = [token for token, idx in zip(tokens, indices) if idx < 0]
    if missing_tokens:
        return {
            "name": name,
            "ok": False,
            "tokens": tokens,
            "error": f"missing token(s): {', '.join(missing_tokens)}",
        }

    for left, right in zip(indices, indices[1:]):
        if left >= right:
            return {
                "name": name,
                "ok": False,
                "tokens": tokens,
                "error": f"order mismatch: {' -> '.join(tokens)}",
            }

    return {
        "name": name,
        "ok": True,
        "tokens": tokens,
        "error": "",
    }


def _build_report(
    *,
    content: str,
    template_path: str,
    strict_extras: bool,
) -> dict[str, Any]:
    snapshot = _extract_snapshot(content)
    ids = snapshot["ids"]
    testids = snapshot["testids"]
    jump_values = snapshot["jump_values"]
    hidden_names = snapshot["hidden_names"]

    missing = {
        "ids": sorted(name for name in REQUIRED_IDS if name not in ids),
        "testids": sorted(name for name in REQUIRED_TESTIDS if name not in testids),
        "jump_values": sorted(name for name in REQUIRED_JUMP_VALUES if name not in jump_values),
        "hidden_names": sorted(name for name in REQUIRED_HIDDEN_NAMES if name not in hidden_names),
    }
    extra = {
        "ids": sorted(name for name in ids if name.startswith("recipients-") and name not in REQUIRED_IDS),
        "testids": sorted(
            name for name in testids if name.startswith("recipients-") and name not in REQUIRED_TESTIDS
        ),
        "jump_values": sorted(name for name in jump_values if name not in REQUIRED_JUMP_VALUES),
        "hidden_names": sorted(
            name for name in hidden_names if name.startswith("recipients_") and name not in REQUIRED_HIDDEN_NAMES
        ),
    }

    order_checks = [_validate_order(content, rule=rule) for rule in ORDER_RULES]

    reasons: list[str] = []
    if any(missing.values()):
        reasons.append("missing_required_tokens")
    if any(not bool(item.get("ok")) for item in order_checks):
        reasons.append("order_violation")
    if strict_extras and any(extra.values()):
        reasons.append("unexpected_extra_tokens")

    status = "PASS" if not reasons else "HOLD"
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template_path": template_path,
        "strict_extras": strict_extras,
        "status": status,
        "reasons": reasons,
        "required": {
            "ids": REQUIRED_IDS,
            "testids": REQUIRED_TESTIDS,
            "jump_values": REQUIRED_JUMP_VALUES,
            "hidden_names": REQUIRED_HIDDEN_NAMES,
            "order_rules": ORDER_RULES,
        },
        "current": snapshot,
        "missing": missing,
        "extra": extra,
        "order_checks": order_checks,
    }


def _build_markdown(*, report: dict[str, Any], json_output_path: Path) -> str:
    status = str(report.get("status") or "HOLD").upper()
    reasons = [str(item) for item in (report.get("reasons") or []) if str(item)]
    reasons_text = ", ".join(reasons) if reasons else "(없음)"

    missing = report.get("missing") or {}
    extra = report.get("extra") or {}
    missing_lines = [
        f"- ids: {', '.join(missing.get('ids') or []) or '(없음)'}",
        f"- testids: {', '.join(missing.get('testids') or []) or '(없음)'}",
        f"- jump_values: {', '.join(missing.get('jump_values') or []) or '(없음)'}",
        f"- hidden_names: {', '.join(missing.get('hidden_names') or []) or '(없음)'}",
    ]
    extra_lines = [
        f"- ids: {', '.join(extra.get('ids') or []) or '(없음)'}",
        f"- testids: {', '.join(extra.get('testids') or []) or '(없음)'}",
        f"- jump_values: {', '.join(extra.get('jump_values') or []) or '(없음)'}",
        f"- hidden_names: {', '.join(extra.get('hidden_names') or []) or '(없음)'}",
    ]

    order_lines: list[str] = []
    for check in report.get("order_checks") or []:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "order")
        ok = bool(check.get("ok"))
        error = str(check.get("error") or "")
        if ok:
            order_lines.append(f"- [PASS] {name}")
        else:
            order_lines.append(f"- [FAIL] {name}: {error}")
    if not order_lines:
        order_lines.append("- (none)")

    return f"""# Sheetbook Consent Freeze Snapshot ({report.get('generated_at', '')})

- status: `{status}`
- strict_extras: `{bool(report.get("strict_extras"))}`
- reasons: {reasons_text}
- template_path: `{report.get("template_path", "")}`
- json_output: `{json_output_path}`

## Missing
{chr(10).join(missing_lines)}

## Extra
{chr(10).join(extra_lines)}

## Order Checks
{chr(10).join(order_lines)}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot consent_review freeze tokens and write diff report JSON."
    )
    parser.add_argument(
        "--template-path",
        default="",
        help="consent_review template path (default: sheetbook/templates/sheetbook/consent_review.html)",
    )
    parser.add_argument(
        "--output",
        default="docs/handoff/sheetbook_consent_freeze_snapshot_latest.json",
        help="snapshot output JSON path",
    )
    parser.add_argument(
        "--strict-extras",
        action="store_true",
        help="extra recipients-* tokens도 HOLD 판정으로 취급",
    )
    parser.add_argument(
        "--md-output",
        default="",
        help="markdown output path (default: docs/runbooks/logs/SHEETBOOK_CONSENT_FREEZE_<YYYY-MM-DD>.md)",
    )
    args = parser.parse_args()

    root = _repo_root()
    today = date.today().isoformat()
    template_path = _resolve_path(
        root,
        args.template_path,
        default_rel_path="sheetbook/templates/sheetbook/consent_review.html",
    )
    output_path = _resolve_path(
        root,
        args.output,
        default_rel_path="docs/handoff/sheetbook_consent_freeze_snapshot_latest.json",
    )

    content = template_path.read_text(encoding="utf-8")
    report = _build_report(
        content=content,
        template_path=str(template_path),
        strict_extras=bool(args.strict_extras),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_output_path = _resolve_path(
        root,
        args.md_output,
        default_rel_path=f"docs/runbooks/logs/SHEETBOOK_CONSENT_FREEZE_{today}.md",
    )
    md_output_path.parent.mkdir(parents=True, exist_ok=True)
    md_output_path.write_text(
        _build_markdown(report=report, json_output_path=output_path),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": report.get("status"),
                "reasons": report.get("reasons"),
                "output": str(output_path),
                "md_output": str(md_output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
