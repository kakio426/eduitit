const DEFAULT_TEMPLATES = {
  parent: {
    title: "학부모 설명회 자료",
    text: [
      "학급 운영 방향",
      "- 아이들이 하루 흐름을 예측할 수 있게 루틴을 고정합니다.",
      "- 수업과 놀이가 균형 있게 이어지도록 시간을 설계합니다.",
      "- 가정과 학교의 소통 내용을 짧고 분명하게 공유합니다.",
      "---",
      "준비물과 약속",
      "- 개인 물통과 실내화를 매일 확인합니다.",
      "- 결석 연락은 오전 8시 40분 전까지 부탁드립니다.",
      "- 알림장과 주간 안내를 함께 확인해 주세요.",
      "---",
      "질문과 마무리",
      "- 발표 후에 질문을 차례대로 받겠습니다.",
      "- 오늘 안내 자료는 다시 열어서 바로 보여드릴 수 있습니다.",
    ].join("\n"),
  },
  class: {
    title: "수업 활동 안내",
    text: [
      "오늘의 배움 목표",
      "- 무엇을 배우는지 한 문장으로 먼저 안내합니다.",
      "- 활동 순서를 짧게 보여 주어 불안을 줄입니다.",
      "---",
      "활동 순서",
      "- 생각 열기",
      "- 친구와 짝 활동",
      "- 전체 나눔",
      "---",
      "준비와 약속",
      "- 발표할 때는 친구 말을 끝까지 듣습니다.",
      "- 활동지를 다 쓰면 조용히 다음 안내를 기다립니다.",
    ].join("\n"),
  },
  meeting: {
    title: "교내 협의회 자료",
    text: [
      "오늘 나눌 안건",
      "- 일정 점검",
      "- 역할 분담",
      "- 전달 사항",
      "---",
      "일정 점검",
      "- 행사 전 준비 일정을 다시 확인합니다.",
      "- 필요한 지원 요청을 정리합니다.",
      "---",
      "정리",
      "- 합의된 내용과 담당자를 마지막에 한 번 더 확인합니다.",
    ].join("\n"),
  },
};

