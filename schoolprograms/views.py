from __future__ import annotations

from datetime import timedelta
import mimetypes
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, Count, F, IntegerField, Prefetch, Q, Value, When
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from core.seo import (
    build_organization_structured_data,
    build_public_article_page_seo,
    build_public_collection_page_seo,
    build_public_service_landing_seo,
)
from products.models import Product

from .forms import (
    InquiryCreateForm,
    InquiryMessageForm,
    InquiryProposalForm,
    InquiryReviewForm,
    ProgramListingForm,
    ProviderProfileForm,
)
from .models import (
    InquiryMessage,
    InquiryProposal,
    InquiryReview,
    InquiryThread,
    ListingAttachment,
    ListingImage,
    ListingViewLog,
    ProgramListing,
    ProviderProfile,
    SavedListing,
)
from .regions import region_suggestions_for


COMPARE_SESSION_KEY = "schoolprograms_compare_listing_ids"
MAX_COMPARE_LISTINGS = 3
SERVICE_TITLE = "학교 체험·행사 찾기"
LEGACY_SERVICE_TITLES = ("학교 프로그램 찾기",)


def _get_service():
    service = Product.objects.filter(launch_route_name="schoolprograms:landing").first()
    if service:
        return service
    return Product.objects.filter(title__in=(SERVICE_TITLE, *LEGACY_SERVICE_TITLES)).first()


def _role_for_user(user) -> str:
    profile = getattr(user, "userprofile", None)
    return str(getattr(profile, "role", "") or "").strip()


def _is_teacher_role(user) -> bool:
    return _role_for_user(user) in {"school", "instructor"}


def _is_company_role(user) -> bool:
    return _role_for_user(user) == "company"


def _user_display_name(user) -> str:
    profile = getattr(user, "userprofile", None)
    nickname = str(getattr(profile, "nickname", "") or "").strip()
    full_name = str(getattr(user, "get_full_name", lambda: "")() or "").strip()
    return nickname or full_name or user.username


def _render_schoolprograms(request, template_name, context, *, noindex=False, status=200):
    payload = {
        "service": _get_service(),
        "category_choices": ProgramListing.Category.choices,
        "province_choices": ProgramListing.PROVINCE_CHOICES,
        "grade_band_choices": ProgramListing.GRADE_BAND_CHOICES,
        "delivery_mode_choices": ProgramListing.DeliveryMode.choices,
    }
    payload.update(context)
    if noindex:
        payload.setdefault("robots", "noindex,nofollow")
    if payload.get("page_title"):
        payload.setdefault("og_title", payload["page_title"])
    if payload.get("meta_description"):
        payload.setdefault("og_description", payload["meta_description"])
    if payload.get("canonical_url"):
        payload.setdefault("og_url", payload["canonical_url"])
    robots_value = str(payload.get("robots") or "").strip()
    response = render(request, template_name, payload, status=status)
    if noindex or robots_value.startswith("noindex"):
        response["X-Robots-Tag"] = (robots_value or "noindex,nofollow").replace(",", ", ")
    return response


def _listing_primary_image_url(listing) -> str:
    primary_image = getattr(listing, "primary_image", None)
    image_field = getattr(primary_image, "image", None)
    try:
        return image_field.url if image_field else ""
    except Exception:
        return ""


def _ensure_company_or_403(user):
    if not getattr(user, "is_authenticated", False) or not _is_company_role(user):
        return HttpResponseForbidden("업체 계정만 접근할 수 있습니다.")
    return None


def _ensure_teacher_or_403(user):
    if not getattr(user, "is_authenticated", False) or not _is_teacher_role(user):
        return HttpResponseForbidden("교사 계정만 접근할 수 있습니다.")
    return None


def _get_or_create_provider(user):
    provider, _ = ProviderProfile.objects.get_or_create(
        user=user,
        defaults={
            "provider_name": _user_display_name(user),
            "summary": "학교와 연결될 프로그램 소개를 정리해 주세요.",
            "contact_email": user.email or "",
        },
    )
    return provider


def _listing_base_queryset():
    return (
        ProgramListing.objects.select_related("provider", "provider__user", "provider__user__userprofile")
        .prefetch_related("images", "attachments")
    )


def _inquiry_base_queryset():
    return (
        InquiryThread.objects.select_related(
            "listing",
            "provider",
            "provider__user",
            "provider__user__userprofile",
            "teacher",
            "teacher__userprofile",
        )
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=InquiryMessage.objects.select_related("sender", "sender__userprofile"),
            )
        )
    )


def _teacher_threads_with_bucket(user):
    threads = list(
        _inquiry_base_queryset()
        .filter(teacher=user)
        .select_related("proposal")
        .order_by("-last_message_at", "-updated_at")
    )
    for thread in threads:
        thread.bucket = thread.teacher_bucket
    return threads


def _vendor_threads_with_bucket(provider):
    threads = list(
        _inquiry_base_queryset()
        .filter(provider=provider)
        .select_related("proposal")
        .order_by("-last_message_at", "-updated_at")
    )
    for thread in threads:
        thread.bucket = thread.vendor_bucket
    return threads


def _filter_threads_by_tab(threads, tab):
    if tab == "all":
        return threads
    return [thread for thread in threads if getattr(thread, "bucket", "") == tab]


def _rank_listing_queryset(queryset):
    recent_cutoff = timezone.now() - timedelta(days=14)
    return queryset.annotate(
        recent_interest=Count("view_logs", filter=Q(view_logs__viewed_at__gte=recent_cutoff))
    ).order_by("-is_featured", "-recent_interest", "-view_count", "-published_at", "-id")


def _published_review_meta_for_provider_ids(provider_ids):
    if not provider_ids:
        return {}

    review_meta = {}
    reviews = (
        InquiryReview.objects.select_related("listing", "thread")
        .filter(
            provider_id__in=provider_ids,
            status=InquiryReview.Status.PUBLISHED,
        )
        .order_by("provider_id", "-published_at", "-created_at", "-id")
    )
    for review in reviews:
        info = review_meta.setdefault(
            review.provider_id,
            {
                "count": 0,
                "headline": "",
                "context_label": "",
            },
        )
        info["count"] += 1
        if not info["headline"]:
            info["headline"] = review.headline
            info["context_label"] = review.public_context_label
    return review_meta


