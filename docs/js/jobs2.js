"use strict";
/* Новые профессии: рыбак, повар, сварщик, машинист, стюардесса */
Object.assign(JOBS, {
  ryb: ["🎣 Рыбак", "Жди поклёвку и подсекай вовремя", fisher],
  pov: ["🍳 Повар", "Запомни рецепт и собери блюдо по порядку", cook],
  sva: ["🔥 Сварщик", "Ставь точки шва точно в зелёную зону", welder],
  mas: ["🚆 Машинист", "Держи тормоз и остановись у платформы", driver],
  stu: ["🛎 Стюардесса", "Подай пассажирам именно то, что они просят", stewardess]
});

/* ===== рыбак ===== */
function fisher(done) {
  const N = 5; let i = 0, total = 0, timer = 0, raf = 0, bite = 0, state = "idle";
  const box = el("div", "center"); stage.appendChild(box);
  const msg = el("div", "big", "🎣"), sub = el("div", "sub", "");
  const btn = el("button", "btn", "Подсечь!"); box.append(msg, sub, btn);
  function next() {
    if (i >= N) return done(Math.round(total / N));
    hint.textContent = "Поклёвка " + (i + 1) + " из " + N; setTime(1 - i / N);
    state = "wait"; msg.textContent = "🌊"; sub.textContent = "Жди поклёвку… не торопись";
    timer = setTimeout(() => { state = "bite"; bite = performance.now(); msg.textContent = "🐟❗"; sub.textContent = "КЛЮЁТ! Жми!"; haptic("warning");
      timer = setTimeout(() => finish(0, "Рыба ушла…"), 1100 / FAST); }, rnd(1300, 3600) / FAST);
  }
  function finish(pts, text) {
    clearTimeout(timer); state = "idle"; total += pts; pill.textContent = Math.round(total / N);
    msg.textContent = pts > 0 ? "🐠" : "💨"; sub.textContent = text; i++; setTimeout(next, 900 / FAST);
  }
  btn.onclick = () => {
    if (state === "wait") return finish(0, "Спугнул рыбу! Подожди клёва");
    if (state === "bite") { const ms = (performance.now() - bite) * FAST; const pts = ms < 350 ? 100 : ms < 700 ? 75 : 45; haptic("success"); finish(pts, "Поймал! " + Math.round(ms) + " мс"); }
  };
  cleanup = () => { clearTimeout(timer); };
  next();
}

/* ===== повар ===== */
function cook(done) {
  const FOOD = ["🍅", "🧅", "🥕", "🧀", "🥚", "🍄", "🌶", "🥩", "🐟", "🥔"];
  const plan = [3, 3, 4, 5]; let r = 0, total = 0, box;
  function round() {
    if (r >= plan.length) return done(Math.round(total / plan.length));
    hint.textContent = "Блюдо " + (r + 1) + " из " + plan.length; setTime(1 - r / plan.length);
    stage.innerHTML = ""; box = el("div", "q"); stage.appendChild(box);
    const n = plan[r], recipe = shuffle(FOOD).slice(0, n);
    const p = el("div", "prompt", "Запомни порядок: <br><span style='font-size:34px'>" + recipe.join(" → ") + "</span>"); box.appendChild(p);
    setTimeout(() => ask(recipe), (1400 + 700 * n) / FAST);
  }
  function ask(recipe) {
    box.innerHTML = ""; let pos = 0, ok = 0, lock = false;
    const p = el("div", "prompt", "Собирай по порядку! Шаг 1 из " + recipe.length), g = el("div", "opts g2");
    shuffle(recipe.concat(shuffle(FOOD.filter(x => !recipe.includes(x))).slice(0, 8 - recipe.length))).forEach(f => {
      const b = el("button", "opt", f);
      b.onclick = () => {
        if (lock) return;
        if (f === recipe[pos]) { b.classList.add("ok"); ok++; haptic("success"); } else { b.classList.add("bad"); haptic("error"); }
        pos++; b.disabled = true; p.textContent = pos < recipe.length ? "Шаг " + (pos + 1) + " из " + recipe.length : "Готово!";
        if (pos >= recipe.length) { lock = true; total += ok / recipe.length * 100; pill.textContent = Math.round(total / plan.length); r++; setTimeout(round, 800 / FAST); }
      };
      g.appendChild(b);
    });
    box.append(p, g);
  }
  round();
}

