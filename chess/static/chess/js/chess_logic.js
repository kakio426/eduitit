// Chess AI Logic - Last Updated: 2026-02-09 (Experience Upgrade)
var board = null;
var game = new Chess();
var moveHistory = [];
var capturedPieces = { white: [], black: [] }; // Track captured pieces
var stockfish = null;
var isAIThinking = false;
var selectedSquare = null;
var isEngineReady = false;
var pendingCommands = [];
var lastMove = null; // Track last move for highlighting
var pendingPromotion = null; // Track pending promotion move
var showLastMoveHighlight = true; // Toggle for last move highlight

// [CONFIGURATION]
// These variables must be defined in the HTML before loading this script:
// var STOCKFISH_PATH = "...";
// var IS_AI_MODE = true / false;
// var AI_DIFFICULTY = 'easy' / 'medium' / 'hard' / 'expert';

// ---------------------------------------------------------
// 1. Initialization
// ---------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
    initGame();
    initBoard();
    updateStatus();

    // Event Listeners
    window.addEventListener('resize', function () {
        if (board) board.resize();
    });

    // Square Click Delegation
    $(document).on('click', '.square-55d63', function (e) {
        var square = $(this).attr('data-square');
        if (square) {
            onSquareClick(square);
        }
    });

    // AI Initialization
    if (typeof IS_AI_MODE !== 'undefined' && IS_AI_MODE) {
        initStockfish();
    }
});

function initGame() {
    game.reset();
    moveHistory = [];
    capturedPieces = { white: [], black: [] };
    lastMove = null;
    selectedSquare = null;
    isAIThinking = false;
}

// ---------------------------------------------------------
// Sound & Notification System
// ---------------------------------------------------------
var sharedAudioContext = null;

function getAudioContext() {
    if (!sharedAudioContext) {
        sharedAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    // 브라우저 정책으로 suspended 상태일 수 있음
    if (sharedAudioContext.state === 'suspended') {
        sharedAudioContext.resume();
    }
    return sharedAudioContext;
}

function playSound(type) {
    try {
        var ctx = getAudioContext();
        var oscillator = ctx.createOscillator();
        var gainNode = ctx.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        if (type === 'move') {
            oscillator.frequency.value = 440;
            gainNode.gain.value = 0.1;
        } else if (type === 'capture') {
            oscillator.frequency.value = 550;
            gainNode.gain.value = 0.15;
        } else if (type === 'check') {
            oscillator.frequency.value = 880;
            gainNode.gain.value = 0.2;
        } else if (type === 'gameOver') {
            // 게임 종료: 낮은 음으로 두 번 울림
            oscillator.frequency.value = 330;
            gainNode.gain.value = 0.25;
            oscillator.start();
            oscillator.stop(ctx.currentTime + 0.2);
            // 두 번째 비프
            var osc2 = ctx.createOscillator();
            var gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.frequency.value = 220;
            gain2.gain.value = 0.25;
            osc2.start(ctx.currentTime + 0.3);
            osc2.stop(ctx.currentTime + 0.6);
            return;
        }

        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.1);
    } catch (e) {
        console.log('Audio not supported:', e);
    }
}

function showToast(message) {
    var toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');

    setTimeout(function () {
        toast.classList.remove('show');
    }, 2000);
}

// ---------------------------------------------------------
// Material Advantage Calculation
// ---------------------------------------------------------
function getMaterialAdvantage() {
    var pieceValues = {
        'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 0
    };

    var whiteMaterial = 0;
    var blackMaterial = 0;

    // Count all pieces on the board
    var board = game.board();
    for (var i = 0; i < 8; i++) {
        for (var j = 0; j < 8; j++) {
            var piece = board[i][j];
            if (piece) {
                var value = pieceValues[piece.type];
                if (piece.color === 'w') {
                    whiteMaterial += value;
                } else {
                    blackMaterial += value;
                }
            }
        }
    }

    return {
        white: whiteMaterial,
        black: blackMaterial,
        advantage: whiteMaterial - blackMaterial
    };
}

