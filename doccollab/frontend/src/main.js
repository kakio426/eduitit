import initRhwp, { HwpDocument } from "@rhwp/core";
import wasmUrl from "@rhwp/core/rhwp_bg.wasm?url";


const form = document.querySelector("[data-doccollab-upload-form='true']");
const documentForm = document.querySelector("[data-doccollab-document-form='true']");
const worksheetForm = document.querySelector("[data-doccollab-worksheet-form='true']");
const instantEditorRoot = document.getElementById("doccollab-instant-editor-app");

class InstantRhwpStudioEmbed {
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
    if (this.iframe.dataset.loaded === "true") {
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
        reject(new Error("편집기 로드 실패"));
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
        reject(new Error(`요청 시간 초과: ${method}`));
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
        // The iframe can answer only after its WASM runtime finishes booting.
      }
      await delay(250);
    }
    throw new Error("편집기 초기화 지연");
  }

  async createNewDocument() {
    return this.request("createNewDocument", {}, 90000);
  }

  async exportHwpx() {
    const result = await this.request("exportHwpx", {}, 90000);
    return {
      bytes: Uint8Array.from(result?.data || []),
      fileName: result?.fileName || "새 문서.hwpx",
      pageCount: Number(result?.pageCount || 0),
    };
  }

  async focus() {
    return this.request("focusEditor", {}, 5000);
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

class DoccollabInstantEditor {
  constructor(rootEl) {
    this.rootEl = rootEl;
    this.saveButton = document.getElementById("doccollab-instant-save-button");
    this.statusEl = document.getElementById("doccollab-instant-status");
    this.editor = null;
    this.isSaving = false;
    this.isDirty = false;
    this.lastFileName = "새 문서.hwpx";
    this.boundFrameEvent = (event) => this.handleFrameEvent(event);
  }

  async start() {
    window.addEventListener("message", this.boundFrameEvent);
    this.bindSave();
    try {
      await this.mountEditor();
      await this.editor.waitReady();
      const result = await this.editor.createNewDocument();
      this.lastFileName = normalizeHwpxName(result?.fileName || this.lastFileName);
      this.isDirty = false;
      this.saveButton?.removeAttribute("disabled");
      this.setStatus("새문서");
      await this.applyOpeningViewport();
      void this.editor.focus().catch(() => undefined);
    } catch (_error) {
      this.setStatus("로드 실패", true);
      this.saveButton?.setAttribute("disabled", "disabled");
    }
  }

  bindSave() {
    this.saveButton?.addEventListener("click", () => {
      void this.saveHwpx();
    });
  }

  async mountEditor() {
    const iframe = document.createElement("iframe");
    iframe.id = "doccollab-instant-editor-frame";
    iframe.className = "doccollab-editor-frame";
    iframe.setAttribute("title", "잇티한글 새문서");
    iframe.setAttribute("allow", "clipboard-read; clipboard-write");
    const studioUrl = new URL(this.rootEl.dataset.studioUrl, window.location.origin);
    studioUrl.searchParams.set("embed", "doccollab");
    iframe.src = studioUrl.toString();
    this.rootEl.innerHTML = "";
    this.rootEl.appendChild(iframe);
    this.editor = new InstantRhwpStudioEmbed(iframe);
    this.setStatus("로딩");
  }

  async applyOpeningViewport() {
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
    if (message.event === "documentChanged" || message.event === "commandExecuted") {
      this.isDirty = true;
      this.setStatus("수정 중");
      return;
    }
    if (message.event === "saveRequested") {
      void this.saveHwpx();
      return;
    }
    if (message.event === "loaded") {
      this.lastFileName = normalizeHwpxName(message.payload?.fileName || this.lastFileName);
    }
  }

  async saveHwpx() {
    if (!this.editor || this.isSaving || this.saveButton?.disabled) {
      return;
    }
    this.isSaving = true;
    this.saveButton?.setAttribute("aria-busy", "true");
    this.setStatus("저장 중");
    try {
      const result = await this.editor.exportHwpx();
      this.lastFileName = normalizeHwpxName(result.fileName || this.lastFileName);
      downloadBytes(result.bytes, this.lastFileName, "application/vnd.hancom.hwpx");
      this.isDirty = false;
      this.setStatus("저장 완료");
    } catch (_error) {
      this.setStatus("저장 실패", true);
    } finally {
      this.isSaving = false;
      this.saveButton?.removeAttribute("aria-busy");
    }
  }

  setStatus(message, isError = false) {
    if (!this.statusEl) {
      return;
    }
    this.statusEl.textContent = message;
    this.statusEl.dataset.state = isError ? "error" : "default";
  }
}

if (instantEditorRoot) {
  bindToolMenus();
  const instantEditor = new DoccollabInstantEditor(instantEditorRoot);
  void instantEditor.start();
}

if (form) {
  const fileInput = form.querySelector("input[name='source_file']");
  const submitButton = form.querySelector("[data-doccollab-open-button='true']");
  const statusEl = document.getElementById("doccollab-upload-status");
  const rhwpReady = initRhwp({ module_or_path: wasmUrl });
  let validation = { key: null, ok: false, running: null };
  let submitLocked = false;

  fileInput?.addEventListener("change", () => {
    const file = fileInput.files?.[0] || null;
    validation = { key: null, ok: false, running: null };
    submitLocked = false;
    submitButton?.removeAttribute("disabled");
    submitButton?.removeAttribute("aria-busy");
    if (!file) {
      setStatus("파일 선택");
      return;
    }
    if (!isDesktopChrome()) {
      setStatus("데스크톱 편집");
      return;
    }
    void runPreflight(file);
  });

  form.addEventListener("submit", async (event) => {
    if (submitLocked) {
      event.preventDefault();
      return;
    }
    const file = fileInput?.files?.[0] || null;
    if (!file || !isDesktopChrome()) {
      return;
    }
    const key = buildFileKey(file);
    if (validation.key === key && validation.ok) {
      lockSubmit("여는 중");
      return;
    }
    event.preventDefault();
    const ok = await runPreflight(file);
    if (ok) {
      lockSubmit("여는 중");
      HTMLFormElement.prototype.submit.call(form);
    }
  });

  async function runPreflight(file) {
    const key = buildFileKey(file);
    if (validation.key === key && validation.ok) {
      return true;
    }
    if (validation.running && validation.key === key) {
      return validation.running;
    }
    validation.key = key;
    validation.ok = false;
    submitButton?.setAttribute("aria-busy", "true");
    setStatus("검사 중");
    validation.running = (async () => {
      try {
        const extension = (file.name.split(".").pop() || "").toLowerCase();
        if (!["hwp", "hwpx"].includes(extension)) {
          throw new Error("HWP 또는 HWPX만 열 수 있습니다.");
        }
        await rhwpReady;
        const bytes = new Uint8Array(await file.arrayBuffer());
        const document = new HwpDocument(bytes);
        if (!document.pageCount()) {
          throw new Error("열 수 없는 파일입니다.");
        }
        validation.ok = true;
        setStatus("열기 가능");
        return true;
      } catch (_error) {
        validation.ok = false;
        setStatus("열 수 없음", true);
        return false;
      } finally {
        validation.running = null;
        submitButton?.removeAttribute("aria-busy");
      }
    })();
    return validation.running;
  }

  function setStatus(message, isError = false) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.dataset.state = isError ? "error" : "default";
  }

  function lockSubmit(message) {
    submitLocked = true;
    submitButton?.setAttribute("disabled", "disabled");
    submitButton?.setAttribute("aria-busy", "true");
    setStatus(message);
  }
}

