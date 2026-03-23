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
      setElementText(state.dropzoneTitle, "사진이 올라왔습니다. 바로 읽는 중이거나, 아래 버튼으로 다시 읽을 수 있습니다.");
      setElementText(state.dropzoneHelp, "다른 사진으로 바꾸려면 이 카드에 다시 놓거나, 아래의 사진 다시 고르기를 누르세요.");
      return;
    }

    setElementText(state.dropzoneTitle, "여기에 사진을 놓거나 눌러서 고르세요");
    setElementText(state.dropzoneHelp, "사진을 고르면 미리보기가 바뀌고, 읽은 글자는 바로 결과 카드에 채워집니다.");
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
    setElementText(state.previewAlert, "사진을 읽는 중입니다. 결과 카드가 곧 채워집니다.");

    var emptyTitle = document.querySelector("#ocrdesk-result-panel [data-result-empty-title]");
    var emptyHelp = document.querySelector("#ocrdesk-result-panel [data-result-empty-help]");
    if (emptyTitle) {
      setElementText(emptyTitle, "사진을 읽는 중입니다.");
    }
    if (emptyHelp) {
      setElementText(emptyHelp, "잠시만 기다리면 이 카드에 편집 가능한 글자가 들어옵니다.");
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
      setElementText(state.fileName, "아직 고른 사진이 없습니다.");
      setElementText(state.previewAlert, "사진을 고르면 이 자리에서 바로 읽기를 시작합니다.");
      setDropzoneState({ hasFile: false, dragging: false });
      syncSubmitState();
      return;
    }

    setElementText(state.fileName, file.name || "사진 1장 선택됨");
    setDropzoneState({ hasFile: true, dragging: false });
    syncSubmitState();
    clearFormErrors();

    if (!window.FileReader) {
      setElementText(state.previewAlert, "이 브라우저에서는 미리보기를 보여주지 못하지만, 읽기는 가능합니다.");
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      return;
    }

    var reader = new FileReader();
    reader.onload = function (event) {
      state.image.src = event.target && event.target.result ? event.target.result : "";
      state.image.classList.remove("hidden");
      state.emptyState.classList.add("hidden");
      setElementText(state.previewAlert, "사진이 들어왔습니다. 바로 읽기를 시작합니다.");
    };
    reader.onerror = function () {
      state.image.src = "";
      state.image.classList.add("hidden");
      state.emptyState.classList.remove("hidden");
      setElementText(state.previewAlert, "사진 미리보기를 불러오지 못했습니다. 다른 사진으로 다시 시도해 주세요.");
    };
    reader.readAsDataURL(file);
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
      window.alert("사진 입력 칸을 찾지 못했습니다. 페이지를 다시 열어 주세요.");
      return false;
    }

    try {
      state.input.files = fileList;
      return true;
    } catch (error) {
      window.alert("드롭한 사진을 불러오지 못했습니다. 버튼을 눌러 사진을 다시 골라 주세요.");
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
      updatePreview(file);
      if (file) {
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

      updatePreview(files[0]);
      submitForOCR();
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
        var state = getState();
        if (state.input) {
          state.input.click();
        } else {
          window.alert("사진 선택 버튼을 찾지 못했습니다. 페이지를 다시 열어 주세요.");
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
        setElementText(state.previewAlert, "읽은 결과가 결과 카드에 채워졌습니다.");
      } else {
        setElementText(state.previewAlert, "사진을 다시 고르면 새 결과를 바로 읽습니다.");
      }

      focusResultPanel();
    });

    document.body.addEventListener("htmx:responseError", function (event) {
      if (!event.target || event.target.id !== "ocrdesk-form") {
        return;
      }

      clearBusyState();
      var state = getState();
      setElementText(state.previewAlert, "서버 응답을 받지 못했습니다. 잠시 뒤 다시 시도해 주세요.");
      window.alert("사진을 읽는 요청에 실패했습니다. 잠시 뒤 다시 시도해 주세요.");
    });

    document.body.addEventListener("htmx:sendError", function (event) {
      if (!event.target || event.target.id !== "ocrdesk-form") {
        return;
      }

      clearBusyState();
      var state = getState();
      setElementText(state.previewAlert, "네트워크 문제로 사진을 보내지 못했습니다.");
      window.alert("네트워크 문제로 사진을 보내지 못했습니다. 연결 상태를 확인해 주세요.");
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
