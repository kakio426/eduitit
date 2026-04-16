"use strict";

function presentResult(detail) {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }
    const shared = window.ppobgiShared;
    if (shared?.openPresentation) {
        shared.openPresentation(detail || {});
        return;
    }
    root.dispatchEvent(new CustomEvent("ppobgi:present", { detail: detail || {} }));
}

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const modeStarsView = document.getElementById("ppb-mode-stars");

    const els = {
        screens: {
            setup: document.getElementById("ppb-setup"),
            universe: document.getElementById("ppb-universe"),
        },
        stars: document.getElementById("ppb-stars"),
        flash: document.getElementById("ppb-flash"),
        particles: document.getElementById("ppb-particles"),
        input: document.getElementById("ppb-name-input"),
        startBtn: document.getElementById("ppb-start-btn"),
        clearInputBtn: document.getElementById("ppb-clear-input-btn"),
        loadSampleBtn: document.getElementById("ppb-load-sample-btn"),
        loadRosterBtn: document.getElementById("ppb-load-roster-btn"),
        statValid: document.getElementById("ppb-stat-valid"),
        statDup: document.getElementById("ppb-stat-dup"),
        statCut: document.getElementById("ppb-stat-cut"),
        setupMessage: document.getElementById("ppb-setup-message"),
        orbGrid: document.getElementById("ppb-orb-grid"),
        chipTotal: document.getElementById("ppb-chip-total"),
        chipLeft: document.getElementById("ppb-chip-left"),
        chipRound: document.getElementById("ppb-chip-round"),
        progressText: document.getElementById("ppb-progress-text"),
        progressBar: document.getElementById("ppb-progress-bar"),
        universeTitle: document.querySelector("#ppb-universe .ppb-universe-title"),
        pickedCard: document.getElementById("ppb-picked-card"),
        pickedName: document.getElementById("ppb-picked-name"),
        resetFromUniverseBtn: document.getElementById("ppb-reset-from-universe-btn"),
        rerollBtn: document.getElementById("ppb-reroll-btn"),
        undoBtn: document.getElementById("ppb-undo-btn"),
        editRosterBtn: document.getElementById("ppb-edit-roster-btn"),
        historyUniverse: document.getElementById("ppb-history-list-universe"),
        liveCard: document.querySelector(".ppb-live-card"),
        liveName: document.getElementById("ppb-live-name"),
        liveMeta: document.getElementById("ppb-live-meta"),
        resultModal: document.getElementById("ppb-result-modal"),
        resultPanel: document.getElementById("ppb-result-panel"),
        resultName: document.getElementById("ppb-result-name"),
        resultMeta: document.getElementById("ppb-result-meta"),
        resultNextBtn: document.getElementById("ppb-result-next-btn"),
        resultFortuneBtn: document.getElementById("ppb-result-fortune-btn"),
        editorOverlay: document.getElementById("ppb-editor-overlay"),
        editorDrawer: document.getElementById("ppb-editor-drawer"),
        editorInput: document.getElementById("ppb-editor-input"),
        editorSummary: document.getElementById("ppb-editor-summary"),
        editorMessage: document.getElementById("ppb-editor-message"),
        editorCloseBtn: document.getElementById("ppb-editor-close-btn"),
        editorCancelBtn: document.getElementById("ppb-editor-cancel-btn"),
        editorSaveBtn: document.getElementById("ppb-editor-save-btn"),
        editorSampleBtn: document.getElementById("ppb-editor-sample-btn"),
        editorRosterBtn: document.getElementById("ppb-editor-roster-btn"),
        reduceMotion: document.getElementById("ppb-reduce-motion"),
        fullscreenBtn: document.getElementById("ppb-fullscreen-btn"),
        toolsLink: document.getElementById("ppb-tools-link"),
        toolsMenu: document.getElementById("ppb-tools-menu"),
    };

    const STAR_COLORS = [
        { core: "rgba(253, 230, 138, 0.98)", glow: "rgba(251, 191, 36, 0.62)" },
        { core: "rgba(191, 219, 254, 0.98)", glow: "rgba(96, 165, 250, 0.56)" },
        { core: "rgba(244, 208, 255, 0.98)", glow: "rgba(216, 180, 254, 0.56)" },
        { core: "rgba(186, 230, 253, 0.98)", glow: "rgba(34, 211, 238, 0.58)" },
        { core: "rgba(255, 255, 255, 0.98)", glow: "rgba(255, 255, 255, 0.5)" },
    ];

    const MAX_NAMES = 40;
    const REDUCE_MOTION_KEY = "ppobgi_reduce_motion";
    const STAR_ROSTER_STORAGE_NAME = "star-roster-v2";

    const state = {
        appState: "setup",
        totalNames: [],
        remainingNames: [],
        history: [],
        selectedName: "",
        transitionLock: false,
        reduceMotion: false,
        resultModalOpen: false,
        editorOpen: false,
        orbLayout: new Map(),
        audioContext: null,
    };

    const AUDIO_CONTEXT_CLASS = window.AudioContext || window.webkitAudioContext || null;

    // Browser-synthesized chimes keep the feature self-contained.
    const STAR_SFX_PATTERNS = {
        launch: [
            { frequency: 523.25, delay: 0, duration: 0.08, gain: 0.035, type: "sine" },
            { frequency: 659.25, delay: 0.09, duration: 0.12, gain: 0.045, type: "triangle" },
        ],
        pick: [
            { frequency: 784, delay: 0, duration: 0.08, gain: 0.045, type: "sine" },
            { frequency: 987.77, delay: 0.09, duration: 0.1, gain: 0.052, type: "triangle" },
            { frequency: 1318.51, delay: 0.2, duration: 0.14, gain: 0.042, type: "sine" },
        ],
        final: [
            { frequency: 659.25, delay: 0, duration: 0.08, gain: 0.05, type: "sine" },
            { frequency: 830.61, delay: 0.1, duration: 0.1, gain: 0.058, type: "triangle" },
            { frequency: 987.77, delay: 0.22, duration: 0.16, gain: 0.065, type: "sine" },
        ],
    };

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw
            .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
            .replace(/\\r\\n/g, "\n")
            .replace(/\\n/g, "\n")
            .replace(/\\r/g, "\n");
    }

    function setScreen(next) {
        state.appState = next;
        Object.entries(els.screens).forEach(([key, screen]) => {
            if (!screen) {
                return;
            }
            screen.classList.toggle("is-hidden", key !== next);
        });
    }

    function normalizeName(name) {
        return String(name || "").replace(/\s+/g, " ").trim();
    }

    function parseNameInput(rawText) {
        const rows = String(rawText || "").split(/\r?\n/);
        const valid = [];
        const dupSet = new Set();
        const seen = new Set();

        rows.forEach((line) => {
            const name = normalizeName(line);
            if (!name) {
                return;
            }
            if (seen.has(name)) {
                dupSet.add(name);
                return;
            }
            seen.add(name);
            valid.push(name);
        });

        const cutCount = Math.max(0, valid.length - MAX_NAMES);
        return {
            valid: valid.slice(0, MAX_NAMES),
            duplicateNames: Array.from(dupSet),
            cutCount,
        };
    }

    function applyMessage(el, text, kind) {
        if (!el) {
            return;
        }
        el.textContent = text || "";
        el.classList.remove("warn", "info");
        if (kind) {
            el.classList.add(kind);
        }
    }

    function setSetupMessage(text, kind) {
        applyMessage(els.setupMessage, text, kind);
    }

    function setEditorMessage(text, kind) {
        applyMessage(els.editorMessage, text, kind);
    }

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function getStarRosterKey() {
        return window.ppobgiShared?.buildScopedStorageKey?.(STAR_ROSTER_STORAGE_NAME)
            || `ppobgi:${STAR_ROSTER_STORAGE_NAME}`;
    }

    function isPresentationOpen() {
        return Boolean(window.ppobgiShared?.isPresentationOpen?.());
    }

    function getAudioContext() {
        if (!AUDIO_CONTEXT_CLASS) {
            return null;
        }
        if (state.audioContext && state.audioContext.state !== "closed") {
            return state.audioContext;
        }
        try {
            state.audioContext = new AUDIO_CONTEXT_CLASS();
        } catch (error) {
            state.audioContext = null;
        }
        return state.audioContext;
    }

    function scheduleTone(context, note, startTime) {
        try {
            const oscillator = context.createOscillator();
            const gainNode = context.createGain();
            const frequency = Math.max(1, Number(note.frequency) || 0);
            const duration = Math.max(0.04, Number(note.duration) || 0.1);
            const gain = Math.max(0.0001, Number(note.gain) || 0.04);
            const attackEnd = startTime + Math.min(0.018, duration * 0.35);

            oscillator.type = note.type || "sine";
            oscillator.frequency.setValueAtTime(frequency, startTime);
            oscillator.frequency.exponentialRampToValueAtTime(frequency * 1.02, startTime + duration);

            gainNode.gain.setValueAtTime(0.0001, startTime);
            gainNode.gain.exponentialRampToValueAtTime(gain, attackEnd);
            gainNode.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

            oscillator.connect(gainNode);
            gainNode.connect(context.destination);
            oscillator.start(startTime);
            oscillator.stop(startTime + duration + 0.05);
            oscillator.addEventListener("ended", () => {
                oscillator.disconnect();
                gainNode.disconnect();
            });
        } catch (error) {
            // Silent fallback if the browser rejects a tone.
        }
    }

    function playStarSfx(kind) {
        const context = getAudioContext();
        if (!context) {
            return;
        }
        if (context.state === "suspended") {
            context.resume().catch(() => {});
        }
        const pattern = STAR_SFX_PATTERNS[kind] || STAR_SFX_PATTERNS.pick;
        const startTime = context.currentTime + 0.01;
        pattern.forEach((note) => {
            scheduleTone(context, note, startTime + (Number(note.delay) || 0));
        });
    }

    function updateSetupStats() {
        if (!els.input) {
            return;
        }
        const parsed = parseNameInput(els.input.value);

        if (els.statValid) {
            els.statValid.textContent = String(parsed.valid.length);
        }
        if (els.statDup) {
            els.statDup.textContent = String(parsed.duplicateNames.length);
        }
        if (els.statCut) {
            els.statCut.textContent = String(parsed.cutCount);
        }

        const messages = [];
        if (parsed.duplicateNames.length > 0) {
            const preview = parsed.duplicateNames.slice(0, 5).join(", ");
            messages.push(`중복 제외: ${preview}${parsed.duplicateNames.length > 5 ? " 외" : ""}`);
        }
        if (parsed.cutCount > 0) {
            messages.push(`최대 ${MAX_NAMES}명 초과로 ${parsed.cutCount}명은 제외됩니다.`);
        }
        if (messages.length === 0) {
            setSetupMessage("유효한 명단 상태입니다.", "info");
        } else {
            setSetupMessage(messages.join(" "), "warn");
        }

        if (els.startBtn) {
            els.startBtn.disabled = parsed.valid.length === 0;
        }
    }

    function updateEditorStats() {
        if (!els.editorInput) {
            return;
        }
        const parsed = parseNameInput(els.editorInput.value);
        if (els.editorSummary) {
            els.editorSummary.textContent = `유효 ${parsed.valid.length}명 / 중복 제외 ${parsed.duplicateNames.length}명 / 초과 제외 ${parsed.cutCount}명`;
        }
        if (els.editorSaveBtn) {
            els.editorSaveBtn.disabled = parsed.valid.length === 0;
        }
        if (parsed.valid.length === 0) {
            setEditorMessage("최소 1명 이상의 이름을 입력해 주세요.", "warn");
            return;
        }
        if (parsed.duplicateNames.length > 0 || parsed.cutCount > 0) {
            setEditorMessage("중복/초과 항목은 저장 시 자동으로 정리됩니다.", "warn");
            return;
        }
        setEditorMessage("저장하면 현재 추첨이 새 명단으로 즉시 다시 시작됩니다.", "info");
    }

    function shuffle(list) {
        const copied = [...list];
        for (let i = copied.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copied[i], copied[j]] = [copied[j], copied[i]];
        }
        return copied;
    }

    function orbFieldSize() {
        const rect = els.orbGrid?.getBoundingClientRect();
        const rawWidth = Math.max(rect?.width || 0, els.orbGrid?.clientWidth || 0, 0);
        const rawHeight = Math.max(rect?.height || 0, els.orbGrid?.clientHeight || 0, 0);
        return {
            width: Math.max(rawWidth, 420),
            height: Math.max(rawHeight, 400),
        };
    }

    function fallbackOrbPosition(index, total, width, height, padding) {
        const safeX = Math.max(width / 2 - padding, 24);
        const safeY = Math.max(height / 2 - padding, 24);
        const ratio = total <= 1 ? 0.2 : 0.2 + (index / Math.max(total - 1, 1)) * 0.72;
        const angle = index * 2.399963229728653;
        const x = width / 2 + Math.cos(angle) * safeX * ratio;
        const y = height / 2 + Math.sin(angle) * safeY * ratio;
        return {
            x: Math.min(width - padding, Math.max(padding, x)),
            y: Math.min(height - padding, Math.max(padding, y)),
        };
    }

    function buildOrbLayout(names) {
        if (!els.orbGrid || !names.length) {
            return new Map();
        }
        const { width, height } = orbFieldSize();
        const padding = Math.max(24, Math.min(width, height) * 0.06);
        const shuffled = shuffle(names);
        const descriptors = shuffled.map((name, index) => {
            const color = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
            const size = Math.max(46, Math.min(84, 88 - shuffled.length * 0.7 + Math.random() * 8));
            const scale = Number((0.92 + Math.random() * 0.18).toFixed(3));
            return {
                name,
                core: color.core,
                glow: color.glow,
                size,
                scale,
                hoverScale: Number((scale * 1.14).toFixed(3)),
                floatScale: Number((scale * 1.025).toFixed(3)),
                delay: Math.random() * 2.4,
                duration: Number((4.2 + Math.random() * 1.6).toFixed(2)),
                floatKey: Math.random() > 0.5 ? "ppb-float" : "ppb-float-reverse",
                rotation: Math.random() * 18 - 9,
                zIndex: 2 + (index % 6),
            };
        });
        const sorted = [...descriptors].sort((a, b) => b.size - a.size);
        const placed = [];

        sorted.forEach((orb, index) => {
            const radius = orb.size * 0.55;
            let coords = null;
            for (let attempt = 0; attempt < 180; attempt += 1) {
                const x = padding + radius + Math.random() * Math.max(width - (padding + radius) * 2, 1);
                const y = padding + radius + Math.random() * Math.max(height - (padding + radius) * 2, 1);
                const blocked = placed.some((item) => {
                    const dx = x - item.x;
                    const dy = y - item.y;
                    const minDist = (radius + item.radius) * 0.78 + 8;
                    return (dx * dx) + (dy * dy) < minDist * minDist;
                });
                if (!blocked) {
                    coords = { x, y };
                    break;
                }
            }
            if (!coords) {
                coords = fallbackOrbPosition(index, sorted.length, width, height, padding + radius);
            }
            placed.push({
                ...orb,
                x: coords.x,
                y: coords.y,
                radius,
            });
        });

        return new Map(placed.map((orb) => [orb.name, orb]));
    }

    function ensureOrbLayout(forceRebuild) {
        if (!state.totalNames.length) {
            state.orbLayout = new Map();
            return;
        }
        const hasAllNames =
            state.orbLayout.size === state.totalNames.length
            && state.totalNames.every((name) => state.orbLayout.has(name));
        if (forceRebuild || !hasAllNames) {
            state.orbLayout = buildOrbLayout(state.totalNames);
        }
    }

    function renderOrbs() {
        if (!els.orbGrid) {
            return;
        }
        ensureOrbLayout(false);
        const missingOrb = state.remainingNames.some((name) => !state.orbLayout.has(name));
        if (missingOrb) {
            state.orbLayout = buildOrbLayout(state.totalNames);
        }
        const orbs = state.remainingNames
            .map((name) => state.orbLayout.get(name))
            .filter(Boolean)
            .sort((a, b) => a.zIndex - b.zIndex);
        if (!orbs.length) {
            const done = document.createElement("div");
            done.className = "ppb-orb-empty";
            done.textContent = "모든 별이 사라졌어요. 같은 명단으로 다시 뽑거나 명단을 수정해 주세요.";
            els.orbGrid.replaceChildren(done);
            return;
        }
        const fragment = document.createDocumentFragment();
        orbs.forEach((orb) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "ppb-orb";
            btn.setAttribute("aria-label", `${orb.name} 선택`);
            btn.style.setProperty("--orb-left", `${orb.x}px`);
            btn.style.setProperty("--orb-top", `${orb.y}px`);
            btn.style.setProperty("--orb-size", `${orb.size}px`);
            btn.style.setProperty("--orb-scale", String(orb.scale));
            btn.style.setProperty("--orb-hover-scale", String(orb.hoverScale));
            btn.style.setProperty("--orb-float-scale", String(orb.floatScale));
            btn.style.setProperty("--orb-core", orb.core);
            btn.style.setProperty("--orb-glow", orb.glow);
            btn.style.setProperty("--orb-delay", `${orb.delay}s`);
            btn.style.setProperty("--orb-duration", `${orb.duration}s`);
            btn.style.setProperty("--orb-float", orb.floatKey);
            btn.style.setProperty("--orb-rotation", `${orb.rotation}deg`);
            btn.style.zIndex = String(orb.zIndex);
            btn.innerHTML = '<span class="ppb-orb-core" aria-hidden="true"></span>';
            btn.addEventListener("click", () => handleOrbClick(orb.name, btn));
            fragment.appendChild(btn);
        });
        els.orbGrid.replaceChildren(fragment);
    }
    function renderHistory() {
        if (!els.historyUniverse) {
            return;
        }
        if (state.history.length === 0) {
            const empty = document.createElement("li");
            empty.innerHTML = '<span class="ppb-history-round">기록 없음</span><span class="ppb-history-name">-</span>';
            els.historyUniverse.replaceChildren(empty);
            return;
        }
        const fragment = document.createDocumentFragment();
        state.history.forEach((item) => {
            const li = document.createElement("li");
            li.innerHTML = `<span class="ppb-history-round">${item.round}회차</span><span class="ppb-history-name">${item.name}</span>`;
            fragment.appendChild(li);
        });
        els.historyUniverse.replaceChildren(fragment);
    }

    function updateCounterUI() {
        const total = state.totalNames.length;
        const left = state.remainingNames.length;
        const round = state.history.length;
        const done = Math.max(0, total - left);
        const percent = total > 0 ? Math.round((done / total) * 100) : 0;

        if (els.chipTotal) {
            els.chipTotal.textContent = String(total);
        }
        if (els.chipLeft) {
            els.chipLeft.textContent = String(left);
        }
        if (els.chipRound) {
            els.chipRound.textContent = String(round);
        }
        if (els.progressText) {
            els.progressText.textContent = `${percent}%`;
        }
        if (els.progressBar) {
            els.progressBar.style.width = `${percent}%`;
        }
        if (els.undoBtn) {
            els.undoBtn.disabled = round === 0;
        }
        if (els.rerollBtn) {
            els.rerollBtn.disabled = total === 0;
        }
        if (els.universeTitle) {
            els.universeTitle.textContent = total > 0 && left === 0
                ? "완료"
                : "별빛";
        }
    }

    function renderParticles() {
        if (!els.particles) {
            return;
        }
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < 18; i += 1) {
            const particle = document.createElement("span");
            particle.className = "ppb-particle";
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.animationDuration = `${Math.random() * 2 + 2.4}s`;
            particle.style.animationDelay = `${Math.random() * 0.3}s`;
            fragment.appendChild(particle);
        }
        els.particles.replaceChildren(fragment);
        window.setTimeout(() => {
            els.particles?.replaceChildren();
        }, state.reduceMotion ? 220 : 900);
    }

    function createStars() {
        if (!els.stars) {
            return;
        }
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < 150; i += 1) {
            const star = document.createElement("span");
            star.className = "ppb-star";
            const size = Math.random() * 2.4 + 0.5;
            star.style.left = `${Math.random() * 100}%`;
            star.style.top = `${Math.random() * 100}%`;
            star.style.width = `${size}px`;
            star.style.height = `${size}px`;
            star.style.opacity = String(Math.random() * 0.56 + 0.08);
            star.style.animationDuration = `${3 + Math.random() * 4.5}s`;
            star.style.animationDelay = `${Math.random() * 6}s`;
            fragment.appendChild(star);
        }
        els.stars.replaceChildren(fragment);
    }

    function setLiveCard(name, meta) {
        if (els.liveName) {
            els.liveName.textContent = name || "대기";
        }
        if (els.liveMeta) {
            els.liveMeta.textContent = meta || "";
        }
        els.liveCard?.classList.toggle("is-selected", Boolean(name));
    }

    function setPickedPanel(name) {
        const pickedName = normalizeName(name);
        if (els.pickedName) {
            els.pickedName.textContent = pickedName || "대기";
        }
        els.pickedCard?.classList.toggle("is-picked", Boolean(pickedName));
    }

    function focusFirstOrb() {
        const orb = els.orbGrid?.querySelector(".ppb-orb:not(:disabled)");
        orb?.focus();
    }

    function closeResultModal(shouldFocus = true) {
        if (!isPresentationOpen()) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:close-presentation"));
        state.resultModalOpen = false;
        if (shouldFocus && state.appState === "universe") {
            focusFirstOrb();
        }
    }

    function openResultModal(name, leftCount) {
        const pickedName = normalizeName(name) || "이름 없음";
        state.resultModalOpen = true;
        presentResult({
            badge: leftCount > 0 ? "오늘의 별빛 주인공" : "별빛 피날레 주인공",
            celebration: leftCount > 0 ? "reveal" : "finale",
            compliment: leftCount > 0
                ? "무대 조명이 이 학생에게 딱 멈추며 분위기가 환하게 살아났어요."
                : "마지막 별빛까지 환하게 마무리됐어요. 오늘 무대의 피날레를 크게 축하합니다.",
            fortuneTarget: {
                sourceLabel: "별빛 추첨 결과",
                targetName: pickedName,
            },
            label: leftCount > 0 ? "방금 뽑힌 학생" : "오늘의 마지막 별빛",
            meta: leftCount > 0 ? `남은 인원 ${leftCount}명` : "모든 학생 추첨 완료",
            mode: "stars",
            nextLabel: leftCount > 0 ? "다음 추첨 계속" : "닫기",
            sourceLabel: "별빛 추첨 결과",
            winnerName: pickedName,
        });
    }

    function persistRoster(names) {
        try {
            window.localStorage.setItem(getStarRosterKey(), JSON.stringify(names));
        } catch (error) {
            // noop
        }
    }

    function loadStoredRoster() {
        try {
            const raw = window.localStorage.getItem(getStarRosterKey());
            if (!raw) {
                return [];
            }
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            const normalized = parseNameInput(parsed.join("\n"));
            return normalized.valid;
        } catch (error) {
            return [];
        }
    }

    function applyRosterAndStart(names, message) {
        state.totalNames = [...names];
        state.remainingNames = [...names];
        state.history = [];
        state.selectedName = "";
        state.transitionLock = false;
        state.orbLayout = new Map();
        if (els.input) {
            els.input.value = names.join("\n");
        }
        setScreen("universe");
        state.orbLayout = buildOrbLayout(names);
        updateSetupStats();
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard("", "");
        setPickedPanel("");
        closeResultModal(false);
        if (message) {
            setSetupMessage(message, "info");
        }
        persistRoster(names);
    }
    function startDraw() {
        if (!els.input) {
            return;
        }
        const parsed = parseNameInput(els.input.value);
        if (parsed.valid.length === 0) {
            window.alert("이름을 최소 1명 이상 입력해 주세요.");
            els.input.focus();
            return;
        }
        applyRosterAndStart(parsed.valid);
        dispatchSfx("launch");
    }

    function handleOrbClick(name, clickedBtn) {
        if (state.transitionLock || state.appState !== "universe") {
            return;
        }
        state.transitionLock = true;
        state.selectedName = name;

        const removeIndex = state.remainingNames.indexOf(name);
        if (removeIndex !== -1) {
            state.remainingNames.splice(removeIndex, 1);
        }
        state.history.unshift({
            round: state.history.length + 1,
            name,
        });

        updateCounterUI();
        renderHistory();
        renderParticles();
        const left = state.remainingNames.length;
        setLiveCard(name, "");
        setPickedPanel(name);
        openResultModal(name, left);

        if (els.flash) {
            els.flash.style.opacity = state.reduceMotion ? "0.4" : "0.8";
        }
        if (clickedBtn) {
            clickedBtn.classList.add("is-picked");
            clickedBtn.disabled = true;
            window.setTimeout(() => {
                clickedBtn.remove();
            }, state.reduceMotion ? 90 : 420);
        }

        window.setTimeout(() => {
            if (els.flash) {
                els.flash.style.opacity = "0";
            }
            state.transitionLock = false;
        }, state.reduceMotion ? 130 : 480);
    }

    function rerollCurrentRoster() {
        if (!state.totalNames.length) {
            return;
        }
        state.remainingNames = [...state.totalNames];
        state.history = [];
        state.selectedName = "";
        state.transitionLock = false;
        state.orbLayout = buildOrbLayout(state.totalNames);
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard("", "");
        setPickedPanel("");
        closeResultModal(false);
    }
    function undoLastDraw() {
        if (state.transitionLock || state.history.length === 0) {
            return;
        }
        const recent = state.history.shift();
        if (!recent) {
            return;
        }
        state.remainingNames.push(recent.name);
        state.selectedName = "";
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard(state.history[0]?.name || "", "");
        setPickedPanel(state.history[0]?.name || "");
        dispatchSfx("undo");
        closeResultModal(false);
    }

    function goSetupScreen() {
        if (els.input && state.totalNames.length) {
            els.input.value = state.totalNames.join("\n");
        }
        updateSetupStats();
        closeResultModal(false);
        setScreen("setup");
    }

    function openEditor() {
        if (!els.editorOverlay || !els.editorDrawer || !els.editorInput) {
            return;
        }
        const namesForEditor = state.totalNames.length
            ? state.totalNames
            : parseNameInput(els.input?.value || "").valid;
        els.editorInput.value = namesForEditor.join("\n");
        updateEditorStats();
        els.editorOverlay.classList.remove("is-hidden");
        els.editorDrawer.classList.remove("is-hidden");
        els.editorOverlay.setAttribute("aria-hidden", "false");
        els.editorDrawer.setAttribute("aria-hidden", "false");
        root.classList.add("ppb-editor-open");
        state.editorOpen = true;
        els.editorInput.focus();
    }

    function closeEditor() {
        if (!els.editorOverlay || !els.editorDrawer) {
            return;
        }
        els.editorOverlay.classList.add("is-hidden");
        els.editorDrawer.classList.add("is-hidden");
        els.editorOverlay.setAttribute("aria-hidden", "true");
        els.editorDrawer.setAttribute("aria-hidden", "true");
        root.classList.remove("ppb-editor-open");
        state.editorOpen = false;
        els.editRosterBtn?.focus();
    }

    function saveEditedRoster() {
        if (!els.editorInput) {
            return;
        }
        const parsed = parseNameInput(els.editorInput.value);
        if (parsed.valid.length === 0) {
            setEditorMessage("최소 1명 이상의 이름을 입력해 주세요.", "warn");
            els.editorInput.focus();
            return;
        }
        closeEditor();
        applyRosterAndStart(parsed.valid);
        setLiveCard("", "");
    }

    async function loadRosterNames(target) {
        const rosterUrl = root.dataset.rosterUrl || "";
        const isEditor = target === "editor";
        const targetInput = isEditor ? els.editorInput : els.input;
        const targetBtn = isEditor ? els.editorRosterBtn : els.loadRosterBtn;
        if (!rosterUrl || !targetInput) {
            return;
        }
        if (targetBtn) {
            targetBtn.disabled = true;
            targetBtn.textContent = "명단 불러오는 중...";
        }
        try {
            const response = await window.fetch(rosterUrl, { credentials: "same-origin" });
            if (!response.ok) {
                throw new Error("명단을 가져오지 못했습니다.");
            }
            const data = await response.json();
            const names = Array.isArray(data.names) ? data.names : [];
            if (!names.length) {
                if (isEditor) {
                    setEditorMessage("등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
                } else {
                    setSetupMessage("등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
                }
                return;
            }
            targetInput.value = names.join("\n");
            if (isEditor) {
                updateEditorStats();
                setEditorMessage(`당번 명단 ${names.length}명을 불러왔습니다.`, "info");
            } else {
                updateSetupStats();
                setSetupMessage(`당번 명단 ${names.length}명을 불러왔습니다.`, "info");
            }
        } catch (error) {
            if (isEditor) {
                setEditorMessage("명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
            } else {
                setSetupMessage("명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
            }
        } finally {
            if (targetBtn) {
                targetBtn.disabled = false;
                targetBtn.textContent = "당번 명단";
            }
        }
    }

    function applyReduceMotion(enabled) {
        state.reduceMotion = enabled;
        root.classList.toggle("ppb-reduce-motion", enabled);
        try {
            window.localStorage.setItem(REDUCE_MOTION_KEY, enabled ? "1" : "0");
        } catch (error) {
            // noop
        }
    }

    function getStoredReduceMotion() {
        try {
            return window.localStorage.getItem(REDUCE_MOTION_KEY) === "1";
        } catch (error) {
            return false;
        }
    }

    function toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen?.();
            return;
        }
        document.exitFullscreen?.();
    }

    function syncFullscreenBtn() {
        if (!els.fullscreenBtn) {
            return;
        }
        root.classList.toggle("ppb-is-fullscreen", Boolean(document.fullscreenElement));
        els.fullscreenBtn.textContent = document.fullscreenElement ? "전체화면 종료" : "전체화면";
    }

    function closeToolsMenu() {
        if (!els.toolsMenu || !els.toolsMenu.open) {
            return;
        }
        els.toolsMenu.open = false;
    }

    function isStarsModeActive() {
        return !modeStarsView?.classList.contains("is-hidden");
    }

    function drawByKeyboard() {
        if (!isStarsModeActive() || state.appState !== "universe" || state.transitionLock || state.resultModalOpen) {
            return;
        }
        const choices = Array.from(els.orbGrid?.querySelectorAll(".ppb-orb") || []).filter((btn) => !btn.disabled);
        if (!choices.length) {
            return;
        }
        const target = choices[Math.floor(Math.random() * choices.length)];
        target.click();
    }

    let orbLayoutFrame = 0;

    function scheduleOrbLayoutRefresh() {
        if (orbLayoutFrame) {
            window.cancelAnimationFrame(orbLayoutFrame);
        }
        orbLayoutFrame = window.requestAnimationFrame(() => {
            orbLayoutFrame = 0;
            if (state.appState !== "universe" || !isStarsModeActive() || !state.totalNames.length) {
                return;
            }
            state.orbLayout = buildOrbLayout(state.totalNames);
            renderOrbs();
        });
    }

    function openFortuneFromSelected() {
        if (!state.selectedName) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", {
            detail: {
                targetName: state.selectedName,
                sourceLabel: "별빛 추첨 결과",
            },
        }));
    }

    function handleKeydown(event) {
        if (!isStarsModeActive()) {
            return;
        }
        if (state.editorOpen) {
            if (event.key === "Escape") {
                event.preventDefault();
                closeEditor();
            }
            return;
        }
        if (root.classList.contains("ppb-fortune-open")) {
            return;
        }
        if (isPresentationOpen()) {
            if (event.key === "Escape") {
                event.preventDefault();
                closeResultModal();
            }
            return;
        }
        const tagName = String(event.target?.tagName || "").toUpperCase();
        const typing = tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT" || Boolean(event.target?.isContentEditable);
        if (typing) {
            return;
        }
        if (state.appState === "universe" && event.code === "Space") {
            event.preventDefault();
            drawByKeyboard();
            return;
        }
        if (state.appState === "universe" && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
            event.preventDefault();
            undoLastDraw();
            return;
        }
    }

    function bindEvents() {
        els.input?.addEventListener("input", updateSetupStats);
        els.startBtn?.addEventListener("click", startDraw);
        els.clearInputBtn?.addEventListener("click", () => {
            if (els.input) {
                els.input.value = "";
            }
            updateSetupStats();
            setSetupMessage("입력이 비워졌습니다.", "info");
        });
        els.loadSampleBtn?.addEventListener("click", () => {
            if (els.input) {
                els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            }
            updateSetupStats();
            setSetupMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", () => loadRosterNames("setup"));
        els.resetFromUniverseBtn?.addEventListener("click", goSetupScreen);
        els.rerollBtn?.addEventListener("click", rerollCurrentRoster);
        els.undoBtn?.addEventListener("click", undoLastDraw);
        els.editRosterBtn?.addEventListener("click", openEditor);
        root.addEventListener("ppobgi:presentation-closed", () => {
            state.resultModalOpen = false;
            if (state.appState === "universe" && isStarsModeActive()) {
                focusFirstOrb();
            }
        });

        els.editorOverlay?.addEventListener("click", closeEditor);
        els.editorCloseBtn?.addEventListener("click", closeEditor);
        els.editorCancelBtn?.addEventListener("click", closeEditor);
        els.editorInput?.addEventListener("input", updateEditorStats);
        els.editorSaveBtn?.addEventListener("click", saveEditedRoster);
        els.editorSampleBtn?.addEventListener("click", () => {
            if (!els.editorInput) {
                return;
            }
            els.editorInput.value = decodeDefaultNames(root.dataset.defaultNames || "");
            updateEditorStats();
            setEditorMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.editorRosterBtn?.addEventListener("click", () => loadRosterNames("editor"));

        els.reduceMotion?.addEventListener("change", (event) => {
            applyReduceMotion(Boolean(event.target.checked));
            closeToolsMenu();
        });
        els.fullscreenBtn?.addEventListener("click", () => {
            toggleFullscreen();
            window.setTimeout(closeToolsMenu, 0);
        });
        els.toolsLink?.addEventListener("click", closeToolsMenu);
        document.addEventListener("fullscreenchange", syncFullscreenBtn);
        document.addEventListener("fullscreenchange", scheduleOrbLayoutRefresh);
        document.addEventListener("keydown", handleKeydown);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeToolsMenu();
            }
        });
        document.addEventListener("click", (event) => {
            if (els.toolsMenu?.open && !els.toolsMenu.contains(event.target)) {
                closeToolsMenu();
            }
        });
        window.addEventListener("resize", scheduleOrbLayoutRefresh);
        root.addEventListener("ppobgi:close-tools", closeToolsMenu);
        root.addEventListener("ppobgi:mode-change", (event) => {
            if (event.detail?.mode === "stars") {
                scheduleOrbLayoutRefresh();
            }
        });
    }
    function bootstrap() {
        if (els.input) {
            els.input.value = "";
        }
        createStars();
        bindEvents();
        const reduceMotion = getStoredReduceMotion();
        if (els.reduceMotion) {
            els.reduceMotion.checked = reduceMotion;
        }
        applyReduceMotion(reduceMotion);
        setScreen("setup");
        updateSetupStats();
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard("", "");
        setPickedPanel("");
        closeResultModal(false);
        syncFullscreenBtn();

        const stored = root.dataset.classroomUrl ? [] : loadStoredRoster();
        if (stored.length > 0) {
            applyRosterAndStart(stored, `저장된 명단 ${stored.length}명을 불러왔습니다.`);
        } else {
            setSetupMessage("명단을 입력하거나 당번 명단을 불러오세요.", "info");
        }
    }

    bootstrap();
})();
(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const shared = window.ppobgiShared || null;
    const modeLadder = document.getElementById("ppb-mode-ladder");

    const els = {
        setupScreen: document.getElementById("pbl-setup"),
        stageScreen: document.getElementById("pbl-stage"),
        input: document.getElementById("pbl-name-input"),
        roleWrap: document.getElementById("pbl-role-wrap"),
        roleInput: document.getElementById("pbl-role-input"),
        modeRadios: Array.from(document.querySelectorAll('input[name="pbl-mode"]')),
        loadSampleBtn: document.getElementById("pbl-load-sample-btn"),
        loadRosterBtn: document.getElementById("pbl-load-roster-btn"),
        clearInputBtn: document.getElementById("pbl-clear-input-btn"),
        startBtn: document.getElementById("pbl-start-btn"),
        setupMessage: document.getElementById("pbl-setup-message"),
        stageMessage: document.getElementById("pbl-stage-message"),
        stageTitle: document.getElementById("pbl-stage-title"),
        topRow: document.getElementById("pbl-top-row"),
        bottomRow: document.getElementById("pbl-bottom-row"),
        svg: document.getElementById("pbl-svg"),
        statValid: document.getElementById("pbl-stat-valid"),
        statRoles: document.getElementById("pbl-stat-roles"),
        statPlan: document.getElementById("pbl-stat-plan"),
        chipTotal: document.getElementById("pbl-chip-total"),
        chipRevealed: document.getElementById("pbl-chip-revealed"),
        chipLeft: document.getElementById("pbl-chip-left"),
        autoBtn: document.getElementById("pbl-auto-btn"),
        rerollBtn: document.getElementById("pbl-reroll-btn"),
        resetBtn: document.getElementById("pbl-reset-btn"),
        liveCard: document.querySelector(".pbl-live-card"),
        liveName: document.getElementById("pbl-live-name"),
        liveRole: document.getElementById("pbl-live-role"),
        liveSparks: document.getElementById("pbl-live-sparks"),
        revealList: document.getElementById("pbl-reveal-list"),
    };

    if (!modeLadder || !els.setupScreen || !els.stageScreen) {
        return;
    }

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw
            .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
            .replace(/\\r\\n/g, "\n")
            .replace(/\\n/g, "\n")
            .replace(/\\r/g, "\n");
    }

    const MAX_LADDER_NAMES = 24;
    const DEFAULT_ROLES = ["발표자", "칠판 정리", "자료 배부", "질문 리더", "피드백 리더"].join("\n");
    const LADDER_VIEW = { width: 1200, height: 680, topY: 70, bottomY: 610, leftX: 70, rightX: 1130 };

    const state = {
        mode: "single",
        scene: null,
        roles: [],
        revealedTop: new Set(),
        revealedBottom: new Set(),
        feed: [],
        animating: false,
        autoRun: false,
        activePath: null,
    };

    function isReducedMotion() {
        return root.classList.contains("ppb-reduce-motion");
    }

    function requestMode(mode) {
        shared?.requestModeChange?.(mode);
    }

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function setLadderScreen(next) {
        els.setupScreen.classList.toggle("is-hidden", next !== "setup");
        els.stageScreen.classList.toggle("is-hidden", next !== "stage");
    }

    function setMessage(target, text, kind) {
        if (!target) return;
        target.textContent = text;
        target.classList.remove("warn", "info");
        if (kind) target.classList.add(kind);
    }

    function parseUniqueLines(raw, maxCount) {
        const rows = (raw || "").split(/\r?\n/);
        const valid = [];
        const seen = new Set();
        const duplicate = new Set();
        rows.forEach((line) => {
            const v = line.replace(/\s+/g, " ").trim();
            if (!v) return;
            if (seen.has(v)) {
                duplicate.add(v);
                return;
            }
            seen.add(v);
            valid.push(v);
        });
        return {
            valid: valid.slice(0, maxCount),
            duplicate: Array.from(duplicate),
            cut: Math.max(0, valid.length - maxCount),
        };
    }

    function shuffle(list) {
        const out = [...list];
        for (let i = out.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [out[i], out[j]] = [out[j], out[i]];
        }
        return out;
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function pickedMode() {
        const selected = els.modeRadios.find((radio) => radio.checked);
        return selected ? selected.value : "single";
    }

    function syncRoleWrap() {
        state.mode = pickedMode();
        const disabled = state.mode === "single";
        if (els.roleWrap) {
            els.roleWrap.hidden = disabled;
            els.roleWrap.classList.toggle("is-disabled", disabled);
            els.roleWrap.setAttribute("aria-hidden", disabled ? "true" : "false");
        }
        if (els.roleInput) {
            els.roleInput.disabled = disabled;
        }
    }

    function updateSetupStats() {
        const participants = parseUniqueLines(els.input?.value || "", MAX_LADDER_NAMES);
        const roles = parseUniqueLines(els.roleInput?.value || "", MAX_LADDER_NAMES);
        const mode = pickedMode();

        if (els.statValid) els.statValid.textContent = String(participants.valid.length);
        if (els.statRoles) els.statRoles.textContent = String(mode === "single" ? 1 : roles.valid.length);
        if (els.statPlan) els.statPlan.textContent = String(participants.valid.length);

        const warnings = [];
        if (participants.duplicate.length) warnings.push(`중복 ${participants.duplicate.length}명 제외`);
        if (participants.cut) warnings.push(`최대 ${MAX_LADDER_NAMES}명 초과 ${participants.cut}명 제외`);
        if (mode === "roles" && !roles.valid.length) warnings.push("역할 1개 이상 입력 필요");
        if (mode === "roles" && roles.valid.length > participants.valid.length) warnings.push("초과 역할은 자동 제외");

        setMessage(
            els.setupMessage,
            warnings.length ? warnings.join(" / ") : "",
            warnings.length ? "warn" : null,
        );

        const valid = participants.valid.length >= 2 && (mode === "single" || roles.valid.length > 0);
        if (els.startBtn) els.startBtn.disabled = !valid;
    }

    function ladderColumns(count) {
        if (count <= 1) return [LADDER_VIEW.leftX];
        const gap = (LADDER_VIEW.rightX - LADDER_VIEW.leftX) / (count - 1);
        return Array.from({ length: count }, (_, i) => LADDER_VIEW.leftX + gap * i);
    }

    function ladderRows(rows) {
        const gap = (LADDER_VIEW.bottomY - LADDER_VIEW.topY) / (rows + 1);
        return Array.from({ length: rows }, (_, i) => LADDER_VIEW.topY + gap * (i + 1));
    }

    function ladderMatrix(cols, rows, density) {
        const out = [];
        for (let r = 0; r < rows; r += 1) {
            const edge = Array(Math.max(0, cols - 1)).fill(false);
            let prev = false;
            for (let c = 0; c < edge.length; c += 1) {
                if (prev) {
                    edge[c] = false;
                    prev = false;
                    continue;
                }
                const on = Math.random() < density;
                edge[c] = on;
                prev = on;
            }
            out.push(edge);
        }
        return out;
    }

    function tracePath(scene, startIndex) {
        let col = startIndex;
        let x = scene.colX[col];
        let y = LADDER_VIEW.topY;
        const points = [[x, y]];
        for (let r = 0; r < scene.rowY.length; r += 1) {
            const yRow = scene.rowY[r];
            if (y !== yRow) {
                points.push([x, yRow]);
                y = yRow;
            }
            if (col > 0 && scene.matrix[r][col - 1]) {
                col -= 1;
                x = scene.colX[col];
                points.push([x, y]);
            } else if (col < scene.colX.length - 1 && scene.matrix[r][col]) {
                col += 1;
                x = scene.colX[col];
                points.push([x, y]);
            }
        }
        if (y !== LADDER_VIEW.bottomY) points.push([x, LADDER_VIEW.bottomY]);
        return { end: col, points };
    }

    function buildScene(participants, mode, roles) {
        const rows = Math.max(9, Math.min(18, Math.round(participants.length * 0.8 + 4)));
        const matrix = ladderMatrix(participants.length, rows, 0.43);
        const colX = ladderColumns(participants.length);
        const rowY = ladderRows(rows);
        let outcomes;
        if (mode === "single") {
            outcomes = Array(participants.length).fill("다음 기회");
            outcomes[Math.floor(Math.random() * participants.length)] = "당첨";
        } else {
            outcomes = roles.slice(0, participants.length);
            while (outcomes.length < participants.length) outcomes.push("대기");
            outcomes = shuffle(outcomes);
        }
        const scene = { participants, outcomes, matrix, colX, rowY, maps: [] };
        scene.maps = participants.map((_, i) => tracePath(scene, i));
        return scene;
    }

    function svgLine(x1, y1, x2, y2, cls) {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", String(x1));
        line.setAttribute("y1", String(y1));
        line.setAttribute("x2", String(x2));
        line.setAttribute("y2", String(y2));
        line.setAttribute("class", cls);
        return line;
    }

    function drawGrid() {
        const scene = state.scene;
        if (!scene || !els.svg) return;
        els.svg.setAttribute("viewBox", `0 0 ${LADDER_VIEW.width} ${LADDER_VIEW.height}`);
        els.svg.replaceChildren();
        scene.colX.forEach((x) => els.svg.appendChild(svgLine(x, LADDER_VIEW.topY, x, LADDER_VIEW.bottomY, "pbl-line-v")));
        scene.rowY.forEach((y, r) => {
            for (let c = 0; c < scene.matrix[r].length; c += 1) {
                if (scene.matrix[r][c]) els.svg.appendChild(svgLine(scene.colX[c], y, scene.colX[c + 1], y, "pbl-line-h"));
            }
        });
        state.activePath = null;
    }

    function drawNodes() {
        const scene = state.scene;
        if (!scene || !els.topRow || !els.bottomRow) return;
        const count = scene.participants.length;
        const cols = `repeat(${count}, minmax(0, 1fr))`;
        els.topRow.style.gridTemplateColumns = cols;
        els.bottomRow.style.gridTemplateColumns = cols;
        els.topRow.classList.remove("is-compact", "is-dense");
        els.bottomRow.classList.remove("is-compact", "is-dense");
        if (count >= 18) {
            els.topRow.classList.add("is-dense");
            els.bottomRow.classList.add("is-dense");
        } else if (count >= 13) {
            els.topRow.classList.add("is-compact");
            els.bottomRow.classList.add("is-compact");
        }

        const topFrag = document.createDocumentFragment();
        scene.participants.forEach((name, i) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "pbl-top-node";
            if (state.revealedTop.has(i)) btn.classList.add("is-revealed");
            btn.dataset.index = String(i);
            btn.innerHTML = `<span class="pbl-node-index">${i + 1}번</span><span class="pbl-node-name">${name}</span>`;
            topFrag.appendChild(btn);
        });
        els.topRow.replaceChildren(topFrag);

        const bottomFrag = document.createDocumentFragment();
        scene.outcomes.forEach((outcome, i) => {
            const div = document.createElement("div");
            div.className = "pbl-bottom-node";
            if (!state.revealedBottom.has(i)) {
                div.classList.add("is-hidden-result");
                div.textContent = "?";
            } else {
                div.classList.add("is-revealed");
                if (outcome === "당첨") div.classList.add("is-prize");
                div.textContent = outcome;
            }
            bottomFrag.appendChild(div);
        });
        els.bottomRow.replaceChildren(bottomFrag);
    }

    function updateCounters() {
        const scene = state.scene;
        if (!scene) return;
        const total = scene.participants.length;
        const revealed = state.revealedTop.size;
        if (els.chipTotal) els.chipTotal.textContent = String(total);
        if (els.chipRevealed) els.chipRevealed.textContent = String(revealed);
        if (els.chipLeft) els.chipLeft.textContent = String(total - revealed);
    }

    function renderFeed() {
        if (!els.revealList) return;
        if (!state.feed.length) {
            const li = document.createElement("li");
            li.innerHTML = '<span class="pbl-reveal-main">아직 발표가 없습니다.</span>';
            els.revealList.replaceChildren(li);
            return;
        }
        const frag = document.createDocumentFragment();
        state.feed.forEach((item) => {
            const li = document.createElement("li");
            li.innerHTML = `<span class="pbl-reveal-step">${item.step}번째 발표</span><span class="pbl-reveal-main">${item.name}</span><span class="pbl-reveal-outcome">→ ${item.outcome}</span>`;
            frag.appendChild(li);
        });
        els.revealList.replaceChildren(frag);
    }

    function unresolvedIndexes() {
        const scene = state.scene;
        if (!scene) return [];
        const out = [];
        for (let i = 0; i < scene.participants.length; i += 1) {
            if (!state.revealedTop.has(i)) out.push(i);
        }
        return out;
    }

    function updateAutoButton() {
        if (!els.autoBtn) return;
        if (!state.scene || state.mode !== "roles") {
            els.autoBtn.hidden = true;
            els.autoBtn.disabled = true;
            els.autoBtn.textContent = "자동 공개";
            return;
        }
        els.autoBtn.hidden = false;
        if (state.autoRun) {
            els.autoBtn.disabled = false;
            els.autoBtn.textContent = "자동 중지";
            return;
        }
        const left = unresolvedIndexes().length;
        els.autoBtn.disabled = left === 0;
        els.autoBtn.textContent = left === 0 ? "공개 완료" : "자동 공개";
    }

    function showLive(name, outcome) {
        if (els.liveName) els.liveName.textContent = name;
        if (els.liveRole) els.liveRole.textContent = outcome;
        els.liveCard?.classList.toggle("is-winner", outcome === "당첨");

        if (!els.liveSparks) return;
        els.liveSparks.replaceChildren();
        if (isReducedMotion()) return;

        const frag = document.createDocumentFragment();
        for (let i = 0; i < 18; i += 1) {
            const spark = document.createElement("span");
            spark.style.left = `${Math.random() * 100}%`;
            spark.style.top = `${Math.random() * 80 + 12}%`;
            spark.style.animationDelay = `${Math.random() * 0.18}s`;
            frag.appendChild(spark);
        }
        els.liveSparks.appendChild(frag);
        window.setTimeout(() => els.liveSparks?.replaceChildren(), 900);
    }

    function pathD(points) {
        return points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0]},${p[1]}`).join(" ");
    }

    async function animatePath(points) {
        if (!els.svg || points.length < 2) return;
        if (state.activePath?.parentNode) state.activePath.parentNode.removeChild(state.activePath);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("class", "pbl-path-active");
        path.setAttribute("d", pathD(points));
        path.setAttribute("fill", "none");
        els.svg.appendChild(path);
        state.activePath = path;

        const length = path.getTotalLength();
        path.style.strokeDasharray = String(length);
        path.style.strokeDashoffset = String(length);
        const duration = isReducedMotion()
            ? 220
            : Math.max(1600, Math.min(3200, Math.round(length * 2.2)));
        path.style.transition = `stroke-dashoffset ${duration}ms cubic-bezier(0.16,1,0.3,1)`;
        window.requestAnimationFrame(() => {
            path.style.strokeDashoffset = "0";
        });
        await sleep(duration + (isReducedMotion() ? 40 : 180));
    }

    async function reveal(index, source) {
        const scene = state.scene;
        if (!scene || state.animating) return;
        if (index < 0 || index >= scene.participants.length) return;
        if (state.revealedTop.has(index)) {
            if (source === "manual") setMessage(els.stageMessage, "이미 발표된 참가자입니다.", "warn");
            return;
        }

        state.animating = true;
        const map = scene.maps[index];
        await animatePath(map.points);

        const name = scene.participants[index];
        const outcome = scene.outcomes[map.end];
        state.revealedTop.add(index);
        state.revealedBottom.add(map.end);
        state.feed.unshift({ step: state.revealedTop.size, name, outcome });
        if (state.feed.length > MAX_LADDER_NAMES) state.feed = state.feed.slice(0, MAX_LADDER_NAMES);

        drawNodes();
        updateCounters();
        renderFeed();
        showLive(name, outcome);
        setMessage(els.stageMessage, "", null);
        presentResult({
            badge: outcome === "당첨"
                ? (unresolvedIndexes().length > 0 ? "사다리 결승 주인공" : "사다리 피날레 주인공")
                : `${outcome} 발표`,
            celebration: unresolvedIndexes().length > 0 ? "reveal" : "finale",
            compliment: outcome === "당첨"
                ? "끝까지 따라간 길이 이 학생에게 환하게 멈췄어요."
                : `${outcome} 결과가 또렷하게 공개되며 무대가 더 선명해졌어요.`,
            fortuneTarget: {
                sourceLabel: "사다리 결과",
                targetName: name,
            },
            label: "사다리 결과 공개",
            meta: outcome === "당첨" ? "오늘의 당첨이 발표되었습니다." : `${outcome} 결과가 공개되었습니다.`,
            mode: "ladder",
            nextLabel: unresolvedIndexes().length > 0 ? "다음 발표 계속" : "닫기",
            sourceLabel: "사다리 결과",
            winnerName: name,
        });

        if (state.revealedTop.size === scene.participants.length) {
            state.autoRun = false;
            setMessage(els.stageMessage, "", null);
        }
        updateAutoButton();
        state.animating = false;
    }

    async function runAuto() {
        if (state.mode !== "roles" || !state.scene) return;
        if (state.autoRun) {
            state.autoRun = false;
            updateAutoButton();
            setMessage(els.stageMessage, "", null);
            return;
        }
        const queue = shuffle(unresolvedIndexes());
        if (!queue.length) {
            setMessage(els.stageMessage, "", null);
            updateAutoButton();
            return;
        }
        state.autoRun = true;
        updateAutoButton();
        setMessage(els.stageMessage, "", null);
        dispatchSfx("auto");
        for (const idx of queue) {
            if (!state.autoRun) break;
            await reveal(idx, "auto");
            if (!state.autoRun) break;
            await sleep(isReducedMotion() ? 120 : 520);
        }
        state.autoRun = false;
        updateAutoButton();
        if (!unresolvedIndexes().length) setMessage(els.stageMessage, "", null);
    }

    function startLadder() {
        const participants = parseUniqueLines(els.input?.value || "", MAX_LADDER_NAMES);
        const roles = parseUniqueLines(els.roleInput?.value || "", MAX_LADDER_NAMES);
        const mode = pickedMode();

        if (participants.valid.length < 2) {
            setMessage(els.setupMessage, "사다리 뽑기는 최소 2명 이상 필요합니다.", "warn");
            return;
        }
        if (mode === "roles" && !roles.valid.length) {
            setMessage(els.setupMessage, "역할 배정 모드는 역할을 최소 1개 입력해야 합니다.", "warn");
            return;
        }

        state.mode = mode;
        state.roles = roles.valid;
        state.scene = buildScene(participants.valid, mode, roles.valid);
        state.revealedTop = new Set();
        state.revealedBottom = new Set();
        state.feed = [];
        state.animating = false;
        state.autoRun = false;

        drawGrid();
        drawNodes();
        updateCounters();
        renderFeed();
        updateAutoButton();
        showLive("대기", "");
        if (els.stageTitle) {
            els.stageTitle.textContent =
                mode === "roles"
                    ? "역할 사다리"
                    : "사다리";
        }
        setMessage(els.stageMessage, "", null);
        setLadderScreen("stage");
        dispatchSfx("launch");
    }

    function reroll() {
        const scene = state.scene;
        if (!scene || state.animating) return;
        state.scene = buildScene(scene.participants, state.mode, state.roles);
        state.revealedTop = new Set();
        state.revealedBottom = new Set();
        state.feed = [];
        state.autoRun = false;
        drawGrid();
        drawNodes();
        updateCounters();
        renderFeed();
        updateAutoButton();
        showLive("대기", "");
        setMessage(els.stageMessage, "", null);
    }

    async function loadRosterInto(targetInput, button, setupMsg) {
        if (!targetInput || !button) return;
        button.disabled = true;
        button.textContent = "명단 불러오는 중...";
        try {
            const url = root.dataset.rosterUrl || "";
            if (!url) throw new Error("no url");
            const res = await fetch(url, { credentials: "same-origin" });
            if (!res.ok) throw new Error("fetch failed");
            const data = await res.json();
            const names = Array.isArray(data.names) ? data.names : [];
            if (!names.length) {
                setMessage(setupMsg, "등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
            } else {
                targetInput.value = names.join("\n");
                setMessage(setupMsg, `당번 명단 ${names.length}명을 불러왔습니다.`, "info");
            }
        } catch (error) {
            setMessage(setupMsg, "명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
        } finally {
            button.disabled = false;
            button.textContent = "당번 명단";
        }
    }

    function bindEvents() {
        els.modeRadios.forEach((radio) => radio.addEventListener("change", () => {
            syncRoleWrap();
            updateSetupStats();
        }));
        els.input?.addEventListener("input", updateSetupStats);
        els.roleInput?.addEventListener("input", updateSetupStats);
        els.loadSampleBtn?.addEventListener("click", () => {
            if (els.input) els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            if (els.roleInput) els.roleInput.value = DEFAULT_ROLES;
            updateSetupStats();
            setMessage(els.setupMessage, "사다리 예시 명단과 역할을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", async () => {
            await loadRosterInto(els.input, els.loadRosterBtn, els.setupMessage);
            updateSetupStats();
        });
        els.clearInputBtn?.addEventListener("click", () => {
            if (els.input) els.input.value = "";
            if (els.roleInput) els.roleInput.value = "";
            updateSetupStats();
        });
        els.startBtn?.addEventListener("click", startLadder);
        els.autoBtn?.addEventListener("click", runAuto);
        els.rerollBtn?.addEventListener("click", reroll);
        els.resetBtn?.addEventListener("click", () => {
            state.autoRun = false;
            state.animating = false;
            setLadderScreen("setup");
            updateAutoButton();
        });
        els.topRow?.addEventListener("click", async (event) => {
            const btn = event.target.closest("button[data-index]");
            if (!btn) return;
            const index = Number(btn.dataset.index);
            if (Number.isNaN(index)) return;
            await reveal(index, "manual");
        });
        root.addEventListener("ppobgi:mode-change", (event) => {
            if (event.detail?.mode !== "ladder" && state.autoRun) {
                state.autoRun = false;
                updateAutoButton();
            }
        });
    }

    function bootstrap() {
        if (els.input) els.input.value = "";
        if (els.roleInput) els.roleInput.value = DEFAULT_ROLES;
        syncRoleWrap();
        updateSetupStats();
        renderFeed();
        updateAutoButton();
        setLadderScreen("setup");
        if (shared?.getMode?.() !== "stars") {
            requestMode("stars");
        }
        bindEvents();
    }

    bootstrap();
})();

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const modeSequence = document.getElementById("ppb-mode-sequence");
    const els = {
        setupScreen: document.getElementById("pps-setup"),
        stageScreen: document.getElementById("pps-stage"),
        input: document.getElementById("pps-name-input"),
        loadSampleBtn: document.getElementById("pps-load-sample-btn"),
        loadRosterBtn: document.getElementById("pps-load-roster-btn"),
        clearInputBtn: document.getElementById("pps-clear-input-btn"),
        startBtn: document.getElementById("pps-start-btn"),
        statValid: document.getElementById("pps-stat-valid"),
        statDup: document.getElementById("pps-stat-dup"),
        statCut: document.getElementById("pps-stat-cut"),
        setupMessage: document.getElementById("pps-setup-message"),
        chipTotal: document.getElementById("pps-chip-total"),
        chipRevealed: document.getElementById("pps-chip-revealed"),
        chipLeft: document.getElementById("pps-chip-left"),
        stageTitle: document.getElementById("pps-stage-title"),
        stageMessage: document.getElementById("pps-stage-message"),
        orderGrid: document.getElementById("pps-order-grid"),
        nextBtn: document.getElementById("pps-next-btn"),
        autoBtn: document.getElementById("pps-auto-btn"),
        rerollBtn: document.getElementById("pps-reroll-btn"),
        resetBtn: document.getElementById("pps-reset-btn"),
        liveIndex: document.getElementById("pps-live-index"),
        liveName: document.getElementById("pps-live-name"),
        liveMeta: document.getElementById("pps-live-meta"),
        fortuneBtn: document.getElementById("pps-fortune-btn"),
        historyList: document.getElementById("pps-history-list"),
    };

    if (!modeSequence || !els.setupScreen || !els.stageScreen || !els.input) {
        return;
    }

    const MAX_SEQUENCE_NAMES = 40;

    const state = {
        sourceNames: [],
        order: [],
        revealedCount: 0,
        history: [],
        autoRun: false,
        currentName: "",
    };

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw
            .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
            .replace(/\\r\\n/g, "\n")
            .replace(/\\n/g, "\n")
            .replace(/\\r/g, "\n");
    }

    function normalizeName(name) {
        return String(name || "").replace(/\s+/g, " ").trim();
    }

    function parseNameInput(rawText) {
        const rows = String(rawText || "").split(/\r?\n/);
        const valid = [];
        const dupSet = new Set();
        const seen = new Set();

        rows.forEach((line) => {
            const name = normalizeName(line);
            if (!name) {
                return;
            }
            if (seen.has(name)) {
                dupSet.add(name);
                return;
            }
            seen.add(name);
            valid.push(name);
        });

        const cutCount = Math.max(0, valid.length - MAX_SEQUENCE_NAMES);
        return {
            valid: valid.slice(0, MAX_SEQUENCE_NAMES),
            duplicateNames: Array.from(dupSet),
            cutCount,
        };
    }

    function shuffle(list) {
        const copied = [...list];
        for (let i = copied.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copied[i], copied[j]] = [copied[j], copied[i]];
        }
        return copied;
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function isReducedMotion() {
        return root.classList.contains("ppb-reduce-motion");
    }

    function applyMessage(target, text, kind) {
        if (!target) {
            return;
        }
        target.textContent = text || "";
        target.classList.remove("warn", "info");
        if (kind) {
            target.classList.add(kind);
        }
    }

    function setSetupMessage(text, kind) {
        applyMessage(els.setupMessage, text, kind);
    }

    function setStageMessage(text, kind) {
        applyMessage(els.stageMessage, text, kind);
    }

    function setSequenceScreen(next) {
        els.setupScreen.classList.toggle("is-hidden", next !== "setup");
        els.stageScreen.classList.toggle("is-hidden", next !== "stage");
    }

    function updateSetupStats() {
        const parsed = parseNameInput(els.input?.value || "");
        if (els.statValid) {
            els.statValid.textContent = String(parsed.valid.length);
        }
        if (els.statDup) {
            els.statDup.textContent = String(parsed.duplicateNames.length);
        }
        if (els.statCut) {
            els.statCut.textContent = String(parsed.cutCount);
        }
        if (els.startBtn) {
            els.startBtn.disabled = parsed.valid.length === 0;
        }

        if (parsed.valid.length === 0) {
            setSetupMessage("최소 1명 이상의 이름을 입력해 주세요.", "warn");
            return;
        }

        const messages = [];
        if (parsed.duplicateNames.length > 0) {
            const preview = parsed.duplicateNames.slice(0, 5).join(", ");
            messages.push(`중복 제외: ${preview}${parsed.duplicateNames.length > 5 ? " 외" : ""}`);
        }
        if (parsed.cutCount > 0) {
            messages.push(`최대 ${MAX_SEQUENCE_NAMES}명 초과로 ${parsed.cutCount}명은 제외됩니다.`);
        }
        if (messages.length) {
            setSetupMessage(messages.join(" "), "warn");
            return;
        }
        setSetupMessage("", null);
    }

    function updateStageTitle() {
        if (!els.stageTitle) {
            return;
        }
        els.stageTitle.textContent = "순서";
    }

    function updateCounters() {
        const total = state.order.length;
        const revealed = state.revealedCount;
        if (els.chipTotal) els.chipTotal.textContent = String(total);
        if (els.chipRevealed) els.chipRevealed.textContent = String(revealed);
        if (els.chipLeft) els.chipLeft.textContent = String(Math.max(total - revealed, 0));
    }

    function renderHistory() {
        if (!els.historyList) {
            return;
        }
        if (!state.history.length) {
            els.historyList.innerHTML = '<li><span class="pps-history-main">아직 공개된 순서가 없습니다.</span></li>';
            return;
        }
        els.historyList.innerHTML = state.history.map((item) => `
            <li>
                <span class="pps-history-step">${item.order}번째 공개</span>
                <span class="pps-history-main">${escapeHtml(item.name)}</span>
                <span class="pps-history-order">전체 ${state.order.length}명 중 ${item.order}번째</span>
            </li>
        `).join("");
    }

    function renderLiveCard() {
        if (!state.currentName) {
            if (els.liveIndex) els.liveIndex.textContent = "";
            if (els.liveName) els.liveName.textContent = "대기";
            if (els.liveMeta) els.liveMeta.textContent = "";
            if (els.fortuneBtn) {
                els.fortuneBtn.hidden = true;
                els.fortuneBtn.disabled = true;
            }
            return;
        }
        const total = state.order.length;
        if (els.liveIndex) {
            els.liveIndex.textContent = `${state.revealedCount}번째 순서`;
        }
        if (els.liveName) {
            els.liveName.textContent = state.currentName;
        }
        if (els.liveMeta) {
            els.liveMeta.textContent = "";
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = false;
            els.fortuneBtn.disabled = false;
        }
    }

    function renderOrderGrid() {
        if (!els.orderGrid) {
            return;
        }
        if (!state.order.length) {
            els.orderGrid.innerHTML = '<div class="pps-empty">순서를 만들면 차례 카드가 여기에 펼쳐집니다.</div>';
            return;
        }
        els.orderGrid.innerHTML = state.order.map((name, index) => {
            const revealed = index < state.revealedCount;
            const current = revealed && index === state.revealedCount - 1;
            const next = index === state.revealedCount;
            const classes = ["pps-order-card"];
            if (revealed) classes.push("is-revealed");
            if (current) classes.push("is-current");
            if (!revealed && next) classes.push("is-next");
            const label = revealed ? escapeHtml(name) : "?";
            return `
                <article class="${classes.join(" ")}">
                    <span class="pps-order-index">${index + 1}번</span>
                    <strong class="pps-order-name">${label}</strong>
                </article>
            `;
        }).join("");
    }

    function updateActionButtons() {
        const total = state.order.length;
        const left = Math.max(total - state.revealedCount, 0);
        if (els.nextBtn) {
            els.nextBtn.disabled = total === 0 || left === 0;
            els.nextBtn.textContent = left === 0 && total > 0 ? "완료" : "다음 공개";
        }
        if (els.autoBtn) {
            if (!total) {
                els.autoBtn.disabled = true;
                els.autoBtn.textContent = "순서가 필요합니다";
            } else if (state.autoRun) {
                els.autoBtn.disabled = false;
                els.autoBtn.textContent = "자동 중지";
            } else {
                els.autoBtn.disabled = left === 0;
                els.autoBtn.textContent = left === 0 ? "공개 완료" : "자동 공개";
            }
        }
        if (els.rerollBtn) {
            els.rerollBtn.disabled = state.sourceNames.length === 0;
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = !state.currentName;
            els.fortuneBtn.disabled = !state.currentName;
        }
    }

    function syncStage() {
        updateStageTitle();
        updateCounters();
        renderOrderGrid();
        renderHistory();
        renderLiveCard();
        updateActionButtons();
    }

    function buildSequence(names, message) {
        state.sourceNames = [...names];
        state.order = shuffle(names);
        state.revealedCount = 0;
        state.history = [];
        state.autoRun = false;
        state.currentName = "";
        if (els.input) {
            els.input.value = names.join("\n");
        }
        setSequenceScreen("stage");
        syncStage();
        setStageMessage("", null);
        dispatchSfx("launch");
    }

    function startSequence() {
        const parsed = parseNameInput(els.input?.value || "");
        if (!parsed.valid.length) {
            window.alert("이름을 최소 1명 이상 입력해 주세요.");
            els.input?.focus();
            return;
        }
        buildSequence(parsed.valid, `총 ${parsed.valid.length}명의 순서를 만들었습니다.`);
    }

    function revealNext(source) {
        if (!state.order.length) {
            setStageMessage("먼저 순서를 만들어 주세요.", "warn");
            return false;
        }
        if (state.revealedCount >= state.order.length) {
            if (source === "manual") {
                setStageMessage("이미 모든 순서가 공개되었습니다.", "info");
            }
            state.autoRun = false;
            updateActionButtons();
            return false;
        }
        const order = state.revealedCount + 1;
        const name = state.order[state.revealedCount];
        state.revealedCount = order;
        state.currentName = name;
        state.history.unshift({ order, name });
        if (state.history.length > state.order.length) {
            state.history = state.history.slice(0, state.order.length);
        }
        syncStage();
        setStageMessage("", null);
        presentResult({
            badge: order === 1 ? "첫 발표 스타" : (state.revealedCount < state.order.length ? "오늘의 발표 스타" : "순서 공개 피날레"),
            celebration: state.revealedCount < state.order.length ? "reveal" : "finale",
            compliment: order === 1
                ? "첫 순서가 힘 있게 열리면서 교실 무대가 자신 있게 시작됩니다."
                : (state.revealedCount < state.order.length
                    ? "다음 순서가 또렷하게 드러나며 흐름이 더 쉬워졌어요."
                    : "마지막 순서까지 환하게 정리되어 오늘 진행이 멋지게 완성됐어요."),
            fortuneTarget: {
                sourceLabel: `${order}번째 순서 공개`,
                targetName: name,
            },
            label: "순서 발표",
            meta: `전체 ${state.order.length}명 중 ${order}번째 순서입니다.`,
            mode: "sequence",
            nextLabel: state.revealedCount < state.order.length ? "다음 순서 계속" : "닫기",
            sourceLabel: "순서 발표",
            winnerName: name,
        });
        if (state.revealedCount >= state.order.length) {
            state.autoRun = false;
            updateActionButtons();
        }
        return true;
    }

    async function runAuto() {
        if (!state.order.length) {
            setStageMessage("먼저 순서를 만들어 주세요.", "warn");
            updateActionButtons();
            return;
        }
        if (state.autoRun) {
            state.autoRun = false;
            updateActionButtons();
            setStageMessage("", null);
            return;
        }
        if (state.revealedCount >= state.order.length) {
            setStageMessage("이미 모든 순서가 공개되었습니다.", "info");
            updateActionButtons();
            return;
        }
        state.autoRun = true;
        updateActionButtons();
        setStageMessage("", null);
        dispatchSfx("auto");
        while (state.autoRun && state.revealedCount < state.order.length) {
            revealNext("auto");
            if (!state.autoRun || state.revealedCount >= state.order.length) {
                break;
            }
            await sleep(isReducedMotion() ? 120 : 520);
        }
        state.autoRun = false;
        updateActionButtons();
        if (state.revealedCount >= state.order.length) {
            setStageMessage("", null);
        }
    }

    function rerollSequence() {
        if (!state.sourceNames.length) {
            return;
        }
        state.order = shuffle(state.sourceNames);
        state.revealedCount = 0;
        state.history = [];
        state.autoRun = false;
        state.currentName = "";
        setSequenceScreen("stage");
        syncStage();
        setStageMessage("", null);
    }

    function resetToSetup() {
        state.autoRun = false;
        state.currentName = "";
        setSequenceScreen("setup");
        updateActionButtons();
        updateSetupStats();
        setSetupMessage("이름을 수정한 뒤 다시 순서를 만들어 주세요.", "info");
    }

    async function loadRosterNames() {
        if (!els.input || !els.loadRosterBtn) {
            return;
        }
        const rosterUrl = root.dataset.rosterUrl || "";
        if (!rosterUrl) {
            setSetupMessage("명단을 불러올 주소를 찾지 못했습니다.", "warn");
            return;
        }
        els.loadRosterBtn.disabled = true;
        els.loadRosterBtn.textContent = "명단 불러오는 중...";
        try {
            const response = await window.fetch(rosterUrl, {
                credentials: "same-origin",
                cache: "no-store",
            });
            if (!response.ok) {
                throw new Error("sequence roster fetch failed");
            }
            const payload = await response.json();
            const names = Array.isArray(payload.names) ? payload.names : [];
            if (!names.length) {
                setSetupMessage("등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
                return;
            }
            els.input.value = names.join("\n");
            updateSetupStats();
            setSetupMessage(`당번 명단 ${names.length}명을 불러왔습니다.`, "info");
        } catch (error) {
            setSetupMessage("명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
        } finally {
            els.loadRosterBtn.disabled = false;
            els.loadRosterBtn.textContent = "당번 명단";
        }
    }

    function openFortuneForCurrent() {
        if (!state.currentName) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", {
            detail: {
                targetName: state.currentName,
                sourceLabel: `${state.revealedCount}번째 순서 공개`,
            },
        }));
    }

    function bindEvents() {
        els.input?.addEventListener("input", updateSetupStats);
        els.loadSampleBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            updateSetupStats();
            setSetupMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", loadRosterNames);
        els.clearInputBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = "";
            updateSetupStats();
        });
        els.startBtn?.addEventListener("click", startSequence);
        els.nextBtn?.addEventListener("click", () => revealNext("manual"));
        els.autoBtn?.addEventListener("click", runAuto);
        els.rerollBtn?.addEventListener("click", rerollSequence);
        els.resetBtn?.addEventListener("click", resetToSetup);
        els.fortuneBtn?.addEventListener("click", openFortuneForCurrent);
        root.addEventListener("ppobgi:mode-change", (event) => {
            if (event.detail?.mode !== "sequence" && state.autoRun) {
                state.autoRun = false;
                updateActionButtons();
            }
        });
    }

    function bootstrap() {
        if (els.input) {
            els.input.value = "";
        }
        updateSetupStats();
        renderOrderGrid();
        renderHistory();
        renderLiveCard();
        updateCounters();
        updateActionButtons();
        setSequenceScreen("setup");
        bindEvents();
    }

    bootstrap();
})();

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const modeTeams = document.getElementById("ppb-mode-teams");
    const els = {
        setupScreen: document.getElementById("ppt-setup"),
        stageScreen: document.getElementById("ppt-stage"),
        input: document.getElementById("ppt-name-input"),
        teamCount: document.getElementById("ppt-team-count"),
        balanceNote: document.getElementById("ppt-balance-note"),
        loadSampleBtn: document.getElementById("ppt-load-sample-btn"),
        loadRosterBtn: document.getElementById("ppt-load-roster-btn"),
        clearInputBtn: document.getElementById("ppt-clear-input-btn"),
        startBtn: document.getElementById("ppt-start-btn"),
        statValid: document.getElementById("ppt-stat-valid"),
        statDup: document.getElementById("ppt-stat-dup"),
        statCut: document.getElementById("ppt-stat-cut"),
        setupMessage: document.getElementById("ppt-setup-message"),
        chipTotal: document.getElementById("ppt-chip-total"),
        chipTeams: document.getElementById("ppt-chip-teams"),
        chipLeft: document.getElementById("ppt-chip-left"),
        stageTitle: document.getElementById("ppt-stage-title"),
        stageMessage: document.getElementById("ppt-stage-message"),
        teamGrid: document.getElementById("ppt-team-grid"),
        nextBtn: document.getElementById("ppt-next-btn"),
        autoBtn: document.getElementById("ppt-auto-btn"),
        rerollBtn: document.getElementById("ppt-reroll-btn"),
        resetBtn: document.getElementById("ppt-reset-btn"),
        liveTeam: document.getElementById("ppt-live-team"),
        liveName: document.getElementById("ppt-live-name"),
        liveMeta: document.getElementById("ppt-live-meta"),
        fortuneBtn: document.getElementById("ppt-fortune-btn"),
        historyList: document.getElementById("ppt-history-list"),
    };

    if (!modeTeams || !els.setupScreen || !els.stageScreen || !els.input || !els.teamCount) {
        return;
    }

    const MAX_TEAM_NAMES = 40;

    const state = {
        sourceNames: [],
        plan: [],
        teamCount: 4,
        assignedCount: 0,
        history: [],
        autoRun: false,
        currentAssignment: null,
    };

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw
            .replace(/\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
            .replace(/\r\n/g, "\n")
            .replace(/\n/g, "\n")
            .replace(/\r/g, "\n");
    }

    function normalizeName(name) {
        return String(name || "").replace(/\s+/g, " ").trim();
    }

    function parseNameInput(rawText) {
        const rows = String(rawText || "").split(/\r?\n/);
        const valid = [];
        const dupSet = new Set();
        const seen = new Set();

        rows.forEach((line) => {
            const name = normalizeName(line);
            if (!name) {
                return;
            }
            if (seen.has(name)) {
                dupSet.add(name);
                return;
            }
            seen.add(name);
            valid.push(name);
        });

        const cutCount = Math.max(0, valid.length - MAX_TEAM_NAMES);
        return {
            valid: valid.slice(0, MAX_TEAM_NAMES),
            duplicateNames: Array.from(dupSet),
            cutCount,
        };
    }

    function shuffle(list) {
        const copied = [...list];
        for (let i = copied.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copied[i], copied[j]] = [copied[j], copied[i]];
        }
        return copied;
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function isReducedMotion() {
        return root.classList.contains("ppb-reduce-motion");
    }

    function applyMessage(target, text, kind) {
        if (!target) {
            return;
        }
        target.textContent = text || "";
        target.classList.remove("warn", "info");
        if (kind) {
            target.classList.add(kind);
        }
    }

    function setSetupMessage(text, kind) {
        applyMessage(els.setupMessage, text, kind);
    }

    function setStageMessage(text, kind) {
        applyMessage(els.stageMessage, text, kind);
    }

    function setTeamScreen(next) {
        els.setupScreen.classList.toggle("is-hidden", next !== "setup");
        els.stageScreen.classList.toggle("is-hidden", next !== "stage");
    }

    function readTeamCount() {
        const parsed = Number.parseInt(String(els.teamCount?.value || state.teamCount || 4), 10);
        if (Number.isNaN(parsed)) {
            return 4;
        }
        return Math.min(6, Math.max(2, parsed));
    }

    function describeBalance(total, teamCount) {
        if (total <= 0) {
            return `${teamCount}팀으로 나누면 인원이 최대한 고르게 배치됩니다.`;
        }
        const base = Math.floor(total / teamCount);
        const extra = total % teamCount;
        if (extra === 0) {
            return `${teamCount}팀으로 나누면 각 팀 ${base}명입니다.`;
        }
        return `${teamCount}팀으로 나누면 ${extra}팀은 ${base + 1}명, 나머지는 ${base}명입니다.`;
    }

    function buildTeamPlan(names, teamCount) {
        const shuffledNames = shuffle(names);
        return shuffledNames.map((name, index) => {
            const teamIndex = index % teamCount;
            return {
                name,
                teamIndex,
                teamLabel: `${teamIndex + 1}팀`,
                order: index + 1,
            };
        });
    }

    function buildTeamsSnapshot() {
        const teams = Array.from({ length: state.teamCount }, (_, index) => ({
            index,
            label: `${index + 1}팀`,
            targetSize: 0,
            members: [],
        }));
        state.plan.forEach((assignment) => {
            teams[assignment.teamIndex].targetSize += 1;
        });
        for (let index = 0; index < state.assignedCount; index += 1) {
            const assignment = state.plan[index];
            if (!assignment) {
                continue;
            }
            teams[assignment.teamIndex].members.push(assignment);
        }
        return teams;
    }

    function updateSetupStats() {
        const parsed = parseNameInput(els.input?.value || "");
        state.teamCount = readTeamCount();
        if (els.statValid) {
            els.statValid.textContent = String(parsed.valid.length);
        }
        if (els.statDup) {
            els.statDup.textContent = String(parsed.duplicateNames.length);
        }
        if (els.statCut) {
            els.statCut.textContent = String(parsed.cutCount);
        }
        if (els.balanceNote) {
            els.balanceNote.textContent = describeBalance(parsed.valid.length, state.teamCount);
        }
        if (els.startBtn) {
            els.startBtn.disabled = parsed.valid.length === 0;
        }

        if (parsed.valid.length === 0) {
            setSetupMessage("최소 1명 이상의 이름을 입력해 주세요.", "warn");
            return;
        }

        const messages = [];
        if (parsed.duplicateNames.length > 0) {
            const preview = parsed.duplicateNames.slice(0, 5).join(", ");
            messages.push(`중복 제외: ${preview}${parsed.duplicateNames.length > 5 ? " 외" : ""}`);
        }
        if (parsed.cutCount > 0) {
            messages.push(`최대 ${MAX_TEAM_NAMES}명 초과로 ${parsed.cutCount}명은 제외됩니다.`);
        }
        if (messages.length) {
            setSetupMessage(messages.join(" "), "warn");
            return;
        }
        setSetupMessage("", null);
    }

    function updateStageTitle() {
        if (!els.stageTitle) {
            return;
        }
        els.stageTitle.textContent = `${state.teamCount}팀`;
    }

    function updateCounters() {
        const total = state.plan.length;
        if (els.chipTotal) els.chipTotal.textContent = String(total);
        if (els.chipTeams) els.chipTeams.textContent = String(state.teamCount);
        if (els.chipLeft) els.chipLeft.textContent = String(Math.max(total - state.assignedCount, 0));
    }

    function renderHistory() {
        if (!els.historyList) {
            return;
        }
        if (!state.history.length) {
            els.historyList.innerHTML = '<li><span class="ppt-history-main">아직 공개된 팀 배치가 없습니다.</span></li>';
            return;
        }
        els.historyList.innerHTML = state.history.map((item) => `
            <li>
                <span class="ppt-history-step">${item.step}번째 배치</span>
                <span class="ppt-history-main">${escapeHtml(item.name)}</span>
                <span class="ppt-history-team">${escapeHtml(item.teamLabel)}</span>
            </li>
        `).join("");
    }

    function renderLiveCard() {
        if (!state.currentAssignment) {
            if (els.liveTeam) els.liveTeam.textContent = "";
            if (els.liveName) els.liveName.textContent = "대기";
            if (els.liveMeta) els.liveMeta.textContent = "";
            if (els.fortuneBtn) {
                els.fortuneBtn.hidden = true;
                els.fortuneBtn.disabled = true;
            }
            return;
        }
        if (els.liveTeam) {
            els.liveTeam.textContent = state.currentAssignment.teamLabel;
        }
        if (els.liveName) {
            els.liveName.textContent = state.currentAssignment.name;
        }
        if (els.liveMeta) {
            els.liveMeta.textContent = "";
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = false;
            els.fortuneBtn.disabled = false;
        }
    }

    function renderTeamGrid() {
        if (!els.teamGrid) {
            return;
        }
        if (!state.plan.length) {
            els.teamGrid.innerHTML = '<div class="ppt-empty">팀 편성을 만들면 팀 카드가 여기에 펼쳐집니다.</div>';
            return;
        }
        const latest = state.assignedCount > 0 ? state.plan[state.assignedCount - 1] : null;
        const teams = buildTeamsSnapshot();
        els.teamGrid.innerHTML = teams.map((team) => {
            const members = team.members.length
                ? team.members.map((member) => {
                    const classes = ["ppt-member-chip"];
                    if (latest === member) {
                        classes.push("is-recent");
                    }
                    if (state.currentAssignment === member) {
                        classes.push("is-selected");
                    }
                    return `<button type="button" class="${classes.join(" ")}" data-name="${escapeHtml(member.name)}" data-team-label="${escapeHtml(member.teamLabel)}">${escapeHtml(member.name)}</button>`;
                }).join("")
                : '<span class="ppt-member-empty">대기</span>';
            return `
                <article class="ppt-team-card">
                    <div class="ppt-team-head">
                        <div>
                            <h3 class="ppt-team-title">${team.label}</h3>
                            <p class="ppt-team-size">${team.members.length}/${team.targetSize}명</p>
                        </div>
                    </div>
                    <div class="ppt-member-list">${members}</div>
                </article>
            `;
        }).join("");
    }

    function updateActionButtons() {
        const total = state.plan.length;
        const left = Math.max(total - state.assignedCount, 0);
        if (els.nextBtn) {
            els.nextBtn.disabled = total === 0 || left === 0;
            els.nextBtn.textContent = left === 0 && total > 0 ? "완료" : "다음 배치";
        }
        if (els.autoBtn) {
            if (!total) {
                els.autoBtn.disabled = true;
                els.autoBtn.textContent = "팀 편성이 필요합니다";
            } else if (state.autoRun) {
                els.autoBtn.disabled = false;
                els.autoBtn.textContent = "자동 중지";
            } else {
                els.autoBtn.disabled = left === 0;
                els.autoBtn.textContent = left === 0 ? "공개 완료" : "자동 공개";
            }
        }
        if (els.rerollBtn) {
            els.rerollBtn.disabled = state.sourceNames.length === 0;
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = !state.currentAssignment;
            els.fortuneBtn.disabled = !state.currentAssignment;
        }
    }

    function syncStage() {
        updateStageTitle();
        updateCounters();
        renderTeamGrid();
        renderHistory();
        renderLiveCard();
        updateActionButtons();
    }

    function buildTeams(names, message) {
        state.sourceNames = [...names];
        state.teamCount = readTeamCount();
        state.plan = buildTeamPlan(names, state.teamCount);
        state.assignedCount = 0;
        state.history = [];
        state.autoRun = false;
        state.currentAssignment = null;
        if (els.input) {
            els.input.value = names.join("\n");
        }
        setTeamScreen("stage");
        syncStage();
        setStageMessage("", null);
        dispatchSfx("launch");
    }

    function startTeamBuild() {
        const parsed = parseNameInput(els.input?.value || "");
        if (!parsed.valid.length) {
            window.alert("이름을 최소 1명 이상 입력해 주세요.");
            els.input?.focus();
            return;
        }
        buildTeams(parsed.valid, `${readTeamCount()}팀 편성을 만들었습니다.`);
    }

    function revealNextAssignment(source) {
        if (!state.plan.length) {
            setStageMessage("먼저 팀 편성을 만들어 주세요.", "warn");
            return false;
        }
        if (state.assignedCount >= state.plan.length) {
            if (source === "manual") {
                setStageMessage("이미 모든 팀 배치가 공개되었습니다.", "info");
            }
            state.autoRun = false;
            updateActionButtons();
            return false;
        }
        const assignment = state.plan[state.assignedCount];
        state.assignedCount += 1;
        state.currentAssignment = assignment;
        state.history.unshift({
            step: state.assignedCount,
            name: assignment.name,
            teamLabel: assignment.teamLabel,
        });
        if (state.history.length > state.plan.length) {
            state.history = state.history.slice(0, state.plan.length);
        }
        syncStage();
        setStageMessage("", null);
        presentResult({
            badge: state.assignedCount < state.plan.length ? `${assignment.teamLabel} 합류 발표` : "팀 편성 피날레",
            celebration: state.assignedCount < state.plan.length ? "reveal" : "finale",
            compliment: state.assignedCount < state.plan.length
                ? `${assignment.teamLabel}의 분위기가 이 학생 합류로 더 또렷해졌어요.`
                : "마지막 배치까지 공개되며 팀 구성이 깔끔하게 완성됐어요.",
            fortuneTarget: {
                sourceLabel: `${assignment.teamLabel} 배치 공개`,
                targetName: assignment.name,
            },
            label: "팀 배치 발표",
            meta: `${assignment.teamLabel}에 새 멤버가 배치되었습니다.`,
            mode: "teams",
            nextLabel: state.assignedCount < state.plan.length ? "다음 팀 배치 계속" : "닫기",
            sourceLabel: "팀 배치 발표",
            winnerName: assignment.name,
        });
        if (state.assignedCount >= state.plan.length) {
            state.autoRun = false;
            updateActionButtons();
        }
        return true;
    }

    async function runAuto() {
        if (!state.plan.length) {
            setStageMessage("먼저 팀 편성을 만들어 주세요.", "warn");
            updateActionButtons();
            return;
        }
        if (state.autoRun) {
            state.autoRun = false;
            updateActionButtons();
            setStageMessage("", null);
            return;
        }
        if (state.assignedCount >= state.plan.length) {
            setStageMessage("이미 모든 팀 배치가 공개되었습니다.", "info");
            updateActionButtons();
            return;
        }
        state.autoRun = true;
        updateActionButtons();
        setStageMessage("", null);
        dispatchSfx("auto");
        while (state.autoRun && state.assignedCount < state.plan.length) {
            revealNextAssignment("auto");
            if (!state.autoRun || state.assignedCount >= state.plan.length) {
                break;
            }
            await sleep(isReducedMotion() ? 120 : 520);
        }
        state.autoRun = false;
        updateActionButtons();
        if (state.assignedCount >= state.plan.length) {
            setStageMessage("", null);
        }
    }

    function rerollTeams() {
        if (!state.sourceNames.length) {
            return;
        }
        state.plan = buildTeamPlan(state.sourceNames, state.teamCount);
        state.assignedCount = 0;
        state.history = [];
        state.autoRun = false;
        state.currentAssignment = null;
        setTeamScreen("stage");
        syncStage();
        setStageMessage("", null);
    }

    function resetToSetup() {
        state.autoRun = false;
        state.currentAssignment = null;
        setTeamScreen("setup");
        updateActionButtons();
        updateSetupStats();
        setSetupMessage("이름이나 팀 수를 조정한 뒤 다시 팀 편성을 만들어 주세요.", "info");
    }

    async function loadRosterNames() {
        if (!els.input || !els.loadRosterBtn) {
            return;
        }
        const rosterUrl = root.dataset.rosterUrl || "";
        if (!rosterUrl) {
            setSetupMessage("명단을 불러올 주소를 찾지 못했습니다.", "warn");
            return;
        }
        els.loadRosterBtn.disabled = true;
        els.loadRosterBtn.textContent = "명단 불러오는 중...";
        try {
            const response = await window.fetch(rosterUrl, {
                credentials: "same-origin",
                cache: "no-store",
            });
            if (!response.ok) {
                throw new Error("team roster fetch failed");
            }
            const payload = await response.json();
            const names = Array.isArray(payload.names) ? payload.names : [];
            if (!names.length) {
                setSetupMessage("등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
                return;
            }
            els.input.value = names.join("\n");
            updateSetupStats();
            setSetupMessage(`당번 명단 ${names.length}명을 불러왔습니다.`, "info");
        } catch (error) {
            setSetupMessage("명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
        } finally {
            els.loadRosterBtn.disabled = false;
            els.loadRosterBtn.textContent = "당번 명단";
        }
    }

    function selectAssignedMember(name, teamLabel) {
        const assignment = state.plan.find((item, index) => index < state.assignedCount && item.name === name && item.teamLabel === teamLabel);
        if (!assignment) {
            return;
        }
        state.currentAssignment = assignment;
        renderTeamGrid();
        renderLiveCard();
        updateActionButtons();
        setStageMessage("", null);
    }

    function openFortuneForCurrent() {
        if (!state.currentAssignment) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", {
            detail: {
                targetName: state.currentAssignment.name,
                sourceLabel: `${state.currentAssignment.teamLabel} 배치 공개`,
            },
        }));
    }

    function bindEvents() {
        els.input?.addEventListener("input", updateSetupStats);
        els.teamCount?.addEventListener("change", updateSetupStats);
        els.loadSampleBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            updateSetupStats();
            setSetupMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", loadRosterNames);
        els.clearInputBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = "";
            updateSetupStats();
        });
        els.startBtn?.addEventListener("click", startTeamBuild);
        els.nextBtn?.addEventListener("click", () => revealNextAssignment("manual"));
        els.autoBtn?.addEventListener("click", runAuto);
        els.rerollBtn?.addEventListener("click", rerollTeams);
        els.resetBtn?.addEventListener("click", resetToSetup);
        els.fortuneBtn?.addEventListener("click", openFortuneForCurrent);
        els.teamGrid?.addEventListener("click", (event) => {
            const button = event.target.closest("button[data-name][data-team-label]");
            if (!button) {
                return;
            }
            selectAssignedMember(button.dataset.name || "", button.dataset.teamLabel || "");
        });
        root.addEventListener("ppobgi:mode-change", (event) => {
            if (event.detail?.mode !== "teams" && state.autoRun) {
                state.autoRun = false;
                updateActionButtons();
            }
        });
    }

    function bootstrap() {
        if (els.input) {
            els.input.value = "";
        }
        updateSetupStats();
        renderTeamGrid();
        renderHistory();
        renderLiveCard();
        updateCounters();
        updateActionButtons();
        setTeamScreen("setup");
        bindEvents();
    }

    bootstrap();
})();

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const modeMeteor = document.getElementById("ppb-mode-meteor");
    const els = {
        setupScreen: document.getElementById("ppm-setup"),
        stageScreen: document.getElementById("ppm-stage"),
        input: document.getElementById("ppm-name-input"),
        loadSampleBtn: document.getElementById("ppm-load-sample-btn"),
        loadRosterBtn: document.getElementById("ppm-load-roster-btn"),
        clearInputBtn: document.getElementById("ppm-clear-input-btn"),
        startBtn: document.getElementById("ppm-start-btn"),
        statValid: document.getElementById("ppm-stat-valid"),
        statDup: document.getElementById("ppm-stat-dup"),
        statCut: document.getElementById("ppm-stat-cut"),
        setupMessage: document.getElementById("ppm-setup-message"),
        chipTotal: document.getElementById("ppm-chip-total"),
        chipRevealed: document.getElementById("ppm-chip-revealed"),
        chipLeft: document.getElementById("ppm-chip-left"),
        stageTitle: document.getElementById("ppm-stage-title"),
        stageMessage: document.getElementById("ppm-stage-message"),
        sky: document.getElementById("ppm-sky"),
        autoRandomBtn: document.getElementById("ppm-auto-random-btn"),
        autoBtn: document.getElementById("ppm-auto-btn"),
        rerollBtn: document.getElementById("ppm-reroll-btn"),
        resetBtn: document.getElementById("ppm-reset-btn"),
        liveOrder: document.getElementById("ppm-live-order"),
        liveName: document.getElementById("ppm-live-name"),
        liveMeta: document.getElementById("ppm-live-meta"),
        fortuneBtn: document.getElementById("ppm-fortune-btn"),
        historyList: document.getElementById("ppm-history-list"),
    };

    if (!modeMeteor || !els.setupScreen || !els.stageScreen || !els.input || !els.sky) {
        return;
    }

    const MAX_METEOR_NAMES = 40;
    const METEOR_FOOTPRINT = {
        width: 210,
        height: 104,
    };

    const state = {
        sourceNames: [],
        remainingNames: [],
        history: [],
        autoRun: false,
        currentName: "",
        meteorLayout: new Map(),
        resizeTimer: 0,
        burstTimer: 0,
    };

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw
            .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
            .replace(/\\r\\n/g, "\n")
            .replace(/\\n/g, "\n")
            .replace(/\\r/g, "\n");
    }

    function normalizeName(name) {
        return String(name || "").replace(/\s+/g, " ").trim();
    }

    function parseNameInput(rawText) {
        const rows = String(rawText || "").split(/\r?\n/);
        const valid = [];
        const dupSet = new Set();
        const seen = new Set();

        rows.forEach((line) => {
            const name = normalizeName(line);
            if (!name) {
                return;
            }
            if (seen.has(name)) {
                dupSet.add(name);
                return;
            }
            seen.add(name);
            valid.push(name);
        });

        const cutCount = Math.max(0, valid.length - MAX_METEOR_NAMES);
        return {
            valid: valid.slice(0, MAX_METEOR_NAMES),
            duplicateNames: Array.from(dupSet),
            cutCount,
        };
    }

    function shuffle(list) {
        const copied = [...list];
        for (let i = copied.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copied[i], copied[j]] = [copied[j], copied[i]];
        }
        return copied;
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function isReducedMotion() {
        return root.classList.contains("ppb-reduce-motion");
    }

    function applyMessage(target, text, kind) {
        if (!target) {
            return;
        }
        target.textContent = text || "";
        target.classList.remove("warn", "info");
        if (kind) {
            target.classList.add(kind);
        }
    }

    function setSetupMessage(text, kind) {
        applyMessage(els.setupMessage, text, kind);
    }

    function setStageMessage(text, kind) {
        applyMessage(els.stageMessage, text, kind);
    }

    function setMeteorScreen(next) {
        els.setupScreen.classList.toggle("is-hidden", next !== "setup");
        els.stageScreen.classList.toggle("is-hidden", next !== "stage");
    }

    function meteorFieldSize() {
        const rect = els.sky?.getBoundingClientRect();
        const rawWidth = Math.max(rect?.width || 0, els.sky?.clientWidth || 0, 0);
        const rawHeight = Math.max(rect?.height || 0, els.sky?.clientHeight || 0, 0);
        return {
            width: Math.max(rawWidth, 680),
            height: Math.max(rawHeight, 540),
        };
    }

    function fallbackMeteorPosition(index, total, width, height) {
        const safeWidth = Math.max(width - METEOR_FOOTPRINT.width, 120);
        const safeHeight = Math.max(height - METEOR_FOOTPRINT.height, 120);
        const ratio = total <= 1 ? 0.24 : 0.18 + (index / Math.max(total - 1, 1)) * 0.68;
        const angle = index * 2.399963229728653;
        const x = METEOR_FOOTPRINT.width * 0.28 + safeWidth * (0.5 + Math.cos(angle) * 0.42 * ratio);
        const y = METEOR_FOOTPRINT.height * 0.24 + safeHeight * (0.5 + Math.sin(angle) * 0.36 * ratio);
        return {
            x: Math.min(width - METEOR_FOOTPRINT.width * 0.34, Math.max(METEOR_FOOTPRINT.width * 0.22, x)),
            y: Math.min(height - METEOR_FOOTPRINT.height * 0.3, Math.max(METEOR_FOOTPRINT.height * 0.2, y)),
        };
    }

    function buildMeteorLayout(names) {
        if (!els.sky || !names.length) {
            return new Map();
        }
        const { width, height } = meteorFieldSize();
        const layout = new Map();
        const placed = [];
        const minDistance = Math.max(84, Math.min(width, height) * 0.14);
        const descriptors = shuffle(names).map((name) => ({
            name,
            scale: Number((0.9 + Math.random() * 0.42).toFixed(3)),
            tilt: Number((-18 - Math.random() * 16).toFixed(3)),
            duration: Number((4.4 + Math.random() * 3.4).toFixed(2)),
            delay: Number((Math.random() * 2.4).toFixed(2)),
        }));

        descriptors.forEach((item, index) => {
            let point = null;
            for (let attempt = 0; attempt < 90; attempt += 1) {
                const x = METEOR_FOOTPRINT.width * 0.24 + Math.random() * Math.max(width - METEOR_FOOTPRINT.width * 1.1, 120);
                const y = METEOR_FOOTPRINT.height * 0.22 + Math.random() * Math.max(height - METEOR_FOOTPRINT.height * 1.06, 120);
                const conflict = placed.some((placedPoint) => {
                    const dx = placedPoint.x - x;
                    const dy = placedPoint.y - y;
                    return Math.hypot(dx, dy) < minDistance;
                });
                if (!conflict) {
                    point = { x, y };
                    break;
                }
            }
            if (!point) {
                point = fallbackMeteorPosition(index, descriptors.length, width, height);
            }
            placed.push(point);
            layout.set(item.name, {
                left: Number(((point.x / width) * 100).toFixed(3)),
                top: Number(((point.y / height) * 100).toFixed(3)),
                scale: item.scale,
                tilt: item.tilt,
                duration: item.duration,
                delay: item.delay,
            });
        });
        return layout;
    }

    function updateSetupStats() {
        const parsed = parseNameInput(els.input?.value || "");
        if (els.statValid) {
            els.statValid.textContent = String(parsed.valid.length);
        }
        if (els.statDup) {
            els.statDup.textContent = String(parsed.duplicateNames.length);
        }
        if (els.statCut) {
            els.statCut.textContent = String(parsed.cutCount);
        }
        if (els.startBtn) {
            els.startBtn.disabled = parsed.valid.length === 0;
        }

        if (parsed.valid.length === 0) {
            setSetupMessage("최소 1명 이상의 이름을 입력해 주세요.", "warn");
            return;
        }

        const messages = [];
        if (parsed.duplicateNames.length > 0) {
            const preview = parsed.duplicateNames.slice(0, 5).join(", ");
            messages.push(`중복 제외: ${preview}${parsed.duplicateNames.length > 5 ? " 외" : ""}`);
        }
        if (parsed.cutCount > 0) {
            messages.push(`최대 ${MAX_METEOR_NAMES}명 초과로 ${parsed.cutCount}명은 제외됩니다.`);
        }
        if (messages.length) {
            setSetupMessage(messages.join(" "), "warn");
            return;
        }
        setSetupMessage("", null);
    }

    function updateStageTitle() {
        if (!els.stageTitle) {
            return;
        }
        els.stageTitle.textContent = "유성우";
    }

    function updateCounters() {
        const total = state.sourceNames.length;
        const revealed = state.history.length;
        const left = state.remainingNames.length;
        if (els.chipTotal) els.chipTotal.textContent = String(total);
        if (els.chipRevealed) els.chipRevealed.textContent = String(revealed);
        if (els.chipLeft) els.chipLeft.textContent = String(left);
    }

    function renderHistory() {
        if (!els.historyList) {
            return;
        }
        if (!state.history.length) {
            els.historyList.innerHTML = '<li><span class="ppm-history-main">아직 공개된 유성이 없습니다.</span></li>';
            return;
        }
        els.historyList.innerHTML = state.history.map((item) => `
            <li>
                <span class="ppm-history-step">${item.order}번째 공개</span>
                <span class="ppm-history-main">${escapeHtml(item.name)}</span>
                <span class="ppm-history-order">전체 ${state.sourceNames.length}명 중 ${item.order}번째</span>
            </li>
        `).join("");
    }

    function renderLiveCard() {
        if (!state.currentName) {
            if (els.liveOrder) els.liveOrder.textContent = "";
            if (els.liveName) els.liveName.textContent = "대기";
            if (els.liveMeta) els.liveMeta.textContent = "";
            if (els.fortuneBtn) {
                els.fortuneBtn.hidden = true;
                els.fortuneBtn.disabled = true;
            }
            return;
        }
        const order = state.history.length;
        if (els.liveOrder) {
            els.liveOrder.textContent = `${order}번째 유성`;
        }
        if (els.liveName) {
            els.liveName.textContent = state.currentName;
        }
        if (els.liveMeta) {
            els.liveMeta.textContent = "";
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = false;
            els.fortuneBtn.disabled = false;
        }
    }

    function updateActionButtons() {
        const total = state.sourceNames.length;
        const left = state.remainingNames.length;
        if (els.autoRandomBtn) {
            els.autoRandomBtn.disabled = total === 0 || left === 0;
            els.autoRandomBtn.textContent = left === 0 && total > 0 ? "완료" : "무작위 공개";
        }
        if (els.autoBtn) {
            if (!total) {
                els.autoBtn.disabled = true;
                els.autoBtn.textContent = "유성우가 필요합니다";
            } else if (state.autoRun) {
                els.autoBtn.disabled = false;
                els.autoBtn.textContent = "자동 중지";
            } else {
                els.autoBtn.disabled = left === 0;
                els.autoBtn.textContent = left === 0 ? "공개 완료" : "자동 공개";
            }
        }
        if (els.rerollBtn) {
            els.rerollBtn.disabled = state.sourceNames.length === 0;
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = !state.currentName;
            els.fortuneBtn.disabled = !state.currentName;
        }
    }

    function triggerBurst() {
        if (!els.sky) {
            return;
        }
        window.clearTimeout(state.burstTimer);
        els.sky.classList.remove("is-burst");
        void els.sky.offsetWidth;
        els.sky.classList.add("is-burst");
        state.burstTimer = window.setTimeout(() => {
            els.sky?.classList.remove("is-burst");
        }, isReducedMotion() ? 140 : 360);
    }

    function renderSky() {
        if (!els.sky) {
            return;
        }
        if (!state.sourceNames.length) {
            els.sky.innerHTML = '<div class="ppm-empty">유성우를 펼치면 숨은 유성들이 여기 흩뿌려집니다.</div>';
            return;
        }
        if (!state.remainingNames.length) {
            els.sky.innerHTML = '<div class="ppm-empty is-complete">모든 유성이 공개되었습니다. 다시 펼치거나 포춘쿠키로 이어가 보세요.</div>';
            return;
        }
        els.sky.innerHTML = state.remainingNames.map((name, index) => {
            const layout = state.meteorLayout.get(name) || (() => {
                const { width, height } = meteorFieldSize();
                const fallback = fallbackMeteorPosition(index, state.remainingNames.length, width, height);
                return {
                    left: Number(((fallback.x / width) * 100).toFixed(3)),
                    top: Number(((fallback.y / height) * 100).toFixed(3)),
                    scale: 1,
                    tilt: -24,
                    duration: 5.4,
                    delay: 0,
                };
            })();
            return `
                <button
                    type="button"
                    class="ppm-meteor"
                    data-name="${escapeHtml(name)}"
                    style="--ppm-left:${layout.left}%; --ppm-top:${layout.top}%; --ppm-scale:${layout.scale}; --ppm-tilt:${layout.tilt}deg; --ppm-duration:${layout.duration}s; --ppm-delay:${layout.delay}s;"
                >
                    <span class="ppm-meteor-core" aria-hidden="true"></span>
                    <span class="ppm-meteor-tail" aria-hidden="true"></span>
                </button>
            `;
        }).join("");
    }

    function syncStage() {
        updateStageTitle();
        updateCounters();
        renderSky();
        renderHistory();
        renderLiveCard();
        updateActionButtons();
    }

    function buildMeteorShow(names, message) {
        state.sourceNames = [...names];
        state.remainingNames = [...names];
        state.history = [];
        state.autoRun = false;
        state.currentName = "";
        state.meteorLayout = buildMeteorLayout(state.sourceNames);
        if (els.input) {
            els.input.value = names.join("\n");
        }
        setMeteorScreen("stage");
        syncStage();
        setStageMessage("", null);
        dispatchSfx("launch");
    }

    function startMeteorShow() {
        const parsed = parseNameInput(els.input?.value || "");
        if (!parsed.valid.length) {
            window.alert("이름을 최소 1명 이상 입력해 주세요.");
            els.input?.focus();
            return;
        }
        buildMeteorShow(parsed.valid, `총 ${parsed.valid.length}명의 유성을 펼쳤습니다.`);
    }

    function revealMeteorByName(name, source) {
        if (!name) {
            return false;
        }
        const index = state.remainingNames.indexOf(name);
        if (index === -1) {
            if (source === "manual") {
                setStageMessage("이미 공개된 유성입니다.", "warn");
            }
            return false;
        }
        state.remainingNames.splice(index, 1);
        state.currentName = name;
        const order = state.history.length + 1;
        state.history.unshift({ order, name });
        if (state.history.length > state.sourceNames.length) {
            state.history = state.history.slice(0, state.sourceNames.length);
        }
        syncStage();
        triggerBurst();
        setStageMessage("", null);
        presentResult({
            badge: state.remainingNames.length ? `${order}번째 유성 주인공` : "유성우 피날레 주인공",
            celebration: state.remainingNames.length ? "reveal" : "finale",
            compliment: state.remainingNames.length
                ? "밤하늘을 가르던 유성이 이 학생의 이름으로 환하게 완성됐어요."
                : "마지막 유성까지 화려하게 닿으며 오늘 무대가 시원하게 마무리됐어요.",
            fortuneTarget: {
                sourceLabel: `${order}번째 유성 공개`,
                targetName: name,
            },
            label: "유성우 발표",
            meta: state.remainingNames.length ? `남은 유성 ${state.remainingNames.length}개` : "모든 유성이 공개되었습니다.",
            mode: "meteor",
            nextLabel: state.remainingNames.length ? "다음 유성 계속" : "닫기",
            sourceLabel: "유성우 발표",
            winnerName: name,
        });
        if (!state.remainingNames.length) {
            state.autoRun = false;
            updateActionButtons();
        }
        return true;
    }

    function revealRandomMeteor(source) {
        if (!state.remainingNames.length) {
            if (source !== "auto") {
                setStageMessage("이미 모든 유성이 공개되었습니다.", "info");
            }
            state.autoRun = false;
            updateActionButtons();
            return false;
        }
        const name = state.remainingNames[Math.floor(Math.random() * state.remainingNames.length)];
        return revealMeteorByName(name, source);
    }

    async function runAuto() {
        if (!state.sourceNames.length) {
            setStageMessage("먼저 유성우를 펼쳐 주세요.", "warn");
            updateActionButtons();
            return;
        }
        if (state.autoRun) {
            state.autoRun = false;
            updateActionButtons();
            setStageMessage("", null);
            return;
        }
        if (!state.remainingNames.length) {
            setStageMessage("이미 모든 유성이 공개되었습니다.", "info");
            updateActionButtons();
            return;
        }
        state.autoRun = true;
        updateActionButtons();
        setStageMessage("", null);
        dispatchSfx("auto");
        while (state.autoRun && state.remainingNames.length) {
            revealRandomMeteor("auto");
            if (!state.autoRun || !state.remainingNames.length) {
                break;
            }
            await sleep(isReducedMotion() ? 140 : 560);
        }
        state.autoRun = false;
        updateActionButtons();
        if (!state.remainingNames.length) {
            setStageMessage("", null);
        }
    }

    function rerollMeteors() {
        if (!state.sourceNames.length) {
            return;
        }
        state.remainingNames = [...state.sourceNames];
        state.history = [];
        state.autoRun = false;
        state.currentName = "";
        state.meteorLayout = buildMeteorLayout(state.sourceNames);
        setMeteorScreen("stage");
        syncStage();
        setStageMessage("", null);
    }

    function resetToSetup() {
        state.autoRun = false;
        state.currentName = "";
        setMeteorScreen("setup");
        updateActionButtons();
        updateSetupStats();
        setSetupMessage("이름을 고친 뒤 다시 유성우를 펼쳐 보세요.", "info");
    }

    async function loadRosterNames() {
        if (!els.input || !els.loadRosterBtn) {
            return;
        }
        const rosterUrl = root.dataset.rosterUrl || "";
        if (!rosterUrl) {
            setSetupMessage("명단을 불러올 주소를 찾지 못했습니다.", "warn");
            return;
        }
        els.loadRosterBtn.disabled = true;
        els.loadRosterBtn.textContent = "명단 불러오는 중...";
        try {
            const response = await window.fetch(rosterUrl, {
                credentials: "same-origin",
                cache: "no-store",
            });
            if (!response.ok) {
                throw new Error("meteor roster fetch failed");
            }
            const payload = await response.json();
            const names = Array.isArray(payload.names) ? payload.names : [];
            if (!names.length) {
                setSetupMessage("등록된 당번 명단이 없습니다. 직접 입력해 주세요.", "warn");
                return;
            }
            els.input.value = names.join("\n");
            updateSetupStats();
            setSetupMessage(`당번 명단 ${names.length}명을 불러왔습니다.`, "info");
        } catch (error) {
            setSetupMessage("명단 불러오기에 실패했습니다. 네트워크 상태를 확인해 주세요.", "warn");
        } finally {
            els.loadRosterBtn.disabled = false;
            els.loadRosterBtn.textContent = "당번 명단";
        }
    }

    function openFortuneForCurrent() {
        if (!state.currentName) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", {
            detail: {
                targetName: state.currentName,
                sourceLabel: `${state.history.length}번째 유성 공개`,
            },
        }));
    }

    function handleSkyClick(event) {
        const button = event.target.closest("button[data-name]");
        if (!button) {
            return;
        }
        revealMeteorByName(button.dataset.name || "", "manual");
    }

    function handleResize() {
        if (!state.sourceNames.length) {
            return;
        }
        window.clearTimeout(state.resizeTimer);
        state.resizeTimer = window.setTimeout(() => {
            state.meteorLayout = buildMeteorLayout(state.sourceNames);
            renderSky();
        }, 120);
    }

    function bindEvents() {
        els.input?.addEventListener("input", updateSetupStats);
        els.loadSampleBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            updateSetupStats();
            setSetupMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", loadRosterNames);
        els.clearInputBtn?.addEventListener("click", () => {
            if (!els.input) {
                return;
            }
            els.input.value = "";
            updateSetupStats();
        });
        els.startBtn?.addEventListener("click", startMeteorShow);
        els.autoRandomBtn?.addEventListener("click", () => revealRandomMeteor("manual"));
        els.autoBtn?.addEventListener("click", runAuto);
        els.rerollBtn?.addEventListener("click", rerollMeteors);
        els.resetBtn?.addEventListener("click", resetToSetup);
        els.fortuneBtn?.addEventListener("click", openFortuneForCurrent);
        els.sky?.addEventListener("click", handleSkyClick);
        window.addEventListener("resize", handleResize);
        root.addEventListener("ppobgi:mode-change", (event) => {
            if (event.detail?.mode !== "meteor" && state.autoRun) {
                state.autoRun = false;
                updateActionButtons();
            }
        });
    }

    function bootstrap() {
        if (els.input) {
            els.input.value = "";
        }
        updateSetupStats();
        renderSky();
        renderHistory();
        renderLiveCard();
        updateCounters();
        updateActionButtons();
        setMeteorScreen("setup");
        bindEvents();
    }

    bootstrap();
})();
(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const modeRoles = document.getElementById("ppb-mode-roles");
    const els = {
        cardGrid: document.getElementById("ppr-card-grid"),
        message: document.getElementById("ppr-message"),
        classroomBadge: document.getElementById("ppr-classroom-badge"),
        chipTotal: document.getElementById("ppr-chip-total"),
        chipRevealed: document.getElementById("ppr-chip-revealed"),
        chipLeft: document.getElementById("ppr-chip-left"),
        refreshBtn: document.getElementById("ppr-refresh-btn"),
        autoBtn: document.getElementById("ppr-auto-btn"),
        liveRoleName: document.getElementById("ppr-live-role-name"),
        liveAssignee: document.getElementById("ppr-live-assignee"),
        fortuneBtn: document.getElementById("ppr-fortune-btn"),
        historyList: document.getElementById("ppr-history-list"),
    };

    if (!modeRoles || !els.cardGrid || !els.message) {
        return;
    }

    const state = {
        roles: [],
        revealed: new Set(),
        history: [],
        autoRun: false,
        loading: false,
        loadedOnce: false,
        lastFortuneTarget: null,
    };

    function dispatchSfx(kind) {
        root.dispatchEvent(new CustomEvent("ppobgi:play-sfx", { detail: { cue: kind } }));
    }

    function isReducedMotion() {
        return root.classList.contains("ppb-reduce-motion");
    }

    function sleep(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function setMessage(text, kind) {
        els.message.textContent = text || "";
        els.message.classList.remove("warn", "info");
        if (kind) {
            els.message.classList.add(kind);
        }
    }

    function unrevealedIndexes() {
        const indexes = [];
        for (let i = 0; i < state.roles.length; i += 1) {
            if (!state.revealed.has(i)) {
                indexes.push(i);
            }
        }
        return indexes;
    }

    function updateCounters() {
        const total = state.roles.length;
        const revealed = state.revealed.size;
        if (els.chipTotal) els.chipTotal.textContent = String(total);
        if (els.chipRevealed) els.chipRevealed.textContent = String(revealed);
        if (els.chipLeft) els.chipLeft.textContent = String(Math.max(total - revealed, 0));
    }

    function renderHistory() {
        if (!els.historyList) {
            return;
        }
        if (!state.history.length) {
            const empty = document.createElement("li");
            empty.innerHTML = '<span class="ppr-history-main">아직 공개된 역할이 없습니다.</span>';
            els.historyList.replaceChildren(empty);
            return;
        }
        const fragment = document.createDocumentFragment();
        state.history.forEach((item) => {
            const li = document.createElement("li");
            li.innerHTML = `<span class="ppr-history-step">${item.step}번째 공개</span><span class="ppr-history-main">${escapeHtml(item.roleName)}</span><span class="ppr-history-role">→ ${escapeHtml(item.assigneeName)}</span>`;
            fragment.appendChild(li);
        });
        els.historyList.replaceChildren(fragment);
    }

    function renderLiveCard(role) {
        if (!role) {
            if (els.liveRoleName) els.liveRoleName.textContent = "역할";
            if (els.liveAssignee) els.liveAssignee.textContent = "대기";
            if (els.fortuneBtn) {
                els.fortuneBtn.hidden = true;
                els.fortuneBtn.disabled = true;
            }
            return;
        }
        const roleName = role.role_name || "이름 없는 역할";
        const assigneeName = role.assignee_name || "미배정";
        if (els.liveRoleName) els.liveRoleName.textContent = roleName;
        if (els.liveAssignee) {
            els.liveAssignee.textContent = role.is_unassigned
                ? "미배정"
                : assigneeName;
        }
        if (els.fortuneBtn) {
            els.fortuneBtn.hidden = role.is_unassigned;
            els.fortuneBtn.disabled = role.is_unassigned;
        }
        state.lastFortuneTarget = role.is_unassigned
            ? null
            : {
                targetName: assigneeName,
                sourceLabel: `${roleName} 역할 공개`,
            };
    }

    function cardMarkup(role, index) {
        const revealed = state.revealed.has(index);
        const classes = ["ppr-card"];
        if (revealed) classes.push("is-revealed");
        if (role.is_completed) classes.push("is-completed");
        if (role.is_unassigned) classes.push("is-unassigned");
        const safeRoleName = escapeHtml(role.role_name || "이름 없는 역할");
        const safeAssignee = escapeHtml(role.assignee_name || "미배정");
        const safeSlot = escapeHtml(role.time_slot || "오늘");
        const safeIcon = escapeHtml(role.icon || "📋");
        return `
            <button type="button" class="${classes.join(" ")}" data-index="${index}" aria-label="${safeRoleName} 카드 열기">
                <span class="ppr-card-inner">
                    <span class="ppr-card-face ppr-card-front">
                        <span>
                            <span class="ppr-card-head">
                                <span class="ppr-card-icon" aria-hidden="true">${safeIcon}</span>
                                <span class="ppr-card-slot">${safeSlot}</span>
                            </span>
                            <span class="ppr-card-title">${safeRoleName}</span>
                        </span>
                        <span class="ppr-card-foot">
                            <span class="ppr-card-number">${index + 1}번째 카드</span>
                        </span>
                    </span>
                    <span class="ppr-card-face ppr-card-back">
                        <span>
                            <span class="ppr-card-back-label">${safeRoleName}</span>
                            <span class="ppr-card-assignee">${safeAssignee}</span>
                        </span>
                        <span class="ppr-card-status">${role.is_unassigned ? "미배정" : safeSlot}</span>
                    </span>
                </span>
            </button>
        `;
    }

    function renderCards() {
        if (state.loading) {
            els.cardGrid.innerHTML = '<div class="ppr-empty">역할 불러오는 중</div>';
            return;
        }
        if (!state.roles.length) {
            els.cardGrid.innerHTML = '<div class="ppr-empty">오늘 역할이 없습니다.</div>';
            return;
        }
        els.cardGrid.innerHTML = state.roles.map((role, index) => cardMarkup(role, index)).join("");
    }

    function updateAutoButton() {
        if (!els.autoBtn) {
            return;
        }
        if (state.loading) {
            els.autoBtn.hidden = true;
            els.autoBtn.disabled = true;
            els.autoBtn.textContent = "불러오는 중...";
            return;
        }
        if (!state.roles.length) {
            els.autoBtn.hidden = true;
            els.autoBtn.disabled = true;
            els.autoBtn.textContent = "역할이 필요합니다";
            return;
        }
        els.autoBtn.hidden = false;
        if (state.autoRun) {
            els.autoBtn.disabled = false;
            els.autoBtn.textContent = "자동 중지";
            return;
        }
        const left = unrevealedIndexes().length;
        els.autoBtn.disabled = left === 0;
        els.autoBtn.textContent = left === 0 ? "공개 완료" : "자동 공개";
    }

    function hydrate(payload) {
        state.roles = Array.isArray(payload.roles) ? payload.roles : [];
        state.revealed = new Set();
        state.history = [];
        state.autoRun = false;
        state.lastFortuneTarget = null;
        state.loadedOnce = true;
        if (els.classroomBadge) {
            els.classroomBadge.textContent = payload.classroom_name || "기본 명단";
        }
        renderCards();
        renderHistory();
        renderLiveCard(null);
        updateCounters();
        updateAutoButton();
        setMessage("", null);
    }

    async function loadRoleCards() {
        if (state.loading) {
            return;
        }
        if (!root.dataset.roleCardsUrl) {
            setMessage("역할 데이터를 불러올 주소를 찾지 못했습니다.", "warn");
            return;
        }
        state.loading = true;
        state.autoRun = false;
        renderCards();
        updateAutoButton();
        setMessage("", null);
        if (els.refreshBtn) {
            els.refreshBtn.disabled = true;
            els.refreshBtn.textContent = "불러오는 중...";
        }
        try {
            const response = await fetch(root.dataset.roleCardsUrl, {
                credentials: "same-origin",
                cache: "no-store",
            });
            if (!response.ok) {
                throw new Error("role cards fetch failed");
            }
            const payload = await response.json();
            hydrate(payload);
            dispatchSfx("launch");
        } catch (error) {
            state.roles = [];
            state.revealed = new Set();
            state.history = [];
            state.lastFortuneTarget = null;
            renderCards();
            renderHistory();
            renderLiveCard(null);
            updateCounters();
            setMessage("오늘 역할을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.", "warn");
        } finally {
            state.loading = false;
            updateAutoButton();
            if (els.refreshBtn) {
                els.refreshBtn.disabled = false;
                els.refreshBtn.textContent = "역할 새로고침";
            }
            renderCards();
        }
    }

    async function revealRole(index, source) {
        if (state.loading) {
            return;
        }
        if (index < 0 || index >= state.roles.length) {
            return;
        }
        if (state.revealed.has(index)) {
            if (source === "manual") {
                setMessage("이미 공개된 역할 카드입니다.", "warn");
            }
            return;
        }
        const role = state.roles[index];
        const roleName = role.role_name || "이름 없는 역할";
        const assigneeName = role.assignee_name || "미배정";
        state.revealed.add(index);
        state.history.unshift({
            step: state.revealed.size,
            roleName,
            assigneeName,
        });
        if (state.history.length > state.roles.length) {
            state.history = state.history.slice(0, state.roles.length);
        }
        renderCards();
        renderHistory();
        renderLiveCard(role);
        updateCounters();
        updateAutoButton();
        setMessage("", null);
        presentResult({
            badge: role.is_unassigned ? `미배정 역할 · ${roleName}` : roleName,
            celebration: unrevealedIndexes().length > 0 ? "reveal" : "finale",
            compliment: role.is_unassigned
                ? "아직 담당 학생은 없지만, 이 역할도 오늘 무대의 중요한 장면으로 남겨 둘 수 있어요."
                : `${assigneeName} 학생이 오늘 맡을 임무가 메달처럼 또렷하게 공개됐어요.`,
            fortuneTarget: role.is_unassigned ? null : {
                sourceLabel: `${roleName} 역할 공개`,
                targetName: assigneeName,
            },
            label: "역할 카드 발표",
            meta: role.is_unassigned ? "아직 담당 학생이 정해지지 않았습니다." : `${assigneeName} 학생이 맡은 역할입니다.`,
            mode: "roles",
            nextLabel: unrevealedIndexes().length > 0 ? "다음 역할 계속" : "닫기",
            sourceLabel: "역할 카드 발표",
            winnerName: role.is_unassigned ? roleName : assigneeName,
        });
        if (!unrevealedIndexes().length) {
            state.autoRun = false;
            updateAutoButton();
        }
    }

    function shuffle(list) {
        const copied = [...list];
        for (let i = copied.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copied[i], copied[j]] = [copied[j], copied[i]];
        }
        return copied;
    }

    async function runAuto() {
        if (!state.roles.length || state.loading) {
            return;
        }
        if (state.autoRun) {
            state.autoRun = false;
            updateAutoButton();
            setMessage("", null);
            return;
        }
        const queue = shuffle(unrevealedIndexes());
        if (!queue.length) {
            setMessage("", null);
            updateAutoButton();
            return;
        }
        state.autoRun = true;
        updateAutoButton();
        setMessage("", null);
        dispatchSfx("auto");
        for (const index of queue) {
            if (!state.autoRun) {
                break;
            }
            await revealRole(index, "auto");
            if (!state.autoRun) {
                break;
            }
            await sleep(isReducedMotion() ? 120 : 520);
        }
        state.autoRun = false;
        updateAutoButton();
        if (!unrevealedIndexes().length) {
            setMessage("", null);
        }
    }

    function openFortuneForRole() {
        if (!state.lastFortuneTarget) {
            return;
        }
        root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", { detail: state.lastFortuneTarget }));
    }

    function bindEvents() {
        els.refreshBtn?.addEventListener("click", loadRoleCards);
        els.autoBtn?.addEventListener("click", runAuto);
        els.fortuneBtn?.addEventListener("click", openFortuneForRole);
        els.cardGrid?.addEventListener("click", async (event) => {
            const button = event.target.closest("button[data-index]");
            if (!button) {
                return;
            }
            const index = Number(button.dataset.index);
            if (Number.isNaN(index)) {
                return;
            }
            await revealRole(index, "manual");
        });
        root.addEventListener("ppobgi:mode-change", (event) => {
            const mode = event.detail?.mode;
            if (mode === "roles") {
                if (!state.loadedOnce) {
                    loadRoleCards();
                }
                return;
            }
            if (state.autoRun) {
                state.autoRun = false;
                updateAutoButton();
            }
        });
    }

    function bootstrap() {
        renderCards();
        renderHistory();
        renderLiveCard(null);
        updateCounters();
        updateAutoButton();
        bindEvents();
    }

    bootstrap();
})();

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const els = {
        modal: document.getElementById("ppb-fortune-modal"),
        panel: document.getElementById("ppb-fortune-panel"),
        target: document.getElementById("ppb-fortune-target"),
        category: document.getElementById("ppb-fortune-category"),
        line: document.getElementById("ppb-fortune-line"),
        meaning: document.getElementById("ppb-fortune-meaning"),
        step: document.getElementById("ppb-fortune-step"),
        note: document.getElementById("ppb-fortune-note"),
        feedback: document.getElementById("ppb-fortune-feedback"),
        rerollBtn: document.getElementById("ppb-fortune-reroll-btn"),
        copyBtn: document.getElementById("ppb-fortune-copy-btn"),
        closeBtn: document.getElementById("ppb-fortune-close-btn"),
    };

    if (!els.modal || !els.panel || !els.line) {
        return;
    }

    const FORTUNE_COOKIES = [
        { category: "용기", line: "지금의 떨림은 네가 자라고 있다는 신호야.", meaning: "불안이 있다고 해서 뒤로 가는 건 아니야. 중요한 건 그 마음을 안고도 한 걸음 내딛는 거야.", step: "오늘 한 번은 스스로 먼저 말해 보기" },
        { category: "용기", line: "작은 시도 하나가 오늘을 바꿀 수 있어.", meaning: "완벽한 시작보다 가벼운 시도가 더 큰 문을 열어줄 때가 많아.", step: "망설이던 활동에 5분만 먼저 참여해 보기" },
        { category: "용기", line: "너는 생각보다 훨씬 단단한 사람일 수 있어.", meaning: "힘들 때도 자리를 지키는 마음은 이미 큰 힘이야.", step: "오늘 힘들었던 일을 한 가지 적어 보고 버틴 나를 인정해 보기" },
        { category: "용기", line: "실수는 멈춤이 아니라 다시 해보라는 초대야.", meaning: "실수한 순간에도 배우는 힘은 계속 자라고 있어.", step: "실수한 일에서 다음에 바꿀 점 한 가지만 정해 보기" },
        { category: "회복", line: "조금 쉬어도 너의 가치가 줄어들지 않아.", meaning: "지친 날에는 속도를 낮추는 것도 중요한 선택이야.", step: "숨을 천천히 세 번 쉬고 어깨 힘을 풀어 보기" },
        { category: "회복", line: "오늘 마음이 무거워도 내일의 빛까지 사라진 건 아니야.", meaning: "지금 힘든 기분은 지나가는 구름처럼 머물다 흘러갈 수 있어.", step: "지금 내 마음을 한 단어로 적어 보기" },
        { category: "회복", line: "괜찮지 않은 날에도 괜찮아질 길은 남아 있어.", meaning: "마음이 흔들리는 날일수록 누군가의 도움을 받는 것이 더 중요해.", step: "믿는 어른 한 명 떠올려 보기" },
        { category: "회복", line: "너는 쉬는 동안에도 다시 힘을 모으고 있어.", meaning: "멈춤은 뒤처짐이 아니라 회복의 시간일 수 있어.", step: "오늘 나를 편하게 해주는 행동 하나 해 보기" },
        { category: "관계", line: "부드러운 한마디가 생각보다 큰 다리가 돼.", meaning: "관계는 거창한 말보다 작은 인사와 표정에서 시작될 때가 많아.", step: "오늘 먼저 인사 한 번 건네 보기" },
        { category: "관계", line: "오해가 생겨도 다시 가까워질 기회는 남아 있어.", meaning: "서로의 마음을 다 알 수 없기 때문에 천천히 풀어 가면 돼.", step: "섭섭했던 일을 차분한 말로 바꿔 생각해 보기" },
        { category: "관계", line: "네 진심은 천천히라도 전해질 수 있어.", meaning: "말이 서툴러도 진심이 사라지는 건 아니야.", step: "고마운 사람에게 짧게라도 표현해 보기" },
        { category: "관계", line: "친절은 너를 약하게 만들지 않아.", meaning: "따뜻하게 말하는 사람은 오히려 관계를 더 오래 지키는 힘이 있어.", step: "오늘 누군가에게 배려 한 가지 실천해 보기" },
        { category: "시작", line: "새롭게 해보려는 마음만으로도 이미 출발한 거야.", meaning: "시작은 준비가 완벽해질 때가 아니라 마음이 움직일 때 열리기도 해.", step: "미뤄 둔 일을 3분만 시작해 보기" },
        { category: "시작", line: "천천히 시작해도 충분히 시작한 거야.", meaning: "빠른 사람만 잘하는 것이 아니라 꾸준한 사람이 끝까지 가는 경우도 많아.", step: "오늘 해야 할 일의 첫 줄만 해 보기" },
        { category: "시작", line: "어제보다 조금만 다르게 해도 큰 변화가 될 수 있어.", meaning: "작은 변화가 쌓이면 스스로도 놀랄 만큼 달라질 수 있어.", step: "평소와 다른 좋은 습관 하나 골라 보기" },
        { category: "시작", line: "새로운 장면은 늘 낯설지만 그 안에서 네 힘도 자라.", meaning: "낯섦은 실패의 신호가 아니라 배우는 중이라는 증거일 수 있어.", step: "처음 해보는 일에 질문 하나 해 보기" },
        { category: "노력", line: "보이지 않는 노력도 너를 조용히 키우고 있어.", meaning: "바로 티 나지 않아도 쌓이는 힘은 분명히 있어.", step: "오늘 내가 해낸 노력 한 가지 적어 보기" },
        { category: "노력", line: "끝까지 해보려는 태도는 큰 재능이야.", meaning: "포기하지 않으려는 마음은 어떤 성적표보다 오래 남는 힘이 돼.", step: "하던 일을 마지막 5분만 더 이어 가기" },
        { category: "노력", line: "조금 늦어도 너만의 속도로 가면 돼.", meaning: "남과 비교하지 않을 때 내 진짜 성장이 더 잘 보여.", step: "비교 대신 오늘의 내 변화 한 가지 찾기" },
        { category: "노력", line: "네가 애쓴 시간은 헛되지 않아.", meaning: "결과가 아쉬워도 노력한 과정은 다음 기회를 위한 바탕이 돼.", step: "오늘 애쓴 순간을 스스로 칭찬해 보기" },
        { category: "감사", line: "고마움을 떠올리면 마음이 조금 더 따뜻해질 수 있어.", meaning: "감사는 문제를 없애지는 못해도 마음을 버티게 하는 힘이 돼.", step: "오늘 고마운 사람이나 장면 한 가지 떠올리기" },
        { category: "감사", line: "도움을 받았던 기억은 다시 친절을 낳아.", meaning: "받은 따뜻함을 다른 사람에게 건네면 교실도 더 편안해질 수 있어.", step: "도와준 사람에게 짧게 고맙다고 말해 보기" },
        { category: "감사", line: "네가 가진 좋은 점은 이미 누군가에게 힘이 되고 있어.", meaning: "밝은 표정, 기다려 주는 마음, 작은 친절도 모두 소중한 힘이야.", step: "내 장점 하나를 조용히 떠올려 보기" },
        { category: "감사", line: "평범한 하루에도 반짝이는 순간은 숨어 있어.", meaning: "작은 즐거움을 찾는 눈이 있으면 하루가 덜 버겁게 느껴질 수 있어.", step: "오늘 좋았던 순간 하나를 기억해 두기" },
    ];

    const state = {
        open: false,
        current: null,
        context: null,
    };

    function setFeedback(text, kind) {
        if (!els.feedback) {
            return;
        }
        els.feedback.textContent = text || "";
        els.feedback.classList.remove("warn", "info");
        if (kind) {
            els.feedback.classList.add(kind);
        }
    }

    function pickFortune(excludeLine) {
        const pool = FORTUNE_COOKIES.filter((item) => item.line !== excludeLine);
        const source = pool.length ? pool : FORTUNE_COOKIES;
        return source[Math.floor(Math.random() * source.length)];
    }

    function renderFortune() {
        if (!state.current) {
            return;
        }
        const targetName = String(state.context?.targetName || "오늘의 응원").trim();
        if (els.target) {
            els.target.textContent = targetName ? `${targetName}에게 건네는 말` : "오늘의 응원";
        }
        if (els.category) {
            els.category.textContent = `${state.current.category} 메시지`;
        }
        if (els.line) {
            els.line.textContent = state.current.line;
        }
        if (els.meaning) {
            els.meaning.textContent = state.current.meaning;
        }
        if (els.step) {
            els.step.textContent = state.current.step;
        }
        const sourceLabel = state.context?.sourceLabel;
        setFeedback(sourceLabel ? `${sourceLabel} 뒤에 건네기 좋은 문장입니다.` : "아이에게 힘이 되는 짧은 문장을 골랐습니다.", "info");
    }

    function closeFortune() {
        if (!state.open) {
            return;
        }
        els.modal.classList.add("is-hidden");
        els.modal.setAttribute("aria-hidden", "true");
        root.classList.remove("ppb-fortune-open");
        state.open = false;
    }

    function openFortune(detail) {
        state.context = detail || {};
        state.current = pickFortune();
        if (els.note) {
            els.note.value = "";
        }
        renderFortune();
        els.modal.classList.remove("is-hidden");
        els.modal.setAttribute("aria-hidden", "false");
        root.classList.add("ppb-fortune-open");
        state.open = true;
        els.rerollBtn?.focus();
    }

    function rerollFortune() {
        if (!state.current) {
            return;
        }
        state.current = pickFortune(state.current.line);
        renderFortune();
    }

    function buildCopyText() {
        const lines = [];
        const targetName = String(state.context?.targetName || "오늘의 응원").trim();
        if (targetName) {
            lines.push(`${targetName}에게 건네는 말`);
        }
        lines.push(state.current.line);
        lines.push(state.current.meaning);
        lines.push(`오늘 해볼 한 걸음: ${state.current.step}`);
        const note = String(els.note?.value || "").trim();
        if (note) {
            lines.push(`선생님 한마디: ${note}`);
        }
        return lines.join("\n");
    }

    async function copyFortune() {
        if (!state.current) {
            return;
        }
        try {
            if (!navigator.clipboard?.writeText) {
                throw new Error("clipboard unavailable");
            }
            await navigator.clipboard.writeText(buildCopyText());
            setFeedback("문장을 복사했습니다. 상담 메모나 전달 문구로 바로 쓸 수 있습니다.", "info");
        } catch (error) {
            setFeedback("복사에 실패했습니다. 직접 선택해 복사해 주세요.", "warn");
        }
    }

    function handleKeydown(event) {
        if (!state.open) {
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            closeFortune();
        }
    }

    function bindEvents() {
        root.addEventListener("ppobgi:open-fortune", (event) => openFortune(event.detail || {}));
        els.rerollBtn?.addEventListener("click", rerollFortune);
        els.copyBtn?.addEventListener("click", copyFortune);
        els.closeBtn?.addEventListener("click", closeFortune);
        els.modal?.addEventListener("click", (event) => {
            if (event.target === els.modal) {
                closeFortune();
            }
        });
        els.panel?.addEventListener("click", (event) => event.stopPropagation());
        document.addEventListener("keydown", handleKeydown);
    }

    bindEvents();
})();