if (documentForm) {
  const promptInput = documentForm.querySelector("textarea[name='prompt']");
  const submitButton = documentForm.querySelector("[data-doccollab-document-button='true']");
  const statusEl = document.getElementById("doccollab-document-status");
  let submitLocked = false;

  promptInput?.addEventListener("input", () => {
    if (!statusEl) {
      return;
    }
    const length = String(promptInput.value || "").trim().length;
    if (!length) {
      statusEl.textContent = "생성 가능";
      statusEl.dataset.state = "default";
      return;
    }
    if (length < 20) {
      statusEl.textContent = `${length}/20`;
      statusEl.dataset.state = "default";
      return;
    }
    statusEl.textContent = "생성 가능";
    statusEl.dataset.state = "default";
  });

  documentForm.addEventListener("submit", async (event) => {
    if (submitLocked) {
      event.preventDefault();
      return;
    }
    if (submitButton?.disabled) {
      return;
    }
    const prompt = String(promptInput?.value || "").trim();
    if (prompt.length < 20) {
      event.preventDefault();
      setDocumentStatus("20자 이상", true);
      return;
    }
    event.preventDefault();
    submitLocked = true;
    submitButton?.setAttribute("aria-busy", "true");
    submitButton?.setAttribute("disabled", "disabled");
    setDocumentStatus("생성 중");

    try {
      const response = await fetch(documentForm.action, {
        method: "POST",
        body: new FormData(documentForm),
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      const payload = await parseJsonResponse(response);
      if (!response.ok) {
        const error = new Error(payload.message || "다시 시도");
        error.status = response.status;
        throw error;
      }
      if (payload.room_url) {
        window.location.assign(payload.room_url);
        return;
      }
      throw new Error("다시 시도");
    } catch (error) {
      submitLocked = false;
      setDocumentStatus(error?.status === 429 ? "오늘 한도" : "다시 시도", true);
      if (error?.status !== 429) {
        submitButton?.removeAttribute("disabled");
      }
      submitButton?.removeAttribute("aria-busy");
    }
  });

  function setDocumentStatus(message, isError = false) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.dataset.state = isError ? "error" : "default";
  }
}

if (worksheetForm) {
  const topicInput = worksheetForm.querySelector("input[name='topic']");
  const submitButton = worksheetForm.querySelector("[data-doccollab-worksheet-button='true']");
  const statusEl = document.getElementById("doccollab-worksheet-status");
  let submitLocked = false;

  topicInput?.addEventListener("input", () => {
    if (!statusEl) {
      return;
    }
    const length = String(topicInput.value || "").trim().length;
    if (!length) {
      statusEl.textContent = "생성 가능 · 편집은 데스크톱 Chrome";
      return;
    }
    statusEl.textContent = `${length}/120`;
  });

  worksheetForm.addEventListener("submit", (event) => {
    if (submitLocked) {
      event.preventDefault();
      return;
    }
    if (submitButton?.disabled) {
      return;
    }
    const topic = String(topicInput?.value || "").trim();
    if (!topic) {
      event.preventDefault();
      if (statusEl) {
        statusEl.textContent = "학습 주제를 먼저 적어 주세요.";
      }
      return;
    }
    submitLocked = true;
    submitButton?.setAttribute("aria-busy", "true");
    submitButton?.setAttribute("disabled", "disabled");
    if (statusEl) {
      statusEl.textContent = "학습지 만드는 중";
    }
  });
}


async function parseJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text);
  } catch (_error) {
    return {};
  }
}

function isDesktopChrome() {
  const ua = String(window.navigator.userAgent || "").toLowerCase();
  return ua.includes("chrome") && !ua.includes("mobile") && !ua.includes("edg/") && !ua.includes("opr/");
}

function buildFileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function bindToolMenus() {
  const menus = Array.from(document.querySelectorAll("[data-doccollab-tool-menu]"));
  menus.forEach((menu) => {
    menu.addEventListener("toggle", () => {
      if (!menu.open) {
        return;
      }
      menus.forEach((other) => {
        if (other !== menu) {
          other.removeAttribute("open");
        }
      });
    });
  });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }
    menus.forEach((menu) => {
      if (!menu.contains(target)) {
        menu.removeAttribute("open");
      }
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    menus.forEach((menu) => menu.removeAttribute("open"));
  });
}

function normalizeHwpxName(fileName) {
  const normalized = String(fileName || "새 문서.hwpx").trim() || "새 문서.hwpx";
  return normalized.replace(/\.[^.]+$/u, "") + ".hwpx";
}

function downloadBytes(bytes, fileName, mimeType) {
  const blob = new Blob([bytes], { type: mimeType || "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
