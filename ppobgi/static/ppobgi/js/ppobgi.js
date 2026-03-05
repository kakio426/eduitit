"use strict";

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
    const STAR_ROSTER_KEY = "ppobgi_star_roster_v1";

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

    function buildOrbs(names) {
        const shuffled = shuffle(names);
        return shuffled.map((name) => {
            const color = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
            return {
                name,
                core: color.core,
                glow: color.glow,
                size: Math.max(54, Math.min(90, 96 - shuffled.length * 0.75 + Math.random() * 10)),
                delay: Math.random() * 2.4,
                floatKey: Math.random() > 0.5 ? "ppb-float" : "ppb-float-reverse",
                offsetY: Math.random() * 16 - 8,
                offsetX: Math.random() * 14 - 7,
                rotation: Math.random() * 18 - 9,
            };
        });
    }

    function renderOrbs() {
        if (!els.orbGrid) {
            return;
        }
        const orbs = buildOrbs(state.remainingNames);
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
            btn.style.setProperty("--orb-size", `${orb.size}px`);
            btn.style.setProperty("--orb-core", orb.core);
            btn.style.setProperty("--orb-glow", orb.glow);
            btn.style.setProperty("--orb-delay", `${orb.delay}s`);
            btn.style.setProperty("--orb-float", orb.floatKey);
            btn.style.setProperty("--orb-offset-y", `${orb.offsetY}px`);
            btn.style.setProperty("--orb-offset-x", `${orb.offsetX}px`);
            btn.style.setProperty("--orb-rotation", `${orb.rotation}deg`);
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
                ? "모든 별이 사라졌어요"
                : "빛나는 별 하나를 선택하세요";
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
            els.liveName.textContent = name || "대기 중";
        }
        if (els.liveMeta) {
            els.liveMeta.textContent = meta || "별을 선택하면 여기에 결과가 나타납니다.";
        }
        els.liveCard?.classList.toggle("is-selected", Boolean(name));
    }

    function setPickedPanel(name) {
        const pickedName = normalizeName(name);
        if (els.pickedName) {
            els.pickedName.textContent = pickedName || "아직 뽑지 않았어요";
        }
        els.pickedCard?.classList.toggle("is-picked", Boolean(pickedName));
    }

    function focusFirstOrb() {
        const orb = els.orbGrid?.querySelector(".ppb-orb:not(:disabled)");
        orb?.focus();
    }

    function closeResultModal(shouldFocus = true) {
        if (!els.resultModal || !state.resultModalOpen) {
            return;
        }
        els.resultModal.classList.add("is-hidden");
        els.resultModal.setAttribute("aria-hidden", "true");
        root.classList.remove("ppb-result-open");
        state.resultModalOpen = false;
        if (shouldFocus && state.appState === "universe") {
            focusFirstOrb();
        }
    }

    function openResultModal(name, leftCount) {
        if (!els.resultModal || !els.resultName || !els.resultMeta) {
            return;
        }
        const pickedName = normalizeName(name) || "이름 없음";
        els.resultName.textContent = pickedName;
        els.resultMeta.textContent = leftCount > 0
            ? `남은 인원 ${leftCount}명`
            : "모든 학생 추첨 완료";
        if (els.resultNextBtn) {
            els.resultNextBtn.textContent = leftCount > 0 ? "다음 추첨 계속" : "닫기";
        }
        els.resultModal.classList.remove("is-hidden");
        els.resultModal.setAttribute("aria-hidden", "false");
        root.classList.add("ppb-result-open");
        state.resultModalOpen = true;
        els.resultNextBtn?.focus();
    }

    function persistRoster(names) {
        try {
            window.localStorage.setItem(STAR_ROSTER_KEY, JSON.stringify(names));
        } catch (error) {
            // noop
        }
    }

    function loadStoredRoster() {
        try {
            const raw = window.localStorage.getItem(STAR_ROSTER_KEY);
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
        if (els.input) {
            els.input.value = names.join("\n");
        }
        updateSetupStats();
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard("준비 완료", `${names.length}명 명단으로 추첨을 시작하세요.`);
        setPickedPanel("");
        closeResultModal(false);
        if (message) {
            setSetupMessage(message, "info");
        }
        persistRoster(names);
        setScreen("universe");
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
        setLiveCard(
            name,
            left > 0
                ? `남은 인원 ${left}명 · 스페이스바로 다음 추첨`
                : "모든 학생 추첨 완료",
        );
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
        updateCounterUI();
        renderHistory();
        renderOrbs();
        setLiveCard("다시 시작", `${state.totalNames.length}명 명단으로 추첨을 다시 시작합니다.`);
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
        setLiveCard("되돌리기", `${recent.name} 학생을 추첨 후보에 다시 추가했습니다.`);
        setPickedPanel(state.history[0]?.name || "");
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
        setLiveCard("명단 업데이트 완료", `${parsed.valid.length}명 명단으로 새 추첨을 시작합니다.`);
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
                targetBtn.textContent = isEditor ? "당번 명단" : "당번 명단 불러오기";
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
        els.fullscreenBtn.textContent = document.fullscreenElement ? "전체화면 종료" : "전체화면";
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
        if (state.resultModalOpen) {
            if (event.key === "Escape" || event.key === "Enter" || event.code === "Space") {
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
        els.resultNextBtn?.addEventListener("click", () => closeResultModal());
        els.resultModal?.addEventListener("click", (event) => {
            if (event.target === els.resultModal) {
                closeResultModal();
            }
        });
        els.resultPanel?.addEventListener("click", (event) => event.stopPropagation());

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
        });
        els.fullscreenBtn?.addEventListener("click", toggleFullscreen);
        document.addEventListener("fullscreenchange", syncFullscreenBtn);
        document.addEventListener("keydown", handleKeydown);
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

        const stored = loadStoredRoster();
        if (stored.length > 0) {
            applyRosterAndStart(stored, `저장된 명단 ${stored.length}명을 불러왔습니다.`);
            setLiveCard("지난 명단 불러옴", "바로 별을 선택해 추첨을 시작할 수 있습니다.");
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

    const modeStarsBtn = document.getElementById("ppb-mode-stars-btn");
    const modeLadderBtn = document.getElementById("ppb-mode-ladder-btn");
    const modeStars = document.getElementById("ppb-mode-stars");
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

    if (!modeStarsBtn || !modeLadderBtn || !modeStars || !modeLadder || !els.setupScreen || !els.stageScreen) {
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

    function setMode(mode) {
        const isStar = mode === "stars";
        modeStars.classList.toggle("is-hidden", !isStar);
        modeLadder.classList.toggle("is-hidden", isStar);
        modeStarsBtn.classList.toggle("is-active", isStar);
        modeLadderBtn.classList.toggle("is-active", !isStar);
        modeStarsBtn.setAttribute("aria-selected", isStar ? "true" : "false");
        modeLadderBtn.setAttribute("aria-selected", isStar ? "false" : "true");
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
            els.roleWrap.classList.toggle("is-disabled", disabled);
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
            warnings.length ? warnings.join(" / ") : "사다리 생성 준비가 완료되었습니다.",
            warnings.length ? "warn" : "info",
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
            els.autoBtn.disabled = true;
            els.autoBtn.textContent = "역할 발표 쇼 시작";
            return;
        }
        if (state.autoRun) {
            els.autoBtn.disabled = false;
            els.autoBtn.textContent = "자동 발표 중지";
            return;
        }
        const left = unresolvedIndexes().length;
        els.autoBtn.disabled = left === 0;
        els.autoBtn.textContent = left === 0 ? "모든 역할 발표 완료" : "역할 발표 쇼 시작";
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
        setMessage(els.stageMessage, outcome === "당첨" ? `${name} 학생이 당첨되었습니다!` : `${name} 학생 결과: ${outcome}`, "info");

        if (state.revealedTop.size === scene.participants.length) {
            state.autoRun = false;
            setMessage(els.stageMessage, "모든 발표가 완료되었습니다.", "info");
        }
        updateAutoButton();
        state.animating = false;
    }

    async function runAuto() {
        if (state.mode !== "roles" || !state.scene) return;
        if (state.autoRun) {
            state.autoRun = false;
            updateAutoButton();
            setMessage(els.stageMessage, "자동 발표를 중지했습니다.", "warn");
            return;
        }
        const queue = shuffle(unresolvedIndexes());
        if (!queue.length) {
            setMessage(els.stageMessage, "이미 모든 역할 발표가 완료되었습니다.", "info");
            updateAutoButton();
            return;
        }
        state.autoRun = true;
        updateAutoButton();
        setMessage(els.stageMessage, "역할 발표 쇼를 시작합니다.", "info");
        for (const idx of queue) {
            if (!state.autoRun) break;
            await reveal(idx, "auto");
            if (!state.autoRun) break;
            await sleep(isReducedMotion() ? 120 : 520);
        }
        state.autoRun = false;
        updateAutoButton();
        if (!unresolvedIndexes().length) setMessage(els.stageMessage, "역할 발표 쇼가 끝났습니다.", "info");
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
        showLive("준비 완료", "사다리 결과가 여기 표시됩니다.");
        if (els.stageTitle) {
            els.stageTitle.textContent =
                mode === "roles"
                    ? "역할 배정 쇼: 이름을 누르거나 자동 발표를 시작하세요"
                    : "당첨 1명을 찾기 위해 이름을 선택하세요";
        }
        setMessage(els.stageMessage, "사다리 생성이 완료되었습니다. 상단 이름을 눌러 결과를 공개하세요.", "info");
        setLadderScreen("stage");
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
        showLive("준비 완료", "사다리 결과가 여기 표시됩니다.");
        setMessage(els.stageMessage, "새 사다리로 다시 준비되었습니다.", "info");
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
            button.textContent = "당번 명단 불러오기";
        }
    }

    function bindEvents() {
        modeStarsBtn.addEventListener("click", () => setMode("stars"));
        modeLadderBtn.addEventListener("click", () => setMode("ladder"));
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
    }

    function bootstrap() {
        if (els.input) els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
        if (els.roleInput) els.roleInput.value = DEFAULT_ROLES;
        syncRoleWrap();
        updateSetupStats();
        renderFeed();
        updateAutoButton();
        setLadderScreen("setup");
        setMode("stars");
        bindEvents();
    }

    bootstrap();
})();


