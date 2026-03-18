import csv
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from products.models import Product
from .forms import BoardForm, CardForm, CollectionForm, StudentCardForm
from .models import Board, Card, Collection, SharedLink, Tag

logger = logging.getLogger(__name__)

SERVICE_ROUTE = 'infoboard:dashboard'
SERVICE_TITLE = '인포보드'


def _get_service(request):
    return (
        Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
        or Product.objects.filter(title=SERVICE_TITLE).first()
    )


# ── 교사 대시보드 ────────────────────────────────────────

@login_required
def dashboard(request):
    """교사용 메인 대시보드 — 내 보드 목록."""
    service = _get_service(request)
    tab = request.GET.get('tab', 'boards')
    sort = request.GET.get('sort', 'recent')
    tag_filter = request.GET.get('tag', '')

    boards = Board.objects.filter(owner=request.user).annotate(num_cards=Count('cards'))

    if tag_filter:
        boards = boards.filter(tags__name=tag_filter)

    sort_map = {
        'recent': '-updated_at',
        'oldest': 'updated_at',
        'name': 'title',
        'cards': '-num_cards',
    }
    boards = boards.order_by(sort_map.get(sort, '-updated_at'))

    user_tags = Tag.objects.filter(owner=request.user).order_by('name')
    collections = Collection.objects.filter(owner=request.user) if tab == 'collections' else None

    context = {
        'service': service,
        'boards': boards,
        'collections': collections,
        'user_tags': user_tags,
        'current_tab': tab,
        'current_sort': sort,
        'current_tag': tag_filter,
    }

    if request.htmx:
        return render(request, 'infoboard/partials/board_grid.html', context)
    return render(request, 'infoboard/dashboard.html', context)


# ── 보드 CRUD ────────────────────────────────────────────

@login_required
def board_create(request):
    """보드 생성."""
    if request.method == 'POST':
        form = BoardForm(request.POST)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            logger.info(f'[InfoBoard] Board created: {board.title} (id={board.id})')
            if request.htmx:
                return render(request, 'infoboard/partials/board_card.html', {'board': board})
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        form = BoardForm()

    user_tags = Tag.objects.filter(owner=request.user).order_by('name')
    context = {'form': form, 'user_tags': user_tags, 'is_edit': False}

    if request.htmx:
        return render(request, 'infoboard/partials/board_form_modal.html', context)
    return render(request, 'infoboard/board_form.html', context)


@login_required
def board_detail(request, board_id):
    """보드 상세 — 카드 그리드."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    service = _get_service(request)

    # 레이아웃 변경 처리
    layout_param = request.GET.get('layout', '')
    if layout_param in ('grid', 'list', 'timeline') and layout_param != board.layout:
        board.layout = layout_param
        board.save(update_fields=['layout'])

    search_q = request.GET.get('q', '')
    cards = board.cards.all()
    if search_q:
        cards = cards.filter(
            Q(title__icontains=search_q) | Q(content__icontains=search_q) | Q(tags__name__icontains=search_q)
        ).distinct()

    board_tags = Tag.objects.filter(
        Q(boards=board) | Q(cards__board=board)
    ).distinct().order_by('name')

    shared_link = board.shared_links.filter(is_active=True).first()

    context = {
        'service': service,
        'board': board,
        'cards': cards,
        'board_tags': board_tags,
        'shared_link': shared_link,
        'search_q': search_q,
    }

    if request.htmx:
        return render(request, 'infoboard/partials/card_grid.html', context)
    return render(request, 'infoboard/board_detail.html', context)


@login_required
def board_edit(request, board_id):
    """보드 수정."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)

    if request.method == 'POST':
        form = BoardForm(request.POST, instance=board)
        if form.is_valid():
            board = form.save_with_tags(request.user)
            logger.info(f'[InfoBoard] Board updated: {board.title} (id={board.id})')
            if request.htmx:
                return render(request, 'infoboard/partials/board_card.html', {'board': board})
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        tag_names = ','.join(board.tags.values_list('name', flat=True))
        form = BoardForm(instance=board, initial={'tag_names': tag_names})

    user_tags = Tag.objects.filter(owner=request.user).order_by('name')
    context = {'form': form, 'board': board, 'user_tags': user_tags, 'is_edit': True}

    if request.htmx:
        return render(request, 'infoboard/partials/board_form_modal.html', context)
    return render(request, 'infoboard/board_form.html', context)


