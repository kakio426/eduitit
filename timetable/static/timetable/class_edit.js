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
  const statusNode = document.getElementById("class-edit-status");
  const issuesList = document.getElementById("class-edit-issues");
  const saveButton = document.getElementById("class-edit-save-button");
  const submitButton = document.getElementById("class-edit-submit-button");
  const dateInput = document.getElementById("class-edit-date");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

  const currentMode = bootstrap.mode || "weekly";

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
      throw new Error("입력자 이름을 먼저 적어 주세요.");
    }
    return value;
  };

  const collectWeeklyEntries = () =>
    Array.from(document.querySelectorAll(".weekly-cell-input")).map((input) => ({
      day_key: input.dataset.dayKey,
      period_no: Number(input.dataset.periodNo),
      text: input.value.trim(),
    }));

  const collectDailyEntries = () =>
    Array.from(document.querySelectorAll(".daily-override-input")).map((input) => ({
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

  const saveCurrent = async (submitted) => {
    const payload = requestPayload(submitted);
    const url = submitted
      ? bootstrap.submit_url
      : currentMode === "daily"
        ? bootstrap.daily_save_url
        : bootstrap.weekly_save_url;
    const button = submitted ? submitButton : saveButton;
    if (button) {
      button.disabled = true;
    }
    setStatus(submitted ? "입력 완료 처리 중..." : "저장 중...", "idle");

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        renderIssues(result.validation || {});
        throw new Error(result.message || "저장에 실패했습니다.");
      }
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
      setStatus(error.message, "error");
      window.alert(error.message);
    } finally {
      if (button) {
        button.disabled = false;
      }
    }
  };

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
