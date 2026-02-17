(function () {
    var engine = null;
    var engineKind = null;
    var engineBooting = false;
    var engineReady = false;
    var variantSupportsJanggi = false;

    var statusEl = null;
    var logEl = null;

    var pendingMoveCallback = null;
    var pendingMoveTimer = null;

    function setStatus(text) {
        if (statusEl) statusEl.textContent = text;
    }

    function log(line) {
        if (!logEl) return;
        logEl.textContent += "\n" + line;
        logEl.scrollTop = logEl.scrollHeight;
    }

    function send(cmd) {
        if (!engine) return;
        log(">> " + cmd);
        engine.postMessage(cmd);
    }

    function getSkillByDifficulty() {
        if (JANGGI_DIFFICULTY === "easy") return 4;
        if (JANGGI_DIFFICULTY === "medium") return 9;
        if (JANGGI_DIFFICULTY === "hard") return 14;
        return 20;
    }

    function clearPendingMove() {
        if (pendingMoveTimer) {
            clearTimeout(pendingMoveTimer);
            pendingMoveTimer = null;
        }
        pendingMoveCallback = null;
    }

    function resolvePendingMove(bestmove) {
        if (!pendingMoveCallback) return;
        var cb = pendingMoveCallback;
        clearPendingMove();
        cb(bestmove || null);
    }

    function applyEngineOptions() {
        send("setoption name Threads value 1");
        send("setoption name Skill Level value " + getSkillByDifficulty());
        send("setoption name UCI_Variant value janggi");
        send("isready");
    }

    function onEngineLine(raw) {
        var line = String(raw || "");
        log("<< " + line);

        if (line.indexOf("option name UCI_Variant") !== -1 && line.toLowerCase().indexOf("janggi") !== -1) {
            variantSupportsJanggi = true;
            return;
        }

        if (line.indexOf("uciok") !== -1) {
            applyEngineOptions();
            return;
        }

        if (line.indexOf("readyok") !== -1) {
            engineReady = true;
            if (variantSupportsJanggi) {
                setStatus("엔진 준비 완료");
            } else {
                // Some builds do not print variant option lines; keep running if engine itself is ready.
                setStatus("엔진 준비 완료 (variant 옵션 미확인)");
            }
            return;
        }

        if (line.indexOf("bestmove") === 0) {
            var parts = line.trim().split(/\s+/);
            resolvePendingMove(parts[1] || null);
        }
    }

    function initByFactory() {
        if (typeof Stockfish !== "function") {
            return Promise.reject(new Error("Stockfish factory unavailable"));
        }
        setStatus("엔진 시작 중...");
        return Stockfish({
            locateFile: function (file) {
                if (file === "stockfish.wasm") {
                    if (typeof JANGGI_ENGINE_WASM_PATH === "string" && JANGGI_ENGINE_WASM_PATH.length > 0) {
                        return JANGGI_ENGINE_WASM_PATH;
                    }
                    return JANGGI_ENGINE_PATH.replace(/stockfish(?:\.[a-z0-9_-]+)?\.js$/i, "stockfish.wasm");
                }
                return file;
            }
        }).then(function (instance) {
            engine = instance;
            engineKind = "factory";
            if (typeof engine.addMessageListener !== "function") {
                throw new Error("Factory addMessageListener API missing");
            }
            engine.addMessageListener(onEngineLine);
            send("uci");
        });
    }

    function init() {
        if (engine || engineBooting) return;
        engineBooting = true;
        engineReady = false;
        variantSupportsJanggi = false;

        initByFactory()
            .catch(function (err) {
                log("[Janggi] Factory init failed: " + err.message);
                setStatus("엔진 초기화 실패");
            })
            .finally(function () {
                engineBooting = false;
            });
    }

    function requestMove(moves, callback) {
        if (typeof callback !== "function") return;

        // Do not hard-block by variantSupportsJanggi: option echo may be missing by build.
        if (!engine || !engineReady) {
            callback(null);
            return;
        }

        clearPendingMove();
        pendingMoveCallback = callback;
        pendingMoveTimer = setTimeout(function () {
            resolvePendingMove(null);
        }, 1100);

        if (!moves || !moves.length) {
            send("position startpos");
        } else {
            send("position startpos moves " + moves.join(" "));
        }
        setStatus("엔진 수 계산 중...");
        send("go movetime 650");
    }

    function askMove() {
        if (!JANGGI_IS_AI_MODE) return;
        if (!engine) init();
        setStatus("AI 수 요청 중...");
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
        } else {
            setStatus("장기 AI 준비 중");
            // Start booting engine in background; local AI keeps game responsive.
            init();
        }
    });

    window.JanggiAI = {
        init: init,
        requestMove: requestMove,
        canUseEngine: function () {
            return !!(engine && engineReady);
        },
        getState: function () {
            if (engine && engineReady) return "ready";
            if (engineBooting) return "booting";
            if (engine && !engineReady) return "loading";
            return "idle";
        }
    };
})();
