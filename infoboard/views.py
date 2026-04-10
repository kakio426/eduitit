import csv
import json
import logging
from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Max, Q, Count, Prefetch
from django.http import JsonResponse, HttpResponse, Http404, QueryDict
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, resolve, Resolver404
from django.utils import timezone
from django.views.decorators.http import require_POST

from products.models import Product
from .forms import BoardForm, CardCommentForm, CardForm, CollectionForm, StudentCardForm
from .models import Board, Card, CardComment, Collection, SharedLink, Tag

logger = logging.getLogger(__name__)

SERVICE_ROUTE = 'infoboard:dashboard'
SERVICE_TITLE = '인포보드'
SUBMIT_ACCESS_LEVELS = ('submit', 'edit')
COMMENT_RATE_LIMITS = ((15, 1), (3600, 20))


def _get_service(request):
    return (
        Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
        or Product.objects.filter(title=SERVICE_TITLE).first()
    )


def _current_request_url(request):
    htmx = getattr(request, 'htmx', None)
    current_url = getattr(htmx, 'current_url_abs_path', None) if htmx else None
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
        response['HX-Retarget'] = retarget
    if reswap:
        response['HX-Reswap'] = reswap
    if trigger_after_swap:
        if isinstance(trigger_after_swap, str):
            trigger_after_swap = {trigger_after_swap: True}
        response['HX-Trigger-After-Swap'] = json.dumps(trigger_after_swap)
    if redirect_to:
        response['HX-Redirect'] = redirect_to
    return response


def _student_submission_query():
    return Q(cards__author_user__isnull=True) & ~Q(cards__author_name='')


def _annotated_board_queryset(owner):
    return (
        Board.objects.filter(owner=owner)
        .annotate(
            num_cards=Count('cards', distinct=True),
            submission_count=Count('cards', filter=_student_submission_query(), distinct=True),
            last_submission_at=Max('cards__created_at', filter=_student_submission_query()),
        )
        .prefetch_related(
            Prefetch(
                'shared_links',
                queryset=SharedLink.objects.filter(is_active=True).order_by('-created_at'),
                to_attr='active_shared_links',
            )
        )
    )


def _build_share_url(request, shared_link):
    if not request or not shared_link:
        return ''
    return request.build_absolute_uri(reverse('infoboard:public_board', args=[shared_link.id]))


def _decorate_board(board, request=None):
    active_links = getattr(board, 'active_shared_links', None)
    if active_links is None:
        active_links = list(board.shared_links.filter(is_active=True).order_by('-created_at'))
    active_share = active_links[0] if active_links else None

    if not hasattr(board, 'num_cards'):
        board.num_cards = board.cards.count()
    if not hasattr(board, 'submission_count'):
        board.submission_count = board.cards.filter(author_user__isnull=True).exclude(author_name='').count()
    if not hasattr(board, 'last_submission_at'):
        board.last_submission_at = (
            board.cards.filter(author_user__isnull=True).exclude(author_name='').order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )

    board.active_share = active_share
    board.primary_share_access = 'submit' if board.allow_student_submit else 'view'
    board.primary_share_ready = bool(
        active_share
        and (
            active_share.access_level in SUBMIT_ACCESS_LEVELS
            if board.primary_share_access == 'submit'
            else True
        )
    )
    board.share_ready = board.primary_share_ready
    board.share_url = _build_share_url(request, active_share) if board.primary_share_ready else ''
    board.any_share_url = _build_share_url(request, active_share) if active_share else ''
    board.is_collecting = bool(board.allow_student_submit and board.primary_share_ready)
    board.has_recent_submission = bool(board.last_submission_at)
    board.primary_action_label = '제출 링크 복사' if board.allow_student_submit else '열람 링크 복사'
    board.primary_create_label = '제출 링크 만들기' if board.allow_student_submit else '열람 링크 만들기'
    board.state_tone = 'draft'
    board.state_label = '초안'
    if board.is_collecting:
        board.state_tone = 'collecting'
        board.state_label = '제출받는 중'
    elif board.has_recent_submission:
        board.state_tone = 'recent'
        board.state_label = '최근 제출 있음'
    return board


def _decorate_board_list(boards, request=None):
    return [_decorate_board(board, request=request) for board in boards]


