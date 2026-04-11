from ..models import TimetableClassInputStatus, TimetableWorkspace


def _sort_timestamp(value):
    return value.timestamp() if value else 0


def build_progress_summary(classrooms, status_map):
    counts = {
        TimetableClassInputStatus.Status.NOT_STARTED: 0,
        TimetableClassInputStatus.Status.EDITING: 0,
        TimetableClassInputStatus.Status.SUBMITTED: 0,
        TimetableClassInputStatus.Status.REVIEWED: 0,
        TimetableClassInputStatus.Status.PUBLISHED: 0,
    }
    review_queue = []
    active_rows = []

    for classroom in classrooms:
        status = status_map.get(classroom.id)
        current_status = status.status if status else TimetableClassInputStatus.Status.NOT_STARTED
        counts[current_status] = counts.get(current_status, 0) + 1
        item = {
            "classroom_id": classroom.id,
            "classroom_label": classroom.label,
            "status": current_status,
            "status_label": status.get_status_display() if status else TimetableClassInputStatus.Status.NOT_STARTED.label,
            "editor_name": status.editor_name if status else "",
            "last_saved_at": getattr(status, "last_saved_at", None),
            "submitted_at": getattr(status, "submitted_at", None),
            "reviewed_at": getattr(status, "reviewed_at", None),
        }
        if current_status == TimetableClassInputStatus.Status.SUBMITTED:
            review_queue.append(item)
        if current_status in {
            TimetableClassInputStatus.Status.EDITING,
            TimetableClassInputStatus.Status.SUBMITTED,
        }:
            active_rows.append(item)

    total_classes = len(classrooms)
    started_count = total_classes - counts[TimetableClassInputStatus.Status.NOT_STARTED]
    reviewed_count = counts[TimetableClassInputStatus.Status.REVIEWED] + counts[TimetableClassInputStatus.Status.PUBLISHED]
    submitted_count = (
        counts[TimetableClassInputStatus.Status.SUBMITTED]
        + counts[TimetableClassInputStatus.Status.REVIEWED]
        + counts[TimetableClassInputStatus.Status.PUBLISHED]
    )
    return {
        "total_classes": total_classes,
        "not_started_count": counts[TimetableClassInputStatus.Status.NOT_STARTED],
        "editing_count": counts[TimetableClassInputStatus.Status.EDITING],
        "submitted_count": counts[TimetableClassInputStatus.Status.SUBMITTED],
        "reviewed_count": counts[TimetableClassInputStatus.Status.REVIEWED],
        "published_count": counts[TimetableClassInputStatus.Status.PUBLISHED],
        "started_count": started_count,
        "ready_for_review_count": submitted_count,
        "review_complete_count": reviewed_count,
        "review_required_count": max(0, total_classes - reviewed_count),
        "input_completion_percent": round((submitted_count / total_classes) * 100) if total_classes else 0,
        "review_completion_percent": round((reviewed_count / total_classes) * 100) if total_classes else 0,
        "review_queue": sorted(
            review_queue,
            key=lambda item: (
                _sort_timestamp(item["submitted_at"] or item["last_saved_at"]),
                item["classroom_label"],
            ),
            reverse=True,
        )[:5],
        "active_rows": sorted(
            active_rows,
            key=lambda item: (
                _sort_timestamp(item["last_saved_at"] or item["submitted_at"]),
                item["classroom_label"],
            ),
            reverse=True,
        )[:5],
    }


def build_publish_readiness(workspace, validation, progress_summary):
    review_blockers = []
    warnings = list((validation or {}).get("warnings") or [])
    validation_conflicts = list((validation or {}).get("conflicts") or [])
    if progress_summary["total_classes"] == 0:
        review_blockers.append("아직 학년 반이 없어 확정할 수 없습니다.")
    elif progress_summary["review_required_count"] > 0:
        review_blockers.append(f"{progress_summary['review_required_count']}개 반이 아직 관리자 검토 전입니다.")
    blockers = review_blockers + validation_conflicts

    if workspace.status == TimetableWorkspace.Status.PUBLISHED and workspace.published_snapshot_id:
        workflow_stage = "published"
        workflow_label = "확정됨"
        stage_message = "현재 확정본 링크가 배포된 상태입니다."
    elif review_blockers:
        workflow_stage = "review_required"
        workflow_label = "검토 필요"
        stage_message = review_blockers[0]
    elif validation_conflicts:
        workflow_stage = "draft"
        workflow_label = "초안"
        stage_message = validation_conflicts[0]
    else:
        workflow_stage = "publish_ready"
        workflow_label = "확정 가능"
        stage_message = "모든 반 검토가 끝났고 현재 큰 충돌이 없습니다."

    if workflow_stage == "review_required" and progress_summary["editing_count"] and not validation_conflicts:
        stage_message = f"입력 중인 반 {progress_summary['editing_count']}개를 먼저 마무리해 주세요."

    return {
        "workflow_stage": workflow_stage,
        "workflow_label": workflow_label,
        "stage_message": stage_message,
        "can_publish": not blockers and not validation_conflicts,
        "blockers": blockers,
        "warnings": warnings,
    }
