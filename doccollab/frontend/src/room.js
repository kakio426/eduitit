class RhwpStudioEmbed {
  constructor(iframe) {
    this.iframe = iframe;
    this.pending = new Map();
    this.requestId = 0;
    this.targetOrigin = new URL(iframe.src, window.location.href).origin;
    this.boundResponse = (event) => this.handleResponse(event);
    window.addEventListener("message", this.boundResponse);
  }

  frameDocument() {
    return this.iframe.contentDocument || this.iframe.contentWindow?.document || null;
  }

  handleResponse(event) {
    if (event.source !== this.iframe.contentWindow || event.origin !== this.targetOrigin) {
      return;
    }
    const message = event.data || {};
    if (message.type !== "rhwp-response" || message.id == null) {
      return;
    }
    const pending = this.pending.get(message.id);
    if (!pending) {
      return;
    }
    this.pending.delete(message.id);
    window.clearTimeout(pending.timeoutId);
    if (message.error) {
      pending.reject(new Error(message.error));
      return;
    }
    pending.resolve(message.result);
  }

  waitForFrameLoad() {
    if (this.iframe.contentWindow && this.iframe.dataset.loaded === "true") {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const handleLoad = () => {
        this.iframe.dataset.loaded = "true";
        this.iframe.removeEventListener("error", handleError);
        resolve();
      };
      const handleError = () => {
        this.iframe.removeEventListener("load", handleLoad);
        reject(new Error("편집기를 열지 못했습니다."));
      };
      this.iframe.addEventListener("load", handleLoad, { once: true });
      this.iframe.addEventListener("error", handleError, { once: true });
    });
  }

  request(method, params = {}, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const id = ++this.requestId;
      const timeoutId = window.setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`요청 시간이 초과되었습니다: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timeoutId });
      this.iframe.contentWindow?.postMessage(
        {
          type: "rhwp-request",
          id,
          method,
          params,
        },
        this.targetOrigin,
      );
    });
  }

  async waitReady() {
    await this.waitForFrameLoad();
    for (let attempt = 0; attempt < 40; attempt += 1) {
      try {
        const ready = await this.request("ready", {}, 2500);
        if (ready) {
          return;
        }
      } catch (_error) {
        // Retry until the studio finishes booting.
      }
      await delay(250);
    }
    throw new Error("rhwp 편집기 초기화가 지연되고 있습니다.");
  }

  async loadFile(bytes, fileName) {
    return this.request(
      "loadFile",
      {
        data: Array.from(bytes || []),
        fileName,
      },
      90000,
    );
  }

  async exportHwp() {
    const result = await this.request("exportHwp", {}, 90000);
    return {
      bytes: Uint8Array.from(result?.data || []),
      fileName: result?.fileName || "document.hwp",
      pageCount: Number(result?.pageCount || 0),
    };
  }

  async exportHwpx() {
    const result = await this.request("exportHwpx", {}, 90000);
    return {
      bytes: Uint8Array.from(result?.data || []),
      fileName: result?.fileName || "document.hwpx",
      pageCount: Number(result?.pageCount || 0),
    };
  }

  async fillWorksheetTemplate(content, layoutProfile) {
    return this.request(
      "fillWorksheetTemplate",
      {
        content,
        layoutProfile,
      },
      90000,
    );
  }

  async pageCount() {
    return this.request("pageCount", {}, 5000);
  }

  async focus() {
    return this.request("focusEditor", {}, 5000);
  }

  async applyCommandBatch(batchId, commands) {
    return this.request(
      "applyCommandBatch",
      {
        batchId,
        commands,
      },
      30000,
    );
  }

  async selectionState() {
    return this.request("selectionState", {}, 5000);
  }

  async setCollaborationState(participantCount) {
    return this.request(
      "setCollaborationState",
      {
        participantCount,
      },
      5000,
    );
  }

  async waitForFrameSelector(selector, attempts = 40, delayMs = 120) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const frameDoc = this.frameDocument();
      const target = frameDoc?.querySelector(selector);
      if (target) {
        return target;
      }
      await delay(delayMs);
    }
    return null;
  }

  async clickFrameButton(selector) {
    const button = await this.waitForFrameSelector(selector, 20, 120);
    if (!(button instanceof HTMLElement)) {
      return false;
    }
    button.click();
    return true;
  }

  async applyDefaultView(mode = "fitPage") {
    await this.waitForFrameLoad();
    const canvas = await this.waitForFrameSelector("#scroll-container canvas", 50, 120);
    if (!canvas) {
      return false;
    }
    const selector = mode === "fitWidth" ? "#sb-zoom-fit-width" : "#sb-zoom-fit";
    return this.clickFrameButton(selector);
  }

  destroy() {
    window.removeEventListener("message", this.boundResponse);
    for (const pending of this.pending.values()) {
      window.clearTimeout(pending.timeoutId);
      pending.reject(new Error("편집기가 닫혔습니다."));
    }
    this.pending.clear();
  }
}

class DoccollabRoom {
  constructor(rootEl, payload) {
    this.rootEl = rootEl;
    this.payload = payload;
    this.canEdit = Boolean(payload.editingEnabled && payload.editingSupported);
    this.runtimeEditingEnabled = Boolean(this.canEdit);
    this.statusBadge = document.getElementById("doccollab-status-badge");
    this.snapshotBadge = document.getElementById("doccollab-snapshot-badge");
    this.participantList = document.getElementById("doccollab-participant-list");
    this.revisionList = document.getElementById("doccollab-revision-list");
    this.editHistoryList = document.getElementById("doccollab-edit-history-list");
    this.currentRevisionLabel = document.getElementById("doccollab-current-revision-label");
    this.publishedRevisionLabel = document.getElementById("doccollab-published-revision-label");
    this.downloadLink = document.getElementById("doccollab-download-link");
    this.loadErrorEl = document.getElementById("doccollab-load-error");
    this.loadErrorMessageEl = document.getElementById("doccollab-load-error-message");
    this.saveButton = document.getElementById("doccollab-save-button");
    this.publishButton = document.getElementById("doccollab-publish-button");
    this.tableSelectionLabel = document.getElementById("doccollab-table-selection");
    this.tableCommandButtons = Array.from(document.querySelectorAll("[data-doccollab-table-command]"));
    this.assistantForms = Array.from(document.querySelectorAll("[data-doccollab-assistant-form='true']"));
    this.assistantStatusEl = document.getElementById("doccollab-assistant-status");
    this.assistantSummaryEl = document.getElementById("doccollab-assistant-summary");
    this.assistantItemsEl = document.getElementById("doccollab-assistant-items");
    this.questionForm = document.querySelector("[data-doccollab-question-form='true']");
    this.questionInput = this.questionForm?.querySelector("input[name='question']");
    this.questionButton = document.getElementById("doccollab-question-button");
    this.assistantAnswerEl = document.getElementById("doccollab-assistant-answer");
    this.assistantCitationsEl = document.getElementById("doccollab-assistant-citations");
    this.renderedRevisionIds = new Set(
      Array.from(document.querySelectorAll("[data-revision-id]"))
        .map((node) => node.dataset.revisionId)
        .filter(Boolean),
    );
    this.renderedEditEventIds = new Set(
      Array.from(document.querySelectorAll("[data-edit-event-id]"))
        .map((node) => node.dataset.editEventId)
        .filter(Boolean),
    );
    this.snapshotTimer = null;
    this.pingTimer = null;
    this.reconnectTimer = null;
    this.reconnectAttempt = 0;
    this.intentionalClose = false;
    this.isDirty = false;
    this.isSaving = false;
    this.documentLoaded = false;
    this.requiresCollabRefresh = false;
    this.lastChangedAt = null;
    this.lastKnownPageCount = 0;
    this.lastLocalRevisionId = "";
    this.assistantBusy = false;
    this.questionBusy = false;
    this.baseRevisionId = payload.collabState?.base_revision_id || payload.currentRevision?.id || "";
    this.pendingReplayBatches = [];
    this.localBatchIds = new Set();
    this.participantCount = 1;
    this.selectionState = null;
    this.clientSessionKey = createSessionKey();
    this.serverSessionKey = "";
    this.boundFrameEvent = (event) => this.handleFrameEvent(event);
    this.boundBeforeUnload = () => this.handleBeforeUnload();
  }

  async start() {
    this.bindUI();
    window.addEventListener("message", this.boundFrameEvent);
    window.addEventListener("beforeunload", this.boundBeforeUnload);
    this.connectSocket();
    await this.mountEditor();
    if (this.payload.initialFileUrl) {
      await this.loadDocument(this.payload.initialFileUrl);
      this.setStatus(this.runtimeEditingEnabled ? "편집 준비 완료" : "보기 모드");
    } else {
      this.setStatus("불러올 문서가 없습니다.", true);
    }
  }

  bindUI() {
    this.saveButton?.addEventListener("click", () => {
      void this.saveRevision();
    });
    this.tableCommandButtons.forEach((button) => {
      button.addEventListener("click", () => {
        void this.applyTableCommand(button.dataset.doccollabTableCommand || "");
      });
    });
    this.assistantForms.forEach((form) => {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        void this.runAssistantAnalysis();
      });
    });
    this.questionForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.askAssistantQuestion();
    });
    this.renderAssistantAnalysis(this.payload.assistantAnalysis || null, { keepAnswer: true });
    this.updateTablePanel();
  }

  async mountEditor() {
    const iframe = document.createElement("iframe");
    iframe.id = "doccollab-editor-frame";
    iframe.className = "doccollab-editor-frame";
    iframe.setAttribute("title", "rhwp 문서 편집기");
    iframe.setAttribute("allow", "clipboard-read; clipboard-write");
    const studioUrl = new URL(this.payload.studioUrl, window.location.origin);
    studioUrl.searchParams.set("embed", "doccollab");
    if (!this.canEdit) {
      studioUrl.searchParams.set("readonly", "1");
    }
    iframe.src = studioUrl.toString();
    this.rootEl.innerHTML = "";
    this.rootEl.appendChild(iframe);
    this.editor = new RhwpStudioEmbed(iframe);
    this.setStatus("편집기 로딩");
    await this.editor.waitReady();
  }

  async loadDocument(fileUrl) {
    try {
      const response = await fetch(fileUrl, { credentials: "same-origin" });
      if (!response.ok) {
        throw new Error("문서를 불러오지 못했습니다.");
      }
      const bytes = new Uint8Array(await response.arrayBuffer());
      const result = await this.editor.loadFile(bytes, this.initialFileName());
      this.lastKnownPageCount = Number(result?.pageCount || 0);
      this.snapshotBadge.textContent = this.runtimeEditingEnabled ? "편집 중" : "보기 모드";
      this.documentLoaded = true;
      await this.applyOpeningViewport();
      await this.replayPendingBatches();
      await this.syncCollaborationState();
      await this.refreshSelectionState();
      if (this.runtimeEditingEnabled) {
        void this.editor.focus().catch(() => undefined);
      }
    } catch (error) {
      this.showLoadError(error);
      throw error;
    }
  }

  async applyOpeningViewport() {
    if (!this.editor) {
      return;
    }
    const modes = ["fitPage", "fitWidth"];
    const delays = [120, 320, 640];
    for (const waitMs of delays) {
      await delay(waitMs);
      for (const mode of modes) {
        const applied = await this.editor.applyDefaultView(mode).catch(() => false);
        if (applied) {
          return;
        }
      }
    }
  }

  handleFrameEvent(event) {
    if (!this.editor || event.source !== this.editor.iframe.contentWindow || event.origin !== this.editor.targetOrigin) {
      return;
    }
    const message = event.data || {};
    if (message.type !== "rhwp-event") {
      return;
    }
    switch (message.event) {
      case "documentChanged":
        this.onDocumentChanged(message.payload || {});
        break;
      case "commandExecuted":
        this.onCommandExecuted(message.payload || {});
        break;
      case "selectionChanged":
        this.onSelectionChanged(message.payload || {});
        break;
      case "saveRequested":
        if (this.runtimeEditingEnabled) {
          void this.saveRevision();
        }
        break;
      case "loaded":
        if (message.payload?.pageCount) {
          this.lastKnownPageCount = Number(message.payload.pageCount || 0);
          void this.applyOpeningViewport().catch(() => undefined);
          void this.replayPendingBatches().catch(() => undefined);
          void this.syncCollaborationState().catch(() => undefined);
        }
        break;
      default:
        break;
    }
  }

  onDocumentChanged(payload) {
    if (!this.runtimeEditingEnabled) {
      return;
    }
    this.isDirty = true;
    this.lastChangedAt = payload.changedAt || new Date().toISOString();
    this.lastKnownPageCount = Number(payload.pageCount || this.lastKnownPageCount || 0);
    this.snapshotBadge.textContent = "자동 저장 예정";
    this.setStatus(this.requiresCollabRefresh ? "새 저장본 확인 필요" : "수정 중");
    this.scheduleSnapshot();
  }

  onCommandExecuted(payload) {
    if (!this.runtimeEditingEnabled) {
      return;
    }
    const commands = Array.isArray(payload.commands) ? payload.commands.filter(Boolean) : [];
    if (!commands.length) {
      return;
    }
    this.sendCommandBatch(commands, payload.selection || {});
  }

  onSelectionChanged(payload) {
    void this.refreshSelectionState(payload || {});
    if (!this.runtimeEditingEnabled || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    this.socket.send(
      JSON.stringify({
        type: "editor.selection",
        payload: {
          senderSessionKey: this.sessionKey(),
          selection: payload || {},
        },
      }),
    );
  }

  scheduleSnapshot() {
    if (!this.payload.snapshotUrl || !this.runtimeEditingEnabled) {
      return;
    }
    if (this.snapshotTimer) {
      window.clearTimeout(this.snapshotTimer);
    }
    this.snapshotTimer = window.setTimeout(() => {
      void this.postSnapshot();
    }, 4000);
  }

  async postSnapshot() {
    if (!this.isDirty || !this.runtimeEditingEnabled) {
      return;
    }
    try {
      const response = await fetch(this.payload.snapshotUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": readCsrfToken(this.payload.csrfToken),
        },
        body: JSON.stringify(this.buildSnapshotPayload()),
        credentials: "same-origin",
      });
      if (!response.ok) {
        this.snapshotBadge.textContent = "자동 저장 실패";
        this.setStatus("자동 저장 실패", true);
        return;
      }
      this.snapshotBadge.textContent = "자동 저장 완료";
    } catch (_error) {
      this.snapshotBadge.textContent = "자동 저장 실패";
      this.setStatus("자동 저장 실패", true);
    }
  }

  buildSnapshotPayload() {
    return {
      roomId: this.payload.roomId,
      sourceFormat: this.payload.sourceFormat,
      saveFormat: this.payload.saveFormat,
      currentRevisionId: this.payload.currentRevision?.id || null,
      pageCount: this.lastKnownPageCount,
      dirty: this.isDirty,
      fileName: this.initialFileName(),
      changedAt: this.lastChangedAt,
      savedAt: new Date().toISOString(),
    };
  }

  async saveRevision() {
    if (!this.editor) {
      this.setStatus("편집기를 먼저 열어 주세요.", true);
      return;
    }
    if (!this.runtimeEditingEnabled || this.isSaving) {
      return;
    }
    this.isSaving = true;
    this.saveButton?.setAttribute("disabled", "disabled");
    this.saveButton?.setAttribute("aria-busy", "true");
    this.setStatus("저장 중");

    try {
      const wantsHwpx = this.payload.saveFormat === "hwpx";
      const exported = wantsHwpx ? await this.editor.exportHwpx() : await this.editor.exportHwp();
      this.lastKnownPageCount = Number(exported.pageCount || this.lastKnownPageCount || 0);
      const fileName = ensureExportFileName(exported.fileName || this.initialFileName() || this.payload.title, this.payload.saveFormat);
      const formData = new FormData();
      formData.append("export_file", new File([exported.bytes], fileName, { type: wantsHwpx ? "application/vnd.hancom.hwpx" : "application/x-hwp" }));
      formData.append("note", "온라인 편집 저장");
      formData.append("snapshot_json", JSON.stringify(this.buildSnapshotPayload()));

      const response = await fetch(this.payload.saveRevisionUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": readCsrfToken(this.payload.csrfToken),
        },
        body: formData,
        credentials: "same-origin",
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        const message = errorPayload.message || "저장에 실패했습니다.";
        this.setStatus(message, true);
        window.alert(message);
        return;
      }

      const payload = await response.json();
      if (payload.revision) {
        this.lastLocalRevisionId = payload.revision.id || "";
        this.baseRevisionId = payload.revision.id || this.baseRevisionId;
        this.requiresCollabRefresh = false;
        this.pendingReplayBatches = [];
        this.upsertRevision(payload.revision);
        this.broadcastSavedRevision(payload.revision.id || "", payload.edit_events || []);
        this.resetAssistantForNewRevision();
      }
      if (Array.isArray(payload.edit_history)) {
        this.replaceEditHistory(payload.edit_history);
      } else if (Array.isArray(payload.edit_events)) {
        this.prependEditHistory(payload.edit_events);
      }
      this.isDirty = false;
      this.snapshotBadge.textContent = "저장 완료";
      this.setStatus("저장 완료");
    } catch (error) {
      const message = error?.message || "저장에 실패했습니다.";
      this.setStatus(message, true);
      window.alert(message);
    } finally {
      this.isSaving = false;
      this.saveButton?.removeAttribute("disabled");
      this.saveButton?.removeAttribute("aria-busy");
    }
  }

  async runAssistantAnalysis() {
    if (!this.payload.assistantEnabled || !this.payload.assistantAnalyzeUrl || this.assistantBusy) {
      return;
    }
    this.assistantBusy = true;
    this.setAssistantButtonsDisabled(true);
    this.setAssistantStatus("정리 중");
    try {
      const response = await fetch(this.payload.assistantAnalyzeUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": readCsrfToken(this.payload.csrfToken),
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.message || "AI 정리에 실패했습니다.");
      }
      const payload = await response.json();
      this.payload.assistantAnalysis = payload.analysis || null;
      this.renderAssistantAnalysis(this.payload.assistantAnalysis);
      this.setStatus("AI 정리 완료");
    } catch (error) {
      const message = error?.message || "AI 정리에 실패했습니다.";
      this.setAssistantStatus(message, true);
      this.setStatus(message, true);
      window.alert(message);
    } finally {
      this.assistantBusy = false;
      this.setAssistantButtonsDisabled(false);
    }
  }

  async askAssistantQuestion() {
    if (!this.payload.assistantEnabled || !this.payload.assistantAskUrl || this.questionBusy) {
      return;
    }
    const question = String(this.questionInput?.value || "").trim();
    if (!question) {
      this.renderQuestionError("질문을 입력해 주세요.");
      this.questionInput?.focus();
      return;
    }
    this.questionBusy = true;
    if (this.questionButton) {
      this.questionButton.disabled = true;
      this.questionButton.setAttribute("aria-busy", "true");
    }
    this.renderQuestionError("");
    try {
      const response = await fetch(this.payload.assistantAskUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": readCsrfToken(this.payload.csrfToken),
        },
        body: JSON.stringify({ question }),
        credentials: "same-origin",
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.message || "답변을 만들지 못했습니다.");
      }
      const payload = await response.json();
      this.renderQuestionAnswer(payload);
    } catch (error) {
      const message = error?.message || "답변을 만들지 못했습니다.";
      this.renderQuestionError(message);
      window.alert(message);
    } finally {
      this.questionBusy = false;
      if (this.questionButton) {
        this.questionButton.disabled = false;
        this.questionButton.removeAttribute("aria-busy");
      }
    }
  }

  renderAssistantAnalysis(analysis, options = {}) {
    if (!this.assistantStatusEl) {
      return;
    }
    if (!analysis) {
      this.setAssistantStatus("정리 전");
      if (this.assistantSummaryEl) {
        this.assistantSummaryEl.textContent = "AI 정리 전";
      }
      this.renderAssistantItems([]);
      if (!options.keepAnswer) {
        this.clearAssistantAnswer();
      }
      return;
    }
    const isFailed = analysis.status === "failed";
    this.setAssistantStatus(analysis.status_label || analysis.status || "정리 완료", isFailed);
    if (this.assistantSummaryEl) {
      this.assistantSummaryEl.textContent = analysis.summary_text || analysis.error_message || "정리 결과 없음";
    }
    this.renderAssistantItems(Array.isArray(analysis.work_items) ? analysis.work_items : []);
    if (!options.keepAnswer) {
      this.clearAssistantAnswer();
    }
  }

  renderAssistantItems(items) {
    if (!this.assistantItemsEl) {
      return;
    }
    this.assistantItemsEl.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "doccollab-empty";
      empty.textContent = "정리 후 표시됩니다.";
      this.assistantItemsEl.appendChild(empty);
      return;
    }
    items.slice(0, 8).forEach((item) => {
      const row = document.createElement("div");
      row.className = "doccollab-assistant-item";
      const title = document.createElement("strong");
      title.textContent = item.title || "확인";
      const action = document.createElement("span");
      action.textContent = item.action_text || item.evidence_text || "";
      row.append(title, action);
      if (item.due_text) {
        const due = document.createElement("em");
        due.textContent = item.due_text;
        row.appendChild(due);
      }
      this.assistantItemsEl.appendChild(row);
    });
  }

  renderQuestionAnswer(payload) {
    if (!this.assistantAnswerEl) {
      return;
    }
    this.assistantAnswerEl.hidden = false;
    this.assistantAnswerEl.textContent = payload.answer || "답변 없음";
    this.assistantAnswerEl.classList.toggle("doccollab-assistant-answer--muted", Boolean(payload.has_insufficient_evidence));
    this.renderQuestionCitations(Array.isArray(payload.citations) ? payload.citations : []);
  }

  renderQuestionError(message) {
    if (!this.assistantAnswerEl) {
      return;
    }
    if (!message) {
      this.assistantAnswerEl.hidden = true;
      this.assistantAnswerEl.textContent = "";
      this.renderQuestionCitations([]);
      return;
    }
    this.assistantAnswerEl.hidden = false;
    this.assistantAnswerEl.textContent = message;
    this.assistantAnswerEl.classList.add("doccollab-assistant-answer--muted");
    this.renderQuestionCitations([]);
  }

  renderQuestionCitations(citations) {
    if (!this.assistantCitationsEl) {
      return;
    }
    this.assistantCitationsEl.innerHTML = "";
    citations.slice(0, 3).forEach((citation) => {
      const item = document.createElement("div");
      item.className = "doccollab-assistant-citation";
      const label = document.createElement("strong");
      label.textContent = citation.label || "근거";
      const text = document.createElement("span");
      text.textContent = citation.text || "";
      item.append(label, text);
      this.assistantCitationsEl.appendChild(item);
    });
  }

  clearAssistantAnswer() {
    this.renderQuestionError("");
  }

  resetAssistantForNewRevision() {
    if (!this.payload.assistantEnabled) {
      return;
    }
    this.payload.assistantAnalysis = null;
    this.renderAssistantAnalysis(null);
  }

  setAssistantStatus(message, isError = false) {
    if (!this.assistantStatusEl) {
      return;
    }
    this.assistantStatusEl.textContent = message;
    this.assistantStatusEl.style.background = isError ? "#fef2f2" : "";
    this.assistantStatusEl.style.color = isError ? "#b91c1c" : "";
  }

  setAssistantButtonsDisabled(disabled) {
    this.assistantForms.forEach((form) => {
      form.querySelectorAll("button").forEach((button) => {
        button.disabled = disabled;
        if (disabled) {
          button.setAttribute("aria-busy", "true");
        } else {
          button.removeAttribute("aria-busy");
        }
      });
    });
  }

  connectSocket() {
    if (!this.payload.wsUrl) {
      return;
    }
    this.socket = new WebSocket(buildWebSocketUrl(this.payload.wsUrl));
    this.socket.addEventListener("open", () => {
      this.reconnectAttempt = 0;
      this.startPinging();
    });
    this.socket.addEventListener("close", () => {
      if (this.pingTimer) {
        window.clearInterval(this.pingTimer);
      }
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    });
    this.socket.addEventListener("message", (event) => this.handleSocketMessage(event));
  }

  handleSocketMessage(event) {
    const message = JSON.parse(event.data || "{}");
    switch (message.type) {
      case "room.snapshot":
        this.handleRoomSnapshot(message.payload || {});
        break;
      case "presence.join":
      case "presence.leave":
        this.updateParticipants(message.payload?.participants || []);
        break;
      case "editor.command":
        this.handleBroadcastCommand(message.payload || {});
        break;
      case "editor.selection":
        this.handleBroadcastSelection(message.payload || {});
        break;
      case "revision.saved":
        this.handleRevisionSaved(message.payload || {});
        break;
      case "error":
        this.handleSocketError(message.payload || {});
        break;
      default:
        break;
    }
  }

  handleRoomSnapshot(payload) {
    if (payload.session_key) {
      this.serverSessionKey = String(payload.session_key);
    }
    this.updateParticipants(payload.presence || []);
    this.syncRevisionState(payload || {});
    this.replaceEditHistory(payload.edit_history || []);
    this.queueSnapshotBatches(payload.collab_state || {});
  }

  handleBroadcastCommand(payload) {
    if (Array.isArray(payload.edit_history)) {
      this.replaceEditHistory(payload.edit_history);
    } else if (Array.isArray(payload.edit_events)) {
      this.prependEditHistory(payload.edit_events);
    }
    const batchId = String(payload.batchId || "").trim();
    if (!batchId) {
      return;
    }
    if (this.localBatchIds.has(batchId)) {
      this.localBatchIds.delete(batchId);
      return;
    }
    if (payload.baseRevisionId && this.baseRevisionId && payload.baseRevisionId !== this.baseRevisionId) {
      this.requiresCollabRefresh = true;
      this.setStatus("다른 저장본 기준의 수정이 들어왔습니다. 저장 후 다시 열어 주세요.", true);
      return;
    }
    this.pendingReplayBatches.push({
      batchId,
      commands: Array.isArray(payload.commands) ? payload.commands : [],
    });
    void this.replayPendingBatches().catch(() => undefined);
  }

  handleBroadcastSelection(_payload) {
    // Presence metadata only for now. Remote caret rendering is a follow-up.
  }

  handleRevisionSaved(payload) {
    if (payload.revision) {
      const revisionId = payload.revision.id || "";
      this.upsertRevision(payload.revision);
      if (Array.isArray(payload.edit_history)) {
        this.replaceEditHistory(payload.edit_history);
      } else if (Array.isArray(payload.edit_events)) {
        this.prependEditHistory(payload.edit_events);
      }
      if (payload.published) {
        this.syncPublishedRevision(payload.revision);
      }
      if (revisionId === this.lastLocalRevisionId) {
        this.baseRevisionId = revisionId;
        this.requiresCollabRefresh = false;
        this.updateTablePanel();
        return;
      }
      if (this.isDirty) {
        this.requiresCollabRefresh = true;
        this.setStatus("새 저장본이 생겼습니다. 저장 후 다시 열면 최신본이 맞춰집니다.");
        this.updateTablePanel();
        return;
      }
      this.baseRevisionId = revisionId || this.baseRevisionId;
      this.requiresCollabRefresh = false;
      this.setStatus("최신 저장본으로 맞춰졌습니다.");
      this.updateTablePanel();
    }
  }

  handleSocketError(payload) {
    const message = String(payload.message || "연결 오류");
    if (message.includes("stale base revision")) {
      this.requiresCollabRefresh = true;
      this.setStatus("다른 저장본 기준이라 함께 수정이 잠시 멈췄습니다. 저장 후 다시 열어 주세요.", true);
      this.updateTablePanel();
      return;
    }
    this.setStatus(message, true);
  }

  broadcastSavedRevision(revisionId, editEvents = []) {
    if (!revisionId || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    this.socket.send(
      JSON.stringify({
        type: "revision.saved",
        payload: {
          revisionId,
          editEvents,
        },
      }),
    );
  }

  async refreshSelectionState(fallback = null) {
    const nextState = { ...(fallback || {}) };
    if (this.editor) {
      try {
        const state = await this.editor.selectionState();
        Object.assign(nextState, state || {});
      } catch (_error) {
        // Keep the latest known selection state when the editor is still settling.
      }
    }
    this.selectionState = {
      ...(this.selectionState || {}),
      ...nextState,
    };
    this.updateTablePanel();
  }

  updateTablePanel() {
    const canUseTableTools = Boolean(
      this.runtimeEditingEnabled
      && this.documentLoaded
      && this.selectionState?.inTable
      && this.selectionState?.cellInfo
      && this.selectionState?.cursor,
    );
    if (this.tableSelectionLabel) {
      if (canUseTableTools) {
        const row = Number(this.selectionState.cellInfo.row || 0) + 1;
        const col = Number(this.selectionState.cellInfo.col || 0) + 1;
        this.tableSelectionLabel.textContent = `${row}행 ${col}열`;
      } else {
        this.tableSelectionLabel.textContent = this.runtimeEditingEnabled ? "셀 선택 필요" : "보기 모드";
      }
    }
    this.tableCommandButtons.forEach((button) => {
      button.disabled = !canUseTableTools || this.requiresCollabRefresh;
    });
  }

  buildTableCommand(commandName) {
    const cursor = this.selectionState?.cursor ? JSON.parse(JSON.stringify(this.selectionState.cursor)) : null;
    const cellInfo = this.selectionState?.cellInfo || null;
    if (!cursor || !cellInfo) {
      return null;
    }
    const row = Number(cellInfo.row || 0);
    const col = Number(cellInfo.col || 0);
    const commandId = `${commandName}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    switch (commandName) {
      case "insert-row-below":
        return { id: commandId, type: "table_row_insert", position: cursor, row, below: true };
      case "insert-col-right":
        return { id: commandId, type: "table_col_insert", position: cursor, col, right: true };
      case "delete-row":
        return { id: commandId, type: "table_row_delete", position: cursor, row };
      case "delete-col":
        return { id: commandId, type: "table_col_delete", position: cursor, col };
      default:
        return null;
    }
  }

  async applyTableCommand(commandName) {
    if (!this.runtimeEditingEnabled || !this.editor) {
      return;
    }
    const command = this.buildTableCommand(commandName);
    if (!command) {
      this.setStatus("표 셀을 먼저 선택해 주세요.", true);
      await this.refreshSelectionState();
      return;
    }
    if (this.requiresCollabRefresh) {
      this.setStatus("새 저장본 확인 전에는 표 수정이 잠시 멈춥니다.", true);
      return;
    }
    const batchId = this.nextBatchId();
    this.localBatchIds.add(batchId);
    trimSet(this.localBatchIds, 180);
    const applied = await this.editor.applyCommandBatch(batchId, [command]).catch(() => null);
    if (!applied?.applied) {
      this.localBatchIds.delete(batchId);
      this.setStatus("표 수정이 반영되지 않았습니다.", true);
      await this.refreshSelectionState();
      return;
    }
    this.sendExistingBatch(batchId, [command], this.selectionState || {});
    this.setStatus("표 수정 반영 중");
    await this.refreshSelectionState();
  }

  queueSnapshotBatches(collabState) {
    if (collabState?.base_revision_id) {
      this.baseRevisionId = collabState.base_revision_id;
    }
    const updates = Array.isArray(collabState?.updates) ? collabState.updates : [];
    this.pendingReplayBatches = updates
      .filter((batch) => batch && batch.batchId)
      .map((batch) => ({
        batchId: String(batch.batchId),
        commands: Array.isArray(batch.commands) ? batch.commands : [],
      }));
    void this.replayPendingBatches().catch(() => undefined);
  }

  async replayPendingBatches() {
    if (!this.documentLoaded || !this.editor || !this.pendingReplayBatches.length) {
      return;
    }
    while (this.pendingReplayBatches.length) {
      const batch = this.pendingReplayBatches.shift();
      if (!batch?.batchId) {
        continue;
      }
      const result = await this.editor.applyCommandBatch(batch.batchId, batch.commands || []);
      if (!result?.applied) {
        this.setStatus("다른 탭 수정 반영 실패", true);
        return;
      }
    }
  }

  sendCommandBatch(commands, selection) {
    if (
      !this.socket
      || this.socket.readyState !== WebSocket.OPEN
      || !Array.isArray(commands)
      || !commands.length
    ) {
      return;
    }
    if (this.requiresCollabRefresh) {
      this.setStatus("새 저장본 확인 전에는 함께 수정이 잠시 멈춥니다.", true);
      return;
    }
    const batchId = this.nextBatchId();
    this.localBatchIds.add(batchId);
    trimSet(this.localBatchIds, 180);
    this.sendExistingBatch(batchId, commands, selection);
  }

  sendExistingBatch(batchId, commands, selection) {
    if (
      !this.socket
      || this.socket.readyState !== WebSocket.OPEN
      || !Array.isArray(commands)
      || !commands.length
    ) {
      return;
    }
    this.socket.send(
      JSON.stringify({
        type: "editor.command",
        payload: {
          batchId,
          baseRevisionId: this.baseRevisionId || this.payload.currentRevision?.id || "",
          senderSessionKey: this.sessionKey(),
          commands,
          selection: selection || {},
        },
      }),
    );
  }

  nextBatchId() {
    return `batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }

  sessionKey() {
    return this.serverSessionKey || this.clientSessionKey;
  }

  scheduleReconnect() {
    if (this.reconnectTimer) {
      return;
    }
    const delayMs = Math.min(5000, 1000 * (2 ** this.reconnectAttempt));
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connectSocket();
    }, delayMs);
  }

  startPinging() {
    if (this.pingTimer) {
      window.clearInterval(this.pingTimer);
    }
    this.pingTimer = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping", payload: {} }));
      }
    }, 20000);
  }

  updateParticipants(participants) {
    this.participantCount = Math.max(1, participants.length || 0);
    if (this.participantList) {
      this.participantList.innerHTML = "";
      if (!participants.length) {
        this.participantList.innerHTML = '<div class="doccollab-empty">아직 접속 중인 사람이 없습니다.</div>';
      } else {
        participants.forEach((item) => {
          const row = document.createElement("div");
          row.className = "doccollab-room-row";
          row.innerHTML = `
            <span class="doccollab-room-title">${escapeHtml(item.display_name || "사용자")}</span>
            <span class="doccollab-room-meta">${escapeHtml(item.role || "")}</span>
          `;
          this.participantList.appendChild(row);
        });
      }
    }
    void this.syncCollaborationState().catch(() => undefined);
  }

  async syncCollaborationState() {
    if (!this.editor) {
      return;
    }
    await this.editor.setCollaborationState(this.participantCount).catch(() => undefined);
  }

  syncRevisionState(payload) {
    if (payload.current_revision) {
      this.syncCurrentRevision(payload.current_revision, { announce: false });
    }
    if (payload.published_revision) {
      this.syncPublishedRevision(payload.published_revision);
    }
    if (payload.collab_state?.base_revision_id) {
      this.baseRevisionId = payload.collab_state.base_revision_id;
    }
  }

  upsertRevision(revision) {
    if (!revision || !this.revisionList) {
      return;
    }
    this.syncCurrentRevision(revision);
    if (revision.is_published) {
      this.syncPublishedRevision(revision);
    }
    if (this.renderedRevisionIds.has(revision.id)) {
      return;
    }
    const emptyState = this.revisionList.querySelector(".doccollab-empty");
    emptyState?.remove();
    const row = document.createElement("a");
    row.className = "doccollab-room-row";
    row.dataset.revisionId = revision.id || "";
    row.href = revision.download_url || "#";
    row.innerHTML = `
      <span class="doccollab-room-title">r${escapeHtml(String(revision.revision_number || ""))} · ${escapeHtml(revision.export_format_label || revision.export_format || "")}</span>
      <span class="doccollab-room-meta">${formatDateTime(revision.created_at)}</span>
    `;
    this.revisionList.prepend(row);
    this.renderedRevisionIds.add(revision.id);
  }

  syncCurrentRevision(revision, options = {}) {
    if (!revision) {
      return;
    }
    const previousRevisionId = this.payload.currentRevision?.id || "";
    this.payload.currentRevision = revision;
    this.payload.currentRevisionFormat = revision.file_format || this.payload.currentRevisionFormat;
    if (this.currentRevisionLabel) {
      this.currentRevisionLabel.textContent = `r${revision.revision_number} · ${revision.export_format_label || revision.export_format || ""}`;
    }
    if (this.downloadLink) {
      this.downloadLink.href = revision.download_url || "#";
      this.downloadLink.classList.remove("doccollab-secondary--disabled");
      this.downloadLink.removeAttribute("aria-disabled");
    }
    if (this.publishButton && this.runtimeEditingEnabled) {
      this.publishButton.removeAttribute("disabled");
    }
    if (options.announce === false) {
      return;
    }
    if (previousRevisionId && previousRevisionId !== revision.id && revision.id !== this.lastLocalRevisionId) {
      this.setStatus("최신 저장본 정보가 갱신되었습니다.");
    }
  }

  syncPublishedRevision(revision) {
    if (!revision || !this.publishedRevisionLabel) {
      return;
    }
    this.payload.publishedRevision = revision;
    this.publishedRevisionLabel.textContent = `r${revision.revision_number} · ${revision.export_format_label || revision.export_format || ""}`;
  }

  replaceEditHistory(events) {
    if (!this.editHistoryList) {
      return;
    }
    this.editHistoryList.innerHTML = "";
    this.renderedEditEventIds.clear();
    if (!events.length) {
      this.editHistoryList.innerHTML = '<div class="doccollab-empty">아직 기록된 편집이 없습니다.</div>';
      return;
    }
    events.forEach((event) => {
      if (!event?.id) {
        return;
      }
      this.editHistoryList.appendChild(this.buildEditHistoryRow(event));
      this.renderedEditEventIds.add(event.id);
    });
  }

  prependEditHistory(events) {
    if (!this.editHistoryList || !events.length) {
      return;
    }
    this.editHistoryList.querySelector(".doccollab-empty")?.remove();
    [...events].reverse().forEach((event) => {
      if (!event?.id || this.renderedEditEventIds.has(event.id)) {
        return;
      }
      this.editHistoryList.prepend(this.buildEditHistoryRow(event));
      this.renderedEditEventIds.add(event.id);
    });
  }

  buildEditHistoryRow(event) {
    const row = document.createElement("div");
    row.className = "doccollab-room-row doccollab-room-row--history";
    row.dataset.editEventId = event.id || "";
    row.innerHTML = `
      <div class="doccollab-room-main">
        <div class="doccollab-room-heading">
          <span class="doccollab-room-title">${escapeHtml(event.display_name || "사용자")}</span>
          <div class="doccollab-room-badges">
            <span class="doccollab-chip doccollab-chip--soft">${escapeHtml(event.command_label || event.command_type || "수정")}</span>
            ${Number(event.event_count || 0) > 1 ? `<span class="doccollab-chip doccollab-chip--soft">${escapeHtml(String(event.event_count))}건</span>` : ""}
          </div>
        </div>
        <span class="doccollab-room-submeta">${escapeHtml(event.summary || "편집")}</span>
        <div class="doccollab-room-meta-row">
          <span class="doccollab-room-meta">${escapeHtml(event.created_at_display || formatDateTime(event.created_at))}</span>
        </div>
      </div>
    `;
    return row;
  }

  initialFileName() {
    return (
      this.payload.currentRevision?.original_name
      || this.payload.sourceName
      || `${this.payload.title || "document"}.${this.payload.sourceFormat || "hwp"}`
    );
  }

  showLoadError(error) {
    const message = error?.message || "브라우저에서 열 수 없는 파일입니다.";
    this.rootEl.innerHTML = "";
    this.rootEl.classList.add("doccollab-editor-surface--failed");
    if (this.loadErrorMessageEl) {
      this.loadErrorMessageEl.textContent = `${message} 원본 파일을 내려받아 확인해 주세요.`;
    }
    if (this.loadErrorEl) {
      this.loadErrorEl.hidden = false;
    }
    if (this.saveButton) {
      this.saveButton.disabled = true;
    }
    if (this.publishButton) {
      this.publishButton.disabled = true;
    }
    this.snapshotBadge.textContent = "사용 불가";
    this.setStatus("열기 실패", true);
  }

  handleBeforeUnload() {
    this.intentionalClose = true;
    if (this.snapshotTimer) {
      window.clearTimeout(this.snapshotTimer);
    }
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
    }
    if (this.pingTimer) {
      window.clearInterval(this.pingTimer);
    }
    if (this.socket) {
      this.socket.close();
    }
    this.editor?.destroy();
  }

  setStatus(message, isError = false) {
    if (!this.statusBadge) {
      return;
    }
    this.statusBadge.textContent = message;
    this.statusBadge.style.background = isError ? "#fef2f2" : "";
    this.statusBadge.style.color = isError ? "#b91c1c" : "";
  }
}

function buildWebSocketUrl(path) {
  if (/^wss?:\/\//.test(path)) {
    return path;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function ensureExportFileName(name, format = "hwp") {
  const trimmed = String(name || "document").trim() || "document";
  const extension = format === "hwpx" ? ".hwpx" : ".hwp";
  if (trimmed.toLowerCase().endsWith(extension)) {
    return trimmed;
  }
  return `${trimmed.replace(/\.[^.]+$/u, "")}${extension}`;
}

function readCsrfToken(initialToken) {
  if (initialToken) {
    return initialToken;
  }
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="));
  return cookie ? cookie.split("=")[1] : "";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString("ko-KR") : "";
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function trimSet(set, limit) {
  while (set.size > limit) {
    const [first] = set;
    set.delete(first);
  }
}

function createSessionKey() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `client-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

const rootEl = document.getElementById("doccollab-editor-app");
const payloadEl = document.getElementById("doccollab-room-payload");

if (rootEl && payloadEl) {
  const payload = JSON.parse(payloadEl.textContent || "{}");
  const app = new DoccollabRoom(rootEl, payload);
  app.start().catch((error) => {
    console.error(error);
    app.showLoadError(error);
  });
}