function updateCapturedPieces(move) {
    if (move.captured) {
        var capturedPiece = move.captured;
        var capturer = move.color; // 'w' or 'b'

        if (capturer === 'w') {
            capturedPieces.white.push(capturedPiece);
        } else {
            capturedPieces.black.push(capturedPiece);
        }

        renderCapturedPieces();
    }
}

function renderCapturedPieces() {
    var pieceSymbols = {
        'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
    };

    // Render White's captured pieces (black pieces)
    var whiteEl = document.getElementById('whiteCaptured');
    if (capturedPieces.white.length === 0) {
        whiteEl.innerHTML = '<span class="text-gray-400 text-sm italic">없음</span>';
    } else {
        whiteEl.innerHTML = '';
        capturedPieces.white.forEach(function (piece) {
            var span = document.createElement('span');
            span.className = 'captured-piece';
            span.textContent = pieceSymbols[piece];
            whiteEl.appendChild(span);
        });
    }

    // Render Black's captured pieces (white pieces)
    var blackEl = document.getElementById('blackCaptured');
    if (capturedPieces.black.length === 0) {
        blackEl.innerHTML = '<span class="text-gray-400 text-sm italic">없음</span>';
    } else {
        blackEl.innerHTML = '';
        capturedPieces.black.forEach(function (piece) {
            var span = document.createElement('span');
            span.className = 'captured-piece';
            span.textContent = pieceSymbols[piece];
            blackEl.appendChild(span);
        });
    }
}

var pieceCDNs = [
    'https://chessboardjs.com/img/chesspieces/wikipedia/', // [1] 공식 사이트 (가장 안정적)
    'https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/img/chesspieces/wikipedia/', // [2] unpkg (안정적)
    'https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/wikipedia/' // [3] GitHub (최후의 수단)
];
var currentCDNIndex = 0;

// Piece Image Fallback Listener - 이미지 로드 실패 시 다음 CDN으로 자동 전환
window.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG' && e.target.src.includes('chesspieces')) {
        if (currentCDNIndex < pieceCDNs.length - 1) {
            console.warn("Piece image failed to load from " + pieceCDNs[currentCDNIndex] + ". Trying next CDN...");
            currentCDNIndex++;
            if (board) board.position(game.fen()); // 보드 재렌더링
        }
    }
}, true);

function initBoard() {
    var config = {
        draggable: false, // STRICTLY Click-to-Move
        position: 'start',
        pieceTheme: function (piece) {
            return pieceCDNs[currentCDNIndex] + piece + '.png';
        },
        onSnapEnd: onSnapEnd
    };
    board = Chessboard('myBoard', config);
}

function initStockfish() {
    if (!STOCKFISH_PATH) {
        console.error("Stockfish path is missing!");
        return;
    }

    try {
        console.log("Initializing Stockfish from:", STOCKFISH_PATH);
        stockfish = new Worker(STOCKFISH_PATH);

        stockfish.onmessage = function (event) {
            var line = event.data;
            if (typeof line !== 'string') return;

            console.log("Engine:", line);
            var trimmedLine = line.trim();

            // UCI 준비 완료
            if (trimmedLine === 'uciok' || trimmedLine.startsWith('uciok')) {
                console.log("UCI mode ready, setting options...");
                setEngineOptions();
            }
            // 엔진 완전히 준비됨
            else if (trimmedLine === 'readyok' || trimmedLine.startsWith('readyok')) {
                console.log("Engine ready!");
                isEngineReady = true;
                flushPendingCommands();
            }
            // 최선의 수 응답
            else if (trimmedLine.indexOf('bestmove') !== -1) {
                onBestMove(trimmedLine);
            }
        };

        stockfish.onerror = function (e) {
            console.error("Stockfish Worker Error:", e);
            alert("AI 엔진 로드에 실패했습니다.");
        };

        // UCI 모드 시작
        sendCommand('uci');

    } catch (e) {
        console.error("Failed to create Stockfish worker:", e);
        alert("AI 엔진을 시작할 수 없습니다: " + e.message);
    }
}