def _dashboard_sections(boards):
    collecting = [board for board in boards if board.is_collecting]
    recent = [board for board in boards if not board.is_collecting and board.has_recent_submission]
    draft = [board for board in boards if not board.is_collecting and not board.has_recent_submission]

    collecting.sort(key=lambda board: (board.last_submission_at or board.updated_at, board.updated_at), reverse=True)
    recent.sort(key=lambda board: (board.last_submission_at or board.updated_at, board.updated_at), reverse=True)
    draft.sort(key=lambda board: board.updated_at, reverse=True)

    return [
        {
            'key': 'collecting',
            'title': '제출받는 중',
            'description': '링크를 뿌리고 바로 수집 중인 보드예요.',
            'boards': collecting,
            'empty_message': '아직 제출을 받고 있는 보드가 없어요.',
        },
        {
            'key': 'recent',
            'title': '최근 제출 있음',
            'description': '조금 전까지 자료가 올라온 보드예요.',
            'boards': recent,
            'empty_message': '최근 제출이 잡힌 보드가 아직 없어요.',
        },
        {
            'key': 'draft',
            'title': '초안',
            'description': '아직 링크를 뿌리기 전, 준비 중인 보드예요.',
            'boards': draft,
            'empty_message': '준비 중인 보드가 없어요.',
        },
    ]


def _dashboard_context(request):
    boards = list(_annotated_board_queryset(request.user))
    boards = _decorate_board_list(boards, request=request)
    sections = _dashboard_sections(boards)
    return {
        'boards': boards,
        'board_sections': sections,
        'all_board_count': len(boards),
        'collecting_count': len(sections[0]['boards']),
        'recent_count': len(sections[1]['boards']),
        'draft_count': len(sections[2]['boards']),
        'board_delete_target': 'ibBoardGrid',
    }


def _board_cards_context(board, search_q=''):
    cards = board.cards.select_related('author_user').prefetch_related('tags')
    if search_q:
        cards = cards.filter(
            Q(title__icontains=search_q) | Q(content__icontains=search_q) | Q(tags__name__icontains=search_q)
        ).distinct()
    cards = cards.annotate(
        visible_comment_count=Count('comments', filter=Q(comments__is_hidden=False), distinct=True),
        total_comment_count=Count('comments', distinct=True),
    )

    return {
        'board': board,
        'cards': cards,
        'search_q': search_q,
        'card_count': board.cards.count(),
    }


def _collection_boards_context(collection):
    boards = list(
        collection.boards.annotate(num_cards=Count('cards', distinct=True)).order_by('-updated_at')
    )
    return {
        'collection': collection,
        'boards': boards,
        'board_count': len(boards),
        'board_delete_target': 'ibCollectionBoards',
    }


def _render_board_grid_response(request, *, close_modal=False):
    context = _dashboard_context(request)
    response = render(request, 'infoboard/partials/board_grid.html', context)
    return _set_htmx_headers(
        response,
        retarget='#ibBoardGrid',
        reswap='innerHTML',
        trigger_after_swap='infoboard:close-modal' if close_modal else None,
    )


def _render_collection_grid_response(request, *, close_modal=False):
    collections = Collection.objects.filter(owner=request.user).annotate(board_count=Count('boards'))
    response = render(request, 'infoboard/partials/collection_grid.html', {'collections': collections})
    return _set_htmx_headers(
        response,
        retarget='#ibCollectionGrid',
        reswap='innerHTML',
        trigger_after_swap='infoboard:close-modal' if close_modal else None,
    )


def _render_card_grid_response(request, board, *, close_modal=False):
    search_q = _current_request_query(request).get('q', '').strip()
    context = _board_cards_context(board, search_q)
    context['public_mode'] = False
    response = render(request, 'infoboard/partials/card_grid.html', context)
    return _set_htmx_headers(
        response,
        retarget='#ibCardGrid',
        reswap='innerHTML',
        trigger_after_swap='infoboard:close-modal' if close_modal else None,
    )


def _render_public_wall_response(request, board, shared, *, close_sheet=False):
    context = _board_cards_context(board)
    context.update({'shared': shared, 'public_mode': True, 'card_count_oob_target': 'ibPublicCardCount'})
    response = render(request, 'infoboard/partials/public_wall.html', context)
    return _set_htmx_headers(
        response,
        retarget='#ibPublicWall',
        reswap='innerHTML',
        trigger_after_swap='infoboard:close-submit-sheet' if close_sheet else None,
    )


