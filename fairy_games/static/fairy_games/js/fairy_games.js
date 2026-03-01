(function () {
  const boardEl = document.getElementById('fg-board');
  const statusEl = document.getElementById('fg-status');
  const historyEl = document.getElementById('fg-history');
  const resetBtn = document.getElementById('fg-reset');
  const undoBtn = document.getElementById('fg-undo');
  const flipBtn = document.getElementById('fg-flip');
  const openRulesBtn = document.getElementById('fg-open-rules');
  const topEl = document.getElementById('fg-extra-top');
  const bottomEl = document.getElementById('fg-extra-bottom');
  const rulesListEl = document.getElementById('fg-rules-list');
  const stageEl = document.getElementById('fg-stage');
  const missionEl = document.getElementById('fg-mission');
  const tipEl = document.getElementById('fg-tip');
  const turnTopEl = document.getElementById('fg-turn-top');
  const turnBottomEl = document.getElementById('fg-turn-bottom');
  const resultModalEl = document.getElementById('fg-result-modal');
  const resultTitleEl = document.getElementById('fg-result-title');
  const resultDescEl = document.getElementById('fg-result-desc');
  const resultRestartBtn = document.getElementById('fg-result-restart');
  const resultCloseBtn = document.getElementById('fg-result-close');
  const rulesModalEl = document.getElementById('fg-rules-modal');
  const rulesCloseBtn = document.getElementById('fg-rules-close');

  const MODE = 'local';
  const VARIANT = (window.FAIRY_VARIANT || 'cfour').toLowerCase();
  const LEVEL = (window.FAIRY_DIFFICULTY || 'medium').toLowerCase();

  let game = null;
  let state = null;
  let undoStack = [];
  let handPick = null;
  let boardFlipped = false;
  let resultShown = false;

  const copy = (o) => JSON.parse(JSON.stringify(o));
  const sideName = (s) => (s === 1 ? '초(빨강)' : '한(파랑)');
  const other = (s) => (s === 1 ? 2 : 1);
  const aiActive = () => false;
  const rand = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const setStatus = (text) => { statusEl.textContent = text; };
  const setHistory = (arr) => { historyEl.textContent = arr.length ? arr.join('\n') : '-'; };
  const pushUndo = () => { undoStack.push(copy(state)); if (undoStack.length > 150) undoStack.shift(); };

  function popUndo() {
    if (!undoStack.length) return;
    state = undoStack.pop();
    handPick = null;
    render();
  }

  function setBoardFlip(active) {
    boardFlipped = !!active;
    if (!boardEl) return;
    boardEl.classList.toggle('flipped', boardFlipped);
  }

  function setRulesModal(open) {
    if (!rulesModalEl) return;
    rulesModalEl.classList.toggle('show', !!open);
    rulesModalEl.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  function setResultModal(open) {
    if (!resultModalEl) return;
    resultModalEl.classList.toggle('show', !!open);
    resultModalEl.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  function maybeShowResult() {
    if (!state || !state.gameOver || resultShown) return;
    resultShown = true;
    if (resultTitleEl) resultTitleEl.textContent = state.winner ? `${sideName(state.winner)} 승리` : '무승부';
    if (resultDescEl) resultDescEl.textContent = state.winner ? '축하합니다! 다시 도전해 보세요.' : '승부가 나지 않았어요. 다시 해볼까요?';
    setResultModal(true);
  }

  function pieceHtml(side, glyph, rotateOpponent = false) {
    if (!glyph) return '';
    const cls = rotateOpponent && side === 2 ? 'fg-piece opponent' : 'fg-piece';
    return `<span class="${cls}">${glyph}</span>`;
  }

  function setTurnIndicator(s) {
    if (!turnTopEl || !turnBottomEl || !s) return;
    const topActive = !s.gameOver && s.turn === 2;
    const bottomActive = !s.gameOver && s.turn === 1;
    turnTopEl.classList.toggle('active', topActive);
    turnBottomEl.classList.toggle('active', bottomActive);

    const topLabel = turnTopEl.querySelector('small');
    const bottomLabel = turnBottomEl.querySelector('small');
    if (s.gameOver) {
      if (s.winner === 1) {
        if (bottomLabel) bottomLabel.textContent = '승리';
        if (topLabel) topLabel.textContent = '패배';
      } else if (s.winner === 2) {
        if (bottomLabel) bottomLabel.textContent = '패배';
        if (topLabel) topLabel.textContent = '승리';
      } else {
        if (bottomLabel) bottomLabel.textContent = '무승부';
        if (topLabel) topLabel.textContent = '무승부';
      }
      return;
    }
    if (topLabel) topLabel.textContent = topActive ? '내 차례' : '대기';
    if (bottomLabel) bottomLabel.textContent = bottomActive ? '내 차례' : '대기';
  }

  function posToken(r, c) { return String.fromCharCode(97 + c) + String(r); }
  function moveToken(fr, fc, tr, tc) { return posToken(fr, fc) + posToken(tr, tc); }

  function cell(cls, html, onClick) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fg-cell ' + cls;
    btn.innerHTML = html;
    btn.addEventListener('click', onClick);
    return btn;
  }

  function drawGrid(rows, cols, make, cellWidth = 52) {
    boardEl.innerHTML = '';
    boardEl.style.setProperty('--fg-cols', String(cols));
    boardEl.style.setProperty('--fg-cell-max', `${cellWidth}px`);
    boardEl.style.gridTemplateColumns = `repeat(${cols}, minmax(0, var(--fg-cell-size)))`;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) boardEl.appendChild(make(r, c));
  }

  function variantUiMeta(variant) {
    if (variant === 'dobutsu') return {
      cls: 'fg-variant-dobutsu',
      mission: '사자를 지키고 상대 사자를 먼저 잡아 보세요.',
      tip: '팁: 손패를 눌러 빈칸에 드롭하면 흐름을 바꿀 수 있어요.'
    };
    if (variant === 'cfour') return {
      cls: 'fg-variant-cfour',
      mission: '가로, 세로, 대각선으로 4개를 먼저 이어 보세요.',
      tip: '팁: 가운데 열을 먼저 잡으면 공격과 방어가 쉬워집니다.'
    };
    if (variant === 'isolation') return {
      cls: 'fg-variant-isolation',
      mission: '이동 후 칸을 막아 상대를 고립시켜 보세요.',
      tip: '팁: 이동 단계와 칸 막기 단계를 번갈아 확인하세요.'
    };
    if (variant === 'ataxx') return {
      cls: 'fg-variant-ataxx',
      mission: '복제와 점프로 내 색을 넓게 퍼뜨려 보세요.',
      tip: '팁: 상대 돌 옆으로 이동하면 한 번에 여러 칸이 바뀝니다.'
    };
    if (variant === 'breakthrough') return {
      cls: 'fg-variant-breakthrough',
      mission: '한 말만 끝줄에 도착시켜도 승리입니다.',
      tip: '팁: 양쪽 날개로 동시에 전진하면 막기 어려워집니다.'
    };
    return { cls: '', mission: '상대보다 한 수 앞서 생각해 보세요.', tip: '' };
  }

  function applyVariantUi() {
    const meta = variantUiMeta(VARIANT);
    if (stageEl) {
      stageEl.classList.remove(
        'fg-variant-dobutsu',
        'fg-variant-cfour',
        'fg-variant-isolation',
        'fg-variant-ataxx',
        'fg-variant-breakthrough'
      );
      if (meta.cls) stageEl.classList.add(meta.cls);
    }
    if (missionEl) missionEl.textContent = meta.mission;
    if (tipEl) tipEl.textContent = meta.tip;
  }

  function lineWin(board, r, c, side, need) {
    const dirs = [[1, 0], [0, 1], [1, 1], [1, -1]];
    for (const [dr, dc] of dirs) {
      let n = 1;
      for (let k = 1; board[r + dr * k] && board[r + dr * k][c + dc * k] === side; k++) n++;
      for (let k = 1; board[r - dr * k] && board[r - dr * k][c - dc * k] === side; k++) n++;
      if (n >= need) return true;
    }
    return false;
  }

  const cfour = {
    init() { return { b: Array.from({ length: 6 }, () => Array(7).fill(0)), turn: 1, gameOver: false, winner: 0, h: [], tokens: [] }; },
    row(s, c) { for (let r = 5; r >= 0; r--) if (!s.b[r][c]) return r; return -1; },
    moves(s) { const m = []; for (let c = 0; c < 7; c++) if (this.row(s, c) >= 0) m.push(c); return m; },
    apply(s, c) {
      const r = this.row(s, c); if (r < 0 || s.gameOver) return;
      s.b[r][c] = s.turn;
      s.tokens.push(String.fromCharCode(97 + c));
      s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} C${c + 1}`);
      if (lineWin(s.b, r, c, s.turn, 4)) { s.gameOver = true; s.winner = s.turn; return; }
      if (!this.moves(s).length) { s.gameOver = true; return; }
      s.turn = other(s.turn);
    },
    onNoMove(s) {
      if (s.gameOver) return;
      s.gameOver = true;
      s.winner = 0;
    },
    ai(s) {
      const moves = this.moves(s); if (!moves.length) return null;
      if (LEVEL === 'easy') return rand(moves);
      for (const c of moves) { const t = copy(s); this.apply(t, c); if (t.gameOver && t.winner === s.turn) return c; }
      moves.sort((a, b) => Math.abs(3 - a) - Math.abs(3 - b));
      return moves[0];
    },
    parseEngineMove(s, token) {
      if (!token || !token.length) return null;
      const col = token.charCodeAt(0) - 97;
      if (col < 0 || col > 6) return null;
      const legal = this.moves(s).includes(col);
      return legal ? col : null;
    },
    render(s) {
      topEl.innerHTML = ''; bottomEl.innerHTML = '';
      const legalCols = this.moves(s);
      drawGrid(6, 7, (r, c) => {
        const v = s.b[r][c];
        const disk = v ? `<div class='fg-disc ${v === 1 ? 'fg-red' : 'fg-blue'}'></div>` : '';
        const cls = `${(r + c) % 2 ? 'dark' : ''} ${(!s.gameOver && !aiActive() && legalCols.includes(c) && r === 5) ? 'hint' : ''}`.trim();
        return cell(cls, `<div class='fg-disc-wrap'>${disk}</div>`, () => {
          if (aiActive() || s.gameOver) return;
          pushUndo(); this.apply(s, c); render(); aiTurn();
        });
      }, 76);
      setStatus(s.gameOver ? (s.winner ? `${sideName(s.winner)} 승리` : '무승부') : `차례: ${sideName(s.turn)}`);
      setHistory(s.h);
    }
  };

  const isolation = {
    init() { return { n: 7, p1: [0, 0], p2: [6, 6], blk: {}, turn: 1, phase: 'move', sel: null, gameOver: false, winner: 0, h: [], tokens: [] }; },
    key(r, c) { return `${r},${c}`; },
    occ(s, r, c) { return s.blk[this.key(r, c)] || (s.p1[0] === r && s.p1[1] === c) || (s.p2[0] === r && s.p2[1] === c); },
    moves(s, side) {
      const p = side === 1 ? s.p1 : s.p2, out = [];
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        if (!dr && !dc) continue;
        const r = p[0] + dr, c = p[1] + dc;
        if (r >= 0 && c >= 0 && r < s.n && c < s.n && !this.occ(s, r, c)) out.push([r, c]);
      }
      return out;
    },
    onNoMove(s) {
      if (s.gameOver) return;
      if (s.phase === 'move' && !this.moves(s, s.turn).length) {
        s.gameOver = true;
        s.winner = other(s.turn);
      }
    },
    apply(s, m) {
      if (s.gameOver) return;
      if (m.t === 'm') {
        const from = s.turn === 1 ? s.p1 : s.p2;
        s.tokens.push(moveToken(from[0], from[1], m.r, m.c));
        if (s.turn === 1) s.p1 = [m.r, m.c]; else s.p2 = [m.r, m.c];
        s.phase = 'block'; s.sel = null; return;
      }
      s.blk[this.key(m.r, m.c)] = 1;
      s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} 막기(${m.r + 1},${m.c + 1})`);
      s.turn = other(s.turn); s.phase = 'move'; s.sel = null;
      if (!this.moves(s, s.turn).length) { s.gameOver = true; s.winner = other(s.turn); }
    },
    ai(s) {
      if (s.phase === 'move') { const m = this.moves(s, s.turn); if (!m.length) return null; const p = rand(m); return { t: 'm', r: p[0], c: p[1] }; }
      const blocks = []; for (let r = 0; r < s.n; r++) for (let c = 0; c < s.n; c++) if (!this.occ(s, r, c)) blocks.push([r, c]);
      const p = rand(blocks); return { t: 'b', r: p[0], c: p[1] };
    },
    parseEngineMove(s, token) {
      if (s.phase !== 'move' || !token || token.length < 4) return null;
      const fc = token.charCodeAt(0) - 97;
      const fr = Number(token.charAt(1));
      const tc = token.charCodeAt(2) - 97;
      const tr = Number(token.charAt(3));
      const me = s.turn === 1 ? s.p1 : s.p2;
      if (me[0] !== fr || me[1] !== fc) return null;
      const legal = this.moves(s, s.turn).find(v => v[0] === tr && v[1] === tc);
      return legal ? { t: 'm', r: tr, c: tc } : null;
    },
    render(s) {
      topEl.innerHTML = ''; bottomEl.innerHTML = '';
      const moveHints = s.phase === 'move' && s.sel ? this.moves(s, s.turn) : [];
      drawGrid(s.n, s.n, (r, c) => {
        let cls = (r + c) % 2 ? 'dark' : '', txt = '';
        if (s.phase === 'move' && s.sel && s.sel[0] === r && s.sel[1] === c) cls += ' sel';
        if (moveHints.some(v => v[0] === r && v[1] === c)) cls += ' hint';
        if (s.blk[this.key(r, c)]) { cls += ' blocked'; txt = 'X'; }
        else if (s.p1[0] === r && s.p1[1] === c) txt = '🔴';
        else if (s.p2[0] === r && s.p2[1] === c) txt = '🔵';
        return cell(cls, txt, () => {
          if (aiActive() || s.gameOver) return;
          if (s.phase === 'move') {
            const me = s.turn === 1 ? s.p1 : s.p2;
            if (me[0] === r && me[1] === c) { s.sel = [r, c]; render(); return; }
            if (!s.sel) return;
            const ok = this.moves(s, s.turn).some(v => v[0] === r && v[1] === c); if (!ok) return;
            pushUndo(); this.apply(s, { t: 'm', r, c }); render(); aiTurn(); return;
          }
          if (this.occ(s, r, c)) return;
          pushUndo(); this.apply(s, { t: 'b', r, c }); render(); aiTurn();
        });
      }, 72);
      setStatus(s.gameOver ? `${sideName(s.winner)} 승리` : `차례: ${sideName(s.turn)} / ${s.phase === 'move' ? '이동' : '칸 막기'}`);
      setHistory(s.h);
    }
  };

  const ataxx = {
    init() {
      const b = Array.from({ length: 7 }, () => Array(7).fill(0));
      b[0][0] = b[6][6] = 1; b[0][6] = b[6][0] = 2;
      return { b, n: 7, turn: 1, sel: null, gameOver: false, winner: 0, h: [], tokens: [] };
    },
    onNoMove(s) {
      if (s.gameOver) return;
      const cur = this.moves(s, s.turn);
      if (cur.length) return;
      const opp = this.moves(s, other(s.turn));
      if (opp.length) {
        s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} 패스`);
        s.turn = other(s.turn);
        return;
      }
      const [a, b] = this.count(s);
      s.gameOver = true;
      s.winner = a === b ? 0 : (a > b ? 1 : 2);
    },
    moves(s, side) {
      const out = [];
      for (let r = 0; r < s.n; r++) for (let c = 0; c < s.n; c++) if (s.b[r][c] === side) {
        for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++) {
          if (!dr && !dc) continue;
          const nr = r + dr, nc = c + dc, d = Math.max(Math.abs(dr), Math.abs(dc));
          if (nr < 0 || nc < 0 || nr >= s.n || nc >= s.n || s.b[nr][nc] || d < 1 || d > 2) continue;
          out.push({ fr: r, fc: c, tr: nr, tc: nc, d });
        }
      }
      return out;
    },
    count(s) { let a = 0, b = 0; for (const row of s.b) for (const v of row) { if (v === 1) a++; if (v === 2) b++; } return [a, b]; },
    apply(s, m) {
      if (m.d === 1) s.b[m.tr][m.tc] = s.turn; else { s.b[m.tr][m.tc] = s.turn; s.b[m.fr][m.fc] = 0; }
      s.tokens.push(moveToken(m.fr, m.fc, m.tr, m.tc));
      let flip = 0;
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        if (!dr && !dc) continue;
        const r = m.tr + dr, c = m.tc + dc;
        if (s.b[r] && s.b[r][c] === other(s.turn)) { s.b[r][c] = s.turn; flip++; }
      }
      s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} flip ${flip}`);
      s.turn = other(s.turn);
      if (!this.moves(s, s.turn).length && !this.moves(s, other(s.turn)).length) {
        const [a, b] = this.count(s); s.gameOver = true; s.winner = a === b ? 0 : (a > b ? 1 : 2);
      }
    },
    parseEngineMove(s, token) {
      if (!token || token.length < 4) return null;
      const fc = token.charCodeAt(0) - 97, fr = Number(token.charAt(1));
      const tc = token.charCodeAt(2) - 97, tr = Number(token.charAt(3));
      return this.moves(s, s.turn).find(m => m.fr === fr && m.fc === fc && m.tr === tr && m.tc === tc) || null;
    },
    ai(s) {
      const ms = this.moves(s, s.turn); if (!ms.length) return null;
      if (LEVEL === 'easy') return rand(ms);
      let best = ms[0], score = -1e9;
      for (const m of ms) {
        const t = copy(s); this.apply(t, m);
        const [a, b] = this.count(t), v = s.turn === 1 ? a - b : b - a;
        if (v > score) { score = v; best = m; }
      }
      return best;
    },
    render(s) {
      topEl.innerHTML = ''; bottomEl.innerHTML = '';
      const moveHints = s.sel ? this.moves(s, s.turn).filter(v => v.fr === s.sel[0] && v.fc === s.sel[1]) : [];
      drawGrid(7, 7, (r, c) => {
        let cls = (r + c) % 2 ? 'dark' : '';
        if (s.sel && s.sel[0] === r && s.sel[1] === c) cls += ' sel';
        if (moveHints.some(v => v.tr === r && v.tc === c)) cls += ' hint';
        return cell(cls, s.b[r][c] === 1 ? '🔴' : (s.b[r][c] === 2 ? '🔵' : ''), () => {
          if (aiActive() || s.gameOver) return;
          if (!s.sel) { if (s.b[r][c] === s.turn) s.sel = [r, c]; render(); return; }
          if (s.b[r][c] === s.turn) { s.sel = [r, c]; render(); return; }
          const m = this.moves(s, s.turn).find(v => v.fr === s.sel[0] && v.fc === s.sel[1] && v.tr === r && v.tc === c);
          if (!m) return;
          pushUndo(); this.apply(s, m); s.sel = null; render(); aiTurn();
        });
      }, 72);
      const [a, b] = this.count(s);
      setStatus(s.gameOver ? (s.winner ? `${sideName(s.winner)} 승리` : '무승부') : `차례: ${sideName(s.turn)} / 점수 ${a}:${b}`);
      setHistory(s.h);
    }
  };

  const breakthrough = {
    init() {
      const b = Array.from({ length: 8 }, () => Array(8).fill(0));
      for (let c = 0; c < 8; c++) { b[0][c] = b[1][c] = 2; b[6][c] = b[7][c] = 1; }
      return { b, turn: 1, sel: null, gameOver: false, winner: 0, h: [], tokens: [] };
    },
    onNoMove(s) {
      if (s.gameOver) return;
      if (!this.moves(s, s.turn).length) {
        s.gameOver = true;
        s.winner = other(s.turn);
      }
    },
    moves(s, side) {
      const d = side === 1 ? -1 : 1, out = [];
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) if (s.b[r][c] === side) {
        const nr = r + d; if (nr < 0 || nr > 7) continue;
        if (!s.b[nr][c]) out.push({ fr: r, fc: c, tr: nr, tc: c });
        if (c > 0 && s.b[nr][c - 1] === other(side)) out.push({ fr: r, fc: c, tr: nr, tc: c - 1 });
        if (c < 7 && s.b[nr][c + 1] === other(side)) out.push({ fr: r, fc: c, tr: nr, tc: c + 1 });
      }
      return out;
    },
    apply(s, m) {
      s.b[m.tr][m.tc] = s.turn; s.b[m.fr][m.fc] = 0;
      s.tokens.push(moveToken(m.fr, m.fc, m.tr, m.tc));
      s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} 이동`);
      if ((s.turn === 1 && m.tr === 0) || (s.turn === 2 && m.tr === 7)) { s.gameOver = true; s.winner = s.turn; return; }
      s.turn = other(s.turn); if (!this.moves(s, s.turn).length) { s.gameOver = true; s.winner = other(s.turn); }
    },
    parseEngineMove(s, token) {
      if (!token || token.length < 4) return null;
      const fc = token.charCodeAt(0) - 97, fr = Number(token.charAt(1));
      const tc = token.charCodeAt(2) - 97, tr = Number(token.charAt(3));
      return this.moves(s, s.turn).find(m => m.fr === fr && m.fc === fc && m.tr === tr && m.tc === tc) || null;
    },
    ai(s) {
      const ms = this.moves(s, s.turn); if (!ms.length) return null;
      if (LEVEL === 'easy') return rand(ms);
      ms.sort((a, b) => (s.turn === 1 ? a.tr - b.tr : b.tr - a.tr));
      return ms[0];
    },
    render(s) {
      topEl.innerHTML = ''; bottomEl.innerHTML = '';
      const moveHints = s.sel ? this.moves(s, s.turn).filter(v => v.fr === s.sel[0] && v.fc === s.sel[1]) : [];
      drawGrid(8, 8, (r, c) => {
        let cls = (r + c) % 2 ? 'dark' : '';
        if (s.sel && s.sel[0] === r && s.sel[1] === c) cls += ' sel';
        if (moveHints.some(v => v.tr === r && v.tc === c)) cls += ' hint';
        return cell(cls, s.b[r][c] === 1 ? '🔴' : (s.b[r][c] === 2 ? '🔵' : ''), () => {
          if (aiActive() || s.gameOver) return;
          if (!s.sel) { if (s.b[r][c] === s.turn) s.sel = [r, c]; render(); return; }
          if (s.b[r][c] === s.turn) { s.sel = [r, c]; render(); return; }
          const m = this.moves(s, s.turn).find(v => v.fr === s.sel[0] && v.fc === s.sel[1] && v.tr === r && v.tc === c);
          if (!m) return;
          pushUndo(); this.apply(s, m); s.sel = null; render(); aiTurn();
        });
      }, 64);
      setStatus(s.gameOver ? `${sideName(s.winner)} 승리` : `차례: ${sideName(s.turn)}`);
      setHistory(s.h);
    }
  };

  const dobutsu = {
    init() {
      const b = Array.from({ length: 4 }, () => Array(3).fill(null));
      b[0][0] = { s: 2, t: 'g' }; b[0][1] = { s: 2, t: 'l' }; b[0][2] = { s: 2, t: 'e' };
      b[1][1] = { s: 2, t: 'c' }; b[2][1] = { s: 1, t: 'c' };
      b[3][0] = { s: 1, t: 'e' }; b[3][1] = { s: 1, t: 'l' }; b[3][2] = { s: 1, t: 'g' };
      return { b, turn: 1, sel: null, hands: { 1: [], 2: [] }, gameOver: false, winner: 0, h: [], tokens: [] };
    },
    onNoMove(s) {
      if (s.gameOver) return;
      if (!this.moves(s, s.turn).length) {
        s.gameOver = true;
        s.winner = other(s.turn);
      }
    },
    icon(p) { return ({ l: '🦁', g: '🦒', e: '🐘', c: '🐥', h: '🐔' })[p.t] || '?'; },
    inb(r, c) { return r >= 0 && c >= 0 && r < 4 && c < 3; },
    vec(p, s) {
      const f = s === 1 ? -1 : 1;
      if (p.t === 'l') return [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
      if (p.t === 'g') return [[-1, 0], [1, 0], [0, -1], [0, 1]];
      if (p.t === 'e') return [[-1, -1], [-1, 1], [1, -1], [1, 1]];
      if (p.t === 'c') return [[f, 0]];
      return [[f, 0], [f, -1], [f, 1], [0, -1], [0, 1], [-f, 0]];
    },
    moves(s, side) {
      const out = [];
      for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) {
        const p = s.b[r][c]; if (!p || p.s !== side) continue;
        for (const [dr, dc] of this.vec(p, side)) {
          const nr = r + dr, nc = c + dc; if (!this.inb(nr, nc)) continue;
          const t = s.b[nr][nc]; if (t && t.s === side) continue;
          out.push({ k: 'm', fr: r, fc: c, tr: nr, tc: nc });
        }
      }
      const h = s.hands[side];
      for (let i = 0; i < h.length; i++) for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) if (!s.b[r][c]) out.push({ k: 'd', i, t: h[i], tr: r, tc: c });
      return out;
    },
    apply(s, m) {
      if (m.k === 'd') {
        if (s.b[m.tr][m.tc]) return;
        const t = s.hands[s.turn].splice(m.i, 1)[0]; if (!t) return;
        s.b[m.tr][m.tc] = { s: s.turn, t }; s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} 드롭`); s.turn = other(s.turn); return;
      }
      const p = s.b[m.fr][m.fc]; if (!p || p.s !== s.turn) return;
      s.tokens.push(moveToken(m.fr, m.fc, m.tr, m.tc));
      const cap = s.b[m.tr][m.tc];
      if (cap && cap.t === 'l') { s.gameOver = true; s.winner = s.turn; }
      if (cap && cap.t !== 'l') s.hands[s.turn].push(cap.t === 'h' ? 'c' : cap.t);
      s.b[m.tr][m.tc] = p; s.b[m.fr][m.fc] = null;
      if (p.t === 'c' && ((p.s === 1 && m.tr === 0) || (p.s === 2 && m.tr === 3))) p.t = 'h';
      s.h.push(`${s.h.length + 1}. ${sideName(s.turn)} 이동`);
      if (!s.gameOver) s.turn = other(s.turn);
    },
    ai(s) {
      const ms = this.moves(s, s.turn); if (!ms.length) return null;
      for (const m of ms) if (m.k === 'm' && s.b[m.tr][m.tc] && s.b[m.tr][m.tc].t === 'l') return m;
      return LEVEL === 'easy' ? rand(ms) : ms[0];
    },
    parseEngineMove(s, token) {
      if (!token || token.length < 4) return null;
      const fc = token.charCodeAt(0) - 97, fr = Number(token.charAt(1));
      const tc = token.charCodeAt(2) - 97, tr = Number(token.charAt(3));
      return this.moves(s, s.turn).find(m => m.k === 'm' && m.fr === fr && m.fc === fc && m.tr === tr && m.tc === tc) || null;
    },
    drawHands(s) {
      const draw = (side, target) => {
        target.innerHTML = '';
        const title = document.createElement('p'); title.className = 'text-sm font-bold text-gray-600 mb-1'; title.textContent = `${sideName(side)} 손패`; target.appendChild(title);
        const wrap = document.createElement('div'); wrap.className = 'fg-hand';
        const arr = s.hands[side];
        if (!arr.length) wrap.innerHTML = "<span class='text-sm text-gray-500'>손패 없음</span>";
        arr.forEach((it, idx) => {
          const b = document.createElement('button'); b.type = 'button';
          b.innerHTML = pieceHtml(side, this.icon({ t: it }), true);
          if (handPick && handPick.side === side && handPick.idx === idx) b.classList.add('sel');
          b.addEventListener('click', () => { if (aiActive() || s.turn !== side) return; handPick = { side, idx, t: it }; s.sel = null; render(); });
          wrap.appendChild(b);
        });
        target.appendChild(wrap);
      };
      draw(2, topEl); draw(1, bottomEl);
    },
    render(s) {
      this.drawHands(s);
      const moveHints = s.sel ? this.moves(s, s.turn).filter(v => v.k === 'm' && v.fr === s.sel[0] && v.fc === s.sel[1]) : [];
      drawGrid(4, 3, (r, c) => {
        const p = s.b[r][c];
        let cls = (r + c) % 2 ? 'dark' : '';
        if (s.sel && s.sel[0] === r && s.sel[1] === c) cls += ' sel';
        if (moveHints.some(v => v.tr === r && v.tc === c)) cls += ' hint';
        return cell(cls, p ? pieceHtml(p.s, this.icon(p), true) : '', () => {
          if (aiActive() || s.gameOver) return;
          if (handPick && handPick.side === s.turn && !p) { pushUndo(); this.apply(s, { k: 'd', i: handPick.idx, t: handPick.t, tr: r, tc: c }); handPick = null; render(); aiTurn(); return; }
          if (!s.sel) { if (p && p.s === s.turn) s.sel = [r, c]; render(); return; }
          if (p && p.s === s.turn) { s.sel = [r, c]; render(); return; }
          const m = this.moves(s, s.turn).find(v => v.k === 'm' && v.fr === s.sel[0] && v.fc === s.sel[1] && v.tr === r && v.tc === c);
          if (!m) return;
          pushUndo(); this.apply(s, m); s.sel = null; render(); aiTurn();
        });
      }, 90);
      setStatus(s.gameOver ? `${sideName(s.winner)} 승리` : `차례: ${sideName(s.turn)}`);
      setHistory(s.h);
    }
  };

  const games = { cfour, isolation, ataxx, breakthrough, dobutsu };

  function render() {
    game.render(state);
    setTurnIndicator(state);
    maybeShowResult();
  }

  function ensureTurnPlayable() {
    if (!state || state.gameOver) return false;
    if (typeof game.moves !== 'function' || typeof game.onNoMove !== 'function') return false;
    const legal = game.moves(state, state.turn);
    if (legal && legal.length) return false;
    game.onNoMove(state);
    render();
    return true;
  }

  function aiTurn() {
    // 로컬 2인 대결 전용: AI 비활성
    return;
  }

  function init() {
    game = games[VARIANT] || cfour;
    applyVariantUi();
    state = game.init();
    undoStack = [];
    handPick = null;
    resultShown = false;
    setResultModal(false);

    render();
    aiTurn();
  }

  if (flipBtn) {
    flipBtn.addEventListener('click', function () {
      setBoardFlip(!boardFlipped);
    });
  }
  if (openRulesBtn) openRulesBtn.addEventListener('click', function () { setRulesModal(true); });
  if (rulesCloseBtn) rulesCloseBtn.addEventListener('click', function () { setRulesModal(false); });
  if (resultCloseBtn) resultCloseBtn.addEventListener('click', function () { setResultModal(false); });
  if (resultRestartBtn) resultRestartBtn.addEventListener('click', function () { init(); });

  if (resultModalEl) {
    resultModalEl.addEventListener('click', function (e) {
      if (e.target === resultModalEl) setResultModal(false);
    });
  }
  if (rulesModalEl) {
    rulesModalEl.addEventListener('click', function (e) {
      if (e.target === rulesModalEl) setRulesModal(false);
    });
  }

  resetBtn.addEventListener('click', init);
  undoBtn.addEventListener('click', popUndo);
  init();
})();
