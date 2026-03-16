import os
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from core.utils import ratelimit_key_for_master_only
from google import genai

from .models import GuidelineDocument, ConsultationMode
from .forms import GuidelineDocumentForm
from .rag_utils import get_rag_service

# Gemini 모델 설정
# RAG 기반 문서 검색 → 중간급 2.5 Flash
GEMINI_MODEL = "gemini-2.5-flash"

# 기본 시스템 프롬프트 (DB에 없을 경우 사용)
DEFAULT_SYSTEM_PROMPTS = {
    'homeroom': """당신은 학교폭력 사안을 접한 담임교사를 돕는 'AI 업무 가이드'입니다.

[핵심 역할]
- 담임교사가 당장 취해야 할 **구체적인 행동**과 **절차**를 안내
- 감정적인 위로보다는 실질적인 행정 절차와 대응법을 간결하게 제시

[답변 가이드라인]
1. **수신자**: 답변을 읽는 사람은 '교사'입니다. 학부모에게 보내는 편지 형식을 사용하지 마세요. (사용자가 명시적으로 요청한 경우 제외)
2. **간결성(Token Saving)**: 불필요한 미사여구를 제거하고, 핵심 내용을 개조식( bullet points)으로 전달하세요.
3. **행동 중심**: "무엇을 해야 하는가"에 집중하여 1, 2, 3 단계별 행동 지침을 제공하세요.
4. **학부모 응대 팁**: 학부모가 요구하는 상황이라면, 교사가 학부모에게 어떤 멘트로 응대해야 할지 '예시 멘트'를 별도 박스로 제시하세요.

[예시]
❌ 잘못된 예: 부모님 안녕하세요, 마음이 많이 힘드시죠. 학교폭력은...
✅ 올바른 예:
1. 즉시 학교장 보고 및 학폭 접수 대장 기록 (필수)
2. 학부모 상담 시 멘트 가이드: "어머님, 학교 규정상 신고 접수가 원칙입니다만..."
""",

    'officer': """당신은 학교폭력 전담 책임교사를 돕는 '법률 및 절차 가이드'입니다.

[핵심 역할]
- 사안조사, 전담기구 운영, 심의위원회 관련 실무 절차 안내
- 법령(학교폭력예방법)에 근거한 정확하고 드라이한 답변 제공

[답변 원칙]
1. **정확성**: 법적 절차와 기한(48시간 이내 보고 등)을 정확히 명시하세요.
2. **객관성**: 감정을 배제하고 행정적 판단 기준을 제시하세요.
3. **구조화**: 긴 줄글 대신 번호 매기기를 통해 가독성을 높이세요.
4. **API 효율성**: 질문에 대한 직답만 빠르게 제공하여 토큰 소모를 줄이세요.""",

    'admin': """당신은 교육청 및 학교 관리자(교감, 교장)를 돕는 '의사결정 지원 시스템'입니다.

[핵심 역할]
- 민원 대응 전략, 사안 은폐/축소 금지 원칙 안내
- 심의위원회 요청 승인 및 학교장 자체해결 요건 검토

[답변 원칙]
1. **리스크 관리**: 법적 분쟁 가능성과 관리자의 책임 범위를 명확히 하세요.
2. **핵심 요약**: 보고서 형식으로 '현황 - 쟁점 - 대응방안' 순으로 요약하세요.
3. **간결성**: 장황한 설명 보다는 핵심 포인트만 짚어서 전달하세요."""
}


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


def get_system_prompt(mode_key: str) -> str:
    """모드별 시스템 프롬프트 가져오기"""
    try:
        mode = ConsultationMode.objects.get(mode_key=mode_key, is_active=True)
        return mode.system_prompt
    except ConsultationMode.DoesNotExist:
        return DEFAULT_SYSTEM_PROMPTS.get(mode_key, DEFAULT_SYSTEM_PROMPTS['homeroom'])


@ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='GET', block=True)
def chat_view(request):
    """채팅 메인 뷰 (Guest: 3/h, Member: 10/h)"""
    if getattr(request, 'limited', False):
         # 메시지 대신 템플릿 내에서 한도 도달 안내를 보여줄 수도 있지만, 여기서는 일반 페이지 노출
         pass
    # 세션에서 현재 모드 가져오기 (기본: 담임교사 모드)
    current_mode = request.session.get('sv_mode', 'homeroom')

    # 모드 목록 가져오기
    modes = list(ConsultationMode.objects.filter(is_active=True).values(
        'mode_key', 'display_name', 'description', 'icon', 'color'
    ))

    # DB에 모드가 없으면 기본값 사용
    if not modes:
        modes = [
            {'mode_key': 'homeroom', 'display_name': '담임교사 모드',
             'description': '초기 대응 및 학부모 상담', 'icon': 'fa-solid fa-chalkboard-user', 'color': 'blue'},
            {'mode_key': 'officer', 'display_name': '학폭책임교사 모드',
             'description': '절차 및 서식 안내', 'icon': 'fa-solid fa-user-shield', 'color': 'purple'},
            {'mode_key': 'admin', 'display_name': '교육청/행정 모드',
             'description': '관리자 의사결정 지원', 'icon': 'fa-solid fa-building-columns', 'color': 'green'},
        ]

    # 채팅 기록 가져오기 (회원: DB, 비회원: Session)
    if request.user.is_authenticated:
        from .models import ChatSession
        chat_history = []
        # 현재 모드의 가장 최근 세션 가져오기
        session = ChatSession.objects.filter(user=request.user, mode=current_mode).first()
        if session:
            messages = session.messages.all()[:50] # 최근 50개
            for msg in messages:
                chat_history.append({'role': msg.role, 'content': msg.content})
    else:
        chat_history = request.session.get('sv_chat_history', [])[-50:]

    return render(request, 'school_violence/chat.html', {
        'modes': modes,
        'current_mode': current_mode,
        'chat_history': chat_history,
    })


