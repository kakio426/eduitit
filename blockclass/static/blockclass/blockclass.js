const BLOCKCLASS_TEMPLATES = {
  sequence: `
    <xml xmlns="https://developers.google.com/blockly/xml">
      <block type="text_print" x="40" y="40">
        <value name="TEXT">
          <shadow type="text">
            <field name="TEXT">준비물을 먼저 확인해요.</field>
          </shadow>
        </value>
        <next>
          <block type="text_print">
            <value name="TEXT">
              <shadow type="text">
                <field name="TEXT">활동 순서를 차례대로 설명해요.</field>
              </shadow>
            </value>
          </block>
        </next>
      </block>
    </xml>
  `,
  if: `
    <xml xmlns="https://developers.google.com/blockly/xml">
      <block type="controls_if" x="40" y="40">
        <mutation else="1"></mutation>
        <value name="IF0">
          <block type="logic_compare">
            <field name="OP">EQ</field>
            <value name="A">
              <shadow type="math_number"><field name="NUM">1</field></shadow>
            </value>
            <value name="B">
              <shadow type="math_number"><field name="NUM">1</field></shadow>
            </value>
          </block>
        </value>
        <statement name="DO0">
          <block type="text_print">
            <value name="TEXT">
              <shadow type="text"><field name="TEXT">조건이 맞으면 활동을 시작해요.</field></shadow>
            </value>
          </block>
        </statement>
        <statement name="ELSE">
          <block type="text_print">
            <value name="TEXT">
              <shadow type="text"><field name="TEXT">다르면 다시 확인해요.</field></shadow>
            </value>
          </block>
        </statement>
      </block>
    </xml>
  `,
  loop: `
    <xml xmlns="https://developers.google.com/blockly/xml">
      <block type="controls_repeat_ext" x="40" y="40">
        <value name="TIMES">
          <shadow type="math_number"><field name="NUM">3</field></shadow>
        </value>
        <statement name="DO">
          <block type="text_print">
            <value name="TEXT">
              <shadow type="text"><field name="TEXT">같은 동작을 반복해요.</field></shadow>
            </value>
          </block>
        </statement>
      </block>
    </xml>
  `,
};

let workspaceSettleTimerId = 0;