function setEngineOptions() {
    // 난이도에 따른 Skill Level 설정
    var skillLevel = 10;
    if (typeof AI_DIFFICULTY !== 'undefined') {
        if (AI_DIFFICULTY === 'easy') skillLevel = 0;      // 초급 (학생용)
        else if (AI_DIFFICULTY === 'medium') skillLevel = 5; // 중급
        else if (AI_DIFFICULTY === 'hard') skillLevel = 10;  // 고급
        else if (AI_DIFFICULTY === 'expert') skillLevel = 20; // 최강
    }

    console.log("Setting AI Skill Level to:", skillLevel);

    // 불필요한 중복 설정 제거 (로그 분석 결과 기본값과 동일)
    sendCommand('setoption name Skill Level value ' + skillLevel);

    // 준비 확인 요청
    sendCommand('isready');

    // [Fallback] 엔진이 readyok를 보내지 않을 경우를 대비해 2초 후 강제 준비 완료
    setTimeout(function () {
        if (!isEngineReady) {
            console.warn("Engine did not respond with readyok in time. Forcing ready state...");
            isEngineReady = true;
            flushPendingCommands();
        }
    }, 2000);
}

function sendCommand(cmd) {
    if (stockfish) {
        console.log("To Engine:", cmd);
        stockfish.postMessage(cmd);
    }
}

function flushPendingCommands() {
    if (pendingCommands.length > 0) {
        console.log("Flushing", pendingCommands.length, "pending commands");
        for (var i = 0; i < pendingCommands.length; i++) {
            sendCommand(pendingCommands[i]);
        }
        pendingCommands = [];
    }
}

// ---------------------------------------------------------
// 2. Interaction Logic (Click-to-Move)
// ---------------------------------------------------------
function onSquareClick(square) {
    if (game.game_over()) return;
    if (IS_AI_MODE && game.turn() === 'b') return; // AI Turn

    var piece = game.get(square);

    // Case 1: Move Logic (If a square was already selected)
    if (selectedSquare) {
        var selectedPiece = game.get(selectedSquare);

        // Check if this is a pawn promotion move
        var isPromotion = selectedPiece && selectedPiece.type === 'p' &&
            ((selectedPiece.color === 'w' && square[1] === '8') ||
                (selectedPiece.color === 'b' && square[1] === '1'));

        if (isPromotion) {
            // Store the move and show promotion modal
            pendingPromotion = { from: selectedSquare, to: square };
            showPromotionModal();
            return;
        }

        // Regular move (no promotion)
        var move = game.move({
            from: selectedSquare,
            to: square
        });

        if (move) {
            handleMoveSuccess(move);
            return;
        }
    }

    // Case 2: Select Logic
    removeHighlights();

    // Only allow selecting own pieces
    if (!piece || piece.color !== game.turn()) {
        selectedSquare = null;
        return;
    }

    selectedSquare = square;
    highlightSquare(square, 'selected');

    // Show Hints
    var moves = game.moves({
        square: square,
        verbose: true
    });

    moves.forEach(function (m) {
        highlightSquare(m.to, m.captured ? 'attack' : 'hint');
    });
}

function handleMoveSuccess(move) {
    board.position(game.fen());
    moveHistory.push(move);
    lastMove = { from: move.from, to: move.to }; // Store for highlighting
    updateCapturedPieces(move); // Track captured pieces
    updateMoveHistory();
    updateStatus();

    selectedSquare = null;
    removeHighlights();
    highlightLastMove(); // Highlight the last move

    // Play sound based on move type
    if (move.captured) {
        playSound('capture');
    } else {
        playSound('move');
    }

    // Show toast for check
    if (game.in_check() && !game.game_over()) {
        playSound('check');
        showToast('⚠️ 체크!');
    }

    // Trigger AI
    if (IS_AI_MODE && !game.game_over()) {
        window.setTimeout(makeAIMove, 250);
    }
}

function onSnapEnd() {
    board.position(game.fen());
}

