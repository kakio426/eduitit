import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from core.ai_usage_limits import (
    _cache_key,
    _current_count,
    _normalize_limits,
    consume_ai_usage_limit,
    user_usage_subject,
)
from products.models import Product

from .forms import BambooCommentForm, BambooStoryForm
from .models import BambooComment, BambooCommentReport, BambooConsent, BambooLike, BambooReport, BambooStory
from .utils.llm import BambooLlmError, generate_bamboo_fable
from .utils.comments import comment_error_message, sanitize_comment_body
from .utils.sanitizer import sanitize_input
from .utils.validator import extract_fable_title, validate_fable_output

BAMBOO_USAGE_BUCKET = "bamboo:generate"
BAMBOO_USAGE_LIMITS = ((3600, 2), (86400, 5))
LIMIT_MESSAGE = "오늘은 충분히 쏟아내셨어요. 내일 다시 숲을 찾아주세요."
SAFETY_FALLBACK_MESSAGE = "이번에는 우화로 풀기 어려운 사연이에요. 조금 더 일반적으로 다시 적어주세요."


def _service():
    return (
        Product.objects.filter(launch_route_name="bamboo:feed", is_active=True).first()
        or Product.objects.filter(title="교사 대나무숲").first()
    )


@login_required
def feed(request):
    sort = request.GET.get("sort") or "latest"
    if sort not in {"latest", "popular", "comments"}:
        sort = "latest"
    stories = (
        BambooStory.objects.visible()
        .select_related("author")
        .prefetch_related("likes")
    )
    if sort == "popular":
        stories = stories.order_by("-like_count", "-comment_count", "-created_at")
    elif sort == "comments":
        stories = stories.order_by("-comment_count", "-created_at")
    else:
        stories = stories.order_by("-created_at")
    paginator = Paginator(stories, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    _mark_liked(page_obj.object_list, request.user)

    context = {
        "service": _service(),
        "stories": page_obj.object_list,
        "page_obj": page_obj,
        "sort": sort,
        "usage": _usage_context(request.user),
    }
    context.update(_sns_context(request))
    return _private(render(request, "bamboo/feed.html", context))


@login_required
def write(request):
    has_consent = BambooConsent.objects.filter(user=request.user).exists()
    if request.method == "POST":
        return _handle_write_post(request, has_consent=has_consent)

    context = {
        "service": _service(),
        "form": BambooStoryForm(),
        "has_consent": has_consent,
        "usage": _usage_context(request.user),
    }
    return _private(render(request, "bamboo/write.html", context))


@login_required
def result(request, story_uuid):
    story = _get_story_for_user(story_uuid, request.user)
    _mark_liked([story], request.user)
    return _private(render(request, "bamboo/result.html", {"service": _service(), "story": story}))


@login_required
def post(request, story_uuid):
    story = _get_story_for_user(story_uuid, request.user)
    _count_view_once(request, story)
    _mark_liked([story], request.user)
    context = {
        "service": _service(),
        "story": story,
        "comment_form": BambooCommentForm(),
    }
    context.update(_comments_context(story))
    return _private(render(request, "bamboo/post.html", context))


@login_required
@require_POST
def update_visibility(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid, author=request.user)
    if story.is_hidden_by_report:
        messages.warning(request, "신고 검토 중")
        return redirect("bamboo:result", story_uuid=story.uuid)

    story.is_public = str(request.POST.get("is_public") or "").lower() in {"1", "true", "on", "yes"}
    story.save(update_fields=["is_public"])
    messages.success(request, "공개" if story.is_public else "비공개")
    return redirect("bamboo:result", story_uuid=story.uuid)


@login_required
@require_POST
def like_story(request, story_uuid):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    like = BambooLike.objects.filter(user=request.user, story=story).first()
    if like:
        like.delete()
    else:
        BambooLike.objects.create(user=request.user, story=story)
    story.like_count = BambooLike.objects.filter(story=story).count()
    story.save(update_fields=["like_count"])
    _mark_liked([story], request.user)
    if request.headers.get("HX-Request") == "true" and request.POST.get("source") == "post":
        return _private(render(request, "bamboo/partials/story_actions.html", {"story": story}))
    if request.headers.get("HX-Request") != "true":
        return redirect(_safe_bamboo_next(request.POST.get("next")) or "bamboo:feed")
    return _private(render(request, "bamboo/partials/story_card.html", {"story": story}))


@login_required
@require_POST
def report_story(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if story.author_id == request.user.id:
        return HttpResponseForbidden("본인 글은 신고할 수 없습니다.")

    with transaction.atomic():
        BambooReport.objects.get_or_create(
            user=request.user,
            story=story,
            defaults={"reason": str(request.POST.get("reason") or "").strip()[:120]},
        )
        BambooStory.objects.filter(pk=story.pk).update(is_hidden_by_report=True, is_public=False)
    story.refresh_from_db()
    story.was_reported_now = True
    if request.headers.get("HX-Request") == "true" and request.POST.get("source") == "post":
        return _private(render(request, "bamboo/partials/story_actions.html", {"story": story}))
    if request.headers.get("HX-Request") != "true":
        messages.success(request, "신고 접수됨")
        return redirect("bamboo:feed")
    return _private(render(request, "bamboo/partials/story_card.html", {"story": story}))


@login_required
@require_POST
def delete_story(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if story.author_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("삭제 권한이 없습니다.")
    story.delete()
    if request.headers.get("HX-Request") == "true":
        return _private(HttpResponse(""))
    messages.success(request, "삭제됨")
    return redirect("bamboo:feed")


@login_required
@require_POST
def create_comment(request, story_uuid):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    form = BambooCommentForm(request.POST)
    if form.is_valid():
        safety = sanitize_comment_body(form.cleaned_data["body"])
        if safety.is_valid:
            BambooComment.objects.create(
                story=story,
                author=request.user,
                anon_handle=_comment_anon_handle(story, request.user),
                body_masked=safety.sanitized.masked_text,
            )
            _sync_comment_count(story)
            form = BambooCommentForm()
        else:
            form.add_error("body", comment_error_message(safety))

    if request.headers.get("HX-Request") == "true":
        status = 200 if not form.errors else 400
        return _render_comments(request, story, form=form, status=status)
    if form.errors:
        messages.error(request, _first_form_error(form))
    return redirect("bamboo:post", story_uuid=story.uuid)


@login_required
@require_POST
def delete_comment(request, story_uuid, comment_id):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    comment = get_object_or_404(BambooComment, pk=comment_id, story=story)
    if comment.author_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("삭제 권한이 없습니다.")
    comment.delete()
    _sync_comment_count(story)
    if request.headers.get("HX-Request") == "true":
        return _render_comments(request, story)
    messages.success(request, "삭제됨")
    return redirect("bamboo:post", story_uuid=story.uuid)


@login_required
@require_POST
def report_comment(request, story_uuid, comment_id):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    comment = get_object_or_404(BambooComment, pk=comment_id, story=story)
    if comment.author_id == request.user.id:
        return HttpResponseForbidden("본인 댓글은 신고할 수 없습니다.")

    with transaction.atomic():
        BambooCommentReport.objects.get_or_create(
            user=request.user,
            comment=comment,
            defaults={"reason": str(request.POST.get("reason") or "").strip()[:120]},
        )
        BambooComment.objects.filter(pk=comment.pk).update(is_hidden_by_report=True)
    _sync_comment_count(story)

    if request.headers.get("HX-Request") == "true":
        return _render_comments(request, story)
    messages.success(request, "신고 접수됨")
    return redirect("bamboo:post", story_uuid=story.uuid)


@ratelimit(key="user", rate="10/h", method="POST", block=False, group="bamboo_generate")
def _handle_write_post(request, *, has_consent: bool):
    form = BambooStoryForm(request.POST)
    if getattr(request, "limited", False):
        return _render_write_result(request, {"error_message": LIMIT_MESSAGE}, status=429)
    if not form.is_valid():
        return _render_write_result(request, {"form": form, "error_message": _first_form_error(form)}, status=400)
    if not has_consent and not form.cleaned_data.get("consent_accepted"):
        form.add_error("consent_accepted", "약속이 필요합니다.")
        return _render_write_result(request, {"form": form, "error_message": "약속이 필요합니다."}, status=400)

    if _is_usage_limit_exceeded(request.user):
        return _render_write_result(request, {"error_message": LIMIT_MESSAGE}, status=429)

    raw_text = form.cleaned_data["raw_text"]
    sanitized = sanitize_input(raw_text)

    try:
        title, fable_output = _generate_validated_fable(sanitized)
    except BambooLlmError:
        return _render_write_result(request, {"error_message": "잠시 후 다시 시도해주세요."}, status=503)
    except ValueError:
        return _render_write_result(request, {"error_message": SAFETY_FALLBACK_MESSAGE}, status=422)

    if _charge_usage_limit(request.user):
        return _render_write_result(request, {"error_message": LIMIT_MESSAGE}, status=429)

    if not has_consent:
        BambooConsent.objects.get_or_create(user=request.user)

    story = BambooStory.objects.create(
        author=request.user,
        anon_handle=_new_anon_handle(),
        title=title,
        input_masked=sanitized.masked_text,
        fable_output=fable_output,
    )

    if request.headers.get("HX-Request") == "true":
        _mark_liked([story], request.user)
        return _private(
            render(
                request,
                "bamboo/partials/result.html",
                {
                    "story": story,
                    "usage": _usage_context(request.user),
                    "result_url": reverse("bamboo:result", kwargs={"story_uuid": story.uuid}),
                },
            )
        )
    return redirect("bamboo:result", story_uuid=story.uuid)


def _generate_validated_fable(sanitized):
    retry_instruction = ""
    last_reasons = ()
    for attempt in range(2):
        output = generate_bamboo_fable(sanitized.masked_text, retry_instruction=retry_instruction)
        result = validate_fable_output(
            output,
            raw_input=sanitized.raw_text,
            masked_input=sanitized.masked_text,
            redacted_values=sanitized.redacted_values,
        )
        if result.is_valid:
            return extract_fable_title(output), output
        last_reasons = result.reasons
        retry_instruction = (
            "이전 출력에 식별 가능 정보 또는 금지 표현이 있었습니다. "
            "실제 사람·학교·지역·날짜·숫자를 모두 버리고 더 추상적인 동물 우화로 다시 쓰세요."
        )
    raise ValueError(",".join(last_reasons))


def _get_story_for_user(story_uuid, user):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if story.is_public and not story.is_hidden_by_report:
        return story
    if story.author_id == user.id or user.is_staff:
        return story
    raise Http404


def _count_view_once(request, story):
    if not story.is_public or story.is_hidden_by_report or story.author_id == request.user.id:
        return
    key = f"bamboo_viewed:{story.uuid}"
    if request.session.get(key):
        return
    BambooStory.objects.filter(pk=story.pk).update(view_count=F("view_count") + 1)
    request.session[key] = True
    story.refresh_from_db(fields=["view_count"])


def _comments_context(story):
    return {
        "comments": BambooComment.objects.visible().filter(story=story).select_related("author").order_by("created_at"),
    }


def _render_comments(request, story, *, form=None, status=200):
    story.refresh_from_db(fields=["comment_count"])
    context = {
        "story": story,
        "comment_form": form or BambooCommentForm(),
    }
    context.update(_comments_context(story))
    return _private(render(request, "bamboo/partials/comments.html", context, status=status))


def _sync_comment_count(story):
    count = BambooComment.objects.visible().filter(story=story).count()
    BambooStory.objects.filter(pk=story.pk).update(comment_count=count)
    story.comment_count = count


def _comment_anon_handle(story, user):
    if story.author_id == user.id:
        return story.anon_handle
    existing = (
        BambooComment.objects.filter(story=story, author=user)
        .order_by("created_at")
        .values_list("anon_handle", flat=True)
        .first()
    )
    return existing or _new_anon_handle()


def _mark_liked(stories, user):
    story_ids = [story.id for story in stories]
    liked_ids = set(
        BambooLike.objects.filter(user=user, story_id__in=story_ids).values_list("story_id", flat=True)
    )
    for story in stories:
        story.user_has_liked = story.id in liked_ids


def _new_anon_handle():
    return f"나무{secrets.randbelow(900) + 100}"


def _safe_bamboo_next(value):
    value = str(value or "")
    if value.startswith("/bamboo/") or value == "/bamboo/":
        return value
    return ""


def _subject(user):
    return user_usage_subject(user)


def _usage_context(user):
    limits = _normalized_usage_limits()
    counts = _usage_counts(user)
    hourly_limit = dict(limits).get(3600, 2)
    daily_limit = dict(limits).get(86400, 5)
    return {
        "hourly_limit": hourly_limit,
        "daily_limit": daily_limit,
        "hourly_remaining": max(hourly_limit - counts.get(3600, 0), 0),
        "daily_remaining": max(daily_limit - counts.get(86400, 0), 0),
    }


def _normalized_usage_limits():
    return _normalize_limits(BAMBOO_USAGE_LIMITS)


def _usage_counts(user):
    now = timezone.now()
    counts = {}
    for window_seconds, _max_count in _normalized_usage_limits():
        cache_key = _cache_key(
            bucket=BAMBOO_USAGE_BUCKET,
            subject=_subject(user),
            window_seconds=window_seconds,
            now=now,
        )
        counts[window_seconds] = _current_count(cache_key)
    return counts


def _is_usage_limit_exceeded(user):
    counts = _usage_counts(user)
    for window_seconds, max_count in _normalized_usage_limits():
        if counts.get(window_seconds, 0) >= max_count:
            return True
    return False


def _charge_usage_limit(user):
    return consume_ai_usage_limit(BAMBOO_USAGE_BUCKET, _subject(user), BAMBOO_USAGE_LIMITS)


def _render_write_result(request, context, *, status=200):
    payload = {
        "form": context.get("form"),
        "error_message": context.get("error_message", ""),
        "usage": _usage_context(request.user),
    }
    if request.headers.get("HX-Request") == "true":
        response = render(request, "bamboo/partials/result.html", payload, status=status)
        if status >= 400:
            response["HX-Bamboo-Error"] = "true"
        return _private(response)

    page_context = {
        "service": _service(),
        "form": payload["form"] or BambooStoryForm(request.POST),
        "has_consent": BambooConsent.objects.filter(user=request.user).exists(),
        "usage": payload["usage"],
        "error_message": payload["error_message"],
    }
    return _private(render(request, "bamboo/write.html", page_context, status=status))


def _first_form_error(form):
    for errors in form.errors.values():
        if errors:
            return errors[0]
    return "입력을 확인해주세요."


def _sns_context(request):
    try:
        from core.views import (
            _attach_teacher_buddy_avatar_context_safe,
            _build_pinned_notice_queryset,
            _build_post_feed_queryset,
            _build_teacher_buddy_avatar_context_safe,
        )

        feed_scope = "all"
        sns_posts = _build_post_feed_queryset(feed_scope=feed_scope)
        sns_page = Paginator(sns_posts, 5).get_page(1)
        pinned_notice_posts = _build_pinned_notice_queryset(feed_scope=feed_scope)
        _attach_teacher_buddy_avatar_context_safe(sns_page.object_list, user=request.user, label="bamboo sns")
        _attach_teacher_buddy_avatar_context_safe(pinned_notice_posts, user=request.user, label="bamboo sns pinned")
        return {
            "posts": sns_page,
            "sns_page_obj": sns_page,
            "pinned_notice_posts": pinned_notice_posts,
            "feed_scope": feed_scope,
            "compact_posts": True,
            "surface_variant": "home_rail",
            "post_list_target_id": "post-list-container",
            "teacher_buddy_current_avatar": _build_teacher_buddy_avatar_context_safe(
                request.user,
                source="bamboo sns",
            ),
            "sns_compose_prefill": "",
        }
    except Exception:
        return {"posts": [], "feed_scope": "all", "compact_posts": True}


def _private(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
