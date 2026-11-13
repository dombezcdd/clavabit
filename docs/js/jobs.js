"use strict";
/* Игры профессий (смена по кнопке из чата) и тренировка */
const JOBS = {
  kur: ["📦 Курьер", "Развези заказы по адресам", courier],
  uby: ["🧹 Уборщик", "Три пальца по пятнам: оттирай!", cleaner],
  pro: ["🛒 Продавец", "Подай покупателям то, что они просят", seller],
  off: ["🍽 Официант", "Не урони поднос", waiter],
  tax: ["🚕 Таксист", "Лови пассажиров, не врежься", taxi],
  prg: ["💻 Программист", "Найди строку с ошибкой", coder],
  vra: ["🩺 Врач", "Поставь диагноз", doctor],
  pil: ["✈️ Пилот", "Тап вверх, пролетай между башнями", pilot],
  dir: ["💼 Директор", "Прими лучшее решение", director]
};

/* ===== общий движок «быстрых раундов» ===== */
function rounds(list, perRoundSec, done, opts) {
  opts = opts || {};
  let i = 0, total = 0, t0 = 0, raf = 0, lock = false;
  const box = el("div", "q"); stage.appendChild(box);
  function show() {
    if (i >= list.length) { cancelAnimationFrame(raf); return done(Math.round(total / list.length)); }
    const r = list[i]; lock = false;
    box.innerHTML = "";
    const p = el("div", "prompt", r.prompt);
    const o = el("div", "opts " + (r.cols === 2 ? "g2" : ""));
    shuffle(r.options).forEach(op => {
      const b = el("button", "opt" + (r.line ? " line" : ""), op.label);
      b.onclick = () => answer(b, op, o);
      op.node = b; o.appendChild(b);
    });
    box.append(p, o);
    t0 = performance.now(); hint.textContent = "Раунд " + (i + 1) + " из " + list.length;
    cancelAnimationFrame(raf); tick();
  }
  function tick() {
    const left = perRoundSec - ((performance.now() - t0) / 1000) * FAST;
    setTime(left / perRoundSec);
    if (left <= 0 && !lock) { answer(null, null, null); return; }
    raf = requestAnimationFrame(tick);
  }
  function answer(btn, op, wrap) {
    if (lock) return; lock = true; cancelAnimationFrame(raf);
    const left = clamp(perRoundSec - ((performance.now() - t0) / 1000) * FAST, 0, perRoundSec);
    let pts = 0;
    if (op && op.ok) { pts = 60 + 40 * (left / perRoundSec); btn.classList.add("ok"); haptic("success"); }
    else { if (btn) btn.classList.add("bad"); haptic("error"); list[i].options.forEach(x => { if (x.ok && x.node) x.node.classList.add("ok"); }); }
    total += pts; pill.textContent = Math.round(total / list.length);
    i++; setTimeout(show, op ? 650 : 900);
  }
  cleanup = () => { cancelAnimationFrame(raf); };
  show();
}

