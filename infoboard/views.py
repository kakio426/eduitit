import csv
import json
import logging
from collections import Counter
from urllib.parse import urlencode, urlsplit

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse
from django.views.decorators.http import require_POST

from products.models import Product
from .forms import (
    BOARD_SHARE_CHOICES,
    BOARD_TEMPLATE_PRESETS,
    BoardForm,
    BoardJoinForm,
    CardCommentForm,
    CardForm,
    CollectionForm,
    ReactionForm,
    ShareLinkForm,
    StudentCardForm,
)
from .models import Board, Card, CardComment, CardReaction, Collection, SharedLink, Tag


logger = logging.getLogger(__name__)

SERVICE_ROUTE = "infoboard:dashboard"
SERVICE_TITLE = "인포보드"
REACTION_META = {
    "like": {"emoji": "👍", "label": "좋아요"},
    "idea": {"emoji": "💡", "label": "아이디어"},
    "question": {"emoji": "❓", "label": "질문"},
}


def _get_service(request):
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(title=SERVICE_TITLE).first()


def _current_request_url(request):
    htmx = getattr(request, "htmx", None)
    current_url = getattr(htmx, "current_url_abs_path", None) if htmx else None
    return current_url or request.get_full_path()


def _current_request_path(request):
    return urlsplit(_current_request_url(request)).path


def _current_request_query(request):
    return QueryDict(urlsplit(_current_request_url(request)).query, mutable=False)


def _resolve_current_route(request):
    try:
        return resolve(_current_request_path(request))
    except Resolver404:
        return None


def _set_htmx_headers(response, *, retarget=None, reswap=None, trigger_after_swap=None, redirect_to=None):
    if retarget:
        response["HX-Retarget"] = retarget
    if reswap:
        response["HX-Reswap"] = reswap
    if trigger_after_swap:
        if isinstance(trigger_after_swap, str):
            trigger_after_swap = {trigger_after_swap: True}
        response["HX-Trigger-After-Swap"] = json.dumps(trigger_after_swap)
    if redirect_to:
        response["HX-Redirect"] = redirect_to
    return response


def _active_shared_link(board):
    return board.shared_links.filter(is_active=True).order_by("-created_at").first()


def _ensure_guest_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _viewer_is_owner(request, board):
    return request.user.is_authenticated and board.owner_id == request.user.id


def _get_shared_link_or_404(board, link_id):
    shared = get_object_or_404(SharedLink, id=link_id, board=board, is_active=True)
    if shared.is_expired:
        raise Http404
    return shared


def _share_mode_options(current_share="private"):
    options = []
    for value, label in BOARD_SHARE_CHOICES:
        if value == "edit" and current_share != "edit":
            continue
        options.append(
            {
                "value": value,
                "label": label,
                "description": {
                    "private": "교사만 보고 관리합니다.",
                    "view": "학생이 읽기만 할 수 있습니다.",
                    "comment": "댓글과 반응으로 가볍게 참여합니다.",
                    "submit": "학생이 새 카드를 제출합니다.",
                    "edit": "기존 관리 링크를 그대로 유지합니다.",
                }[value],
            }
        )
    return options


def _layout_options(board=None):
    options = [
        {"value": "grid", "label": "격자형", "description": "카드를 한눈에 훑기 좋습니다."},
        {"value": "list", "label": "목록형", "description": "질문이나 제출물을 차례로 보기 좋습니다."},
    ]
    if board and board.layout == "timeline":
        options.append(
            {
                "value": "timeline",
                "label": "타임라인",
                "description": "기존 보드 호환용 레이아웃입니다.",
                "legacy": True,
            }
        )
    return options


def _template_preset_cards():
    return [{"key": key, **config} for key, config in BOARD_TEMPLATE_PRESETS.items()]


def _join_url(request, board):
    query = urlencode({"code": board.access_code})
    return request.build_absolute_uri(f"{reverse('infoboard:join')}?{query}")


def _share_url(request, shared_link):
    return request.build_absolute_uri(reverse("infoboard:public_board", args=[shared_link.id]))


def _sync_share_link(board, user, access_level):
    current_active = _active_shared_link(board)
    active_links = board.shared_links.filter(is_active=True)
    if access_level == "private":
        active_links.update(is_active=False)
        return None

    valid_levels = {choice[0] for choice in SharedLink.ACCESS_CHOICES}
    if access_level not in valid_levels:
        access_level = "view"
    if access_level == "edit" and not (current_active and current_active.access_level == "edit"):
        access_level = "view"

    if current_active and current_active.access_level == access_level and not current_active.is_expired:
        active_links.exclude(id=current_active.id).update(is_active=False)
        return current_active

    active_links.update(is_active=False)
    return SharedLink.objects.create(board=board, created_by=user, access_level=access_level)