def _build_provider_cards(listings, *, review_meta=None):
    review_meta = review_meta or {}
    cards_by_provider = {}

    for listing in listings:
        provider = listing.provider
        card = cards_by_provider.get(provider.pk)
        if card is None:
            card = {
                "provider": provider,
                "representative_listing": listing,
                "listings": [],
                "category_labels": [],
                "region_labels": [],
            }
            cards_by_provider[provider.pk] = card

        card["listings"].append(listing)

        category_label = listing.get_category_display()
        if category_label not in card["category_labels"]:
            card["category_labels"].append(category_label)

        region_label = listing.public_regions_text
        if region_label and region_label not in card["region_labels"]:
            card["region_labels"].append(region_label)

    cards = list(cards_by_provider.values())
    for card in cards:
        representative_listing = card["representative_listing"]
        review_info = review_meta.get(card["provider"].pk, {})
        card["listing_count"] = len(card["listings"])
        card["category_labels"] = card["category_labels"][:2]
        card["region_labels"] = card["region_labels"][:2]
        card["headline_listing_title"] = representative_listing.title
        card["summary"] = card["provider"].summary or representative_listing.summary
        card["service_area_text"] = (
            card["provider"].service_area_summary
            or " · ".join(card["region_labels"])
            or representative_listing.public_regions_text
        )
        card["price_hint"] = representative_listing.price_text
        card["attachment_count"] = len(list(representative_listing.attachments.all()))
        card["review_count"] = int(review_info.get("count") or 0)
        card["review_headline"] = str(review_info.get("headline") or "").strip()
        card["review_context_label"] = str(review_info.get("context_label") or "").strip()
        if card["review_count"]:
            card["trust_badge"] = f"이용후기 {card['review_count']}개"
            card["trust_summary"] = card["review_headline"]
            card["trust_context"] = card["review_context_label"] or "합의 완료 후 공개된 후기"
        else:
            card["trust_badge"] = "운영 승인"
            card["trust_summary"] = f"공개 활동 {card['listing_count']}개"
            card["trust_context"] = "학교 검색에 공개된 업체"

    return cards


def _normalize_attachment_removals(raw_ids):
    cleaned_ids = []
    for raw_value in raw_ids or []:
        try:
            attachment_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if attachment_id not in cleaned_ids:
            cleaned_ids.append(attachment_id)
    return cleaned_ids


def _apply_listing_filters(
    queryset,
    *,
    q="",
    province="",
    region_text="",
    category="",
    grade_band="",
    delivery_mode="",
):
    if province:
        queryset = queryset.filter(province=province)
    if region_text:
        queryset = queryset.filter(
            Q(city__icontains=region_text)
            | Q(coverage_note__icontains=region_text)
            | Q(provider__service_area_summary__icontains=region_text)
        )
    if category:
        queryset = queryset.filter(category=category)
    if grade_band:
        queryset = queryset.filter(grade_bands_text__icontains=grade_band)
    if delivery_mode:
        queryset = queryset.filter(delivery_mode=delivery_mode)
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(summary__icontains=q)
            | Q(description__icontains=q)
            | Q(provider__provider_name__icontains=q)
            | Q(city__icontains=q)
            | Q(coverage_note__icontains=q)
            | Q(provider__service_area_summary__icontains=q)
            | Q(theme_tags_text__icontains=q)
        )
    return queryset


def _choice_label(choices, value):
    for candidate, label in choices:
        if candidate == value:
            return label
    return value


def _teacher_saved_listings_queryset(user):
    return (
        _listing_base_queryset()
        .filter(
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
            saved_by_users__user=user,
        )
        .distinct()
        .order_by("-saved_by_users__created_at", "-id")
    )


def _get_compare_listing_ids(request):
    raw_ids = request.session.get(COMPARE_SESSION_KEY, [])
    if not isinstance(raw_ids, list):
        return []

    cleaned_ids = []
    for raw_value in raw_ids:
        try:
            listing_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if listing_id not in cleaned_ids:
            cleaned_ids.append(listing_id)
    return cleaned_ids[:MAX_COMPARE_LISTINGS]


def _set_compare_listing_ids(request, listing_ids):
    cleaned_ids = []
    for raw_value in listing_ids:
        try:
            listing_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if listing_id not in cleaned_ids:
            cleaned_ids.append(listing_id)
    request.session[COMPARE_SESSION_KEY] = cleaned_ids[:MAX_COMPARE_LISTINGS]
    request.session.modified = True


def _compare_count_for_request(request):
    if not request.user.is_authenticated or not _is_teacher_role(request.user):
        return 0
    return len(_get_compare_listing_ids(request))


def _teacher_compare_listings_queryset(request):
    compare_ids = _get_compare_listing_ids(request)
    if not compare_ids:
        return _listing_base_queryset().none()

    order_case = Case(
        *[When(pk=listing_id, then=Value(index)) for index, listing_id in enumerate(compare_ids)],
        output_field=IntegerField(),
    )
    return (
        _listing_base_queryset()
        .filter(
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
            pk__in=compare_ids,
        )
        .annotate(compare_order=order_case)
        .order_by("compare_order")
    )


def _compare_inquiry_form_prefix(listing):
    return f"compare-{listing.pk}"


def _build_compare_inquiry_entries(compare_listings, *, bound_form=None, open_slug=""):
    bound_prefix = str(getattr(bound_form, "prefix", "") or "")
    entries = []
    for listing in compare_listings:
        prefix = _compare_inquiry_form_prefix(listing)
        form = bound_form if bound_prefix == prefix else InquiryCreateForm(prefix=prefix)
        entries.append(
            {
                "listing": listing,
                "form": form,
                "is_open": bool(listing.slug == open_slug or bound_prefix == prefix),
            }
        )
    return entries


def _pick_listing_by_slug(listings, slug):
    selected_slug = str(slug or "").strip()
    if not listings:
        return None
    if selected_slug:
        for listing in listings:
            if listing.slug == selected_slug:
                return listing
    return listings[0]


