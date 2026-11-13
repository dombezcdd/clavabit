"use strict";
/* Монополия против ботов (упрощённые правила): покупка улиц, аренда, дома, шанс, тюрьма, банкротство */

const MONO = (() => {
  const GROUPS = {
    brown: { c: "#8b5a2b", h: 50 }, lblue: { c: "#6cc6ff", h: 50 }, pink: { c: "#ff7ac0", h: 100 }, orange: { c: "#ff9f43", h: 100 },
    red: { c: "#ff5252", h: 150 }, yellow: { c: "#ffe14d", h: 150 }, green: { c: "#37c871", h: 200 }, blue: { c: "#4a6cff", h: 200 }
  };
  const P = (g, n, p) => ({ t: "prop", g, n, p });
  const TILES = [
    { t: "start", n: "СТАРТ", i: "🏁" }, P("brown", "Бульвар", 60), { t: "chance", n: "Шанс", i: "❓" }, P("brown", "Переулок", 60),
    { t: "tax", n: "Налог", i: "💸", amt: 150 }, { t: "station", n: "Вокзал", i: "🚉", p: 200 }, P("lblue", "Набережная", 100),
    { t: "jail", n: "Тюрьма", i: "🔒" }, P("lblue", "Парк", 120), P("pink", "Арбат", 140), { t: "util", n: "Электро", i: "💡", p: 150 },
    P("pink", "Тверская", 160), { t: "chance", n: "Шанс", i: "❓" }, P("orange", "Невский", 180), { t: "parking", n: "Отдых", i: "🅿️" },
    P("orange", "Садовая", 200), P("red", "Покровка", 220), { t: "station", n: "Аэропорт", i: "✈️", p: 200 }, P("red", "Петровка", 240),
    { t: "chance", n: "Шанс", i: "❓" }, P("yellow", "Лубянка", 260), { t: "gojail", n: "В тюрьму", i: "👮" }, P("yellow", "Маросейка", 280),
    { t: "util", n: "Водоканал", i: "💧", p: 150 }, P("green", "Рублёвка", 300), P("green", "Патриаршие", 320),
    P("blue", "Кутузовский", 350), P("blue", "Красная пл.", 400)
  ];
  const CARDS = [
    { t: "Банковская ошибка в вашу пользу: +150", m: 150 }, { t: "Штраф за парковку: −60", m: -60 },
    { t: "Вы выиграли конкурс красоты: +100", m: 100 }, { t: "Оплатите ремонт: −120", m: -120 },
    { t: "Идите на СТАРТ и получите +200", go: 0 }, { t: "Отправляйтесь в тюрьму!", jail: true },
    { t: "Вперёд на 3 клетки", mv: 3 }, { t: "Назад на 3 клетки", mv: -3 },
    { t: "День рождения: каждый игрок дарит вам по 30", each: 30 }, { t: "Благотворительность: заплатите каждому по 20", payEach: 20 },
    { t: "Идите к ближайшему вокзалу", st: true }
  ];
  const SIDES = ["🎩", "🚗", "🐕", "🚢"], COLORS = ["#4cd98a", "#ff6b6b", "#6cb6ff", "#ffb84d"], NAMES = ["Ты", "Бот Макс", "Бот Лиза", "Бот Гоша"];
  const RENT = [1, 2, 5, 15, 45, 80, 125];            // множители p/30: нет набора, набор, 1-4 дома, отель
  const START = 1500, SALARY = 200, JAIL_FINE = 50, MAX_ROUNDS = 40, N = TILES.length;
  const cellPos = i => i === 0 ? [7, 7] : i <= 7 ? [7, 7 - i] : i <= 14 ? [14 - i, 0] : i <= 21 ? [0, i - 14] : [i - 21, 7];
  return { GROUPS, TILES, CARDS, SIDES, COLORS, NAMES, RENT, START, SALARY, JAIL_FINE, MAX_ROUNDS, N, cellPos };
})();

function startMonopoly() {
  reset(); showBar(false); setTitle("🎩 Монополия", "Ты против ботов");
  const box = el("div", "center");
  box.innerHTML = "<div class='big'>🎩</div><div class='sub'><b>Монополия</b><br>Покупай улицы, собирай цветные наборы, строй дома и разоряй ботов. После " + MONO.MAX_ROUNDS + " кругов побеждает самый богатый.</div>";
  const row = el("div", "row");
  [1, 2, 3].forEach(n => { const b = el("button", "btn sm", n + " " + (n === 1 ? "бот" : "бота")); b.onclick = () => monoRun(n); row.appendChild(b); });
  box.appendChild(row); stage.appendChild(box);
  window.__monoStart = monoRun;
  if (q.get("bots")) monoRun(Number(q.get("bots")));
}

