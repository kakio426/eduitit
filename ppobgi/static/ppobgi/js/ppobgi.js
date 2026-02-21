"use strict";

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const els = {
        screens: {
            setup: document.getElementById("ppb-setup"),
            universe: document.getElementById("ppb-universe"),
            reveal: document.getElementById("ppb-reveal"),
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
        selectedName: document.getElementById("ppb-selected-name"),
        revealLeft: document.getElementById("ppb-reveal-left"),
        revealRound: document.getElementById("ppb-reveal-round"),
        nextDrawBtn: document.getElementById("ppb-next-draw-btn"),
        resetBtn: document.getElementById("ppb-reset-btn"),
        resetFromUniverseBtn: document.getElementById("ppb-reset-from-universe-btn"),
        historyUniverse: document.getElementById("ppb-history-list-universe"),
        historyReveal: document.getElementById("ppb-history-list-reveal"),
        reduceMotion: document.getElementById("ppb-reduce-motion"),
        fullscreenBtn: document.getElementById("ppb-fullscreen-btn"),
    };

    const ORB_COLORS = [
        { main: "rgba(253, 224, 71, 1)", glow: "rgba(253, 224, 71, 0.6)" },
        { main: "rgba(147, 197, 253, 1)", glow: "rgba(147, 197, 253, 0.6)" },
        { main: "rgba(249, 168, 212, 1)", glow: "rgba(249, 168, 212, 0.6)" },
        { main: "rgba(216, 180, 254, 1)", glow: "rgba(216, 180, 254, 0.6)" },
        { main: "rgba(255, 255, 255, 1)", glow: "rgba(255, 255, 255, 0.55)" },
    ];

    const MAX_NAMES = 40;
    const REDUCE_MOTION_KEY = "ppobgi_reduce_motion";

    const state = {
        appState: "setup",
        totalNames: [],
        remainingNames: [],
        history: [],
        selectedName: "",
        transitionLock: false,
        reduceMotion: false,
    };

    function decodeDefaultNames(raw) {
        if (!raw) {
            return "";
        }
        return raw.replace(/\\n/g, "\n");
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
        return name.replace(/\s+/g, " ").trim();
    }

    function parseNameInput(rawText) {
        const rows = rawText.split(/\r?\n/);
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

    function setSetupMessage(text, kind) {
        if (!els.setupMessage) {
            return;
        }
        els.setupMessage.textContent = text;
        els.setupMessage.classList.remove("warn", "info");
        if (kind) {
            els.setupMessage.classList.add(kind);
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

    function buildOrbs(names) {
        const shuffled = shuffle(names);
        return shuffled.map((name, idx) => {
            const color = ORB_COLORS[Math.floor(Math.random() * ORB_COLORS.length)];
            return {
                id: idx,
                name,
                main: color.main,
                glow: color.glow,
                size: Math.max(46, Math.min(82, 86 - shuffled.length * 0.5 + Math.random() * 8)),
                delay: Math.random() * 2.5,
                floatKey: Math.random() > 0.5 ? "ppb-float" : "ppb-float-reverse",
                offsetY: Math.random() * 18 - 9,
                offsetX: Math.random() * 14 - 7,
            };
        });
    }

    function renderOrbs() {
        if (!els.orbGrid) {
            return;
        }

        const orbs = buildOrbs(state.remainingNames);
        const fragment = document.createDocumentFragment();
        orbs.forEach((orb) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "ppb-orb";
            btn.setAttribute("aria-label", "별 선택");
            btn.style.setProperty("--orb-size", `${orb.size}px`);
            btn.style.setProperty("--orb-main", orb.main);
            btn.style.setProperty("--orb-glow", orb.glow);
            btn.style.setProperty("--orb-delay", `${orb.delay}s`);
            btn.style.setProperty("--orb-float", orb.floatKey);
            btn.style.setProperty("--orb-offset-y", `${orb.offsetY}px`);
            btn.style.setProperty("--orb-offset-x", `${orb.offsetX}px`);
            btn.addEventListener("click", () => handleOrbClick(orb.name));
            fragment.appendChild(btn);
        });
        els.orbGrid.replaceChildren(fragment);
    }

    function renderHistory() {
        const renderTarget = (target) => {
            if (!target) {
                return;
            }
            if (state.history.length === 0) {
                const empty = document.createElement("li");
                empty.innerHTML = '<span class="ppb-history-round">기록 없음</span><span class="ppb-history-name">-</span>';
                target.replaceChildren(empty);
                return;
            }
            const fragment = document.createDocumentFragment();
            state.history.forEach((item) => {
                const li = document.createElement("li");
                li.innerHTML =
                    `<span class="ppb-history-round">${item.round}회차</span>` +
                    `<span class="ppb-history-name">${item.name}</span>`;
                fragment.appendChild(li);
            });
            target.replaceChildren(fragment);
        };

        renderTarget(els.historyUniverse);
        renderTarget(els.historyReveal);
    }

    function updateCounterUI() {
        const total = state.totalNames.length;
        const left = state.remainingNames.length;
        const round = state.history.length;

        if (els.chipTotal) {
            els.chipTotal.textContent = String(total);
        }
        if (els.chipLeft) {
            els.chipLeft.textContent = String(left);
        }
        if (els.chipRound) {
            els.chipRound.textContent = String(round);
        }
        if (els.revealLeft) {
            els.revealLeft.textContent = String(left);
        }
        if (els.revealRound) {
            els.revealRound.textContent = String(round);
        }
        if (els.nextDrawBtn) {
            els.nextDrawBtn.disabled = left <= 0;
            els.nextDrawBtn.textContent = left > 0 ? "다음 추첨" : "모든 인원 추첨 완료";
        }
    }

    function renderParticles() {
        if (!els.particles) {
            return;
        }
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < 20; i += 1) {
            const particle = document.createElement("span");
            particle.className = "ppb-particle";
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.animationDuration = `${Math.random() * 5 + 5}s`;
            particle.style.animationDelay = `${Math.random() * 2}s`;
            fragment.appendChild(particle);
        }
        els.particles.replaceChildren(fragment);
    }

    function createStars() {
        if (!els.stars) {
            return;
        }
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < 140; i += 1) {
            const star = document.createElement("span");
            star.className = "ppb-star";
            const size = Math.random() * 2 + 0.5;
            star.style.left = `${Math.random() * 100}%`;
            star.style.top = `${Math.random() * 100}%`;
            star.style.width = `${size}px`;
            star.style.height = `${size}px`;
            star.style.opacity = String(Math.random() * 0.5 + 0.1);
            star.style.animationDuration = `${3 + Math.random() * 4}s`;
            star.style.animationDelay = `${Math.random() * 5}s`;
            fragment.appendChild(star);
        }
        els.stars.replaceChildren(fragment);
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

        state.totalNames = parsed.valid;
        state.remainingNames = [...parsed.valid];
        state.history = [];
        state.selectedName = "";
        state.transitionLock = false;

        updateCounterUI();
        renderHistory();
        renderOrbs();
        setScreen("universe");
    }

    function handleOrbClick(name) {
        if (state.transitionLock) {
            return;
        }
        state.transitionLock = true;
        state.selectedName = name;

        state.remainingNames = state.remainingNames.filter((item) => item !== name);
        state.history.unshift({
            round: state.history.length + 1,
            name,
        });

        if (els.flash) {
            els.flash.style.opacity = "1";
        }

        const transitionDelay = state.reduceMotion ? 140 : 700;
        window.setTimeout(() => {
            if (els.selectedName) {
                els.selectedName.textContent = state.selectedName;
            }
            renderParticles();
            updateCounterUI();
            renderHistory();
            setScreen("reveal");
            if (els.flash) {
                els.flash.style.opacity = "0";
            }
            state.transitionLock = false;
        }, transitionDelay);
    }

    function goNextDraw() {
        if (state.remainingNames.length <= 0) {
            return;
        }
        setScreen("universe");
        renderOrbs();
        updateCounterUI();
        renderHistory();
    }

    function resetAll() {
        state.totalNames = [];
        state.remainingNames = [];
        state.history = [];
        state.selectedName = "";
        setScreen("setup");
        updateCounterUI();
        renderHistory();
        updateSetupStats();
    }

    async function loadRosterNames() {
        const rosterUrl = root.dataset.rosterUrl || "";
        if (!rosterUrl || !els.input) {
            return;
        }

        if (els.loadRosterBtn) {
            els.loadRosterBtn.disabled = true;
            els.loadRosterBtn.textContent = "명단 불러오는 중...";
        }
        try {
            const response = await window.fetch(rosterUrl, { credentials: "same-origin" });
            if (!response.ok) {
                throw new Error("명단을 가져오지 못했습니다.");
            }
            const data = await response.json();
            const names = Array.isArray(data.names) ? data.names : [];
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
            if (els.loadRosterBtn) {
                els.loadRosterBtn.disabled = false;
                els.loadRosterBtn.textContent = "당번 명단 불러오기";
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

    function bindEvents() {
        els.input?.addEventListener("input", updateSetupStats);
        els.startBtn?.addEventListener("click", startDraw);
        els.clearInputBtn?.addEventListener("click", () => {
            if (els.input) {
                els.input.value = "";
            }
            updateSetupStats();
        });
        els.loadSampleBtn?.addEventListener("click", () => {
            if (els.input) {
                els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
            }
            updateSetupStats();
            setSetupMessage("예시 명단을 불러왔습니다.", "info");
        });
        els.loadRosterBtn?.addEventListener("click", loadRosterNames);
        els.nextDrawBtn?.addEventListener("click", goNextDraw);
        els.resetBtn?.addEventListener("click", resetAll);
        els.resetFromUniverseBtn?.addEventListener("click", resetAll);
        els.reduceMotion?.addEventListener("change", (event) => {
            applyReduceMotion(Boolean(event.target.checked));
        });
        els.fullscreenBtn?.addEventListener("click", toggleFullscreen);
        document.addEventListener("fullscreenchange", syncFullscreenBtn);
    }

    function bootstrap() {
        if (els.input) {
            els.input.value = decodeDefaultNames(root.dataset.defaultNames || "");
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
        syncFullscreenBtn();
    }

    bootstrap();
})();

