const pdfModuleUrl = new URL("./vendor/pdfjs/pdf.min.mjs", import.meta.url).href;
const pdfWorkerUrl = new URL("./vendor/pdfjs/pdf.worker.min.mjs", import.meta.url).href;

let pdfjsPromise = null;
const previewStates = new WeakMap();

function formatBytes(size) {
  const value = Number(size || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  if (value < 1024) {
    return `${value}B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)}KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)}MB`;
}

function getElements(root) {
  return {
    placeholder: root.querySelector("[data-preview-placeholder]"),
    canvas: root.querySelector("[data-preview-canvas]"),
    image: root.querySelector("[data-preview-image]"),
    status: root.querySelector("[data-preview-status]"),
    meta: root.querySelector("[data-preview-meta]"),
    pagination: root.querySelector("[data-preview-pagination]"),
    prevButton: root.querySelector("[data-preview-prev]"),
    nextButton: root.querySelector("[data-preview-next]"),
    pageIndicator: root.querySelector("[data-preview-page]"),
  };
}

function getPreviewState(root) {
  let state = previewStates.get(root);
  if (!state) {
    state = {
      pdf: null,
      kind: "remote",
      currentPage: 1,
      totalPages: 1,
      renderToken: 0,
    };
    previewStates.set(root, state);
  }
  return state;
}

function setStatus(root, text) {
  const { status } = getElements(root);
  if (status) {
    status.textContent = text;
  }
}

function setMeta(root, text) {
  const { meta } = getElements(root);
  if (meta) {
    meta.textContent = text;
  }
}

function setPagination(root, { visible, currentPage = 1, totalPages = 1, disabled = false }) {
  const { pagination, prevButton, nextButton, pageIndicator } = getElements(root);
  if (!pagination) {
    return;
  }

  if (!visible) {
    pagination.classList.add("hidden");
    return;
  }

  pagination.classList.remove("hidden");
  if (pageIndicator) {
    pageIndicator.textContent = `${currentPage} / ${totalPages}쪽`;
  }
  if (prevButton) {
    prevButton.disabled = disabled || currentPage <= 1;
  }
  if (nextButton) {
    nextButton.disabled = disabled || currentPage >= totalPages;
  }
}

function resetPdfState(root) {
  const state = getPreviewState(root);
  state.pdf = null;
  state.currentPage = 1;
  state.totalPages = 1;
  state.renderToken = 0;
  setPagination(root, { visible: false });
}

function showPlaceholder(root, text) {
  const { placeholder, canvas, image } = getElements(root);
  resetPdfState(root);
  if (placeholder) {
    placeholder.textContent = text;
    placeholder.classList.remove("hidden");
  }
  if (canvas) {
    canvas.classList.add("hidden");
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  if (image) {
    image.classList.add("hidden");
    image.removeAttribute("src");
  }
}

function isPdf(fileType, fileName) {
  return (fileType || "").toLowerCase() === "pdf" || (fileName || "").toLowerCase().endsWith(".pdf");
}

async function loadPdfJs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import(pdfModuleUrl).then((pdfjsLib) => {
      pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
      return pdfjsLib;
    });
  }
  return pdfjsPromise;
}

function buildReadyStatus(kind, currentPage, totalPages) {
  if (kind === "upload") {
    return `업로드 전 확인 완료 · ${currentPage} / ${totalPages}쪽`;
  }
  return `${currentPage} / ${totalPages}쪽 미리보기`;
}

function buildLoadingStatus(kind, currentPage, totalPages) {
  if (kind === "upload") {
    return `업로드 전 ${currentPage} / ${totalPages}쪽을 불러오는 중입니다.`;
  }
  return `${currentPage} / ${totalPages}쪽을 불러오는 중입니다.`;
}

function bindPagination(root) {
  if (root.dataset.previewPaginationBound === "1") {
    return;
  }
  const { prevButton, nextButton } = getElements(root);
  if (!prevButton || !nextButton) {
    return;
  }

  prevButton.addEventListener("click", () => {
    const state = getPreviewState(root);
    if (!state.pdf || state.currentPage <= 1) {
      return;
    }
    renderPdfPage(root, state.currentPage - 1).catch((error) => {
      console.warn("consent-preview-prev-page-failed", error);
      setStatus(root, "이전 페이지를 불러오지 못했습니다.");
    });
  });

  nextButton.addEventListener("click", () => {
    const state = getPreviewState(root);
    if (!state.pdf || state.currentPage >= state.totalPages) {
      return;
    }
    renderPdfPage(root, state.currentPage + 1).catch((error) => {
      console.warn("consent-preview-next-page-failed", error);
      setStatus(root, "다음 페이지를 불러오지 못했습니다.");
    });
  });

  root.dataset.previewPaginationBound = "1";
}

async function renderPdfPage(root, pageNumber) {
  const state = getPreviewState(root);
  const { placeholder, canvas, image } = getElements(root);
  if (!canvas || !state.pdf) {
    return null;
  }

  const safePage = Math.max(1, Math.min(pageNumber, state.totalPages || 1));
  state.renderToken += 1;
  const renderToken = state.renderToken;

  setPagination(root, {
    visible: state.totalPages > 1,
    currentPage: safePage,
    totalPages: state.totalPages,
    disabled: true,
  });
  setStatus(root, buildLoadingStatus(state.kind, safePage, state.totalPages));

  const page = await state.pdf.getPage(safePage);
  const container = canvas.parentElement;
  const maxWidth = Number(root.dataset.maxWidth || 920);
  const availableWidth = Math.min(container?.clientWidth || maxWidth, maxWidth);
  const baseViewport = page.getViewport({ scale: 1 });
  const scale = Math.max(0.55, availableWidth / baseViewport.width);
  const viewport = page.getViewport({ scale });
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  await page.render({
    canvasContext: canvas.getContext("2d"),
    viewport,
  }).promise;

  if (renderToken !== state.renderToken) {
    return state.totalPages;
  }

  if (placeholder) {
    placeholder.classList.add("hidden");
  }
  if (image) {
    image.classList.add("hidden");
  }
  canvas.classList.remove("hidden");

  state.currentPage = safePage;
  setPagination(root, {
    visible: state.totalPages > 1,
    currentPage: safePage,
    totalPages: state.totalPages,
    disabled: false,
  });
  setStatus(root, buildReadyStatus(state.kind, safePage, state.totalPages));
  return state.totalPages;
}

async function loadPdfPreview(root, sourceUrl, kind) {
  const state = getPreviewState(root);
  state.kind = kind;
  const pdfjsLib = await loadPdfJs();
  state.pdf = await pdfjsLib.getDocument(sourceUrl).promise;
  state.totalPages = state.pdf.numPages;
  state.currentPage = 1;
  bindPagination(root);
  return renderPdfPage(root, 1);
}

async function renderImage(root, sourceUrl, altText) {
  const { placeholder, canvas, image } = getElements(root);
  resetPdfState(root);
  if (!image) {
    return;
  }
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
    image.src = sourceUrl;
    image.alt = altText || "문서 미리보기";
  });
  if (placeholder) {
    placeholder.classList.add("hidden");
  }
  if (canvas) {
    canvas.classList.add("hidden");
  }
  image.classList.remove("hidden");
}

