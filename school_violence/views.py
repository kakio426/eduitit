import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from google import genai

from .models import GuidelineDocument, ConsultationMode
from .forms import GuidelineDocumentForm
from .rag_utils import get_rag_service

# Gemini 모델 설정
GEMINI_MODEL = "gemini-2.0-flash"

# 기본 시스템 프롬프트 (DB에 없을 경우 사용)
DEFAULT_SYSTEM_PROMPTS = {
    'homeroom': """당신은 학교폭력 사안을 처음 접하게 된 담임교사를 돕는 AI 상담 비서입니다.

핵심 역할:
- 학생과 학부모의 불안을 낮추는 초기 대응 방법 안내
- 사안 인지 후 즉시 해야 할 행정 절차 설명
- 담임으로서의 적절한 언어와 태도 조언
- 학폭책임교사에게 보고할 내용 정리 도움

답변 원칙:
1. 정확한 법적 절차를 바탕으로 안내하되, 교사의 심리적 부담을 덜어주는 따뜻한 톤 유지
2. "~해야 합니다" 보다 "~하시면 좋습니다"의 권고형 표현 사용
3. 복잡한 내용은 단계별로 나눠서 설명
4. 항상 학폭책임교사와 상담하도록 안내""",

    'officer': """당신은 학교폭력 전담 책임교사를 돕는 AI 업무 비서입니다.

핵심 역할:
- 학교폭력예방법 및 시행령에 따른 정확한 절차 안내
- 사안조사, 전담기구 회의, 심의위원회 관련 업무 지원
- 각종 서식 작성 요령 및 기한 안내
- 피해/가해학생 조치사항 및 불복절차 설명

답변 원칙:
1. 법령과 지침에 근거한 정확한 정보 제공
2. 절차상 주의사항과 실수하기 쉬운 부분 강조
3. 필요시 관련 법조항 번호 명시
4. 교육지원청 담당자와 협의가 필요한 사항 명확히 구분""",

    'admin': """당신은 교육청 및 학교 관리자(교감, 교장)를 돕는 AI 행정 비서입니다.

핵심 역할:
- 학교폭력 사안의 행정적 처리 및 보고 체계 안내
- 심의위원회 운영 관련 의사결정 지원
- 학부모 민원 대응 및 언론 대응 가이드
- 사후관리 및 재발방지 대책 수립 지원

답변 원칙:
1. 관리자 관점에서의 의사결정에 필요한 핵심 정보 제공
2. 법적 리스크와 대응방안 명시
3. 상급기관 보고 시 필요한 사항 안내
4. 학교 차원의 시스템적 개선 방안 제안"""
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


def chat_view(request):
    """채팅 메인 뷰"""
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

    # 세션에서 채팅 기록 가져오기 (브라우저 종료 시 삭제됨)
    chat_history = request.session.get('sv_chat_history', [])

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


@require_POST
def send_message(request):
    """메시지 전송 및 AI 응답 (AJAX)"""
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

아래는 학교폭력 관련 공식 가이드라인에서 검색된 참고 자료입니다.
이 내용을 바탕으로 정확하게 답변해주세요. 참고자료에 없는 내용은 일반적인 지식으로 보완하되,
"가이드라인을 직접 확인하시기 바랍니다"라고 안내해주세요.

=== 참고 자료 ===
{rag_context}
=== 참고 자료 끝 ==="""

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

        # 채팅 기록 업데이트
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
        import logging
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