@login_required
@require_POST
def board_delete(request, board_id):
    """보드 삭제."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    title = board.title
    board.delete()
    logger.info(f'[InfoBoard] Board deleted: {title}')
    if request.htmx:
        return HttpResponse('')
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
            # OG 메타 자동 추출 (링크 카드)
            if card.card_type == 'link' and card.url and not card.og_title:
                from .utils import fetch_url_meta
                meta = fetch_url_meta(card.url)
                if meta:
                    for k, v in meta.items():
                        setattr(card, k, v)
                    card.save(update_fields=list(meta.keys()))
            logger.info(f'[InfoBoard] Card added: {card.title} to {board.title}')
            if request.htmx:
                return render(request, 'infoboard/partials/card_item.html', {'card': card, 'board': board})
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        form = CardForm(initial={'card_type': request.GET.get('type', 'text')})

    user_tags = Tag.objects.filter(owner=request.user).order_by('name')
    context = {'form': form, 'board': board, 'user_tags': user_tags, 'is_edit': False}

    if request.htmx:
        return render(request, 'infoboard/partials/card_form_modal.html', context)
    return render(request, 'infoboard/card_form.html', context)


@login_required
def card_edit(request, card_id):
    """카드 수정."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board = card.board

    if request.method == 'POST':
        form = CardForm(request.POST, request.FILES, instance=card)
        if form.is_valid():
            card = form.save_with_tags(board, author_user=request.user)
            # OG 메타 자동 추출 (링크 카드 - URL이 변경된 경우)
            if card.card_type == 'link' and card.url and not card.og_title:
                from .utils import fetch_url_meta
                meta = fetch_url_meta(card.url)
                if meta:
                    for k, v in meta.items():
                        setattr(card, k, v)
                    card.save(update_fields=list(meta.keys()))
            logger.info(f'[InfoBoard] Card updated: {card.title}')
            if request.htmx:
                return render(request, 'infoboard/partials/card_item.html', {'card': card, 'board': board})
            return redirect('infoboard:board_detail', board_id=board.id)
    else:
        tag_names = ','.join(card.tags.values_list('name', flat=True))
        form = CardForm(instance=card, initial={'tag_names': tag_names})

    user_tags = Tag.objects.filter(owner=request.user).order_by('name')
    context = {'form': form, 'board': board, 'card': card, 'user_tags': user_tags, 'is_edit': True}

    if request.htmx:
        return render(request, 'infoboard/partials/card_form_modal.html', context)
    return render(request, 'infoboard/card_form.html', context)


@login_required
@require_POST
def card_delete(request, card_id):
    """카드 삭제."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    board_id = card.board_id
    card.delete()
    if request.htmx:
        return HttpResponse('')
    return redirect('infoboard:board_detail', board_id=board_id)


@login_required
@require_POST
def card_toggle_pin(request, card_id):
    """카드 고정/해제 토글."""
    card = get_object_or_404(Card, id=card_id, board__owner=request.user)
    card.is_pinned = not card.is_pinned
    card.save(update_fields=['is_pinned'])
    if request.htmx:
        return render(request, 'infoboard/partials/card_item.html', {'card': card, 'board': card.board})
    return redirect('infoboard:board_detail', board_id=card.board_id)


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
    cards = board.cards.all()

    search_q = request.GET.get('q', '')
    if search_q:
        cards = cards.filter(
            Q(title__icontains=search_q) | Q(content__icontains=search_q) | Q(tags__name__icontains=search_q)
        ).distinct()

    context = {
        'board': board,
        'cards': cards,
        'shared': shared,
        'search_q': search_q,
        'can_submit': shared.access_level in ('submit', 'edit'),
    }
    return render(request, 'infoboard/public_board.html', context)


def student_submit(request, link_id):
    """학생 카드 제출 (비로그인)."""
    shared = get_object_or_404(SharedLink, id=link_id, is_active=True)
    if shared.is_expired or shared.access_level not in ('submit', 'edit'):
        raise Http404

    board = shared.board
    if request.method == 'POST':
        form = StudentCardForm(request.POST, request.FILES)
        if form.is_valid():
            card = form.save(commit=False)
            card.board = board
            card.author_name = form.cleaned_data['author_name']
            if card.file:
                card.original_filename = card.file.name
                card.file_size = card.file.size
            card.save()
            logger.info(f'[InfoBoard] Student submitted card: {card.title} by {card.author_name}')
            if request.htmx:
                return render(request, 'infoboard/partials/submit_success.html', {'card': card})
            return redirect('infoboard:public_board', link_id=link_id)
    else:
        form = StudentCardForm(initial={'card_type': 'text'})

    context = {'form': form, 'board': board, 'shared': shared}
    if request.htmx:
        return render(request, 'infoboard/partials/student_submit_form.html', context)
    return render(request, 'infoboard/student_submit.html', context)


# ── 공유 링크 관리 ───────────────────────────────────────

@login_required
def share_panel(request, board_id):
    """공유 패널 (HTMX partial)."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    shared_link = board.shared_links.filter(is_active=True).first()
    context = {'board': board, 'shared_link': shared_link}
    return render(request, 'infoboard/partials/share_panel.html', context)