def _prepare_board_form_data(request):
    data = request.POST.copy()
    preset = data.get('preset', request.GET.get('preset', 'submit')).strip() or 'submit'
    if preset == 'submit':
        data['icon'] = data.get('icon') or '📥'
        data['color_theme'] = data.get('color_theme') or 'green'
        data['layout'] = data.get('layout') or 'grid'
        data['allow_student_submit'] = 'on'
        data.pop('is_public', None)
    else:
        data['icon'] = data.get('icon') or '📌'
        data['color_theme'] = data.get('color_theme') or 'blue'
        data['layout'] = data.get('layout') or 'grid'
    return data, preset


def _refresh_link_card_metadata(card, previous_url=None):
    if card.card_type != 'link' or not card.url:
        return

    url_changed = previous_url is not None and card.url != previous_url
    has_existing_meta = any([card.og_title, card.og_description, card.og_image, card.og_site_name])
    if not url_changed and has_existing_meta:
        return

    if url_changed:
        card.og_title = ''
        card.og_description = ''
        card.og_image = ''
        card.og_site_name = ''
        card.save(update_fields=['og_title', 'og_description', 'og_image', 'og_site_name'])

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


def _get_request_ip(request):
    forwarded_for = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip() or 'unknown'


def _comment_rate_limit_exceeded(request, shared_link):
    now_ts = int(timezone.now().timestamp())
    actor_key = _get_request_ip(request)
    for window_seconds, max_count in COMMENT_RATE_LIMITS:
        slot = now_ts // window_seconds
        cache_key = f'infoboard:comment:{shared_link.id}:{actor_key}:{window_seconds}:{slot}'
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, timeout=window_seconds + 2)
            current = 1
        else:
            try:
                current = cache.incr(cache_key)
            except Exception:
                current = int(current) + 1
                cache.set(cache_key, current, timeout=window_seconds + 2)
        if current > max_count:
            return True
    return False


def _public_comment_count(card):
    if hasattr(card, 'visible_comment_count'):
        return card.visible_comment_count
    return card.comments.filter(is_hidden=False).count()


def _total_comment_count(card):
    if hasattr(card, 'total_comment_count'):
        return card.total_comment_count
    return card.comments.count()


def _comment_thread_queryset(card, *, public_mode):
    queryset = card.comments.select_related('author_user').order_by('created_at')
    if public_mode:
        queryset = queryset.filter(is_hidden=False)
    return queryset


def _comment_shell_context(card, *, public_mode, shared=None, form=None, comments_open=False):
    visible_comment_count = _public_comment_count(card)
    total_comment_count = _total_comment_count(card)
    card.visible_comment_count = visible_comment_count
    card.total_comment_count = total_comment_count
    can_write_comments = False
    if public_mode:
        can_write_comments = bool(
            shared
            and card.board.allow_student_submit
            and shared.access_level in SUBMIT_ACCESS_LEVELS
        )
    else:
        can_write_comments = bool(card.board.allow_student_submit or total_comment_count)

    if form is None and can_write_comments:
        form = CardCommentForm(require_name=public_mode)

    return {
        'card': card,
        'shared': shared,
        'public_mode': public_mode,
        'comments_open': comments_open,
        'comment_thread_url': (
            reverse('infoboard:public_card_comments', args=[shared.id, card.id])
            if public_mode and shared
            else reverse('infoboard:card_comments', args=[card.id])
        ),
        'comment_create_url': (
            reverse('infoboard:public_comment_create', args=[shared.id, card.id])
            if public_mode and shared
            else reverse('infoboard:card_comment_create', args=[card.id])
        ),
        'comments': _comment_thread_queryset(card, public_mode=public_mode) if comments_open else [],
        'form': form,
        'can_write_comments': can_write_comments,
        'visible_comment_count': visible_comment_count,
        'total_comment_count': total_comment_count,
        'show_comment_shell': public_mode or card.board.allow_student_submit or bool(total_comment_count),
    }


def _render_comment_shell(request, card, *, public_mode, shared=None, form=None, comments_open=False, status=200):
    context = _comment_shell_context(
        card,
        public_mode=public_mode,
        shared=shared,
        form=form,
        comments_open=comments_open,
    )
    return render(request, 'infoboard/partials/card_comment_shell.html', context, status=status)


