import json
import logging
from types import SimpleNamespace

from asgiref.sync import sync_to_async
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.core import is_ratelimited

from core.seo import build_fortune_chat_page_seo
from core.utils import ratelimit_key_for_master_only

from .models import FortuneResult
from .privacy import apply_private_fortune_headers, scrub_personal_fortune_text
from .utils.chat_ai import get_ai_response_stream
from .utils.chat_logic import build_system_prompt

logger = logging.getLogger(__name__)

MAX_CHAT_TURNS = 10


def _select_prior_general_results(user, limit=2):
    return list(
        FortuneResult.objects.filter(user=user, mode='general')
        .order_by('-created_at')
        .values('id', 'created_at', 'result_text')[:limit]
    )


def _parse_json_payload(raw_value, default):
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError):
        return default


def _normalize_history(history):
    normalized = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = (item.get('content') or '').strip()
        if role in {'user', 'assistant'} and content:
            normalized.append({'role': role, 'content': content})
    return normalized[-20:]


def _build_runtime_context(payload):
    if not isinstance(payload, dict):
        return None

    natal_chart = payload.get('natal_chart') or {}
    if not isinstance(natal_chart, dict) or not natal_chart.get('day'):
        return None

    return {
        'display_name': '선생님',
        'person_name': '선생님',
        'gender': payload.get('gender') or 'female',
        'mode': payload.get('mode') or 'teacher',
        'day_master': payload.get('day_master') or {},
        'natal_chart': natal_chart,
    }


def _render_inline_message(content):
    return SimpleNamespace(role='assistant', content=content, created_at=timezone.now())


@login_required
def chat_main_page(request):
    response = render(
        request,
        'fortune/chat_main.html',
        build_fortune_chat_page_seo(request).as_context(),
    )
    return apply_private_fortune_headers(response)


@login_required
@require_POST
def create_chat_session(request):
    return JsonResponse(
        {'success': False, 'error': '저장 프로필 기반 채팅은 종료되었습니다. 현재 탭의 분석 결과로만 상담할 수 있습니다.'},
        status=410,
    )


@login_required
async def send_chat_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    ratelimited = await sync_to_async(is_ratelimited)(
        request,
        group='fortune_chat',
        key=ratelimit_key_for_master_only,
        rate='20/d',
        method='POST',
        increment=True,
    )
    if ratelimited:
        return JsonResponse({'error': 'DAILY_LIMIT_EXCEEDED', 'message': '오늘 채팅 한도를 모두 사용했습니다.'}, status=429)

    content = request.POST.get('message', '').strip()
    if not content:
        return JsonResponse({'error': 'Message required'}, status=400)

    working_context = _build_runtime_context(_parse_json_payload(request.POST.get('working_context_json'), {}))
    if not working_context:
        return JsonResponse({'error': 'WORKING_CONTEXT_REQUIRED', 'message': '현재 분석 결과가 없어 상담을 시작할 수 없습니다.'}, status=400)

    history = _normalize_history(_parse_json_payload(request.POST.get('history_json'), []))
    used_turns = sum(1 for item in history if item.get('role') == 'user')
    if used_turns >= MAX_CHAT_TURNS:
        return await sync_to_async(render)(
            request,
            'fortune/partials/chat_message.html',
            {'message': _render_inline_message('오늘 상담 한도를 모두 사용했습니다. 새 분석 결과로 다시 시작해주세요!')},
        )

    prior_general_results = await sync_to_async(_select_prior_general_results)(request.user, 2)
    system_prompt = build_system_prompt(working_context, working_context['natal_chart'], prior_general_results)
    remaining_turns = max(0, MAX_CHAT_TURNS - (used_turns + 1))

    async def stream_response():
        full_response_parts = []
        yield """
<div class="flex flex-col space-y-2 mb-6 w-full animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div class="flex items-start gap-3 self-start max-w-[90%] mr-auto">
        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-white text-lg shadow-lg shrink-0 border border-white/20 relative top-1">
            🧙\u200d♂️
        </div>
        <div class="chat-ai-content glass-card p-5 rounded-tl-none bg-white/5 text-gray-100 leading-relaxed shadow-lg backdrop-blur-md border border-white/10 relative group prose prose-invert prose-p:my-1 prose-headings:text-purple-300 prose-strong:text-yellow-400 break-words whitespace-pre-wrap">
"""
        async for chunk in get_ai_response_stream(system_prompt, history, content):
            full_response_parts.append(chunk['plain'])
            yield chunk['html']

        assistant_text = ''.join(full_response_parts).strip()
        yield """
            <span class="text-[10px] text-gray-400 mt-2 block opacity-0 group-hover:opacity-100 transition-opacity absolute bottom-1 left-4">Now</span>
        </div>
    </div>
</div>
"""
        yield f"""
<script>
    if (window.FortuneChat) {{
        window.FortuneChat.recordExchange({json.dumps(content, ensure_ascii=False)}, {json.dumps(assistant_text, ensure_ascii=False)}, {remaining_turns});
    }}
    if (window.ChatUX) {{
        window.ChatUX.scrollToBottom(false);
    }}
</script>
"""

    logger.info(
        "[Fortune] Action: CHAT_STREAM, Status: STARTED, User: %s, UsedTurns: %s",
        request.user.username,
        used_turns,
    )
    return StreamingHttpResponse(stream_response(), content_type='text/html')


@login_required
@require_POST
def save_chat_to_history(request):
    working_context = _build_runtime_context(_parse_json_payload(request.POST.get('working_context_json'), {}))
    history = _normalize_history(_parse_json_payload(request.POST.get('history_json'), []))

    if not working_context or not history:
        return JsonResponse({'status': 'error', 'message': '저장할 상담 내용이 없습니다.'}, status=400)

    mode = working_context.get('mode')
    if mode not in {'teacher', 'general', 'daily'}:
        mode = 'teacher'

    markdown_content = "# 사주 상담 기록\n\n"
    for msg in history:
        role = "Teacher" if msg['role'] == 'assistant' else "Student"
        content = msg['content'].replace('\n', '\n> ')
        markdown_content += f"**{role}**: {content}\n\n"

    sanitized_content = scrub_personal_fortune_text(markdown_content)
    if not sanitized_content:
        return JsonResponse({'status': 'error', 'message': '저장 가능한 상담 내용이 없습니다.'}, status=400)

    saved_result = FortuneResult.objects.create(
        user=request.user,
        mode=mode,
        result_text=sanitized_content,
        target_date=None,
    )

    logger.info("[Fortune] Action: CHAT_SAVE, Status: SUCCESS, User: %s, ResultID: %s", request.user.username, saved_result.id)
    return JsonResponse({'status': 'success', 'message': 'Saved to history', 'result_id': saved_result.id})