/* ===== сварщик ===== */
function welder(done) {
  const N = 6; let i = 0, total = 0, pos = 0, dir = 1, speed = 70, zone = 0, zw = 22, raf = 0, last = performance.now(), lock = false, hist = [];
  const box = el("div", "q"); stage.appendChild(box);
  const track = el("div", "weld"); track.style.cssText = "position:relative;height:46px;background:#2a2540;border-radius:12px;margin:26px 0;overflow:hidden";
  const zdiv = el("div"); zdiv.style.cssText = "position:absolute;top:0;bottom:0;background:#2ecc71;opacity:.75";
  const mk = el("div"); mk.style.cssText = "position:absolute;top:-2px;bottom:-2px;width:8px;background:#ffd166;border-radius:4px;box-shadow:0 0 12px #ffd166";
  track.append(zdiv, mk);
  const seam = el("div", "sub", ""), btn = el("button", "btn", "🔥 Варить!");
  box.append(el("div", "prompt", "Жми, когда искра в зелёной зоне"), track, seam, btn);
  function newZone() { zw = Math.max(9, 22 - i * 2.4); zone = rnd(8, 92 - zw); zdiv.style.left = zone + "%"; zdiv.style.width = zw + "%"; speed = 62 + i * 14; lock = false;
    hint.textContent = "Шов " + (i + 1) + " из " + N; setTime(1 - i / N); }
  function loop(now) { const dt = Math.min(0.05, (now - last) / 1000) * FAST; last = now;
    pos += dir * speed * dt; if (pos > 100) { pos = 100; dir = -1; } if (pos < 0) { pos = 0; dir = 1; } mk.style.left = pos + "%";
    hist.push([now, pos]); if (hist.length > 30) hist.shift(); raf = requestAnimationFrame(loop); }
  /* позиция искры в момент самого нажатия (а не момента, когда браузер дошёл до обработчика) */
  function posAt(t) { for (let k = hist.length - 1; k >= 0; k--) if (hist[k][0] <= t) return hist[k][1]; return pos; }
  btn.style.touchAction = "manipulation";
  btn.onpointerdown = (ev) => {
    ev.preventDefault();
    if (lock) return; lock = true;
    const p0 = posAt(ev.timeStamp || performance.now());
    const c = zone + zw / 2, d = Math.abs(p0 - c), pts = d <= zw / 2 ? 100 - d / (zw / 2) * 25 : Math.max(0, 55 - (d - zw / 2) * 3);
    total += pts; pill.textContent = Math.round(total / N); seam.textContent = pts > 70 ? "Ровный шов! ✨" : pts > 30 ? "Сойдёт…" : "Непровар 😬";
    haptic(pts > 50 ? "success" : "error"); i++;
    if (i >= N) { cancelAnimationFrame(raf); return setTimeout(() => done(Math.round(total / N)), 600 / FAST); }
    setTimeout(newZone, 600 / FAST);
  };
  cleanup = () => cancelAnimationFrame(raf);
  newZone(); raf = requestAnimationFrame(loop);
}

