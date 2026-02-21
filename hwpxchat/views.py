import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from products.models import Product

from .utils.hwpx_parser import HwpxParseError, parse_hwpx_to_markdown
from .utils.llm_client import LlmClientError, generate_chat_response

logger = logging.getLogger(__name__)

SERVICE_TITLE = "한글문서 AI야 읽어줘"
LEGACY_SERVICE_TITLES = (
    "한글 문서 톡톡",
    "HWPX 문서 AI 대화",
)

HWPX_SESSION_CONTEXT_KEY = "hwpxchat_markdown_context"
HWPX_SESSION_MESSAGES_KEY = "hwpxchat_messages"
HWPX_SESSION_PROVIDER_KEY = "hwpxchat_provider"
MAX_HWPX_CONTEXT_LENGTH = 50000
MAX_HWPX_CHAT_MESSAGES = 12


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="hwpxchat:main").first()


@login_required
def main(request):
    return render(
        request,
        "hwpxchat/main.html",
        {
            "service": _get_service(),
            "messages": _get_chat_messages(request),
            "has_document_context": bool(request.session.get(HWPX_SESSION_CONTEXT_KEY)),
            "selected_provider": request.session.get(HWPX_SESSION_PROVIDER_KEY, "gemini"),
        },
    )


@login_required
@require_POST
def chat_process(request):
    question = (request.POST.get("question", "") or "").strip()
    provider = (request.POST.get("provider", "gemini") or "gemini").strip().lower()
    uploaded_file = request.FILES.get("hwpx_file")

    if uploaded_file and uploaded_file.name.lower().endswith(".hwp"):
        return _render_result(
            request,
            error_message="HWP 파일은 지원하지 않습니다. HWPX로 변환해서 업로드해 주세요.",
            provider=provider,
        )

    if uploaded_file and not uploaded_file.name.lower().endswith(".hwpx"):
        return _render_result(
            request,
            error_message="HWPX 파일만 업로드할 수 있습니다.",
            provider=provider,
        )

    if uploaded_file:
        try:
            markdown_context = parse_hwpx_to_markdown(uploaded_file)
            request.session[HWPX_SESSION_CONTEXT_KEY] = markdown_context[:MAX_HWPX_CONTEXT_LENGTH]
            request.session[HWPX_SESSION_MESSAGES_KEY] = []
        except HwpxParseError as e:
            logger.error(f"[hwpxchat] Action: PARSE_HWPX, Status: FAIL, Reason: {e}")
            return _render_result(
                request,
                error_message="HWPX 파싱에 실패했습니다. 파일 형식을 확인한 뒤 다시 시도해 주세요.",
                provider=provider,
            )
        except Exception as e:
            logger.error(f"[hwpxchat] Action: PARSE_HWPX, Status: FAIL, Reason: {e}")
            return _render_result(
                request,
                error_message="문서 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                provider=provider,
            )

    context_markdown = request.session.get(HWPX_SESSION_CONTEXT_KEY, "")
    if not context_markdown:
        return _render_result(
            request,
            error_message="먼저 HWPX 파일을 업로드해 주세요.",
            provider=provider,
        )

    if not question:
        return _render_result(
            request,
            error_message="질문을 입력해 주세요.",
            provider=provider,
        )

    chat_messages = _get_chat_messages(request)
    prompt = _build_prompt(
        document_markdown=context_markdown,
        messages=chat_messages,
        question=question,
    )

    try:
        ai_answer = generate_chat_response(
            provider=provider,
            prompt=prompt,
            user=request.user,
        )
    except LlmClientError as e:
        logger.error(f"[hwpxchat] Action: CALL_LLM, Status: FAIL, Reason: {e}")
        return _render_result(
            request,
            error_message="AI 응답을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.",
            provider=provider,
        )
    except Exception as e:
        logger.error(f"[hwpxchat] Action: CALL_LLM, Status: FAIL, Reason: {e}")
        return _render_result(
            request,
            error_message="AI 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            provider=provider,
        )

    chat_messages.append({"role": "user", "content": question})
    chat_messages.append({"role": "assistant", "content": ai_answer})
    chat_messages = chat_messages[-MAX_HWPX_CHAT_MESSAGES:]

    request.session[HWPX_SESSION_MESSAGES_KEY] = chat_messages
    request.session[HWPX_SESSION_PROVIDER_KEY] = provider

    info_message = "문서를 새로 업로드해 대화를 초기화했습니다." if uploaded_file else ""
    return _render_result(request, info_message=info_message, provider=provider)


@login_required
@require_POST
def chat_reset(request):
    request.session.pop(HWPX_SESSION_CONTEXT_KEY, None)
    request.session.pop(HWPX_SESSION_MESSAGES_KEY, None)
    request.session.pop(HWPX_SESSION_PROVIDER_KEY, None)
    return _render_result(
        request,
        info_message="문서 컨텍스트와 대화 기록을 초기화했습니다.",
    )


def _render_result(request, error_message="", info_message="", provider="gemini"):
    return render(
        request,
        "hwpxchat/partials/chat_result.html",
        {
            "messages": _get_chat_messages(request),
            "error_message": error_message,
            "info_message": info_message,
            "has_document_context": bool(request.session.get(HWPX_SESSION_CONTEXT_KEY)),
            "selected_provider": provider or request.session.get(HWPX_SESSION_PROVIDER_KEY, "gemini"),
        },
    )


def _get_chat_messages(request):
    messages = request.session.get(HWPX_SESSION_MESSAGES_KEY, [])
    if not isinstance(messages, list):
        return []

    normalized = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = (item.get("role", "") or "").strip()
        content = (item.get("content", "") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized[-MAX_HWPX_CHAT_MESSAGES:]


def _build_prompt(document_markdown, messages, question):
    recent_messages = messages[-6:]
    history_lines = []
    for msg in recent_messages:
        role_name = "사용자" if msg["role"] == "user" else "AI"
        history_lines.append(f"{role_name}: {msg['content']}")

    history_block = "\n".join(history_lines) if history_lines else "(이전 대화 없음)"

    return (
        "당신은 교사를 돕는 문서 분석 AI입니다.\n"
        "아래 HWPX 문서 내용을 우선 참고하고, 문서에 근거해 정확하게 답변해 주세요.\n"
        "근거가 부족한 내용은 추측하지 말고 부족하다고 명시해 주세요.\n\n"
        "[문서 내용 - Markdown]\n"
        f"{document_markdown}\n\n"
        "[이전 대화]\n"
        f"{history_block}\n\n"
        "[새 질문]\n"
        f"{question}\n"
    )