/* ===== курьер ===== */
function courier(done) {
  const streets = ["Ленина", "Садовая", "Мира", "Речная", "Парковая", "Школьная", "Лесная", "Новая"];
  const list = [];
  for (let k = 0; k < 8; k++) {
    const n = irnd(11, 98), s = new Set([n]);
    const ds = String(n); const cand = [Number(ds[1] + ds[0]), n + 1, n - 1, n + 10, n - 10, n + 11, Number(ds[0] + (9 - Number(ds[1])))];
    shuffle(cand).forEach(c => { if (s.size < 4 && c > 9 && c < 100) s.add(c); });
    while (s.size < 4) s.add(irnd(11, 98));
    list.push({ prompt: "📦 Заказ №" + irnd(100, 999) + "<br>ул. " + pick(streets) + ", дом <b>" + n + "</b>", cols: 2,
      options: [...s].map(v => ({ label: "🏠 " + v, ok: v === n })) });
  }
  hint.textContent = "Нажми на нужный дом, пока не вышло время";
  rounds(list, 5, done);
}
/* ===== продавец ===== */
function seller(done) {
  const items = [["🍎", "яблоки"], ["🥛", "молоко"], ["🍞", "хлеб"], ["🧀", "сыр"], ["🍫", "шоколад"], ["🥕", "морковь"], ["🍌", "бананы"], ["🧃", "сок"], ["🥚", "яйца"], ["🍅", "помидоры"], ["🍪", "печенье"], ["🍉", "арбуз"]];
  const people = ["🧓", "👩", "🧑", "👨", "👧", "🧔"];
  const list = [];
  for (let k = 0; k < 8; k++) {
    const set = shuffle(items).slice(0, 6), want = pick(set);
    list.push({ prompt: pick(people) + " «Здравствуйте, мне " + want[1] + ", пожалуйста!»", cols: 2,
      options: set.map(it => ({ label: "<span style='font-size:30px'>" + it[0] + "</span>", ok: it === want })) });
  }
  rounds(list, 4.5, done);
}
/* ===== врач ===== */
function doctor(done) {
  const cases = [
    ["Температура 38, кашель, насморк", "ОРВИ", ["Перелом руки", "Ожог"]],
    ["Нога опухла после падения, больно наступать", "Ушиб или перелом", ["Изжога", "Грипп"]],
    ["Чихание и сыпь при цветении тополей", "Аллергия", ["Ангина", "Вывих"]],
    ["Боль в горле, трудно глотать, налёт на миндалинах", "Ангина", ["Аллергия", "Ушиб"]],
    ["Тошнота и боль в животе после жирного ужина", "Расстройство желудка", ["Ожог", "Перелом"]],
    ["Покраснение и пузыри после кипятка", "Ожог", ["Ангина", "Аллергия"]],
    ["Красные слезящиеся глаза, зуд, песок в глазах", "Конъюнктивит", ["Вывих", "Изжога"]],
    ["Слабость и головокружение после часа на жаре", "Тепловой удар", ["Перелом", "Ангина"]],
    ["Кашель, жар, ломота во всём теле", "Грипп", ["Ожог", "Изжога"]],
    ["Острая боль в плече после неудачного падения, рука не поднимается", "Вывих", ["Аллергия", "ОРВИ"]]
  ];
  const list = shuffle(cases).slice(0, 7).map(c => ({ prompt: "🧑‍⚕️ Пациент жалуется:<br><b>" + c[0] + "</b>",
    options: shuffle([c[1], ...c[2]]).map(v => ({ label: v, ok: v === c[1] })) }));
  hint.textContent = "Игра, не медицинский совет";
  rounds(list, 9, done);
}
/* ===== программист ===== */
function coder(done) {
  const sn = [
    [["x = 5", "if x = 5:", "    print('ok')"], 1],
    [["let a = [1, 2, 3];", "for (let i = 0; i <= a.length; i++) {", "  console.log(a[i]);", "}"], 1],
    [["def add(a, b):", "    return a - b", "print(add(2, 3))  # ждём 5"], 1],
    [["name = input()", "print('Привет, ' + nme)"], 1],
    [["const s = 'abc';", "s.push('d');", "console.log(s);"], 1],
    [["a = [1, 2, 3]", "print(a[3])  # третий элемент"], 1],
    [["import os", "print(os.getcwdd())"], 1],
    [["for i in range(3)", "    print(i)"], 0],
    [["SELEKT * FROM users", "WHERE name = 'Аня'"], 0]
  ];
  const list = shuffle(sn).slice(0, 7).map(s => ({ line: true, prompt: "🐞 В коде ошибка. Нажми на строку с багом:",
    options: s[0].map((l, idx) => ({ label: l.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/ /g, "&nbsp;"), ok: idx === s[1] })) }));
  rounds(list, 9, done);
}
/* ===== директор ===== */
function director(done) {
  const sc = [
    ["Сотрудники просят премию, но касса почти пуста.", "Честно объяснить ситуацию и обещать премию позже", ["Взять кредит и выдать всем", "Уволить недовольных"]],
    ["Клиент требует вернуть деньги за бракованный заказ.", "Вернуть деньги и исправить причину брака", ["Сделать вид, что не заметил", "Обвинить клиента"]],
    ["Конкурент снизил цены на 20%.", "Улучшить сервис и найти свою нишу", ["Поднять цены вдвое", "Закрыть магазин"]],
    ["Лучший сотрудник собирается уйти.", "Поговорить и предложить развитие", ["Пригрозить штрафом", "Сделать вид, что не заметил"]],
    ["Проект горит, срок завтра.", "Честно предупредить заказчика и сократить объём", ["Скрыть проблему", "Заставить всех работать всю ночь"]],
    ["Инвестор хочет 90% компании за небольшие деньги.", "Отказаться и торговаться за честную долю", ["Согласиться сразу", "Продать долю втайне"]],
    ["В отделе конфликт между двумя сильными работниками.", "Выслушать обоих и договориться о правилах", ["Уволить обоих", "Ничего не делать"]]
  ];
  const list = shuffle(sc).slice(0, 6).map(c => ({ prompt: "💼 " + c[0], options: shuffle([c[1], ...c[2]]).map(v => ({ label: v, ok: v === c[1] })) }));
  rounds(list, 11, done);
}

