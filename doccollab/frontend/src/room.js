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
    this.runtimeEditingEnabled = Boolean(payload.editingEnabled && payload.editingSupported);
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
    this.baseRevisionId = payload.collabState?.base_revision_id || payload.currentRevision?.id || "";
    this.pendingReplayBatches = [];
    this.localBatchIds = new Set();
    this.participantCount = 1;
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
    await this.loadDocument(this.payload.initialFileUrl);
    this.setStatus(this.runtimeEditingEnabled ? "편집 준비 완료" : "보기 모드");
  }

  bindUI() {
    this.saveButton?.addEventListener("click", () => {
      void this.saveRevision();
    });
  }

  async mountEditor() {
    const iframe = document.createElement("iframe");
    iframe.id = "doccollab-editor-frame";
    iframe.className = "doccollab-editor-frame";
    iframe.setAttribute("title", "rhwp 문서 편집기");
    iframe.setAttribute("allow", "clipboard-read; clipboard-write");
    const studioUrl = new URL(this.payload.studioUrl, window.location.origin);
    studioUrl.searchParams.set("embed", "doccollab");
    if (!this.runtimeEditingEnabled) {
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
      const exported = await this.editor.exportHwp();
      this.lastKnownPageCount = Number(exported.pageCount || this.lastKnownPageCount || 0);
      const fileName = ensureHwpFileName(exported.fileName || this.initialFileName() || this.payload.title);
      const formData = new FormData();
      formData.append("export_file", new File([exported.bytes], fileName, { type: "application/x-hwp" }));
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
      }
      if (Array.isArray(payload.edit_events)) {
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
    if (Array.isArray(payload.edit_events)) {
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
      if (Array.isArray(payload.edit_events)) {
        this.prependEditHistory(payload.edit_events);
      }
      if (payload.published) {
        this.syncPublishedRevision(payload.revision);
      }
      if (revisionId === this.lastLocalRevisionId) {
        this.baseRevisionId = revisionId;
        this.requiresCollabRefresh = false;
        return;
      }
      if (this.isDirty) {
        this.requiresCollabRefresh = true;
        this.setStatus("새 저장본이 생겼습니다. 저장 후 다시 열면 최신본이 맞춰집니다.");
        return;
      }
      this.baseRevisionId = revisionId || this.baseRevisionId;
      this.requiresCollabRefresh = false;
      this.setStatus("최신 저장본으로 맞춰졌습니다.");
    }
  }

  handleSocketError(payload) {
    const message = String(payload.message || "연결 오류");
    if (message.includes("stale base revision")) {
      this.requiresCollabRefresh = true;
      this.setStatus("다른 저장본 기준이라 함께 수정이 잠시 멈췄습니다. 저장 후 다시 열어 주세요.", true);
      return;
    }
    this.setStatus(message, true);
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
      await this.editor.applyCommandBatch(batch.batchId, batch.commands || []);
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
            <span class="doccollab-chip doccollab-chip--soft">${escapeHtml(event.command_type || "edit")}</span>
          </div>
        </div>
        <span class="doccollab-room-submeta">${escapeHtml(event.summary || "편집")}</span>
      </div>
      <div class="doccollab-room-side">
        <span class="doccollab-room-meta">${formatDateTime(event.created_at)}</span>
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

function ensureHwpFileName(name) {
  const trimmed = String(name || "document").trim() || "document";
  if (trimmed.toLowerCase().endsWith(".hwp")) {
    return trimmed;
  }
  return `${trimmed.replace(/\.[^.]+$/u, "")}.hwp`;
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
