import initRhwp, { HwpDocument } from "@rhwp/core";
import wasmUrl from "@rhwp/core/rhwp_bg.wasm?url";
import * as Y from "yjs";


class DoccollabRoom {
  constructor(rootEl, payload) {
    this.rootEl = rootEl;
    this.payload = payload;
    this.pageEls = new Map();
    this.remoteSelections = new Map();
    this.appliedCommandIds = new Set();
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
    this.isComposing = false;
    this.pendingOutboundCommands = [];
    this.ydoc = new Y.Doc();
    this.commandArray = this.ydoc.getArray("commands");
    this.statusBadge = document.getElementById("doccollab-status-badge");
    this.snapshotBadge = document.getElementById("doccollab-snapshot-badge");
    this.cursorLabel = document.getElementById("doccollab-cursor-label");
    this.participantList = document.getElementById("doccollab-participant-list");
    this.revisionList = document.getElementById("doccollab-revision-list");
    this.editHistoryList = document.getElementById("doccollab-edit-history-list");
    this.currentRevisionLabel = document.getElementById("doccollab-current-revision-label");
    this.publishedRevisionLabel = document.getElementById("doccollab-published-revision-label");
    this.downloadLink = document.getElementById("doccollab-download-link");
    this.loadErrorEl = document.getElementById("doccollab-load-error");
    this.loadErrorMessageEl = document.getElementById("doccollab-load-error-message");
    this.saveButton = document.getElementById("doccollab-save-button");
    this.inputProxy = document.getElementById("doccollab-input-proxy");
    this.tableSelect = document.getElementById("doccollab-table-select");
    this.tableRowInput = document.getElementById("doccollab-table-row");
    this.tableColInput = document.getElementById("doccollab-table-col");
    this.cellTextInput = document.getElementById("doccollab-cell-text");
    this.cellApplyButton = document.getElementById("doccollab-cell-apply-button");
    this.rowAddButton = document.getElementById("doccollab-row-add-button");
    this.colAddButton = document.getElementById("doccollab-col-add-button");
    this.tables = [];
    this.currentCursor = null;
  }

  async start() {
    this.installYjsBridge();
    this.bindUI();
    await this.loadDocument(this.payload.initialFileUrl);
    this.applyCollabState(this.payload.collabState);
    this.connectSocket();
    window.addEventListener("beforeunload", () => {
      this.intentionalClose = true;
      if (this.reconnectTimer) {
        window.clearTimeout(this.reconnectTimer);
      }
      if (this.socket) {
        this.socket.close();
      }
    });
    this.setStatus("준비 완료");
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
    if (this.snapshotBadge) {
      this.snapshotBadge.textContent = "사용 불가";
    }
    this.setStatus("열기 실패", true);
  }