def _get_public_card(link_id, card_id, *, require_write=False):
    shared = get_object_or_404(
        SharedLink.objects.select_related('board'),
        id=link_id,
        is_active=True,
    )
    if shared.is_expired:
        raise Http404
    card = get_object_or_404(
        Card.objects.select_related('board'),
        id=card_id,
        board=shared.board,
    )
    if require_write and (not shared.board.allow_student_submit or shared.access_level not in SUBMIT_ACCESS_LEVELS):
        raise Http404
    return shared, card


# ── 교사 대시보드 ────────────────────────────────────────

@login_required
def dashboard(request):
    """교사용 메인 대시보드 — 내 보드 목록."""
    service = _get_service(request)
    context = {
        'service': service,
    }
    context.update(_dashboard_context(request))

    if request.htmx:
        return render(request, 'infoboard/partials/board_grid.html', context)
    return render(request, 'infoboard/dashboard.html', context)


# ── 보드 CRUD ────────────────────────────────────────────

@login_required
def board_create(request):
    """보드 생성."""
    preset = (request.POST.get('preset') or request.GET.get('preset') or 'submit').strip() or 'submit'
    if request.method == 'POST':
        form_data, preset = _prepare_board_form_data(request)
        form = BoardForm(form_data, owner=request.user)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            if preset == 'submit':
                board.shared_links.filter(is_active=True).update(is_active=False)
                SharedLink.objects.create(
                    board=board,
                    created_by=request.user,
                    access_level='submit',
                )
            logger.info(f'[InfoBoard] Board created: {board.title} (id={board.id})')
            if request.htmx:
                return _render_board_grid_response(request, close_modal=True)
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        form = BoardForm(
            initial={
                'icon': '📥' if preset == 'submit' else '📌',
                'color_theme': 'green' if preset == 'submit' else 'blue',
                'layout': 'grid',
                'allow_student_submit': preset == 'submit',
            },
            owner=request.user,
        )

    context = {
        'form': form,
        'is_edit': False,
        'modal_mode': bool(request.htmx),
        'preset': preset,
    }

    if request.htmx:
        return render(request, 'infoboard/partials/board_form_modal.html', context)
    return render(request, 'infoboard/board_form.html', context)


@login_required
def board_detail(request, board_id):
    """보드 상세 — 카드 그리드."""
    board = get_object_or_404(_annotated_board_queryset(request.user), id=board_id)
    board = _decorate_board(board, request=request)
    service = _get_service(request)
    search_q = request.GET.get('q', '')
    cards_context = _board_cards_context(board, search_q)

    context = {
        'service': service,
        'board': board,
        'cards': cards_context['cards'],
        'search_q': search_q,
        'card_count': cards_context['card_count'],
        'current_path': request.get_full_path(),
        'modal_mode': False,
        'public_mode': False,
    }

    if request.htmx:
        return render(request, 'infoboard/partials/card_grid.html', context)
    return render(request, 'infoboard/board_detail.html', context)


@login_required
@require_POST
def board_layout(request, board_id):
    """보드 레이아웃 변경."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    layout = request.POST.get('layout', '').strip()
    if layout in dict(Board.LAYOUT_CHOICES) and layout != board.layout:
        board.layout = layout
        board.save(update_fields=['layout'])

    next_url = request.POST.get('next', '').strip() or reverse('infoboard:board_detail', args=[board.id])
    if request.htmx:
        return _set_htmx_headers(HttpResponse(status=204), redirect_to=next_url)
    return redirect(next_url)


@login_required
def board_edit(request, board_id):
    """보드 수정."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    current_route = _resolve_current_route(request)
    preset = 'submit' if board.allow_student_submit else 'general'

    if request.method == 'POST':
        form = BoardForm(request.POST, instance=board, owner=request.user)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            logger.info(f'[InfoBoard] Board updated: {board.title} (id={board.id})')
            if request.htmx:
                if current_route and current_route.url_name == 'dashboard':
                    return _render_board_grid_response(request, close_modal=True)
                if current_route and current_route.url_name == 'board_detail':
                    return _set_htmx_headers(
                        HttpResponse(status=204),
                        redirect_to=_current_request_url(request),
                    )
                return _set_htmx_headers(
                    HttpResponse(status=204),
                    redirect_to=reverse('infoboard:board_detail', args=[board.id]),
                )
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        tag_names = ','.join(board.tags.values_list('name', flat=True))
        form = BoardForm(instance=board, initial={'tag_names': tag_names}, owner=request.user)

    context = {
        'form': form,
        'board': board,
        'is_edit': True,
        'modal_mode': bool(request.htmx),
        'preset': preset,
    }

    if request.htmx:
        return render(request, 'infoboard/partials/board_form_modal.html', context)
    return render(request, 'infoboard/board_form.html', context)


