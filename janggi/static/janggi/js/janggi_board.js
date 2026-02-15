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
    var aiWaitAttempts = 0;
    var gameEnded = false;

    function piece(type, side, label) {
        return { type: type, side: side, label: label };
    }

    function clonePiece(p) {
        return p ? { type: p.type, side: p.side, label: p.label } : null;
    }

    function cloneBoardState(srcBoard) {
        var copied = [];
        for (var r = 0; r < ROWS; r++) {
            var row = [];
            for (var c = 0; c < COLS; c++) row.push(clonePiece(srcBoard[r][c]));
            copied.push(row);
        }
        return copied;
    }

    function pushUndoState() {
        undoStack.push({
            board: cloneBoardState(board),
            currentTurn: currentTurn,
            moveHistory: moveHistory.slice(),
            moveTokens: moveTokens.slice(),
            gameEnded: gameEnded,
            lastMove: lastMove ? {
                from: { r: lastMove.from.r, c: lastMove.from.c },
                to: { r: lastMove.to.r, c: lastMove.to.c }
            } : null
        });
        if (undoStack.length > 120) undoStack.shift();
    }

    function showToast(title, desc) {
        if (!toastEl) return;
        toastEl.innerHTML = "<div class='toast-title'>" + title + "</div><div class='toast-desc'>" + desc + "</div>";
        toastEl.classList.add("show");
        setTimeout(function () { toastEl.classList.remove("show"); }, 1600);
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

    function initBoardState() {
        board = [];
        for (var r = 0; r < ROWS; r++) {
            var row = [];
            for (var c = 0; c < COLS; c++) row.push(null);
            board.push(row);
        }

        // Blue (상단)
        board[0][0] = piece("rook", "blue", "車");
        board[0][1] = piece("horse", "blue", "馬");
        board[0][2] = piece("elephant", "blue", "象");
        board[0][3] = piece("guard", "blue", "士");
        board[0][4] = piece("king", "blue", "將");
        board[0][5] = piece("guard", "blue", "士");
        board[0][6] = piece("elephant", "blue", "象");
        board[0][7] = piece("horse", "blue", "馬");
        board[0][8] = piece("rook", "blue", "車");
        board[2][1] = piece("cannon", "blue", "砲");
        board[2][7] = piece("cannon", "blue", "砲");
        board[3][0] = piece("pawn", "blue", "卒");
        board[3][2] = piece("pawn", "blue", "卒");
        board[3][4] = piece("pawn", "blue", "卒");
        board[3][6] = piece("pawn", "blue", "卒");
        board[3][8] = piece("pawn", "blue", "卒");

        // Red (하단)
        board[9][0] = piece("rook", "red", "車");
        board[9][1] = piece("horse", "red", "馬");
        board[9][2] = piece("elephant", "red", "相");
        board[9][3] = piece("guard", "red", "士");
        board[9][4] = piece("king", "red", "帥");
        board[9][5] = piece("guard", "red", "士");
        board[9][6] = piece("elephant", "red", "相");
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
                [{ r: 0, c: 5 }, { r: 1, c: 4 }, { r: 2, c: 3 }]
            ];
        }
        return [
            [{ r: 7, c: 3 }, { r: 8, c: 4 }, { r: 9, c: 5 }],
            [{ r: 7, c: 5 }, { r: 8, c: 4 }, { r: 9, c: 3 }]
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
                for (var k = fromIdx + step; k !== toIdx; k += step) path.push(chain[k]);
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

    function getSingleScreenPieceStraight(from, to) {
        if (from.r === to.r) {
            var stepC = to.c > from.c ? 1 : -1;
            var found = null;
            for (var c = from.c + stepC; c !== to.c; c += stepC) {
                var p = getPiece(from.r, c);
                if (!p) continue;
                if (found) return null;
                found = p;
            }
            return found;
        }
        if (from.c === to.c) {
            var stepR = to.r > from.r ? 1 : -1;
            var found2 = null;
            for (var r = from.r + stepR; r !== to.r; r += stepR) {
                var p2 = getPiece(r, from.c);
                if (!p2) continue;
                if (found2) return null;
                found2 = p2;
            }
            return found2;
        }
        return null;
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
            if (from.r === to.r || from.c === to.c) return countBetweenStraight(from, to) === 0;
            var path = getPalacePath(from, to, pieceObj.side);
            if (!path) return false;
            for (var i = 0; i < path.length; i++) if (getPiece(path[i].r, path[i].c)) return false;
            return true;
        }

        if (pieceObj.type === "cannon") {
            if (from.r === to.r || from.c === to.c) {
                var between = countBetweenStraight(from, to);
                if (between !== 1) return false;
                var screenPiece = getSingleScreenPieceStraight(from, to);
                if (!screenPiece) return false;
                // 포는 포를 받침으로 사용할 수 없다.
                if (screenPiece.type === "cannon") return false;
                if (target && target.type === "cannon") return false;
                return true;
            }
            var cPath = getPalacePath(from, to, pieceObj.side);
            if (!cPath) return false;
            var screens = 0;
            var screenType = null;
            for (var j = 0; j < cPath.length; j++) {
                var sp = getPiece(cPath[j].r, cPath[j].c);
                if (!sp) continue;
                screens++;
                screenType = sp.type;
            }
            if (screens !== 1) return false;
            if (screenType === "cannon") return false;
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

        if (pieceObj.type === "guard" || pieceObj.type === "king") {
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

            var enemyPalace = pieceObj.side === "red" ? "blue" : "red";
            if (inPalace(enemyPalace, from.r, from.c) && dr === forward && adc === 1) {
                return canPalaceDiagonalOneStep(from, to, enemyPalace);
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

        var minR = Math.min(redKing.r, blueKing.r);
        var maxR = Math.max(redKing.r, blueKing.r);
        for (var r = minR + 1; r < maxR; r++) if (getPiece(r, redKing.c)) return false;
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
                if (p && p.side === enemy && canMove({ r: r, c: c }, king, p)) return true;
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

    function pieceValue(type) {
        if (type === "king") return 1000;
        if (type === "rook") return 13;
        if (type === "cannon") return 7;
        if (type === "horse") return 6;
        if (type === "elephant") return 4;
        if (type === "guard") return 3;
        return 2;
    }

    function evaluateMove(side, from, to) {
        var moved = getPiece(from.r, from.c);
        var captured = getPiece(to.r, to.c);
        if (!moved) return -99999;

        var score = 0;
        if (captured) score += pieceValue(captured.type) * 14;
        if (to.r >= 3 && to.r <= 6 && to.c >= 2 && to.c <= 6) score += 2;

        score += withTempMove(from, to, function () {
            var local = 0;
            var enemy = side === "red" ? "blue" : "red";
            if (isInCheck(enemy)) local += 8;
            if (!hasAnyLegalMove(enemy)) local += 30;
            return local;
        });

        return score + Math.random() * 1.5;
    }

    function findLocalAiMove(side) {
        var best = null;
        var bestScore = -99999;
        for (var r = 0; r < ROWS; r++) {
            for (var c = 0; c < COLS; c++) {
                var p = getPiece(r, c);
                if (!p || p.side !== side) continue;
                var from = { r: r, c: c };
                var targets = collectValidTargets(from, p);
                for (var i = 0; i < targets.length; i++) {
                    var to = targets[i];
                    var score = evaluateMove(side, from, to);
                    if (score > bestScore) {
                        bestScore = score;
                        best = { from: { r: from.r, c: from.c }, to: { r: to.r, c: to.c } };
                    }
                }
            }
        }
        return best;
    }

    function squareName(pos) {
        return String.fromCharCode("a".charCodeAt(0) + pos.c) + String(pos.r);
    }

    function moveToken(from, to) {
        return squareName(from) + squareName(to);
    }

    function pieceKoreanName(type) {
        if (type === "rook") return "차";
        if (type === "horse") return "마";
        if (type === "elephant") return "상";
        if (type === "guard") return "사";
        if (type === "king") return "궁";
        if (type === "cannon") return "포";
        return "졸";
    }

    function recordMove(from, to, p, captured) {
        var text = (moveHistory.length + 1) + ". " + pieceKoreanName(p.type) + " " + squareName(from) + "-" + squareName(to);
        if (captured) text += " x" + pieceKoreanName(captured.type);
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
            endGame(movedSide, "궁 포획", "상대 궁을 잡아 즉시 승리했습니다.");
            return;
        }
        if (isInCheck(enemy)) {
            showToast("장군!", "상대 궁이 공격받는 상태입니다.");
        }
        if (!hasAnyLegalMove(enemy)) {
            if (isInCheck(enemy)) {
                endGame(movedSide, "외통 승리", "상대가 장군을 피할 수 없어 대국이 종료되었습니다.");
            } else {
                endGame("draw", "무승부", "합법적인 수가 없어 대국이 종료되었습니다.");
            }
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
                    token.textContent = p.label;
                    token.setAttribute("aria-label", p.label);
                    cell.appendChild(token);
                }
                boardEl.appendChild(cell);
            }
        }
    }

    function parseEngineMove(bestmove) {
        if (!bestmove || bestmove.length < 4) return null;
        var from = {
            c: bestmove.charCodeAt(0) - "a".charCodeAt(0),
            r: Number(bestmove.charAt(1))
        };
        var to = {
            c: bestmove.charCodeAt(2) - "a".charCodeAt(0),
            r: Number(bestmove.charAt(3))
        };
        if (!inRange(from.r, from.c) || !inRange(to.r, to.c)) return null;
        return { from: from, to: to };
    }

    function requestAiMove() {
        if (aiRequestPending || gameEnded || currentTurn !== "blue") return;
        if (!window.JanggiAI || typeof window.JanggiAI.requestMove !== "function") {
            showToast("엔진 오류", "AI 엔진 연결에 실패했습니다. 새로고침 후 다시 시도하세요.");
            return;
        }

        if (!window.JanggiAI.canUseEngine()) {
            if (typeof window.JanggiAI.init === "function") window.JanggiAI.init();
            aiWaitAttempts += 1;
            if (aiWaitAttempts === 1) {
                showToast("엔진 준비 중", "엔진 준비가 끝나면 AI가 자동으로 수를 둡니다.");
            }
            if (aiWaitAttempts <= 30) {
                setTimeout(function () {
                    requestAiMove();
                }, 400);
            } else {
                showToast("엔진 준비 실패", "엔진이 준비되지 않았습니다. 다시 시작을 눌러 주세요.");
            }
            return;
        }

        aiRequestPending = true;
        window.JanggiAI.requestMove(moveTokens.slice(), function (bestmove) {
            if (!aiRequestPending || gameEnded || currentTurn !== "blue") return;
            var parsed = parseEngineMove(bestmove);
            if (parsed && movePiece(parsed.from, parsed.to, false)) {
                aiRequestPending = false;
                aiWaitAttempts = 0;
                return;
            }
            aiRequestPending = false;
            showToast("엔진 응답 오류", "AI 수를 해석하지 못했습니다. 다시 요청합니다.");
            setTimeout(function () {
                requestAiMove();
            }, 300);
        });
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
        aiRequestPending = false;
        aiWaitAttempts = 0;
        if (historyEl) historyEl.textContent = moveHistory.length ? moveHistory.join("\n") : "-";
        if (turnEl) turnEl.textContent = "차례: " + currentTurn.toUpperCase();
        if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        renderBoard();
    }

    function resetAll() {
        currentTurn = "red";
        moveHistory = [];
        moveTokens = [];
        undoStack = [];
        lastMove = null;
        selected = null;
        validTargets = [];
        aiRequestPending = false;
        aiWaitAttempts = 0;
        gameEnded = false;
        if (historyEl) historyEl.textContent = "-";
        if (turnEl) turnEl.textContent = "차례: RED";
        if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        initBoardState();
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
        var askMoveBtn = document.getElementById("askMoveBtn");

        if (resetBtn) resetBtn.addEventListener("click", resetAll);
        if (undoBtn) undoBtn.addEventListener("click", undoMove);
        if (closeResultBtn) closeResultBtn.addEventListener("click", function () {
            if (resultOverlayEl) resultOverlayEl.classList.remove("show");
        });
        if (retryResultBtn) retryResultBtn.addEventListener("click", resetAll);
        if (askMoveBtn) askMoveBtn.addEventListener("click", function () {
            if (JANGGI_MODE === "ai" && currentTurn === "blue") requestAiMove();
        });

        resetAll();
        if (window.JanggiAI && JANGGI_MODE === "ai" && typeof window.JanggiAI.init === "function") {
            window.JanggiAI.init();
        }
    });
})();