/* ===== общий каркас аркад ===== */
function arcade(totalSec, setup, drawHint) {
  const cv = el("canvas"); stage.appendChild(cv);
  const ctx = cv.getContext("2d");
  let W = 0, H = 0, raf = 0, last = performance.now(), time = 0, over = false, st;
  function fit() { const r = stage.getBoundingClientRect(); const d = Math.min(window.devicePixelRatio || 1, 2); W = r.width; H = r.height; cv.width = W * d; cv.height = H * d; ctx.setTransform(d, 0, 0, d, 0, 0); }
  fit(); const ro = new ResizeObserver(fit); ro.observe(stage);
  hint.textContent = drawHint || "";
  const api = { cv, ctx, get W() { return W; }, get H() { return H; }, end: s => { if (over) return; over = true; cancelAnimationFrame(raf); done(s); } };
  st = setup(api);
  function loop(now) {
    const dt = Math.min(0.05, (now - last) / 1000) * FAST; last = now; time += dt;
    ctx.clearRect(0, 0, W, H);
    st.step(dt, time);
    setTime(1 - time / totalSec);
    if (!over && time >= totalSec) { api.end(st.score ? st.score(true) : 0); return; }
    if (!over) raf = requestAnimationFrame(loop);
  }
  raf = requestAnimationFrame(loop);
  cleanup = () => { over = true; cancelAnimationFrame(raf); ro.disconnect(); if (st.off) st.off(); };
  function done(s) { finishGame(s); }
}
function pointers(cv, onDown, onMove, onUp) {
  const pos = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  const d = e => { e.preventDefault(); onDown && onDown(...pos(e), e); };
  const m = e => { onMove && onMove(...pos(e), e); };
  const u = e => { onUp && onUp(...pos(e), e); };
  cv.addEventListener("pointerdown", d); cv.addEventListener("pointermove", m);
  window.addEventListener("pointerup", u); window.addEventListener("pointercancel", u);
  return () => { cv.removeEventListener("pointerdown", d); cv.removeEventListener("pointermove", m); window.removeEventListener("pointerup", u); window.removeEventListener("pointercancel", u); };
}

