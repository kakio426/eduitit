(function () {
  const bootstrapNode = document.getElementById("class-edit-bootstrap");
  if (!bootstrapNode) {
    return;
  }

  let bootstrap = {};
  try {
    bootstrap = JSON.parse(bootstrapNode.textContent || "{}");
  } catch (_error) {
    return;
  }

  const editorNameInput = document.getElementById("class-editor-name");
  const editorNameError = document.getElementById("class-editor-name-error");
  const statusNode = document.getElementById("class-edit-status");
  const issuesList = document.getElementById("class-edit-issues");
  const saveButton = document.getElementById("class-edit-save-button");
  const submitButton = document.getElementById("class-edit-submit-button");
  const dateInput = document.getElementById("class-edit-date");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

  const currentMode = bootstrap.mode || "weekly";

  const visibleInputs = (selector) =>
    Array.from(document.querySelectorAll(selector)).filter((input) => input.offsetParent !== null && !input.disabled);

  const messageFromError = (error, fallback) => {
    const message = String(error?.message || "").trim();
    if (!message || message === "Failed to fetch" || message.includes("JSON")) {
      return fallback;
    }
    return message;
  };

  const readJsonResponse = async (response) => {
    const text = await response.text();
    if (!text) {
      return {};
    }
    try {
      return JSON.parse(text);
    } catch (_error) {
      return { ok: false, message: response.redirected ? "로그인 필요" : "다시 시도" };
    }
  };

  const requestJson = async (url, payload) => {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(payload),
    });
    const result = await readJsonResponse(response);
    if (!response.ok || !result.ok) {
      const error = new Error(result.message || "다시 시도");
      error.payload = result;
      throw error;
    }
    return result;
  };

  const setStatus = (text, tone) => {
    if (!statusNode) {
      return;
    }
    statusNode.textContent = text;
    statusNode.className = "mt-4 rounded-2xl px-4 py-3 text-sm font-semibold ";
    if (tone === "error") {
      statusNode.className += "bg-rose-50 text-rose-700";
    } else if (tone === "success") {
      statusNode.className += "bg-emerald-50 text-emerald-700";
    } else {
      statusNode.className += "bg-slate-100 text-slate-600";
    }
  };

  const setNameError = (message) => {
    if (!editorNameInput || !editorNameError) {
      return;
    }
    editorNameInput.setAttribute("aria-invalid", message ? "true" : "false");
    editorNameError.textContent = message || "";
    editorNameError.classList.toggle("hidden", !message);
  };

  const renderIssues = (validation) => {
    if (!issuesList) {
      return;
    }
    const messages = [
      ...((validation && validation.conflicts) || []),
      ...((validation && validation.warnings) || []),
    ].slice(0, 8);

    if (!messages.length) {
      issuesList.innerHTML =
        '<li class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-6 text-center text-sm font-semibold text-emerald-700">지금 확인된 큰 충돌은 없습니다.</li>';
      return;
    }

    issuesList.innerHTML = messages
      .map((message, index) => {
        const isConflict = index < (((validation && validation.conflicts) || []).length);
        return `<li class="rounded-2xl px-4 py-3 text-sm ${
          isConflict
            ? "border border-rose-200 bg-rose-50 text-rose-700"
            : "border border-amber-200 bg-amber-50 text-amber-800"
        }">${message}</li>`;
      })
      .join("");
  };

  const requireEditorName = () => {
    const value = editorNameInput?.value?.trim() || "";
    if (!value) {
      setNameError("이름 필요");
      throw new Error("이름 필요");
    }
    setNameError("");
    return value;
  };

  const collectWeeklyEntries = () =>
    visibleInputs(".weekly-cell-input").map((input) => ({
      day_key: input.dataset.dayKey,
      period_no: Number(input.dataset.periodNo),
      text: input.value.trim(),
    }));

  const collectDailyEntries = () =>
    visibleInputs(".daily-override-input").map((input) => ({
      period_no: Number(input.dataset.periodNo),
      text: input.value.trim(),
    }));

  const requestPayload = (submitted) => {
    const payload = {
      editor_name: requireEditorName(),
      mode: currentMode,
    };
    if (currentMode === "daily") {
      payload.date = dateInput?.value || bootstrap.selected_date;
      payload.entries = collectDailyEntries();
    } else {
      payload.entries = collectWeeklyEntries();
    }
    payload.submitted = submitted;
    return payload;
  };

  const syncPeerInputs = (source) => {
    if (source.classList.contains("weekly-cell-input")) {
      document.querySelectorAll(".weekly-cell-input").forEach((input) => {
        if (
          input !== source &&
          input.dataset.dayKey === source.dataset.dayKey &&
          input.dataset.periodNo === source.dataset.periodNo
        ) {
          input.value = source.value;
        }
      });
    }
    if (source.classList.contains("daily-override-input")) {
      document.querySelectorAll(".daily-override-input").forEach((input) => {
        if (input !== source && input.dataset.periodNo === source.dataset.periodNo) {
          input.value = source.value;
        }
      });
    }
  };

  const saveCurrent = async (submitted) => {
    try {
      const payload = requestPayload(submitted);
      const url = submitted
        ? bootstrap.submit_url
        : currentMode === "daily"
          ? bootstrap.daily_save_url
          : bootstrap.weekly_save_url;
      [saveButton, submitButton].forEach((button) => {
        if (button) {
          button.disabled = true;
        }
      });
      setStatus(submitted ? "입력 완료 처리 중..." : "저장 중...", "idle");

      const result = await requestJson(url, payload);
      renderIssues(result.validation || {});
      setStatus(
        submitted
          ? "입력 완료로 표시했습니다. 화면을 새로 고칩니다."
          : currentMode === "daily"
            ? "날짜별 일정을 저장했습니다. 화면을 새로 고칩니다."
            : "주간 기본 시간표를 저장했습니다.",
        "success",
      );
      if (submitted || currentMode === "daily") {
        window.setTimeout(() => {
          window.location.href = result.redirect_url || window.location.href;
        }, 250);
      }
    } catch (error) {
      renderIssues(error.payload?.validation || {});
      setStatus(messageFromError(error, "다시 시도"), "error");
    } finally {
      [saveButton, submitButton].forEach((button) => {
        if (button) {
          button.disabled = false;
        }
      });
    }
  };

  editorNameInput?.addEventListener("input", () => {
    if (editorNameInput.value.trim()) {
      setNameError("");
    }
  });

  document.addEventListener("input", (event) => {
    if (event.target instanceof HTMLInputElement) {
      syncPeerInputs(event.target);
    }
  });

  saveButton?.addEventListener("click", () => {
    saveCurrent(false);
  });

  submitButton?.addEventListener("click", () => {
    saveCurrent(true);
  });

  dateInput?.addEventListener("change", () => {
    const params = new URLSearchParams(window.location.search);
    params.set("mode", "daily");
    if (dateInput.value) {
      params.set("date", dateInput.value);
    } else {
      params.delete("date");
    }
    window.location.search = params.toString();
  });
})();
