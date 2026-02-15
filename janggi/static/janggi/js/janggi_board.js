(function () {
    var ROWS = 10;
    var COLS = 9;
    var boardEl = null;
    var turnEl = null;
    var historyEl = null;
    var toastEl = null;
    var resultOverlayEl = null;
    var resultTitleEl = null;
    var resultDescEl = null;
    var selected = null;
    var validTargets = [];
    var currentTurn = "red";
    var moveHistory = [];
    var moveTokens = [];
    var board = [];
    var undoStack = [];
    var lastMove = null;
    var aiRequestPending = false;
    var gameEnded = false;

    var pieceSourceBases = [
        (typeof JANGGI_STATIC_PIECE_BASE === "string" ? JANGGI_STATIC_PIECE_BASE : "/static/janggi/images/pieces/"),
        "https://raw.githubusercontent.com/gbtami/pychess-variants/master/client/piece/janggi/",
    ];

    function piece(type, side, label) {
        return { type: type, side: side, label: label };
    }

    function clonePiece(p) {
        return p ? { type: p.type, side: p.side, label: p.label } : null;
    }

    function cloneBoardState(srcBoard) {
        var cloned = [];
        for (var r = 0; r < ROWS; r++) {
            var row = [];
            for (var c = 0; c < COLS; c++) {
                row.push(clonePiece(srcBoard[r][c]));
            }
            cloned.push(row);
        }
        return cloned;
    }

    function pushUndoState() {
        undoStack.push({
            board: cloneBoardState(board),
            currentTurn: currentTurn,
            moveHistory: moveHistory.slice(),
            moveTokens: moveTokens.slice(),
            gameEnded: gameEnded,
            lastMove: lastMove ? { from: { r: lastMove.from.r, c: lastMove.from.c }, to: { r: lastMove.to.r, c: lastMove.to.c } } : null
        });
        if (undoStack.length > 120) undoStack.shift();
    }

    function showToast(title, desc) {
        if (!toastEl) return;
        toastEl.innerHTML = "<div class='toast-title'>" + title + "</div><div class='toast-desc'>" + desc + "</div>";
        toastEl.classList.add("show");
        setTimeout(function () {
            toastEl.classList.remove("show");
        }, 1700);
    }

    function endGame(winnerSide, title, desc) {
        gameEnded = true;
        if (!resultOverlayEl || !resultTitleEl || !resultDescEl) return;
        resultTitleEl.className = "result-title";
        if (winnerSide === "red") {
            resultTitleEl.classList.add("win-red");
            resultTitleEl.textContent = "RED 승리";
        } else if (winnerSide === "blue") {
            resultTitleEl.classList.add("win-blue");
            resultTitleEl.textContent = "BLUE 승리";
        } else {
            resultTitleEl.classList.add("draw");
            resultTitleEl.textContent = "무승부";
        }
        resultDescEl.textContent = title + " - " + desc;
        resultOverlayEl.classList.add("show");
    }

    function pieceCode(p) {
        var prefix = p.side === "red" ? "r_" : "b_";
        return prefix + p.type + ".png";
    }

    function pieceText(p) {
        if (p.type === "rook") return "차";
        if (p.type === "horse") return "마";
        if (p.type === "elephant") return "상";
        if (p.type === "guard") return "사";
        if (p.type === "king") return "궁";
        if (p.type === "cannon") return "포";
        if (p.type === "pawn") return p.side === "red" ? "병" : "졸";
        return p.label || "?";
    }

    function pieceSvgData(p) {
        var fg = p.side === "red" ? "#b91c1c" : "#1e40af";
        var bg = "#ffffff";
        var text = encodeURIComponent(p.label);
        var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><circle cx='32' cy='32' r='30' fill='" + bg + "' stroke='" + fg + "' stroke-width='4'/><text x='32' y='39' text-anchor='middle' font-size='26' font-weight='700' fill='" + fg + "'>" + text + "</text></svg>";
        return "data:image/svg+xml;utf8," + svg;
    }

    function buildPieceSources(p) {
        var file = pieceCode(p);
        return [pieceSourceBases[0] + file, pieceSourceBases[1] + file, pieceSvgData(p)];
    }

    function attachImageFallback(img, sources) {
        var idx = 0;
        img.src = sources[idx];
        img.onerror = function () {
            idx += 1;
            if (idx < sources.length) img.src = sources[idx];
        };
    }

    function initBoardState() {
        board = [];
        for (var r = 0; r < ROWS; r++) {
            var row = [];
            for (var c = 0; c < COLS; c++) row.push(null);
            board.push(row);
        }
        board[0][0] = piece("rook", "blue", "車");
        board[0][1] = piece("horse", "blue", "馬");
        board[0][2] = piece("elephant", "blue", "象");
        board[0][3] = piece("guard", "blue", "士");
        board[0][4] = piece("king", "blue", "將");
        board[0][5] = piece("guard", "blue", "士");
        board[0][6] = piece("elephant", "blue", "象");
        board[0][7] = piece("horse", "blue", "馬");
        board[0][8] = piece("rook", "blue", "車");
        board[2][1] = piece("cannon", "blue", "包");
        board[2][7] = piece("cannon", "blue", "包");
        board[3][0] = piece("pawn", "blue", "卒");
        board[3][2] = piece("pawn", "blue", "卒");
        board[3][4] = piece("pawn", "blue", "卒");
        board[3][6] = piece("pawn", "blue", "卒");
        board[3][8] = piece("pawn", "blue", "卒");

        board[9][0] = piece("rook", "red", "車");
        board[9][1] = piece("horse", "red", "馬");
        board[9][2] = piece("elephant", "red", "象");
        board[9][3] = piece("guard", "red", "士");
        board[9][4] = piece("king", "red", "帥");
        board[9][5] = piece("guard", "red", "士");
        board[9][6] = piece("elephant", "red", "象");
        board[9][7] = piece("horse", "red", "馬");
        board[9][8] = piece("rook", "red", "車");
        board[7][1] = piece("cannon", "red", "包");
        board[7][7] = piece("cannon", "red", "包");
        board[6][0] = piece("pawn", "red", "兵");
        board[6][2] = piece("pawn", "red", "兵");
        board[6][4] = piece("pawn", "red", "兵");
        board[6][6] = piece("pawn", "red", "兵");
        board[6][8] = piece("pawn", "red", "兵");
    }

    function inRange(r, c) {
        return r >= 0 && r < ROWS && c >= 0 && c < COLS;
    }

    function inPalace(side, r, c) {
        if (side === "blue") return r >= 0 && r <= 2 && c >= 3 && c <= 5;
        return r >= 7 && r <= 9 && c >= 3 && c <= 5;
    }

    function palaceDiagonalChains(side) {
        if (side === "blue") {
            return [
                [{ r: 0, c: 3 }, { r: 1, c: 4 }, { r: 2, c: 5 }],
                [{ r: 0, c: 5 }, { r: 1, c: 4 }, { r: 2, c: 3 }],
            ];
        }
        return [
            [{ r: 7, c: 3 }, { r: 8, c: 4 }, { r: 9, c: 5 }],
            [{ r: 7, c: 5 }, { r: 8, c: 4 }, { r: 9, c: 3 }],
        ];
    }

    function samePos(a, b) {
        return a && b && a.r === b.r && a.c === b.c;
    }

    function getPalacePath(from, to, side) {
        if (!inPalace(side, from.r, from.c) || !inPalace(side, to.r, to.c)) return null;
        var chains = palaceDiagonalChains(side);
        for (var i = 0; i < chains.length; i++) {
            var chain = chains[i];
            var fromIdx = -1;
            var toIdx = -1;
            for (var j = 0; j < chain.length; j++) {
                if (samePos(chain[j], from)) fromIdx = j;
                if (samePos(chain[j], to)) toIdx = j;
            }
            if (fromIdx !== -1 && toIdx !== -1) {
                var path = [];
                var step = fromIdx < toIdx ? 1 : -1;
                for (var k = fromIdx + step; k !== toIdx; k += step) {
                    path.push(chain[k]);
                }
                return path;
            }
        }
        return null;
    }

    function canPalaceDiagonalOneStep(from, to, side) {
        var path = getPalacePath(from, to, side);
        if (!path) return false;
        return Math.abs(from.r - to.r) === 1 && Math.abs(from.c - to.c) === 1;
    }

    function getPiece(r, c) {
        if (!inRange(r, c)) return null;
        return board[r][c];
    }

    function setPiece(r, c, p) {
        if (inRange(r, c)) board[r][c] = p;
    }

    function countBetweenStraight(from, to) {
        var cnt = 0;
        if (from.r === to.r) {
            var stepC = to.c > from.c ? 1 : -1;
            for (var c = from.c + stepC; c !== to.c; c += stepC) if (getPiece(from.r, c)) cnt++;
        } else if (from.c === to.c) {
            var stepR = to.r > from.r ? 1 : -1;
            for (var r = from.r + stepR; r !== to.r; r += stepR) if (getPiece(r, from.c)) cnt++;
        } else {
            return -1;
        }
        return cnt;
    }

    function canMove(from, to, pieceObj) {
        if (!inRange(to.r, to.c)) return false;
        if (from.r === to.r && from.c === to.c) return false;
        var target = getPiece(to.r, to.c);
        if (target && target.side === pieceObj.side) return false;

        var dr = to.r - from.r;
        var dc = to.c - from.c;
        var adr = Math.abs(dr);
        var adc = Math.abs(dc);

        if (pieceObj.type === "rook") {
            if (from.r === to.r || from.c === to.c) {
                return countBetweenStraight(from, to) === 0;
            }
            var diagPath = getPalacePath(from, to, pieceObj.side);
            if (!diagPath) return false;
            for (var i = 0; i < diagPath.length; i++) {
                if (getPiece(diagPath[i].r, diagPath[i].c)) return false;
            }
            return true;
        }

        if (pieceObj.type === "cannon") {
            if (from.r === to.r || from.c === to.c) {
                var between = countBetweenStraight(from, to);
                if (between !== 1) return false;
                if (target && target.type === "cannon") return false;
                return true;
            }
            var cPath = getPalacePath(from, to, pieceObj.side);
            if (!cPath) return false;
            var screens = 0;
            for (var j = 0; j < cPath.length; j++) if (getPiece(cPath[j].r, cPath[j].c)) screens++;
            if (screens !== 1) return false;
            if (target && target.type === "cannon") return false;
            return true;
        }

        if (pieceObj.type === "horse") {
            if (!((adr === 2 && adc === 1) || (adr === 1 && adc === 2))) return false;
            var legR = from.r + (adr === 2 ? dr / 2 : 0);
            var legC = from.c + (adc === 2 ? dc / 2 : 0);
            return !getPiece(legR, legC);
        }

        if (pieceObj.type === "elephant") {
            if (!(adr === 3 && adc === 2 || adr === 2 && adc === 3)) return false;
            var stepR = dr === 0 ? 0 : dr / Math.abs(dr);
            var stepC = dc === 0 ? 0 : dc / Math.abs(dc);
            var b1r = from.r + stepR;
            var b1c = from.c + stepC;
            var b2r = from.r + stepR * 2;
            var b2c = from.c + stepC * 2;
            return !getPiece(b1r, b1c) && !getPiece(b2r, b2c);
        }

        if (pieceObj.type === "guard") {
            if (!inPalace(pieceObj.side, to.r, to.c)) return false;
            if ((adr + adc) === 1) return true;
            if (adr === 1 && adc === 1) return canPalaceDiagonalOneStep(from, to, pieceObj.side);
            return false;
        }

        if (pieceObj.type === "king") {
            if (!inPalace(pieceObj.side, to.r, to.c)) return false;
            if ((adr + adc) === 1) return true;
            if (adr === 1 && adc === 1) return canPalaceDiagonalOneStep(from, to, pieceObj.side);
            return false;
        }

        if (pieceObj.type === "pawn") {
            var forward = pieceObj.side === "red" ? -1 : 1;
            if (dr === forward && dc === 0) return true;
            var crossed = pieceObj.side === "red" ? from.r <= 4 : from.r >= 5;
            if (crossed && dr === 0 && adc === 1) return true;
            if (inPalace(pieceObj.side === "red" ? "blue" : "red", from.r, from.c) && dr === forward && adc === 1) {
                return canPalaceDiagonalOneStep(from, to, pieceObj.side === "red" ? "blue" : "red");
            }
            return false;
        }

        return false;
    }

    function findKing(side) {
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var p = getPiece(r, c);
                if (p && p.type === "king" && p.side === side) return { r: r, c: c };
            }
        }
        return null;
    }

    function hasKing(side) {
        return !!findKing(side);
    }

    function kingsFacing() {
        var redKing = findKing("red");
        var blueKing = findKing("blue");
        if (!redKing || !blueKing) return false;
        if (redKing.c !== blueKing.c) return false;
        var c = redKing.c;
        var minR = Math.min(redKing.r, blueKing.r);
        var maxR = Math.max(redKing.r, blueKing.r);
        for (var r = minR + 1; r < maxR; r++) if (getPiece(r, c)) return false;
        return true;
    }

    function withTempMove(from, to, fn) {
        var mover = getPiece(from.r, from.c);
        var captured = getPiece(to.r, to.c);
        setPiece(to.r, to.c, mover);
        setPiece(from.r, from.c, null);
        var result = fn();
        setPiece(from.r, from.c, mover);
        setPiece(to.r, to.c, captured);
        return result;
    }

    function isInCheck(side) {
        var king = findKing(side);
        if (!king) return false;
        var enemy = side === "red" ? "blue" : "red";
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var p = getPiece(r, c);
                if (p && p.side === enemy) {
                    if (canMove({ r: r, c: c }, king, p)) return true;
                }
            }
        }
        return false;
    }

    function isLegalMove(from, to, p) {
        if (!canMove(from, to, p)) return false;
        return withTempMove(from, to, function () {
            if (kingsFacing()) return false;
            return !isInCheck(p.side);
        });
    }

    function collectValidTargets(from, p) {
        var list = [];
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                if (isLegalMove(from, { r: r, c: c }, p)) list.push({ r: r, c: c });
            }
        }
        return list;
    }

    function hasAnyLegalMove(side) {
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var p = getPiece(r, c);
                if (!p || p.side !== side) continue;
                if (collectValidTargets({ r: r, c: c }, p).length > 0) return true;
            }
        }
        return false;
    }

    function findFallbackMove(side) {
        var candidates = [];
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var p = getPiece(r, c);
                if (!p || p.side !== side) continue;
                var from = { r: r, c: c };
                var targets = collectValidTargets(from, p);
                for (var i = 0; i < targets.length; i++) {
                    candidates.push({ from: from, to: targets[i] });
                }
            }
        }
        if (!candidates.length) return null;
        return candidates[Math.floor(Math.random() * candidates.length)];
    }

    function squareName(pos) {
        return String.fromCharCode("a".charCodeAt(0) + pos.c) + String(pos.r);
    }

    function moveToken(from, to) {
        return squareName(from) + squareName(to);
    }

    function recordMove(from, to, p, captured) {
        var text = moveHistory.length + 1 + ". " + p.label + " " + squareName(from) + "-" + squareName(to);
        if (captured) text += " x" + captured.label;
        moveHistory.push(text);
        moveTokens.push(moveToken(from, to));
        if (historyEl) historyEl.textContent = moveHistory.join("\n");
    }

    function toggleTurn() {
        currentTurn = currentTurn === "red" ? "blue" : "red";
        if (turnEl) turnEl.textContent = "차례: " + currentTurn.toUpperCase();
    }

    function evaluateAfterMove(movedSide) {
        var enemy = movedSide === "red" ? "blue" : "red";
        if (!hasKing(enemy)) {
            endGame(movedSide, "왕 포획", "상대 궁이 잡혀서 즉시 승리했습니다.");
            return;
        }
        if (isInCheck(enemy)) {
            showToast("장군!", "상대 궁이 바로 공격받는 상태입니다. 다음 수에서 반드시 막거나 피해야 합니다.");
        }
        if (!hasAnyLegalMove(enemy)) {
            if (isInCheck(enemy)) {
                showToast("외통!", "상대가 장군을 피할 수 없어 게임이 끝났습니다.");
                endGame(movedSide, "외통 승리", "상대가 장군을 막을 수 없어 승패가 확정되었습니다.");
            } else {
                showToast("교착(무승부)", "합법적인 수가 없어 대국이 더 진행되지 않습니다.");
                endGame("draw", "무승부", "합법적인 수가 없어 대국이 종료되었습니다.");
            }
        }
        if (kingsFacing()) {
            showToast("빅장 경고", "두 궁이 같은 줄에서 마주보고 있습니다. 일반적으로 피하는 형태입니다.");
        }
    }

    function movePiece(from, to, silent) {
        var p = getPiece(from.r, from.c);
        if (!p) return false;
        if (!isLegalMove(from, to, p)) return false;
        pushUndoState();
        var captured = getPiece(to.r, to.c);
        setPiece(to.r, to.c, p);
        setPiece(from.r, from.c, null);
        lastMove = { from: { r: from.r, c: from.c }, to: { r: to.r, c: to.c } };
        if (!silent) recordMove(from, to, p, captured);
        evaluateAfterMove(p.side);
        toggleTurn();
        selected = null;
        validTargets = [];
        renderBoard();
        return true;
    }

    function handleCellClick(r, c) {
        if (gameEnded) return;
        var clicked = getPiece(r, c);
        if (!selected) {
            if (!clicked || clicked.side !== currentTurn) return;
            selected = { r: r, c: c };
            validTargets = collectValidTargets(selected, clicked);
            renderBoard();
            return;
        }

        if (samePos(selected, { r: r, c: c })) {
            selected = null;
            validTargets = [];
            renderBoard();
            return;
        }

        if (clicked && clicked.side === currentTurn) {
            selected = { r: r, c: c };
            validTargets = collectValidTargets(selected, clicked);
            renderBoard();
            return;
        }

        var moved = movePiece(selected, { r: r, c: c }, false);
        if (moved && !gameEnded && JANGGI_MODE === "ai" && currentTurn === "blue") {
            requestAiMove();
        }
    }

    function renderBoard() {
        if (!boardEl) return;
        boardEl.innerHTML = "";
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var cell = document.createElement("button");
                cell.type = "button";
                cell.className = "janggi-cell";
                if (selected && selected.r === r && selected.c === c) cell.classList.add("selected");
                if (validTargets.some(function (v) { return v.r === r && v.c === c; })) cell.classList.add("hint");
                if (lastMove && ((lastMove.from.r === r && lastMove.from.c === c) || (lastMove.to.r === r && lastMove.to.c === c))) {
                    cell.classList.add("last-move");
                }
                (function (rr, cc) {
                    cell.addEventListener("click", function () { handleCellClick(rr, cc); });
                })(r, c);
                var p = getPiece(r, c);
                if (p) {
                    var token = document.createElement("div");
                    token.className = "janggi-piece " + (p.side === "red" ? "piece-red" : "piece-blue");
                    token.textContent = pieceText(p);
                    token.setAttribute("aria-label", pieceText(p));
                    cell.appendChild(token);
                }
                boardEl.appendChild(cell);
            }
        }
    }

    function applyEngineMove(bestmove) {
        if (!bestmove || bestmove.length < 4 || gameEnded) return;
        var from = { c: bestmove.charCodeAt(0) - "a".charCodeAt(0), r: Number(bestmove.charAt(1)) };
        var to = { c: bestmove.charCodeAt(2) - "a".charCodeAt(0), r: Number(bestmove.charAt(3)) };
        var p = getPiece(from.r, from.c);
        if (!p || p.side !== currentTurn) return false;
        return movePiece(from, to, false);
    }

    function requestAiMove() {
        if (aiRequestPending || gameEnded || currentTurn !== "blue") return;
        aiRequestPending = true;
        if (window.JanggiAI) {
            window.JanggiAI.setPosition(moveTokens);
            window.JanggiAI.askMove();
        }
        setTimeout(function () {
            if (!aiRequestPending || gameEnded || currentTurn !== "blue") return;
            var fallback = findFallbackMove("blue");
            if (fallback) {
                showToast("AI 대체 수", "엔진 응답이 지연되어 기본 AI가 수를 두었습니다.");
                movePiece(fallback.from, fallback.to, false);
            }
            aiRequestPending = false;
        }, 1400);
    }

    function resetAll() {
        currentTurn = "red";
        moveHistory = [];
        moveTokens = [];
        undoStack = [];
        lastMove = null;
        aiRequestPending = false;
        selected = null;
        validTargets = [];
        gameEnded = false;
        if (historyEl) historyEl.textContent = "-";
        if (turnEl) turnEl.textContent = "차례: RED";
        if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        initBoardState();
        renderBoard();
    }

    function undoMove() {
        if (!undoStack.length) {
            showToast("알림", "되돌릴 수가 없습니다.");
            return;
        }
        var prev = undoStack.pop();
        board = cloneBoardState(prev.board);
        currentTurn = prev.currentTurn;
        moveHistory = prev.moveHistory.slice();
        moveTokens = prev.moveTokens.slice();
        gameEnded = prev.gameEnded;
        lastMove = prev.lastMove ? {
            from: { r: prev.lastMove.from.r, c: prev.lastMove.from.c },
            to: { r: prev.lastMove.to.r, c: prev.lastMove.to.c }
        } : null;
        selected = null;
        validTargets = [];
        if (historyEl) historyEl.textContent = moveHistory.length ? moveHistory.join("\n") : "-";
        if (turnEl) turnEl.textContent = "차례: " + currentTurn.toUpperCase();
        if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        renderBoard();
    }

    document.addEventListener("DOMContentLoaded", function () {
        boardEl = document.getElementById("janggiBoard");
        turnEl = document.getElementById("turnStatus");
        historyEl = document.getElementById("moveHistory");
        toastEl = document.getElementById("toast");
        resultOverlayEl = document.getElementById("gameResultOverlay");
        resultTitleEl = document.getElementById("resultTitle");
        resultDescEl = document.getElementById("resultDesc");
        var resetBtn = document.getElementById("resetBoardBtn");
        var undoBtn = document.getElementById("undoMoveBtn");
        var closeResultBtn = document.getElementById("closeResultBtn");
        var retryResultBtn = document.getElementById("retryResultBtn");
        if (resetBtn) resetBtn.addEventListener("click", resetAll);
        if (undoBtn) undoBtn.addEventListener("click", undoMove);
        if (closeResultBtn) closeResultBtn.addEventListener("click", function () {
            if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        });
        if (retryResultBtn) retryResultBtn.addEventListener("click", resetAll);

        resetAll();
        if (window.JanggiAI) {
            if (JANGGI_MODE === "ai") window.JanggiAI.init();
            window.JanggiAI.onBestMove(function (bestmove) {
                if (JANGGI_MODE === "ai" && currentTurn === "blue") {
                    var moved = applyEngineMove(bestmove);
                    if (!moved) {
                        var fallback = findFallbackMove("blue");
                        if (fallback) movePiece(fallback.from, fallback.to, false);
                    }
                    aiRequestPending = false;
                }
            });
        }
    });
})();