def _create_inquiry_thread(*, listing, teacher, form):
    thread = InquiryThread.objects.create(
        listing=listing,
        provider=listing.provider,
        teacher=teacher,
        category=listing.category,
        school_region=form.cleaned_data["school_region"],
        preferred_schedule=form.cleaned_data["preferred_schedule"],
        target_audience=form.cleaned_data["target_audience"],
        expected_participants=form.cleaned_data["expected_participants"],
        budget_text=form.cleaned_data["budget_text"],
        status=InquiryThread.Status.AWAITING_VENDOR,
    )
    InquiryMessage.objects.create(
        thread=thread,
        sender=teacher,
        sender_role=InquiryThread.SenderRole.TEACHER,
        body=form.cleaned_data["request_message"],
    )
    return thread


def _build_listing_review_status(listing):
    if listing.approval_status == ProgramListing.ApprovalStatus.REJECTED:
        return {
            "title": "수정 후 다시 심사 요청이 필요합니다",
            "description": "운영 피드백을 반영한 뒤 다시 심사 요청을 보내면 재검토가 시작됩니다.",
            "next_step": "반려 사유를 확인하고 내용을 보완하세요.",
            "pill_class": "bg-rose-100 text-rose-700",
            "panel_class": "border-rose-200 bg-rose-50 text-rose-900",
            "time_label": "마지막 수정",
            "time_value": listing.updated_at,
        }
    if listing.approval_status == ProgramListing.ApprovalStatus.PENDING:
        return {
            "title": "심사 대기 중입니다",
            "description": "승인 전까지 교사 검색에는 노출되지 않으며, 운영 검토가 끝나면 공개로 전환됩니다.",
            "next_step": "추가 수정이 있으면 저장 후 다시 확인하세요.",
            "pill_class": "bg-amber-100 text-amber-700",
            "panel_class": "border-amber-200 bg-amber-50 text-amber-900",
            "time_label": "심사 요청",
            "time_value": listing.submitted_at,
        }
    if listing.approval_status == ProgramListing.ApprovalStatus.APPROVED:
        return {
            "title": "교사가 검색할 수 있는 공개 상태입니다",
            "description": "현재 공개 검색과 상세 페이지에서 바로 문의를 받을 수 있습니다.",
            "next_step": "가격, 안전 정보, 방문 가능 지역을 최신 상태로 유지하세요.",
            "pill_class": "bg-emerald-100 text-emerald-700",
            "panel_class": "border-emerald-200 bg-emerald-50 text-emerald-900",
            "time_label": "공개 시작",
            "time_value": listing.published_at,
        }
    return {
        "title": "아직 심사 요청 전입니다",
        "description": "임시 저장 상태라 교사 검색에는 보이지 않습니다. 내용이 갖춰지면 심사 요청을 보내세요.",
        "next_step": "대표 소개, 대상, 지역, 안전 정보를 먼저 채워 주세요.",
        "pill_class": "bg-slate-100 text-slate-700",
        "panel_class": "border-slate-200 bg-slate-50 text-slate-900",
        "time_label": "현재 상태",
        "time_value": None,
    }


def landing(request):
    if request.user.is_authenticated and _is_company_role(request.user):
        return redirect("schoolprograms:vendor_dashboard")

    service = _get_service()
    listings = _listing_base_queryset().filter(
        approval_status=ProgramListing.ApprovalStatus.APPROVED,
    )
    q = str(request.GET.get("q") or "").strip()
    province = str(request.GET.get("province") or "").strip()
    region_text = str(request.GET.get("region_text") or "").strip()
    category = str(request.GET.get("category") or "").strip()
    grade_band = str(request.GET.get("grade_band") or "").strip()
    delivery_mode = str(request.GET.get("delivery_mode") or "").strip()

    listings = _apply_listing_filters(
        listings,
        q=q,
        province=province,
        region_text=region_text,
        category=category,
        grade_band=grade_band,
        delivery_mode=delivery_mode,
    )
    ranked_listings = list(_rank_listing_queryset(listings))
    review_meta = _published_review_meta_for_provider_ids({listing.provider_id for listing in ranked_listings})
    provider_cards = _build_provider_cards(ranked_listings, review_meta=review_meta)
    page_obj = Paginator(provider_cards, 12).get_page(request.GET.get("page"))
    has_active_filters = bool(q or province or region_text or category or grade_band or delivery_mode)
    has_advanced_filters = bool(region_text or grade_band or delivery_mode or q)
    active_filter_labels = []
    if category:
        active_filter_labels.append(_choice_label(ProgramListing.Category.choices, category))
    if province:
        active_filter_labels.append(_choice_label(ProgramListing.PROVINCE_CHOICES, province))
    if region_text:
        active_filter_labels.append(region_text)
    if grade_band:
        active_filter_labels.append(_choice_label(ProgramListing.GRADE_BAND_CHOICES, grade_band))
    if delivery_mode:
        active_filter_labels.append(_choice_label(ProgramListing.DeliveryMode.choices, delivery_mode))
    if q:
        active_filter_labels.append(f"주제 {q}")
    robots = "noindex,follow" if has_active_filters or page_obj.number > 1 else "index,follow"

    return _render_schoolprograms(
        request,
        "schoolprograms/landing.html",
        {
            **build_public_service_landing_seo(
                request,
                product=service,
                title=f"{SERVICE_TITLE} | Eduitit",
                description="지역과 주제로 학교로 찾아오는 체험학습, 교사연수, 학교행사를 바로 비교하고 문의하세요.",
                route_name="schoolprograms:landing",
                landing_name=SERVICE_TITLE,
                robots=robots,
            ).as_context(),
            "page_obj": page_obj,
            "provider_count": len(provider_cards),
            "has_active_filters": has_active_filters,
            "has_advanced_filters": has_advanced_filters,
            "active_filter_labels": active_filter_labels,
            "region_suggestions": region_suggestions_for(province),
            "q": q,
            "selected_province": province,
            "selected_region_text": region_text,
            "selected_category": category,
            "selected_grade_band": grade_band,
            "selected_delivery_mode": delivery_mode,
            "can_use_saved_listings": request.user.is_authenticated and _is_teacher_role(request.user),
            "saved_count": (
                SavedListing.objects.filter(user=request.user).count()
                if request.user.is_authenticated and _is_teacher_role(request.user)
                else 0
            ),
            "compare_count": _compare_count_for_request(request),
        },
    )


