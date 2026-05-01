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
    if (element.id === "ocrdesk-preview-alert") {
      element.dataset.ocrdeskInlineError = "";
    }
  }

  function setInlineError(element, text) {
    if (!element) {
      return;
    }
    element.textContent = text || "";
    element.dataset.ocrdeskInlineError = text ? "true" : "";
  }

  function getState() {
    return {
      shell: byId("ocrdesk-shell"),
      form: byId("ocrdesk-form"),
      input: byId("ocrdesk-image-input"),
      dropzone: byId("ocrdesk-dropzone"),
      dropzoneTitle: byId("ocrdesk-dropzone-title"),
      dropzoneHelp: byId("ocrdesk-dropzone-help"),
      submitButton: byId("ocrdesk-submit-button"),
      image: byId("ocrdesk-preview-image"),
      emptyState: byId("ocrdesk-preview-empty"),
      fileName: byId("ocrdesk-file-name"),
      previewAlert: byId("ocrdesk-preview-alert"),
    };
  }

  function updateDropzoneCopy(hasFile) {
    var state = getState();
    if (!state.dropzoneTitle || !state.dropzoneHelp) {
      return;
    }

    if (hasFile) {
      setElementText(state.dropzoneTitle, "사진 선택됨");
      setElementText(state.dropzoneHelp, "다시 고르기 가능");
      return;
    }

    setElementText(state.dropzoneTitle, "여기에 사진을 놓거나 눌러서 고르세요");
    setElementText(state.dropzoneHelp, "사진 넣기");
  }

  function setDropzoneState(options) {
    var state = getState();
    if (!state.dropzone) {
      return;
    }

    var dragging = Boolean(options && options.dragging);
    var hasFile = Boolean(options && options.hasFile);

    state.dropzone.dataset.dragging = dragging ? "true" : "false";
    state.dropzone.dataset.hasFile = hasFile ? "true" : "false";
    updateDropzoneCopy(hasFile);
  }

  function clearFormErrors() {
    var formErrors = byId("ocrdesk-form-errors");
    if (formErrors) {
      formErrors.innerHTML = "";
    }
  }

  function syncSubmitState() {
    var state = getState();
    if (!state.submitButton || !state.input) {
      return;
    }
    state.submitButton.disabled = !(state.input.files && state.input.files.length);
  }

  function isSupportedImage(file) {
    if (!file) {
      return false;
    }

    var name = String(file.name || "").toLowerCase();
    var hasImageType = String(file.type || "").toLowerCase().indexOf("image/") === 0;
    var hasAllowedName = /\.(jpe?g|png|webp)$/i.test(name);
    return hasImageType && hasAllowedName;
  }

  function focusResultPanel() {
    var panel = byId("ocrdesk-result-panel");
    if (!panel) {
      return;
    }

    panel.scrollIntoView({ behavior: "smooth", block: "start" });

    var textarea = byId("ocrdesk-result-text");
    if (textarea) {
      textarea.focus({ preventScroll: true });
      return;
    }

    panel.focus({ preventScroll: true });
  }

  function markResultPending() {
    var panel = byId("ocrdesk-result-panel");
    if (panel) {
      panel.setAttribute("aria-busy", "true");
    }

    var state = getState();
    setElementText(state.previewAlert, "읽는 중");

    var emptyTitle = document.querySelector("#ocrdesk-result-panel [data-result-empty-title]");
    var emptyHelp = document.querySelector("#ocrdesk-result-panel [data-result-empty-help]");
    if (emptyTitle) {
      setElementText(emptyTitle, "읽는 중");
    }
    if (emptyHelp) {
      setElementText(emptyHelp, "잠시만");
    }
  }

  function clearBusyState() {
    var panel = byId("ocrdesk-result-panel");
    if (panel) {
      panel.removeAttribute("aria-busy");
    }
    var shell = byId("ocrdesk-shell");
    if (shell) {
      shell.dataset.loading = "false";
    }
  }

  function updatePreview(file) {
    var state = getState();
    if (!state.image || !state.emptyState || !state.fileName || !state.previewAlert) {
      return;
    }

    setElementText(state.previewAlert, "");

    if (!file) {
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      setElementText(state.fileName, "사진 없음");
      setElementText(state.previewAlert, "");
      setDropzoneState({ hasFile: false, dragging: false });
      syncSubmitState();
      return false;
    }

    if (!isSupportedImage(file)) {
      if (state.input) {
        state.input.value = "";
      }
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      setElementText(state.fileName, "사진 없음");
      setDropzoneState({ hasFile: false, dragging: false });
      syncSubmitState();
      setInlineError(state.previewAlert, "사진 확인");
      return false;
    }

    setElementText(state.fileName, file.name || "사진 1장 선택됨");
    setDropzoneState({ hasFile: true, dragging: false });
    syncSubmitState();
    clearFormErrors();

    if (!window.FileReader) {
      setElementText(state.previewAlert, "미리보기 없음");
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      return true;
    }

    var reader = new FileReader();
    reader.onload = function (event) {
      state.image.src = event.target && event.target.result ? event.target.result : "";
      state.image.classList.remove("hidden");
      state.emptyState.classList.add("hidden");
      setElementText(state.previewAlert, "읽기 준비");
    };
    reader.onerror = function () {
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      setElementText(state.previewAlert, "미리보기 실패");
    };
    reader.readAsDataURL(file);
    return true;
  }

  function submitForOCR() {
    var state = getState();
    if (!state.form || !state.input || !state.input.files || !state.input.files.length) {
      return;
    }

    if (!window.htmx) {
      return;
    }

    markResultPending();

    if (typeof state.form.requestSubmit === "function") {
      state.form.requestSubmit(state.submitButton || undefined);
      return;
    }

    state.form.submit();
  }

  function tryAssignDroppedFiles(fileList) {
    var state = getState();
    if (!state.input) {
      setInlineError(state.previewAlert, "사진 확인");
      return false;
    }

    try {
      state.input.files = fileList;
      return true;
    } catch (error) {
      setInlineError(state.previewAlert, "사진 확인");
      return false;
    }
  }

  function bindPreviewInput() {
    var state = getState();
    if (!state.input) {
      return;
    }

    state.input.addEventListener("change", function () {
      var file = state.input.files && state.input.files.length ? state.input.files[0] : null;
      var isReady = updatePreview(file);
      if (file && isReady) {
        submitForOCR();
      }
    });

    updatePreview(state.input.files && state.input.files.length ? state.input.files[0] : null);
  }

  function bindDropzone() {
    var state = getState();
    if (!state.dropzone || !state.input) {
      return;
    }

    state.dropzone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        state.input.click();
      }
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
      state.dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        setDropzoneState({ dragging: true, hasFile: state.input.files && state.input.files.length });
      });
    });

    ["dragleave", "dragend"].forEach(function (eventName) {
      state.dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        setDropzoneState({ dragging: false, hasFile: state.input.files && state.input.files.length });
      });
    });

    state.dropzone.addEventListener("drop", function (event) {
      event.preventDefault();
      var files = event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files : null;
      setDropzoneState({ dragging: false, hasFile: files && files.length });

      if (!files || !files.length) {
        return;
      }

      if (!tryAssignDroppedFiles(files)) {
        return;
      }

      if (updatePreview(files[0])) {
        submitForOCR();
      }
    });

    ["dragover", "drop"].forEach(function (eventName) {
      window.addEventListener(eventName, function (event) {
        if (event.dataTransfer && Array.prototype.indexOf.call(event.dataTransfer.types || [], "Files") !== -1) {
          event.preventDefault();
        }
      });
    });
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
      setElementText(status, "복사했습니다.");
    } catch (error) {
      textarea.focus();
      textarea.select();
      setElementText(status, "복사에 실패했습니다. 글자를 직접 선택해서 복사해 주세요.");
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
        var state = getState();
        if (state.input) {
          state.input.click();
        } else {
          setInlineError(state.previewAlert, "다시 시도");
        }
      }
    });
  }

  function bindHtmxLifecycle() {
    document.body.addEventListener("htmx:beforeRequest", function (event) {
      if (!event.target || event.target.id !== "ocrdesk-form") {
        return;
      }

      var shell = byId("ocrdesk-shell");
      if (shell) {
        shell.dataset.loading = "true";
      }
      markResultPending();
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
      if (!event.detail || !event.detail.target || event.detail.target.id !== "ocrdesk-result-panel") {
        return;
      }

      clearBusyState();

      var state = getState();
      var resultText = byId("ocrdesk-result-text");
      if (resultText) {
        setElementText(state.previewAlert, "결과 준비 완료");
      } else {
        setElementText(state.previewAlert, "다시 고르기 가능");
      }

      focusResultPanel();
    });

    document.body.addEventListener("htmx:responseError", function (event) {
      if (!event.target || event.target.id !== "ocrdesk-form") {
        return;
      }

      clearBusyState();
      var state = getState();
      setInlineError(state.previewAlert, "다시 시도");
    });

    document.body.addEventListener("htmx:sendError", function (event) {
      if (!event.target || event.target.id !== "ocrdesk-form") {
        return;
      }

      clearBusyState();
      var state = getState();
      setInlineError(state.previewAlert, "다시 시도");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindPreviewInput();
    bindDropzone();
    bindActionButtons();
    if (window.htmx) {
      bindHtmxLifecycle();
    }
    syncSubmitState();

    if (byId("ocrdesk-result-text")) {
      focusResultPanel();
    }
  });
})();
