import os
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from core.utils import ratelimit_key_for_master_only
from google import genai

from .models import PadletDocument, PadletBotSettings, LinkedPadletBoard
from .forms import PadletDocumentForm
from .rag_utils import get_padlet_rag_service, chunk_text
from .padlet_api import get_padlet_client, is_padlet_api_configured, PadletAPIClient

# Gemini 모델 설정
# 게시판 요약/질의응답 → 저렴한 Lite 모델
GEMINI_MODEL = "gemini-2.5-flash-lite"

# 기본 시스템 프롬프트
DEFAULT_SYSTEM_PROMPT = """당신은 패들릿(Padlet)에 올라온 게시물을 기반으로 질문에 답변하는 AI 비서입니다.

핵심 역할:
- 패들릿에 올라온 내용을 바탕으로 정확하게 답변
- 학생들의 질문에 친근하고 이해하기 쉽게 설명
- 패들릿에 없는 내용은 솔직하게 "해당 내용은 패들릿에서 찾을 수 없습니다"라고 안내

답변 원칙:
1. 패들릿의 게시물 내용을 참고하여 정확히 답변
2. 친절하고 학생 눈높이에 맞는 설명 사용
3. 필요시 관련 게시물 제목이나 작성자 언급
4. 불확실한 내용은 "패들릿을 직접 확인해보세요"라고 안내"""


def get_gemini_client(request):
    """Gemini 클라이언트 생성"""
    api_key = None

    if request.user.is_authenticated:
        try:
            user_key = request.user.userprofile.gemini_api_key
            if user_key:
                api_key = user_key
        except Exception:
            pass

    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY', '')

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


def get_system_prompt() -> str:
    """시스템 프롬프트 가져오기"""
    try:
        settings = PadletBotSettings.objects.filter(is_active=True).first()
        if settings:
            return settings.system_prompt
    except Exception:
        pass
    return DEFAULT_SYSTEM_PROMPT


def get_welcome_message() -> str:
    """환영 메시지 가져오기"""
    try:
        settings = PadletBotSettings.objects.filter(is_active=True).first()
        if settings and settings.welcome_message:
            return settings.welcome_message
    except Exception:
        pass
    return "안녕하세요! 패들릿 내용에 대해 질문해 주세요."


@login_required
def chat_view(request):
    """채팅 메인 뷰 (로그인 필요)"""
    # 세션에서 채팅 기록 가져오기 (최대 50개 유지)
    chat_history = request.session.get('padlet_chat_history', [])[-50:]

    # 업로드된 문서 수 확인
    doc_count = PadletDocument.objects.filter(is_processed=True).count()

    # 연동된 패들릿 수 확인
    linked_count = LinkedPadletBoard.objects.filter(is_processed=True).count()

    # RAG 서비스에서 청크 수 확인
    chunk_count = 0
    try:
        rag = get_padlet_rag_service()
        if rag:
            chunk_count = rag.get_document_count()
    except Exception:
        pass

    return render(request, 'padlet_bot/chat.html', {
        'chat_history': chat_history,
        'doc_count': doc_count,
        'linked_count': linked_count,
        'chunk_count': chunk_count,
        'welcome_message': get_welcome_message(),
    })


