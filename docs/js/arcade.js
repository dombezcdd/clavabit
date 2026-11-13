"use strict";
/* Аркады хаба: 2048, Сапёр, Змейка (награды нет, просто игры) */

/* общие свайпы по элементу */
function swipes(node, onDir) {
  let sx = 0, sy = 0, on = false;
  node.addEventListener("pointerdown", e => { sx = e.clientX; sy = e.clientY; on = true; });
  node.addEventListener("pointerup", e => {
    if (!on) return; on = false;
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return;
    onDir(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "R" : "L") : (dy > 0 ? "D" : "U"));
  });
}
function endCard(title, sub, again) {
  const box = el("div", "center");
  box.style.background = "#1b1530d9"; box.style.zIndex = 5;
  box.innerHTML = "<div class='big' style='font-size:44px'>" + title + "</div><div class='sub'>" + sub + "</div>";
  const b = el("button", "btn", "🔁 Ещё раз"); b.onclick = again; box.appendChild(b);
  stage.appendChild(box);
}

/* ===== 2048 ===== */
function start2048() {
  reset(); showBar(false); setTitle("🔢 2048", "Свайпай, чтобы двигать плитки");
  const N = 4; let g, score = 0, best = Number(localStorage.getItem("best2048") || 0), over = false;
  const wrap = el("div", "center"); wrap.style.padding = "8px";
  const board = el("div"); board.style.cssText = "display:grid;grid-template-columns:repeat(4,1fr);gap:8px;width:min(92%,420px);aspect-ratio:1;background:#00000040;padding:8px;border-radius:16px;touch-action:none";
  wrap.appendChild(board); stage.appendChild(wrap);
  const colors = { 0: "#ffffff10", 2: "#eee4da", 4: "#ede0c8", 8: "#f2b179", 16: "#f59563", 32: "#f67c5f", 64: "#f65e3b", 128: "#edcf72", 256: "#edcc61", 512: "#edc850", 1024: "#edc53f", 2048: "#edc22e" };
  function add() { const free = []; for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) if (!g[r][c]) free.push([r, c]); if (!free.length) return; const [r, c] = pick(free); g[r][c] = Math.random() < 0.9 ? 2 : 4; }
  function draw() {
    board.innerHTML = "";
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const v = g[r][c]; const t = el("div", "", v || "");
      t.style.cssText = "display:flex;align-items:center;justify-content:center;border-radius:10px;font-weight:800;font-size:" + (v >= 1024 ? 20 : v >= 128 ? 24 : 30) + "px;background:" + (colors[v] || "#3c3a32") + ";color:" + (v <= 4 ? "#776e65" : "#fff");
      board.appendChild(t);
    }
    pill.textContent = score; hint.textContent = "Рекорд: " + best;
  }
  function slide(row) { const a = row.filter(x => x); for (let i = 0; i < a.length - 1; i++) if (a[i] === a[i + 1]) { a[i] *= 2; score += a[i]; a.splice(i + 1, 1); } while (a.length < N) a.push(0); return a; }
  function move(d) {
    if (over) return;
    const old = JSON.stringify(g);
    const get = (i, j) => d === "L" ? g[i][j] : d === "R" ? g[i][N - 1 - j] : d === "U" ? g[j][i] : g[N - 1 - j][i];
    const set = (i, j, v) => { if (d === "L") g[i][j] = v; else if (d === "R") g[i][N - 1 - j] = v; else if (d === "U") g[j][i] = v; else g[N - 1 - j][i] = v; };
    for (let i = 0; i < N; i++) { const row = []; for (let j = 0; j < N; j++) row.push(get(i, j)); const s = slide(row); for (let j = 0; j < N; j++) set(i, j, s[j]); }
    if (JSON.stringify(g) === old) return;
    haptic("success"); add(); best = Math.max(best, score); try { localStorage.setItem("best2048", best); } catch (e) {} draw();
    if (!canMove()) { over = true; endCard("Конец игры", "Счёт: " + score, start2048); }
  }
  function canMove() { for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) { if (!g[r][c]) return true; if (c < N - 1 && g[r][c] === g[r][c + 1]) return true; if (r < N - 1 && g[r][c] === g[r + 1][c]) return true; } return false; }
  g = Array.from({ length: N }, () => Array(N).fill(0)); add(); add(); draw();
  swipes(wrap, move);
  const key = e => { const m = { ArrowLeft: "L", ArrowRight: "R", ArrowUp: "U", ArrowDown: "D" }[e.key]; if (m) { e.preventDefault(); move(m); } };
  document.addEventListener("keydown", key); cleanup = () => document.removeEventListener("keydown", key);
  window.__g2048 = { move, grid: () => g, score: () => score };
}