/* ===== уборщик ===== */
function cleaner() {
  arcade(30, A => {
    const { ctx } = A; const spots = []; let down = false, lx = 0, ly = 0, px = -99, py = -99;
    for (let i = 0; i < 12; i++) spots.push({ x: rnd(50, A.W - 50), y: rnd(60, A.H - 60), r: rnd(26, 40), hp: 100, seed: Math.random() * 6 });
    const off = pointers(A.cv, (x, y) => { down = true; lx = px = x; ly = py = y; }, (x, y) => {
      px = x; py = y;
      if (!down) return;
      const dist = Math.hypot(x - lx, y - ly);
      spots.forEach(s => { if (s.hp > 0 && Math.hypot(x - s.x, y - s.y) < s.r + 14) s.hp -= dist * 0.9 + 2; });
      lx = x; ly = y; pill.textContent = Math.round(score());
    }, () => { down = false; });
    const score = () => spots.reduce((a, s) => a + clamp(1 - s.hp / 100, 0, 1), 0) / spots.length * 100;
    return { off, score, step() {
      ctx.fillStyle = "#c9b99a"; ctx.fillRect(0, 0, A.W, A.H);
      ctx.fillStyle = "#b8a785"; for (let x = 0; x < A.W; x += 60) ctx.fillRect(x, 0, 2, A.H);
      spots.forEach(s => { if (s.hp <= 0) return; ctx.globalAlpha = clamp(s.hp / 100, 0.25, 1); ctx.fillStyle = "#5a4630";
        ctx.beginPath(); for (let a = 0; a < 6.3; a += 0.5) { const rr = s.r * (0.8 + 0.25 * Math.sin(a * 3 + s.seed)); ctx.lineTo(s.x + Math.cos(a) * rr, s.y + Math.sin(a) * rr); } ctx.fill(); ctx.globalAlpha = 1; });
      ctx.font = "34px serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; if (px > -50) ctx.fillText("🧽", px, py);
      if (spots.every(s => s.hp <= 0)) A.end(100);
    } };
  }, "Води пальцем по пятнам, пока не оттрёшь всё");
}

/* ===== официант ===== */
function waiter() {
  arcade(28, A => {
    const { ctx } = A; let th = 0, om = 0, drift = 0, dir = 0, plates = ["🍷", "🍕", "🍔"];
    const keys = e => { if (e.key === "ArrowLeft") dir = e.type === "keydown" ? -1 : 0; if (e.key === "ArrowRight") dir = e.type === "keydown" ? 1 : 0; };
    window.addEventListener("keydown", keys); window.addEventListener("keyup", keys);
    const off0 = pointers(A.cv, x => { dir = x < A.W / 2 ? -1 : 1; }, null, () => { dir = 0; });
    const off = () => { off0(); window.removeEventListener("keydown", keys); window.removeEventListener("keyup", keys); };
    const score = t => clamp((t === true ? time : time) / 28 * 100, 0, 100); let time = 0;
    return { off, score: () => 100, step(dt, t) {
      time = t; drift += (Math.random() - 0.5) * 6 * dt; drift = clamp(drift, -1.1, 1.1);
      om += (th * 2.2 + drift * 1.4 + dir * 4.2) * dt; om *= (1 - 0.6 * dt); th += om * dt;
      pill.textContent = Math.round(clamp(t / 28 * 100, 0, 100));
      ctx.fillStyle = "#3b2a2a"; ctx.fillRect(0, 0, A.W, A.H);
      ctx.fillStyle = "#4a3535"; ctx.fillRect(0, A.H * 0.78, A.W, A.H);
      const cx = A.W / 2, cy = A.H * 0.58, L = Math.min(A.W * 0.8, 360) / 2;
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(th);
      ctx.fillStyle = "#cfd3da"; ctx.fillRect(-L, -6, L * 2, 12);
      ctx.font = "44px serif"; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
      plates.forEach((p, i) => ctx.fillText(p, -L * 0.55 + i * L * 0.55, -10));
      ctx.restore();
      ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(cx, cy + 12, 10, 0, 7); ctx.fill();
      ctx.font = "60px serif"; ctx.fillText("🧑‍🍳", cx, cy + 90);
      ctx.fillStyle = "#ffffff30"; ctx.fillRect(0, 0, A.W / 2, 0);
      ctx.fillStyle = "#ffffff55"; ctx.font = "16px sans-serif"; ctx.fillText("◀ толкни влево        вправо ▶", cx, A.H - 18);
      if (Math.abs(th) > 0.62) { haptic("error"); A.end(clamp(t / 28 * 100, 0, 100)); }
    } };
  }, "Жми левую/правую часть экрана и держи поднос ровно");
}