// ---------------------------------------------------------
// 3. AI Logic
// ---------------------------------------------------------
function makeAIMove() {
    if (game.game_over() || !stockfish || isAIThinking) return;

    isAIThinking = true;
    updateStatus(); // Show "AI Thinking..."

    // UI 표시 (올바른 ID 사용)
    var statusEl = document.getElementById('aiThinking');
    if (statusEl) {
        statusEl.classList.add('active');
    }

    var fen = game.fen();

    // 난이도별 파라미터 설정 (학생용 최적화)
    var params = getAIParams();

    // 엔진이 준비되지 않았으면 잠시 후 재시도
    if (!isEngineReady) {
        console.log("Engine not ready yet, retrying in 500ms...");
        isAIThinking = false;
        if (statusEl) {
            statusEl.classList.remove('active');
        }
        // 500ms 후 자동으로 재시도
        window.setTimeout(makeAIMove, 500);
        return;
    }

    // 브라우저 성능 및 난이도 고려
    sendCommand('position fen ' + fen);
    sendCommand('go depth ' + params.depth + ' movetime ' + params.movetime);
}

function getAIParams() {
    var depth = 10;
    var movetime = 2000; // 기본 2초

    if (typeof AI_DIFFICULTY !== 'undefined') {
        if (AI_DIFFICULTY === 'easy') {
            depth = 3;       // 매우 얕게 (즉시 응답)
            movetime = 300;  // 최대 0.3초
        } else if (AI_DIFFICULTY === 'medium') {
            depth = 6;       // 적당히 (빠름)
            movetime = 800;  // 최대 0.8초
        } else if (AI_DIFFICULTY === 'hard') {
            depth = 10;      // 정밀하게
            movetime = 2000; // 최대 2초
        } else if (AI_DIFFICULTY === 'expert') {
            depth = 15;      // 최장 계산
            movetime = 5000; // 최대 5초
        }
    }
    return { depth: depth, movetime: movetime };
}

function onBestMove(line) {
    var match = line.match(/bestmove\s+(\w+)/);
    if (match) {
        var moveStr = match[1];
        var from = moveStr.substring(0, 2);
        var to = moveStr.substring(2, 4);
        var promotion = moveStr.length > 4 ? moveStr[4] : 'q';

        var move = game.move({
            from: from,
            to: to,
            promotion: promotion
        });

        if (move) {
            board.position(game.fen());
            moveHistory.push(move);
            lastMove = { from: from, to: to }; // Store AI's last move
            updateCapturedPieces(move); // Track captured pieces
            updateMoveHistory();
            updateStatus();
            removeHighlights();
            highlightLastMove(); // Highlight AI's move
        } else {
            console.warn("AI attempted invalid move:", moveStr);
            // 잘못된 수일 경우 AI를 다시 시도하도록 허용
            isAIThinking = false;
            var statusEl = document.getElementById('aiThinking');
            if (statusEl) {
                statusEl.classList.remove('active');
            }
            // 재시도
            window.setTimeout(makeAIMove, 500);
            return;
        }

        // 상태 초기화 및 UI 숨기기 (올바른 ID 사용)
        isAIThinking = false;
        var statusEl = document.getElementById('aiThinking');
        if (statusEl) {
            statusEl.classList.remove('active');
        }
    }
}

// ---------------------------------------------------------
// 4. UI Helpers
// ---------------------------------------------------------
function highlightSquare(square, type) {
    var $square = $('#myBoard .square-' + square);
    if (type === 'selected') $square.addClass('highlight-selected');
    else if (type === 'hint') $square.addClass('highlight-hint');
    else if (type === 'attack') $square.addClass('highlight-attack');
    else if (type === 'last-move') $square.addClass('highlight-last-move');
    else if (type === 'check-king') $square.addClass('highlight-check-king');
}

function removeHighlights() {
    $('#myBoard .square-55d63').removeClass('highlight-selected highlight-hint highlight-attack highlight-last-move highlight-check-king');
}

function highlightLastMove() {
    if (lastMove && showLastMoveHighlight) {
        highlightSquare(lastMove.from, 'last-move');
        highlightSquare(lastMove.to, 'last-move');
    }
}

