import hashlib
import logging
import secrets

from django.contrib import messages
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
from .models import BambooComment, BambooCommentReport, BambooLike, BambooReport, BambooStory
from .utils.llm import BambooLlmError, generate_bamboo_fable, review_bamboo_fable_quality
from .utils.quality import validate_fable_quality
from .utils.comments import comment_error_message, sanitize_comment_body
from .utils.sanitizer import sanitize_input
from .utils.validator import extract_fable_title, validate_fable_output

BAMBOO_USAGE_BUCKET = "bamboo:generate"
BAMBOO_MEMBER_USAGE_LIMITS = ((86400, 5),)
BAMBOO_GUEST_USAGE_LIMITS = ((86400, 2),)
BAMBOO_GUEST_SESSION_KEY = "bamboo_guest_key"
LIMIT_MESSAGE = "오늘은 충분히 쏟아내셨어요. 내일 다시 숲을 찾아주세요."
GUEST_LIMIT_MESSAGE = "오늘 비회원 체험을 모두 썼어요."
SAFETY_FALLBACK_MESSAGE = "이번에는 우화로 풀기 어려운 사연이에요. 조금 더 일반적으로 다시 적어주세요."
PROMPT_FLUSH_EVENT = "bambooPromptFlushed"

logger = logging.getLogger(__name__)


def _service():
    return (
        Product.objects.filter(launch_route_name="bamboo:feed", is_active=True).first()
        or Product.objects.filter(title="교사 대나무숲").first()
    )


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
    page_stories = _prepare_stories(page_obj.object_list, request)
    page_obj.object_list = page_stories

    context = {
        "service": _service(),
        "stories": page_stories,
        "page_obj": page_obj,
        "sort": sort,
        "usage": _usage_context(request),
    }
    context.update(_sns_context(request))
    return _private(render(request, "bamboo/feed.html", context))


def write(request):
    if request.method == "POST":
        return _handle_write_post(request)

    context = {
        "service": _service(),
        "form": BambooStoryForm(),
        "usage": _usage_context(request),
    }
    return _private(render(request, "bamboo/write.html", context))


def result(request, story_uuid):
    story = _get_story_for_user(story_uuid, request)
    _prepare_stories([story], request)
    return _private(render(request, "bamboo/result.html", {"service": _service(), "story": story}))


def post(request, story_uuid):
    story = _get_story_for_user(story_uuid, request)
    _count_view_once(request, story)
    _prepare_stories([story], request)
    context = {
        "service": _service(),
        "story": story,
        "comment_form": BambooCommentForm(),
    }
    context.update(_comments_context(story, request))
    return _private(render(request, "bamboo/post.html", context))


