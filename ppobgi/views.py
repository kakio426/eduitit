from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from core.active_classroom import get_active_classroom_for_request
from products.dutyticker_scope import apply_classroom_scope
from products.models import DTRole, DTRoleAssignment, DTStudent


DEFAULT_NAMES = "\n".join(
    [
        "김민준",
        "이서연",
        "박도윤",
        "최지우",
        "정시우",
        "강서아",
        "조하준",
        "윤하은",
        "장예준",
        "임서윤",
        "한은우",
        "오민서",
        "서주원",
        "신지아",
        "권준우",
        "황채원",
        "안건우",
        "송윤아",
        "류지훈",
        "전수아",
        "홍우진",
        "고지안",
        "문선우",
        "양소윤",
        "손연우",
        "배다은",
        "백승현",
        "허지민",
        "유현우",
        "남유진",
    ]
)


def _is_phone_user_agent(user_agent):
    ua = (user_agent or "").lower()
    if "iphone" in ua or "ipod" in ua:
        return True
    if "android" in ua and "mobile" in ua:
        return True
    if "mobile" in ua and "ipad" not in ua and "tablet" not in ua:
        return True
    return False


def _is_force_desktop(request):
    return request.GET.get("force_desktop", "").lower() in ("1", "true", "yes")


def _should_block_for_large_screen_service(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    lower = ua.lower()

    if _is_force_desktop(request):
        return False

    if _is_phone_user_agent(ua):
        return True

    allow_tablet_access = getattr(settings, "ALLOW_TABLET_ACCESS", True)
    if not allow_tablet_access and ("ipad" in lower or "tablet" in lower):
        return True

    return False


@login_required
def main(request):
    active_classroom = get_active_classroom_for_request(request)
    storage_scope = f"user:{request.user.pk}"
    if active_classroom:
        storage_scope = f"{storage_scope}:classroom:{active_classroom.pk}"
    if _should_block_for_large_screen_service(request):
        return render(
            request,
            "products/mobile_not_supported.html",
            {
                "service_name": "별빛 추첨기",
                "reason": "교실 TV, PC, 태블릿 같은 큰 화면에 맞춰 설계된 서비스입니다.",
                "suggestion": "교사용 TV나 데스크톱 환경에서 실행해 주세요.",
                "continue_url": f"{request.path}?force_desktop=1",
                "hide_navbar": True,
            },
        )

    return render(
        request,
        "ppobgi/main.html",
        {
            "active_classroom": active_classroom,
            "audio_pack_name": "premium_gameshow_v1",
            "audio_pack_version": "1",
            "audio_default": "on",
            "default_names": DEFAULT_NAMES,
            "hide_navbar": True,
            "show_profile": "premium_gameshow",
            "storage_scope": storage_scope,
        },
    )


@login_required
def roster_names(request):
    names = list(
        DTStudent.objects.filter(user=request.user, is_active=True)
        .order_by("number", "name")
        .values_list("name", flat=True)
    )
    return JsonResponse({"names": names})


@login_required
def classroom_students(request, pk):
    """HSClassroom 기반 학생 목록 API (ppobgi 자동 채우기용)."""
    try:
        from happy_seed.models import HSClassroom
        classroom = HSClassroom.objects.get(pk=pk, teacher=request.user, is_active=True)
    except Exception:
        return JsonResponse({"error": "classroom not found"}, status=404)
    names = list(
        classroom.students.filter(is_active=True)
        .order_by("number", "name")
        .values_list("name", flat=True)
    )
    return JsonResponse({"names": names, "classroom_name": classroom.name})

def _serialize_role_cards(user, classroom):
    roles = list(
        apply_classroom_scope(DTRole.objects.filter(user=user), classroom)
        .order_by("time_slot", "id")
    )
    assignments_qs = (
        apply_classroom_scope(
            DTRoleAssignment.objects.filter(user=user, role__in=roles),
            classroom,
        )
        .select_related("role", "student")
        .order_by("role_id", "-date", "-id")
    )

    assignment_by_role_id = {}
    for assignment in assignments_qs:
        if assignment.role_id not in assignment_by_role_id:
            assignment_by_role_id[assignment.role_id] = assignment

    cards = []
    for role in roles:
        assignment = assignment_by_role_id.get(role.id)
        student = assignment.student if assignment and assignment.student and assignment.student.is_active else None
        cards.append(
            {
                "role_id": role.id,
                "role_name": role.name,
                "icon": role.icon or "📋",
                "description": role.description or "",
                "time_slot": role.time_slot or "오늘",
                "assignee_name": student.name if student else "미배정",
                "is_completed": bool(assignment and assignment.is_completed and student),
                "is_unassigned": student is None,
            }
        )

    return cards


@login_required
def role_cards(request):
    classroom = get_active_classroom_for_request(request)
    cards = _serialize_role_cards(request.user, classroom)
    classroom_name = classroom.name if classroom else "기본 명단"
    if cards:
        message = f"{classroom_name}의 오늘 역할 {len(cards)}개를 불러왔습니다."
    else:
        message = f"{classroom_name}의 1인 1역이 아직 없습니다. 알림판에서 먼저 설정해 주세요."

    return JsonResponse(
        {
            "classroom_name": classroom_name,
            "roles": cards,
            "message": message,
        }
    )