def _card_queryset(board, *, status=None, search_q=""):
    queryset = (
        board.cards.select_related("author_user")
        .prefetch_related(
            "tags",
            Prefetch(
                "comments",
                queryset=CardComment.objects.filter(status="published").select_related("author_user").order_by("created_at"),
                to_attr="visible_comments",
            ),
            Prefetch("reactions", queryset=CardReaction.objects.order_by("created_at"), to_attr="all_reactions"),
        )
        .annotate(
            comment_count=Count("comments", filter=Q(comments__status="published"), distinct=True),
            pending_comments_count=Count("comments", filter=Q(comments__status="pending"), distinct=True),
        )
    )
    if status:
        queryset = queryset.filter(status=status)
    if search_q:
        queryset = queryset.filter(
            Q(title__icontains=search_q) | Q(content__icontains=search_q) | Q(tags__name__icontains=search_q)
        ).distinct()
    return queryset


def _selected_reaction(request, reactions):
    if request.user.is_authenticated:
        for reaction in reactions:
            if reaction.user_id == request.user.id:
                return reaction.reaction_type
        return ""
    session_key = request.session.session_key
    if not session_key:
        return ""
    for reaction in reactions:
        if reaction.guest_key == session_key:
            return reaction.reaction_type
    return ""


def _comment_form_for_card(request, *, require_author, data=None):
    initial = {}
    if require_author:
        initial["author_name"] = request.session.get("infoboard_guest_name", "")
    if data is not None:
        return CardCommentForm(data=data, require_author=require_author)
    return CardCommentForm(initial=initial, require_author=require_author)


def _prepare_cards_for_display(
    request,
    cards,
    *,
    shared=None,
    viewer_is_owner=False,
    invalid_comment_card_id=None,
    invalid_comment_form=None,
    notice_by_card_id=None,
):
    prepared = []
    can_comment = viewer_is_owner or bool(shared and shared.can_comment)
    require_author = can_comment and not request.user.is_authenticated and not viewer_is_owner

    for card in cards:
        reactions = list(getattr(card, "all_reactions", []))
        counts = Counter(reaction.reaction_type for reaction in reactions)
        selected = _selected_reaction(request, reactions)
        card.total_reactions = sum(counts.values())
        card.reaction_options = [
            {
                "value": value,
                "emoji": meta["emoji"],
                "label": meta["label"],
                "count": counts.get(value, 0),
                "selected": selected == value,
            }
            for value, meta in REACTION_META.items()
        ]
        card.visible_comments = list(getattr(card, "visible_comments", []))
        card.viewer_is_owner = viewer_is_owner
        card.shared = shared
        card.can_comment = can_comment
        card.can_react = can_comment
        card.comment_notice = ""
        if notice_by_card_id:
            card.comment_notice = notice_by_card_id.get(str(card.id), "")
        if invalid_comment_card_id and str(card.id) == str(invalid_comment_card_id):
            card.comment_form = invalid_comment_form
        else:
            card.comment_form = _comment_form_for_card(request, require_author=require_author)
        prepared.append(card)
    return prepared


def _board_summary_context(board):
    card_counts = board.cards.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status="published")),
        pending=Count("id", filter=Q(status="pending")),
        hidden=Count("id", filter=Q(status="hidden")),
    )
    comment_counts = CardComment.objects.filter(card__board=board).aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status="published")),
        pending=Count("id", filter=Q(status="pending")),
    )
    reaction_total = CardReaction.objects.filter(card__board=board).count()
    top_tags = (
        Tag.objects.filter(cards__board=board)
        .annotate(card_refs=Count("cards", filter=Q(cards__board=board), distinct=True))
        .order_by("-card_refs", "name")[:5]
    )
    recent_activity = []
    for card in board.cards.exclude(status="hidden").order_by("-created_at")[:4]:
        recent_activity.append(
            {
                "kind": "card",
                "title": card.title,
                "actor": card.display_author,
                "timestamp": card.created_at,
                "status": card.get_status_display(),
            }
        )
    for comment in CardComment.objects.filter(card__board=board).exclude(status="hidden").select_related("card").order_by("-created_at")[:4]:
        recent_activity.append(
            {
                "kind": "comment",
                "title": comment.card.title,
                "actor": comment.display_author,
                "timestamp": comment.created_at,
                "status": comment.get_status_display(),
            }
        )
    recent_activity.sort(key=lambda item: item["timestamp"], reverse=True)
    return {
        "card_counts": card_counts,
        "comment_counts": comment_counts,
        "reaction_total": reaction_total,
        "top_tags": top_tags,
        "recent_activity": recent_activity[:6],
    }