function buildSlides(title, text) {
  const normalizedTitle = (title || "").trim() || "학부모 설명회 자료";
  const normalizedText = (text || "").trim();
  const blocks = normalizedText
    ? normalizedText.split(/\n---\n/g).map((block) => block.trim()).filter(Boolean)
    : [];

  const slides = [
    {
      kind: "cover",
      number: 1,
      title: normalizedTitle,
      paragraphs: ["왼쪽 편집 화면에서 제목과 본문을 바꾼 뒤, 새 탭 발표 화면으로 바로 이어갈 수 있습니다."],
      bullets: ["표지 슬라이드는 발표 시작 문장을 빠르게 잡는 용도로 고정합니다."],
    },
  ];

  blocks.forEach((block, index) => {
    const lines = block
      .split(/\n/g)
      .map((line) => line.trim())
      .filter(Boolean);

    if (!lines.length) {
      return;
    }

    const bullets = [];
    const paragraphs = [];

    lines.slice(1).forEach((line) => {
      if (line.startsWith("- ") || line.startsWith("* ")) {
        bullets.push(line.slice(2).trim());
      } else {
        paragraphs.push(line);
      }
    });

    if (!bullets.length && !paragraphs.length) {
      paragraphs.push("핵심 내용을 한 줄씩 덧붙여 주세요.");
    }

    slides.push({
      kind: "content",
      number: index + 2,
      title: lines[0],
      paragraphs,
      bullets,
    });
  });

  return slides;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderPreview(slides) {
  return slides
    .map((slide) => {
      const paragraphs = slide.paragraphs.length
        ? `
            <div class="mt-4 space-y-2 text-sm md:text-base text-gray-600">
              ${slide.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
            </div>
          `
        : "";

      const bullets = slide.bullets.length
        ? `
            <ul class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2 text-sm md:text-base text-gray-700">
              ${slide.bullets.map((bullet) => `<li class="rounded-2xl bg-slate-50 border border-slate-100 px-4 py-3">${escapeHtml(bullet)}</li>`).join("")}
            </ul>
          `
        : "";

      return `
        <article class="rounded-[1.75rem] border border-white/70 bg-white/80 px-5 py-5 shadow-[0_14px_30px_rgba(148,163,184,0.14)]" data-slide-kind="${slide.kind}">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs uppercase tracking-[0.18em] text-gray-400 mb-2">${slide.kind === "cover" ? "Cover" : `Slide ${slide.number}`}</p>
              <h3 class="text-2xl font-bold text-gray-700 font-title">${escapeHtml(slide.title)}</h3>
            </div>
            <span class="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">${slide.kind === "cover" ? "표지" : "본문"}</span>
          </div>
          ${paragraphs}
          ${bullets}
        </article>
      `;
    })
    .join("");
}

function initSlidesmith() {
  const form = document.getElementById("slidesmith-form");
  if (!form) {
    return;
  }

  const titleInput = document.getElementById("slidesmith-title-input");
  const textInput = document.getElementById("slidesmith-text-input");
  const previewList = document.getElementById("slidesmith-preview-list");
  const slideCount = document.getElementById("slidesmith-slide-count");
  const estimateMinutes = document.getElementById("slidesmith-estimate-minutes");
  const stageSummary = document.getElementById("slidesmith-stage-summary");
  const firstSlide = document.getElementById("slidesmith-first-slide");
  const nextStep = document.getElementById("slidesmith-next-step");
  const previewMeta = document.getElementById("slidesmith-preview-meta");
  const status = document.getElementById("slidesmith-editor-status");
  const presentButton = document.getElementById("slidesmith-present-button");
  const previewButton = document.getElementById("slidesmith-preview-button");
  const templateButtons = Array.from(document.querySelectorAll(".slidesmith-template-button"));

  if (!titleInput || !textInput || !previewList) {
    return;
  }

  let frameHandle = 0;

  const updatePreview = (message) => {
    const slides = buildSlides(titleInput.value, textInput.value);
    previewList.innerHTML = renderPreview(slides);
    if (slideCount) {
      slideCount.textContent = String(slides.length);
    }
    if (estimateMinutes) {
      estimateMinutes.textContent = String(Math.max(slides.length - 1, 3));
    }
    if (stageSummary) {
      stageSummary.textContent = `${slides.length}장의 발표 흐름이 준비되었습니다.`;
    }
    if (firstSlide) {
      firstSlide.textContent = slides[0].title;
    }
    if (previewMeta) {
      previewMeta.textContent = `표지 포함 ${slides.length}장 구성입니다.`;
    }
    if (nextStep) {
      nextStep.textContent = slides.length > 1
        ? "오른쪽 흐름을 확인한 뒤 발표 시작 (새 탭)을 눌러 주세요."
        : "본문을 더 적으면 여러 장의 슬라이드로 나눌 수 있습니다.";
    }
    if (message && status) {
      status.textContent = message;
    }
  };

  const schedulePreview = (message) => {
    window.cancelAnimationFrame(frameHandle);
    frameHandle = window.requestAnimationFrame(() => updatePreview(message));
  };

  titleInput.addEventListener("input", () => {
    schedulePreview("제목 변경 내용이 오른쪽 미리보기에 반영되었습니다.");
  });
  textInput.addEventListener("input", () => {
    schedulePreview("본문 변경 내용이 오른쪽 미리보기에 반영되었습니다.");
  });

  templateButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preset = DEFAULT_TEMPLATES[button.dataset.templateKey];
      if (!preset) {
        return;
      }
      titleInput.value = preset.title;
      textInput.value = preset.text;
      updatePreview(`${button.textContent.trim().split(/\s+/)[0]} 템플릿을 불러왔습니다.`);
      textInput.focus();
      textInput.setSelectionRange(textInput.value.length, textInput.value.length);
    });
  });

  if (previewButton) {
    previewButton.addEventListener("click", () => {
      if (status) {
        status.textContent = "미리보기 새로고침 요청을 처리합니다.";
      }
    });
  }

  if (presentButton) {
    presentButton.addEventListener("click", () => {
      if (status) {
        status.textContent = "새 탭으로 발표 화면을 엽니다.";
      }
    });
  }

  updatePreview("입력한 내용은 오른쪽 슬라이드 미리보기에 바로 반영됩니다.");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSlidesmith);
} else {
  initSlidesmith();
}
