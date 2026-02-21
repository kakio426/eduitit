import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from products.models import Product

from .utils.hwpx_parser import HwpxParseError, parse_hwpx_to_markdown

logger = logging.getLogger(__name__)

SERVICE_TITLE = "한글문서 AI야 읽어줘"
LEGACY_SERVICE_TITLES = (
    "한글 문서 톡톡",
    "HWPX 문서 AI 대화",
)

HWPX_SESSION_MARKDOWN_KEY = "hwpxchat_markdown_output"
MAX_HWPX_MARKDOWN_LENGTH = 120000


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
    markdown_output = request.session.get(HWPX_SESSION_MARKDOWN_KEY, "")
    return render(
        request,
        "hwpxchat/main.html",
        {
            "service": _get_service(),
            "markdown_output": markdown_output,
            "has_markdown_output": bool(markdown_output),
        },
    )


@login_required
@require_POST
def chat_process(request):
    uploaded_file = request.FILES.get("hwpx_file")

    if uploaded_file and uploaded_file.name.lower().endswith(".hwp"):
        return _render_result(
            request,
            error_message="HWP 파일은 지원하지 않습니다. HWPX로 변환해서 업로드해 주세요.",
        )

    if not uploaded_file:
        return _render_result(
            request,
            error_message="HWPX 파일을 업로드해 주세요.",
        )

    if not uploaded_file.name.lower().endswith(".hwpx"):
        return _render_result(
            request,
            error_message="HWPX 파일만 업로드할 수 있습니다.",
        )

    try:
        markdown_output = parse_hwpx_to_markdown(uploaded_file)
    except HwpxParseError as e:
        logger.error(f"[hwpxchat] Action: PARSE_HWPX, Status: FAIL, Reason: {e}")
        return _render_result(
            request,
            error_message="HWPX 파싱에 실패했습니다. 파일 형식을 확인한 뒤 다시 시도해 주세요.",
        )
    except Exception as e:
        logger.error(f"[hwpxchat] Action: PARSE_HWPX, Status: FAIL, Reason: {e}")
        return _render_result(
            request,
            error_message="문서 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )

    request.session[HWPX_SESSION_MARKDOWN_KEY] = markdown_output[:MAX_HWPX_MARKDOWN_LENGTH]
    return _render_result(
        request,
        info_message=(
            "변환 완료. 아래 Markdown을 복사해서 Gemini/Claude/ChatGPT 같은 "
            "원하는 LLM 사이트에 붙여 넣고 질문하세요."
        ),
    )


@login_required
@require_POST
def chat_reset(request):
    request.session.pop(HWPX_SESSION_MARKDOWN_KEY, None)
    return _render_result(
        request,
        info_message="변환 결과를 초기화했습니다.",
    )


def _render_result(request, error_message="", info_message=""):
    markdown_output = request.session.get(HWPX_SESSION_MARKDOWN_KEY, "")
    return render(
        request,
        "hwpxchat/partials/chat_result.html",
        {
            "error_message": error_message,
            "info_message": info_message,
            "markdown_output": markdown_output,
            "has_markdown_output": bool(markdown_output),
        },
    )