function monoRun(bots) {
  reset(); showBar(false); pill.textContent = "$" + MONO.START;
  const { TILES, GROUPS, RENT, N } = MONO;
  const AUTO = q.get("auto") !== null;
  let alive = true; cleanup = () => { alive = false; };
  const players = [];
  for (let i = 0; i <= bots; i++) players.push({ id: i, name: MONO.NAMES[i], ico: MONO.SIDES[i], color: MONO.COLORS[i], cash: MONO.START, pos: 0, jail: 0, dead: false, human: i === 0, dbl: 0, risk: 0.4 + Math.random() * 0.5 });
  const owner = {}, houses = {}; let turn = 0, round = 1, canBuild = false, over = false; const log = [];
  window.__mono = { players, owner, houses, get over() { return over; }, get round() { return round; } };

  /* ---- разметка ---- */
  const wrap = el("div"); wrap.style.cssText = "display:flex;flex-direction:column;height:100%;gap:8px";
  const boardBox = el("div"); boardBox.style.cssText = "flex:1;min-height:0;display:flex;align-items:center;justify-content:center";
  const board = el("div"); board.style.cssText = "display:grid;grid-template-columns:repeat(8,1fr);grid-template-rows:repeat(8,1fr);gap:2px;aspect-ratio:1;background:#00000030;padding:3px;border-radius:14px";
  boardBox.appendChild(board);
  const strip = el("div"); strip.style.cssText = "display:flex;gap:6px;flex:0 0 auto";
  wrap.append(boardBox, strip); stage.appendChild(wrap);
  function fit() { const r = boardBox.getBoundingClientRect(); const s = Math.max(200, Math.min(r.width, r.height)); board.style.width = s + "px"; }
  fit(); addEventListener("resize", fit); const oc = cleanup; cleanup = () => { oc(); removeEventListener("resize", fit); };
  const center = el("div"); center.style.cssText = "grid-area:2/2/8/8;display:flex;flex-direction:column;align-items:center;justify-content:space-between;gap:4px;padding:6px;background:#ffffff0f;border-radius:10px;min-height:0;overflow:hidden";
  const who = el("div"); who.style.cssText = "font-weight:800;font-size:15px;text-align:center";
  const dice = el("div"); dice.style.cssText = "font-size:34px;letter-spacing:6px;min-height:42px";
  const msg = el("div"); msg.style.cssText = "font-size:12px;color:var(--mut);text-align:center;line-height:1.3;flex:1;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end";
  const acts = el("div"); acts.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;justify-content:center;min-height:42px;align-items:center";
  center.append(who, dice, msg, acts);

  const cur = () => players[turn], liveCount = () => players.filter(p => !p.dead).length;
  const money = n => "$" + n, tileOwner = i => owner[i] !== undefined ? players[owner[i]] : null;
  const group = g => TILES.map((t, i) => ({ t, i })).filter(x => x.t.g === g);
  const hasSet = (pid, g) => group(g).every(x => owner[x.i] === pid);
  function rentOf(i, dsum) {
    const t = TILES[i], o = owner[i];
    if (t.t === "station") return 25 * Math.pow(2, TILES.reduce((a, x, k) => a + (x.t === "station" && owner[k] === o ? 1 : 0), 0) - 1);
    if (t.t === "util") { const both = TILES.reduce((a, x, k) => a + (x.t === "util" && owner[k] === o ? 1 : 0), 0) === 2; return (dsum || 7) * (both ? 10 : 4); }
    const h = houses[i] || 0, lvl = h ? 1 + h : hasSet(o, t.g) ? 1 : 0;
    return Math.round(t.p / 30 * RENT[lvl]);
  }
  const worth = p => p.cash + TILES.reduce((a, t, i) => a + (owner[i] === p.id ? (t.p || 0) / 2 + (houses[i] || 0) * (GROUPS[t.g] ? GROUPS[t.g].h / 2 : 0) : 0), 0);
  function say(t) { log.push(t); if (log.length > 40) log.shift(); msg.innerHTML = log.slice(-3).map(x => "<div>" + x + "</div>").join(""); }

  /* ---- отрисовка ---- */
  function render() {
    board.innerHTML = ""; board.appendChild(center);
    TILES.forEach((t, i) => {
      const [r, c] = MONO.cellPos(i); const d = el("button"); const o = tileOwner(i);
      d.style.cssText = "grid-area:" + (r + 1) + "/" + (c + 1) + ";position:relative;border:0;padding:0;border-radius:6px;background:#ffffff1c;color:var(--tx);overflow:hidden;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;font-family:inherit;cursor:pointer" + (o ? ";box-shadow:inset 0 -4px 0 " + o.color : "");
      let h = "";
      if (t.g) h += "<i style='display:block;width:100%;height:30%;background:" + GROUPS[t.g].c + "'></i>";
      h += "<span style='font-size:" + (t.g ? 7 : 15) + "px;line-height:1.05;margin-top:1px'>" + (t.i || t.n.slice(0, 7)) + "</span>";
      if (t.p) h += "<span style='font-size:8px;color:var(--mut)'>" + t.p + "</span>";
      const hh = houses[i] || 0; if (hh) h += "<span style='font-size:8px;position:absolute;top:1px;right:2px'>" + (hh === 5 ? "🏨" : "🏠".repeat(hh)) + "</span>";
      const here = players.filter(p => !p.dead && p.pos === i); if (here.length) h += "<span style='position:absolute;bottom:1px;font-size:11px;line-height:1'>" + here.map(p => p.ico).join("") + "</span>";
      d.innerHTML = h; d.onclick = () => tileInfo(i); board.appendChild(d);
    });
    strip.innerHTML = "";
    players.forEach(p => {
      const s = el("div"); s.style.cssText = "flex:1;min-width:0;background:var(--card);border:2px solid " + (p === cur() && !over ? p.color : "var(--line)") + ";border-radius:12px;padding:5px 7px;text-align:center;font-size:11px;opacity:" + (p.dead ? .35 : 1);
      s.innerHTML = "<div>" + p.ico + " <b>" + p.name + "</b></div><div style='color:" + (p.cash < 0 ? "var(--bad)" : "var(--tx)") + ";font-weight:800'>" + (p.dead ? "банкрот" : money(p.cash)) + "</div>";
      strip.appendChild(s);
    });
    pill.textContent = money(players[0].cash); hint.textContent = "Круг " + round + " из " + MONO.MAX_ROUNDS;
    who.innerHTML = over ? "Игра окончена" : cur().ico + " Ходит: " + cur().name;
  }

  /* ---- выбор кнопками ---- */
  function choose(opts, bot) {
    return new Promise(res => {
      acts.innerHTML = "";
      const done = v => { acts.innerHTML = ""; res(v); };
      if (bot !== undefined || AUTO) { setTimeout(() => done(bot !== undefined && bot !== null ? bot : opts[0].v), 450 / FAST); return; }
      opts.forEach(o => { const b = el("button", "btn sm" + (o.sec ? " sec" : ""), o.label); b.style.minWidth = "0"; b.onclick = () => done(o.v); acts.appendChild(b); });
    });
  }
  function tileInfo(i) {
    const t = TILES[i], o = tileOwner(i); const ov = el("div", "center"); ov.style.cssText += ";background:#1b1530ee;z-index:9";
    let h = "<div class='big' style='font-size:40px'>" + (t.i || "🏘") + "</div><div class='sub'><b>" + t.n + "</b>";
    if (t.p) { h += "<br>Цена: " + money(t.p) + "<br>Владелец: " + (o ? o.ico + " " + o.name : "банк"); if (o) h += "<br>Аренда сейчас: " + money(rentOf(i, 7)); if (t.g) h += "<br>Дом: " + money(GROUPS[t.g].h) + " · домов: " + (houses[i] || 0); }
    else h += "<br>" + ({ start: "Проходя СТАРТ, получаешь $" + MONO.SALARY, chance: "Карточка с сюрпризом", tax: "Налог $" + t.amt, jail: "Просто посещение или отсидка", parking: "Отдыхаешь", gojail: "Отправляешься в тюрьму" }[t.t] || ""); h += "</div>";
    ov.innerHTML = h; const row = el("div", "row");
    if (canBuildOn(i, players[0])) { const b = el("button", "btn sm", "🏠 Построить дом −" + money(GROUPS[t.g].h)); b.onclick = () => { build(players[0], i); stage.removeChild(ov); render(); }; row.appendChild(b); }
    const c = el("button", "btn sm sec", "Закрыть"); c.onclick = () => stage.removeChild(ov); row.appendChild(c); ov.appendChild(row); stage.appendChild(ov);
  }
  function canBuildOn(i, p) {
    const t = TILES[i]; if (!t.g || owner[i] !== p.id || !hasSet(p.id, t.g) || p.dead || over) return false;
    if (p.human && !canBuild) return false;
    const h = houses[i] || 0; if (h >= 5 || p.cash < GROUPS[t.g].h) return false;
    return h <= Math.min(...group(t.g).map(x => houses[x.i] || 0));
  }
  function build(p, i) { p.cash -= GROUPS[TILES[i].g].h; houses[i] = (houses[i] || 0) + 1; say(p.ico + " " + p.name + " строит на «" + TILES[i].n + "»"); }

  /* ---- деньги ---- */
  function liquidate(p, need) {
    const mine = TILES.map((t, i) => i).filter(i => owner[i] === p.id);
    for (const i of mine.filter(i => houses[i]).sort((a, b) => houses[b] - houses[a])) { while (houses[i] > 0 && p.cash < need) { houses[i]--; p.cash += GROUPS[TILES[i].g].h / 2; } }
    for (const i of mine) { if (p.cash >= need) break; if (!houses[i]) { delete owner[i]; p.cash += TILES[i].p / 2; say(p.ico + " продаёт «" + TILES[i].n + "» банку"); } }
  }
  function pay(p, amt, to) {
    if (p.cash < amt) liquidate(p, amt);
    if (p.cash >= amt) { p.cash -= amt; if (to) to.cash += amt; return true; }
    if (to) to.cash += Math.max(0, p.cash);
    TILES.forEach((t, i) => { if (owner[i] === p.id) { if (to) owner[i] = to.id; else delete owner[i]; houses[i] = 0; } });
    p.cash = 0; p.dead = true; say("💀 " + p.name + " банкрот!"); return false;
  }

  /* ---- ход ---- */
  const FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
  async function roll() {
    for (let k = 0; k < 6 && alive; k++) { dice.textContent = FACES[irnd(0, 5)] + " " + FACES[irnd(0, 5)]; await wait(70); }
    const a = irnd(1, 6), b = irnd(1, 6); dice.textContent = FACES[a - 1] + " " + FACES[b - 1] + "  =" + (a + b); return [a, b];
  }
  async function moveBy(p, steps) {
    const dir = steps < 0 ? -1 : 1;
    for (let k = 0; k < Math.abs(steps) && alive; k++) { p.pos = (p.pos + dir + N) % N; if (dir > 0 && p.pos === 0) { p.cash += MONO.SALARY; say(p.ico + " проходит СТАРТ: +" + money(MONO.SALARY)); } render(); await wait(150); }
  }
  async function toJail(p) { p.pos = 7; p.jail = 3; p.dbl = 0; say("🔒 " + p.name + " отправляется в тюрьму"); render(); await wait(500); }
  async function land(p, dsum, depth) {
    const t = TILES[p.pos], i = p.pos; depth = depth || 0;
    if (t.t === "prop" || t.t === "station" || t.t === "util") {
      const o = tileOwner(i);
      if (!o) {
        if (p.cash < t.p) { say(p.name + ": не хватает денег на «" + t.n + "»"); return; }
        let buy;
        if (p.human) buy = await choose([{ label: "Купить −" + money(t.p), v: true }, { label: "Пропустить", v: false, sec: true }]);
        else { const completes = t.g && group(t.g).filter(x => x.i !== i).every(x => owner[x.i] === p.id); buy = await choose([], p.cash - t.p >= 200 * (1.1 - p.risk) || (completes && p.cash - t.p >= 40)); }
        if (buy) { p.cash -= t.p; owner[i] = p.id; say(p.ico + " " + p.name + " покупает «" + t.n + "» за " + money(t.p)); haptic("success"); }
      } else if (o !== p) { const r = rentOf(i, dsum); say(p.name + " платит " + o.name + " аренду " + money(r)); pay(p, r, o); if (p.human) haptic("error"); }
    } else if (t.t === "tax") { say(p.name + " платит налог " + money(t.amt)); pay(p, t.amt, null); }
    else if (t.t === "gojail") await toJail(p);
    else if (t.t === "chance") {
      const c = pick(MONO.CARDS); say("❓ " + c.t); await wait(900);
      if (c.m) { if (c.m > 0) p.cash += c.m; else pay(p, -c.m, null); }
      else if (c.go !== undefined) { const st = (N - p.pos) % N; await moveBy(p, st); }
      else if (c.jail) await toJail(p);
      else if (c.mv && depth < 2) { await moveBy(p, c.mv); await land(p, 7, depth + 1); }
      else if (c.st && depth < 2) { let k = 0; while (TILES[(p.pos + k) % N].t !== "station") k++; await moveBy(p, k); await land(p, 7, depth + 1); }
      else if (c.each) players.forEach(o => { if (o !== p && !o.dead) { const d = Math.min(c.each, Math.max(0, o.cash)); o.cash -= d; p.cash += d; } });
      else if (c.payEach) players.forEach(o => { if (o !== p && !o.dead && !p.dead) pay(p, c.payEach, o); });
    }
  }
  function botBuild(p) {
    for (let k = 0; k < 2; k++) {
      const opts = TILES.map((t, i) => i).filter(i => canBuildOn(i, p) && p.cash - GROUPS[TILES[i].g].h >= 250);
      if (!opts.length) break; build(p, pick(opts));
    }
  }
  async function takeTurn(p) {
    render(); await wait(300);
    if (!p.human) botBuild(p);
    if (p.jail > 0) {
      let free = false;
      const payIt = p.human ? await choose([{ label: "💵 Выйти −" + money(MONO.JAIL_FINE), v: true }, { label: "🎲 Бросить на дубль", v: false, sec: true }]) : await choose([], p.cash > 500);
      if (payIt && p.cash >= MONO.JAIL_FINE) { pay(p, MONO.JAIL_FINE, null); p.jail = 0; free = true; say(p.name + " откупился из тюрьмы"); }
      else { const [a, b] = await roll(); if (a === b) { p.jail = 0; free = true; say(p.name + " выбросил дубль и вышел"); await moveBy(p, a + b); await land(p, a + b); return false; }
        p.jail--; if (p.jail === 0) { pay(p, MONO.JAIL_FINE, null); say(p.name + " отсидел и заплатил штраф"); free = true; } else say(p.name + " сидит в тюрьме"); await wait(500); if (!free) return false; }
    }
    canBuild = p.human;
    await choose([{ label: "🎲 Бросить кубики", v: 1 }], p.human ? undefined : 1);
    canBuild = false;
    const [a, b] = await roll(); const dsum = a + b; const dbl = a === b;
    if (dbl) p.dbl++; else p.dbl = 0;
    if (p.dbl >= 3) { say("Три дубля подряд!"); await toJail(p); return false; }
    await moveBy(p, dsum); render(); await land(p, dsum);
    render(); await wait(400);
    return dbl && !p.dead && p.jail === 0;
  }
  function endCheck() {
    const left = players.filter(p => !p.dead);
    if (left.length === 1) return left[0];
    if (players[0].dead) return players.filter(p => !p.dead).sort((a, b) => worth(b) - worth(a))[0];
    if (round > MONO.MAX_ROUNDS) return left.sort((a, b) => worth(b) - worth(a))[0];
    return null;
  }
  function finish(w) {
    over = true; render(); window.__monoWinner = w.id;
    const me = w.id === 0, dead = players[0].dead;
    const ov = el("div", "center"); ov.style.cssText += ";background:#1b1530ee;z-index:9";
    ov.innerHTML = "<div class='big' style='font-size:48px'>" + (me ? "🏆" : dead ? "💀" : "🥈") + "</div><div class='big' style='font-size:26px'>" + (me ? "Ты победил!" : dead ? "Ты банкрот" : "Победил " + w.name) + "</div><div class='sub'>" +
      players.map(p => p.ico + " " + p.name + ": " + (p.dead ? "банкрот" : money(Math.round(worth(p))))).join("<br>") + "</div>";
    const b = el("button", "btn", "🔁 Играть ещё"); b.onclick = startMonopoly; ov.appendChild(b); stage.appendChild(ov);
  }
  async function loop() {
    render(); say("Игра началась! У каждого " + money(MONO.START));
    while (alive && !over) {
      const p = cur();
      if (!p.dead) { const again = await takeTurn(p); if (!alive) return; const w = endCheck(); if (w) return finish(w); if (again) continue; }
      turn = (turn + 1) % players.length; if (turn === 0) round++;
      const w = endCheck(); if (w) return finish(w);
    }
  }
  loop();
}