async function renderRemotePreview(root) {
  const sourceUrl = root.dataset.sourceUrl || "";
  const fileType = root.dataset.fileType || "";
  const fileName = root.dataset.fileName || "";
  if (!sourceUrl) {
    showPlaceholder(root, "미리보기 주소를 찾지 못했습니다.");
    setStatus(root, "문서 연결 정보를 다시 확인해 주세요.");
    return;
  }

  showPlaceholder(root, "문서를 불러오는 중입니다.");
  setStatus(root, "same-origin으로 문서를 불러오는 중입니다.");
  setMeta(root, [fileName, formatBytes(root.dataset.fileSize)].filter(Boolean).join(" · "));

  try {
    if (isPdf(fileType, fileName)) {
      await loadPdfPreview(root, sourceUrl, "remote");
      return;
    }

    await renderImage(root, sourceUrl, fileName);
    setStatus(root, "이미지 문서를 표시했습니다.");
  } catch (error) {
    console.warn("consent-remote-preview-failed", error);
    showPlaceholder(root, "문서를 불러오지 못했습니다.");
    setStatus(root, "새 탭 열기 또는 다운로드 버튼으로 이어가 주세요.");
  }
}

function bindUploadPreview(root) {
  const input = document.getElementById(root.dataset.fileInputId || "");
  if (!input) {
    return;
  }

  let activeUrl = "";
  const reset = () => {
    if (activeUrl) {
      URL.revokeObjectURL(activeUrl);
      activeUrl = "";
    }
  };

  const emptyLabel = root.dataset.emptyLabel || "파일을 고르면 업로드 전 문서를 여기서 바로 확인합니다.";
  showPlaceholder(root, emptyLabel);
  setStatus(root, "PDF는 페이지 이동, 이미지는 원본 비율로 미리보기 합니다.");
  setMeta(root, "");

  input.addEventListener("change", async () => {
    const file = input.files?.[0];
    reset();

    if (!file) {
      showPlaceholder(root, emptyLabel);
      setStatus(root, "아직 선택된 파일이 없습니다.");
      setMeta(root, "");
      return;
    }

    activeUrl = URL.createObjectURL(file);
    showPlaceholder(root, "선택한 파일을 준비하는 중입니다.");
    setStatus(root, "업로드 전 문서를 불러오는 중입니다.");
    setMeta(root, [file.name, formatBytes(file.size)].filter(Boolean).join(" · "));

    try {
      if (isPdf(file.type, file.name)) {
        await loadPdfPreview(root, activeUrl, "upload");
      } else {
        await renderImage(root, activeUrl, file.name);
        setStatus(root, "업로드 전 이미지 확인 완료");
      }
    } catch (error) {
      console.warn("consent-upload-preview-failed", error);
      showPlaceholder(root, "이 파일은 여기서 바로 미리보지 못했습니다.");
      setStatus(root, "파일 형식이나 브라우저 상태를 확인해 주세요.");
    }
  });
}

function init() {
  document.querySelectorAll("[data-consent-document-preview]").forEach((root) => {
    renderRemotePreview(root);
  });
  document.querySelectorAll("[data-consent-upload-preview]").forEach((root) => {
    bindUploadPreview(root);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init, { once: true });
} else {
  init();
}