def _moderation_queue_context(board):
    pending_cards = board.cards.filter(status="pending").select_related("author_user").prefetch_related("tags").order_by("-created_at")
    pending_comments = CardComment.objects.filter(card__board=board, status="pending").select_related("card", "author_user").order_by("-created_at")
    return {
        "pending_cards": pending_cards,
        "pending_comments": pending_comments,
        "pending_total": pending_cards.count() + pending_comments.count(),
    }


def _board_cards_context(board, *, request=None, shared=None, viewer_is_owner=False, search_q="", comment_context=None):
    cards = list(_card_queryset(board, status="published", search_q=search_q))
    cards = _prepare_cards_for_display(
        request,
        cards,
        shared=shared,
        viewer_is_owner=viewer_is_owner,
        invalid_comment_card_id=(comment_context or {}).get("card_id"),
        invalid_comment_form=(comment_context or {}).get("form"),
        notice_by_card_id=(comment_context or {}).get("notice_by_card_id"),
    )
    return {
        "board": board,
        "cards": cards,
        "search_q": search_q,
        "card_count": len(cards),
        "viewer_is_owner": viewer_is_owner,
        "shared": shared,
    }


def _board_detail_context(request, board, search_q="", comment_context=None):
    shared_link = _active_shared_link(board)
    board_tags = Tag.objects.filter(Q(boards=board) | Q(cards__board=board)).distinct().order_by("name")
    cards_context = _board_cards_context(
        board,
        request=request,
        viewer_is_owner=True,
        search_q=search_q,
        comment_context=comment_context,
    )
    return {
        "board": board,
        "shared_link": shared_link,
        "board_tags": board_tags,
        "search_q": search_q,
        "current_path": request.get_full_path(),
        "layout_options": _layout_options(board),
        "board_join_url": _join_url(request, board),
        "share_mode_options": _share_mode_options(shared_link.access_level if shared_link else "private"),
        "summary": _board_summary_context(board),
        "moderation": _moderation_queue_context(board),
        **cards_context,
    }


def _dashboard_context(owner, query):
    search_q = query.get("q", "").strip()
    tag_filter = query.get("tag", "").strip()
    boards = (
        Board.objects.filter(owner=owner)
        .annotate(
            num_cards=Count("cards", filter=Q(cards__status="published"), distinct=True),
            pending_cards=Count("cards", filter=Q(cards__status="pending"), distinct=True),
            comment_count=Count("cards__comments", filter=Q(cards__comments__status="published"), distinct=True),
        )
        .prefetch_related("tags", "shared_links")
        .order_by("-updated_at")
    )
    if search_q:
        boards = boards.filter(Q(title__icontains=search_q) | Q(description__icontains=search_q))
    if tag_filter:
        boards = boards.filter(tags__name=tag_filter)
    boards = list(boards)
    for board in boards:
        board.active_shared_link = next((link for link in board.shared_links.all() if link.is_active), None)
    return {
        "boards": boards,
        "user_tags": Tag.objects.filter(owner=owner).order_by("name"),
        "search_q": search_q,
        "current_tag": tag_filter,
        "collection_count": Collection.objects.filter(owner=owner).count(),
        "board_total": len(boards),
        "pending_total": sum(board.pending_cards for board in boards),
        "board_delete_target": "ibBoardGrid",
    }


def _collection_boards_context(collection):
    boards = collection.boards.annotate(num_cards=Count("cards", filter=Q(cards__status="published"))).order_by("-updated_at")
    return {
        "collection": collection,
        "boards": boards,
        "board_count": boards.count(),
        "board_delete_target": "ibCollectionBoards",
    }


def _render_board_grid_response(request, *, close_modal=False):
    context = _dashboard_context(request.user, _current_request_query(request))
    response = render(request, "infoboard/partials/board_grid.html", context)
    return _set_htmx_headers(
        response,
        retarget="#ibBoardGrid",
        reswap="innerHTML",
        trigger_after_swap="infoboard:close-modal" if close_modal else None,
    )


def _render_collection_grid_response(request, *, close_modal=False):
    collections = Collection.objects.filter(owner=request.user).annotate(board_count=Count("boards")).order_by("-updated_at")
    response = render(request, "infoboard/partials/collection_grid.html", {"collections": collections})
    return _set_htmx_headers(
        response,
        retarget="#ibCollectionGrid",
        reswap="innerHTML",
        trigger_after_swap="infoboard:close-modal" if close_modal else None,
    )