@login_required
def clear_chat(request):
    """채팅 기록 삭제 (AJAX, 로그인 필요)"""
    if request.method == 'POST':
        request.session['padlet_chat_history'] = []
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=True)
@require_POST
def send_message(request):
    """메시지 전송 및 AI 응답 (AJAX, 로그인 필요)"""
    user_message = request.POST.get('message', '').strip()

    if not user_message:
        return JsonResponse({'error': '메시지를 입력해주세요.'}, status=400)

    # Gemini 클라이언트 가져오기
    client = get_gemini_client(request)
    if not client:
        return JsonResponse({
            'error': 'API 키가 설정되지 않았습니다. 설정 페이지에서 Gemini API 키를 등록해주세요.'
        }, status=400)

    # RAG 컨텍스트 가져오기
    rag_context = ""
    try:
        rag = get_padlet_rag_service()
        if rag:
            rag_context = rag.get_context_for_query(user_message, n_results=5)
    except Exception as e:
        print(f"[WARNING] RAG 검색 실패: {e}")

    # 시스템 프롬프트 구성
    system_prompt = get_system_prompt()

    if rag_context:
        system_prompt += f"""

아래는 패들릿에서 검색된 관련 게시물입니다.
이 내용을 바탕으로 정확하게 답변해주세요.

=== 패들릿 게시물 ===
{rag_context}
=== 게시물 끝 ==="""
    else:
        system_prompt += """

(참고: 현재 등록된 패들릿 데이터가 없거나 관련 내용을 찾을 수 없습니다.
일반적인 안내만 가능합니다.)"""

    # 채팅 기록 가져오기 (최근 10개만)
    chat_history = request.session.get('padlet_chat_history', [])[-10:]

    # 대화 히스토리 구성
    conversation = []
    for msg in chat_history:
        role = "user" if msg['role'] == 'user' else "model"
        conversation.append({"role": role, "parts": [{"text": msg['content']}]})

    # 현재 사용자 메시지 추가
    conversation.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        # Gemini API 호출
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=conversation,
            config={
                "system_instruction": system_prompt,
            }
        )

        ai_response = response.text

        # 채팅 기록 업데이트
        chat_history = request.session.get('padlet_chat_history', [])
        chat_history.append({'role': 'user', 'content': user_message})
        chat_history.append({'role': 'assistant', 'content': ai_response})
        request.session['padlet_chat_history'] = chat_history

        return JsonResponse({
            'success': True,
            'response': ai_response,
        })

    except Exception as e:
        logging.exception("AI 응답 생성 오류")
        return JsonResponse({
            'error': 'AI 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
        }, status=500)


# === 관리자 기능 ===

@staff_member_required
def manage_docs(request):
    """문서 관리 페이지 (관리자 전용)"""
    documents = PadletDocument.objects.all()

    if request.method == 'POST':
        form = PadletDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            # 파일 확장자로 file_type 설정
            if doc.file:
                ext = doc.file.name.split('.')[-1].lower()
                doc.file_type = 'csv' if ext == 'csv' else 'pdf'
            doc.save()
            messages.success(request, f'"{doc.title}" 문서가 업로드되었습니다.')
            return redirect('padlet_bot:manage_docs')
    else:
        form = PadletDocumentForm()

    return render(request, 'padlet_bot/manage_docs.html', {
        'documents': documents,
        'form': form,
    })