def set_mode(request):
    """모드 변경 (AJAX)"""
    if request.method == 'POST':
        mode = request.POST.get('mode', 'homeroom')
        if mode in ['homeroom', 'officer', 'admin']:
            request.session['sv_mode'] = mode
            # 모드 변경 시 채팅 기록 초기화 (선택적)
            request.session['sv_chat_history'] = []
            return JsonResponse({'success': True, 'mode': mode})

    return JsonResponse({'success': False}, status=400)


def clear_chat(request):
    """채팅 기록 삭제 (AJAX)"""
    if request.method == 'POST':
        request.session['sv_chat_history'] = []
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@ratelimit(key=ratelimit_key_for_master_only, rate='5/h', method='POST', block=True)
@ratelimit(key=ratelimit_key_for_master_only, rate='10/d', method='POST', block=True)
@require_POST
def send_message(request):
    """상담 메시지 전송 및 AI 응답 (통합 한도: 5/h, 10/d)"""
    if getattr(request, 'limited', False):
        return JsonResponse({
            'error': 'LIMIT_EXCEEDED',
            'message': '선생님, 현재 공용 AI 한도가 모두 사용 중입니다. [내 설정]에서 개인 Gemini API 키를 등록하시면 계속해서 상담을 이어가실 수 있습니다.'
        }, status=429)
    user_message = request.POST.get('message', '').strip()

    if not user_message:
        return JsonResponse({'error': '메시지를 입력해주세요.'}, status=400)

    # 현재 모드 가져오기
    current_mode = request.session.get('sv_mode', 'homeroom')

    # Gemini 클라이언트 가져오기
    client = get_gemini_client(request)
    if not client:
        return JsonResponse({
            'error': 'API 키가 설정되지 않았습니다. 설정 페이지에서 Gemini API 키를 등록해주세요.'
        }, status=400)

    # RAG 컨텍스트 가져오기
    rag_context = ""
    try:
        rag = get_rag_service()
        if rag:
            rag_context = rag.get_context_for_query(user_message, n_results=3)
    except Exception as e:
        print(f"[WARNING] RAG 검색 실패: {e}")

    # 시스템 프롬프트 구성
    system_prompt = get_system_prompt(current_mode)

    if rag_context:
        system_prompt += f"""

[참고 자료(공식 가이드라인)]
{rag_context}

[지시사항]
위 참고 자료를 바탕으로 교사가 취해야 할 조치를 **핵심만 요약**해서 답변하세요.
서론/본론/결론의 긴 형식을 피하고, **행동 지침(Action Item)** 위주로 작성하세요.
자료에 없는 내용은 "가이드라인 확인 필요"라고 짧게 언급하세요.
"""

    # 채팅 기록 가져오기 (최근 10개만 컨텍스트에 포함)
    chat_history = request.session.get('sv_chat_history', [])[-10:]

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

        # 회원/비회원 분기 처리: 기록 저장
        if request.user.is_authenticated:
            from .models import ChatSession, ChatMessage
            
            # 현재 세션 가져오기 또는 생성 (가장 최근 세션 사용)
            session = ChatSession.objects.filter(user=request.user, mode=current_mode).first()
            if not session:
                session = ChatSession.objects.create(
                    user=request.user, 
                    mode=current_mode,
                    topic=user_message[:50] + "..." if len(user_message) > 50 else user_message
                )
            
            # 메시지 저장
            ChatMessage.objects.create(session=session, role='user', content=user_message)
            ChatMessage.objects.create(session=session, role='assistant', content=ai_response)
        
        # 세션(Cookie) 업데이트 (비회원/회원 공통 UI 표시용)
        chat_history = request.session.get('sv_chat_history', [])
        chat_history.append({'role': 'user', 'content': user_message})
        chat_history.append({'role': 'assistant', 'content': ai_response})
        request.session['sv_chat_history'] = chat_history

        return JsonResponse({
            'success': True,
            'response': ai_response,
            'mode': current_mode
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
    documents = GuidelineDocument.objects.all()

    if request.method == 'POST':
        form = GuidelineDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, f'"{doc.title}" 문서가 업로드되었습니다.')
            return redirect('school_violence:manage_docs')
    else:
        form = GuidelineDocumentForm()

    return render(request, 'school_violence/manage_docs.html', {
        'documents': documents,
        'form': form,
    })


@staff_member_required
@require_POST
def process_document(request, pk):
    """문서 벡터DB 처리 (AJAX)"""
    doc = get_object_or_404(GuidelineDocument, pk=pk)

    try:
        rag = get_rag_service()
        if not rag:
            return JsonResponse({'error': 'RAG 서비스를 초기화할 수 없습니다.'}, status=500)

        # 파일 경로 가져오기
        file_path = doc.file.path

        # 벡터DB에 추가
        chunk_count = rag.add_document(
            doc_id=doc.pk,
            file_path=file_path,
            title=doc.title,
            category=doc.category
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
    doc = get_object_or_404(GuidelineDocument, pk=pk)

    try:
        # 벡터DB에서 삭제
        if doc.is_processed:
            rag = get_rag_service()
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
