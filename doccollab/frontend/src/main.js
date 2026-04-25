import initRhwp, { HwpDocument } from "@rhwp/core";
import wasmUrl from "@rhwp/core/rhwp_bg.wasm?url";


const form = document.querySelector("[data-doccollab-upload-form='true']");
const documentForm = document.querySelector("[data-doccollab-document-form='true']");
const worksheetForm = document.querySelector("[data-doccollab-worksheet-form='true']");

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
      const message = error instanceof Error ? error.message : "다시 시도";
      setDocumentStatus(error?.status === 429 ? "오늘 한도" : "다시 시도", true);
      if (error?.status !== 429) {
        submitButton?.removeAttribute("disabled");
      }
      submitButton?.removeAttribute("aria-busy");
      window.alert(message);
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
