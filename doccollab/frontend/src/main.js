import initRhwp, { HwpDocument } from "@rhwp/core";
import wasmUrl from "@rhwp/core/rhwp_bg.wasm?url";


const form = document.querySelector("[data-doccollab-upload-form='true']");

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


function isDesktopChrome() {
  const ua = String(window.navigator.userAgent || "").toLowerCase();
  return ua.includes("chrome") && !ua.includes("mobile") && !ua.includes("edg/") && !ua.includes("opr/");
}

function buildFileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}