window.toggleLastMoveHighlight = function () {
    showLastMoveHighlight = !showLastMoveHighlight;
    var btn = document.getElementById('highlightToggleBtn');
    if (btn) {
        btn.textContent = showLastMoveHighlight ? '이전 수 표시: ON' : '이전 수 표시: OFF';
        btn.className = showLastMoveHighlight
            ? 'btn-game text-sm py-2 px-4 bg-yellow-100 text-yellow-700 border border-yellow-300 rounded-xl'
            : 'btn-game text-sm py-2 px-4 bg-gray-100 text-gray-500 border border-gray-300 rounded-xl';
    }
    removeHighlights();
    if (showLastMoveHighlight) highlightLastMove();
    // 체크 하이라이트 복원
    if (game.in_check() && !game.game_over()) highlightKingInCheck();
};

function updateStatus() {
    var status = '';
    var statusEl = document.getElementById('status');
    var moveColor = game.turn() === 'w' ? '백' : '흑';
    var winner = game.turn() === 'w' ? '흑' : '백';

    if (game.in_checkmate()) {
        status = '체크메이트! ' + winner + ' 승리!';
        statusEl.className = 'status-badge status-check';
        playSound('gameOver');
        showToast('♚ 체크메이트! ' + winner + '이 승리했습니다!');
        showGameOver('체크메이트!', winner + ' 승리! 킹이 잡혔습니다.');
    } else if (game.in_stalemate()) {
        status = '스테일메이트 - 무승부';
        statusEl.className = 'status-badge status-white';
        playSound('gameOver');
        showToast('🤝 스테일메이트! 둘 수 있는 수가 없습니다.');
        showGameOver('스테일메이트!', moveColor + '이 둘 수 있는 합법적인 수가 없어 무승부입니다.');
    } else if (game.in_threefold_repetition()) {
        status = '3회 반복 - 무승부';
        statusEl.className = 'status-badge status-white';
        playSound('gameOver');
        showToast('🔄 같은 상황이 3번 반복되어 무승부!');
        showGameOver('3회 반복 무승부!', '같은 보드 상태가 3번 반복되어 무승부입니다.');
    } else if (game.in_draw()) {
        status = '무승부';
        statusEl.className = 'status-badge status-white';
        playSound('gameOver');

        // 기물 부족 vs 50수 규칙 구분
        var drawReason = getDrawReason();
        showToast('🤝 ' + drawReason);
        showGameOver('무승부!', drawReason);
    } else {
        if (isAIThinking) {
            status = 'AI가 생각 중...';
            statusEl.className = 'status-badge status-black';
        } else {
            status = moveColor + '의 차례' + (game.in_check() ? ' - 체크!' : '');
            statusEl.className = game.turn() === 'w' ? 'status-badge status-white' : 'status-badge status-black';
        }

        if (game.in_check()) {
            statusEl.className += ' status-check';
            highlightKingInCheck();
        }
    }

    statusEl.textContent = status;
}

function getDrawReason() {
    // 기물 부족 체크: 킹만 남거나 킹+비숍/나이트만 남은 경우
    var dominated = game.board();
    var pieceCount = 0;
    var hasMinorOnly = true;
    for (var i = 0; i < 8; i++) {
        for (var j = 0; j < 8; j++) {
            var p = dominated[i][j];
            if (p && p.type !== 'k') {
                pieceCount++;
                if (p.type !== 'b' && p.type !== 'n') hasMinorOnly = false;
            }
        }
    }
    if (pieceCount === 0) return '양쪽 모두 킹만 남아 체크메이트가 불가능합니다.';
    if (pieceCount <= 1 && hasMinorOnly) return '남은 기물이 부족하여 체크메이트가 불가능합니다.';
    return '50수 동안 폰 이동이나 기물 잡기가 없어 무승부입니다.';
}

function highlightKingInCheck() {
    // Find the king's position for the current player
    var kingColor = game.turn();
    var board = game.board();

    for (var i = 0; i < 8; i++) {
        for (var j = 0; j < 8; j++) {
            var piece = board[i][j];
            if (piece && piece.type === 'k' && piece.color === kingColor) {
                var files = 'abcdefgh';
                var square = files[j] + (8 - i);
                highlightSquare(square, 'check-king');
                return;
            }
        }
    }
}

