(function () {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setElementText(element, text) {
    if (!element) {
      return;
    }
    element.textContent = text || "";
  }

  function updatePreview(file) {
    var image = byId("ocrdesk-preview-image");
    var emptyState = byId("ocrdesk-preview-empty");
    var fileName = byId("ocrdesk-file-name");
    var previewAlert = byId("ocrdesk-preview-alert");

    if (!image || !emptyState || !fileName || !previewAlert) {
      return;
    }

    setElementText(previewAlert, "");

    if (!file) {
      image.src = "";
      image.classList.add("hidden");
      emptyState.classList.remove("hidden");
      setElementText(fileName, "아직 고른 사진이 없습니다.");
      return;
    }

    setElementText(fileName, file.name || "사진 1장 선택됨");

    if (!window.FileReader) {
      setElementText(previewAlert, "이 브라우저에서는 미리보기를 보여주지 못합니다. 바로 읽기는 가능합니다.");
      image.src = "";
      image.classList.add("hidden");
      emptyState.classList.remove("hidden");
      return;
    }

    var reader = new FileReader();
    reader.onload = function (event) {
      image.src = event.target && event.target.result ? event.target.result : "";
      image.classList.remove("hidden");
      emptyState.classList.add("hidden");
    };
    reader.onerror = function () {
      image.src = "";
      image.classList.add("hidden");
      emptyState.classList.remove("hidden");
      setElementText(previewAlert, "사진 미리보기를 불러오지 못했습니다. 다른 사진으로 다시 시도해 주세요.");
    };
    reader.readAsDataURL(file);
  }

  function bindPreviewInput() {
    var input = byId("ocrdesk-image-input");
    if (!input) {
      return;
    }

    input.addEventListener("change", function () {
      updatePreview(input.files && input.files.length ? input.files[0] : null);
    });

    updatePreview(input.files && input.files.length ? input.files[0] : null);
  }

  async function copyResult(targetSelector) {
    var textarea = document.querySelector(targetSelector || "#ocrdesk-result-text");
    var status = byId("ocrdesk-copy-status");

    if (!textarea) {
      setElementText(status, "복사할 글자를 아직 찾지 못했습니다.");
      return;
    }

    var value = textarea.value || "";
    if (!value.trim()) {
      setElementText(status, "복사할 글자가 비어 있습니다.");
      textarea.focus();
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      setElementText(status, "복사했습니다. 필요한 곳에 바로 붙여넣으면 됩니다.");
    } catch (error) {
      textarea.focus();
      textarea.select();
      setElementText(status, "복사에 실패했습니다. 글자를 직접 선택해서 복사해 주세요.");
      window.alert("복사에 실패했습니다. 글자를 직접 선택해서 복사해 주세요.");
    }
  }

  function bindActionButtons() {
    document.addEventListener("click", function (event) {
      var copyButton = event.target.closest("[data-ocrdesk-copy-btn]");
      if (copyButton) {
        event.preventDefault();
        void copyResult(copyButton.getAttribute("data-target"));
        return;
      }

      var pickerButton = event.target.closest("[data-ocrdesk-picker-btn]");
      if (pickerButton) {
        event.preventDefault();
        var input = byId("ocrdesk-image-input");
        if (input) {
          input.click();
        } else {
          window.alert("사진 선택 버튼을 찾지 못했습니다. 페이지를 다시 열어 주세요.");
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindPreviewInput();
    bindActionButtons();
  });
})();
