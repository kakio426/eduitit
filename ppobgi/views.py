from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from products.models import DTStudent


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
            "default_names": DEFAULT_NAMES,
            "hide_navbar": True,
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