function updateMoveHistory() {
    var historyEl = document.getElementById('moveHistory');
    historyEl.innerHTML = '';

    if (moveHistory.length === 0) {
        historyEl.innerHTML = '<p class="text-gray-400 italic">아직 이동이 없습니다</p>';
        return;
    }

    // Build history list
    for (var i = 0; i < moveHistory.length; i += 2) {
        var moveNum = Math.floor(i / 2) + 1;
        var whiteMove = moveHistory[i].san;
        var blackMove = moveHistory[i + 1] ? moveHistory[i + 1].san : '...';

        var moveDiv = document.createElement('div');
        moveDiv.className = 'move-item flex items-center gap-3 text-sm';
        moveDiv.innerHTML = `
            <span class="font-bold text-gray-400 w-8">${moveNum}.</span>
            <span class="flex-1 text-gray-700">${whiteMove}</span>
            <span class="flex-1 text-gray-700">${blackMove}</span>
        `;
        historyEl.appendChild(moveDiv);
    }
    historyEl.scrollTop = historyEl.scrollHeight;
}

// Global functions for buttons
window.resetGame = function () {
    initGame();
    board.start();
    removeHighlights();
    renderCapturedPieces();
    updateMoveHistory();
    updateStatus();
    closeGameOverModal();
};

window.undoMove = function () {
    if (moveHistory.length === 0) return;

    // If AI is thinking, ignore undo to prevent state corruption
    if (isAIThinking) return;

    var undoCount = (IS_AI_MODE && moveHistory.length >= 2) ? 2 : (!IS_AI_MODE ? 1 : 0);
    if (undoCount === 0) return;

    for (var i = 0; i < undoCount; i++) {
        var undoneMove = moveHistory.pop();
        game.undo();

        // 잡은 기물 동기화: 되돌린 수에 잡힌 기물이 있었으면 제거
        if (undoneMove && undoneMove.captured) {
            var capturer = undoneMove.color === 'w' ? 'white' : 'black';
            var idx = capturedPieces[capturer].lastIndexOf(undoneMove.captured);
            if (idx !== -1) {
                capturedPieces[capturer].splice(idx, 1);
            }
        }
    }

    // lastMove 갱신: 남은 기록의 마지막 수로 설정
    if (moveHistory.length > 0) {
        var last = moveHistory[moveHistory.length - 1];
        lastMove = { from: last.from, to: last.to };
    } else {
        lastMove = null;
    }

    board.position(game.fen());
    selectedSquare = null;
    removeHighlights();
    highlightLastMove();
    renderCapturedPieces();
    updateMoveHistory();
    updateStatus();
};

window.closeGameOverModal = function () {
    document.getElementById('gameOverModal').classList.add('hidden');
};

// ---------------------------------------------------------
// Promotion Modal Functions
// ---------------------------------------------------------
function showPromotionModal() {
    document.getElementById('promotionModal').classList.remove('hidden');
}

function closePromotionModal() {
    document.getElementById('promotionModal').classList.add('hidden');
}

window.selectPromotion = function (pieceType) {
    if (!pendingPromotion) return;

    // Execute the promotion move
    var move = game.move({
        from: pendingPromotion.from,
        to: pendingPromotion.to,
        promotion: pieceType
    });

    if (move) {
        handleMoveSuccess(move);
    }

    // Clear pending promotion and close modal
    pendingPromotion = null;
    closePromotionModal();
};

function showGameOver(title, message) {
    document.getElementById('gameOverTitle').textContent = title;
    document.getElementById('gameOverMessage').textContent = message;

    var icon = '🏆';
    if (title.includes('무승부') || title.includes('스테일메이트') || title.includes('반복')) {
        icon = '🤝';
    } else if (title.includes('체크메이트')) {
        // 진 쪽(현재 턴)이 백이면 흑 승리
        icon = game.turn() === 'w' ? '♚' : '♔';
    }
    document.getElementById('gameOverIcon').textContent = icon;

    setTimeout(function () {
        document.getElementById('gameOverModal').classList.remove('hidden');
    }, 500);
}
