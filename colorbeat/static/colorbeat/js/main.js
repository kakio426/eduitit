"use strict";

(function () {
    const root = document.getElementById("cb-app");
    if (!root) {
        return;
    }

    const STORAGE_KEY = root.dataset.storageKey || "colorbeat_pattern_v1";
    const TRACKS = [
        { key: "kick", label: "쿵", name: "큰북", hue: "red" },
        { key: "snare", label: "짝", name: "작은북", hue: "orange" },
        { key: "hat", label: "치", name: "심벌", hue: "yellow" },
        { key: "bell", label: "딩", name: "벨", hue: "cyan" },
    ];
    const STEPS = 8;
    const DEFAULT_PATTERN = [
        [1, 0, 0, 0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0, 0, 1, 0],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 1, 0, 0, 0, 1],
    ];

    const els = {
        grid: document.getElementById("cb-grid"),
        play: document.getElementById("cb-play"),
        random: document.getElementById("cb-random"),
        clear: document.getElementById("cb-clear"),
        fullscreen: document.getElementById("cb-fullscreen"),
        status: document.getElementById("cb-status"),
        tempo: document.getElementById("cb-tempo"),
        tempoValue: document.getElementById("cb-tempo-value"),
        kitButtons: Array.from(document.querySelectorAll("[data-kit]")),
        codeToggle: document.getElementById("cb-code-toggle"),
        code: document.getElementById("cb-code"),
    };

    const state = {
        pattern: loadPattern(),
        tempo: Number(els.tempo ? els.tempo.value : 110),
        kit: "drum",
        playing: false,
        playhead: -1,
        scheduledId: null,
        audioReady: false,
        instruments: null,
    };

    function clonePattern(pattern) {
        return pattern.map((row) => row.slice());
    }

    function loadPattern() {
        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return clonePattern(DEFAULT_PATTERN);
            }
            const parsed = JSON.parse(raw);
            if (!isValidPattern(parsed)) {
                return clonePattern(DEFAULT_PATTERN);
            }
            return parsed.map((row) => row.map((cell) => (cell ? 1 : 0)));
        } catch (error) {
            return clonePattern(DEFAULT_PATTERN);
        }
    }

    function isValidPattern(pattern) {
        return Array.isArray(pattern)
            && pattern.length === TRACKS.length
            && pattern.every((row) => (
                Array.isArray(row)
                && row.length === STEPS
                && row.every((cell) => cell === 0 || cell === 1 || cell === true || cell === false)
            ));
    }

    function savePattern() {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.pattern));
            setStatus(state.playing ? "재생 중" : "저장됨");
        } catch (error) {
            setStatus("저장 실패");
        }
    }

    function setStatus(text) {
        if (els.status) {
            els.status.textContent = text;
        }
    }

    function getTransport() {
        if (!window.Tone) {
            return null;
        }
        return typeof Tone.getTransport === "function" ? Tone.getTransport() : Tone.Transport;
    }

    function setNodeVolume(node, volume) {
        if (node && node.volume && typeof node.volume.value === "number") {
            node.volume.value = volume;
        }
        return node;
    }

    function createHatSynth(noiseType, decay, release, volume, channel) {
        const synth = new Tone.NoiseSynth({
            noise: { type: noiseType },
            envelope: {
                attack: 0.001,
                decay,
                sustain: 0,
                release,
            },
        }).connect(channel);
        return setNodeVolume(synth, volume);
    }

    function buildInstruments(kit) {
        disposeInstruments();
        const limiter = new Tone.Limiter(-1).toDestination();
        const channel = new Tone.Channel({ volume: -6 }).connect(limiter);

        if (kit === "sparkle") {
            state.instruments = {
                output: channel,
                limiter,
                kick: new Tone.MembraneSynth({ pitchDecay: 0.03, octaves: 3, envelope: { attack: 0.001, decay: 0.28, sustain: 0.02, release: 0.2 } }).connect(channel),
                snare: new Tone.MetalSynth({ frequency: 240, envelope: { attack: 0.001, decay: 0.18, release: 0.08 }, harmonicity: 4.2, modulationIndex: 14, resonance: 1200, octaves: 1.2 }).connect(channel),
                hat: createHatSynth("white", 0.07, 0.025, -5, channel),
                bell: new Tone.Synth({ oscillator: { type: "triangle" }, envelope: { attack: 0.003, decay: 0.22, sustain: 0.08, release: 0.22 } }).connect(channel),
            };
            return;
        }

        if (kit === "space") {
            state.instruments = {
                output: channel,
                limiter,
                kick: new Tone.MembraneSynth({ pitchDecay: 0.08, octaves: 6, envelope: { attack: 0.001, decay: 0.45, sustain: 0.01, release: 0.35 } }).connect(channel),
                snare: new Tone.NoiseSynth({ noise: { type: "pink" }, envelope: { attack: 0.002, decay: 0.18, sustain: 0.03, release: 0.16 } }).connect(channel),
                hat: createHatSynth("pink", 0.1, 0.04, -4, channel),
                bell: new Tone.FMSynth({ harmonicity: 1.5, modulationIndex: 12, envelope: { attack: 0.01, decay: 0.18, sustain: 0.06, release: 0.25 } }).connect(channel),
            };
            return;
        }

        state.instruments = {
            output: channel,
            limiter,
            kick: new Tone.MembraneSynth({ pitchDecay: 0.04, octaves: 4, envelope: { attack: 0.001, decay: 0.35, sustain: 0.01, release: 0.18 } }).connect(channel),
            snare: new Tone.NoiseSynth({ noise: { type: "white" }, envelope: { attack: 0.001, decay: 0.14, sustain: 0.02, release: 0.12 } }).connect(channel),
            hat: createHatSynth("white", 0.055, 0.018, -4, channel),
            bell: new Tone.Synth({ oscillator: { type: "sine" }, envelope: { attack: 0.002, decay: 0.16, sustain: 0.06, release: 0.18 } }).connect(channel),
        };
    }

    function disposeInstruments() {
        if (!state.instruments) {
            return;
        }
        Object.values(state.instruments).forEach((node) => {
            if (node && typeof node.dispose === "function") {
                node.dispose();
            }
        });
        state.instruments = null;
    }

    async function ensureAudio() {
        if (!window.Tone) {
            setStatus("소리 실패");
            return false;
        }
        try {
            await Tone.start();
            if (!state.audioReady || !state.instruments) {
                buildInstruments(state.kit);
            }
            state.audioReady = true;
            return true;
        } catch (error) {
            setStatus("소리 실패");
            return false;
        }
    }

    function playTrack(trackKey, time) {
        if (!state.instruments || !state.instruments[trackKey]) {
            return;
        }
        const instrument = state.instruments[trackKey];
        if (trackKey === "kick") {
            instrument.triggerAttackRelease(state.kit === "space" ? "A1" : "C2", "8n", time, 0.9);
        } else if (trackKey === "snare") {
            instrument.triggerAttackRelease("16n", time, 0.62);
        } else if (trackKey === "hat") {
            instrument.triggerAttackRelease("32n", time, 0.82);
        } else {
            const note = state.kit === "space" ? "G4" : state.kit === "sparkle" ? "E5" : "C5";
            instrument.triggerAttackRelease(note, "16n", time, 0.72);
        }
    }

    function scheduleLoop() {
        const transport = getTransport();
        if (!transport) {
            return false;
        }
        if (state.scheduledId !== null && typeof transport.clear === "function") {
            transport.clear(state.scheduledId);
        }
        if (typeof transport.cancel === "function") {
            transport.cancel(0);
        }
        transport.bpm.value = state.tempo;
        let step = 0;
        state.scheduledId = transport.scheduleRepeat((time) => {
            const currentStep = step % STEPS;
            scheduleDraw(() => {
                state.playhead = currentStep;
                renderPlayhead();
            }, time);
            TRACKS.forEach((track, rowIndex) => {
                if (state.pattern[rowIndex][currentStep]) {
                    playTrack(track.key, time);
                }
            });
            step = (step + 1) % STEPS;
        }, "8n");
        return true;
    }

    function scheduleDraw(callback, time) {
        if (window.Tone && Tone.Draw && typeof Tone.Draw.schedule === "function") {
            Tone.Draw.schedule(callback, time);
            return;
        }
        window.setTimeout(callback, 0);
    }

    async function togglePlay() {
        if (state.playing) {
            stopPlayback();
            return;
        }
        const ready = await ensureAudio();
        if (!ready || !scheduleLoop()) {
            setStatus("재생 실패");
            return;
        }
        const transport = getTransport();
        state.playing = true;
        state.playhead = -1;
        updatePlayButton();
        setStatus("재생 중");
        if (transport) {
            transport.start("+0.05");
        }
    }

    function stopPlayback() {
        const transport = getTransport();
        if (transport) {
            transport.stop();
            if (state.scheduledId !== null && typeof transport.clear === "function") {
                transport.clear(state.scheduledId);
            }
            if (typeof transport.cancel === "function") {
                transport.cancel(0);
            }
        }
        state.scheduledId = null;
        state.playing = false;
        state.playhead = -1;
        updatePlayButton();
        renderPlayhead();
        setStatus("멈춤");
    }

    function updatePlayButton() {
        if (!els.play) {
            return;
        }
        els.play.textContent = state.playing ? "멈춤" : "재생";
        els.play.classList.toggle("is-playing", state.playing);
        els.play.setAttribute("aria-pressed", state.playing ? "true" : "false");
    }

    function renderGrid() {
        if (!els.grid) {
            return;
        }
        els.grid.innerHTML = "";
        TRACKS.forEach((track, rowIndex) => {
            const label = document.createElement("div");
            label.className = `cb-track cb-track-${track.hue}`;
            label.textContent = track.label;
            label.setAttribute("aria-label", track.name);
            els.grid.appendChild(label);

            for (let step = 0; step < STEPS; step += 1) {
                const cell = document.createElement("button");
                cell.type = "button";
                cell.className = `cb-cell cb-cell-${track.hue}`;
                cell.dataset.row = String(rowIndex);
                cell.dataset.step = String(step);
                cell.setAttribute("role", "gridcell");
                cell.setAttribute("aria-label", `${track.name} ${step + 1}박`);
                cell.addEventListener("click", () => toggleCell(rowIndex, step));
                els.grid.appendChild(cell);
            }
        });
        renderCells();
    }

    function renderCells() {
        if (!els.grid) {
            return;
        }
        els.grid.querySelectorAll(".cb-cell").forEach((cell) => {
            const row = Number(cell.dataset.row);
            const step = Number(cell.dataset.step);
            const isOn = Boolean(state.pattern[row][step]);
            cell.classList.toggle("is-on", isOn);
            cell.setAttribute("aria-selected", isOn ? "true" : "false");
        });
        renderPlayhead();
        renderCode();
    }

    function renderPlayhead() {
        if (!els.grid) {
            return;
        }
        els.grid.querySelectorAll(".cb-cell, .cb-track").forEach((node) => {
            node.classList.remove("is-current");
        });
        if (state.playhead < 0) {
            return;
        }
        els.grid.querySelectorAll(`[data-step="${state.playhead}"]`).forEach((cell) => {
            cell.classList.add("is-current");
        });
    }

    function renderCode() {
        if (els.code) {
            els.code.textContent = JSON.stringify(state.pattern);
        }
    }

    function toggleCell(row, step) {
        state.pattern[row][step] = state.pattern[row][step] ? 0 : 1;
        renderCells();
        savePattern();
    }

    function randomizePattern() {
        const chances = [0.32, 0.24, 0.58, 0.22];
        state.pattern = state.pattern.map((row, rowIndex) => (
            row.map((_, step) => {
                if (rowIndex === 0 && step % 4 === 0) {
                    return 1;
                }
                return Math.random() < chances[rowIndex] ? 1 : 0;
            })
        ));
        renderCells();
        savePattern();
    }

    function clearPattern() {
        state.pattern = TRACKS.map(() => Array(STEPS).fill(0));
        renderCells();
        savePattern();
    }

    function setKit(kit) {
        if (state.kit === kit) {
            return;
        }
        state.kit = kit;
        els.kitButtons.forEach((button) => {
            const isActive = button.dataset.kit === kit;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
        if (state.audioReady) {
            buildInstruments(kit);
        }
        setStatus(kit === "drum" ? "드럼" : kit === "sparkle" ? "반짝" : "우주");
    }

    function updateTempo() {
        state.tempo = Number(els.tempo.value);
        if (els.tempoValue) {
            els.tempoValue.textContent = String(state.tempo);
        }
        const transport = getTransport();
        if (transport && transport.bpm) {
            transport.bpm.value = state.tempo;
        }
    }

    async function toggleFullscreen() {
        try {
            if (document.fullscreenElement) {
                await document.exitFullscreen();
                setStatus(state.playing ? "재생 중" : "준비");
            } else if (root.requestFullscreen) {
                await root.requestFullscreen();
                setStatus("전체");
            }
        } catch (error) {
            setStatus("전체 실패");
        }
    }

    function toggleCode() {
        if (!els.code || !els.codeToggle) {
            return;
        }
        const nextHidden = !els.code.hidden;
        els.code.hidden = nextHidden;
        els.codeToggle.classList.toggle("is-active", !nextHidden);
        els.codeToggle.setAttribute("aria-expanded", nextHidden ? "false" : "true");
    }

    function bindEvents() {
        if (els.play) {
            els.play.addEventListener("click", togglePlay);
        }
        if (els.random) {
            els.random.addEventListener("click", randomizePattern);
        }
        if (els.clear) {
            els.clear.addEventListener("click", clearPattern);
        }
        if (els.fullscreen) {
            els.fullscreen.addEventListener("click", toggleFullscreen);
        }
        if (els.tempo) {
            els.tempo.addEventListener("input", updateTempo);
        }
        els.kitButtons.forEach((button) => {
            button.setAttribute("aria-pressed", button.classList.contains("is-active") ? "true" : "false");
            button.addEventListener("click", () => setKit(button.dataset.kit));
        });
        if (els.codeToggle) {
            els.codeToggle.setAttribute("aria-expanded", "false");
            els.codeToggle.addEventListener("click", toggleCode);
        }
        window.addEventListener("pagehide", stopPlayback);
    }

    renderGrid();
    updateTempo();
    updatePlayButton();
    bindEvents();
}());
