// Chess AI Logic - Last Updated: 2026-02-04 (Railway Sync Trigger)
var board = null;
var game = new Chess();
var moveHistory = [];
var stockfish = null;
var isAIThinking = false;
var selectedSquare = null;
var isEngineReady = false;
var pendingCommands = [];

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
    selectedSquare = null;
    isAIThinking = false;
}

function initBoard() {
    var config = {
        draggable: false, // STRICTLY Click-to-Move
        position: 'start',
        pieceTheme: function (piece) {
            return 'https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/wikipedia/' + piece + '.png';
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
            console.log("Engine:", line);

            // UCI 준비 완료
            if (line === 'uciok') {
                console.log("UCI mode ready, setting options...");
                setEngineOptions();
            }
            // 엔진 완전히 준비됨
            else if (line === 'readyok') {
                console.log("Engine ready!");
                isEngineReady = true;
                flushPendingCommands();
            }
            // 최선의 수 응답
            else if (line.indexOf('bestmove') !== -1) {
                onBestMove(line);
            }
        };

        stockfish.onerror = function (e) {
            console.error("Stockfish Worker Error:", e);
            alert("AI 엔진 로드에 실패했습니다.");
        };

        // UCI 모드 시작
        stockfish.postMessage('uci');

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

    // 브라우저 성능 고려 - 가벼운 설정
    stockfish.postMessage('setoption name Hash value 16');      // 메모리 최소화
    stockfish.postMessage('setoption name Threads value 1');    // 단일 스레드
    stockfish.postMessage('setoption name Skill Level value ' + skillLevel);

    // 준비 확인 요청
    stockfish.postMessage('isready');
}

function flushPendingCommands() {
    if (pendingCommands.length > 0) {
        console.log("Flushing", pendingCommands.length, "pending commands");
        for (var i = 0; i < pendingCommands.length; i++) {
            stockfish.postMessage(pendingCommands[i]);
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
        var move = game.move({
            from: selectedSquare,
            to: square,
            promotion: 'q' // Force Queen promotion for simplicity
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
    updateMoveHistory();
    updateStatus();

    selectedSquare = null;
    removeHighlights();

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
    document.getElementById('aiThinking').classList.add('active');

    var fen = game.fen();

    // 엔진이 준비되지 않았으면 대기열에 추가
    if (!isEngineReady) {
        console.log("Engine not ready yet, queuing commands...");
        pendingCommands.push('position fen ' + fen);
        pendingCommands.push('go depth 10');
        return;
    }

    // 브라우저 성능 고려 - 깊이 제한 (학생용이므로 가볍게)
    var depth = 10;
    stockfish.postMessage('position fen ' + fen);
    stockfish.postMessage('go depth ' + depth);
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
            updateMoveHistory();
            updateStatus();
        }

        isAIThinking = false;
        document.getElementById('aiThinking').classList.remove('active');
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
}

function removeHighlights() {
    $('#myBoard .square-55d63').removeClass('highlight-selected highlight-hint highlight-attack');
}

function updateStatus() {
    var status = '';
    var statusEl = document.getElementById('status');
    var moveColor = game.turn() === 'w' ? '백' : '흑';

    if (game.in_checkmate()) {
        status = '게임 종료 - ' + (game.turn() === 'w' ? '흑' : '백') + ' 승리!';
        statusEl.className = 'status-badge status-check';
        showGameOver(game.turn() === 'w' ? '흑 승리!' : '백 승리!', '체크메이트!');
    } else if (game.in_draw() || game.in_stalemate() || game.in_threefold_repetition()) {
        status = '게임 종료 - 무승부';
        statusEl.className = 'status-badge status-white';
        showGameOver('무승부', '무승부 상황입니다.');
    } else {
        if (isAIThinking) {
            status = 'AI가 생각 중...';
            statusEl.className = 'status-badge status-black';
        } else {
            status = moveColor + '의 차례' + (game.in_check() ? ' - 체크!' : '');
            statusEl.className = game.turn() === 'w' ? 'status-badge status-white' : 'status-badge status-black';
        }

        if (game.in_check()) statusEl.className += ' status-check';
    }

    statusEl.textContent = status;
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
    updateMoveHistory();
    updateStatus();
    closeGameOverModal();
};

window.undoMove = function () {
    if (moveHistory.length === 0) return;

    // If AI is thinking, ignore undo to prevent state corruption
    if (isAIThinking) return;

    if (IS_AI_MODE && moveHistory.length >= 2) {
        game.undo(); game.undo();
        moveHistory.pop(); moveHistory.pop();
    } else if (!IS_AI_MODE) {
        game.undo(); moveHistory.pop();
    }

    board.position(game.fen());
    selectedSquare = null;
    removeHighlights();
    updateMoveHistory();
    updateStatus();
};

window.closeGameOverModal = function () {
    document.getElementById('gameOverModal').classList.add('hidden');
};

function showGameOver(title, message) {
    document.getElementById('gameOverTitle').textContent = title;
    document.getElementById('gameOverMessage').textContent = message;
    var icon = '🏆';
    if (message.includes('무승부')) icon = '🤝';
    else if (title.includes('흑')) icon = '♚';
    else icon = '♔';
    document.getElementById('gameOverIcon').textContent = icon;

    setTimeout(function () {
        document.getElementById('gameOverModal').classList.remove('hidden');
    }, 500);
}