def listing_detail(request, slug):
    listing = get_object_or_404(
        _listing_base_queryset().filter(approval_status=ProgramListing.ApprovalStatus.APPROVED),
        slug=slug,
    )
    ProgramListing.objects.filter(pk=listing.pk).update(view_count=F("view_count") + 1)
    viewer_key = ""
    if request.user.is_authenticated:
        viewer_key = f"user:{request.user.pk}"
    else:
        if not request.session.session_key:
            request.session.create()
        viewer_key = f"session:{request.session.session_key}"
    ListingViewLog.objects.create(listing=listing, viewer_key=viewer_key)
    listing.refresh_from_db(fields=["view_count"])

    inquiry_form = None
    is_saved = False
    is_compared = False
    if request.user.is_authenticated and _is_teacher_role(request.user):
        inquiry_form = InquiryCreateForm()
        is_saved = SavedListing.objects.filter(user=request.user, listing=listing).exists()
        is_compared = listing.pk in _get_compare_listing_ids(request)

    related_listings = (
        _listing_base_queryset()
        .filter(
            provider=listing.provider,
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        )
        .exclude(pk=listing.pk)[:3]
    )
    seo = build_public_article_page_seo(
        request,
        title=f"{listing.title} | {SERVICE_TITLE}",
        description=listing.summary,
        route_name="schoolprograms:listing_detail",
        route_kwargs={"slug": listing.slug},
        article_name=listing.title,
        breadcrumb_items=(
            ("홈", reverse("home")),
            (SERVICE_TITLE, reverse("schoolprograms:landing")),
            (listing.title, reverse("schoolprograms:listing_detail", args=[listing.slug])),
        ),
        og_image=_listing_primary_image_url(listing),
        date_published=listing.published_at or listing.created_at,
        date_modified=listing.updated_at,
        article_section=listing.get_category_display(),
        about_name=listing.provider.provider_name,
        keywords=listing.theme_tags,
        same_as=listing.provider.website,
    )

    return _render_schoolprograms(
        request,
        "schoolprograms/listing_detail.html",
        {
            **seo.as_context(),
            "listing": listing,
            "related_listings": related_listings,
            "inquiry_form": inquiry_form,
            "is_saved": is_saved,
            "is_compared": is_compared,
            "compare_count": _compare_count_for_request(request),
        },
    )


def download_listing_attachment(request, slug, attachment_id):
    listing = get_object_or_404(_listing_base_queryset(), slug=slug)
    is_vendor_owner = (
        request.user.is_authenticated
        and _is_company_role(request.user)
        and listing.provider.user_id == request.user.id
    )
    if listing.approval_status != ProgramListing.ApprovalStatus.APPROVED and not is_vendor_owner:
        raise Http404("첨부 파일을 찾을 수 없습니다.")
    attachment = get_object_or_404(listing.attachments.all(), pk=attachment_id)
    try:
        file_handle = attachment.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("첨부 파일을 찾을 수 없습니다.") from exc

    filename = attachment.display_name
    content_type = attachment.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    response = FileResponse(file_handle, as_attachment=True, filename=filename, content_type=content_type)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@login_required
def create_inquiry(request, slug):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    listing = get_object_or_404(
        _listing_base_queryset().filter(approval_status=ProgramListing.ApprovalStatus.APPROVED),
        slug=slug,
    )
    if request.method != "POST":
        return redirect("schoolprograms:listing_detail", slug=listing.slug)

    form = InquiryCreateForm(request.POST)
    if form.is_valid():
        thread = _create_inquiry_thread(listing=listing, teacher=request.user, form=form)
        messages.success(request, "문의가 접수되었습니다. 업체 답변이 오면 여기서 이어서 확인할 수 있습니다.")
        return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

    related_listings = (
        _listing_base_queryset()
        .filter(provider=listing.provider, approval_status=ProgramListing.ApprovalStatus.APPROVED)
        .exclude(pk=listing.pk)[:3]
    )
    seo = build_public_article_page_seo(
        request,
        title=f"{listing.title} | {SERVICE_TITLE}",
        description=listing.summary,
        route_name="schoolprograms:listing_detail",
        route_kwargs={"slug": listing.slug},
        article_name=listing.title,
        breadcrumb_items=(
            ("홈", reverse("home")),
            (SERVICE_TITLE, reverse("schoolprograms:landing")),
            (listing.title, reverse("schoolprograms:listing_detail", args=[listing.slug])),
        ),
        og_image=_listing_primary_image_url(listing),
        date_published=listing.published_at or listing.created_at,
        date_modified=listing.updated_at,
        article_section=listing.get_category_display(),
        about_name=listing.provider.provider_name,
        keywords=listing.theme_tags,
        same_as=listing.provider.website,
    )
    return _render_schoolprograms(
        request,
        "schoolprograms/listing_detail.html",
        {
            **seo.as_context(),
            "listing": listing,
            "related_listings": related_listings,
            "inquiry_form": form,
        },
        status=400,
    )


