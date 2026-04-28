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
    stage: root.querySelector("[data-preview-stage]"),
    placeholder: root.querySelector("[data-preview-placeholder]"),
    canvas: root.querySelector("[data-preview-canvas]"),
    image: root.querySelector("[data-preview-image]"),
    overlay: root.querySelector("[data-preview-overlay]"),
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
      previewMarks: null,
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
  const { placeholder, canvas, image, overlay } = getElements(root);
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
  if (overlay) {
    overlay.classList.add("hidden");
    const ctx = overlay.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, overlay.width, overlay.height);
    }
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

function getPreviewMarks(root) {
  const state = getPreviewState(root);
  if (state.previewMarks !== null) {
    return state.previewMarks;
  }
  try {
    const parsed = JSON.parse(root.dataset.previewMarks || "[]");
    state.previewMarks = Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.warn("consent-preview-mark-parse-failed", error);
    state.previewMarks = [];
  }
  return state.previewMarks;
}

function hideOverlay(root) {
  const { overlay } = getElements(root);
  if (!overlay) {
    return;
  }
  const ctx = overlay.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, overlay.width, overlay.height);
  }
  overlay.classList.add("hidden");
}

function sizeOverlayCanvas(root, width, height) {
  const { overlay } = getElements(root);
  if (!overlay || !width || !height) {
    return null;
  }
  const outputScale = window.devicePixelRatio || 1;
  overlay.width = Math.ceil(width * outputScale);
  overlay.height = Math.ceil(height * outputScale);
  overlay.style.width = `${width}px`;
  overlay.style.height = `${height}px`;
  const ctx = overlay.getContext("2d");
  ctx.setTransform(outputScale, 0, 0, outputScale, 0, 0);
  ctx.clearRect(0, 0, width, height);
  overlay.classList.remove("hidden");
  return ctx;
}

function getCurrentDecision(root) {
  const decisionName = root.dataset.previewDecisionName || "";
  if (!decisionName) {
    return "";
  }
  const checked = document.querySelector(`input[name="${decisionName}"]:checked`);
  return checked ? checked.value : "";
}

function getCurrentSignerName(root, fallbackText = "") {
  const signerInput = document.getElementById(root.dataset.previewSignerInputId || "");
  if (!signerInput) {
    return fallbackText;
  }
  return (signerInput.value || "").trim() || fallbackText;
}

function getCurrentSignatureData(root) {
  const signatureInput = document.getElementById(root.dataset.previewSignatureInputId || "");
  return signatureInput ? (signatureInput.value || "").trim() : "";
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function appliesCheckRule(mark, decision) {
  if (mark.check_rule === "always") {
    return true;
  }
  if (mark.check_rule === "disagree") {
    return decision === "disagree";
  }
  return decision === "agree";
}

function drawNameMark(ctx, mark, left, top, width, height, root) {
  const textValue = mark.text_source === "signer_name"
    ? getCurrentSignerName(root, mark.text_value || "")
    : (mark.text_value || "");
  const displayText = textValue || mark.text_label || "이름";
  const fontSize = Math.max(12, Math.min(height * 0.42, 24));
  ctx.save();
  drawRoundedRect(ctx, left, top, width, height, 10);
  ctx.fillStyle = "rgba(245, 158, 11, 0.18)";
  ctx.strokeStyle = "rgba(180, 83, 9, 0.45)";
  ctx.lineWidth = 1.5;
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#92400e";
  ctx.font = `700 ${fontSize}px "Noto Sans KR", sans-serif`;
  ctx.textBaseline = "middle";
  ctx.fillText(displayText, left + 10, top + (height / 2));
  ctx.restore();
}

function drawCheckMark(ctx, left, top, width, height, options = {}) {
  const active = Boolean(options.active);
  const label = options.label || "";
  ctx.save();
  drawRoundedRect(ctx, left, top, width, height, 10);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = active ? "rgba(15, 23, 42, 0.6)" : "rgba(148, 163, 184, 0.7)";
  ctx.setLineDash(active ? [] : [5, 5]);
  ctx.stroke();
  if (active) {
    ctx.setLineDash([]);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = Math.max(2.5, Math.min(width, height) * 0.11);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(left + (width * 0.24), top + (height * 0.56));
    ctx.lineTo(left + (width * 0.42), top + (height * 0.74));
    ctx.lineTo(left + (width * 0.78), top + (height * 0.28));
    ctx.stroke();
  } else if (label) {
    ctx.fillStyle = "#64748b";
    ctx.font = `700 ${Math.max(11, Math.min(height * 0.22, 15))}px "Noto Sans KR", sans-serif`;
    ctx.textBaseline = "middle";
    ctx.fillText(label, left + 10, top + (height / 2));
  }
  ctx.restore();
}

async function drawSignatureMark(ctx, left, top, width, height, signatureData) {
  ctx.save();
  drawRoundedRect(ctx, left, top, width, height, 10);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = "rgba(37, 99, 235, 0.45)";
  ctx.stroke();

  if (signatureData.startsWith("data:image")) {
    const signatureImage = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = signatureData;
    });
    const padding = 6;
    const availableWidth = Math.max(width - (padding * 2), 1);
    const availableHeight = Math.max(height - (padding * 2), 1);
    const scale = Math.min(
      availableWidth / signatureImage.width,
      availableHeight / signatureImage.height,
    );
    const drawWidth = signatureImage.width * scale;
    const drawHeight = signatureImage.height * scale;
    const drawLeft = left + padding + ((availableWidth - drawWidth) / 2);
    const drawTop = top + padding + ((availableHeight - drawHeight) / 2);
    ctx.drawImage(signatureImage, drawLeft, drawTop, drawWidth, drawHeight);
  } else {
    ctx.fillStyle = "#2563eb";
    ctx.font = `700 ${Math.max(11, Math.min(height * 0.22, 15))}px "Noto Sans KR", sans-serif`;
    ctx.textBaseline = "middle";
    ctx.fillText("사인", left + 10, top + (height / 2));
  }
  ctx.restore();
}