@login_required
@require_POST
def board_delete(request, board_id):
    """보드 삭제."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    current_route = _resolve_current_route(request)
    collection = None
    if current_route and current_route.url_name == 'collection_detail':
        collection_id = current_route.kwargs.get('collection_id')
        if collection_id:
            collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    title = board.title
    board.delete()
    logger.info(f'[InfoBoard] Board deleted: {title}')
    if request.htmx:
        if current_route and current_route.url_name == 'collection_detail' and collection is not None:
            return render(
                request,
                'infoboard/partials/collection_boards.html',
                _collection_boards_context(collection),
            )
        if current_route and current_route.url_name == 'board_detail':
            return _set_htmx_headers(
                HttpResponse(status=204),
                redirect_to=reverse('infoboard:dashboard'),
            )
        return _render_board_grid_response(request)
    return redirect('infoboard:dashboard')


# ── 카드 CRUD ────────────────────────────────────────────

@login_required
def card_add(request, board_id):
    """카드 추가."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)

    if request.method == 'POST':
        form = CardForm(request.POST, request.FILES)
        if form.is_valid():
            card = form.save_with_tags(board, author_user=request.user)
            _refresh_link_card_metadata(card)
            logger.info(f'[InfoBoard] Card added: {card.title} to {board.title}')
            if request.htmx:
                return _render_card_grid_response(request, board, close_modal=True)
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        form = CardForm(initial={'card_type': request.GET.get('type', 'text')})

    context = {'form': form, 'board': board, 'is_edit': False, 'modal_mode': bool(request.htmx)}

    if request.htmx:
        return render(request, 'infoboard/partials/card_form_modal.html', context)
    return render(request, 'infoboard/card_form.html', context)


@login_required
def card_edit(request, card_id):
    """카드 수정."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    previous_url = card.url

    if request.method == 'POST':
        form = CardForm(request.POST, request.FILES, instance=card)
        if form.is_valid():
            card = form.save_with_tags(board, author_user=request.user)
            _refresh_link_card_metadata(card, previous_url=previous_url)
            logger.info(f'[InfoBoard] Card updated: {card.title}')
            if request.htmx:
                return _render_card_grid_response(request, board, close_modal=True)
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        tag_names = ','.join(card.tags.values_list('name', flat=True))
        form = CardForm(instance=card, initial={'tag_names': tag_names})

    context = {'form': form, 'board': board, 'card': card, 'is_edit': True, 'modal_mode': bool(request.htmx)}

    if request.htmx:
        return render(request, 'infoboard/partials/card_form_modal.html', context)
    return render(request, 'infoboard/card_form.html', context)


@login_required
@require_POST
def card_delete(request, card_id):
    """카드 삭제."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    card.delete()
    if request.htmx:
        return _render_card_grid_response(request, board)
    return redirect('infoboard:board_detail', board_id=board.id)