def provider_detail(request, slug):
    provider = get_object_or_404(
        ProviderProfile.objects.select_related("user", "user__userprofile"),
        slug=slug,
    )
    listings = list(
        _listing_base_queryset().filter(
            provider=provider,
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
        )
    )
    if not listings:
        raise Http404("공개된 프로그램이 없습니다.")

    published_reviews_queryset = (
        InquiryReview.objects.select_related("listing", "thread")
        .filter(provider=provider, status=InquiryReview.Status.PUBLISHED)
        .order_by("-published_at", "-created_at", "-id")
    )
    published_review_count = published_reviews_queryset.count()
    published_reviews = list(published_reviews_queryset[:4])

    selected_listing = _pick_listing_by_slug(
        listings,
        request.POST.get("listing_slug") if request.method == "POST" else request.GET.get("activity"),
    )
    inquiry_form = None

    if request.method == "POST":
        if not request.user.is_authenticated:
            next_url = f"{reverse('schoolprograms:provider_detail', args=[provider.slug])}?activity={selected_listing.slug}"
            login_url = f"{reverse('account_login')}?next={quote(next_url)}"
            return redirect(login_url)
        denied = _ensure_teacher_or_403(request.user)
        if denied:
            return denied
        inquiry_form = InquiryCreateForm(request.POST)
        if inquiry_form.is_valid():
            thread = _create_inquiry_thread(listing=selected_listing, teacher=request.user, form=inquiry_form)
            messages.success(request, "업체 상세에서 바로 문의를 보냈습니다. 답변은 문의함에서 이어집니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
    elif request.user.is_authenticated and _is_teacher_role(request.user):
        inquiry_form = InquiryCreateForm()

    provider_inquiry_next_url = f"{reverse('schoolprograms:provider_detail', args=[provider.slug])}?activity={selected_listing.slug}"
    provider_inquiry_login_url = f"{reverse('account_login')}?next={quote(provider_inquiry_next_url)}"
    seo = build_public_collection_page_seo(
        request,
        title=f"{provider.provider_name} | {SERVICE_TITLE}",
        description=provider.summary or provider.description[:120],
        route_name="schoolprograms:provider_detail",
        route_kwargs={"slug": provider.slug},
        collection_name=provider.provider_name,
        breadcrumb_items=(
            ("홈", reverse("home")),
            (SERVICE_TITLE, reverse("schoolprograms:landing")),
            (provider.provider_name, reverse("schoolprograms:provider_detail", args=[provider.slug])),
        ),
        additional_structured_data=(
            build_organization_structured_data(
                name=provider.provider_name,
                url=reverse("schoolprograms:provider_detail", args=[provider.slug]),
                description=provider.summary or provider.description[:120],
                email=provider.contact_email,
                telephone=provider.contact_phone,
                same_as=provider.website,
            ),
        ),
    )

    return _render_schoolprograms(
        request,
        "schoolprograms/provider_detail.html",
        {
            **seo.as_context(),
            "provider": provider,
            "listings": listings,
            "selected_listing": selected_listing,
            "inquiry_form": inquiry_form,
            "provider_inquiry_login_url": provider_inquiry_login_url,
            "published_reviews": published_reviews,
            "published_review_count": published_review_count,
        },
        status=400 if request.method == "POST" and inquiry_form is not None and inquiry_form.errors else 200,
    )


@login_required
def toggle_saved_listing(request, slug):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    listing = get_object_or_404(
        _listing_base_queryset().filter(approval_status=ProgramListing.ApprovalStatus.APPROVED),
        slug=slug,
    )
    next_url = str(request.POST.get("next") or request.GET.get("next") or "").strip()
    if not next_url or not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("schoolprograms:listing_detail", args=[listing.slug])

    saved = SavedListing.objects.filter(user=request.user, listing=listing).first()
    if saved:
        saved.delete()
        messages.success(request, "저장한 프로그램에서 제거했습니다.")
    else:
        SavedListing.objects.create(user=request.user, listing=listing)
        messages.success(request, "나중에 다시 볼 수 있게 저장했습니다.")
    return redirect(next_url)


@login_required
def teacher_saved_listings(request):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    q = str(request.GET.get("q") or "").strip()
    province = str(request.GET.get("province") or "").strip()
    region_text = str(request.GET.get("region_text") or "").strip()
    category = str(request.GET.get("category") or "").strip()
    grade_band = str(request.GET.get("grade_band") or "").strip()
    delivery_mode = str(request.GET.get("delivery_mode") or "").strip()

    saved_listings = list(
        _apply_listing_filters(
            _teacher_saved_listings_queryset(request.user),
            q=q,
            province=province,
            region_text=region_text,
            category=category,
            grade_band=grade_band,
            delivery_mode=delivery_mode,
        )
    )
    compare_listing_ids = _get_compare_listing_ids(request)
    return _render_schoolprograms(
        request,
        "schoolprograms/teacher_saved_listings.html",
        {
            "page_title": f"저장한 프로그램 | {SERVICE_TITLE}",
            "meta_description": "나중에 다시 비교하려고 저장한 학교 프로그램 목록입니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:teacher_saved_listings")),
            "saved_listings": saved_listings,
            "saved_count": SavedListing.objects.filter(user=request.user).count(),
            "compare_count": len(compare_listing_ids),
            "compare_listing_ids": compare_listing_ids,
            "region_suggestions": region_suggestions_for(province),
            "q": q,
            "selected_province": province,
            "selected_region_text": region_text,
            "selected_category": category,
            "selected_grade_band": grade_band,
            "selected_delivery_mode": delivery_mode,
        },
        noindex=True,
    )


@login_required
def toggle_compare_listing(request, slug):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    listing = get_object_or_404(
        _listing_base_queryset().filter(approval_status=ProgramListing.ApprovalStatus.APPROVED),
        slug=slug,
    )
    next_url = str(request.POST.get("next") or request.GET.get("next") or "").strip()
    if not next_url or not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("schoolprograms:teacher_compare_listings")

    compare_ids = _get_compare_listing_ids(request)
    if listing.pk in compare_ids:
        _set_compare_listing_ids(request, [listing_id for listing_id in compare_ids if listing_id != listing.pk])
        messages.success(request, "비교함에서 제거했습니다.")
        return redirect(next_url)

    if len(compare_ids) >= MAX_COMPARE_LISTINGS:
        messages.error(request, f"비교함은 최대 {MAX_COMPARE_LISTINGS}개까지만 담을 수 있습니다.")
        return redirect(next_url)

    compare_ids.append(listing.pk)
    _set_compare_listing_ids(request, compare_ids)
    messages.success(request, "비교함에 담았습니다. 이제 나란히 확인할 수 있습니다.")
    return redirect(next_url)


@login_required
def teacher_compare_listings(request):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    compare_listings = list(_teacher_compare_listings_queryset(request))
    compare_listing_ids = [listing.pk for listing in compare_listings]
    if compare_listing_ids != _get_compare_listing_ids(request):
        _set_compare_listing_ids(request, compare_listing_ids)
    open_slug = str(request.GET.get("open") or "").strip()

    return _render_schoolprograms(
        request,
        "schoolprograms/teacher_compare_listings.html",
        {
            "page_title": f"프로그램 비교함 | {SERVICE_TITLE}",
            "meta_description": "저장하거나 담아둔 프로그램을 한눈에 비교하는 비공개 비교함입니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:teacher_compare_listings")),
            "compare_listings": compare_listings,
            "compare_entries": _build_compare_inquiry_entries(compare_listings, open_slug=open_slug),
            "compare_count": len(compare_listing_ids),
            "compare_limit": MAX_COMPARE_LISTINGS,
            "saved_count": SavedListing.objects.filter(user=request.user).count(),
        },
        noindex=True,
    )