/* ===== таксист ===== */
function taxi() {
  arcade(35, A => {
    const { ctx } = A; let lane = 1, lives = 3, pax = 0, items = [], spawn = 0, inv = 0, time = 0;
    const move = d => { lane = clamp(lane + d, 0, 2); };
    const keys = e => { if (e.key === "ArrowLeft") move(-1); if (e.key === "ArrowRight") move(1); };
    window.addEventListener("keydown", keys);
    const off0 = pointers(A.cv, x => move(x < A.W / 2 ? -1 : 1));
    const off = () => { off0(); window.removeEventListener("keydown", keys); };
    const score = () => Math.min(100, pax * 12 + time / 35 * 40);
    return { off, score, step(dt, t) {
      time = t; spawn -= dt;
      if (spawn <= 0) { spawn = rnd(0.55, 0.95); items.push({ lane: irnd(0, 2), y: -60, kind: Math.random() < 0.38 ? "p" : "c" }); }
      const sp = 260 + t * 4, laneW = A.W / 3;
      ctx.fillStyle = "#34363f"; ctx.fillRect(0, 0, A.W, A.H);
      ctx.fillStyle = "#ffffff55"; for (let i = 1; i < 3; i++) for (let y = -((t * sp) % 60); y < A.H; y += 60) ctx.fillRect(i * laneW - 2, y, 4, 30);
      ctx.font = "42px serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const py = A.H * 0.82; inv -= dt;
      items.forEach(it => { it.y += sp * dt; const x = laneW * (it.lane + 0.5); ctx.fillText(it.kind === "p" ? "🙋" : "🚗", x, it.y);
        if (!it.hit && it.lane === lane && Math.abs(it.y - py) < 40) { it.hit = true;
          if (it.kind === "p") { pax++; haptic("success"); } else if (inv <= 0) { lives--; inv = 1; haptic("error"); } } });
      items = items.filter(it => it.y < A.H + 60 && !(it.hit && it.kind === "p"));
      if (inv <= 0 || Math.floor(t * 12) % 2) ctx.fillText("🚕", laneW * (lane + 0.5), py);
      ctx.font = "20px sans-serif"; ctx.textAlign = "left"; ctx.fillText("❤️".repeat(Math.max(lives, 0)) + "   🙋 " + pax, 12, 22);
      pill.textContent = Math.round(score());
      if (lives <= 0) A.end(score());
    } };
  }, "Тапни слева или справа, чтобы сменить полосу. Лови 🙋, объезжай 🚗");
}

/* ===== пилот ===== */
function pilot() {
  arcade(40, A => {
    const { ctx } = A; let y = A.H * 0.5, vy = 0, passed = 0, gates = [], spawn = 0.6, time = 0;
    const flap = () => { vy = -330; };
    const keys = e => { if (e.key === " " || e.key === "ArrowUp") { e.preventDefault(); flap(); } };
    window.addEventListener("keydown", keys);
    const off0 = pointers(A.cv, () => flap());
    const off = () => { off0(); window.removeEventListener("keydown", keys); };
    const score = () => Math.min(100, passed * 10);
    return { off, score, step(dt, t) {
      time = t; spawn -= dt; vy += 900 * dt; y += vy * dt;
      if (spawn <= 0) { spawn = 1.7; const gap = Math.max(150, A.H * 0.32); gates.push({ x: A.W + 30, top: rnd(40, A.H - gap - 40), gap, done: false }); }
      const px = A.W * 0.28, sp = 175 + t * 1.5;
      const g = ctx.createLinearGradient(0, 0, 0, A.H); g.addColorStop(0, "#5aa7ff"); g.addColorStop(1, "#bfe3ff"); ctx.fillStyle = g; ctx.fillRect(0, 0, A.W, A.H);
      ctx.fillStyle = "#ffffff80"; for (let i = 0; i < 5; i++) { const cx = ((i * 190 - t * 40) % (A.W + 200) + A.W + 200) % (A.W + 200) - 100; ctx.beginPath(); ctx.arc(cx, 60 + i * 55, 30, 0, 7); ctx.arc(cx + 30, 70 + i * 55, 24, 0, 7); ctx.fill(); }
      let crash = y < 10 || y > A.H - 10;
      gates.forEach(gt => { gt.x -= sp * dt; ctx.fillStyle = "#6b7a99"; ctx.fillRect(gt.x, 0, 54, gt.top); ctx.fillRect(gt.x, gt.top + gt.gap, 54, A.H);
        ctx.fillStyle = "#8d9bb8"; ctx.fillRect(gt.x - 4, gt.top - 14, 62, 14); ctx.fillRect(gt.x - 4, gt.top + gt.gap, 62, 14);
        if (px + 16 > gt.x && px - 16 < gt.x + 54 && (y - 12 < gt.top || y + 12 > gt.top + gt.gap)) crash = true;
        if (!gt.done && gt.x + 54 < px - 16) { gt.done = true; passed++; haptic("success"); } });
      gates = gates.filter(gt => gt.x > -80);
      ctx.save(); ctx.translate(px, y); ctx.rotate(clamp(vy / 700, -0.5, 0.7)); ctx.font = "40px serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("✈️", 0, 0); ctx.restore();
      pill.textContent = Math.round(score());
      if (crash) { haptic("error"); A.end(score()); } else if (passed >= 10) A.end(100);
    } };
  }, "Тапай, чтобы лететь вверх. Пролети 10 проёмов");
}