@login_required
@require_POST
def card_toggle_pin(request, card_id):
    """카드 고정/해제 토글."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board
    card.is_pinned = not card.is_pinned
    card.save(update_fields=['is_pinned'])
    if request.htmx:
        return _render_card_grid_response(request, board)
    return redirect('infoboard:board_detail', board_id=board.id)


# ── 카드 댓글 ────────────────────────────────────────────

@login_required
def card_comments(request, card_id):
    """교사용 카드 댓글 스레드."""
    card = get_object_or_404(Card.objects.select_related('board'), id=card_id, board__owner=request.user)
    comments_open = request.GET.get('open', '1') != '0'
    return _render_comment_shell(request, card, public_mode=False, comments_open=comments_open)


@login_required
@require_POST
def card_comment_create(request, card_id):
    """교사용 카드 댓글 작성."""
    card = get_object_or_404(Card.objects.select_related('board'), id=card_id, board__owner=request.user)
    form = CardCommentForm(request.POST, require_name=False)
    if form.is_valid():
        form.save_for_card(card, author_user=request.user)
        if request.htmx:
            return _render_comment_shell(request, card, public_mode=False, comments_open=True)
        return redirect('infoboard:board_detail', board_id=card.board.id)

    if request.htmx:
        return _render_comment_shell(request, card, public_mode=False, form=form, comments_open=True)
    return redirect('infoboard:board_detail', board_id=card.board.id)


@login_required
@require_POST
def comment_hide(request, comment_id):
    """교사가 카드 댓글을 숨김 처리."""
    comment = get_object_or_404(
        CardComment.objects.select_related('card__board'),
        id=comment_id,
        card__board__owner=request.user,
    )
    if not comment.is_hidden:
        comment.is_hidden = True
        comment.hidden_reason = 'teacher'
        comment.save(update_fields=['is_hidden', 'hidden_reason', 'updated_at'])

    if request.htmx:
        return _render_comment_shell(request, comment.card, public_mode=False, comments_open=True)
    return redirect('infoboard:board_detail', board_id=comment.card.board.id)


@login_required
@require_POST
def comment_delete(request, comment_id):
    """교사가 카드 댓글을 완전 삭제."""
    comment = get_object_or_404(
        CardComment.objects.select_related('card__board'),
        id=comment_id,
        card__board__owner=request.user,
    )
    board_id = comment.card.board.id
    card = comment.card
    comment.delete()

    if request.htmx:
        return _render_comment_shell(request, card, public_mode=False, comments_open=True)
    return redirect('infoboard:board_detail', board_id=board_id)


# ── 태그 ─────────────────────────────────────────────────

@login_required
def tags_json(request):
    """사용자 태그 목록 JSON 반환."""
    tags = Tag.objects.filter(owner=request.user).values('id', 'name', 'color')
    return JsonResponse(list(tags), safe=False)


# ── 공유 보드 (비로그인) ─────────────────────────────────

def public_board(request, link_id):
    """공유 링크로 접근하는 공개 보드."""
    shared = get_object_or_404(SharedLink, id=link_id, is_active=True)
    if shared.is_expired:
        return render(request, 'infoboard/public_expired.html', {'board_title': shared.board.title})

    shared.access_count += 1
    shared.save(update_fields=['access_count'])

    board = shared.board
    cards_context = _board_cards_context(board)

    context = {
        'board': board,
        'cards': cards_context['cards'],
        'shared': shared,
        'can_submit': board.allow_student_submit and shared.access_level in ('submit', 'edit'),
        'card_count': cards_context['card_count'],
        'public_mode': True,
    }
    return render(request, 'infoboard/public_board.html', context)


def student_submit(request, link_id):
    """학생 카드 제출 (비로그인)."""
    shared = get_object_or_404(SharedLink, id=link_id, is_active=True)
    if shared.is_expired or not shared.board.allow_student_submit or shared.access_level not in ('submit', 'edit'):
        raise Http404

    board = shared.board
    if request.method == 'POST':
        form = StudentCardForm(request.POST, request.FILES, board=board)
        if form.is_valid():
            card = form.save_for_board(board)
            _refresh_link_card_metadata(card)
            logger.info(f'[InfoBoard] Student submitted card: {card.title} by {card.author_name}')
            if request.htmx:
                return _render_public_wall_response(request, board, shared, close_sheet=True)
            return redirect('infoboard:public_board', link_id=link_id)
    else:
        form = StudentCardForm(initial={'card_type': 'text'}, board=board)

    context = {'form': form, 'board': board, 'shared': shared}
    if request.htmx:
        return render(request, 'infoboard/partials/student_submit_form.html', context)
    return render(request, 'infoboard/student_submit.html', context)


def public_card_comments(request, link_id, card_id):
    """공개 보드 카드 댓글 스레드."""
    shared, card = _get_public_card(link_id, card_id)
    comments_open = request.GET.get('open', '1') != '0'
    return _render_comment_shell(request, card, public_mode=True, shared=shared, comments_open=comments_open)


@require_POST
def public_comment_create(request, link_id, card_id):
    """공개 보드 카드 댓글 작성."""
    shared, card = _get_public_card(link_id, card_id, require_write=True)
    form = CardCommentForm(request.POST, require_name=True)

    if form.is_valid():
        if _comment_rate_limit_exceeded(request, shared):
            return HttpResponse('댓글 작성 속도가 너무 빠릅니다. 잠시 후 다시 시도해주세요.', status=429)

        form.save_for_card(card, author_name=form.cleaned_data['author_name'])
        if request.htmx:
            return _render_comment_shell(request, card, public_mode=True, shared=shared, comments_open=True)
        return redirect('infoboard:public_board', link_id=shared.id)

    if request.htmx:
        return _render_comment_shell(
            request,
            card,
            public_mode=True,
            shared=shared,
            form=form,
            comments_open=True,
        )
    return redirect('infoboard:public_board', link_id=shared.id)


# ── 공유 링크 관리 ───────────────────────────────────────

@login_required
def share_panel(request, board_id):
    """공유 패널 (HTMX partial)."""
    board = get_object_or_404(_annotated_board_queryset(request.user), id=board_id)
    board = _decorate_board(board, request=request)
    shared_link = board.active_share
    context = {'board': board, 'shared_link': shared_link}
    return render(request, 'infoboard/partials/share_panel.html', context)


@login_required
@require_POST
def share_create(request, board_id):
    """공유 링크 생성/갱신."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    default_access = 'submit' if board.allow_student_submit else 'view'
    access_level = request.POST.get('access_level', default_access)
    if access_level not in {'view', 'submit'}:
        access_level = default_access

    # 기존 활성 링크 비활성화
    board.shared_links.filter(is_active=True).update(is_active=False)

    shared_link = SharedLink.objects.create(
        board=board,
        created_by=request.user,
        access_level=access_level,
    )
    logger.info(f'[InfoBoard] Share link created: {shared_link.id} for {board.title}')

    board = _decorate_board(board, request=request)
    board.active_share = shared_link
    board.primary_share_ready = True if access_level == board.primary_share_access or board.primary_share_access == 'view' else False
    board.share_ready = board.primary_share_ready
    board.share_url = _build_share_url(request, shared_link) if board.primary_share_ready else ''
    board.any_share_url = _build_share_url(request, shared_link)
    context = {'board': board, 'shared_link': shared_link}
    if request.htmx:
        return render(request, 'infoboard/partials/share_panel.html', context)
    return redirect('infoboard:board_detail', board_id=board.id)


