import * as pdfjsLib from "./vendor/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    "./vendor/pdfjs/pdf.worker.min.mjs",
    import.meta.url,
).toString();

const SCALE_STEP = 0.2;
const MIN_SCALE = 0.6;
const MAX_SCALE = 2.4;

function byId(id) {
    return document.getElementById(id);
}

function formatFileSize(size) {
    if (!Number.isFinite(size) || size <= 0) {
        return "";
    }
    if (size >= 1024 * 1024) {
        return `${(size / (1024 * 1024)).toFixed(1)}MB`;
    }
    return `${Math.max(1, Math.round(size / 1024))}KB`;
}

const state = {
    pdfDocument: null,
    currentPage: 1,
    pageCount: 0,
    scale: 1,
    currentBlobUrl: "",
    selectedFileName: "",
    selectedFileSize: 0,
    renderTask: null,
};

const elements = {
    fileInput: byId("docviewer-file-input"),
    dropZone: byId("docviewer-drop-zone"),
    status: byId("docviewer-status"),
    fileMeta: byId("docviewer-file-meta"),
    pageIndicator: byId("docviewer-page-indicator"),
    zoomIndicator: byId("docviewer-zoom-indicator"),
    pageSummary: byId("docviewer-page-summary"),
    scaleSummary: byId("docviewer-scale-summary"),
    nextStep: byId("docviewer-next-step"),
    prevButton: byId("docviewer-prev-button"),
    nextButton: byId("docviewer-next-button"),
    zoomOutButton: byId("docviewer-zoom-out-button"),
    zoomInButton: byId("docviewer-zoom-in-button"),
    resetButton: byId("docviewer-reset-button"),
    printButton: byId("docviewer-print-button"),
    emptyState: byId("docviewer-empty-state"),
    loadingState: byId("docviewer-loading-state"),
    canvasWrap: byId("docviewer-canvas-wrap"),
    canvas: byId("docviewer-canvas"),
};

function setStatus(message, tone = "info") {
    const tones = {
        info: "bg-blue-50 text-blue-700 border-blue-100",
        success: "bg-emerald-50 text-emerald-700 border-emerald-100",
        warning: "bg-amber-50 text-amber-800 border-amber-200",
        error: "bg-red-50 text-red-700 border-red-100",
    };
    const nextTone = tones[tone] || tones.info;
    elements.status.className = `mt-4 rounded-2xl border px-4 py-3 text-sm md:text-base ${nextTone}`;
    elements.status.textContent = message;
}

function setDropZoneActive(active) {
    if (active) {
        elements.dropZone.classList.remove("border-gray-300", "bg-white/75");
        elements.dropZone.classList.add("border-blue-400", "bg-blue-50");
        return;
    }

    elements.dropZone.classList.remove("border-blue-400", "bg-blue-50");
    elements.dropZone.classList.add("border-gray-300", "bg-white/75");
}

function setLoadingState(isLoading) {
    elements.emptyState.classList.toggle("hidden", isLoading || !!state.pdfDocument);
    elements.loadingState.classList.toggle("hidden", !isLoading);
    elements.canvasWrap.classList.toggle("hidden", isLoading || !state.pdfDocument);
}

function updateControls() {
    const hasDocument = Boolean(state.pdfDocument);
    elements.prevButton.disabled = !hasDocument || state.currentPage <= 1;
    elements.nextButton.disabled = !hasDocument || state.currentPage >= state.pageCount;
    elements.zoomOutButton.disabled = !hasDocument || state.scale <= MIN_SCALE;
    elements.zoomInButton.disabled = !hasDocument || state.scale >= MAX_SCALE;
    elements.resetButton.disabled = !hasDocument;
    elements.printButton.disabled = !hasDocument || !state.currentBlobUrl;

    elements.pageIndicator.textContent = `${state.currentPage} / ${state.pageCount}쪽`;
    elements.zoomIndicator.textContent = `${Math.round(state.scale * 100)}%`;

    if (!hasDocument) {
        elements.pageIndicator.textContent = "0 / 0쪽";
        elements.zoomIndicator.textContent = "100%";
        elements.pageSummary.textContent = "문서를 열면 현재 쪽 정보가 보입니다.";
        elements.scaleSummary.textContent = "기본값 100%";
        elements.nextStep.textContent = "먼저 PDF를 선택해 주세요.";
        return;
    }

    elements.pageSummary.textContent = `${state.currentPage}쪽을 보고 있습니다. 총 ${state.pageCount}쪽입니다.`;
    elements.scaleSummary.textContent = `현재 ${Math.round(state.scale * 100)}%로 보고 있습니다.`;
    elements.nextStep.textContent = state.currentPage < state.pageCount
        ? "다음 쪽 버튼으로 이어서 확인하거나 확대해서 자세히 보세요."
        : "검수가 끝났다면 인쇄하기 (새 탭)으로 바로 넘어가세요.";
}