/* ===== конец смены, награда, запуск ===== */
let lastScore = 0, curCode = "";
function finishGame(s) {
  if (finished) return; finished = true;
  s = clamp(Math.round(s), 0, 100); lastScore = s; setTime(0); pill.textContent = s;
  stage.innerHTML = ""; hint.textContent = "";
  const stars = s >= 80 ? "⭐⭐⭐" : s >= 50 ? "⭐⭐" : s >= 20 ? "⭐" : "💤";
  const msg = s >= 80 ? "Отличная смена! Начальство довольно." : s >= 50 ? "Хорошая работа, так держать." : s >= 20 ? "Неплохо, но можно лучше." : "Смена вышла тяжёлой. Попробуй ещё!";
  const box = el("div", "center");
  box.innerHTML = "<div class='stars'>" + stars + "</div><div class='big'>" + s + "<span style='font-size:26px;color:var(--mut)'>/100</span></div><div class='sub'>" + msg + "</div>";
  if (!demo && !training) {
    const b = el("button", "btn", "💰 Забрать награду"); b.onclick = claim; box.appendChild(b);
    box.appendChild(el("div", "sub", "Откроется бот. Нажми «Старт», и результат засчитается."));
  } else {
    box.appendChild(el("div", "sub", "Это тренировка. Награду даёт смена, открытая из чата по кнопке под заданием."));
  }
  const again = el("button", "btn sec", "🔁 Ещё раз (тренировка)"); again.onclick = () => { training = true; runJob(curCode); }; box.appendChild(again);
  stage.appendChild(box);
  window.__result = s;
}
function claim() {
  const url = "https://t.me/" + BOT + "?start=r_" + sid + "_" + lastScore;
  if (tg && tg.openTelegramLink) { tg.openTelegramLink(url); setTimeout(() => { try { tg.close(); } catch (e) {} }, 400); } else { window.open(url, "_blank"); }
}
let training = false;
function runJob(code, isTraining) {
  if (isTraining) training = true;
  if (!JOBS[code]) code = pick(Object.keys(JOBS));
  curCode = code;
  reset(); showBar(true); const j = JOBS[code];
  setTitle(j[0], j[1]);
  const box = el("div", "center"); box.innerHTML = "<div class='big'>" + j[0].split(" ")[0] + "</div><div class='sub'><b>" + j[0].split(" ").slice(1).join(" ") + "</b><br>" + j[1] + "</div>";
  const go = el("button", "btn", "▶ Начать смену"); go.onclick = () => { reset(); j[2](finishGame); window.__started = true; };
  box.appendChild(go); stage.appendChild(box);
}
