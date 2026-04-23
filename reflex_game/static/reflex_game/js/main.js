"use strict";

(function () {
    const root = document.getElementById("rg-app");
    if (!root) {
        return;
    }

    const STORAGE_KEY = "reflex_game_leaderboard_v1";

    function emptyBattleResults() {
        return {
            p1: null,
            p2: null,
            winner: null,
            foulPlayer: null,
        };
    }

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
        singleHud: document.getElementById("rg-single-hud"),
        singleHint: document.getElementById("rg-single-hint"),
        singleBadge: document.getElementById("rg-single-badge"),
        singleMain: document.getElementById("rg-single-main"),
        singleSub: document.getElementById("rg-single-sub"),
        singleStartBtn: document.getElementById("rg-single-start"),
        singleRetryBtn: document.getElementById("rg-single-retry"),
        singleSaveForm: document.getElementById("rg-single-save-form"),
        singleNameInput: document.getElementById("rg-single-name"),
        singleSaveBtn: document.getElementById("rg-single-save"),
        singleSaveStatus: document.getElementById("rg-single-save-status"),
        battleBackBtn: document.getElementById("rg-battle-back"),
        battleHud: document.getElementById("rg-battle-hud"),
        battleStartBtn: document.getElementById("rg-battle-start"),
        battleRestartBtn: document.getElementById("rg-battle-restart"),
        battleCenter: document.getElementById("rg-battle-center"),
        battleStatus: document.getElementById("rg-battle-status"),
        battleSub: document.getElementById("rg-battle-sub"),
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
        singleSaveVisible: false,
        singleSaveEligible: false,
        singleSaveSubmitted: false,
        singleSaveMessage: "",
        battleResults: emptyBattleResults(),
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

    function addLeaderboardEntry(name, ms) {
        state.leaderboard = [...state.leaderboard, { name: name.slice(0, 16), time: ms }]
            .sort((a, b) => a.time - b.time)
            .slice(0, 5);
        saveLeaderboard();
        renderLeaderboard();
    }

    function qualifiesForLeaderboard(ms) {
        if (state.leaderboard.length < 5) {
            return true;
        }
        return ms < state.leaderboard[state.leaderboard.length - 1].time;
    }

    function clearReadyTimer() {
        if (state.timeoutId) {
            window.clearTimeout(state.timeoutId);
            state.timeoutId = null;
        }
    }

    function resetSingleSaveState() {
        state.singleSaveVisible = false;
        state.singleSaveEligible = false;
        state.singleSaveSubmitted = false;
        state.singleSaveMessage = "";
        if (els.singleNameInput) {
            els.singleNameInput.value = "";
        }
    }

    function vibrate(ms) {
        if (navigator.vibrate) {
            navigator.vibrate(ms);
        }
    }

    function formatMs(ms) {
        return `${ms}ms`;
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
        resetSingleSaveState();
        state.battleResults = emptyBattleResults();
        render();
    }

    function startRound() {
        clearReadyTimer();
        state.gameState = "waiting";
        state.startTime = 0;
        state.singleResult = null;
        state.singleResultType = null;
        resetSingleSaveState();
        state.battleResults = emptyBattleResults();
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
        resetSingleSaveState();
        render();
        vibrate(120);
    }

    function finishSingleSuccess() {
        const reaction = Math.max(1, Math.round(window.performance.now() - state.startTime));
        clearReadyTimer();
        state.gameState = "finished";
        state.singleResultType = "time";
        state.singleResult = reaction;
        state.singleSaveVisible = true;
        state.singleSaveEligible = qualifiesForLeaderboard(reaction);
        state.singleSaveSubmitted = false;
        state.singleSaveMessage = state.singleSaveEligible
            ? "TOP 5 찬스! 이름을 남겨 보세요."
            : "이번엔 TOP 5 밖이에요. 바로 다시 도전!";
        render();
        vibrate(70);
        if (state.singleSaveEligible && els.singleNameInput) {
            window.setTimeout(() => {
                els.singleNameInput?.focus();
            }, 60);
        }
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
            row.className = "rg-rank-row";

            const rank = document.createElement("span");
            rank.className = "rg-rank-no";
            rank.textContent = `${index + 1}`;

            const name = document.createElement("span");
            name.className = "rg-rank-name";
            name.textContent = item.name;

            const time = document.createElement("strong");
            time.className = "rg-rank-time";
            time.textContent = formatMs(item.time);

            row.append(rank, name, time);
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

    function renderSingleSavePanel() {
        if (!els.singleSaveForm || !els.singleSaveBtn || !els.singleNameInput || !els.singleSaveStatus) {
            return;
        }

        els.singleSaveForm.classList.toggle("is-hidden", !state.singleSaveVisible);
        els.singleNameInput.disabled = !state.singleSaveEligible || state.singleSaveSubmitted;
        els.singleSaveBtn.disabled = !state.singleSaveEligible || state.singleSaveSubmitted;
        els.singleSaveBtn.textContent = state.singleSaveSubmitted ? "저장 완료" : "저장";
        els.singleSaveStatus.textContent = state.singleSaveMessage;
    }

    function renderSingleStage() {
        if (!els.singleStage || !els.singleHud || !els.singleHint || !els.singleBadge || !els.singleMain || !els.singleSub) {
            return;
        }

        const classList = ["rg-stage"];
        let badge = "READY";
        let main = "손은 멈춤!";
        let sub = "신호 전에 누르면 반칙 처리됩니다.";
        let hint = "초록 불만 기다리면 돼요.";
        let showStart = true;
        let showRetry = false;
        let tone = "idle";

        if (state.gameState === "waiting") {
            classList.push("rg-stage-waiting");
            badge = "WAIT";
            main = "멈춰!";
            sub = "초록 불 전에는 절대 누르지 마세요.";
            hint = "빨강 불! 아직 아니에요.";
            showStart = false;
        } else if (state.gameState === "ready") {
            classList.push("rg-stage-ready");
            badge = "GO!";
            main = "지금 TAP!";
            sub = "초록 불! 가장 빠르게 눌러요.";
            hint = "초록 불! 바로 탭!";
            showStart = false;
            tone = "win";
        } else if (state.gameState === "finished") {
            showStart = false;
            showRetry = true;
            if (state.singleResultType === "foul") {
                classList.push("rg-stage-foul");
                badge = "FOUL";
                main = "반칙!";
                sub = "초록 불 전에 눌렀어요.";
                hint = "반칙! 잠깐 멈추고 다시 도전.";
                tone = "foul";
            } else {
                classList.push("rg-stage-finished");
                badge = state.singleResult !== null && state.singleResult <= 250 ? "WOW" : "CLEAR";
                main = formatMs(state.singleResult);
                sub = state.singleSaveEligible
                    ? "TOP 5에 이름을 남길 수 있어요!"
                    : "좋았어요! 조금만 더 빨라지면 TOP 5!";
                hint = state.singleSaveEligible
                    ? "이름을 저장하면 명예의 전당에 올라가요."
                    : "한 번 더 하면 더 빨라질 수 있어요.";
                tone = "win";
            }
        } else {
            classList.push("rg-stage-idle");
            sub = "시작을 누르면 랜덤 신호가 뜹니다.";
        }

        els.singleStage.className = classList.join(" ");
        els.singleHud.dataset.state = state.gameState;
        els.singleHud.dataset.tone = tone;
        els.singleBadge.textContent = badge;
        els.singleMain.textContent = main;
        els.singleSub.textContent = sub;
        els.singleHint.textContent = hint;
        els.singleStartBtn.classList.toggle("is-hidden", !showStart);
        els.singleRetryBtn.classList.toggle("is-hidden", !showRetry);
        renderSingleSavePanel();
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
        if (foulPlayer && winner) {
            const foulNode = foulPlayer === "p1" ? p1 : p2;
            const winnerNode = winner === "p1" ? p1 : p2;
            foulNode.classList.add("is-foul");
            winnerNode.classList.add("is-winner");
            return;
        }

        if (winner) {
            const winnerNode = winner === "p1" ? p1 : p2;
            const loserNode = winner === "p1" ? p2 : p1;
            winnerNode.classList.add("is-winner");
            loserNode.classList.add("is-muted");
        }
    }

    function renderBattleBoard() {
        if (
            !els.battleStatus ||
            !els.battleSub ||
            !els.battleStartBtn ||
            !els.battleRestartBtn ||
            !els.battleHud ||
            !els.battleCenter ||
            !els.battleP1Result ||
            !els.battleP2Result
        ) {
            return;
        }

        const p1Result = state.battleResults.p1;
        const p2Result = state.battleResults.p2;
        let tone = "idle";

        els.battleP1Result.textContent = p1Result === null ? "대기" : p1Result === "foul" ? "반칙" : formatMs(p1Result);
        els.battleP2Result.textContent = p2Result === null ? "대기" : p2Result === "foul" ? "반칙" : formatMs(p2Result);

        if (state.gameState === "idle") {
            els.battleStatus.textContent = "친구와 동시에 준비!";
            els.battleSub.textContent = "가운데 버튼으로 시작하세요.";
            els.battleStartBtn.classList.remove("is-hidden");
            els.battleRestartBtn.classList.add("is-hidden");
        } else if (state.gameState === "waiting") {
            els.battleStatus.textContent = "멈춰! 아직 아니에요.";
            els.battleSub.textContent = "초록 불 전 터치 = 바로 패배";
            els.battleStartBtn.classList.add("is-hidden");
            els.battleRestartBtn.classList.add("is-hidden");
            tone = "waiting";
        } else if (state.gameState === "ready") {
            els.battleStatus.textContent = "지금! 가장 빠르게 탭!";
            els.battleSub.textContent = "누가 먼저 누를까?";
            els.battleStartBtn.classList.add("is-hidden");
            els.battleRestartBtn.classList.add("is-hidden");
            tone = "win";
        } else {
            const foulPlayer = state.battleResults.foulPlayer;
            if (foulPlayer) {
                const winner = state.battleResults.winner;
                els.battleStatus.textContent = `${playerLabel(foulPlayer)} 반칙!`;
                els.battleSub.textContent = winner ? `${playerLabel(winner)} 승리! 한 판 더?` : "한 판 더?";
                tone = "foul";
            } else {
                const winner = state.battleResults.winner;
                const time = winner ? state.battleResults[winner] : null;
                els.battleStatus.textContent = winner ? `${playerLabel(winner)} 승리` : "승부 완료";
                els.battleSub.textContent = time ? `${formatMs(time)} 기록으로 승리!` : "한 판 더 도전!";
                tone = "win";
            }
            els.battleStartBtn.classList.add("is-hidden");
            els.battleRestartBtn.classList.remove("is-hidden");
        }

        els.battleHud.dataset.state = state.gameState;
        els.battleHud.dataset.tone = tone;
        els.battleCenter.dataset.state = state.gameState;
        els.battleCenter.dataset.tone = tone;
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

    function bindTapTarget(node, handler) {
        if (!node) {
            return;
        }

        let suppressClick = false;

        if (window.PointerEvent) {
            node.addEventListener("pointerdown", (event) => {
                if (event.pointerType === "mouse" && event.button !== 0) {
                    return;
                }
                suppressClick = true;
                window.setTimeout(() => {
                    suppressClick = false;
                }, 350);
                event.preventDefault();
                handler();
            });
        }

        node.addEventListener("click", (event) => {
            if (suppressClick) {
                event.preventDefault();
                return;
            }
            handler();
        });
    }

    function handleSingleSave(event) {
        event.preventDefault();
        if (!state.singleSaveVisible || !state.singleSaveEligible || state.singleSaveSubmitted || state.singleResult === null) {
            return;
        }

        const name = (els.singleNameInput?.value || "").trim();
        if (!name) {
            state.singleSaveMessage = "이름을 넣어 주세요.";
            renderSingleSavePanel();
            els.singleNameInput?.focus();
            return;
        }

        addLeaderboardEntry(name, state.singleResult);
        state.singleSaveSubmitted = true;
        state.singleSaveMessage = `${name.slice(0, 16)} 기록 저장 완료!`;
        renderSingleSavePanel();
    }

    function render() {
        renderScreenVisibility();
        renderLeaderboard();
        renderSingleStage();
        renderBattleBoard();
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
        bindTapTarget(els.singleStage, handleSingleTap);
        els.singleStage?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                handleSingleTap();
            }
        });
        els.singleSaveForm?.addEventListener("submit", handleSingleSave);

        els.battleStartBtn?.addEventListener("click", startRound);
        els.battleRestartBtn?.addEventListener("click", startRound);
        bindTapTarget(els.battleP1, () => handleBattleTap("p1"));
        bindTapTarget(els.battleP2, () => handleBattleTap("p2"));

        els.fullscreenBtn?.addEventListener("click", toggleFullscreen);
        document.addEventListener("fullscreenchange", updateFullscreenButtonText);
    }

    bindEvents();
    updateFullscreenButtonText();
    render();
})();
