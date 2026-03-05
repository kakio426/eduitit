import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
from django.utils import timezone  # noqa: E402

django.setup()

from classcalendar.message_capture import parse_message_capture_draft  # noqa: E402


@dataclass
class GoldenCase:
    case_id: str
    raw_text: str
    has_files: bool
    expected_parse_status: str
    expected_start_time: Optional[datetime]
    expected_end_time: Optional[datetime]
    expected_is_all_day: Optional[bool]
    expected_title: Optional[str]


def _local_aware(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime(year, month, day, hour, minute), tz)


def _build_cases(case_count: int, *, anchor_date: date) -> List[GoldenCase]:
    if case_count < 5:
        raise ValueError("case_count must be >= 5")

    patterns = [
        "absolute_range",
        "korean_range",
        "relative_time",
        "todo_only",
        "empty",
    ]
    cases: List[GoldenCase] = []
    index = 0
    day_offset = 1

    while len(cases) < case_count:
        pattern = patterns[index % len(patterns)]
        target = anchor_date + timedelta(days=day_offset + 5)
        case_no = len(cases) + 1

        if pattern == "absolute_range":
            start_at = _local_aware(target.year, target.month, target.day, 14, 0)
            end_at = _local_aware(target.year, target.month, target.day, 15, 0)
            cases.append(
                GoldenCase(
                    case_id=f"ABS-{case_no:03d}",
                    raw_text=(
                        f"학급 공지 {case_no}\n"
                        f"{target.year}-{target.month:02d}-{target.day:02d} 14:00-15:00 과학실 수업\n"
                        "준비물: 실험 노트"
                    ),
                    has_files=False,
                    expected_parse_status="parsed",
                    expected_start_time=start_at,
                    expected_end_time=end_at,
                    expected_is_all_day=False,
                    expected_title=f"학급 공지 {case_no}",
                )
            )
        elif pattern == "korean_range":
            start_at = _local_aware(target.year, target.month, target.day, 14, 0)
            end_at = _local_aware(target.year, target.month, target.day, 15, 0)
            cases.append(
                GoldenCase(
                    case_id=f"KOR-{case_no:03d}",
                    raw_text=(
                        f"상담 안내 {case_no}\n"
                        f"{target.month}월 {target.day}일 오후 2시-오후 3시 상담실 방문"
                    ),
                    has_files=False,
                    expected_parse_status="parsed",
                    expected_start_time=start_at,
                    expected_end_time=end_at,
                    expected_is_all_day=False,
                    expected_title=f"상담 안내 {case_no}",
                )
            )
        elif pattern == "relative_time":
            relative_date = anchor_date + timedelta(days=1)
            start_at = _local_aware(relative_date.year, relative_date.month, relative_date.day, 15, 0)
            end_at = _local_aware(relative_date.year, relative_date.month, relative_date.day, 16, 0)
            cases.append(
                GoldenCase(
                    case_id=f"REL-{case_no:03d}",
                    raw_text=f"학부모 상담 {case_no}\n내일 3시 상담실 방문",
                    has_files=False,
                    expected_parse_status="needs_review",
                    expected_start_time=start_at,
                    expected_end_time=end_at,
                    expected_is_all_day=False,
                    expected_title=f"학부모 상담 {case_no}",
                )
            )
        elif pattern == "todo_only":
            cases.append(
                GoldenCase(
                    case_id=f"TODO-{case_no:03d}",
                    raw_text=f"준비물 안내 {case_no}\n실험 노트 챙기기",
                    has_files=False,
                    expected_parse_status="needs_review",
                    expected_start_time=None,
                    expected_end_time=None,
                    expected_is_all_day=False,
                    expected_title=f"준비물 안내 {case_no}",
                )
            )
        else:
            cases.append(
                GoldenCase(
                    case_id=f"EMPTY-{case_no:03d}",
                    raw_text="",
                    has_files=False,
                    expected_parse_status="failed",
                    expected_start_time=None,
                    expected_end_time=None,
                    expected_is_all_day=False,
                    expected_title="메시지에서 만든 일정",
                )
            )

        index += 1
        if index % len(patterns) == 0:
            day_offset += 1

    return cases


def _iso_or_empty(value: Optional[datetime]) -> str:
    return value.isoformat() if value else ""