function downloadFile(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function safeStatus(message) {
  const status = document.getElementById("blockclass-status");
  if (status) {
    status.textContent = message;
  }
}

function setActiveTemplateButton(activeKey) {
  const buttons = document.querySelectorAll(".blockclass-template-button");
  buttons.forEach((button) => {
    const isActive = button.dataset.templateKey === activeKey;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function clearToolboxSelection(workspace) {
  if (!workspace || typeof workspace.getToolbox !== "function") {
    return;
  }

  const toolbox = workspace.getToolbox();
  if (toolbox && typeof toolbox.clearSelection === "function") {
    toolbox.clearSelection();
  }
}

function shouldPreserveFlyout(target) {
  if (!(target instanceof Element)) {
    return false;
  }

  return Boolean(
    target.closest(
      ".blocklyToolbox, .blocklyToolboxDiv, .blocklyToolboxCategoryContainer, .blocklyToolboxCategory, .blocklyFlyout, .blocklyDropDownDiv, .blocklyWidgetDiv",
    ),
  );
}

function isBlockCreateEvent(event, workspace) {
  if (!event || !workspace || event.workspaceId !== workspace.id) {
    return false;
  }

  const blockCreateType = typeof Blockly !== "undefined" && Blockly.Events && Blockly.Events.BLOCK_CREATE
    ? Blockly.Events.BLOCK_CREATE
    : "create";
  return event.type === blockCreateType;
}

function revealWorkspaceContent(workspace, blockId) {
  if (!workspace || typeof workspace.scrollBoundsIntoView !== "function") {
    return;
  }

  if (blockId && typeof workspace.getBlockById === "function") {
    const block = workspace.getBlockById(blockId);
    if (block && typeof block.getBoundingRectangle === "function") {
      workspace.scrollBoundsIntoView(block.getBoundingRectangle());
      return;
    }
  }

  if (typeof workspace.getBlocksBoundingBox === "function") {
    const bounds = workspace.getBlocksBoundingBox();
    if (bounds && (bounds.top !== bounds.bottom || bounds.left !== bounds.right)) {
      workspace.scrollBoundsIntoView(bounds);
    }
  }
}

function syncWorkspaceViewport(workspace, blockId) {
  window.requestAnimationFrame(() => {
    clearToolboxSelection(workspace);
    stabilizeWorkspace(workspace, { blockId });
  });
}

function resizeWorkspace(workspace) {
  const workspaceElement = document.getElementById("blockclass-workspace");
  if (!workspaceElement || !workspace || typeof Blockly === "undefined") {
    return;
  }

  const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
  const minHeight = isDesktop ? 560 : 460;
  const maxHeight = isDesktop ? 760 : 640;
  const viewportHeight = window.innerHeight || minHeight;
  const ratio = isDesktop ? 0.72 : 0.62;
  const desiredHeight = Math.max(minHeight, Math.min(Math.round(viewportHeight * ratio), maxHeight));

  workspaceElement.style.height = `${desiredHeight}px`;
  Blockly.svgResize(workspace);
  if (typeof workspace.resize === "function") {
    workspace.resize();
  }
}

function scheduleWorkspaceResize(workspace) {
  window.requestAnimationFrame(() => {
    resizeWorkspace(workspace);
    window.requestAnimationFrame(() => {
      resizeWorkspace(workspace);
    });
  });
}

function stabilizeWorkspace(workspace, options = {}) {
  const blockId = options.blockId || null;
  const reveal = options.reveal !== false;

  window.requestAnimationFrame(() => {
    resizeWorkspace(workspace);
    window.requestAnimationFrame(() => {
      resizeWorkspace(workspace);
      if (reveal) {
        revealWorkspaceContent(workspace, blockId);
      }
    });
  });

  window.clearTimeout(workspaceSettleTimerId);
  workspaceSettleTimerId = window.setTimeout(() => {
    resizeWorkspace(workspace);
    if (reveal) {
      revealWorkspaceContent(workspace, blockId);
    }
  }, 120);
}

function observeWorkspaceShell(workspace) {
  const workspaceElement = document.getElementById("blockclass-workspace");
  if (!workspaceElement || typeof ResizeObserver === "undefined") {
    return;
  }

  const observer = new ResizeObserver(() => {
    resizeWorkspace(workspace);
  });
  observer.observe(workspaceElement);
  if (workspaceElement.parentElement) {
    observer.observe(workspaceElement.parentElement);
  }
}

function renderCode(workspace) {
  const codeOutput = document.getElementById("blockclass-code-output");
  const codeSummary = document.getElementById("blockclass-code-summary");
  if (!codeOutput) {
    return;
  }

  let code = "";
  try {
    code = Blockly.JavaScript.workspaceToCode(workspace).trim();
  } catch (error) {
    code = "코드 생성 중 오류가 발생했습니다.";
    safeStatus("코드 생성 중 오류가 발생했습니다. 블록 연결을 다시 확인해 주세요.");
  }

  if (!code) {
    codeOutput.textContent = "블록을 배치하면 코드가 여기에 표시됩니다.";
    if (codeSummary) {
      codeSummary.textContent = "아직 코드가 없습니다. 블록을 하나 더 놓아 보세요.";
    }
    return;
  }

  codeOutput.textContent = code;
  if (codeSummary) {
    codeSummary.textContent = `${code.split("\n").length}줄 코드가 만들어졌습니다.`;
  }
}

function updateSummary(workspace) {
  const blockCount = workspace.getAllBlocks(false).length;
  const topCount = workspace.getTopBlocks(true).length;
  const stageSummary = document.getElementById("blockclass-stage-summary");
  const nextStep = document.getElementById("blockclass-next-step");
  const blockCountEl = document.getElementById("blockclass-block-count");
  const topCountEl = document.getElementById("blockclass-top-count");

  if (blockCountEl) {
    blockCountEl.textContent = String(blockCount);
  }
  if (topCountEl) {
    topCountEl.textContent = String(topCount);
  }
  if (stageSummary) {
    stageSummary.textContent = `${blockCount}개의 블록과 ${topCount}개의 상단 흐름을 배치했습니다.`;
  }
  if (nextStep) {
    nextStep.textContent = blockCount > 0
      ? "블록을 더 정리한 뒤 JSON 저장이나 활동판 저장으로 이어가세요."
      : "왼쪽 템플릿을 먼저 눌러 기본 흐름을 불러오세요.";
  }
  renderCode(workspace);
}

function loadTemplate(workspace, key) {
  const xmlText = BLOCKCLASS_TEMPLATES[key];
  if (!xmlText) {
    safeStatus("템플릿을 찾지 못했습니다.");
    return;
  }

  setActiveTemplateButton(key);
  workspace.clear();
  const xml = Blockly.utils.xml.textToDom(xmlText);
  Blockly.Xml.domToWorkspace(xml, workspace);
  scheduleWorkspaceResize(workspace);
  updateSummary(workspace);
  syncWorkspaceViewport(workspace);
  const labels = {
    sequence: "순서",
    if: "조건",
    loop: "반복",
  };
  safeStatus(`${labels[key]} 템플릿을 불러왔습니다.`);
}

function saveWorkspaceJson(workspace) {
  const data = Blockly.serialization.workspaces.save(workspace);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
  downloadFile("blockclass-workspace.json", blob);
  safeStatus("현재 워크스페이스를 JSON으로 저장했습니다.");
}

function restoreWorkspaceJson(workspace, rawText) {
  let data;
  try {
    data = JSON.parse(rawText);
  } catch (error) {
    window.alert("JSON 파일을 읽지 못했습니다. 다시 선택해 주세요.");
    safeStatus("JSON 파일을 읽지 못했습니다.");
    return;
  }

  workspace.clear();
  Blockly.serialization.workspaces.load(data, workspace);
  scheduleWorkspaceResize(workspace);
  updateSummary(workspace);
  syncWorkspaceViewport(workspace);
  safeStatus("JSON 파일에서 워크스페이스를 불러왔습니다.");
}

function saveWorkspaceSvg(workspace) {
  const svg = workspace.getParentSvg().cloneNode(true);
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  const serializer = new XMLSerializer();
  const blob = new Blob([serializer.serializeToString(svg)], { type: "image/svg+xml;charset=utf-8" });
  downloadFile("blockclass-workspace.svg", blob);
  safeStatus("활동판을 SVG 이미지로 저장했습니다.");
}

function initBlockclass() {
  const workspaceElement = document.getElementById("blockclass-workspace");
  const toolbox = document.getElementById("blockclass-toolbox");
  if (!workspaceElement || !toolbox || typeof Blockly === "undefined") {
    return;
  }

  if (typeof Blockly.setLocale === "function") {
    Blockly.setLocale(Blockly.Msg);
  }

  const workspace = Blockly.inject(workspaceElement, {
    toolbox,
    media: window.BLOCKCLASS_MEDIA_URL,
    trashcan: false,
    sounds: false,
    scrollbars: false,
    renderer: "zelos",
    zoom: {
      controls: false,
      wheel: true,
      startScale: 0.95,
      maxScale: 1.8,
      minScale: 0.5,
      scaleSpeed: 1.1,
    },
    move: {
      scrollbars: false,
      drag: true,
      wheel: true,
    },
  });

  window.blockclassWorkspace = workspace;

  const jsonInput = document.getElementById("blockclass-json-input");
  const saveJsonButton = document.getElementById("blockclass-save-json-button");
  const loadJsonButton = document.getElementById("blockclass-load-json-button");
  const saveImageButton = document.getElementById("blockclass-save-image-button");
  const templateButtons = Array.from(document.querySelectorAll(".blockclass-template-button"));

  templateButtons.forEach((button) => {
    button.addEventListener("click", () => {
      loadTemplate(workspace, button.dataset.templateKey);
    });
  });

  if (saveJsonButton) {
    saveJsonButton.addEventListener("click", () => {
      saveWorkspaceJson(workspace);
    });
  }

  if (loadJsonButton && jsonInput) {
    loadJsonButton.addEventListener("click", () => {
      jsonInput.click();
    });

    jsonInput.addEventListener("change", async (event) => {
      const [file] = event.target.files;
      if (!file) {
        return;
      }
      const rawText = await file.text();
      restoreWorkspaceJson(workspace, rawText);
      jsonInput.value = "";
    });
  }

  if (saveImageButton) {
    saveImageButton.addEventListener("click", () => {
      saveWorkspaceSvg(workspace);
    });
  }

  workspace.addChangeListener((event) => {
    updateSummary(workspace);

    if (isBlockCreateEvent(event, workspace)) {
      syncWorkspaceViewport(workspace, event.blockId);
    }
  });

  workspaceElement.addEventListener("pointerdown", (event) => {
    if (shouldPreserveFlyout(event.target)) {
      return;
    }

    clearToolboxSelection(workspace);
  });

  document.addEventListener("pointerup", (event) => {
    if (!shouldPreserveFlyout(event.target)) {
      return;
    }

    stabilizeWorkspace(workspace, { reveal: false });
  });

  window.addEventListener("resize", () => {
    resizeWorkspace(workspace);
  });

  observeWorkspaceShell(workspace);
  scheduleWorkspaceResize(workspace);
  loadTemplate(workspace, "sequence");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initBlockclass);
} else {
  initBlockclass();
}