@login_required
def create_compare_inquiry(request, slug):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied
    if request.method != "POST":
        return redirect("schoolprograms:teacher_compare_listings")

    compare_ids = _get_compare_listing_ids(request)
    listing = get_object_or_404(
        _listing_base_queryset().filter(
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
            pk__in=compare_ids,
        ),
        slug=slug,
    )
    form = InquiryCreateForm(request.POST, prefix=_compare_inquiry_form_prefix(listing))
    if form.is_valid():
        thread = _create_inquiry_thread(listing=listing, teacher=request.user, form=form)
        messages.success(request, "비교 중이던 프로그램으로 바로 문의를 보냈습니다.")
        return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

    compare_listings = list(_teacher_compare_listings_queryset(request))
    compare_listing_ids = [item.pk for item in compare_listings]
    return _render_schoolprograms(
        request,
        "schoolprograms/teacher_compare_listings.html",
        {
            "page_title": f"프로그램 비교함 | {SERVICE_TITLE}",
            "meta_description": "저장하거나 담아둔 프로그램을 한눈에 비교하는 비공개 비교함입니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:teacher_compare_listings")),
            "compare_listings": compare_listings,
            "compare_entries": _build_compare_inquiry_entries(compare_listings, bound_form=form),
            "compare_count": len(compare_listing_ids),
            "compare_limit": MAX_COMPARE_LISTINGS,
            "saved_count": SavedListing.objects.filter(user=request.user).count(),
        },
        noindex=True,
        status=400,
    )


@login_required
def teacher_inquiries(request):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    tab = str(request.GET.get("tab") or "new").strip() or "new"
    threads = _teacher_threads_with_bucket(request.user)
    tab_counts = {
        "new": sum(1 for thread in threads if thread.bucket == "new"),
        "progress": sum(1 for thread in threads if thread.bucket == "progress"),
        "proposal": sum(1 for thread in threads if thread.bucket == "proposal"),
        "hold": sum(1 for thread in threads if thread.bucket == "hold"),
        "closed": sum(1 for thread in threads if thread.bucket == "closed"),
    }

    return _render_schoolprograms(
        request,
        "schoolprograms/teacher_inquiries.html",
        {
            "page_title": f"내 문의함 | {SERVICE_TITLE}",
            "meta_description": "보낸 문의와 업체 답변, 제안 카드를 한곳에서 확인합니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:teacher_inquiries")),
            "threads": _filter_threads_by_tab(threads, tab),
            "selected_tab": tab,
            "tab_counts": tab_counts,
        },
        noindex=True,
    )