async function renderCurrentPage() {
    if (!state.pdfDocument) {
        return;
    }

    if (state.renderTask) {
        try {
            state.renderTask.cancel();
        } catch (error) {
            console.error("[docviewer] render cancel failed", error);
        }
    }

    const page = await state.pdfDocument.getPage(state.currentPage);
    const viewport = page.getViewport({ scale: state.scale });
    const context = elements.canvas.getContext("2d");
    elements.canvas.width = Math.floor(viewport.width);
    elements.canvas.height = Math.floor(viewport.height);
    elements.canvas.style.width = `${viewport.width}px`;
    elements.canvas.style.height = `${viewport.height}px`;

    state.renderTask = page.render({
        canvasContext: context,
        viewport,
    });

    try {
        await state.renderTask.promise;
    } catch (error) {
        if (error?.name !== "RenderingCancelledException") {
            throw error;
        }
    } finally {
        state.renderTask = null;
    }
}

function resetViewer(message = "PDF를 선택하면 오른쪽에서 바로 확인할 수 있어요.") {
    if (state.currentBlobUrl) {
        URL.revokeObjectURL(state.currentBlobUrl);
    }

    state.pdfDocument = null;
    state.currentPage = 1;
    state.pageCount = 0;
    state.scale = 1;
    state.currentBlobUrl = "";
    state.selectedFileName = "";
    state.selectedFileSize = 0;

    const context = elements.canvas.getContext("2d");
    context.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
    elements.canvas.width = 0;
    elements.canvas.height = 0;
    elements.fileMeta.textContent = "아직 열린 PDF가 없습니다.";
    elements.fileInput.value = "";
    setLoadingState(false);
    setStatus(message, "info");
    updateControls();
}

async function loadPdf(file) {
    if (!file) {
        setStatus("PDF 파일을 선택해 주세요.", "warning");
        return;
    }

    const fileName = (file.name || "").trim();
    if (!fileName.toLowerCase().endsWith(".pdf")) {
        resetViewer("PDF를 다시 선택해 주세요.");
        setStatus("PDF 파일만 선택할 수 있어요. 파일 형식을 다시 확인해 주세요.", "error");
        return;
    }

    setLoadingState(true);
    setStatus("PDF를 열고 있습니다. 첫 페이지를 준비할게요.", "info");

    try {
        const fileBytes = new Uint8Array(await file.arrayBuffer());
        const loadingTask = pdfjsLib.getDocument({ data: fileBytes });
        const pdfDocument = await loadingTask.promise;

        if (state.currentBlobUrl) {
            URL.revokeObjectURL(state.currentBlobUrl);
        }

        state.pdfDocument = pdfDocument;
        state.pageCount = pdfDocument.numPages;
        state.currentPage = 1;
        state.scale = 1;
        state.currentBlobUrl = URL.createObjectURL(file);
        state.selectedFileName = fileName;
        state.selectedFileSize = file.size || 0;

        elements.fileMeta.textContent = `${state.selectedFileName} · ${state.pageCount}쪽 · ${formatFileSize(state.selectedFileSize)}`;
        await renderCurrentPage();
        setLoadingState(false);
        setStatus("PDF를 열었습니다. 오른쪽에서 바로 검수해 보세요.", "success");
        updateControls();
    } catch (error) {
        console.error("[docviewer] failed to load pdf", error);
        resetViewer("PDF를 다시 선택해 주세요.");
        setStatus("PDF를 여는 중 오류가 발생했습니다. 다른 파일인지 다시 확인해 주세요.", "error");
    }
}