@staff_member_required
@require_POST
def process_document(request, pk):
    """문서 벡터DB 처리 (AJAX)"""
    doc = get_object_or_404(PadletDocument, pk=pk)

    try:
        rag = get_padlet_rag_service()
        if not rag:
            return JsonResponse({'error': 'RAG 서비스를 초기화할 수 없습니다.'}, status=500)

        # 파일 경로 가져오기
        file_path = doc.file.path

        # 벡터DB에 추가
        chunk_count = rag.add_document(
            doc_id=doc.pk,
            file_path=file_path,
            title=doc.title,
            file_type=doc.file_type
        )

        if chunk_count > 0:
            doc.is_processed = True
            doc.chunk_count = chunk_count
            doc.save()
            return JsonResponse({
                'success': True,
                'message': f'{chunk_count}개의 청크로 처리되었습니다.',
                'chunk_count': chunk_count
            })
        else:
            return JsonResponse({
                'error': '텍스트를 추출할 수 없습니다. 파일 형식을 확인해주세요.'
            }, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_POST
def delete_document(request, pk):
    """문서 삭제 (AJAX)"""
    doc = get_object_or_404(PadletDocument, pk=pk)

    try:
        # 벡터DB에서 삭제
        if doc.is_processed:
            rag = get_padlet_rag_service()
            if rag:
                rag.delete_document(doc.pk)

        # 파일 삭제
        if doc.file:
            doc.file.delete(save=False)

        title = doc.title
        doc.delete()

        return JsonResponse({
            'success': True,
            'message': f'"{title}" 문서가 삭제되었습니다.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# === 패들릿 API 연동 기능 ===

@staff_member_required
def api_connect(request):
    """패들릿 API 연동 페이지"""
    linked_boards = LinkedPadletBoard.objects.all()
    api_configured = is_padlet_api_configured()

    return render(request, 'padlet_bot/api_connect.html', {
        'linked_boards': linked_boards,
        'api_configured': api_configured,
    })


@staff_member_required
@require_POST
def link_padlet(request):
    """패들릿 URL로 보드 연동 (AJAX)"""
    padlet_url = request.POST.get('padlet_url', '').strip()

    if not padlet_url:
        return JsonResponse({'error': '패들릿 URL을 입력해주세요.'}, status=400)

    if not is_padlet_api_configured():
        return JsonResponse({'error': 'PADLET_API_KEY가 설정되지 않았습니다.'}, status=400)

    try:
        client = get_padlet_client()
        if not client:
            return JsonResponse({'error': '패들릿 API 클라이언트를 초기화할 수 없습니다.'}, status=500)

        # 보드 ID 추출
        board_id = PadletAPIClient.extract_board_id_from_url(padlet_url)
        if not board_id:
            return JsonResponse({'error': '유효한 패들릿 URL이 아닙니다.'}, status=400)

        # 이미 연동된 보드인지 확인
        if LinkedPadletBoard.objects.filter(board_id=board_id).exists():
            return JsonResponse({'error': '이미 연동된 패들릿입니다.'}, status=400)

        # 패들릿 데이터 가져오기
        board = client.fetch_board_with_posts(board_id)

        # DB에 저장
        linked_board = LinkedPadletBoard.objects.create(
            board_id=board_id,
            board_url=padlet_url,
            title=board.title,
            description=board.description,
            post_count=len(board.posts),
            linked_by=request.user,
            last_synced=timezone.now(),
        )

        return JsonResponse({
            'success': True,
            'message': f'"{board.title}" 패들릿이 연동되었습니다. ({len(board.posts)}개 게시물)',
            'board_id': linked_board.pk,
            'title': board.title,
            'post_count': len(board.posts),
        })

    except Exception as e:
        import logging
        logging.exception("패들릿 연동 오류")
        return JsonResponse({'error': f'연동 실패: {str(e)}'}, status=500)


@staff_member_required
@require_POST
def sync_padlet(request, pk):
    """패들릿 동기화 및 벡터DB 처리 (AJAX)"""
    board = get_object_or_404(LinkedPadletBoard, pk=pk)

    if not is_padlet_api_configured():
        return JsonResponse({'error': 'PADLET_API_KEY가 설정되지 않았습니다.'}, status=400)

    try:
        client = get_padlet_client()
        if not client:
            return JsonResponse({'error': '패들릿 API 클라이언트를 초기화할 수 없습니다.'}, status=500)

        # 패들릿 데이터 가져오기
        padlet_board = client.fetch_board_with_posts(board.board_id)

        # 텍스트로 변환
        text = client.posts_to_text(padlet_board)

        if not text:
            return JsonResponse({'error': '게시물 내용을 가져올 수 없습니다.'}, status=400)

        # RAG 서비스에 추가
        rag = get_padlet_rag_service()
        if not rag:
            return JsonResponse({'error': 'RAG 서비스를 초기화할 수 없습니다.'}, status=500)

        # 기존 청크 삭제 (linked_ 접두사로 구분)
        try:
            results = rag.collection.get(
                where={"doc_id": f"linked_{board.pk}"}
            )
            if results['ids']:
                rag.collection.delete(ids=results['ids'])
        except Exception:
            pass

        # 청크 분할 및 추가
        chunks = chunk_text(text)
        if not chunks:
            return JsonResponse({'error': '텍스트를 청크로 분할할 수 없습니다.'}, status=400)

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"linked_{board.pk}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "doc_id": f"linked_{board.pk}",
                "title": padlet_board.title,
                "source": "api",
                "chunk_index": i,
            })

        rag.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        # DB 업데이트
        board.title = padlet_board.title
        board.description = padlet_board.description
        board.post_count = len(padlet_board.posts)
        board.is_processed = True
        board.chunk_count = len(chunks)
        board.last_synced = timezone.now()
        board.save()

        return JsonResponse({
            'success': True,
            'message': f'{len(chunks)}개의 청크로 처리되었습니다. ({len(padlet_board.posts)}개 게시물)',
            'chunk_count': len(chunks),
            'post_count': len(padlet_board.posts),
        })

    except Exception as e:
        import logging
        logging.exception("패들릿 동기화 오류")
        return JsonResponse({'error': f'동기화 실패: {str(e)}'}, status=500)


@staff_member_required
@require_POST
def unlink_padlet(request, pk):
    """패들릿 연동 해제 (AJAX)"""
    board = get_object_or_404(LinkedPadletBoard, pk=pk)

    try:
        # 벡터DB에서 삭제
        if board.is_processed:
            rag = get_padlet_rag_service()
            if rag:
                try:
                    results = rag.collection.get(
                        where={"doc_id": f"linked_{board.pk}"}
                    )
                    if results['ids']:
                        rag.collection.delete(ids=results['ids'])
                except Exception:
                    pass

        title = board.title
        board.delete()

        return JsonResponse({
            'success': True,
            'message': f'"{title}" 연동이 해제되었습니다.'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