@login_required
@require_POST
def share_create(request, board_id):
    """공유 링크 생성/갱신."""
    board = get_object_or_404(Board, id=board_id, owner=request.user)
    access_level = request.POST.get('access_level', 'view')

    # 기존 활성 링크 비활성화
    board.shared_links.filter(is_active=True).update(is_active=False)

    shared_link = SharedLink.objects.create(
        board=board,
        created_by=request.user,
        access_level=access_level,
    )
    logger.info(f'[InfoBoard] Share link created: {shared_link.id} for {board.title}')

    context = {'board': board, 'shared_link': shared_link}
    if request.htmx:
        return render(request, 'infoboard/partials/share_panel.html', context)
    return redirect('infoboard:board_detail', board_id=board.id)


# ── 검색 ─────────────────────────────────────────────────

@login_required
def search(request):
    """전체 검색 (보드 + 카드 + 태그)."""
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
    if request.htmx:
        return render(request, 'infoboard/partials/search_results.html', context)
    return render(request, 'infoboard/search.html', context)


# ── 파일 다운로드 ────────────────────────────────────────

def card_download(request, card_id):
    """카드 파일 다운로드."""
    card = get_object_or_404(Card, id=card_id)

    # 소유자이거나 공개 보드인 경우만 허용
    if not card.board.is_public and (not request.user.is_authenticated or card.board.owner != request.user):
        # 공유 링크를 통한 접근인지 확인
        referer = request.META.get('HTTP_REFERER', '')
        if '/s/' not in referer:
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
                return render(request, 'infoboard/partials/collection_card.html', {'collection': collection})
            return redirect('infoboard:collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm()

    boards = Board.objects.filter(owner=request.user).order_by('title')
    context = {'form': form, 'boards': boards, 'is_edit': False}
    if request.htmx:
        return render(request, 'infoboard/partials/collection_form_modal.html', context)
    return render(request, 'infoboard/collection_form.html', context)


@login_required
def collection_detail(request, collection_id):
    """컬렉션 상세 — 포함된 보드 목록."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    boards = collection.boards.annotate(num_cards=Count('cards')).order_by('-updated_at')
    context = {'collection': collection, 'boards': boards}
    return render(request, 'infoboard/collection_detail.html', context)


@login_required
def collection_edit(request, collection_id):
    """컬렉션 수정."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            collection = form.save()
            board_ids = request.POST.getlist('board_ids')
            boards = Board.objects.filter(id__in=board_ids, owner=request.user)
            collection.boards.set(boards)
            logger.info(f'[InfoBoard] Collection updated: {collection.title}')
            if request.htmx:
                return render(request, 'infoboard/partials/collection_card.html', {'collection': collection})
            return redirect('infoboard:collection_detail', collection_id=collection.id)
    else:
        form = CollectionForm(instance=collection)

    boards = Board.objects.filter(owner=request.user).order_by('title')
    selected_ids = set(str(b.id) for b in collection.boards.all())
    context = {'form': form, 'collection': collection, 'boards': boards, 'selected_ids': selected_ids, 'is_edit': True}
    if request.htmx:
        return render(request, 'infoboard/partials/collection_form_modal.html', context)
    return render(request, 'infoboard/collection_form.html', context)


@login_required
@require_POST
def collection_delete(request, collection_id):
    """컬렉션 삭제 (보드 자체는 유지)."""
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    collection.delete()
    if request.htmx:
        return HttpResponse('')
    return redirect('infoboard:dashboard', **{'tab': 'collections'})


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
    boards = collection.boards.annotate(num_cards=Count('cards')).order_by('-updated_at')
    context = {'collection': collection, 'boards': boards}
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

    from .utils import fetch_url_meta
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