/* ===== машинист ===== */
function driver(done) {
  const N = 3; let i = 0, total = 0, x = 0, v = 0, brake = false, raf = 0, last = performance.now(), zs = 0, ze = 0, over = false;
  const box = el("div", "q"); stage.appendChild(box);
  const rail = el("div"); rail.style.cssText = "position:relative;height:70px;background:#2a2540;border-radius:12px;margin:24px 0;overflow:hidden";
  const plat = el("div"); plat.style.cssText = "position:absolute;top:0;bottom:0;background:#2ecc71;opacity:.8";
  const tr = el("div", "", "🚆"); tr.style.cssText = "position:absolute;top:12px;font-size:36px;transform:translateX(-100%)";
  rail.append(plat, tr);
  const info = el("div", "sub", ""), btn = el("button", "btn", "🛑 Держи тормоз");
  box.append(el("div", "prompt", "Зажми тормоз и остановись на платформе"), rail, info, btn);
  function start() { x = 0; v = 40 + i * 6; zs = rnd(62, 74); ze = zs + 16 - i * 2; plat.style.left = zs + "%"; plat.style.width = (ze - zs) + "%"; over = false;
    hint.textContent = "Станция " + (i + 1) + " из " + N; setTime(1 - i / N); info.textContent = "Скорость " + Math.round(v); }
  function loop(now) {
    const dt = Math.min(0.05, (now - last) / 1000) * FAST; last = now;
    if (!over) { v = Math.max(0, v - (brake ? 26 : 2.2) * dt); x += v * dt; tr.style.left = Math.min(x, 104) + "%"; info.textContent = "Скорость " + Math.round(v);
      if (v <= 0.3 && x > 3 || x > 100) { over = true; const mid = (zs + ze) / 2, d = Math.abs(x - mid), pts = x > 100 ? 0 : (x >= zs && x <= ze) ? 100 - d * 2 : Math.max(0, 60 - (d - (ze - zs) / 2) * 5);
        total += pts; pill.textContent = Math.round(total / N); info.textContent = pts > 70 ? "Мягкая остановка! ✨" : x > 100 ? "Проскочил станцию! 😱" : "Не дотянул до платформы"; haptic(pts > 50 ? "success" : "error");
        i++; setTimeout(() => { if (i >= N) { cancelAnimationFrame(raf); done(Math.round(total / N)); } else start(); }, 1100 / FAST); } }
    raf = requestAnimationFrame(loop); }
  const on = e => { e.preventDefault(); brake = true; }, offf = () => { brake = false; };
  btn.addEventListener("pointerdown", on); window.addEventListener("pointerup", offf); window.addEventListener("pointercancel", offf);
  cleanup = () => { cancelAnimationFrame(raf); window.removeEventListener("pointerup", offf); window.removeEventListener("pointercancel", offf); };
  start(); raf = requestAnimationFrame(loop);
}

/* ===== стюардесса ===== */
function stewardess(done) {
  const ITEMS = [["🍵", "чай"], ["☕", "кофе"], ["💧", "воду"], ["🧣", "плед"], ["🍪", "печенье"], ["🎧", "наушники"], ["🍱", "обед"], ["🧃", "сок"]];
  const list = [];
  for (let k = 0; k < 8; k++) {
    const two = shuffle(ITEMS).slice(0, 2), seat = irnd(2, 30) + pick(["A", "B", "C", "D", "E", "F"]);
    const right = two[0][0] + " + " + two[1][0], opts = [{ label: right, ok: true }], used = new Set([right]);
    while (opts.length < 4) { const w = shuffle(ITEMS).slice(0, 2), l = w[0][0] + " + " + w[1][0]; if (!used.has(l) && !(w.includes(two[0]) && w.includes(two[1]))) { used.add(l); opts.push({ label: l }); } }
    list.push({ prompt: "✈️ Место " + seat + " просит: " + two[0][1] + " и " + two[1][1], options: opts, cols: 2 });
  }
  rounds(list, 7, done);
}

/* ===== адвокат ===== */
JOBS.adv = ["⚖️ Адвокат", "Выбери самый веский аргумент в защиту", lawyerGame];
function lawyerGame(done) {
  const CASES = [
    ["Свидетель путается в показаниях.", "Указать на противоречия в показаниях", ["Накричать на свидетеля", "Попросить прощения у судьи", "Сменить тему"]],
    ["У клиента есть алиби.", "Предъявить билет и записи камер", ["Сказать «он хороший человек»", "Промолчать", "Обвинить судью"]],
    ["Улики добыты без ордера.", "Потребовать исключить улики из дела", ["Согласиться с обвинением", "Признать вину", "Уйти из зала"]],
    ["Обвинение давит на присяжных.", "Заявить возражение судье", ["Хлопнуть дверью", "Поддакивать прокурору", "Читать газету"]],
    ["Клиент вернул украденное сам.", "Подчеркнуть раскаяние и возврат", ["Скрыть этот факт", "Обвинить потерпевшего", "Попросить увеличить штраф"]],
    ["Нет прямых доказательств вины.", "Напомнить: сомнения толкуются в пользу обвиняемого", ["Признать иск целиком", "Требовать тюрьму для клиента", "Подать иск на судью"]],
    ["Показания свидетеля — слухи.", "Заявить, что слухи не доказательство", ["Принять их как факт", "Назвать их истиной", "Игнорировать суд"]],
    ["Суд задаёт вопрос по существу.", "Ответить кратко и по делу", ["Отшутиться", "Говорить час подряд", "Спросить время обеда"]]
  ];
  rounds(shuffle(CASES).map(c => ({ prompt: "⚖️ " + c[0] + " Что делаешь?", options: [{ label: c[1], ok: true }].concat(c[2].map(l => ({ label: l }))) })), 8, done);
}
