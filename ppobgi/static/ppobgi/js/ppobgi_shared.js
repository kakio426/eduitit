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
            stageTitle: "별빛 뽑기",
            desc: "별 하나를 누르면 오늘의 주인공이 바로 공개됩니다.",
        },
        ladder: {
            buttonId: "ppb-mode-ladder-btn",
            viewId: "ppb-mode-ladder",
            label: "사다리 뽑기",
            stageTitle: "사다리 뽑기",
            desc: "출발점부터 끝점까지 따라가며 결과를 선명하게 공개합니다.",
        },
        sequence: {
            buttonId: "ppb-mode-sequence-btn",
            viewId: "ppb-mode-sequence",
            label: "순서 뽑기",
            stageTitle: "순서 뽑기",
            desc: "몇 번째 차례인지와 학생 이름을 함께 보여 줍니다.",
        },
        teams: {
            buttonId: "ppb-mode-teams-btn",
            viewId: "ppb-mode-teams",
            label: "팀 나누기",
            stageTitle: "팀 나누기",
            desc: "어느 팀에 배치됐는지부터 크게 보여 주는 팀 발표 화면입니다.",
        },
        meteor: {
            buttonId: "ppb-mode-meteor-btn",
            viewId: "ppb-mode-meteor",
            label: "유성우 뽑기",
            stageTitle: "유성우 뽑기",
            desc: "유성이 떨어지듯 결과가 내려와 교실 시선을 한 번에 모읍니다.",
        },
        roles: {
            buttonId: "ppb-mode-roles-btn",
            viewId: "ppb-mode-roles",
            label: "역할 카드",
            stageTitle: "역할 카드",
            desc: "무슨 역할인지와 누가 맡는지 한 번에 읽히는 역할 발표 화면입니다.",
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
            // Ignore storage failures in kiosk/private mode.
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
            // Ignore audio failures so the stage keeps moving.
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

    function syncShowBanner(mode) {
        const config = MODE_CONFIG[mode] || MODE_CONFIG.stars;
        if (els.stageTitle) {
            els.stageTitle.textContent = config.stageTitle || config.label;
        }
        if (els.stageDesc) {
            els.stageDesc.hidden = false;
            els.stageDesc.textContent = config.desc || "";
        }
    }

    function syncFullscreenState() {
        root.classList.toggle("ppb-is-fullscreen", Boolean(document.fullscreenElement));
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
        root.addEventListener("ppobgi:play-sfx", (event) => {
            playSound(event.detail?.cue || event.detail?.kind || "reveal");
        });
        root.addEventListener("ppobgi:close-tools", () => {
            const toolsMenu = document.getElementById("ppb-tools-menu");
            if (toolsMenu?.open) {
                toolsMenu.open = false;
            }
        });
        els.audioBtn?.addEventListener("click", () => {
            unlockAudio();
            setAudioEnabled(!state.audioEnabled, true);
            if (state.audioEnabled) {
                playSound("mode");
            }
            root.dispatchEvent(new CustomEvent("ppobgi:close-tools"));
        });
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
        syncFullscreenState();
        syncShowBanner("stars");
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
        closePresentation: () => {},
        getMode: () => state.activeMode,
        isPresentationOpen: () => false,
        requestModeChange: (mode) => setMode(mode),
    };
})();