def _render_board_detail_fragment_response(request, board, *, main_panel="cards", close_modal=False, comment_context=None):
    search_q = _current_request_query(request).get("q", "").strip()
    context = _board_detail_context(request, board, search_q=search_q, comment_context=comment_context)
    context["main_panel"] = main_panel
    response = render(request, "infoboard/partials/board_refresh.html", context)
    return _set_htmx_headers(
        response,
        retarget="#ibCardGrid" if main_panel == "cards" else "#ibModerationQueue",
        reswap="innerHTML",
        trigger_after_swap="infoboard:close-modal" if close_modal else None,
    )


def _render_single_card_response(request, card, *, shared=None, viewer_is_owner=False, comment_context=None):
    cards = _prepare_cards_for_display(
        request,
        [card],
        shared=shared,
        viewer_is_owner=viewer_is_owner,
        invalid_comment_card_id=(comment_context or {}).get("card_id"),
        invalid_comment_form=(comment_context or {}).get("form"),
        notice_by_card_id=(comment_context or {}).get("notice_by_card_id"),
    )
    return render(
        request,
        "infoboard/partials/card_item.html",
        {"card": cards[0], "board": card.board, "viewer_is_owner": viewer_is_owner, "shared": shared},
    )


def _refresh_link_card_metadata(card, previous_url=None):
    if card.card_type != "link" or not card.url:
        return
    url_changed = previous_url is not None and card.url != previous_url
    has_existing_meta = any([card.og_title, card.og_description, card.og_image, card.og_site_name])
    if not url_changed and has_existing_meta:
        return
    if url_changed:
        card.og_title = ""
        card.og_description = ""
        card.og_image = ""
        card.og_site_name = ""
        card.save(update_fields=["og_title", "og_description", "og_image", "og_site_name"])

    from .utils import fetch_url_meta

    meta = fetch_url_meta(card.url)
    if not meta:
        return
    changed_fields = []
    for key, value in meta.items():
        if getattr(card, key) != value:
            setattr(card, key, value)
            changed_fields.append(key)
    if changed_fields:
        card.save(update_fields=changed_fields)


@login_required
def dashboard(request):
    service = _get_service(request)
    context = {"service": service}
    context.update(_dashboard_context(request.user, request.GET))
    if request.htmx:
        return render(request, "infoboard/partials/board_grid.html", context)
    return render(request, "infoboard/dashboard.html", context)


@login_required
def board_create(request):
    default_preset = BOARD_TEMPLATE_PRESETS["question"]
    if request.method == "POST":
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            _sync_share_link(board, request.user, form.cleaned_data["share_mode"])
            logger.info("[InfoBoard] Board created: %s (id=%s)", board.title, board.id)
            if request.htmx:
                return _render_board_grid_response(request, close_modal=True)
            return redirect("infoboard:board_detail", board_id=board.id)
    else:
        form = BoardForm(
            initial={
                "template_preset": "question",
                "icon": default_preset["icon"],
                "color_theme": default_preset["color_theme"],
                "layout": default_preset["layout"],
                "moderation_mode": default_preset["moderation_mode"],
                "share_mode": default_preset["share_mode"],
                "allow_student_submit": default_preset["allow_student_submit"],
                "is_public": default_preset["is_public"],
            }
        )

    context = {
        "form": form,
        "user_tags": Tag.objects.filter(owner=request.user).order_by("name"),
        "is_edit": False,
        "modal_mode": bool(request.htmx),
        "template_presets": _template_preset_cards(),
        "layout_options": _layout_options(),
        "share_mode_options": _share_mode_options(form["share_mode"].value() or "private"),
    }
    if request.htmx:
        return render(request, "infoboard/partials/board_form_modal.html", context)
    return render(request, "infoboard/board_form.html", context)