async function movePage(direction) {
    if (!state.pdfDocument) {
        return;
    }

    const nextPage = state.currentPage + direction;
    if (nextPage < 1 || nextPage > state.pageCount) {
        return;
    }

    state.currentPage = nextPage;
    setStatus(`${state.currentPage}쪽으로 이동했습니다.`, "info");
    try {
        await renderCurrentPage();
        updateControls();
    } catch (error) {
        console.error("[docviewer] failed to render page", error);
        setStatus("쪽을 바꾸는 중 오류가 발생했습니다. 다시 시도해 주세요.", "error");
    }
}

async function changeScale(direction) {
    if (!state.pdfDocument) {
        return;
    }

    const nextScale = Number((state.scale + direction * SCALE_STEP).toFixed(1));
    if (nextScale < MIN_SCALE || nextScale > MAX_SCALE) {
        return;
    }

    state.scale = nextScale;
    setStatus(`확대 비율을 ${Math.round(state.scale * 100)}%로 바꿨습니다.`, "info");
    try {
        await renderCurrentPage();
        updateControls();
    } catch (error) {
        console.error("[docviewer] failed to update zoom", error);
        setStatus("확대 비율을 바꾸는 중 오류가 발생했습니다. 다시 시도해 주세요.", "error");
    }
}

function printCurrentPdf() {
    if (!state.currentBlobUrl) {
        setStatus("먼저 PDF를 열어 주세요.", "warning");
        return;
    }

    let opened = false;
    const printWindow = window.open(state.currentBlobUrl, "_blank", "noopener,noreferrer");
    if (printWindow) {
        opened = true;
    }

    if (!opened) {
        try {
            const link = document.createElement("a");
            link.href = state.currentBlobUrl;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.style.display = "none";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            opened = true;
        } catch (error) {
            console.error("[docviewer] failed to open print tab", error);
        }
    }

    if (!opened) {
        setStatus("새 탭을 열 수 없습니다. 브라우저 팝업 차단을 확인해 주세요.", "error");
        return;
    }

    setStatus("인쇄용 새 탭을 열었습니다. 브라우저 인쇄 기능을 사용해 주세요.", "success");
}

function bindDragAndDrop() {
    elements.dropZone.addEventListener("dragenter", (event) => {
        event.preventDefault();
        setDropZoneActive(true);
    });
    elements.dropZone.addEventListener("dragover", (event) => {
        event.preventDefault();
        setDropZoneActive(true);
    });
    elements.dropZone.addEventListener("dragleave", (event) => {
        event.preventDefault();
        if (event.currentTarget.contains(event.relatedTarget)) {
            return;
        }
        setDropZoneActive(false);
    });
    elements.dropZone.addEventListener("drop", async (event) => {
        event.preventDefault();
        setDropZoneActive(false);
        const files = event.dataTransfer?.files;
        if (!files || files.length === 0) {
            setStatus("끌어다 놓은 파일이 없습니다. 다시 시도해 주세요.", "warning");
            return;
        }

        const file = files[0];
        try {
            const transfer = new DataTransfer();
            transfer.items.add(file);
            elements.fileInput.files = transfer.files;
        } catch (error) {
            console.error("[docviewer] failed to sync drag drop input", error);
            setStatus("드래그한 파일을 입력창에 연결하지 못했습니다. 파일 선택 버튼으로 다시 시도해 주세요.", "error");
        }
        await loadPdf(file);
    });
}

function bindControls() {
    elements.fileInput.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        await loadPdf(file);
    });
    elements.prevButton.addEventListener("click", async () => {
        await movePage(-1);
    });
    elements.nextButton.addEventListener("click", async () => {
        await movePage(1);
    });
    elements.zoomOutButton.addEventListener("click", async () => {
        await changeScale(-1);
    });
    elements.zoomInButton.addEventListener("click", async () => {
        await changeScale(1);
    });
    elements.resetButton.addEventListener("click", () => {
        resetViewer("다른 PDF를 고를 준비가 됐습니다.");
    });
    elements.printButton.addEventListener("click", () => {
        printCurrentPdf();
    });
}

function init() {
    if (!elements.fileInput || !elements.canvas) {
        return;
    }

    updateControls();
    bindControls();
    bindDragAndDrop();
}

init();
