(function () {
    var engine = null;
    var engineKind = null;
    var isReady = false;
    var statusEl = null;
    var logEl = null;
    var bestMoveHandler = null;
    var pendingMoves = [];
    var pendingAsk = false;
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
                setStatus("?붿쭊 以鍮??꾨즺(" + engineKind + ")");
            } else {
                setStatus("?붿쭊 以鍮??꾨즺(" + engineKind + ", janggi ?듭뀡 誘명솗??");
                log("[Janggi] UCI_Variant 紐⑸줉?먯꽌 janggi瑜??뺤씤?섏? 紐삵뻽?듬땲??");
            }
            if (pendingAsk) {
                pendingAsk = false;
                askMove();
            }
        } else if (line.indexOf("bestmove") === 0) {
            setStatus("AI ??怨꾩궛 ?꾨즺");
            var parts = line.split(/\s+/);
            var move = parts[1] || "";
            if (bestMoveHandler) bestMoveHandler(move);
        }
    }

    async function initByFactory() {
        if (typeof Stockfish !== "function") throw new Error("Stockfish factory unavailable.");
        setStatus("?붿쭊 ?쒖옉 以?factory)...");
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
        setStatus("?붿쭊 ?쒖옉 以?worker)...");
        engine = new Worker(JANGGI_ENGINE_WORKER_PATH || JANGGI_ENGINE_PATH);
        engineKind = "worker";
        engine.onmessage = function (evt) {
            onEngineLine(evt.data);
        };
        engine.onerror = function () {
            setStatus("?붿쭊 ?ㅻ쪟");
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
            log("[Janggi] local 紐⑤뱶?먯꽌??AI ?붿껌??臾댁떆?⑸땲??");
            return;
        }
        if (!engine) {
            pendingAsk = true;
            init();
            log("[Janggi] Engine is starting. Your AI request is queued.");
            return;
        }
        if (!isReady) {
            pendingAsk = true;
            log("[Janggi] Engine is preparing. AI will move automatically when ready.");
            return;
        }
        setStatus("AI ??怨꾩궛 以?..");
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
            setStatus("濡쒖뺄 紐⑤뱶");
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

