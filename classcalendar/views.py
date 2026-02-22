from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from happy_seed.models import HSClassroom
from products.models import Product

from .forms import CalendarEventCreateForm
from .models import CalendarEvent

SERVICE_ROUTE = "classcalendar:main"


def _serialize_event(event):
    return {
        "id": str(event.id),
        "title": event.title,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "is_all_day": event.is_all_day,
        "color": event.color or "indigo",
        "source": event.source,
        "visibility": event.visibility,
    }


def _get_active_classroom_for_user(request):
    classroom_id = request.session.get("active_classroom_id")
    if not classroom_id:
        return None
    return HSClassroom.objects.filter(id=classroom_id, teacher=request.user, is_active=True).first()


def _get_teacher_visible_events(request):
    active_classroom = _get_active_classroom_for_user(request)
    queryset = CalendarEvent.objects.filter(author=request.user)
    if active_classroom:
        queryset = CalendarEvent.objects.filter(Q(author=request.user) | Q(classroom=active_classroom))
    return queryset.select_related("classroom").distinct().order_by("start_time", "id")


def _get_owned_event(request, event_id):
    return get_object_or_404(CalendarEvent, id=event_id, author=request.user)


@login_required
def main_view(request):
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    context = {
        "service": service,
        "title": service.title if service else "학급 캘린더 (Eduitit Calendar)",
        "events_json": [_serialize_event(event) for event in _get_teacher_visible_events(request)],
    }
    return render(request, "classcalendar/main.html", context)


@login_required
@require_GET
def api_events(request):
    events_data = [_serialize_event(event) for event in _get_teacher_visible_events(request)]
    return JsonResponse({"status": "success", "events": events_data})


@login_required
@require_POST
def api_create_event(request):
    classroom = _get_active_classroom_for_user(request)
    if not classroom:
        return JsonResponse(
            {
                "status": "error",
                "code": "active_classroom_required",
                "message": "활성 학급이 없어 일정을 생성할 수 없습니다.",
            },
            status=400,
        )

    form = CalendarEventCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    event = CalendarEvent.objects.create(
        title=form.cleaned_data["title"],
        start_time=form.cleaned_data["start_time"],
        end_time=form.cleaned_data["end_time"],
        is_all_day=form.cleaned_data.get("is_all_day", False),
        color=form.cleaned_data.get("color") or "indigo",
        visibility=CalendarEvent.VISIBILITY_TEACHER,
        author=request.user,
        classroom=classroom,
        source=CalendarEvent.SOURCE_LOCAL,
    )
    return JsonResponse({"status": "success", "event": _serialize_event(event)}, status=201)


@login_required
@require_POST
def api_update_event(request, event_id):
    event = _get_owned_event(request, event_id)
    form = CalendarEventCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "status": "error",
                "code": "validation_error",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    event.title = form.cleaned_data["title"]
    event.start_time = form.cleaned_data["start_time"]
    event.end_time = form.cleaned_data["end_time"]
    event.is_all_day = form.cleaned_data.get("is_all_day", False)
    event.color = form.cleaned_data.get("color") or "indigo"
    event.visibility = CalendarEvent.VISIBILITY_TEACHER
    event.source = CalendarEvent.SOURCE_LOCAL
    event.save(
        update_fields=[
            "title",
            "start_time",
            "end_time",
            "is_all_day",
            "color",
            "visibility",
            "source",
            "updated_at",
        ]
    )
    return JsonResponse({"status": "success", "event": _serialize_event(event)})


@login_required
@require_POST
def api_delete_event(request, event_id):
    event = _get_owned_event(request, event_id)
    event_id_str = str(event.id)
    event.delete()
    return JsonResponse({"status": "success", "deleted_id": event_id_str})
