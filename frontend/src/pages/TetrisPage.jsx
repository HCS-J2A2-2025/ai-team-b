import React, { useEffect, useMemo, useRef, useState } from "react";

const COLS = 10;
const ROWS = 20;
const BLOCK = 28;
const DROP_MS_START = 650;

const TYPES = ["I", "O", "T", "S", "Z", "J", "L"];

const SHAPES = {
  I: [
    [
      [0, 0, 0, 0],
      [1, 1, 1, 1],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
    ],
    [
      [0, 0, 1, 0],
      [0, 0, 1, 0],
      [0, 0, 1, 0],
      [0, 0, 1, 0],
    ],
  ],
  O: [[[1, 1], [1, 1]]],
  T: [
    [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    [[0, 1, 0], [0, 1, 1], [0, 1, 0]],
    [[0, 0, 0], [1, 1, 1], [0, 1, 0]],
    [[0, 1, 0], [1, 1, 0], [0, 1, 0]],
  ],
  S: [
    [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    [[0, 1, 0], [0, 1, 1], [0, 0, 1]],
  ],
  Z: [
    [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
    [[0, 0, 1], [0, 1, 1], [0, 1, 0]],
  ],
  J: [
    [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    [[0, 1, 1], [0, 1, 0], [0, 1, 0]],
    [[0, 0, 0], [1, 1, 1], [0, 0, 1]],
    [[0, 1, 0], [0, 1, 0], [1, 1, 0]],
  ],
  L: [
    [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
    [[0, 1, 0], [0, 1, 0], [0, 1, 1]],
    [[0, 0, 0], [1, 1, 1], [1, 0, 0]],
    [[1, 1, 0], [0, 1, 0], [0, 1, 0]],
  ],
};

const COLORS = {
  I: "#6ee7ff",
  O: "#ffe36e",
  T: "#c7a3ff",
  S: "#8cff8c",
  Z: "#ff8c8c",
  J: "#8cb3ff",
  L: "#ffc18c",
  G: "#666666", // お邪魔
};

function emptyBoard() {
  return Array.from({ length: ROWS }, () => Array.from({ length: COLS }, () => null));
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ✅ 7-bag：7種類が必ず1回ずつ → なくなったら再シャッフル
function makeBag() {
  return shuffle(TYPES);
}
function takeFromBag(bag) {
  if (!bag || bag.length === 0) {
    const b = makeBag();
    return { type: b[0], bag: b.slice(1) };
  }
  const [head, ...rest] = bag;
  return { type: head, bag: rest };
}

function pieceFromType(type) {
  const rotations = SHAPES[type];
  const rot = 0;
  const matrix = rotations[rot];
  const x = Math.floor((COLS - matrix[0].length) / 2);
  const y = -1;
  return { type, rot, x, y };
}

function matrixOf(piece) {
  return SHAPES[piece.type][piece.rot];
}

// ✅ 回転：右/左（※ここがあなたのコードで壊れてたので修正）
function rotateRight(piece) {
  const rotations = SHAPES[piece.type];
  return { ...piece, rot: (piece.rot + 1) % rotations.length };
}
function rotateLeft(piece) {
  const rotations = SHAPES[piece.type];
  return { ...piece, rot: (piece.rot - 1 + rotations.length) % rotations.length };
}

function collides(board, piece) {
  const m = matrixOf(piece);
  for (let r = 0; r < m.length; r++) {
    for (let c = 0; c < m[r].length; c++) {
      if (!m[r][c]) continue;
      const bx = piece.x + c;
      const by = piece.y + r;
      if (bx < 0 || bx >= COLS) return true;
      if (by >= ROWS) return true;
      if (by >= 0 && board[by][bx]) return true;
    }
  }
  return false;
}

function merge(board, piece) {
  const next = board.map((row) => row.slice());
  const m = matrixOf(piece);
  for (let r = 0; r < m.length; r++) {
    for (let c = 0; c < m[r].length; c++) {
      if (!m[r][c]) continue;
      const bx = piece.x + c;
      const by = piece.y + r;
      if (by >= 0 && by < ROWS && bx >= 0 && bx < COLS) {
        next[by][bx] = piece.type;
      }
    }
  }
  return next;
}

function clearLinesWithRows(board) {
  const fullRows = [];
  for (let y = 0; y < ROWS; y++) {
    if (board[y].every((cell) => cell !== null)) fullRows.push(y);
  }
  if (fullRows.length === 0) return { board, cleared: 0, rows: [] };

  const next = board.filter((_, y) => !fullRows.includes(y));
  while (next.length < ROWS) next.unshift(Array.from({ length: COLS }, () => null));
  return { board: next, cleared: fullRows.length, rows: fullRows };
}

function tryKick(board, original, rotated) {
  const kicks = [0, -1, 1, -2, 2];
  for (const k of kicks) {
    const test = { ...rotated, x: rotated.x + k };
    if (!collides(board, test)) return test;
  }
  return original;
}

// ✅ T-Spin（簡易）
function isTSpin(board, piece) {
  if (piece.type !== "T") return false;

  const cx = piece.x + 1;
  const cy = piece.y + 1;

  const corners = [
    [cx - 1, cy - 1],
    [cx + 1, cy - 1],
    [cx - 1, cy + 1],
    [cx + 1, cy + 1],
  ];

  let filled = 0;
  for (const [x, y] of corners) {
    if (x < 0 || x >= COLS || y < 0 || y >= ROWS) {
      filled++;
      continue;
    }
    if (board[y][x]) filled++;
  }
  return filled >= 3;
}

// ✅ お邪魔行（下から追加、穴1つ）
function addGarbage(board, n) {
  if (n <= 0) return board;
  let b = board.map((r) => r.slice());
  for (let i = 0; i < n; i++) {
    const hole = Math.floor(Math.random() * COLS);
    const garbage = Array.from({ length: COLS }, (_, x) => (x === hole ? null : "G"));
    b.shift();
    b.push(garbage);
  }
  return b;
}

// 攻撃量
function attackFromClears(cleared, tspin = false) {
  if (cleared < 2) return 0;

  // T-Spinなら強め（お好みで）
  if (tspin) {
    if (cleared === 2) return 3; // T-spin double
    if (cleared === 3) return 5; // T-spin triple
    if (cleared === 1) return 2; // （一応）T-spin single
  }

  if (cleared === 2) return 1;
  if (cleared === 3) return 2;
  if (cleared === 4) return 4;
  return 0;
}

function initPlayerState() {
  const bag0 = makeBag();
  const first = bag0[0];
  const bag1 = bag0.slice(1);
  const pick = takeFromBag(bag1);

  return {
    board: emptyBoard(),
    bag: pick.bag,
    piece: pieceFromType(first),
    nextType: pick.type,
    holdType: null,
    holdUsed: false,

    running: false,
    gameOver: false,

    score: 0,
    lines: 0,
    level: 1,

    flashRows: [],
    flashUntil: 0,

    announce: "",
    announceUntil: 0,

    lastAction: "none",
  };
}

function lineScoreTable(cleared, level) {
  const table = [0, 100, 300, 500, 800];
  return table[cleared] * level;
}

function announceText({ tspin, cleared }) {
  if (cleared <= 0) return "";
  if (tspin) {
    if (cleared === 1) return "T-SPIN SINGLE!";
    if (cleared === 2) return "T-SPIN DOUBLE!";
    if (cleared === 3) return "T-SPIN TRIPLE!";
    return "T-SPIN!";
  }
  if (cleared === 4) return "TETRIS!";
  return `${cleared} LINE!`;
}

// ミニプレビュー（Hold/Next）
function MiniPreview({ type, size = 16, label }) {
  const ref = useRef(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);

    ctx.fillStyle = "rgba(255,255,255,0.06)";
    ctx.fillRect(0, 0, c.width, c.height);

    if (!type) return;

    const rotations = SHAPES[type];
    const m = rotations[0];
    const h = m.length;
    const w = m[0].length;

    const offX = Math.floor((c.width / size - w) / 2);
    const offY = Math.floor((c.height / size - h) / 2);

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (!m[y][x]) continue;
        ctx.fillStyle = COLORS[type] || "#999";
        ctx.fillRect((offX + x) * size, (offY + y) * size, size, size);
        ctx.strokeStyle = "rgba(255,255,255,0.12)";
        ctx.strokeRect((offX + x) * size + 0.5, (offY + y) * size + 0.5, size - 1, size - 1);
      }
    }
  }, [type, size]);

  return (
    <div>
      <div style={{ fontSize: 12, opacity: 0.9, marginBottom: 6 }}>{label}</div>
      <canvas
        ref={ref}
        width={size * 6}
        height={size * 6}
        style={{
          borderRadius: 10,
          border: "1px solid rgba(255,255,255,0.15)",
          background: "#0b1020",
        }}
      />
    </div>
  );
}

export default function TetrisPage() {
  const wrapRef = useRef(null);
  const canvas1 = useRef(null);
  const canvas2 = useRef(null);

  const [p1, setP1] = useState(() => initPlayerState());
  const [p2, setP2] = useState(() => initPlayerState());

  const [isFullscreen, setIsFullscreen] = useState(false);

  const dropMs1 = useMemo(() => Math.max(120, DROP_MS_START - (p1.level - 1) * 55), [p1.level]);
  const dropMs2 = useMemo(() => Math.max(120, DROP_MS_START - (p2.level - 1) * 55), [p2.level]);

  const toggleFullscreen = async () => {
    const el = wrapRef.current;
    if (!el) return;
    try {
      if (!document.fullscreenElement) await el.requestFullscreen();
      else await document.exitFullscreen();
    } catch (e) {
      console.error("Fullscreen error:", e);
    }
  };

  useEffect(() => {
    const onFs = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const startBoth = () => {
    setP1((s) => (s.gameOver ? s : { ...s, running: true }));
    setP2((s) => (s.gameOver ? s : { ...s, running: true }));
  };

  const pauseBoth = () => {
    setP1((s) => ({ ...s, running: false }));
    setP2((s) => ({ ...s, running: false }));
  };

  const resetBoth = () => {
    setP1(initPlayerState());
    setP2(initPlayerState());
  };

  function spawnPlayer(prev) {
    const currentType = prev.nextType;

    const pick = takeFromBag(prev.bag && prev.bag.length ? prev.bag : makeBag());
    const nextPiece = pieceFromType(currentType);

    const next = {
      ...prev,
      piece: nextPiece,
      nextType: pick.type,
      bag: pick.bag,
      holdUsed: false,
      lastAction: "none",
    };

    if (collides(next.board, nextPiece)) {
      return { ...next, running: false, gameOver: true };
    }
    return next;
  }

  function movePlayer(prev, dx) {
    const moved = { ...prev.piece, x: prev.piece.x + dx };
    if (!collides(prev.board, moved)) return { ...prev, piece: moved };
    return prev;
  }

  // ✅ 回転（dir: "R" or "L"）
  function rotPlayer(prev, dir) {
    const rotated = dir === "L" ? rotateLeft(prev.piece) : rotateRight(prev.piece);
    const kicked = tryKick(prev.board, prev.piece, rotated);
    if (!collides(prev.board, kicked)) return { ...prev, piece: kicked, lastAction: "rotate" };
    return prev;
  }

  function softDropPlayer(prev) {
    const moved = { ...prev.piece, y: prev.piece.y + 1 };
    if (!collides(prev.board, moved)) return { ...prev, piece: moved, score: prev.score + 1, lastAction: "none" };
    return lockAndProcess(prev).after;
  }

  function hardDropPlayer(prev, opponentSetter) {
    let p = prev.piece;
    let steps = 0;
    while (!collides(prev.board, { ...p, y: p.y + 1 })) {
      p = { ...p, y: p.y + 1 };
      steps++;
    }
    const mergedPrev = { ...prev, piece: p, score: prev.score + steps };
    const { after, attack } = lockAndProcess(mergedPrev);
    if (attack > 0) queueMicrotask(() => sendAttackToOpponent(attack, opponentSetter));
    return after;
  }

  function holdPlayer(prev) {
    if (!prev.running || prev.gameOver) return prev;
    if (prev.holdUsed) return prev;

    const currentType = prev.piece.type;

    if (!prev.holdType) {
      const next = { ...prev, holdType: currentType, holdUsed: true, lastAction: "none" };
      return spawnPlayer(next);
    }

    const swapped = pieceFromType(prev.holdType);
    const next = { ...prev, holdType: currentType, holdUsed: true, piece: swapped, lastAction: "none" };

    if (collides(next.board, swapped)) {
      return { ...next, running: false, gameOver: true };
    }
    return next;
  }

  function lockAndProcess(prev) {
    const merged = merge(prev.board, prev.piece);
    const { board: clearedBoard, cleared, rows } = clearLinesWithRows(merged);

    const tspin = prev.piece.type === "T" && prev.lastAction === "rotate" && isTSpin(merged, prev.piece);
    const atk = attackFromClears(cleared, tspin);
    const now = Date.now();
    const afterScore =
      cleared > 0
        ? {
            ...prev,
            board: clearedBoard,
            score: prev.score + lineScoreTable(cleared, prev.level),
            lines: prev.lines + cleared,
            level: 1 + Math.floor((prev.lines + cleared) / 10),
            flashRows: rows,
            flashUntil: now + 160,
            announce: announceText({ tspin, cleared }),
            announceUntil: now + 1000,
          }
        : { ...prev, board: clearedBoard };

    return { after: spawnPlayer(afterScore), attack: atk };
  }

  function tickDownPlayer(prev, opponentSetter) {
    const moved = { ...prev.piece, y: prev.piece.y + 1 };
    if (!collides(prev.board, moved)) return { ...prev, piece: moved, lastAction: "none" };

    const { after, attack } = lockAndProcess(prev);
    if (attack > 0) queueMicrotask(() => sendAttackToOpponent(attack, opponentSetter));
    return after;
  }

  function sendAttackToOpponent(attack, targetSetter) {
    if (attack <= 0) return;
    targetSetter((op) => {
      const newBoard = addGarbage(op.board, attack);
      if (collides(newBoard, op.piece)) {
        return { ...op, board: newBoard, running: false, gameOver: true };
      }
      return { ...op, board: newBoard };
    });
  }

  useEffect(() => {
    if (!p1.running || p1.gameOver) return;
    const id = setInterval(() => {
      setP1((prev) => tickDownPlayer(prev, setP2));
    }, dropMs1);
    return () => clearInterval(id);
  }, [p1.running, p1.gameOver, dropMs1]);

  useEffect(() => {
    if (!p2.running || p2.gameOver) return;
    const id = setInterval(() => {
      setP2((prev) => tickDownPlayer(prev, setP1));
    }, dropMs2);
    return () => clearInterval(id);
  }, [p2.running, p2.gameOver, dropMs2]);

  // ======= 入力 =======
  useEffect(() => {
    const onKeyDown = (e) => {
      const preventKeys = ["ArrowLeft", "ArrowRight", "ArrowDown", "ArrowUp", " "];
      if (preventKeys.includes(e.key)) e.preventDefault();

      if (e.key === "Enter") return startBoth();
      if (e.key.toLowerCase() === "p") return pauseBoth();
      if (e.key.toLowerCase() === "") return resetBoth();

      if (e.key.toLowerCase() === "h") return toggleFullscreen();

      // ---- P1（WASD）----
      setP1((prev) => {
        if (!prev.running || prev.gameOver) return prev;
        const k = e.key.toLowerCase();

        if (k === "a") return movePlayer(prev, -1);
        if (k === "d") return movePlayer(prev, 1);
        if (k === "s") return softDropPlayer(prev);

        // ✅ W：右回転 / Shift+W：左回転
        if (k === "w") return rotPlayer(prev, e.shiftKey ? "L" : "R");

        if (k === "q") return holdPlayer(prev);
        if (k === "e") return hardDropPlayer(prev, setP2);

        return prev;
      });

      // ---- P2（矢印）----
      setP2((prev) => {
        if (!prev.running || prev.gameOver) return prev;

        if (e.key === "ArrowLeft") return movePlayer(prev, -1);
        if (e.key === "ArrowRight") return movePlayer(prev, 1);
        if (e.key === "ArrowDown") return softDropPlayer(prev);

        // ✅ ↑：右回転 / Shift+↑：左回転
        if (e.key === "ArrowUp") return rotPlayer(prev, e.shiftKey ? "L" : "R");

        if (e.key === "Shift") return holdPlayer(prev);

        // ✅ 右Ctrlで即落とし（e.code を使う）
        if (e.code === "ControlRight") return hardDropPlayer(prev, setP1);

        return prev;
      });
    };

    window.addEventListener("keydown", onKeyDown, { passive: false });
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ======= 描画 =======
  function draw(canvasRef, state) {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");

    const now = Date.now();
    const flash = state.flashRows.length > 0 && now < state.flashUntil;

    const drawCell = (x, y, type) => {
      const px = x * BLOCK;
      const py = y * BLOCK;

      if (flash && state.flashRows.includes(y)) {
        ctx.fillStyle = "rgba(255,255,255,0.95)";
        ctx.fillRect(px, py, BLOCK, BLOCK);
        ctx.strokeStyle = "rgba(0,0,0,0.15)";
        ctx.strokeRect(px + 0.5, py + 0.5, BLOCK - 1, BLOCK - 1);
        return;
      }

      ctx.fillStyle = type ? (COLORS[type] || "#999") : "#0b1020";
      ctx.fillRect(px, py, BLOCK, BLOCK);
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.strokeRect(px + 0.5, py + 0.5, BLOCK - 1, BLOCK - 1);
    };

    ctx.clearRect(0, 0, COLS * BLOCK, ROWS * BLOCK);

    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) drawCell(x, y, state.board[y][x]);
    }

    const m = matrixOf(state.piece);
    for (let r = 0; r < m.length; r++) {
      for (let cc = 0; cc < m[r].length; cc++) {
        if (!m[r][cc]) continue;
        const x = state.piece.x + cc;
        const y = state.piece.y + r;
        if (y >= 0) drawCell(x, y, state.piece.type);
      }
    }

    if (state.announce && now < state.announceUntil) {
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      ctx.fillRect(0, 0, COLS * BLOCK, ROWS * BLOCK);
      ctx.fillStyle = "white";
      ctx.font = "bold 22px sans-serif";
      const text = state.announce;
      const w = ctx.measureText(text).width;
      ctx.fillText(text, (COLS * BLOCK - w) / 2, (ROWS * BLOCK) / 2);
    }

    if (!state.running && !state.gameOver) {
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(0, 0, COLS * BLOCK, ROWS * BLOCK);
      ctx.fillStyle = "white";
      ctx.font = "bold 18px sans-serif";
      const t = "ENTERで両方START";
      const w = ctx.measureText(t).width;
      ctx.fillText(t, (COLS * BLOCK - w) / 2, 260);
    }

    if (state.gameOver) {
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(0, 0, COLS * BLOCK, ROWS * BLOCK);
      ctx.fillStyle = "white";
      ctx.font = "bold 22px sans-serif";
      const t = "GAME OVER";
      const w = ctx.measureText(t).width;
      ctx.fillText(t, (COLS * BLOCK - w) / 2, 260);
    }
  }

  useEffect(() => {
    draw(canvas1, p1);
  }, [p1]);

  useEffect(() => {
    draw(canvas2, p2);
  }, [p2]);

  const canvasW = COLS * BLOCK;
  const canvasH = ROWS * BLOCK;

  const panelStyle = {
    padding: 14,
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.15)",
    background: isFullscreen ? "rgba(255,255,255,0.06)" : "transparent",
    minWidth: 280,
  };

  return (
    <div
      ref={wrapRef}
      style={{
        minHeight: "100vh",
        padding: 18,
        background: isFullscreen ? "#0b1020" : "transparent",
        color: isFullscreen ? "#e5e7eb" : "inherit",
      }}
    >
      <div style={{ maxWidth: 1500, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <h2 style={{ margin: "0 0 12px" }}>ジョブナビインテリジェンス：Tetris 対戦（7-bag / T-Spin）</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button onClick={startBoth} style={{ padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}>
              Start（両方）
            </button>
            <button onClick={pauseBoth} style={{ padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}>
              Pause（両方）
            </button>
            <button onClick={resetBoth} style={{ padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}>
              Reset（両方）
            </button>
            <button onClick={toggleFullscreen} style={{ padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}>
              {isFullscreen ? "全画面OFF" : "全画面ON"}（H）
            </button>
          </div>
        </div>

        <div style={{ display: "flex", gap: 26, justifyContent: "center", alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* P1 */}
          <div>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>P1（WASD）</div>
            <canvas
              ref={canvas1}
              width={canvasW}
              height={canvasH}
              style={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.15)", background: "#0b1020" }}
            />
            <div style={{ marginTop: 10, ...panelStyle }}>
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
                <MiniPreview type={p1.holdType} label="HOLD" />
                <MiniPreview type={p1.nextType} label="NEXT" />
              </div>
              <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
                <div>Score: <b>{p1.score}</b></div>
                <div>Lines: <b>{p1.lines}</b></div>
                <div>Level: <b>{p1.level}</b></div>
                <div>Speed: <b>{dropMs1}ms</b></div>
              </div>
              <div style={{ marginTop: 10, fontSize: 12, opacity: 0.9, lineHeight: 1.6 }}>
                移動：A/D　ソフト：S<br />
                回転：W（右） / Shift+W（左）<br />
                Hold：Q　即落とし：E
              </div>
            </div>
          </div>

          {/* P2 */}
          <div>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>P2（矢印）</div>
            <canvas
              ref={canvas2}
              width={canvasW}
              height={canvasH}
              style={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.15)", background: "#0b1020" }}
            />
            <div style={{ marginTop: 10, ...panelStyle }}>
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
                <MiniPreview type={p2.holdType} label="HOLD" />
                <MiniPreview type={p2.nextType} label="NEXT" />
              </div>
              <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
                <div>Score: <b>{p2.score}</b></div>
                <div>Lines: <b>{p2.lines}</b></div>
                <div>Level: <b>{p2.level}</b></div>
                <div>Speed: <b>{dropMs2}ms</b></div>
              </div>
              <div style={{ marginTop: 10, fontSize: 12, opacity: 0.9, lineHeight: 1.6 }}>
                移動：←→　ソフト：↓<br />
                回転：↑（右） / Shift+↑（左）<br />
                Hold：Shift　即落とし：右Ctrl
              </div>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 14, fontSize: 12, opacity: 0.85, textAlign: "center", lineHeight: 1.7 }}>
          ✅ 7-bag：7種類が必ず1回ずつ出る → 7個出たら順番を変えてまた7種類が出る<br />
          ✅ ライン消しで攻撃：2消し=1 / 3消し=2 / 4消し=4（お邪魔行）<br />
          ✅ ラインフラッシュエフェクト / T-SPIN・TETRIS文字表示
        </div>
      </div>
    </div>
  );
}
