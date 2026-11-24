"use strict";
/* Врач 2.0: приём пациентов с показателями; Директор 2.0: панель KPI и решения совета */
(function () {
  const css = document.createElement("style");
  css.textContent =
    ".dx{display:flex;flex-direction:column;gap:9px;height:100%;overflow:auto;padding-bottom:6px}" +
    ".pcard{background:linear-gradient(160deg,#16213a,#101626);border:1px solid #2c3d63;border-radius:14px;padding:10px 12px;box-shadow:0 0 18px #22d3ee22}" +
    ".pcard .h{display:flex;gap:10px;align-items:center}.pcard .av{font-size:34px}.pcard b{font-size:15px}.pcard small{color:#8fa0c8;display:block;font-size:12px}" +
    ".pcard .cm{margin-top:7px;font-size:13px;line-height:1.4;color:#e6ecff;background:#0b1220;border-radius:10px;padding:7px 10px}" +
    ".vit{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}.vit div{background:#0b1220;border:1px solid #243457;border-radius:10px;text-align:center;padding:6px 2px;font-size:10px;color:#8fa0c8}" +
    ".vit b{display:block;font:700 15px ui-monospace,monospace;color:#6ee7a0}.vit .w b{color:#fbbf24}.vit .d b{color:#ff6b86}" +
    ".ecg{height:42px;border-radius:10px;background:#050a14;border:1px solid #243457;overflow:hidden}.ecg svg{width:200%;height:100%;animation:ecg 2.2s linear infinite}@keyframes ecg{to{transform:translateX(-50%)}}" +
    ".step{font-size:12px;color:#b4a8ff;font-weight:700;letter-spacing:.5px}" +
    ".dx .ch{display:grid;gap:8px}.dx .ch button{background:linear-gradient(160deg,#ffffff16,#ffffff08);border:1px solid #7c6bff55;border-radius:12px;padding:12px;font-size:14px;font-weight:600;color:#fff;text-align:left;font-family:inherit}" +
    ".dx .ch button.ok{border-color:#35f5a0;background:#35f5a022}.dx .ch button.no{border-color:#ff5c7a;background:#ff5c7a22}" +
    ".note{font-size:12px;color:#d7dcf5;background:#0e1019;border:1px solid #2c3050;border-radius:10px;padding:7px 10px;min-height:34px}" +
    ".kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.kpi{background:linear-gradient(160deg,#1a1f33,#121626);border:1px solid #2c3354;border-radius:12px;padding:8px 8px 9px;text-align:center}" +
    ".kpi small{display:block;color:#8b93b8;font-size:10.5px}.kpi b{font:800 18px ui-monospace,monospace}.kpi i{display:block;height:5px;border-radius:3px;background:#ffffff14;margin-top:6px;overflow:hidden}.kpi i s{display:block;height:100%;border-radius:3px;transition:width .5s,background .5s}" +
    ".kpi .d{font-size:10.5px;font-weight:700;min-height:13px}.up{color:#6ee7a0}.dn{color:#ff6b86}" +
    ".mail{background:#14182b;border:1px solid #2c3354;border-radius:12px;padding:10px 12px}.mail .f{font-size:11px;color:#8b93b8;margin-bottom:4px}.mail p{margin:0;font-size:13.5px;line-height:1.4;color:#eef0ff}" +
    ".dec button small{display:block;color:#9aa3c7;font-weight:500;font-size:11.5px;margin-top:3px}";
  document.head.appendChild(css);
  const S = () => window.SFX || { tap() {}, ok() {}, bad() {} };

  /* ================= ВРАЧ ================= */
  const CASES = [
    { who: "Анна, 27 лет", av: "👩", say: "Горло болит, трудно глотать, знобит.", v: { t: 38.9, p: 96, bp: "118/76", s: 98 }, w: ["t"], dx: "Ангина", wrongDx: ["Аллергия", "Перелом"], tr: "Антибиотик и тёплое питьё", wrongTr: ["Гипс на 3 недели", "Только сладкое"] },
    { who: "Борис, 45 лет", av: "👨", say: "Давит в груди, отдаёт в левую руку, холодный пот.", v: { t: 36.8, p: 118, bp: "165/100", s: 94 }, w: ["bp", "s"], d: ["p"], dx: "Инфаркт (подозрение)", wrongDx: ["Простуда", "Растяжение"], tr: "Вызвать скорую, аспирин, покой", wrongTr: ["Отправить домой спать", "Сделать массаж"] },
    { who: "Оля, 9 лет", av: "👧", say: "Упала с велосипеда, рука опухла и не двигается.", v: { t: 36.7, p: 104, bp: "100/65", s: 99 }, w: ["p"], dx: "Перелом руки", wrongDx: ["Ангина", "Отравление"], tr: "Рентген и гипс", wrongTr: ["Антибиотики", "Горчичники"] },
    { who: "Павел, 33 года", av: "🧔", say: "Тошнит, болит живот, после шаурмы прошло 3 часа.", v: { t: 37.6, p: 92, bp: "112/72", s: 98 }, w: ["t"], dx: "Пищевое отравление", wrongDx: ["Перелом", "Ангина"], tr: "Промывание и много воды", wrongTr: ["Гипс", "Пробежка"] },
    { who: "Света, 52 года", av: "👵", say: "Постоянная жажда, слабость, много пью воды.", v: { t: 36.6, p: 80, bp: "130/85", s: 98, g: 11.2 }, w: ["bp"], dx: "Диабет (подозрение)", wrongDx: ["Ангина", "Вывих"], tr: "Анализ сахара и диета", wrongTr: ["Больше сладкого", "Гипс"] },
    { who: "Игорь, 19 лет", av: "🧑", say: "Чихаю, слёзы, зуд в глазах с утра, в парке цвела берёза.", v: { t: 36.6, p: 78, bp: "115/70", s: 99 }, w: [], dx: "Аллергия", wrongDx: ["Инфаркт", "Перелом"], tr: "Антигистаминное", wrongTr: ["Рентген", "Антибиотик"] },
    { who: "Макс, 6 лет", av: "👦", say: "Кашель, насморк, температура 37,5 уже два дня.", v: { t: 37.5, p: 98, bp: "95/60", s: 97 }, w: ["t"], dx: "ОРВИ", wrongDx: ["Перелом", "Инфаркт"], tr: "Покой, питьё, жаропонижающее", wrongTr: ["Операция", "Гипс"] }
  ];
  function ecgSvg(bad) {
    const seg = bad ? "0,20 10,20 14,10 18,30 22,6 26,34 30,20 60,20" : "0,20 20,20 26,20 30,6 34,34 38,20 80,20";
    const p = bad ? 60 : 80;
    let pts = ""; for (let k = 0; k < 6; k++) pts += seg.split(" ").map(s => { const [x, y] = s.split(","); return (+x + k * p) + "," + y; }).join(" ") + " ";
    return "<svg viewBox='0 0 " + p * 3 + " 40' preserveAspectRatio='none'><polyline fill='none' stroke='" + (bad ? "#ff6b86" : "#35f5a0") + "' stroke-width='2' points='" + pts + "'/></svg>";
  }
  function doctor2(done) {
    const list = shuffle(CASES).slice(0, 5); let i = 0, total = 0, raf = 0, lock = false;
    const wrap = el("div", "dx"); stage.appendChild(wrap); cleanup = () => { cancelAnimationFrame(raf); lock = true; };
    hint.textContent = "Смотри показатели, ставь диагноз, потом выбирай лечение";
    function show() {
      if (i >= list.length) return done(Math.round(total / list.length));
      const c = list[i]; wrap.innerHTML = ""; lock = false; let pts = 0, stage_ = 0, t0 = performance.now(); const LIM = 24;
      const cls = k => (c.d || []).includes(k) ? "d" : (c.w || []).includes(k) ? "w" : "";
      const card = el("div", "pcard");
      card.innerHTML = "<div class='h'><div class='av'>" + c.av + "</div><div><b>" + c.who + "</b><small>Приём " + (i + 1) + "/" + list.length + " · кабинет 4</small></div></div>" +
        "<div class='cm'>💬 «" + c.say + "»</div><div class='vit'><div class='" + cls("t") + "'>ТЕМП.<b>" + c.v.t + "°</b></div><div class='" + cls("p") + "'>ПУЛЬС<b>" + c.v.p + "</b></div><div class='" + cls("bp") + "'>ДАВЛ.<b>" + c.v.bp + "</b></div><div class='" + cls("s") + "'>SpO₂<b>" + c.v.s + "%</b></div></div>";
      const ecg = el("div", "ecg", ecgSvg((c.d || []).length > 0)); const note = el("div", "note", "🩺 Что с пациентом? Выбери диагноз.");
      const step = el("div", "step", "ШАГ 1/2 · ДИАГНОЗ"); const ch = el("div", "ch");
      wrap.append(card, ecg, step, ch, note);
      function offer(right, wrong, onRight, onWrong) {
        ch.innerHTML = "";
        shuffle([{ t: right, ok: 1 }, ...wrong.map(t => ({ t }))]).forEach(o => {
          const b = el("button", "", o.t);
          b.onclick = () => { if (lock) return; lock = true; b.classList.add(o.ok ? "ok" : "no"); [...ch.children].forEach(x => { x.disabled = true; if (x.textContent === right) x.classList.add("ok"); }); o.ok ? onRight() : onWrong(); };
          ch.appendChild(b);
        });
      }
      const speed = () => clamp(1 - ((performance.now() - t0) / 1000) / LIM, 0.3, 1);
      offer(c.dx, c.wrongDx, () => { S().ok(); pts += 55 * speed() + 15; note.textContent = "✅ Диагноз верный: " + c.dx + ". Теперь лечение."; setTimeout(() => { lock = false; step.textContent = "ШАГ 2/2 · ЛЕЧЕНИЕ"; offer(c.tr, c.wrongTr, () => { S().ok(); pts += 30; note.textContent = "💊 Назначено верно. Пациент благодарит!"; next(); }, () => { S().bad(); note.textContent = "❌ Лечение не подошло. Нужно было: " + c.tr; next(); }); }, 900); },
        () => { S().bad(); note.textContent = "❌ Не тот диагноз. Верно: " + c.dx; pts += 0; setTimeout(next, 1700); });
      function next() { total += clamp(pts, 0, 100); pill.textContent = Math.round(total / list.length); i++; setTimeout(show, 1400); }
      const tick = () => { const left = LIM - (performance.now() - t0) / 1000 * FAST; setTime(left / LIM); if (left <= 0 && !lock) { lock = true; note.textContent = "⏱ Время вышло, пациента забрала скорая"; S().bad(); next(); return; } raf = requestAnimationFrame(tick); };
      cancelAnimationFrame(raf); tick();
    }
    show();
  }
  JOBS.vra = ["🩺 Врач", "Принимай пациентов: диагноз и лечение", doctor2];

  /* ================= ДИРЕКТОР ================= */
  const EV = [
    { from: "HR · Марина", t: "Сотрудники просят повысить зарплаты на 10%.", o: [["Повысить всем", "ровно, но дорого", { p: -14, tm: 18, r: 3 }], ["Только лучшим", "по заслугам", { p: -6, tm: 6, r: 0 }], ["Отказать", "экономим", { p: 6, tm: -16, r: -3 }]] },
    { from: "Маркетинг · Данил", t: "Блогер предлагает рекламу за 15% квартального бюджета.", o: [["Согласиться", "охват огромный", { p: -10, tm: 0, r: 16 }], ["Выбрать микроблогеров", "дешевле, эффект скромный", { p: -4, tm: 0, r: 7 }], ["Отказаться", "обойдёмся без рекламы", { p: 3, tm: 0, r: -6 }]] },
    { from: "Юрист · Олег", t: "Конкурент подаёт иск за схожий логотип, шансы 50 на 50.", o: [["Идти в суд", "риск, но репутация", { p: -8, tm: 0, r: 4 }], ["Договориться", "заплатим, но тихо", { p: -12, tm: 0, r: 2 }], ["Сменить логотип", "ребрендинг", { p: -6, tm: -4, r: -4 }]] },
    { from: "Продажи · Ира", t: "Крупный клиент требует скидку 20% и обещает большой заказ.", o: [["Дать скидку", "объём важнее", { p: 8, tm: 2, r: -2 }], ["Дать 10%", "компромисс", { p: 10, tm: 0, r: 1 }], ["Отказать", "держим цену", { p: -8, tm: 0, r: 2 }]] },
    { from: "IT · Артём", t: "Сервер падает каждую неделю. Нужна новая инфраструктура.", o: [["Купить новую", "надёжно", { p: -12, tm: 8, r: 8 }], ["Починить старую", "на время", { p: -4, tm: -2, r: -3 }], ["Игнорировать", "авось", { p: 4, tm: -6, r: -12 }]] },
    { from: "Операции · Лена", t: "Сотрудники хотят удалёнку два дня в неделю.", o: [["Разрешить", "команда довольна", { p: 2, tm: 14, r: 0 }], ["Пилот на месяц", "проверим", { p: 0, tm: 6, r: 0 }], ["Запретить", "офис важнее", { p: 0, tm: -14, r: -2 }]] },
    { from: "Инвестор · Виктор", t: "Предлагает вложить деньги за долю в компании.", o: [["Принять", "деньги сейчас", { p: 16, tm: 4, r: -2 }], ["Попросить меньше доли", "торг", { p: 8, tm: 2, r: 2 }], ["Отказать", "сами справимся", { p: -2, tm: 0, r: 4 }]] },
    { from: "Поддержка · Соня", t: "Клиенты жалуются на долгие ответы. Нужно ещё 3 оператора.", o: [["Нанять", "качество важнее", { p: -9, tm: 5, r: 12 }], ["Чат-бот", "дёшево, не идеально", { p: -3, tm: -2, r: 4 }], ["Оставить как есть", "терпят же", { p: 3, tm: -6, r: -12 }]] }
  ];
  function director2(done) {
    const list = shuffle(EV).slice(0, 6); const K = { p: 55, tm: 55, r: 55 }; let i = 0, lock = false;
    const wrap = el("div", "dx"); stage.appendChild(wrap); cleanup = () => { lock = true; };
    hint.textContent = "Держи прибыль, команду и репутацию выше 30 и как можно выше";
    const NAMES = { p: ["💰 Прибыль", "#fbbf24"], tm: ["👥 Команда", "#22d3ee"], r: ["⭐ Репутация", "#b4a8ff"] };
    const kp = el("div", "kpis");
    Object.keys(K).forEach(k => kp.appendChild(el("div", "kpi", "<small>" + NAMES[k][0] + "</small><b id='v" + k + "'>" + K[k] + "</b><div class='d' id='d" + k + "'></div><i><s id='b" + k + "' style='width:" + K[k] + "%;background:" + NAMES[k][1] + "'></s></i>")));
    wrap.appendChild(kp); const box = el("div", "dec"); wrap.appendChild(box);
    function paint(delta) { Object.keys(K).forEach(k => { const v = clamp(K[k], 0, 100); wrap.querySelector("#v" + k).textContent = v; const b = wrap.querySelector("#b" + k); b.style.width = v + "%"; b.style.background = v < 30 ? "#ff5c7a" : NAMES[k][1]; const d = wrap.querySelector("#d" + k); const x = delta ? delta[k] : 0; d.textContent = x ? (x > 0 ? "+" + x : x) : ""; d.className = "d " + (x > 0 ? "up" : "dn"); }); }
    function show() {
      if (i >= list.length) return finish();
      const e = list[i]; lock = false; box.innerHTML = ""; setTime(1 - i / list.length);
      box.appendChild(el("div", "mail", "<div class='f'>✉ " + e.from + " · вопрос " + (i + 1) + "/" + list.length + "</div><p>" + e.t + "</p>"));
      const ch = el("div", "ch"); ch.style.marginTop = "9px";
      e.o.forEach(o => {
        const b = el("button", "", o[0] + "<small>" + o[1] + "</small>");
        b.onclick = () => { if (lock) return; lock = true; S().tap(); b.classList.add("ok"); Object.keys(K).forEach(k => (K[k] = clamp(K[k] + (o[2][k] || 0), 0, 100))); paint(o[2]); const m = Math.min(...Object.values(K)); m < 30 ? S().bad() : S().ok(); i++; pill.textContent = Math.round((K.p + K.tm + K.r) / 3); setTimeout(show, 1500); };
        ch.appendChild(b);
      });
      box.appendChild(ch);
    }
    function finish() {
      const avg = (K.p + K.tm + K.r) / 3, mn = Math.min(...Object.values(K));
      const score = Math.round(clamp(avg * 1.15 - (mn < 30 ? 25 : 0) + (mn > 50 ? 8 : 0), 0, 100));
      box.innerHTML = ""; box.appendChild(el("div", "mail", "<div class='f'>📊 Итог квартала</div><p>" + (mn < 30 ? "Один из показателей провалился, совет директоров недоволен." : avg > 65 ? "Отличный квартал! Акционеры довольны 🎉" : "Нормальный квартал, но есть куда расти.") + "</p>"));
      S()[mn < 30 ? "bad" : "ok"](); setTimeout(() => done(score), 2200);
    }
    paint(null); show();
  }
  JOBS.dir = ["💼 Директор", "Управляй компанией: прибыль, команда, репутация", director2];
})();
