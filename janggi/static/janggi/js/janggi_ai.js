(function () {
    var engine = null;
    var engineKind = null;
    var isReady = false;
    var statusEl = null;
    var logEl = null;
    var bestMoveHandler = null;
    var pendingMoves = [];
    var variantSupportsJanggi = false;

    function log(line) {
        if (!logEl) return;
        logEl.textContent += "\n" + line;
        logEl.scrollTop = logEl.scrollHeight;
    }

    function setStatus(text) {
        if (statusEl) statusEl.textContent = text;
    }

    function send(cmd) {
        if (!engine) {
            log("[Janggi] Engine not initialized.");
            return;
        }
        log(">> " + cmd);
        engine.postMessage(cmd);
    }

    function applyDifficulty() {
        var skill = 10;
        if (JANGGI_DIFFICULTY === "easy") skill = 3;
        else if (JANGGI_DIFFICULTY === "medium") skill = 8;
        else if (JANGGI_DIFFICULTY === "hard") skill = 14;
        else if (JANGGI_DIFFICULTY === "expert") skill = 20;
        send("setoption name Threads value 1");
        send("setoption name Skill Level value " + skill);
        send("setoption name UCI_Variant value janggi");
        send("isready");
    }

    function onEngineLine(raw) {
        var line = String(raw || "");
        log("<< " + line);
        if (line.indexOf("uciok") !== -1) {
            applyDifficulty();
        } else if (line.indexOf("option name UCI_Variant") !== -1) {
            if (line.toLowerCase().indexOf("janggi") !== -1) variantSupportsJanggi = true;
        } else if (line.indexOf("readyok") !== -1) {
            isReady = true;
            if (variantSupportsJanggi) {
                setStatus("엔진 준비 완료(" + engineKind + ")");
            } else {
                setStatus("엔진 준비 완료(" + engineKind + ", janggi 옵션 미확인)");
                log("[Janggi] UCI_Variant 목록에서 janggi를 확인하지 못했습니다.");
            }
        } else if (line.indexOf("bestmove") === 0) {
            setStatus("AI 수 계산 완료");
            var parts = line.split(/\s+/);
            var move = parts[1] || "";
            if (bestMoveHandler) bestMoveHandler(move);
        }
    }

    async function initByFactory() {
        if (typeof Stockfish !== "function") throw new Error("Stockfish factory unavailable.");
        setStatus("엔진 시작 중(factory)...");
        engine = await Stockfish({
            locateFile: function (file) {
                if (file === "stockfish.wasm") {
                    return JANGGI_ENGINE_PATH.replace("stockfish.js", "stockfish.wasm");
                }
                return file;
            }
        });
        engineKind = "factory";
        if (typeof engine.addMessageListener === "function") {
            engine.addMessageListener(onEngineLine);
        } else {
            throw new Error("addMessageListener API missing.");
        }
        send("uci");
    }

    function initByWorker() {
        setStatus("엔진 시작 중(worker)...");
        engine = new Worker(JANGGI_ENGINE_WORKER_PATH || JANGGI_ENGINE_PATH);
        engineKind = "worker";
        engine.onmessage = function (evt) {
            onEngineLine(evt.data);
        };
        engine.onerror = function () {
            setStatus("엔진 오류");
            log("[Janggi] Worker init failed.");
        };
        send("uci");
    }

    async function init() {
        if (engine) {
            log("[Janggi] Engine already initialized.");
            return;
        }
        isReady = false;
        try {
            await initByFactory();
        } catch (err) {
            log("[Janggi] Factory init failed: " + err.message);
            initByWorker();
        }
    }

    function setPositionMoves(moves) {
        pendingMoves = Array.isArray(moves) ? moves.slice() : [];
    }

    function askMove() {
        if (!JANGGI_IS_AI_MODE) {
            log("[Janggi] local 모드에서는 AI 요청을 무시합니다.");
            return;
        }
        if (!engine || !isReady) {
            log("[Janggi] 엔진 준비 전입니다.");
            return;
        }
        setStatus("AI 수 계산 중...");
        if (!pendingMoves.length) {
            send("position startpos");
        } else {
            send("position startpos moves " + pendingMoves.join(" "));
        }
        send("go movetime 800");
    }

    function onBestMove(fn) {
        bestMoveHandler = fn;
    }

    document.addEventListener("DOMContentLoaded", function () {
        statusEl = document.getElementById("engineStatus");
        logEl = document.getElementById("engineLog");
        var initBtn = document.getElementById("initEngineBtn");
        var askBtn = document.getElementById("askMoveBtn");
        if (initBtn) initBtn.addEventListener("click", init);
        if (askBtn) askBtn.addEventListener("click", askMove);
        if (!JANGGI_IS_AI_MODE) {
            setStatus("로컬 모드");
        }
    });

    window.JanggiAI = {
        init: init,
        askMove: askMove,
        setPosition: setPositionMoves,
        onBestMove: onBestMove,
        isReady: function () { return isReady; },
    };
})();