  installYjsBridge() {
    this.commandArray.observe((event) => {
      event.changes.added.forEach((item) => {
        item.content.getContent().forEach((command) => {
          if (!command || !command.id || this.appliedCommandIds.has(command.id)) {
            return;
          }
          this.appliedCommandIds.add(command.id);
          try {
            this.executeCommand(command);
          } catch (error) {
            this.setStatus(`원격 반영 실패: ${error.message || error}`, true);
          }
        });
      });
    });

    this.ydoc.on("update", (update, origin) => {
      if (origin === "remote") {
        return;
      }
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        return;
      }
      const commands = this.pendingOutboundCommands.splice(0);
      this.socket.send(JSON.stringify({
        type: "editor.command",
        payload: {
          update: Array.from(update),
          commands,
        },
      }));
    });
  }

  bindUI() {
    this.bindInputProxy();

    this.cellApplyButton?.addEventListener("click", () => {
      const tableRef = this.getSelectedTable();
      if (!tableRef) {
        this.setStatus("표가 없습니다.", true);
        return;
      }
      this.applyLocalCommand({
        type: "set_cell_text",
        table: tableRef,
        row: Number(this.tableRowInput.value || 0),
        col: Number(this.tableColInput.value || 0),
        text: this.cellTextInput.value || "",
      });
    });

    this.rowAddButton?.addEventListener("click", () => {
      const tableRef = this.getSelectedTable();
      if (!tableRef) {
        this.setStatus("표가 없습니다.", true);
        return;
      }
      this.applyLocalCommand({
        type: "insert_table_row",
        table: tableRef,
        row: Number(this.tableRowInput.value || 0),
        below: true,
      });
    });

    this.colAddButton?.addEventListener("click", () => {
      const tableRef = this.getSelectedTable();
      if (!tableRef) {
        this.setStatus("표가 없습니다.", true);
        return;
      }
      this.applyLocalCommand({
        type: "insert_table_col",
        table: tableRef,
        col: Number(this.tableColInput.value || 0),
        right: true,
      });
    });

    this.saveButton?.addEventListener("click", () => this.saveRevision());
  }

  bindInputProxy() {
    if (!this.inputProxy || !this.payload.editingEnabled) {
      return;
    }
    this.inputProxy.addEventListener("keydown", (event) => this.handleEditorKeyDown(event));
    this.inputProxy.addEventListener("beforeinput", (event) => this.handleBeforeInput(event));
    this.inputProxy.addEventListener("paste", (event) => this.handlePaste(event));
    this.inputProxy.addEventListener("compositionstart", () => {
      this.isComposing = true;
    });
    this.inputProxy.addEventListener("compositionend", () => {
      this.isComposing = false;
    });
    this.inputProxy.addEventListener("input", () => {
      if (!this.isComposing) {
        if (this.inputProxy.value) {
          this.insertPlainText(this.inputProxy.value);
        }
        this.inputProxy.value = "";
      }
    });
  }

  handleEditorKeyDown(event) {
    if (!this.payload.editingEnabled) {
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      this.saveRevision();
      return;
    }
    if (event.key === "Backspace") {
      event.preventDefault();
      this.deleteBackward();
      return;
    }
    if (event.key === "Delete") {
      event.preventDefault();
      this.deleteForward();
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      this.splitParagraph();
    }
  }

  handleBeforeInput(event) {
    if (!this.payload.editingEnabled || this.isComposing) {
      return;
    }
    if (event.inputType === "insertText" && event.data) {
      event.preventDefault();
      this.insertPlainText(event.data);
      return;
    }
    if ((event.inputType === "insertParagraph" || event.inputType === "insertLineBreak")) {
      event.preventDefault();
      this.splitParagraph();
    }
  }

  handlePaste(event) {
    if (!this.payload.editingEnabled) {
      return;
    }
    event.preventDefault();
    this.insertPlainText(event.clipboardData?.getData("text/plain") || "");
  }

  ensureCursor(message) {
    if (this.currentCursor) {
      return true;
    }
    this.setStatus(message, true);
    return false;
  }

  insertPlainText(text) {
    if (!this.ensureCursor("페이지를 눌러 위치를 먼저 잡아 주세요.")) {
      return;
    }
    const normalized = String(text || "").replace(/\r\n?/g, "\n");
    if (!normalized) {
      return;
    }
    const lines = normalized.split("\n");
    lines.forEach((line, index) => {
      if (line) {
        this.applyLocalCommand({
          type: "insert_text",
          cursor: this.currentCursor,
          text: line,
        });
      }
      if (index < lines.length - 1) {
        this.applyLocalCommand({
          type: "split_paragraph",
          cursor: this.currentCursor,
        });
      }
    });
    this.focusInputProxy();
  }

  deleteBackward() {
    if (!this.ensureCursor("페이지를 눌러 위치를 먼저 잡아 주세요.")) {
      return;
    }
    if ((this.currentCursor.charOffset || 0) <= 0) {
      this.setStatus("문단 시작에서는 지울 수 없습니다.", true);
      return;
    }
    this.applyLocalCommand({
      type: "delete_text",
      cursor: {
        ...this.currentCursor,
        charOffset: this.currentCursor.charOffset - 1,
      },
      count: 1,
    });
    this.focusInputProxy();
  }

  deleteForward() {
    if (!this.ensureCursor("페이지를 눌러 위치를 먼저 잡아 주세요.")) {
      return;
    }
    this.applyLocalCommand({
      type: "delete_text",
      cursor: this.currentCursor,
      count: 1,
    });
    this.focusInputProxy();
  }

  splitParagraph() {
    if (!this.ensureCursor("페이지를 눌러 위치를 먼저 잡아 주세요.")) {
      return;
    }
    this.applyLocalCommand({
      type: "split_paragraph",
      cursor: this.currentCursor,
    });
    this.focusInputProxy();
  }

  async loadDocument(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error("문서를 불러오지 못했습니다.");
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    try {
      this.document = new HwpDocument(bytes);
      this.pageCount = this.document.pageCount();
      if (!this.pageCount) {
        throw new Error("empty page count");
      }
      this.currentCursor = this.safeJson(() => this.document.getCaretPosition()) || {
        sectionIndex: 0,
        paragraphIndex: 0,
        charOffset: 0,
      };
      this.scanTables();
      this.renderPages();
      this.sendSelection();
    } catch (_error) {
      throw new Error("브라우저에서 열 수 없는 파일입니다.");
    }
  }

  renderPages() {
    this.rootEl.innerHTML = "";
    this.pageEls.clear();
    for (let pageIndex = 0; pageIndex < this.pageCount; pageIndex += 1) {
      const pageEl = document.createElement("div");
      pageEl.className = "doccollab-page";
      pageEl.dataset.pageIndex = String(pageIndex);
      pageEl.innerHTML = this.document.renderPageSvg(pageIndex);

      const overlay = document.createElement("button");
      overlay.type = "button";
      overlay.className = "doccollab-page-overlay";
      overlay.addEventListener("click", (event) => this.handlePageClick(pageIndex, event));
      pageEl.appendChild(overlay);

      this.pageEls.set(pageIndex, pageEl);
      this.rootEl.appendChild(pageEl);
    }
    if (this.inputProxy && this.payload.editingEnabled) {
      this.rootEl.appendChild(this.inputProxy);
    }
    this.renderCursor();
    this.renderRemoteSelections();
    this.refreshCursorLabel();
    this.refreshTablesUI();
  }

  handlePageClick(pageIndex, event) {
    const pageEl = this.pageEls.get(pageIndex);
    if (!pageEl) {
      return;
    }
    const coords = this.resolvePageCoordinates(pageEl, event);
    const result = this.safeJson(() => this.document.hitTest(pageIndex, coords.x, coords.y));
    if (!result || result.sectionIndex == null) {
      this.setStatus("글자 위치를 찾지 못했습니다.", true);
      return;
    }
    this.currentCursor = {
      sectionIndex: result.sectionIndex,
      paragraphIndex: result.paragraphIndex,
      charOffset: result.charOffset,
    };
    this.renderCursor();
    this.refreshCursorLabel();
    this.sendSelection();
    this.focusInputProxy();
  }

  resolvePageCoordinates(pageEl, event) {
    const overlayRect = pageEl.getBoundingClientRect();
    const svg = pageEl.querySelector("svg");
    const viewBox = svg?.viewBox?.baseVal;
    const scaleX = viewBox && viewBox.width ? viewBox.width / overlayRect.width : 1;
    const scaleY = viewBox && viewBox.height ? viewBox.height / overlayRect.height : 1;
    return {
      x: (event.clientX - overlayRect.left) * scaleX,
      y: (event.clientY - overlayRect.top) * scaleY,
    };
  }

  refreshCursorLabel() {
    if (!this.cursorLabel) {
      return;
    }
    if (!this.currentCursor) {
      this.cursorLabel.textContent = "페이지를 눌러 위치를 잡아 주세요.";
      return;
    }
    this.cursorLabel.textContent = `구역 ${this.currentCursor.sectionIndex + 1} · 문단 ${this.currentCursor.paragraphIndex + 1} · 위치 ${this.currentCursor.charOffset}`;
  }

  renderCursor() {
    this.rootEl.querySelectorAll(".doccollab-caret").forEach((node) => node.remove());
    if (!this.currentCursor) {
      this.hideInputProxy();
      return;
    }
    const rect = this.safeJson(() => this.document.getCursorRect(
      this.currentCursor.sectionIndex,
      this.currentCursor.paragraphIndex,
      this.currentCursor.charOffset,
    ));
    if (!rect || rect.pageIndex == null) {
      this.hideInputProxy();
      return;
    }
    const pageEl = this.pageEls.get(rect.pageIndex);
    if (!pageEl) {
      this.hideInputProxy();
      return;
    }
    const position = this.projectRect(pageEl, rect);
    const caret = document.createElement("div");
    caret.className = "doccollab-caret";
    caret.style.left = `${position.x}px`;
    caret.style.top = `${position.y}px`;
    caret.style.height = `${position.height}px`;
    pageEl.appendChild(caret);
    this.positionInputProxy(pageEl, position);
  }

  renderRemoteSelections() {
    this.rootEl.querySelectorAll(".doccollab-remote-cursor").forEach((node) => node.remove());
    let colorIndex = 0;
    for (const [name, cursor] of this.remoteSelections.entries()) {
      if (!cursor || cursor.pageIndex == null) {
        continue;
      }
      const pageEl = this.pageEls.get(cursor.pageIndex);
      if (!pageEl) {
        continue;
      }
      const position = this.projectRect(pageEl, cursor);
      const marker = document.createElement("div");
      marker.className = "doccollab-remote-cursor";
      marker.dataset.name = name;
      marker.style.left = `${position.x}px`;
      marker.style.top = `${position.y}px`;
      marker.style.height = `${position.height}px`;
      marker.style.background = REMOTE_COLORS[colorIndex % REMOTE_COLORS.length];
      marker.style.color = REMOTE_COLORS[colorIndex % REMOTE_COLORS.length];
      pageEl.appendChild(marker);
      colorIndex += 1;
    }
  }

  projectRect(pageEl, rect) {
    const pageRect = pageEl.getBoundingClientRect();
    const svg = pageEl.querySelector("svg");
    const viewBox = svg?.viewBox?.baseVal;
    const scaleX = viewBox && viewBox.width ? pageRect.width / viewBox.width : 1;
    const scaleY = viewBox && viewBox.height ? pageRect.height / viewBox.height : 1;
    return {
      x: rect.x * scaleX,
      y: rect.y * scaleY,
      height: Math.max(18, rect.height * scaleY),
    };
  }

  positionInputProxy(pageEl, position) {
    if (!this.inputProxy || !this.payload.editingEnabled) {
      return;
    }
    this.inputProxy.style.left = `${pageEl.offsetLeft + position.x}px`;
    this.inputProxy.style.top = `${pageEl.offsetTop + position.y}px`;
    this.inputProxy.style.height = `${position.height}px`;
    this.inputProxy.hidden = false;
  }

  hideInputProxy() {
    if (!this.inputProxy) {
      return;
    }
    this.inputProxy.hidden = true;
  }

  focusInputProxy() {
    if (!this.inputProxy || !this.payload.editingEnabled) {
      return;
    }
    this.inputProxy.focus({ preventScroll: true });
    this.inputProxy.value = "";
  }

  connectSocket() {
    const wsUrl = this.buildWebSocketUrl(this.payload.wsUrl);
    this.socket = new WebSocket(wsUrl);
    this.socket.addEventListener("open", () => {
      this.reconnectAttempt = 0;
      this.setStatus("연결됨");
      this.startPinging();
    });
    this.socket.addEventListener("close", () => {
      this.setStatus("연결 끊김", true);
      if (this.pingTimer) {
        clearInterval(this.pingTimer);
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
        this.updateParticipants(message.payload?.presence || []);
        this.syncRevisionState(message.payload);
        this.replaceEditHistory(message.payload?.edit_history || []);
        this.applyCollabState(message.payload?.collab_state);
        break;
      case "presence.join":
      case "presence.leave":
        this.updateParticipants(message.payload?.participants || []);
        break;
      case "editor.command": {
        const update = message.payload?.update || [];
        if (update.length) {
          Y.applyUpdate(this.ydoc, new Uint8Array(update), "remote");
        }
        this.prependEditHistory(message.payload?.edit_events || []);
        break;
      }
      case "editor.selection": {
        const sender = message.payload?.sender || "";
        if (!sender || sender === this.payload.displayName) {
          return;
        }
        this.remoteSelections.set(sender, message.payload?.cursor || null);
        this.renderRemoteSelections();
        break;
      }
      case "revision.saved":
        if (message.payload?.revision) {
          this.upsertRevision(message.payload.revision);
        }
        if (message.payload?.published) {
          this.syncPublishedRevision(message.payload.revision);
        }
        break;
      case "error":
        this.setStatus(message.payload?.message || "연결 오류", true);
        break;
      default:
        break;
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) {
      return;
    }
    const delay = Math.min(5000, 1000 * (2 ** this.reconnectAttempt));
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connectSocket();
    }, delay);
  }

  updateParticipants(participants) {
    if (!this.participantList) {
      return;
    }
    this.participantList.innerHTML = "";
    if (!participants.length) {
      this.participantList.innerHTML = '<div class="doccollab-empty">아직 접속 중인 사람이 없습니다.</div>';
      return;
    }
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

  buildWebSocketUrl(path) {
    if (/^wss?:\/\//.test(path)) {
      return path;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${path}`;
  }

  startPinging() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
    }
    this.pingTimer = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping", payload: {} }));
      }
    }, 20000);
  }

  sendSelection() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN || !this.currentCursor) {
      return;
    }
    const rect = this.safeJson(() => this.document.getCursorRect(
      this.currentCursor.sectionIndex,
      this.currentCursor.paragraphIndex,
      this.currentCursor.charOffset,
    ));
    this.socket.send(JSON.stringify({
      type: "editor.selection",
      payload: {
        cursor: {
          ...this.currentCursor,
          ...(rect || {}),
        },
      },
    }));
  }

  applyLocalCommand(command) {
    const envelope = {
      ...command,
      id: globalThis.crypto?.randomUUID?.() || `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      sender: this.payload.displayName || "선생님",
      sentAt: new Date().toISOString(),
    };
    try {
      this.executeCommand(envelope);
      this.appliedCommandIds.add(envelope.id);
      this.pendingOutboundCommands.push({ ...envelope });
      this.commandArray.push([envelope]);
      this.scheduleSnapshot();
      this.sendSelection();
      this.setStatus("반영됨");
    } catch (error) {
      this.setStatus(error.message || "반영 실패", true);
    }
  }

  executeCommand(command) {
    switch (command.type) {
      case "insert_text":
        this.currentCursor = this.applyInsertText(command.cursor, command.text);
        break;
      case "delete_text":
        this.currentCursor = this.applyDeleteText(command.cursor, command.count || 1);
        break;
      case "split_paragraph":
        this.currentCursor = this.applySplitParagraph(command.cursor);
        break;
      case "set_cell_text":
        this.applySetCellText(command.table, command.row, command.col, command.text || "");
        break;
      case "insert_table_row":
        this.applyInsertTableRow(command.table, command.row, command.below !== false);
        break;
      case "insert_table_col":
        this.applyInsertTableCol(command.table, command.col, command.right !== false);
        break;
      default:
        throw new Error("지원하지 않는 명령입니다.");
    }
    this.pageCount = this.document.pageCount();
    this.scanTables();
    this.renderPages();
  }

  applyInsertText(cursor, text) {
    const result = this.safeJson(() => this.document.insertText(
      cursor.sectionIndex,
      cursor.paragraphIndex,
      cursor.charOffset,
      text,
    )) || {};
    return {
      sectionIndex: cursor.sectionIndex,
      paragraphIndex: cursor.paragraphIndex,
      charOffset: result.charOffset ?? (cursor.charOffset + text.length),
    };
  }

  applyDeleteText(cursor, count) {
    const result = this.safeJson(() => this.document.deleteText(
      cursor.sectionIndex,
      cursor.paragraphIndex,
      cursor.charOffset,
      count,
    )) || {};
    return {
      sectionIndex: cursor.sectionIndex,
      paragraphIndex: cursor.paragraphIndex,
      charOffset: result.charOffset ?? cursor.charOffset,
    };
  }

  applySplitParagraph(cursor) {
    const result = this.safeJson(() => this.document.splitParagraph(
      cursor.sectionIndex,
      cursor.paragraphIndex,
      cursor.charOffset,
    )) || {};
    return {
      sectionIndex: cursor.sectionIndex,
      paragraphIndex: result.paraIdx ?? (cursor.paragraphIndex + 1),
      charOffset: result.charOffset ?? 0,
    };
  }

  applySetCellText(table, row, col, text) {
    const cell = this.findCell(table, row, col);
    if (!cell) {
      throw new Error("셀을 찾지 못했습니다.");
    }
    const length = this.document.getCellParagraphLength(
      table.sectionIndex,
      table.parentParaIndex,
      table.controlIndex,
      cell.cellIdx,
      0,
    );
    if (length > 0) {
      this.document.deleteTextInCell(
        table.sectionIndex,
        table.parentParaIndex,
        table.controlIndex,
        cell.cellIdx,
        0,
        0,
        length,
      );
    }
    if (text) {
      this.document.insertTextInCell(
        table.sectionIndex,
        table.parentParaIndex,
        table.controlIndex,
        cell.cellIdx,
        0,
        0,
        text,
      );
    }
  }

  applyInsertTableRow(table, row, below) {
    this.document.insertTableRow(
      table.sectionIndex,
      table.parentParaIndex,
      table.controlIndex,
      row,
      below,
    );
  }

  applyInsertTableCol(table, col, right) {
    this.document.insertTableColumn(
      table.sectionIndex,
      table.parentParaIndex,
      table.controlIndex,
      col,
      right,
    );
  }

  findCell(table, row, col) {
    const cells = this.safeJson(() => this.document.getTableCellBboxes(
      table.sectionIndex,
      table.parentParaIndex,
      table.controlIndex,
    )) || [];
    return cells.find((item) => item.row === row && item.col === col) || null;
  }

  scanTables() {
    const tables = [];
    const seen = new Set();
    const sectionCount = this.document.getSectionCount();
    for (let sectionIndex = 0; sectionIndex < sectionCount; sectionIndex += 1) {
      const paraCount = this.document.getParagraphCount(sectionIndex);
      for (let paragraphIndex = 0; paragraphIndex < paraCount; paragraphIndex += 1) {
        for (let controlIndex = 0; controlIndex < (this.payload.maxControlScan || 12); controlIndex += 1) {
          const key = `${sectionIndex}:${paragraphIndex}:${controlIndex}`;
          if (seen.has(key)) {
            continue;
          }
          const dimensions = this.safeJson(() => this.document.getTableDimensions(
            sectionIndex,
            paragraphIndex,
            controlIndex,
          ));
          if (!dimensions || typeof dimensions.rowCount !== "number") {
            continue;
          }
          seen.add(key);
          tables.push({
            sectionIndex,
            parentParaIndex: paragraphIndex,
            controlIndex,
            rowCount: dimensions.rowCount,
            colCount: dimensions.colCount,
          });
        }
      }
    }
    this.tables = tables;
  }

  refreshTablesUI() {
    if (!this.tableSelect) {
      return;
    }
    this.tableSelect.innerHTML = "";
    if (!this.tables.length) {
      this.tableSelect.innerHTML = '<option value="">표 없음</option>';
      return;
    }
    this.tables.forEach((table, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `표 ${index + 1} (${table.rowCount}x${table.colCount})`;
      this.tableSelect.appendChild(option);
    });
  }

  getSelectedTable() {
    const index = Number(this.tableSelect?.value || 0);
    return this.tables[index] || null;
  }

  scheduleSnapshot() {
    if (this.snapshotTimer) {
      window.clearTimeout(this.snapshotTimer);
    }
    if (this.snapshotBadge) {
      this.snapshotBadge.textContent = "스냅샷 예정";
    }
    this.snapshotTimer = window.setTimeout(() => this.postSnapshot(), 4000);
  }

  async postSnapshot() {
    try {
      const response = await fetch(this.payload.snapshotUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(this.payload.csrfToken),
        },
        body: JSON.stringify(this.buildSnapshotPayload()),
        credentials: "same-origin",
      });
      if (!response.ok) {
        if (this.snapshotBadge) {
          this.snapshotBadge.textContent = "스냅샷 실패";
        }
        this.setStatus("자동 스냅샷 실패", true);
        return;
      }
      if (this.snapshotBadge) {
        this.snapshotBadge.textContent = "스냅샷 저장";
      }
    } catch (_error) {
      if (this.snapshotBadge) {
        this.snapshotBadge.textContent = "스냅샷 실패";
      }
      this.setStatus("자동 스냅샷 실패", true);
    }
  }

  buildSnapshotPayload() {
    return {
      commands: this.commandArray.toArray().slice(-100),
      cursor: this.currentCursor,
      pageCount: this.pageCount,
      tableCount: this.tables.length,
      savedAt: new Date().toISOString(),
    };
  }

  async saveRevision() {
    if (!this.document) {
      this.setStatus("문서를 먼저 열어 주세요.", true);
      return;
    }
    try {
      const bytes = this.document.exportHwp();
      const fileName = `${this.payload.title || "document"}.hwp`;
      const formData = new FormData();
      formData.append("export_file", new File([bytes], fileName, { type: "application/x-hwp" }));
      formData.append("note", "협업 저장");
      formData.append("snapshot_json", JSON.stringify(this.buildSnapshotPayload()));
      const response = await fetch(this.payload.saveRevisionUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(this.payload.csrfToken),
        },
        body: formData,
        credentials: "same-origin",
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        window.alert(payload.message || "저장에 실패했습니다.");
        return;
      }
      const payload = await response.json();
      this.upsertRevision(payload.revision);
      this.setStatus("저장 완료");
    } catch (error) {
      window.alert(error.message || "저장에 실패했습니다.");
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
    if (emptyState) {
      emptyState.remove();
    }
    const row = document.createElement("a");
    row.className = "doccollab-room-row";
    row.dataset.revisionId = revision.id;
    row.href = revision.download_url || "#";
    row.innerHTML = `
      <span class="doccollab-room-title">r${escapeHtml(String(revision.revision_number))} · ${escapeHtml(revision.export_format_label || revision.export_format || "")}</span>
      <span class="doccollab-room-meta">${new Date(revision.created_at).toLocaleString("ko-KR")}</span>
    `;
    this.revisionList.prepend(row);
    this.renderedRevisionIds.add(revision.id);
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
    const emptyState = this.editHistoryList.querySelector(".doccollab-empty");
    if (emptyState) {
      emptyState.remove();
    }
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
        <span class="doccollab-room-meta">${formatTimestamp(event.created_at)}</span>
      </div>
    `;
    return row;
  }

  syncRevisionState(payload) {
    if (!payload) {
      return;
    }
    if (payload.current_revision) {
      this.syncCurrentRevision(payload.current_revision);
    }
    if (payload.published_revision) {
      this.syncPublishedRevision(payload.published_revision);
    }
  }

  syncCurrentRevision(revision) {
    if (!revision) {
      return;
    }
    const previousRevisionId = this.payload.currentRevision?.id || null;
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
    if (previousRevisionId && previousRevisionId !== revision.id) {
      this.setStatus("새 저장본 반영");
    }
  }

  syncPublishedRevision(revision) {
    if (!revision || !this.publishedRevisionLabel) {
      return;
    }
    this.payload.publishedRevision = revision;
    this.publishedRevisionLabel.textContent = `r${revision.revision_number} · ${revision.export_format_label || revision.export_format || ""}`;
  }

  applyCollabState(collabState) {
    if (!collabState) {
      return;
    }
    const baseRevisionId = collabState.base_revision_id || collabState.baseRevisionId || null;
    const currentRevisionId = this.payload.currentRevision?.id || null;
    if (baseRevisionId && currentRevisionId && baseRevisionId !== currentRevisionId) {
      return;
    }
    const updates = Array.isArray(collabState.updates) ? collabState.updates : [];
    updates.forEach((update) => {
      if (Array.isArray(update) && update.length) {
        Y.applyUpdate(this.ydoc, Uint8Array.from(update), "remote");
      }
    });
  }

  safeJson(fn) {
    try {
      const value = fn();
      if (typeof value === "string") {
        if (!value) {
          return null;
        }
        return JSON.parse(value);
      }
      return value;
    } catch (_error) {
      return null;
    }
  }

  setStatus(message, isError = false) {
    if (this.statusBadge) {
      this.statusBadge.textContent = message;
      this.statusBadge.style.background = isError ? "#fef2f2" : "";
      this.statusBadge.style.color = isError ? "#b91c1c" : "";
    }
  }
}


const REMOTE_COLORS = ["#0f766e", "#2563eb", "#9333ea", "#ea580c", "#e11d48"];

function getCsrfToken(seed) {
  if (seed) {
    return seed;
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

function formatTimestamp(value) {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleString("ko-KR");
}


const root = document.getElementById("doccollab-editor-app");
const payloadEl = document.getElementById("doccollab-room-payload");

if (root && payloadEl) {
  globalThis.measureTextWidth = (() => {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    let lastFont = "";
    return (font, text) => {
      if (!context) {
        return String(text || "").length * 8;
      }
      if (font !== lastFont) {
        context.font = font;
        lastFont = font;
      }
      return context.measureText(String(text || "")).width;
    };
  })();

  const payload = JSON.parse(payloadEl.textContent);
  const app = new DoccollabRoom(root, payload);

  try {
    await initRhwp({ module_or_path: wasmUrl });
    await app.start();
  } catch (error) {
    console.error(error);
    app.showLoadError(error);
  }
}
