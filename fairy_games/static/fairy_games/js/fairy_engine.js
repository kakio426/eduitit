(function () {
    let engine = null;
    let booting = false;
    let ready = false;
    let supportedVariant = null;
    let pending = null;
    let pendingTimer = null;

    function levelByDifficulty(difficulty) {
        if (difficulty === "easy") return 4;
        if (difficulty === "medium") return 9;
        if (difficulty === "hard") return 14;
        return 20;
    }

    function clearPending() {
        if (pendingTimer) {
            clearTimeout(pendingTimer);
            pendingTimer = null;
        }
        pending = null;
    }

    function send(cmd) {
        if (!engine) return;
        engine.postMessage(cmd);
    }

    function onLine(raw) {
        const line = String(raw || "");
        const lower = line.toLowerCase();
        if (lower.includes("uciok")) {
            send("setoption name Threads value 1");
            send("isready");
            return;
        }
        if (lower.includes("readyok")) {
            ready = true;
            return;
        }
        if (line.indexOf("bestmove") === 0 && pending) {
            const parts = line.trim().split(/\s+/);
            const move = parts[1] || null;
            const cb = pending;
            clearPending();
            cb(move);
        }
    }

    function init(variant, difficulty) {
        if (booting || engine) return;
        if (typeof Stockfish !== "function") return;
        booting = true;
        supportedVariant = variant || null;
        Stockfish({
            locateFile: function (file) {
                if (file === "stockfish.wasm" && window.FAIRY_ENGINE_WASM_PATH) {
                    return window.FAIRY_ENGINE_WASM_PATH;
                }
                return file;
            }
        }).then(function (instance) {
            engine = instance;
            if (typeof engine.addMessageListener === "function") {
                engine.addMessageListener(onLine);
            } else {
                booting = false;
                return;
            }
            send("uci");
            if (supportedVariant) {
                send("setoption name UCI_Variant value " + supportedVariant);
            }
            send("setoption name Skill Level value " + levelByDifficulty(difficulty || "medium"));
            send("isready");
        }).finally(function () {
            booting = false;
        });
    }

    function requestMove(moveTokens, callback) {
        if (!engine || !ready || typeof callback !== "function") {
            callback(null);
            return;
        }
        clearPending();
        pending = callback;
        pendingTimer = setTimeout(function () {
            if (!pending) return;
            const cb = pending;
            clearPending();
            cb(null);
        }, 1200);

        if (moveTokens && moveTokens.length) {
            send("position startpos moves " + moveTokens.join(" "));
        } else {
            send("position startpos");
        }
        send("go movetime 700");
    }

    window.FairyEngine = {
        init: init,
        requestMove: requestMove,
        canUseEngine: function () {
            return !!(engine && ready);
        }
    };
})();