@login_required
def teacher_inquiry_detail(request, thread_id):
    denied = _ensure_teacher_or_403(request.user)
    if denied:
        return denied

    thread = get_object_or_404(
        _inquiry_base_queryset().select_related("proposal", "review"),
        id=thread_id,
        teacher=request.user,
    )
    review = getattr(thread, "review", None)
    message_form = InquiryMessageForm()
    review_form = InquiryReviewForm(instance=review) if thread.is_agreement_reached and review is None else None
    response_status = 200

    if request.method == "POST":
        action = str(request.POST.get("action") or "message").strip()
        if action == "save_review":
            if not thread.is_agreement_reached:
                messages.error(request, "합의가 완료된 문의에만 이용후기를 남길 수 있습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            if review is not None:
                messages.error(request, "이용후기는 한 번만 남길 수 있습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            review_form = InquiryReviewForm(request.POST)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.thread = thread
                review.listing = thread.listing
                review.provider = thread.provider
                review.teacher = request.user
                review.status = InquiryReview.Status.PENDING
                review.save()
                messages.success(request, "이용후기를 남겼습니다. 운영 검토 후 업체 상세에 공개됩니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            response_status = 400

        if action == "close":
            thread.status = InquiryThread.Status.CLOSED
            thread.is_agreement_reached = False
            thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
            messages.success(request, "문의가 종료되었습니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

        if thread.status == InquiryThread.Status.CLOSED:
            messages.error(request, "종료된 스레드에는 더 이상 메시지를 보낼 수 없습니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

        if action == "accept_proposal":
            if not hasattr(thread, "proposal"):
                messages.error(request, "수락할 제안 카드가 아직 없습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            InquiryMessage.objects.create(
                thread=thread,
                sender=request.user,
                sender_role=InquiryThread.SenderRole.TEACHER,
                body="[합의 완료] 제안 내용을 기준으로 진행하겠습니다. 세부 확정은 후속 연락으로 이어가겠습니다.",
            )
            thread.status = InquiryThread.Status.CLOSED
            thread.is_agreement_reached = True
            thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
            messages.success(request, "제안을 수락하고 합의 완료로 정리했습니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

        if action == "hold_proposal":
            if not hasattr(thread, "proposal"):
                messages.error(request, "보류할 제안 카드가 아직 없습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            InquiryMessage.objects.create(
                thread=thread,
                sender=request.user,
                sender_role=InquiryThread.SenderRole.TEACHER,
                body="[보류] 내부 일정과 예산을 다시 확인한 뒤 이어서 답변드리겠습니다.",
            )
            thread.status = InquiryThread.Status.ON_HOLD
            thread.is_agreement_reached = False
            thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
            messages.success(request, "제안을 보류 상태로 두었습니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

        if action == "request_revision":
            if not hasattr(thread, "proposal"):
                messages.error(request, "재협의를 요청할 제안 카드가 아직 없습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            InquiryMessage.objects.create(
                thread=thread,
                sender=request.user,
                sender_role=InquiryThread.SenderRole.TEACHER,
                body="[재협의 요청] 제안 조건을 조금 더 조율하고 싶습니다. 아래 메시지에서 세부 요청을 이어가겠습니다.",
            )
            thread.status = InquiryThread.Status.IN_PROGRESS
            thread.is_agreement_reached = False
            thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
            messages.success(request, "재협의 상태로 전환했습니다.")
            return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)

        if action == "message":
            message_form = InquiryMessageForm(request.POST)
            if message_form.is_valid():
                InquiryMessage.objects.create(
                    thread=thread,
                    sender=request.user,
                    sender_role=InquiryThread.SenderRole.TEACHER,
                    body=message_form.cleaned_data["body"],
                )
                next_status = InquiryThread.Status.IN_PROGRESS
                if thread.status != InquiryThread.Status.CLOSED:
                    thread.status = next_status
                    thread.is_agreement_reached = False
                    thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
                messages.success(request, "추가 메시지를 보냈습니다.")
                return redirect("schoolprograms:teacher_inquiry_detail", thread_id=thread.id)
            response_status = 400

    return _render_schoolprograms(
        request,
        "schoolprograms/teacher_inquiry_detail.html",
        {
            "page_title": f"{thread.listing.title} 문의 | {SERVICE_TITLE}",
            "meta_description": thread.last_message_preview or thread.listing.summary,
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:teacher_inquiry_detail", args=[thread.id])),
            "thread": thread,
            "message_form": message_form,
            "review": review,
            "review_form": review_form,
        },
        noindex=True,
        status=response_status,
    )


@login_required
def vendor_dashboard(request):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied

    provider = _get_or_create_provider(request.user)
    listings = list(provider.listings.order_by("-updated_at"))
    for listing in listings:
        listing.review_status = _build_listing_review_status(listing)
    recent_threads = _vendor_threads_with_bucket(provider)[:5]
    seven_days_ago = timezone.now() - timedelta(days=7)
    action_required_listings = [
        listing
        for listing in listings
        if listing.approval_status in {ProgramListing.ApprovalStatus.DRAFT, ProgramListing.ApprovalStatus.REJECTED}
    ]
    pending_review_listings = [
        listing for listing in listings if listing.approval_status == ProgramListing.ApprovalStatus.PENDING
    ]

    checklist = {
        "profile_ready": provider.is_profile_ready,
        "has_listing": bool(listings),
        "has_review_ready_listing": provider.listings.filter(
            approval_status__in=[
                ProgramListing.ApprovalStatus.PENDING,
                ProgramListing.ApprovalStatus.APPROVED,
            ]
        ).exists(),
    }

    return _render_schoolprograms(
        request,
        "schoolprograms/vendor/dashboard.html",
        {
            "page_title": f"업체 대시보드 | {SERVICE_TITLE}",
            "meta_description": "업체 정보, 프로그램 등록, 문의 답변, 제안 카드 발송을 한곳에서 관리합니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:vendor_dashboard")),
            "provider": provider,
            "listings": listings,
            "recent_threads": recent_threads,
            "approved_count": provider.listings.filter(approval_status=ProgramListing.ApprovalStatus.APPROVED).count(),
            "pending_count": provider.listings.filter(approval_status=ProgramListing.ApprovalStatus.PENDING).count(),
            "new_inquiry_count": provider.inquiries.filter(status=InquiryThread.Status.AWAITING_VENDOR).count(),
            "view_count_7d": ListingViewLog.objects.filter(
                listing__provider=provider,
                viewed_at__gte=seven_days_ago,
            ).count(),
            "action_required_listings": action_required_listings,
            "pending_review_listings": pending_review_listings,
            "checklist": checklist,
        },
        noindex=True,
    )


@login_required
def vendor_profile_edit(request):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied

    provider = _get_or_create_provider(request.user)
    if request.method == "POST":
        form = ProviderProfileForm(request.POST, request.FILES, instance=provider, service_area_list_id="provider-region-suggestions")
        if form.is_valid():
            form.save()
            messages.success(request, "업체 정보를 저장했습니다.")
            return redirect("schoolprograms:vendor_dashboard")
    else:
        form = ProviderProfileForm(instance=provider, service_area_list_id="provider-region-suggestions")

    return _render_schoolprograms(
        request,
        "schoolprograms/vendor/profile_form.html",
        {
            "page_title": f"업체 정보 수정 | {SERVICE_TITLE}",
            "meta_description": f"{SERVICE_TITLE} 업체 기본 정보를 관리합니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:vendor_profile_edit")),
            "provider": provider,
            "form": form,
            "region_suggestions": region_suggestions_for(""),
        },
        noindex=True,
    )


@login_required
def vendor_listing_create(request):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied
    return _vendor_listing_editor(request)


@login_required
def vendor_listing_edit(request, slug):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied
    provider = _get_or_create_provider(request.user)
    listing = get_object_or_404(provider.listings.prefetch_related("images", "attachments"), slug=slug)
    return _vendor_listing_editor(request, provider=provider, listing=listing)


def _vendor_listing_editor(request, provider=None, listing=None):
    provider = provider or _get_or_create_provider(request.user)
    is_create_mode = listing is None or not getattr(listing, "pk", None)
    selected_province = ""
    if request.method == "POST":
        selected_province = str(request.POST.get("province") or "").strip()
        form = ProgramListingForm(
            request.POST,
            request.FILES,
            instance=listing,
            region_list_id="listing-region-suggestions",
        )
        if form.is_valid():
            existing_status = (
                listing.approval_status if listing is not None else ProgramListing.ApprovalStatus.DRAFT
            )
            listing = form.save(commit=False)
            listing.provider = provider
            action = str(request.POST.get("action") or "save").strip()
            if action == "submit" and not provider.is_profile_ready:
                form.add_error(None, "회사 정보와 증빙 서류를 먼저 완료해 주세요. 그다음 심사 요청을 보낼 수 있습니다.")
            else:
                if action == "submit" and existing_status != ProgramListing.ApprovalStatus.APPROVED:
                    listing.mark_pending_review()
                elif not listing.pk:
                    listing.mark_draft()
                listing.save()
                remove_attachment_ids = _normalize_attachment_removals(request.POST.getlist("remove_attachment_ids"))
                if remove_attachment_ids:
                    listing.attachments.filter(pk__in=remove_attachment_ids).delete()
                for image in request.FILES.getlist("new_images"):
                    ListingImage.objects.create(listing=listing, image=image, sort_order=listing.images.count())
                existing_attachment_count = listing.attachments.count()
                for offset, attachment in enumerate(form.cleaned_data.get("attachments", [])):
                    ListingAttachment.objects.create(
                        listing=listing,
                        file=attachment,
                        original_name=getattr(attachment, "name", "") or "",
                        content_type=str(getattr(attachment, "content_type", "") or ""),
                        file_size=int(getattr(attachment, "size", 0) or 0),
                        sort_order=existing_attachment_count + offset,
                    )
                if existing_status == ProgramListing.ApprovalStatus.APPROVED:
                    messages.success(request, "공개중 프로그램 정보를 저장했습니다. 현재 공개 상태는 유지됩니다.")
                elif action == "submit":
                    messages.success(request, "심사 요청까지 보냈습니다. 승인 전에는 공개 검색에 노출되지 않습니다.")
                else:
                    messages.success(request, "프로그램을 저장했습니다.")
                return redirect("schoolprograms:vendor_listing_edit", slug=listing.slug)
    else:
        selected_province = getattr(listing, "province", "") if listing else ""
        form = ProgramListingForm(instance=listing, region_list_id="listing-region-suggestions")

    return _render_schoolprograms(
        request,
        "schoolprograms/vendor/listing_form.html",
        {
            "page_title": f"프로그램 등록 | {SERVICE_TITLE}" if is_create_mode else f"프로그램 수정 | {SERVICE_TITLE}",
            "meta_description": "학교 프로그램 등록 정보를 작성하고 심사 요청을 보냅니다.",
            "canonical_url": request.build_absolute_uri(
                reverse(
                    "schoolprograms:vendor_listing_create" if is_create_mode else "schoolprograms:vendor_listing_edit",
                    args=[] if is_create_mode else [listing.slug],
                )
            ),
            "provider": provider,
            "listing": listing,
            "review_status": _build_listing_review_status(listing) if listing else None,
            "form": form,
            "region_suggestions": region_suggestions_for(selected_province),
            "profile_ready": provider.is_profile_ready,
        },
        noindex=True,
    )


@login_required
def vendor_inquiries(request):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied

    provider = _get_or_create_provider(request.user)
    tab = str(request.GET.get("tab") or "new").strip() or "new"
    threads = _vendor_threads_with_bucket(provider)
    tab_counts = {
        "new": sum(1 for thread in threads if thread.bucket == "new"),
        "progress": sum(1 for thread in threads if thread.bucket == "progress"),
        "proposal": sum(1 for thread in threads if thread.bucket == "proposal"),
        "hold": sum(1 for thread in threads if thread.bucket == "hold"),
        "closed": sum(1 for thread in threads if thread.bucket == "closed"),
    }

    return _render_schoolprograms(
        request,
        "schoolprograms/vendor/inquiries.html",
        {
            "page_title": f"업체 문의함 | {SERVICE_TITLE}",
            "meta_description": "학교 문의와 제안 카드를 한곳에서 관리합니다.",
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:vendor_inquiries")),
            "provider": provider,
            "threads": _filter_threads_by_tab(threads, tab),
            "selected_tab": tab,
            "tab_counts": tab_counts,
        },
        noindex=True,
    )


@login_required
def vendor_inquiry_detail(request, thread_id):
    denied = _ensure_company_or_403(request.user)
    if denied:
        return denied

    provider = _get_or_create_provider(request.user)
    thread = get_object_or_404(
        _inquiry_base_queryset().select_related("proposal"),
        id=thread_id,
        provider=provider,
    )
    message_form = InquiryMessageForm()
    proposal_form = InquiryProposalForm(instance=getattr(thread, "proposal", None))

    if request.method == "POST":
        action = str(request.POST.get("action") or "message").strip()
        if action == "close":
            thread.status = InquiryThread.Status.CLOSED
            thread.is_agreement_reached = False
            thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
            messages.success(request, "문의 스레드를 종료했습니다.")
            return redirect("schoolprograms:vendor_inquiry_detail", thread_id=thread.id)

        if thread.status == InquiryThread.Status.CLOSED:
            messages.error(request, "종료된 스레드에는 더 이상 답변이나 제안을 보낼 수 없습니다.")
            return redirect("schoolprograms:vendor_inquiry_detail", thread_id=thread.id)

        if action == "proposal":
            proposal_form = InquiryProposalForm(request.POST, instance=getattr(thread, "proposal", None))
            if proposal_form.is_valid():
                proposal = proposal_form.save(commit=False)
                proposal.thread = thread
                proposal.sent_by = request.user
                proposal.save()
                InquiryMessage.objects.create(
                    thread=thread,
                    sender=request.user,
                    sender_role=InquiryThread.SenderRole.VENDOR,
                    body=f"[제안 카드] {proposal.price_text} / {proposal.schedule_note}",
                )
                thread.status = InquiryThread.Status.PROPOSAL_SENT
                thread.is_agreement_reached = False
                thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
                messages.success(request, "제안 카드를 보냈습니다.")
                return redirect("schoolprograms:vendor_inquiry_detail", thread_id=thread.id)
        else:
            message_form = InquiryMessageForm(request.POST)
            if message_form.is_valid():
                InquiryMessage.objects.create(
                    thread=thread,
                    sender=request.user,
                    sender_role=InquiryThread.SenderRole.VENDOR,
                    body=message_form.cleaned_data["body"],
                )
                if thread.status != InquiryThread.Status.CLOSED:
                    thread.status = InquiryThread.Status.IN_PROGRESS
                    thread.is_agreement_reached = False
                    thread.save(update_fields=["status", "is_agreement_reached", "updated_at"])
                messages.success(request, "답변을 보냈습니다.")
                return redirect("schoolprograms:vendor_inquiry_detail", thread_id=thread.id)

    return _render_schoolprograms(
        request,
        "schoolprograms/vendor/inquiry_detail.html",
        {
            "page_title": f"{thread.listing.title} 문의 응답 | {SERVICE_TITLE}",
            "meta_description": thread.last_message_preview or thread.listing.summary,
            "canonical_url": request.build_absolute_uri(reverse("schoolprograms:vendor_inquiry_detail", args=[thread.id])),
            "provider": provider,
            "thread": thread,
            "message_form": message_form,
            "proposal_form": proposal_form,
        },
        noindex=True,
    )
