"use strict";
/* Точка входа: смена профессии (ссылка из чата) или игровой хаб */
function hub() {
  reset(); showBar(false); setBack(null); setTitle("🕹 Игры", "Выбирай и играй");
  pill.textContent = ""; pill.style.visibility = "hidden";
  const m = el("div", "menu");
  const add = (ic, title, sub, fn) => { const b = el("button", "card", "<div class='ic'>" + ic + "</div><div><b>" + title + "</b><span>" + sub + "</span></div>"); b.onclick = fn; m.appendChild(b); };
  add("🎩", "Монополия", "Против 1–3 ботов: покупай, строй, разоряй", () => openGame(startMonopoly));
  add("🔢", "2048", "Двигай плитки и собери 2048", () => openGame(start2048));
  add("💣", "Сапёр", "Найди все мины на поле 9×9", () => openGame(startMines));
  add("🐍", "Змейка", "Свайпы по экрану, не врежься", () => openGame(startSnake));
  add("💼", "Тренировка профессий", "Мини-игры смен: курьер, врач, пилот…", jobMenu);
  stage.appendChild(m);
}
function openGame(fn) { pill.style.visibility = "visible"; pill.textContent = "0"; setBack(hub); fn(); }
function jobMenu() {
  reset(); showBar(false); setBack(hub); setTitle("💼 Профессии", "Тренировка без награды");
  const m = el("div", "menu");
  Object.keys(JOBS).forEach(k => {
    const j = JOBS[k]; const b = el("button", "card", "<div class='ic'>" + j[0].split(" ")[0] + "</div><div><b>" + j[0].split(" ").slice(1).join(" ") + "</b><span>" + j[1] + "</span></div>");
    b.onclick = () => { pill.style.visibility = "visible"; setBack(jobMenu); runJob(k, true); };
    m.appendChild(b);
  });
  stage.appendChild(m);
}
if (sid === "hub" || (demo && q.get("hub") !== null)) hub();
else if (q.get("game")) { const g = { mono: startMonopoly, g2048: start2048, mines: startMines, snake: startSnake }[q.get("game")]; if (g) openGame(g); else hub(); }
else runJob(sid.slice(0, 3));
