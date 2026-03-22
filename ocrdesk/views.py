import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import OCRImageUploadForm
from .services import OCRProcessingError, OCREngineUnavailable, extract_text_from_upload, get_service


logger = logging.getLogger(__name__)


def _apply_workspace_cache_headers(response):
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _build_page_context(*, form, result_text="", result_error="", result_notice="", ocr_attempted=False):
    return {
        "service": get_service(),
        "form": form,
        "result_text": result_text,
        "result_error": result_error,
        "result_notice": result_notice,
        "ocr_attempted": ocr_attempted,
        "page_title": "사진 글자 읽기 - Eduitit",
    }


@login_required
@require_http_methods(["GET", "POST"])
def main(request):
    result_text = ""
    result_error = ""
    result_notice = ""
    ocr_attempted = False

    if request.method == "POST":
        form = OCRImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            ocr_attempted = True
            uploaded_image = form.cleaned_data["image"]
            try:
                result_text = extract_text_from_upload(uploaded_image)
            except OCREngineUnavailable:
                result_error = "OCR 엔진을 준비하지 못했습니다. 서버 설정을 확인한 뒤 다시 시도해 주세요."
            except OCRProcessingError:
                result_error = "사진을 읽는 중 문제가 생겼습니다. 글씨가 선명하게 보이도록 다시 찍어 보세요."
            except Exception:
                logger.exception("[ocrdesk] unexpected OCR error")
                result_error = "사진을 읽는 중 문제가 생겼습니다. 글씨가 선명하게 보이도록 다시 찍어 보세요."
            else:
                if not result_text:
                    result_notice = "사진에서 읽은 글자를 찾지 못했습니다. 글씨가 더 크게 보이도록 다시 찍어 보세요."
        else:
            logger.info("[ocrdesk] upload validation failed")
    else:
        form = OCRImageUploadForm()

    context = _build_page_context(
        form=form,
        result_text=result_text,
        result_error=result_error,
        result_notice=result_notice,
        ocr_attempted=ocr_attempted,
    )

    template_name = "ocrdesk/partials/result_panel_response.html" if getattr(request, "htmx", False) else "ocrdesk/main.html"
    return _apply_workspace_cache_headers(render(request, template_name, context))
