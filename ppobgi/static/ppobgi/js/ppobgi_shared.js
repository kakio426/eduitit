"use strict";

(function () {
    const root = document.getElementById("ppobgi-app");
    if (!root) {
        return;
    }

    const MODE_CONFIG = {
        stars: {
            buttonId: "ppb-mode-stars-btn",
            viewId: "ppb-mode-stars",
            label: "별빛 추첨기",
            desc: "별을 누르면 반짝 폭발과 함께 오늘의 주인공이 크게 공개됩니다.",
            badge: "오늘의 별빛 주인공",
            compliments: [
                "무대 조명이 이 학생을 기다리고 있었어요.",
                "오늘의 별빛이 딱 이 순간을 환하게 비춰 줬어요.",
                "이름이 뜨는 순간 교실 분위기가 한 번 더 살아났어요.",
            ],
        },
        ladder: {
            buttonId: "ppb-mode-ladder-btn",
            viewId: "ppb-mode-ladder",
            label: "사다리 뽑기",
            desc: "네온 사다리 경로를 따라 결과가 보여져서 아이들이 끝까지 집중하기 좋습니다.",
            badge: "사다리 결승 주인공",
            compliments: [
                "끝까지 따라간 길이 이 학생에게 딱 멈췄어요.",
                "긴장감이 모였다가 한 번에 시원하게 터졌어요.",
                "모두가 지켜보던 결승 게이트가 환하게 열렸어요.",
            ],
        },
        sequence: {
            buttonId: "ppb-mode-sequence-btn",
            viewId: "ppb-mode-sequence",
            label: "순서 뽑기",
            desc: "발표와 활동 순서를 카드처럼 한 명씩 자신 있게 공개합니다.",
            badge: "오늘의 발표 스타",
            compliments: [
                "차례가 선명하게 공개되니 시작할 준비가 더 쉬워졌어요.",
                "다음 순서를 기다리던 분위기가 기분 좋게 이어집니다.",
                "무대의 다음 장면을 이 학생이 자신 있게 이어 갑니다.",
            ],
        },
        teams: {
            buttonId: "ppb-mode-teams-btn",
            viewId: "ppb-mode-teams",
            label: "팀 나누기",
            desc: "팀 깃발처럼 배치를 하나씩 보여 주며 자연스럽게 모둠을 구성합니다.",
            badge: "팀 발표 주인공",
            compliments: [
                "팀이 완성될수록 교실 에너지도 더 커지고 있어요.",
                "이 학생이 들어가며 팀 색깔이 더 또렷해졌어요.",
                "팀 깃발이 올라가는 순간 분위기가 훨씬 선명해졌어요.",
            ],
        },
        meteor: {
            buttonId: "ppb-mode-meteor-btn",
            viewId: "ppb-mode-meteor",
            label: "유성우 뽑기",
            desc: "유성이 쏟아지듯 이름이 공개돼서 짧은 활동에도 임팩트가 큽니다.",
            badge: "유성우 주인공",
            compliments: [
                "밤하늘을 가르던 유성이 이 학생의 이름으로 완성됐어요.",
                "짧은 공개인데도 무대 임팩트가 크게 남아요.",
                "유성 충돌처럼 눈에 딱 들어오는 순간이 만들어졌어요.",
            ],
        },
        roles: {
            buttonId: "ppb-mode-roles-btn",
            viewId: "ppb-mode-roles",
            label: "역할 카드",
            desc: "오늘의 역할을 트로피 카드처럼 펼쳐 아이들이 자기 임무를 기대하게 만듭니다.",
            badge: "오늘의 역할 주인공",
            compliments: [
                "오늘 맡은 역할이 메달처럼 또렷하게 빛났어요.",
                "이 학생이 맡을 임무가 기대감 있게 공개됐어요.",
                "역할이 발표되는 순간 책임감도 멋지게 시작됩니다.",
            ],
        },
    };

    const AUDIO_FILES = {
        applause: "applause-tail.wav",
        arming: "arming-rise.wav",
        close: "panel-close.wav",
        finale: "finale-fanfare.wav",
        mode: "mode-shift.wav",
        reveal: "reveal-hit.wav",
        suspense: "suspense-pulse.wav",
        tab: "ui-tab.wav",
        undo: "undo-soft.wav",
    };

    const AUDIO_VOLUME = {
        applause: 0.72,
        arming: 0.6,
        close: 0.46,
        finale: 0.88,
        mode: 0.5,
        reveal: 0.8,
        suspense: 0.54,
        tab: 0.44,
        undo: 0.52,
    };

    const els = {
        audioBtn: document.getElementById("ppb-audio-btn"),
        resultBadge: document.getElementById("ppb-result-badge"),
        resultCompliment: document.getElementById("ppb-result-compliment"),
        resultFortuneBtn: document.getElementById("ppb-result-fortune-btn"),
        resultLabel: document.getElementById("ppb-result-label"),
        resultMeta: document.getElementById("ppb-result-meta"),
        resultModal: document.getElementById("ppb-result-modal"),
        resultName: document.getElementById("ppb-result-name"),
        resultNextBtn: document.getElementById("ppb-result-next-btn"),
        resultPanel: document.getElementById("ppb-result-panel"),
        resultPhase: document.getElementById("ppb-result-phase"),
        resultSource: document.getElementById("ppb-result-source"),
        resultWait: document.getElementById("ppb-result-wait"),
        stageDesc: document.getElementById("ppb-shell-mode-desc"),
        stageTitle: document.getElementById("ppb-shell-mode-label"),
    };

    const scope = String(root.dataset.storageScope || "anonymous");
    const showProfile = String(root.dataset.showProfile || "premium_gameshow");
    const audioPackBase = String(root.dataset.audioPackBase || "");
    const audioPackName = String(root.dataset.audioPackName || "premium_gameshow_v1");
    const audioPackVersion = String(root.dataset.audioPackVersion || "1");
    const defaultAudioEnabled = String(root.dataset.audioDefault || "on").toLowerCase() !== "off";
    const state = {
        activeMode: "stars",
        audioEnabled: defaultAudioEnabled,
        audioUnlocked: false,
        nextReady: false,
        openTimers: [],
        presentationDetail: null,
        presentationOpen: false,
    };

    function buildScopedStorageKey(name) {
        return `ppobgi:${name}:${scope}`;
    }

    function readLocalStorage(key) {
        try {
            return window.localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function writeLocalStorage(key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (error) {
            // Ignore kiosk/private mode storage failures.
        }
    }

    function buildAudioUrl(fileName) {
        if (!audioPackBase) {
            return "";
        }
        return `${audioPackBase}${fileName}`;
    }

    function unlockAudio() {
        state.audioUnlocked = true;
    }

    function playSound(cue) {
        const cueMap = {
            auto: "suspense",
            final: "finale",
            launch: "arming",
            mode: "mode",
            reveal: "reveal",
            shuffle: "tab",
            undo: "undo",
        };
        const resolvedCue = AUDIO_FILES[cue] ? cue : (cueMap[cue] || "reveal");
        if (!state.audioEnabled || !state.audioUnlocked) {
            return;
        }
        const src = buildAudioUrl(AUDIO_FILES[resolvedCue]);
        if (!src) {
            return;
        }
        try {
            const audio = new Audio(src);
            audio.preload = "auto";
            audio.volume = AUDIO_VOLUME[resolvedCue] || 0.6;
            audio.play().catch(() => {});
        } catch (error) {
            // Ignore audio failures to keep the presentation moving.
        }
    }

    function updateAudioButton() {
        if (!els.audioBtn) {
            return;
        }
        els.audioBtn.textContent = state.audioEnabled ? "🔊 소리 켜짐" : "🔈 소리 꺼짐";
        els.audioBtn.setAttribute("aria-pressed", state.audioEnabled ? "true" : "false");
        root.classList.toggle("ppb-audio-off", !state.audioEnabled);
    }

    function setAudioEnabled(enabled, persist) {
        state.audioEnabled = Boolean(enabled);
        updateAudioButton();
        if (persist !== false) {
            writeLocalStorage(buildScopedStorageKey("audio-enabled"), state.audioEnabled ? "1" : "0");
        }
    }

    function pickCompliment(mode, celebration) {
        const config = MODE_CONFIG[mode] || MODE_CONFIG.stars;
        if (celebration === "finale") {
            return "마지막 공개까지 멋지게 이어졌어요. 오늘 무대의 피날레를 크게 축하합니다.";
        }
        const pool = config.compliments || MODE_CONFIG.stars.compliments;
        return pool[Math.floor(Math.random() * pool.length)] || MODE_CONFIG.stars.compliments[0];
    }

    function normalizePresentation(detail) {
        const raw = detail || {};
        const mode = MODE_CONFIG[raw.mode] ? raw.mode : state.activeMode;
        const celebration = raw.celebration === "finale" || raw.celebration === "final" ? "finale" : "reveal";
        const winnerName = String(raw.winnerName || raw.targetName || raw.title || raw.name || "-").trim() || "-";
        const badge = String(raw.badge || MODE_CONFIG[mode]?.badge || MODE_CONFIG.stars.badge);
        const compliment = String(raw.compliment || pickCompliment(mode, celebration));
        const sourceLabel = String(raw.sourceLabel || `${MODE_CONFIG[mode]?.label || "교실 쇼"} 결과`);
        const label = String(raw.label || "방금 공개된 결과");
        const meta = String(raw.meta || (celebration === "finale"
            ? "오늘 무대의 마지막 장면이 환하게 마무리되었습니다."
            : "축하 연출이 끝나면 다음 진행을 바로 이어갈 수 있습니다."));
        const nextLabel = String(raw.nextLabel || "다음 진행");
        return {
            badge,
            celebration,
            compliment,
            fortuneTarget: raw.fortuneTarget || null,
            label,
            meta,
            mode,
            nextLabel,
            sourceLabel,
            winnerName,
        };
    }

    function buildSuspenseCopy(payload) {
        const isRoleMode = payload.mode === "roles";
        return {
            name: isRoleMode ? "담당 학생 공개 준비 중" : "이름 공개 준비 중",
            compliment: isRoleMode
                ? "카드가 완전히 펼쳐질 때까지 담당 학생 이름은 숨겨 둡니다."
                : "이름은 아직 숨겨 두고, 축하 연출이 시작되는 순간 크게 보여 줍니다.",
            meta: payload.celebration === "finale"
                ? "마지막 발표를 위한 긴장감을 모으고 있습니다."
                : "지금은 결과 이름이 먼저 보이지 않도록 무대를 가리고 있습니다.",
        };
    }

    function clearPresentationTimers() {
        state.openTimers.forEach((timerId) => window.clearTimeout(timerId));
        state.openTimers = [];
    }

    function setPresentationClass(stage, celebration) {
        if (!els.resultPanel) {
            return;
        }
        els.resultPanel.classList.remove("is-arming", "is-suspense", "is-celebrating", "is-finale");
        if (stage) {
            els.resultPanel.classList.add(stage);
        }
        if (celebration === "finale") {
            els.resultPanel.classList.add("is-finale");
        }
    }

    function syncFullscreenState() {
        root.classList.toggle("ppb-is-fullscreen", Boolean(document.fullscreenElement));
    }

    function syncShowBanner(mode) {
        const config = MODE_CONFIG[mode] || MODE_CONFIG.stars;
        if (els.stageTitle) {
            els.stageTitle.textContent = config.label;
        }
        if (els.stageDesc) {
            els.stageDesc.textContent = config.desc;
        }
    }

    function setMode(mode, options) {
        const nextMode = MODE_CONFIG[mode] ? mode : "stars";
        const silent = Boolean(options && options.silent);
        state.activeMode = nextMode;
        Object.entries(MODE_CONFIG).forEach(([name, config]) => {
            const button = document.getElementById(config.buttonId);
            const view = document.getElementById(config.viewId);
            const active = name === nextMode;
            if (button) {
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", active ? "true" : "false");
            }
            if (view) {
                view.classList.toggle("is-hidden", !active);
            }
        });
        root.dataset.activeMode = nextMode;
        syncShowBanner(nextMode);
        if (!silent) {
            playSound("tab");
            window.setTimeout(() => playSound("mode"), 80);
            root.dispatchEvent(new CustomEvent("ppobgi:mode-change", { detail: { mode: nextMode } }));
        }
    }

    function setActionAvailability(ready, payload) {
        state.nextReady = Boolean(ready);
        if (els.resultNextBtn) {
            els.resultNextBtn.disabled = !state.nextReady;
            els.resultNextBtn.textContent = payload?.nextLabel || "다음 진행";
        }
        if (els.resultFortuneBtn) {
            const enableFortune = state.nextReady && Boolean(payload?.fortuneTarget);
            els.resultFortuneBtn.hidden = !payload?.fortuneTarget;
            els.resultFortuneBtn.disabled = !enableFortune;
        }
        if (els.resultWait) {
            els.resultWait.hidden = state.nextReady;
        }
    }

    function openPresentation(detail) {
        if (!els.resultModal || !els.resultName || !els.resultMeta || !els.resultPanel) {
            return;
        }
        clearPresentationTimers();
        const payload = normalizePresentation(detail);
        const suspenseCopy = buildSuspenseCopy(payload);
        state.presentationDetail = payload;
        state.presentationOpen = true;
        setActionAvailability(false, payload);

        if (els.resultPhase) {
            els.resultPhase.textContent = "무대 준비 중";
        }
        if (els.resultLabel) {
            els.resultLabel.textContent = payload.label;
        }
        if (els.resultSource) {
            els.resultSource.textContent = payload.sourceLabel;
        }
        if (els.resultBadge) {
            els.resultBadge.textContent = payload.badge;
        }
        if (els.resultName) {
            els.resultName.textContent = suspenseCopy.name;
        }
        if (els.resultCompliment) {
            els.resultCompliment.textContent = suspenseCopy.compliment;
        }
        if (els.resultMeta) {
            els.resultMeta.textContent = suspenseCopy.meta;
        }
        if (els.resultWait) {
            els.resultWait.hidden = false;
            els.resultWait.textContent = "축하 연출이 진행 중입니다.";
        }

        els.resultModal.classList.remove("is-hidden");
        els.resultModal.setAttribute("aria-hidden", "false");
        root.classList.add("ppb-result-open");
        setPresentationClass("is-arming", payload.celebration);
        playSound("arming");

        state.openTimers.push(window.setTimeout(() => {
            if (!state.presentationOpen) {
                return;
            }
            if (els.resultPhase) {
                els.resultPhase.textContent = "기대감 상승";
            }
            if (els.resultWait) {
                els.resultWait.textContent = "무대 긴장감을 모으고 있습니다.";
            }
            setPresentationClass("is-suspense", payload.celebration);
            playSound("suspense");
        }, 220));

        state.openTimers.push(window.setTimeout(() => {
            if (!state.presentationOpen) {
                return;
            }
            if (els.resultName) {
                els.resultName.textContent = payload.winnerName;
            }
            if (els.resultCompliment) {
                els.resultCompliment.textContent = payload.compliment;
            }
            if (els.resultMeta) {
                els.resultMeta.textContent = payload.meta;
            }
            if (els.resultPhase) {
                els.resultPhase.textContent = payload.celebration === "finale" ? "그랜드 피날레" : "축하합니다";
            }
            if (els.resultWait) {
                els.resultWait.textContent = payload.celebration === "finale"
                    ? "마지막 무대 환호가 이어지고 있습니다."
                    : "축하 무대가 이어지고 있습니다.";
            }
            setPresentationClass("is-celebrating", payload.celebration);
            playSound(payload.celebration === "finale" ? "finale" : "reveal");
            if (payload.celebration === "finale") {
                state.openTimers.push(window.setTimeout(() => playSound("applause"), 380));
            }
        }, 1180));

        state.openTimers.push(window.setTimeout(() => {
            if (!state.presentationOpen) {
                return;
            }
            if (els.resultPhase) {
                els.resultPhase.textContent = "다음 진행 준비 완료";
            }
            if (els.resultWait) {
                els.resultWait.textContent = "이제 다음 진행을 이어갈 수 있습니다.";
            }
            setActionAvailability(true, payload);
            els.resultNextBtn?.focus();
        }, 3360));
    }

    function closePresentation() {
        if (!state.presentationOpen || !els.resultModal) {
            return;
        }
        clearPresentationTimers();
        playSound("close");
        els.resultModal.classList.add("is-hidden");
        els.resultModal.setAttribute("aria-hidden", "true");
        root.classList.remove("ppb-result-open");
        setPresentationClass("", null);
        state.presentationOpen = false;
        state.nextReady = false;
        const detail = state.presentationDetail;
        state.presentationDetail = null;
        root.dispatchEvent(new CustomEvent("ppobgi:presentation-closed", { detail: { presentation: detail } }));
    }

    function handlePresentationKeydown(event) {
        if (!state.presentationOpen) {
            return;
        }
        const tagName = String(event.target?.tagName || "").toUpperCase();
        const typing = tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT" || Boolean(event.target?.isContentEditable);
        if (typing && event.key !== "Escape") {
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            closePresentation();
            return;
        }
        if (!state.nextReady) {
            return;
        }
        if (event.key === "Enter" || event.code === "Space") {
            event.preventDefault();
            closePresentation();
        }
    }

    function bindModeButtons() {
        Object.entries(MODE_CONFIG).forEach(([mode, config]) => {
            const button = document.getElementById(config.buttonId);
            button?.addEventListener("click", () => setMode(mode));
        });
    }

    function bindEvents() {
        bindModeButtons();
        root.addEventListener("ppobgi:mode-change-request", (event) => {
            setMode(event.detail?.mode || "stars");
        });
        root.addEventListener("ppobgi:present", (event) => {
            openPresentation(event.detail || {});
        });
        root.addEventListener("ppobgi:close-presentation", closePresentation);
        root.addEventListener("ppobgi:play-sfx", (event) => {
            playSound(event.detail?.cue || event.detail?.kind || "reveal");
        });
        els.audioBtn?.addEventListener("click", () => {
            unlockAudio();
            setAudioEnabled(!state.audioEnabled, true);
            if (state.audioEnabled) {
                playSound("mode");
            }
        });
        els.resultNextBtn?.addEventListener("click", () => {
            if (!state.nextReady) {
                return;
            }
            closePresentation();
        });
        els.resultFortuneBtn?.addEventListener("click", () => {
            if (!state.nextReady || !state.presentationDetail?.fortuneTarget) {
                return;
            }
            root.dispatchEvent(new CustomEvent("ppobgi:open-fortune", { detail: state.presentationDetail.fortuneTarget }));
        });
        els.resultModal?.addEventListener("click", (event) => {
            if (event.target === els.resultModal) {
                closePresentation();
            }
        });
        els.resultPanel?.addEventListener("click", (event) => event.stopPropagation());
        document.addEventListener("keydown", handlePresentationKeydown);
        document.addEventListener("pointerdown", unlockAudio, { passive: true });
        document.addEventListener("keydown", unlockAudio, { passive: true });
        document.addEventListener("fullscreenchange", syncFullscreenState);
    }

    function bootstrap() {
        const storedAudio = readLocalStorage(buildScopedStorageKey("audio-enabled"));
        if (storedAudio === "0") {
            state.audioEnabled = false;
        } else if (storedAudio === "1") {
            state.audioEnabled = true;
        }
        root.dataset.showProfile = showProfile;
        root.dataset.audioPack = `${audioPackName}@${audioPackVersion}`;
        root.classList.add(`ppb-show-profile-${showProfile}`);
        updateAudioButton();
        syncShowBanner("stars");
        syncFullscreenState();
        setMode("stars", { silent: true });
        bindEvents();
    }

    bootstrap();

    window.ppobgiShared = {
        assetManifest: {
            audioPackBase,
            audioPackName,
            audioPackVersion,
            files: AUDIO_FILES,
        },
        buildScopedStorageKey,
        closePresentation,
        getMode: () => state.activeMode,
        isPresentationOpen: () => state.presentationOpen,
        requestModeChange: (mode) => setMode(mode),
    };
})();