@require_POST
def update_visibility(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if not _is_story_owner(story, request):
        return HttpResponseForbidden("공개 설정 권한이 없습니다.")
    if story.is_hidden_by_report:
        messages.warning(request, "신고 검토 중")
        return redirect("bamboo:result", story_uuid=story.uuid)

    story.is_public = str(request.POST.get("is_public") or "").lower() in {"1", "true", "on", "yes"}
    story.save(update_fields=["is_public"])
    messages.success(request, "공개" if story.is_public else "비공개")
    return redirect("bamboo:result", story_uuid=story.uuid)


@require_POST
def like_story(request, story_uuid):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    like = _like_queryset(request, story).first()
    if like:
        like.delete()
    else:
        BambooLike.objects.create(story=story, **_actor_fields(request))
    story.like_count = BambooLike.objects.filter(story=story).count()
    story.save(update_fields=["like_count"])
    _prepare_stories([story], request)
    if request.headers.get("HX-Request") == "true" and request.POST.get("source") == "post":
        return _private(render(request, "bamboo/partials/story_actions.html", {"story": story}))
    if request.headers.get("HX-Request") != "true":
        return redirect(_safe_bamboo_next(request.POST.get("next")) or "bamboo:feed")
    return _private(render(request, "bamboo/partials/story_card.html", {"story": story}))


@require_POST
def report_story(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if _is_story_owner(story, request):
        return HttpResponseForbidden("본인 글은 신고할 수 없습니다.")

    with transaction.atomic():
        report_fields = _actor_fields(request)
        BambooReport.objects.get_or_create(
            story=story,
            defaults={"reason": str(request.POST.get("reason") or "").strip()[:120]},
            **report_fields,
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


@require_POST
def delete_story(request, story_uuid):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if not _is_story_owner(story, request):
        return HttpResponseForbidden("삭제 권한이 없습니다.")
    story.delete()
    if request.headers.get("HX-Request") == "true" and request.POST.get("source") == "result":
        return _private(render(request, "bamboo/partials/result.html", {"success_message": "삭제됨"}))
    if request.headers.get("HX-Request") == "true" and request.POST.get("source") == "post":
        response = HttpResponse("")
        response["HX-Redirect"] = reverse("bamboo:feed")
        return _private(response)
    if request.headers.get("HX-Request") == "true":
        return _private(HttpResponse(""))
    messages.success(request, "삭제됨")
    return redirect("bamboo:feed")


@require_POST
def create_comment(request, story_uuid):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    form = BambooCommentForm(request.POST)
    if form.is_valid():
        safety = sanitize_comment_body(form.cleaned_data["body"])
        if safety.is_valid:
            BambooComment.objects.create(
                story=story,
                anon_handle=_comment_anon_handle(story, request),
                body_masked=safety.sanitized.masked_text,
                **_actor_fields(request, user_field="author", guest_field="author_guest_key"),
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


@require_POST
def delete_comment(request, story_uuid, comment_id):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    comment = get_object_or_404(BambooComment, pk=comment_id, story=story)
    if not _is_comment_owner(comment, request):
        return HttpResponseForbidden("삭제 권한이 없습니다.")
    comment.delete()
    _sync_comment_count(story)
    if request.headers.get("HX-Request") == "true":
        return _render_comments(request, story)
    messages.success(request, "삭제됨")
    return redirect("bamboo:post", story_uuid=story.uuid)


@require_POST
def report_comment(request, story_uuid, comment_id):
    story = get_object_or_404(BambooStory.objects.visible(), uuid=story_uuid)
    comment = get_object_or_404(BambooComment, pk=comment_id, story=story)
    if _is_comment_owner(comment, request):
        return HttpResponseForbidden("본인 댓글은 신고할 수 없습니다.")

    with transaction.atomic():
        report_fields = _actor_fields(request)
        BambooCommentReport.objects.get_or_create(
            comment=comment,
            defaults={"reason": str(request.POST.get("reason") or "").strip()[:120]},
            **report_fields,
        )
        BambooComment.objects.filter(pk=comment.pk).update(is_hidden_by_report=True)
    _sync_comment_count(story)

    if request.headers.get("HX-Request") == "true":
        return _render_comments(request, story)
    messages.success(request, "신고 접수됨")
    return redirect("bamboo:post", story_uuid=story.uuid)


@ratelimit(key="ip", rate="10/h", method="POST", block=False, group="bamboo_generate")
def _handle_write_post(request):
    form = BambooStoryForm(request.POST)
    if getattr(request, "limited", False):
        return _render_write_result(request, _limit_payload(request), status=429)
    if not form.is_valid():
        return _render_write_result(request, {"form": form, "error_message": _first_form_error(form)}, status=400)

    if _is_usage_limit_exceeded(request):
        return _render_write_result(request, _limit_payload(request), status=429)

    raw_text = form.cleaned_data["raw_text"]
    sanitized = sanitize_input(raw_text)

    try:
        title, fable_output = _generate_validated_fable(sanitized)
    except BambooLlmError:
        return _render_write_result(request, {"error_message": "잠시 후 다시 시도해주세요."}, status=503)
    except ValueError as exc:
        logger.warning("[Bamboo] fable generation rejected after retries: %s", exc)
        return _render_write_result(request, {"error_message": SAFETY_FALLBACK_MESSAGE, "flush_prompt": True}, status=200)

    if _charge_usage_limit(request):
        return _render_write_result(request, _limit_payload(request), status=429)

    story = BambooStory.objects.create(
        **_actor_fields(request, user_field="author", guest_field="author_guest_key"),
        anon_handle=_new_anon_handle(),
        title=title,
        input_masked="",
        fable_output=fable_output,
    )

    if request.headers.get("HX-Request") == "true":
        _prepare_stories([story], request)
        response = render(
            request,
            "bamboo/partials/result.html",
            {
                "story": story,
                "usage": _usage_context(request),
                "result_url": reverse("bamboo:result", kwargs={"story_uuid": story.uuid}),
            },
        )
        response["HX-Trigger"] = PROMPT_FLUSH_EVENT
        return _private(response)
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
            local_quality = validate_fable_quality(output)
            if not local_quality.is_valid:
                last_reasons = local_quality.reasons
                retry_instruction = _quality_retry_instruction(last_reasons)
                continue

            llm_quality = review_bamboo_fable_quality(sanitized.masked_text, output)
            if llm_quality.is_valid:
                return extract_fable_title(output), output
            last_reasons = llm_quality.reasons or ("quality_review_failed",)
            retry_instruction = _quality_retry_instruction(last_reasons)
            continue
        last_reasons = result.reasons
        retry_instruction = (
            "이전 출력에 식별 가능 정보 또는 금지 표현이 있었습니다. "
            "사과나 해명 없이 제목부터 시작하고, 실제 사람·학교·지역·날짜·숫자를 모두 버려 "
            "더 추상적인 동물 우화로 다시 쓰세요."
        )
    raise ValueError(",".join(last_reasons))


def _quality_retry_instruction(reasons):
    reason_text = ", ".join(str(reason) for reason in reasons if reason)
    return (
        "이전 우화는 이야기 흐름이나 자연스러움 검토를 통과하지 못했습니다. "
        f"문제: {reason_text}. "
        "사과나 해명 없이 제목부터 시작하고, 한 사건을 중심으로 캐릭터와 인과를 끝까지 유지해 "
        "모순 없는 4~8문장 동물 우화로 다시 쓰세요."
    )


def _get_story_for_user(story_uuid, request):
    story = get_object_or_404(BambooStory, uuid=story_uuid)
    if story.is_public and not story.is_hidden_by_report:
        return story
    if _is_story_owner(story, request):
        return story
    raise Http404


def _count_view_once(request, story):
    if not story.is_public or story.is_hidden_by_report or _is_story_owner(story, request):
        return
    key = f"bamboo_viewed:{story.uuid}"
    if request.session.get(key):
        return
    BambooStory.objects.filter(pk=story.pk).update(view_count=F("view_count") + 1)
    request.session[key] = True
    story.refresh_from_db(fields=["view_count"])


def _comments_context(story, request):
    comments = list(BambooComment.objects.visible().filter(story=story).select_related("author").order_by("created_at"))
    for comment in comments:
        comment.user_can_manage = _is_comment_owner(comment, request)
        comment.user_can_report = not comment.user_can_manage
        comment.is_story_author = _is_comment_from_story_author(comment, story)
    return {"comments": comments}


def _render_comments(request, story, *, form=None, status=200):
    story.refresh_from_db(fields=["comment_count"])
    context = {
        "story": story,
        "comment_form": form or BambooCommentForm(),
    }
    context.update(_comments_context(story, request))
    return _private(render(request, "bamboo/partials/comments.html", context, status=status))


def _sync_comment_count(story):
    count = BambooComment.objects.visible().filter(story=story).count()
    BambooStory.objects.filter(pk=story.pk).update(comment_count=count)
    story.comment_count = count


def _comment_anon_handle(story, request):
    if _is_story_owner(story, request):
        return story.anon_handle
    comments = BambooComment.objects.filter(story=story)
    if _is_authenticated(request):
        comments = comments.filter(author=request.user)
    else:
        comments = comments.filter(author_guest_key=_guest_key(request))
    existing = comments.order_by("created_at").values_list("anon_handle", flat=True).first()
    return existing or _new_anon_handle()


def _prepare_stories(stories, request):
    stories = list(stories)
    _mark_liked(stories, request)
    for story in stories:
        story.user_can_manage = _is_story_owner(story, request)
        story.user_can_report = not story.user_can_manage
    return stories


def _mark_liked(stories, request):
    story_ids = [story.id for story in stories]
    if not story_ids:
        return
    likes = BambooLike.objects.filter(story_id__in=story_ids)
    if _is_authenticated(request):
        likes = likes.filter(user=request.user)
    else:
        likes = likes.filter(guest_key=_guest_key(request))
    liked_ids = set(likes.values_list("story_id", flat=True))
    for story in stories:
        story.user_has_liked = story.id in liked_ids


def _like_queryset(request, story):
    likes = BambooLike.objects.filter(story=story)
    if _is_authenticated(request):
        return likes.filter(user=request.user)
    return likes.filter(guest_key=_guest_key(request))


def _new_anon_handle():
    return f"나무{secrets.randbelow(900) + 100}"


def _safe_bamboo_next(value):
    value = str(value or "")
    if value.startswith("/bamboo/") or value == "/bamboo/":
        return value
    return ""


def _is_authenticated(request):
    return bool(getattr(request.user, "is_authenticated", False))


def _is_staff(request):
    return _is_authenticated(request) and bool(getattr(request.user, "is_staff", False))


def _guest_key(request):
    raw_key = request.session.get(BAMBOO_GUEST_SESSION_KEY)
    if not raw_key:
        raw_key = secrets.token_urlsafe(32)
        request.session[BAMBOO_GUEST_SESSION_KEY] = raw_key
        request.session.modified = True
    return hashlib.sha256(str(raw_key).encode("utf-8")).hexdigest()


def _actor_fields(request, *, user_field="user", guest_field="guest_key"):
    if _is_authenticated(request):
        return {user_field: request.user}
    return {guest_field: _guest_key(request)}


def _is_story_owner(story, request):
    if _is_staff(request):
        return True
    if _is_authenticated(request):
        return story.author_id == request.user.id
    guest_key = getattr(story, "author_guest_key", "")
    return bool(guest_key and guest_key == _guest_key(request))


def _is_comment_owner(comment, request):
    if _is_staff(request):
        return True
    if _is_authenticated(request):
        return comment.author_id == request.user.id
    guest_key = getattr(comment, "author_guest_key", "")
    return bool(guest_key and guest_key == _guest_key(request))


def _is_comment_from_story_author(comment, story):
    if story.author_id and comment.author_id:
        return story.author_id == comment.author_id
    if story.author_guest_key and comment.author_guest_key:
        return story.author_guest_key == comment.author_guest_key
    return False


def _limit_payload(request):
    if _is_authenticated(request):
        return {"error_message": LIMIT_MESSAGE}
    return {
        "error_message": GUEST_LIMIT_MESSAGE,
        "show_guest_signup_modal": True,
    }


def _subject(request):
    if _is_authenticated(request):
        return user_usage_subject(request.user)
    return f"guest:{_guest_key(request)}"


def _usage_context(request):
    limits = _normalized_usage_limits(request)
    counts = _usage_counts(request)
    daily_limit = dict(limits).get(86400, 0)
    daily_remaining = max(daily_limit - counts.get(86400, 0), 0)
    return {
        "daily_limit": daily_limit,
        "daily_remaining": daily_remaining,
        "is_available": daily_remaining > 0,
        "is_guest": not _is_authenticated(request),
    }


def _normalized_usage_limits(request):
    return _normalize_limits(BAMBOO_MEMBER_USAGE_LIMITS if _is_authenticated(request) else BAMBOO_GUEST_USAGE_LIMITS)


def _usage_counts(request):
    now = timezone.now()
    counts = {}
    for window_seconds, _max_count in _normalized_usage_limits(request):
        cache_key = _cache_key(
            bucket=BAMBOO_USAGE_BUCKET,
            subject=_subject(request),
            window_seconds=window_seconds,
            now=now,
        )
        counts[window_seconds] = _current_count(cache_key)
    return counts


def _is_usage_limit_exceeded(request):
    counts = _usage_counts(request)
    for window_seconds, max_count in _normalized_usage_limits(request):
        if counts.get(window_seconds, 0) >= max_count:
            return True
    return False


def _charge_usage_limit(request):
    return consume_ai_usage_limit(BAMBOO_USAGE_BUCKET, _subject(request), _normalized_usage_limits(request))


def _render_write_result(request, context, *, status=200):
    payload = {
        "form": context.get("form"),
        "error_message": context.get("error_message", ""),
        "usage": _usage_context(request),
        "show_guest_signup_modal": bool(context.get("show_guest_signup_modal")),
        "flush_prompt": bool(context.get("flush_prompt", True)),
    }
    if request.headers.get("HX-Request") == "true":
        response = render(request, "bamboo/partials/result.html", payload, status=status)
        if status >= 400:
            response["HX-Bamboo-Error"] = "true"
        if payload["flush_prompt"]:
            response["HX-Trigger"] = PROMPT_FLUSH_EVENT
        return _private(response)

    page_context = {
        "service": _service(),
        "form": BambooStoryForm(),
        "usage": payload["usage"],
        "error_message": payload["error_message"],
        "show_guest_signup_modal": payload["show_guest_signup_modal"],
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