async function renderPreviewOverlay(root) {
  const marks = getPreviewMarks(root);
  const { canvas, image } = getElements(root);
  if (!marks.length) {
    hideOverlay(root);
    return;
  }

  const state = getPreviewState(root);
  const currentPage = state.currentPage || 1;
  const visibleMarks = marks.filter((mark) => Number(mark.page) === currentPage);
  if (!visibleMarks.length) {
    hideOverlay(root);
    return;
  }

  let width = 0;
  let height = 0;
  if (canvas && !canvas.classList.contains("hidden")) {
    width = parseFloat(canvas.style.width) || canvas.clientWidth || canvas.width;
    height = parseFloat(canvas.style.height) || canvas.clientHeight || canvas.height;
  } else if (image && !image.classList.contains("hidden")) {
    width = image.clientWidth;
    height = image.clientHeight;
  }
  if (!width || !height) {
    hideOverlay(root);
    return;
  }

  const ctx = sizeOverlayCanvas(root, width, height);
  if (!ctx) {
    return;
  }

  const decision = getCurrentDecision(root);
  const signatureData = getCurrentSignatureData(root);

  for (const mark of visibleMarks) {
    const xRatio = Number(mark.x_ratio);
    const yRatio = Number(mark.y_ratio);
    const wRatio = Number(mark.w_ratio);
    const hRatio = Number(mark.h_ratio);
    if (![xRatio, yRatio, wRatio, hRatio].every(Number.isFinite)) {
      continue;
    }
    const left = xRatio * width;
    const top = (1 - yRatio - hRatio) * height;
    const markWidth = wRatio * width;
    const markHeight = hRatio * height;

    if (mark.mark_type === "name") {
      drawNameMark(ctx, mark, left, top, markWidth, markHeight, root);
      continue;
    }
    if (mark.mark_type === "checkmark") {
      drawCheckMark(ctx, left, top, markWidth, markHeight, {
        active: appliesCheckRule(mark, decision),
        label: mark.check_rule === "disagree" ? "비동의" : "동의",
      });
      continue;
    }
    await drawSignatureMark(ctx, left, top, markWidth, markHeight, signatureData);
  }
}

function bindPreviewInputs(root) {
  if (root.dataset.previewInputsBound === "1") {
    return;
  }
  const refresh = () => {
    renderPreviewOverlay(root).catch((error) => {
      console.warn("consent-preview-overlay-refresh-failed", error);
    });
  };
  const decisionName = root.dataset.previewDecisionName || "";
  if (decisionName) {
    document.querySelectorAll(`input[name="${decisionName}"]`).forEach((input) => {
      input.addEventListener("change", refresh);
    });
  }
  const signatureInput = document.getElementById(root.dataset.previewSignatureInputId || "");
  if (signatureInput) {
    signatureInput.addEventListener("input", refresh);
    signatureInput.addEventListener("change", refresh);
  }
  const signerInput = document.getElementById(root.dataset.previewSignerInputId || "");
  if (signerInput) {
    signerInput.addEventListener("input", refresh);
    signerInput.addEventListener("change", refresh);
  }
  document.addEventListener("consent-preview-refresh", refresh);
  root.dataset.previewInputsBound = "1";
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
  const outputScale = window.devicePixelRatio || 1;
  canvas.width = Math.ceil(viewport.width * outputScale);
  canvas.height = Math.ceil(viewport.height * outputScale);
  canvas.style.width = `${Math.ceil(viewport.width)}px`;
  canvas.style.height = `${Math.ceil(viewport.height)}px`;
  const renderContext = canvas.getContext("2d");
  renderContext.setTransform(1, 0, 0, 1, 0, 0);
  renderContext.clearRect(0, 0, canvas.width, canvas.height);
  await page.render({
    canvasContext: renderContext,
    viewport,
    transform: outputScale === 1 ? null : [outputScale, 0, 0, outputScale, 0, 0],
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
  await renderPreviewOverlay(root);
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
  await renderPreviewOverlay(root);
}

async function renderRemotePreview(root) {
  const sourceUrl = root.dataset.sourceUrl || "";
  const fileType = root.dataset.fileType || "";
  const fileName = root.dataset.fileName || "";
  if (!sourceUrl) {
    showPlaceholder(root, "미리보기 주소를 찾지 못했습니다.");
    setStatus(root, "문서 확인");
    return;
  }

  showPlaceholder(root, "문서를 불러오는 중입니다.");
  setStatus(root, "문서 확인 중");
  setMeta(root, [fileName, formatBytes(root.dataset.fileSize)].filter(Boolean).join(" · "));

  try {
    bindPreviewInputs(root);
    if (isPdf(fileType, fileName)) {
      await loadPdfPreview(root, sourceUrl, "remote");
      return;
    }

    await renderImage(root, sourceUrl, fileName);
    setStatus(root, "이미지 문서를 표시했습니다.");
  } catch (error) {
    console.warn("consent-remote-preview-failed", error);
    showPlaceholder(root, "문서를 불러오지 못했습니다.");
    setStatus(root, "문서 확인");
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
      setStatus(root, "파일 확인");
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