def _evaluate_cases(cases: List[GoldenCase], *, anchor_now: datetime) -> dict:
    total = len(cases)
    parse_status_matches = 0
    datetime_expected_count = 0
    datetime_matches = 0
    title_matches = 0
    failures = []

    expected_status_counts = {"parsed": 0, "needs_review": 0, "failed": 0}
    actual_status_counts = {"parsed": 0, "needs_review": 0, "failed": 0}

    for case in cases:
        result = parse_message_capture_draft(
            case.raw_text,
            now=anchor_now,
            has_files=case.has_files,
        )
        actual_status = result["parse_status"]
        expected_status = case.expected_parse_status
        expected_status_counts[expected_status] = expected_status_counts.get(expected_status, 0) + 1
        actual_status_counts[actual_status] = actual_status_counts.get(actual_status, 0) + 1

        status_ok = actual_status == expected_status
        if status_ok:
            parse_status_matches += 1

        title_ok = (result.get("extracted_title") or "") == (case.expected_title or "")
        if title_ok:
            title_matches += 1

        datetime_ok = True
        if case.expected_start_time and case.expected_end_time:
            datetime_expected_count += 1
            datetime_ok = (
                result.get("extracted_start_time") == case.expected_start_time
                and result.get("extracted_end_time") == case.expected_end_time
                and bool(result.get("extracted_is_all_day")) == bool(case.expected_is_all_day)
            )
            if datetime_ok:
                datetime_matches += 1

        if not (status_ok and datetime_ok and title_ok):
            failures.append(
                {
                    "case_id": case.case_id,
                    "raw_text": case.raw_text,
                    "expected": {
                        "parse_status": case.expected_parse_status,
                        "start_time": _iso_or_empty(case.expected_start_time),
                        "end_time": _iso_or_empty(case.expected_end_time),
                        "title": case.expected_title or "",
                    },
                    "actual": {
                        "parse_status": result.get("parse_status"),
                        "start_time": _iso_or_empty(result.get("extracted_start_time")),
                        "end_time": _iso_or_empty(result.get("extracted_end_time")),
                        "title": result.get("extracted_title") or "",
                    },
                    "warnings": result.get("warnings") or [],
                }
            )

    parse_status_accuracy = (parse_status_matches / total) if total else 0.0
    datetime_accuracy = (datetime_matches / datetime_expected_count) if datetime_expected_count else 1.0
    title_accuracy = (title_matches / total) if total else 0.0

    thresholds = {
        "parse_status_accuracy_min": 0.90,
        "datetime_accuracy_min": 0.85,
        "title_accuracy_min": 0.90,
    }
    reasons = []
    if parse_status_accuracy < thresholds["parse_status_accuracy_min"]:
        reasons.append("parse_status_accuracy below threshold")
    if datetime_accuracy < thresholds["datetime_accuracy_min"]:
        reasons.append("datetime_accuracy below threshold")
    if title_accuracy < thresholds["title_accuracy_min"]:
        reasons.append("title_accuracy below threshold")

    return {
        "total_cases": total,
        "expected_status_counts": expected_status_counts,
        "actual_status_counts": actual_status_counts,
        "parse_status_accuracy": round(parse_status_accuracy, 4),
        "datetime_accuracy": round(datetime_accuracy, 4),
        "title_accuracy": round(title_accuracy, 4),
        "thresholds": thresholds,
        "evaluation": {
            "pass": not reasons,
            "reasons": reasons,
        },
        "failure_count": len(failures),
        "failure_samples": failures[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run message capture golden-set evaluation against classcalendar parser."
    )
    parser.add_argument("--case-count", type=int, default=150, help="number of golden cases to evaluate")
    parser.add_argument(
        "--output",
        default="docs/handoff/message_capture_golden_eval_latest.json",
        help="output JSON path",
    )
    parser.add_argument(
        "--anchor-date",
        default="2026-03-04",
        help="anchor date for relative expressions (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    anchor_date = datetime.strptime(args.anchor_date, "%Y-%m-%d").date()
    anchor_now = _local_aware(anchor_date.year, anchor_date.month, anchor_date.day, 9, 0)
    cases = _build_cases(args.case_count, anchor_date=anchor_date)
    summary = _evaluate_cases(cases, anchor_now=anchor_now)

    report = {
        "generated_at": timezone.localtime().isoformat(),
        "anchor_date": args.anchor_date,
        "parser": "classcalendar.message_capture.parse_message_capture_draft",
        "case_count": len(cases),
        "summary": summary,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[message-capture] golden evaluation written: {output_path}")
    print(
        "[message-capture] metrics:",
        f"parse_status_accuracy={summary['parse_status_accuracy']:.4f}",
        f"datetime_accuracy={summary['datetime_accuracy']:.4f}",
        f"title_accuracy={summary['title_accuracy']:.4f}",
        f"pass={summary['evaluation']['pass']}",
    )
    return 0 if summary["evaluation"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