# ── 검색 ─────────────────────────────────────────────────

@login_required
def search(request):
    """전체 검색 (보드 + 카드 + 태그)."""
    if not request.htmx:
        return redirect('infoboard:dashboard')

    q = request.GET.get('q', '').strip()
    results = {'boards': [], 'cards': [], 'tags': []}

    if q:
        results['boards'] = Board.objects.filter(
            owner=request.user
        ).filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        ).annotate(num_cards=Count('cards'))[:10]

        results['cards'] = Card.objects.filter(
            board__owner=request.user
        ).filter(
            Q(title__icontains=q) | Q(content__icontains=q)
        ).select_related('board')[:10]

        results['tags'] = Tag.objects.filter(
            owner=request.user, name__icontains=q
        ).annotate(
            board_count=Count('boards', distinct=True),
            card_count=Count('cards', distinct=True),
        )[:10]

    context = {'q': q, **results}
    return render(request, 'infoboard/partials/search_results.html', context)


# ── 파일 다운로드 ────────────────────────────────────────

def card_download(request, card_id):
    """카드 파일 다운로드."""
    card = get_object_or_404(Card, id=card_id)
    link_id = request.GET.get('link_id', '').strip()

    # 소유자, 공개 보드, 또는 활성 공유 링크 문맥에서만 허용
    if not request.user.is_authenticated or card.board.owner != request.user:
        if not card.board.is_public:
            if not link_id:
                raise Http404
            shared = get_object_or_404(SharedLink, id=link_id, board=card.board, is_active=True)
            if shared.is_expired:
                raise Http404
    if not card.file:
        raise Http404

    filename = card.original_filename or 'download'
    response = HttpResponse(card.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── 컬렉션 CRUD ──────────────────────────────────────────

@login_required
def collection_list(request):
    """컬렉션 목록."""
    collections = Collection.objects.filter(owner=request.user).annotate(
        board_count=Count('boards')
    )
    context = {'collections': collections}
    if request.htmx:
        return render(request, 'infoboard/partials/collection_grid.html', context)
    return render(request, 'infoboard/collection_list.html', context)


@login_required
def collection_create(request):
    """컬렉션 생성."""
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.owner = request.user
            collection.save()
            # 보드 연결
            board_ids = request.POST.getlist('board_ids')
            if board_ids:
                boards = Board.objects.filter(id__in=board_ids, owner=request.user)
                collection.boards.set(boards)
            logger.info(f'[InfoBoard] Collection created: {collection.title}')
            if request.htmx:
                return _render_collection_grid_response(request, close_modal=True)
            return redirect('infoboard:collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm()

    boards = Board.objects.filter(owner=request.user).order_by('title')
    context = {'form': form, 'boards': boards, 'is_edit': False, 'modal_mode': bool(request.htmx)}
    if request.htmx:
        return render(request, 'infoboard/partials/collection_form_modal.html', context)
    return render(request, 'infoboard/collection_form.html', context)


@login_required
def collection_detail(request, collection_id):
    """컬렉션 상세 — 포함된 보드 목록."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    context = _collection_boards_context(collection)
    context['collection'] = collection
    return render(request, 'infoboard/collection_detail.html', context)


@login_required
def collection_edit(request, collection_id):
    """컬렉션 수정."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    current_route = _resolve_current_route(request)
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            collection = form.save()
            board_ids = request.POST.getlist('board_ids')
            boards = Board.objects.filter(id__in=board_ids, owner=request.user)
            collection.boards.set(boards)
            logger.info(f'[InfoBoard] Collection updated: {collection.title}')
            if request.htmx:
                if current_route and current_route.url_name == 'collection_detail':
                    return _set_htmx_headers(
                        HttpResponse(status=204),
                        redirect_to=_current_request_url(request),
                    )
                return _render_collection_grid_response(request, close_modal=True)
            return redirect('infoboard:collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm(instance=collection)

    boards = Board.objects.filter(owner=request.user).order_by('title')
    selected_ids = set(str(b.id) for b in collection.boards.all())
    context = {
        'form': form,
        'collection': collection,
        'boards': boards,
        'selected_ids': selected_ids,
        'is_edit': True,
        'modal_mode': bool(request.htmx),
    }
    if request.htmx:
        return render(request, 'infoboard/partials/collection_form_modal.html', context)
    return render(request, 'infoboard/collection_form.html', context)


@login_required
@require_POST
def collection_delete(request, collection_id):
    """컬렉션 삭제 (보드 자체는 유지)."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    current_route = _resolve_current_route(request)
    collection.delete()
    if request.htmx:
        if current_route and current_route.url_name == 'collection_detail':
            return _set_htmx_headers(
                HttpResponse(status=204),
                redirect_to=f"{reverse('infoboard:dashboard')}?tab=collections",
            )
        return _render_collection_grid_response(request)
    return redirect(f"{reverse('infoboard:dashboard')}?tab=collections")


@login_required
@require_POST
def collection_toggle_board(request, collection_id):
    """컬렉션에 보드 추가/제거 토글."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    board_id = request.POST.get('board_id')
    if board_id:
        board = get_object_or_404(Board, id=board_id, owner=request.user)
        if collection.boards.filter(id=board.id).exists():
            collection.boards.remove(board)
        else:
            collection.boards.add(board)
    context = _collection_boards_context(collection)
    if request.htmx:
        return render(request, 'infoboard/partials/collection_boards.html', context)
    return redirect('infoboard:collection_detail', collection_id=collection.id)


# ── OG 메타 추출 API ─────────────────────────────────────

@login_required
def fetch_og_meta(request):
    """URL에서 OG 메타를 추출해 JSON으로 반환."""
    url = request.GET.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'URL이 필요합니다.'}, status=400)

    from core.news_ingest import UnsafeNewsUrlError, assert_safe_public_url
    from .utils import fetch_url_meta

    try:
        assert_safe_public_url(url)
    except UnsafeNewsUrlError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    meta = fetch_url_meta(url)
    return JsonResponse(meta)


# ── 내보내기 ─────────────────────────────────────────────

@login_required
def board_export_csv(request, board_id):
    """보드 카드를 CSV로 내보내기."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    cards = board.cards.all()

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="infoboard_{board.title}.csv"'

    # BOM for Excel
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['유형', '제목', '내용', 'URL', '파일명', '태그', '작성자', '고정', '생성일'])
    for card in cards:
        tags = ', '.join(card.tags.values_list('name', flat=True))
        writer.writerow([
            card.get_card_type_display(),
            card.title,
            card.content,
            card.url,
            card.original_filename,
            tags,
            card.display_author,
            '✓' if card.is_pinned else '',
            card.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response