@login_required
def board_detail(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    service = _get_service(request)
    search_q = request.GET.get("q", "").strip()
    context = {"service": service, "modal_mode": False}
    context.update(_board_detail_context(request, board, search_q=search_q))
    if request.htmx:
        return render(request, "infoboard/partials/card_grid.html", context)
    return render(request, "infoboard/board_detail.html", context)


@login_required
@require_POST
def board_layout(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    layout = request.POST.get("layout", "").strip()
    valid_layouts = {"grid", "list"}
    if board.layout == "timeline":
        valid_layouts.add("timeline")
    if layout in valid_layouts and layout != board.layout:
        board.layout = layout
        board.save(update_fields=["layout", "updated_at"])
    next_url = request.POST.get("next", "").strip() or reverse("infoboard:board_detail", args=[board.id])
    if request.htmx:
        return _set_htmx_headers(HttpResponse(status=204), redirect_to=next_url)
    return redirect(next_url)


@login_required
def board_edit(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    current_route = _resolve_current_route(request)
    current_share = _active_shared_link(board)
    if request.method == "POST":
        form = BoardForm(request.POST, instance=board)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            _sync_share_link(board, request.user, form.cleaned_data["share_mode"])
            logger.info("[InfoBoard] Board updated: %s (id=%s)", board.title, board.id)
            if request.htmx:
                if current_route and current_route.url_name == "dashboard":
                    return _render_board_grid_response(request, close_modal=True)
                if current_route and current_route.url_name == "board_detail":
                    return _set_htmx_headers(HttpResponse(status=204), redirect_to=_current_request_url(request))
                return _set_htmx_headers(HttpResponse(status=204), redirect_to=reverse("infoboard:board_detail", args=[board.id]))
            return redirect("infoboard:board_detail", board_id=board.id)
    else:
        form = BoardForm(
            instance=board,
            initial={
                "tag_names": ",".join(board.tags.values_list("name", flat=True)),
                "share_mode": current_share.access_level if current_share else "private",
                "template_preset": "question",
            },
        )

    context = {
        "form": form,
        "board": board,
        "user_tags": Tag.objects.filter(owner=request.user).order_by("name"),
        "is_edit": True,
        "modal_mode": bool(request.htmx),
        "template_presets": _template_preset_cards(),
        "layout_options": _layout_options(board),
        "share_mode_options": _share_mode_options(form["share_mode"].value() or "private"),
        "active_shared_link": current_share,
    }
    if request.htmx:
        return render(request, "infoboard/partials/board_form_modal.html", context)
    return render(request, "infoboard/board_form.html", context)


@login_required
@require_POST
def board_delete(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    current_route = _resolve_current_route(request)
    collection = None
    if current_route and current_route.url_name == "collection_detail":
        collection_id = current_route.kwargs.get("collection_id")
        if collection_id:
            collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    title = board.title
    board.delete()
    logger.info("[InfoBoard] Board deleted: %s", title)
    if request.htmx:
        if current_route and current_route.url_name == "collection_detail" and collection is not None:
            return render(request, "infoboard/partials/collection_boards.html", _collection_boards_context(collection))
        if current_route and current_route.url_name == "board_detail":
            return _set_htmx_headers(HttpResponse(status=204), redirect_to=reverse("infoboard:dashboard"))
        return _render_board_grid_response(request)
    return redirect("infoboard:dashboard")


@login_required
def card_add(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    if request.method == "POST":
        form = CardForm(request.POST, request.FILES)
        if form.is_valid():
            card = form.save_with_tags(board, author_user=request.user, status="published")
            _refresh_link_card_metadata(card)
            logger.info("[InfoBoard] Card added: %s to %s", card.title, board.title)
            if request.htmx:
                return _render_board_detail_fragment_response(request, board, main_panel="cards", close_modal=True)
            return redirect("infoboard:board_detail", board_id=board.id)
    else:
        form = CardForm(initial={"card_type": request.GET.get("type", "text")})

    context = {
        "form": form,
        "board": board,
        "user_tags": Tag.objects.filter(owner=request.user).order_by("name"),
        "is_edit": False,
        "modal_mode": bool(request.htmx),
    }
    if request.htmx:
        return render(request, "infoboard/partials/card_form_modal.html", context)
    return render(request, "infoboard/card_form.html", context)


@login_required
def card_edit(request, card_id):
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    previous_url = card.url
    if request.method == "POST":
        form = CardForm(request.POST, request.FILES, instance=card)
        if form.is_valid():
            card = form.save_with_tags(board, author_user=request.user, status=card.status)
            _refresh_link_card_metadata(card, previous_url=previous_url)
            logger.info("[InfoBoard] Card updated: %s", card.title)
            if request.htmx:
                return _render_board_detail_fragment_response(request, board, main_panel="cards", close_modal=True)
            return redirect("infoboard:board_detail", board_id=board.id)
    else:
        form = CardForm(instance=card, initial={"tag_names": ",".join(card.tags.values_list("name", flat=True))})

    context = {
        "form": form,
        "board": board,
        "card": card,
        "user_tags": Tag.objects.filter(owner=request.user).order_by("name"),
        "is_edit": True,
        "modal_mode": bool(request.htmx),
    }
    if request.htmx:
        return render(request, "infoboard/partials/card_form_modal.html", context)
    return render(request, "infoboard/card_form.html", context)


@login_required
@require_POST
def card_delete(request, card_id):
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    card.delete()
    if request.htmx:
        return _render_board_detail_fragment_response(request, board, main_panel="cards")
    return redirect("infoboard:board_detail", board_id=board.id)


@login_required
@require_POST
def card_toggle_pin(request, card_id):
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    card.is_pinned = not card.is_pinned
    card.save(update_fields=["is_pinned", "updated_at"])
    if request.htmx:
        return _render_board_detail_fragment_response(request, board, main_panel="cards")
    return redirect("infoboard:board_detail", board_id=board.id)


def _shared_context_or_404(request, card):
    viewer_is_owner = _viewer_is_owner(request, card.board)
    if viewer_is_owner:
        return viewer_is_owner, None

    link_id = request.POST.get("link_id", "").strip() or request.GET.get("link_id", "").strip()
    if not link_id:
        raise Http404
    shared = _get_shared_link_or_404(card.board, link_id)
    return viewer_is_owner, shared


@require_POST
def card_comment(request, card_id):
    card = get_object_or_404(Card, id=card_id)
    viewer_is_owner, shared = _shared_context_or_404(request, card)
    if not viewer_is_owner and not shared.can_comment:
        raise Http404

    require_author = not request.user.is_authenticated and not viewer_is_owner
    form = CardCommentForm(request.POST, require_author=require_author)
    if not form.is_valid():
        response = _render_single_card_response(
            request,
            card,
            shared=shared,
            viewer_is_owner=viewer_is_owner,
            comment_context={"card_id": card.id, "form": form},
        )
        if request.htmx:
            response["HX-Retarget"] = f"#card-{card.id}"
            response["HX-Reswap"] = "outerHTML"
        return response

    author_name = ""
    author_user = request.user if request.user.is_authenticated else None
    if require_author:
        author_name = form.cleaned_data["author_name"]
        request.session["infoboard_guest_name"] = author_name
    status = "published" if viewer_is_owner or card.board.moderation_mode == "instant" else "pending"
    CardComment.objects.create(
        card=card,
        author_user=author_user,
        author_name=author_name,
        shared_link=shared,
        content=form.cleaned_data["content"],
        status=status,
    )
    notice = "댓글이 승인 대기열에 들어갔어요." if status == "pending" else "댓글이 남겨졌어요."
    response = _render_single_card_response(
        request,
        get_object_or_404(Card, id=card.id),
        shared=shared,
        viewer_is_owner=viewer_is_owner,
        comment_context={"notice_by_card_id": {str(card.id): notice}},
    )
    if request.htmx:
        response["HX-Retarget"] = f"#card-{card.id}"
        response["HX-Reswap"] = "outerHTML"
    return response


@require_POST
def card_reaction(request, card_id):
    card = get_object_or_404(Card, id=card_id)
    viewer_is_owner, shared = _shared_context_or_404(request, card)
    if not viewer_is_owner and not shared.can_comment:
        raise Http404

    form = ReactionForm(request.POST)
    if not form.is_valid():
        raise Http404

    defaults = {"reaction_type": form.cleaned_data["reaction_type"], "shared_link": shared}
    if request.user.is_authenticated:
        CardReaction.objects.update_or_create(card=card, user=request.user, defaults=defaults)
    else:
        guest_key = _ensure_guest_session_key(request)
        CardReaction.objects.update_or_create(card=card, guest_key=guest_key, defaults=defaults)

    response = _render_single_card_response(
        request,
        get_object_or_404(Card, id=card.id),
        shared=shared,
        viewer_is_owner=viewer_is_owner,
    )
    if request.htmx:
        response["HX-Retarget"] = f"#card-{card.id}"
        response["HX-Reswap"] = "outerHTML"
    return response


@login_required
@require_POST
def card_moderate(request, card_id):
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    action = request.POST.get("action", "").strip()
    if action == "publish":
        card.status = "published"
    elif action == "hide":
        card.status = "hidden"
    else:
        raise Http404
    card.save(update_fields=["status", "updated_at"])
    if request.htmx:
        return _render_board_detail_fragment_response(request, card.board, main_panel="queue")
    return redirect("infoboard:board_detail", board_id=card.board.id)


@login_required
@require_POST
def comment_moderate(request, comment_id):
    comment = get_object_or_404(CardComment, id=comment_id, card__board__owner=request.user)
    action = request.POST.get("action", "").strip()
    if action == "publish":
        comment.status = "published"
    elif action == "hide":
        comment.status = "hidden"
    else:
        raise Http404
    comment.save(update_fields=["status", "updated_at"])
    if request.htmx:
        return _render_board_detail_fragment_response(request, comment.card.board, main_panel="queue")
    return redirect("infoboard:board_detail", board_id=comment.card.board.id)


@login_required
def tags_json(request):
    tags = Tag.objects.filter(owner=request.user).values("id", "name", "color")
    return JsonResponse(list(tags), safe=False)


def public_board(request, link_id):
    shared = get_object_or_404(SharedLink, id=link_id, is_active=True)
    if shared.is_expired:
        return render(request, "infoboard/public_expired.html", {"board_title": shared.board.title})

    shared.access_count += 1
    shared.save(update_fields=["access_count"])

    board = shared.board
    search_q = request.GET.get("q", "").strip()
    cards_context = _board_cards_context(board, request=request, shared=shared, search_q=search_q)
    context = {
        "board": board,
        "shared": shared,
        "search_q": search_q,
        "can_comment": shared.can_comment,
        "can_react": shared.can_comment,
        "can_submit": shared.can_submit,
        "join_code": board.access_code,
        **cards_context,
    }
    return render(request, "infoboard/public_board.html", context)


def student_submit(request, link_id):
    shared = get_object_or_404(SharedLink, id=link_id, is_active=True)
    if shared.is_expired or not shared.can_submit:
        raise Http404

    board = shared.board
    if request.method == "POST":
        form = StudentCardForm(request.POST, request.FILES)
        if form.is_valid():
            status = "published" if board.moderation_mode == "instant" else "pending"
            card = form.save_for_board(board, status=status)
            _refresh_link_card_metadata(card)
            logger.info("[InfoBoard] Student submitted card: %s by %s", card.title, card.author_name)
            if request.htmx:
                return render(request, "infoboard/partials/submit_success.html", {"card": card, "status": status})
            return redirect("infoboard:public_board", link_id=link_id)
    else:
        form = StudentCardForm(initial={"card_type": "text"})

    context = {"form": form, "board": board, "shared": shared}
    if request.htmx:
        return render(request, "infoboard/partials/student_submit_form.html", context)
    return render(request, "infoboard/student_submit.html", context)


def join(request):
    submitted = request.method == "POST" or bool(request.GET.get("code"))
    form = BoardJoinForm(request.POST or request.GET or None)
    if submitted and form.is_valid():
        board = Board.objects.filter(access_code=form.cleaned_data["code"]).first()
        if not board:
            form.add_error("code", "입장 코드를 다시 확인해주세요.")
        else:
            shared = _active_shared_link(board)
            if not shared or shared.is_expired:
                form.add_error("code", "아직 학생 입장이 열려 있지 않아요.")
            else:
                return redirect("infoboard:public_board", link_id=shared.id)
    return render(request, "infoboard/join.html", {"form": form})


@login_required
def share_panel(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    shared_link = _active_shared_link(board)
    context = {
        "board": board,
        "shared_link": shared_link,
        "form": ShareLinkForm(initial={"access_level": shared_link.access_level if shared_link else "view"}),
        "share_url": _share_url(request, shared_link) if shared_link else "",
        "join_url": _join_url(request, board),
        "share_mode_options": _share_mode_options(shared_link.access_level if shared_link else "private"),
    }
    return render(request, "infoboard/partials/share_panel.html", context)


@login_required
@require_POST
def share_create(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    current_active = _active_shared_link(board)
    form = ShareLinkForm(request.POST)
    if form.is_valid():
        access_level = form.cleaned_data["access_level"]
        if access_level == "edit" and not (current_active and current_active.access_level == "edit"):
            access_level = "view"
        shared_link = _sync_share_link(board, request.user, access_level)
        logger.info("[InfoBoard] Share link updated: %s for %s", getattr(shared_link, "id", None), board.title)
    else:
        shared_link = current_active
    context = {
        "board": board,
        "shared_link": shared_link,
        "form": ShareLinkForm(initial={"access_level": shared_link.access_level if shared_link else "view"}),
        "share_url": _share_url(request, shared_link) if shared_link else "",
        "join_url": _join_url(request, board),
        "share_mode_options": _share_mode_options(shared_link.access_level if shared_link else "private"),
    }
    if request.htmx:
        return render(request, "infoboard/partials/share_panel.html", context)
    return redirect("infoboard:board_detail", board_id=board.id)


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    results = {"boards": [], "cards": [], "tags": []}
    if q:
        results["boards"] = (
            Board.objects.filter(owner=request.user)
            .filter(Q(title__icontains=q) | Q(description__icontains=q))
            .annotate(num_cards=Count("cards", filter=Q(cards__status="published")))[:10]
        )
        results["cards"] = (
            Card.objects.filter(board__owner=request.user)
            .filter(Q(title__icontains=q) | Q(content__icontains=q))
            .select_related("board")[:10]
        )
        results["tags"] = (
            Tag.objects.filter(owner=request.user, name__icontains=q)
            .annotate(board_count=Count("boards", distinct=True), card_count=Count("cards", distinct=True))[:10]
        )
    context = {"q": q, **results}
    if request.htmx:
        return render(request, "infoboard/partials/search_results.html", context)
    return render(request, "infoboard/search.html", context)


def card_download(request, card_id):
    card = get_object_or_404(Card, id=card_id)
    link_id = request.GET.get("link_id", "").strip()
    if not _viewer_is_owner(request, card.board):
        if card.board.is_public:
            pass
        elif not link_id:
            raise Http404
        else:
            _get_shared_link_or_404(card.board, link_id)
    if not card.file:
        raise Http404

    filename = card.original_filename or "download"
    response = HttpResponse(card.file.read(), content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def collection_list(request):
    collections = Collection.objects.filter(owner=request.user).annotate(board_count=Count("boards")).order_by("-updated_at")
    context = {"collections": collections}
    if request.htmx:
        return render(request, "infoboard/partials/collection_grid.html", context)
    return render(request, "infoboard/collection_list.html", context)


@login_required
def collection_create(request):
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.owner = request.user
            collection.save()
            board_ids = request.POST.getlist("board_ids")
            if board_ids:
                boards = Board.objects.filter(id__in=board_ids, owner=request.user)
                collection.boards.set(boards)
            logger.info("[InfoBoard] Collection created: %s", collection.title)
            if request.htmx:
                return _render_collection_grid_response(request, close_modal=True)
            return redirect("infoboard:collection_detail", collection_id=collection.id)
    else:
        form = CollectionForm()

    context = {
        "form": form,
        "boards": Board.objects.filter(owner=request.user).order_by("title"),
        "is_edit": False,
        "modal_mode": bool(request.htmx),
    }
    if request.htmx:
        return render(request, "infoboard/partials/collection_form_modal.html", context)
    return render(request, "infoboard/collection_form.html", context)


@login_required
def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    context = _collection_boards_context(collection)
    context["collection"] = collection
    return render(request, "infoboard/collection_detail.html", context)


@login_required
def collection_edit(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    current_route = _resolve_current_route(request)
    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            collection = form.save()
            board_ids = request.POST.getlist("board_ids")
            boards = Board.objects.filter(id__in=board_ids, owner=request.user)
            collection.boards.set(boards)
            logger.info("[InfoBoard] Collection updated: %s", collection.title)
            if request.htmx:
                if current_route and current_route.url_name == "collection_detail":
                    return _set_htmx_headers(HttpResponse(status=204), redirect_to=_current_request_url(request))
                return _render_collection_grid_response(request, close_modal=True)
            return redirect("infoboard:collection_detail", collection_id=collection.id)
    else:
        form = CollectionForm(instance=collection)

    context = {
        "form": form,
        "collection": collection,
        "boards": Board.objects.filter(owner=request.user).order_by("title"),
        "selected_ids": set(str(board.id) for board in collection.boards.all()),
        "is_edit": True,
        "modal_mode": bool(request.htmx),
    }
    if request.htmx:
        return render(request, "infoboard/partials/collection_form_modal.html", context)
    return render(request, "infoboard/collection_form.html", context)


@login_required
@require_POST
def collection_delete(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    current_route = _resolve_current_route(request)
    collection.delete()
    if request.htmx:
        if current_route and current_route.url_name == "collection_detail":
            return _set_htmx_headers(HttpResponse(status=204), redirect_to=reverse("infoboard:collection_list"))
        return _render_collection_grid_response(request)
    return redirect("infoboard:collection_list")


@login_required
@require_POST
def collection_toggle_board(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    board_id = request.POST.get("board_id")
    if board_id:
        board = get_object_or_404(Board, id=board_id, owner=request.user)
        if collection.boards.filter(id=board.id).exists():
            collection.boards.remove(board)
        else:
            collection.boards.add(board)
    context = _collection_boards_context(collection)
    if request.htmx:
        return render(request, "infoboard/partials/collection_boards.html", context)
    return redirect("infoboard:collection_detail", collection_id=collection.id)


@login_required
def fetch_og_meta(request):
    url = request.GET.get("url", "").strip()
    if not url:
        return JsonResponse({"error": "URL이 필요합니다."}, status=400)

    from core.news_ingest import UnsafeNewsUrlError, assert_safe_public_url
    from .utils import fetch_url_meta

    try:
        assert_safe_public_url(url)
    except UnsafeNewsUrlError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    meta = fetch_url_meta(url)
    return JsonResponse(meta)


@login_required
def board_export_csv(request, board_id):
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    cards = board.cards.all()

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="infoboard_{board.title}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["상태", "유형", "제목", "내용", "URL", "파일명", "태그", "작성자", "고정", "생성일"])
    for card in cards:
        writer.writerow(
            [
                card.get_status_display(),
                card.get_card_type_display(),
                card.title,
                card.content,
                card.url,
                card.original_filename,
                ", ".join(card.tags.values_list("name", flat=True)),
                card.display_author,
                "Y" if card.is_pinned else "",
                card.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return response
