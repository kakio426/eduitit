"use strict";

(function () {
    const root = document.getElementById("rg-app");
    if (!root) {
        return;
    }

    const STORAGE_KEY = "reflex_game_leaderboard_v1";

    const els = {
        menu: document.getElementById("rg-menu"),
        single: document.getElementById("rg-single"),
        battle: document.getElementById("rg-battle"),
        openSingleBtn: document.getElementById("rg-open-single"),
        openBattleBtn: document.getElementById("rg-open-battle"),
        leaderboard: document.getElementById("rg-leaderboard"),
        fullscreenBtn: document.getElementById("rg-fullscreen-btn"),
        singleBackBtn: document.getElementById("rg-single-back"),
        singleStage: document.getElementById("rg-single-stage"),
        singleMain: document.getElementById("rg-single-main"),
        singleSub: document.getElementById("rg-single-sub"),
        singleStartBtn: document.getElementById("rg-single-start"),
        singleRetryBtn: document.getElementById("rg-single-retry"),
        battleBackBtn: document.getElementById("rg-battle-back"),
        battleStartBtn: document.getElementById("rg-battle-start"),
        battleRestartBtn: document.getElementById("rg-battle-restart"),
        battleStatus: document.getElementById("rg-battle-status"),
        battleP1: document.getElementById("rg-battle-p1"),
        battleP2: document.getElementById("rg-battle-p2"),
        battleP1Result: document.getElementById("rg-battle-p1-result"),
        battleP2Result: document.getElementById("rg-battle-p2-result"),
    };

    const state = {
        mode: "menu",
        gameState: "idle",
        timeoutId: null,
        startTime: 0,
        singleResult: null,
        singleResultType: null,
        battleResults: {
            p1: null,
            p2: null,
            winner: null,
            foulPlayer: null,
        },
        leaderboard: loadLeaderboard(),
    };

    function loadLeaderboard() {
        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return [];
            }
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed
                .filter((item) => item && typeof item.name === "string" && Number.isFinite(item.time))
                .map((item) => ({
                    name: item.name.slice(0, 16),
                    time: Math.max(1, Math.round(Number(item.time))),
                }))
                .sort((a, b) => a.time - b.time)
                .slice(0, 5);
        } catch (error) {
            return [];
        }
    }

    function saveLeaderboard() {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.leaderboard));
        } catch (error) {
            // ignore storage errors
        }
    }

    function updateLeaderboard(ms) {
        const rawName = window.prompt("이름을 입력하면 TOP 5에 저장됩니다.", "");
        const name = (rawName || "").trim();
        if (!name) {
            return;
        }

        state.leaderboard = [...state.leaderboard, { name: name.slice(0, 16), time: ms }]
            .sort((a, b) => a.time - b.time)
            .slice(0, 5);

        saveLeaderboard();
        renderLeaderboard();
    }

    function clearReadyTimer() {
        if (state.timeoutId) {
            window.clearTimeout(state.timeoutId);
            state.timeoutId = null;
        }
    }

    function vibrate(ms) {
        if (navigator.vibrate) {
            navigator.vibrate(ms);
        }
    }

    function playerLabel(player) {
        return player === "p1" ? "왼쪽 플레이어" : "오른쪽 플레이어";
    }

    function setMode(mode) {
        clearReadyTimer();
        state.mode = mode;
        state.gameState = "idle";
        state.startTime = 0;
        state.singleResult = null;
        state.singleResultType = null;
        state.battleResults = {
            p1: null,
            p2: null,
            winner: null,
            foulPlayer: null,
        };
        render();
    }

    function startRound() {
        clearReadyTimer();
        state.gameState = "waiting";
        state.startTime = 0;
        state.singleResult = null;
        state.singleResultType = null;
        state.battleResults = {
            p1: null,
            p2: null,
            winner: null,
            foulPlayer: null,
        };
        render();

        const delay = Math.floor(Math.random() * 3000) + 2000;
        state.timeoutId = window.setTimeout(() => {
            state.timeoutId = null;
            state.gameState = "ready";
            state.startTime = window.performance.now();
            vibrate(45);
            render();
        }, delay);
    }

    function finishSingleFoul() {
        clearReadyTimer();
        state.gameState = "finished";
        state.singleResultType = "foul";
        state.singleResult = null;
        render();
        vibrate(120);
    }

    function finishSingleSuccess() {
        clearReadyTimer();
        const reaction = Math.max(1, Math.round(window.performance.now() - state.startTime));
        state.gameState = "finished";
        state.singleResultType = "time";
        state.singleResult = reaction;
        render();
        vibrate(70);
        updateLeaderboard(reaction);
    }

    function handleSingleTap() {
        if (state.mode !== "single") {
            return;
        }

        if (state.gameState === "waiting") {
            finishSingleFoul();
            return;
        }
        if (state.gameState === "ready") {
            finishSingleSuccess();
        }
    }

    function finishBattle(player, result) {
        clearReadyTimer();
        state.gameState = "finished";
        state.battleResults[player] = result;

        if (result === "foul") {
            state.battleResults.foulPlayer = player;
            state.battleResults.winner = player === "p1" ? "p2" : "p1";
            vibrate(120);
            return;
        }

        state.battleResults.winner = player;
        vibrate(70);
    }

    function handleBattleTap(player) {
        if (state.mode !== "battle") {
            return;
        }

        if (state.gameState === "waiting") {
            finishBattle(player, "foul");
            render();
            return;
        }

        if (state.gameState === "ready") {
            const reaction = Math.max(1, Math.round(window.performance.now() - state.startTime));
            finishBattle(player, reaction);
            render();
        }
    }

    function renderLeaderboard() {
        if (!els.leaderboard) {
            return;
        }

        if (!state.leaderboard.length) {
            const empty = document.createElement("li");
            empty.className = "rg-empty-rank";
            empty.textContent = "아직 기록이 없습니다. 첫 기록을 남겨보세요.";
            els.leaderboard.replaceChildren(empty);
            return;
        }

        const fragment = document.createDocumentFragment();
        state.leaderboard.forEach((item, index) => {
            const row = document.createElement("li");
            row.textContent = `${index + 1}. ${item.name} · ${item.time}ms`;
            fragment.appendChild(row);
        });
        els.leaderboard.replaceChildren(fragment);
    }

    function renderScreenVisibility() {
        const map = {
            menu: els.menu,
            single: els.single,
            battle: els.battle,
        };

        Object.entries(map).forEach(([key, node]) => {
            if (!node) {
                return;
            }
            const active = state.mode === key;
            node.classList.toggle("is-active", active);
            node.setAttribute("aria-hidden", active ? "false" : "true");
        });
    }

    function renderSingleStage() {
        if (!els.singleStage || !els.singleMain || !els.singleSub) {
            return;
        }

        const classList = ["rg-stage"];
        let main = "시작 버튼을 눌러 준비하세요";
        let sub = "신호 전에 누르면 반칙 처리됩니다.";
        let showStart = true;
        let showRetry = false;

        if (state.gameState === "waiting") {
            classList.push("rg-stage-waiting");
            main = "기다리세요...";
            sub = "신호 전에 누르면 바로 반칙입니다.";
            showStart = false;
        } else if (state.gameState === "ready") {
            classList.push("rg-stage-ready");
            main = "TAP!";
            sub = "지금 바로 화면을 터치하세요.";
            showStart = false;
        } else if (state.gameState === "finished") {
            showStart = false;
            showRetry = true;
            if (state.singleResultType === "foul") {
                classList.push("rg-stage-foul");
                main = "반칙!";
                sub = "탭 사인 전에 눌렀습니다.";
            } else {
                classList.push("rg-stage-finished");
                main = `${state.singleResult}ms`;
                sub = "다시 시작해서 기록을 갱신해 보세요.";
            }
        } else {
            classList.push("rg-stage-idle");
        }

        els.singleStage.className = classList.join(" ");
        els.singleMain.textContent = main;
        els.singleSub.textContent = sub;
        els.singleStartBtn.classList.toggle("is-hidden", !showStart);
        els.singleRetryBtn.classList.toggle("is-hidden", !showRetry);
    }

    function setBattleSideState() {
        const p1 = els.battleP1;
        const p2 = els.battleP2;
        if (!p1 || !p2) {
            return;
        }

        [p1, p2].forEach((node) => {
            node.classList.remove("is-ready", "is-winner", "is-foul", "is-muted");
        });

        if (state.gameState === "ready") {
            p1.classList.add("is-ready");
            p2.classList.add("is-ready");
            return;
        }

        if (state.gameState !== "finished") {
            return;
        }

        const foulPlayer = state.battleResults.foulPlayer;
        const winner = state.battleResults.winner;

        if (foulPlayer) {
            const foulNode = foulPlayer === "p1" ? p1 : p2;
            const winnerNode = winner === "p1" ? p1 : p2;
            foulNode.classList.add("is-foul");
            winnerNode.classList.add("is-winner");
            return;
        }

        const winnerNode = winner === "p1" ? p1 : p2;
        const loserNode = winner === "p1" ? p2 : p1;
        winnerNode.classList.add("is-winner");
        loserNode.classList.add("is-muted");
    }

    function renderBattleBoard() {
        if (!els.battleStatus || !els.battleP1Result || !els.battleP2Result) {
            return;
        }

        const p1Result = state.battleResults.p1;
        const p2Result = state.battleResults.p2;

        els.battleP1Result.textContent = p1Result === null ? "대기" : p1Result === "foul" ? "반칙" : `${p1Result}ms`;
        els.battleP2Result.textContent = p2Result === null ? "대기" : p2Result === "foul" ? "반칙" : `${p2Result}ms`;

        if (state.gameState === "idle") {
            els.battleStatus.textContent = "시작 버튼을 누르세요.";
            els.battleRestartBtn.classList.add("is-hidden");
        } else if (state.gameState === "waiting") {
            els.battleStatus.textContent = "준비... 신호 전에 누르면 반칙입니다.";
            els.battleRestartBtn.classList.add("is-hidden");
        } else if (state.gameState === "ready") {
            els.battleStatus.textContent = "TAP!";
            els.battleRestartBtn.classList.add("is-hidden");
        } else {
            const foulPlayer = state.battleResults.foulPlayer;
            if (foulPlayer) {
                const winner = state.battleResults.winner;
                els.battleStatus.textContent = `${playerLabel(foulPlayer)} 반칙! ${playerLabel(winner)} 승리`;
            } else {
                const winner = state.battleResults.winner;
                const time = winner ? state.battleResults[winner] : null;
                els.battleStatus.textContent = `${playerLabel(winner)} 승리 (${time}ms)`;
            }
            els.battleRestartBtn.classList.remove("is-hidden");
        }

        setBattleSideState();
    }

    function isFullscreenSupported() {
        return Boolean(document.documentElement.requestFullscreen);
    }

    function updateFullscreenButtonText() {
        if (!els.fullscreenBtn) {
            return;
        }

        if (!isFullscreenSupported()) {
            els.fullscreenBtn.disabled = true;
            els.fullscreenBtn.textContent = "전체화면 미지원";
            return;
        }

        els.fullscreenBtn.textContent = document.fullscreenElement ? "전체화면 해제" : "전체화면";
    }

    async function toggleFullscreen() {
        if (!isFullscreenSupported()) {
            window.alert("현재 브라우저에서는 전체화면을 지원하지 않습니다.");
            return;
        }

        try {
            if (document.fullscreenElement) {
                await document.exitFullscreen();
            } else {
                await document.documentElement.requestFullscreen();
            }
        } catch (error) {
            window.alert("전체화면 전환에 실패했습니다.");
        }
    }

    function render() {
        renderScreenVisibility();
        renderLeaderboard();
        if (state.mode === "single") {
            renderSingleStage();
        }
        if (state.mode === "battle") {
            renderBattleBoard();
        }
    }

    function bindEvents() {
        els.openSingleBtn?.addEventListener("click", () => setMode("single"));
        els.openBattleBtn?.addEventListener("click", () => setMode("battle"));
        els.singleBackBtn?.addEventListener("click", () => setMode("menu"));
        els.battleBackBtn?.addEventListener("click", () => setMode("menu"));

        els.singleStartBtn?.addEventListener("click", (event) => {
            event.stopPropagation();
            startRound();
        });
        els.singleRetryBtn?.addEventListener("click", (event) => {
            event.stopPropagation();
            startRound();
        });
        els.singleStage?.addEventListener("click", handleSingleTap);
        els.singleStage?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                handleSingleTap();
            }
        });

        els.battleStartBtn?.addEventListener("click", startRound);
        els.battleRestartBtn?.addEventListener("click", startRound);
        els.battleP1?.addEventListener("click", () => handleBattleTap("p1"));
        els.battleP2?.addEventListener("click", () => handleBattleTap("p2"));

        els.fullscreenBtn?.addEventListener("click", toggleFullscreen);
        document.addEventListener("fullscreenchange", updateFullscreenButtonText);
    }

    bindEvents();
    updateFullscreenButtonText();
    render();
})();