/* ===== Сапёр ===== */
function startMines() {
  reset(); showBar(false); setTitle("💣 Сапёр", "Тап: открыть · режим 🚩: флажок");
  const W = 9, H = 9, M = 10; let cells, opened, over, flagMode = false, first = true, flags = 0;
  const wrap = el("div", "center"); wrap.style.cssText += ";gap:10px;padding:8px";
  const board = el("div"); board.style.cssText = "display:grid;grid-template-columns:repeat(9,1fr);gap:3px;width:min(94%,420px);aspect-ratio:1";
  const tools = el("div", "row"); const fb = el("button", "btn sec sm", "🚩 Флажок: выкл"); fb.onclick = () => { flagMode = !flagMode; fb.textContent = "🚩 Флажок: " + (flagMode ? "вкл" : "выкл"); };
  const nb = el("button", "btn sec sm", "🔁 Заново"); nb.onclick = startMines; tools.append(fb, nb);
  wrap.append(board, tools); stage.appendChild(wrap);
  cells = Array.from({ length: H * W }, () => ({ mine: false, open: false, flag: false, n: 0 })); opened = 0; over = false;
  const nbrs = i => { const r = Math.floor(i / W), c = i % W, out = []; for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) { if (!dr && !dc) continue; const rr = r + dr, cc = c + dc; if (rr >= 0 && rr < H && cc >= 0 && cc < W) out.push(rr * W + cc); } return out; };
  function plant(safe) {
    const ban = new Set([safe, ...nbrs(safe)]); let k = 0;
    while (k < M) { const i = irnd(0, H * W - 1); if (ban.has(i) || cells[i].mine) continue; cells[i].mine = true; k++; }
    cells.forEach((c, i) => { c.n = nbrs(i).filter(j => cells[j].mine).length; });
  }
  const cols = ["", "#6cb6ff", "#4cd98a", "#ff6b6b", "#b48cff", "#ffb84d", "#4ce0d9", "#fff", "#aaa"];
  function draw() {
    board.innerHTML = "";
    cells.forEach((c, i) => {
      const b = el("button", "", c.flag ? "🚩" : c.open ? (c.mine ? "💥" : (c.n || "")) : (over && c.mine ? "💣" : ""));
      b.style.cssText = "border:0;border-radius:7px;font-weight:800;font-size:17px;cursor:pointer;padding:0;color:" + (cols[c.n] || "#fff") + ";background:" + (c.open ? "#ffffff0d" : "#ffffff30");
      b.onclick = () => tap(i); board.appendChild(b);
    });
    pill.textContent = "💣 " + (M - flags);
  }
  function openCell(i) {
    const st = [i];
    while (st.length) { const k = st.pop(), c = cells[k]; if (c.open || c.flag) continue; c.open = true; opened++; if (c.n === 0 && !c.mine) nbrs(k).forEach(j => st.push(j)); }
  }
  function tap(i) {
    if (over) return; const c = cells[i];
    if (flagMode) { if (!c.open) { c.flag = !c.flag; flags += c.flag ? 1 : -1; haptic("success"); } draw(); return; }
    if (c.flag || c.open) return;
    if (first) { plant(i); first = false; }
    if (c.mine) { over = true; cells.forEach(x => { if (x.mine) x.open = true; }); haptic("error"); draw(); setTimeout(() => endCard("💥 Бабах!", "Попробуй ещё раз", startMines), 700); return; }
    openCell(i); draw();
    if (opened === H * W - M) { over = true; haptic("success"); setTimeout(() => endCard("🏆 Победа!", "Все мины найдены", startMines), 300); }
  }
  draw();
  window.__mines = { tap, cells: () => cells, over: () => over, opened: () => opened, total: H * W - M };
}

/* ===== Змейка ===== */
function startSnake() {
  reset(); showBar(false); setTitle("🐍 Змейка", "Свайпай по полю");
  const cv = el("canvas"); stage.appendChild(cv); const ctx = cv.getContext("2d");
  const N = 16; let snake, dir, nd, food, score, alive = true, timer = 0, W = 0, cell = 0, ox = 0, oy = 0;
  function size() { const r = stage.getBoundingClientRect(); cv.width = r.width * devicePixelRatio; cv.height = r.height * devicePixelRatio; W = Math.min(cv.width, cv.height) * 0.94; cell = W / N; ox = (cv.width - W) / 2; oy = (cv.height - W) / 2; }
  size(); addEventListener("resize", size);
  function put() { do { food = [irnd(0, N - 1), irnd(0, N - 1)]; } while (snake.some(s => s[0] === food[0] && s[1] === food[1])); }
  snake = [[8, 8], [7, 8], [6, 8]]; dir = "R"; nd = "R"; score = 0; put(); pill.textContent = 0;
  const opp = { L: "R", R: "L", U: "D", D: "U" };
  const turn = d => { if (d !== opp[dir]) nd = d; };
  swipes(cv, turn);
  const key = e => { const m = { ArrowLeft: "L", ArrowRight: "R", ArrowUp: "U", ArrowDown: "D" }[e.key]; if (m) { e.preventDefault(); turn(m); } };
  document.addEventListener("keydown", key);
  function step() {
    dir = nd; const h = snake[0], d = { L: [-1, 0], R: [1, 0], U: [0, -1], D: [0, 1] }[dir]; const n = [h[0] + d[0], h[1] + d[1]];
    if (n[0] < 0 || n[1] < 0 || n[0] >= N || n[1] >= N || snake.some(s => s[0] === n[0] && s[1] === n[1])) { alive = false; clearInterval(timer); haptic("error"); endCard("Игра окончена", "Счёт: " + score, startSnake); return; }
    snake.unshift(n);
    if (n[0] === food[0] && n[1] === food[1]) { score++; pill.textContent = score; haptic("success"); put(); if (timer) { clearInterval(timer); timer = setInterval(step, Math.max(70, 150 - score * 3) / FAST); } } else snake.pop();
    draw();
  }
  function draw() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = "#0000003a"; ctx.fillRect(ox, oy, W, W);
    ctx.fillStyle = "#ff6b6b"; ctx.beginPath(); ctx.arc(ox + (food[0] + .5) * cell, oy + (food[1] + .5) * cell, cell * .38, 0, 7); ctx.fill();
    snake.forEach((s, i) => { ctx.fillStyle = i ? "#4cd98a" : "#9dffc4"; ctx.fillRect(ox + s[0] * cell + 1, oy + s[1] * cell + 1, cell - 2, cell - 2); });
  }
  draw(); timer = setInterval(step, 150 / FAST);
  cleanup = () => { clearInterval(timer); document.removeEventListener("keydown", key); removeEventListener("resize", size); };
  window.__snake = { turn, alive: () => alive, score: () => score };
}
