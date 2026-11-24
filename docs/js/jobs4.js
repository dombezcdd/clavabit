"use strict";
/* Пилот 2.0: предполётный чек-лист + заход на посадку (глиссада, боковой ветер) + выравнивание */
(function () {
  const css = document.createElement("style");
  css.textContent =
    ".lg{display:flex;flex-direction:column;gap:8px;height:100%;overflow:auto}" +
    ".lg .atc{background:#14182b;border:1px solid #2c3354;border-radius:12px;padding:8px 11px;font-size:12.5px;line-height:1.4;color:#d7dcf5}.lg .atc b{color:#6ee7a0}.lg .atc small{color:#8b93b8}" +
    ".pfd{position:relative;height:310px;flex:none;border-radius:14px;overflow:hidden;border:1px solid #2c3354;box-shadow:0 10px 30px #000a,0 0 22px #22d3ee22}" +
    ".pfd .sky{position:absolute;left:0;right:0;top:0;height:50%}.pfd .gnd{position:absolute;left:0;right:0;top:50%;bottom:0}" +
    ".pfd .rw{position:absolute;left:50%;top:50%;width:0;height:0;border-left:var(--w) solid transparent;border-right:var(--w) solid transparent;border-bottom:var(--h) solid #3a3d48;transform-origin:50% 0}" +
    ".pfd .cl{position:absolute;left:50%;top:50%;width:3px;transform-origin:50% 0;background:repeating-linear-gradient(#fff 0 10px,transparent 10px 20px)}" +
    ".pfd .tape{position:absolute;top:34px;bottom:30px;width:50px;background:#0a0d18cc;border:1px solid #2c3354;font:11px ui-monospace,monospace;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:6px;color:#9fe7ff;text-align:center}" +
    ".pfd .tape b{display:block;width:88%;background:#000;border:1px solid #22d3ee;color:#fff;padding:3px 0;box-shadow:0 0 8px #22d3ee66;font-size:13px}.pfd .tape small{font-size:9px;color:#7d86ad}" +
    ".pfd .tape.l{left:8px}.pfd .tape.r{right:8px}" +
    ".pfd .gs{position:absolute;left:66px;top:50px;bottom:48px;width:12px;background:#0008;border-radius:6px}.pfd .gs i{position:absolute;left:1px;right:1px;height:10px;border-radius:5px;background:#35f5a0;box-shadow:0 0 10px #35f5a0;transition:background .2s}" +
    ".pfd .ls{position:absolute;left:86px;right:86px;bottom:26px;height:12px;background:#0008;border-radius:6px}.pfd .ls i{position:absolute;top:1px;bottom:1px;width:10px;border-radius:5px;background:#35f5a0;box-shadow:0 0 10px #35f5a0}" +
    ".pfd .hud{position:absolute;top:8px;left:50%;transform:translateX(-50%);font:11px ui-monospace,monospace;background:#000a;padding:3px 10px;border-radius:8px;color:#35f5a0;white-space:nowrap}" +
    ".pfd .pl{position:absolute;left:50%;top:44%;transform:translateX(-50%);font-size:13px;color:#ffd84d;text-shadow:0 0 8px #000}" +
    ".pfd .warn{position:absolute;bottom:46px;left:50%;transform:translateX(-50%);border-radius:8px;padding:3px 12px;font:700 11px sans-serif;white-space:nowrap;border:1px solid}" +
    ".pfd .warn.ok{background:#35f5a022;border-color:#35f5a0;color:#35f5a0}.pfd .warn.no{background:#ff5c7a22;border-color:#ff5c7a;color:#ff5c7a}.pfd .warn.fl{background:#fbbf2422;border-color:#fbbf24;color:#fbbf24}" +
    ".lg .chk{display:flex;gap:6px;font-size:11px}.lg .chk div{flex:1;text-align:center;padding:6px;border-radius:8px;border:1px solid #2c3354;background:#14182b;color:#8b93b8}.lg .chk .ok{border-color:#2f7d52;color:#6ee7a0;background:#13261c}" +
    ".lg .ctl{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:7px}.lg .bt{background:linear-gradient(160deg,#ffffff16,#ffffff08);border:1px solid #7c6bff55;border-radius:12px;padding:12px 4px;text-align:center;font-weight:700;font-size:13px;color:#fff;font-family:inherit}" +
    ".lg .bt:active{border-color:#22d3ee;box-shadow:0 0 14px #22d3ee66}.lg .bt.wide{grid-column:span 4;background:linear-gradient(90deg,#7c6bff,#22d3ee);color:#06041a;border:0;font-size:15px;box-shadow:0 0 22px #7c6bff88}" +
    ".lg .sw{display:grid;gap:8px;grid-template-columns:1fr 1fr}.lg .sw button{background:linear-gradient(160deg,#ffffff16,#ffffff08);border:1px solid #7c6bff55;border-radius:12px;padding:16px 8px;font-size:15px;font-weight:700;color:#fff;font-family:inherit}" +
    ".lg .sw button.ok{border-color:#35f5a0;background:#35f5a022}.lg .sw button.no{border-color:#ff5c7a;background:#ff5c7a22;animation:shk .25s}" +
    "@keyframes shk{25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}";
  document.head.appendChild(css);
  const S = () => window.SFX || { tap() {}, ok() {}, bad() {} };

  const WX = [
    { n: "День", sky: ["#1d4ed8", "#7dd3fc"], gnd: ["#4d7c3a", "#2f5a2a"], wind: 0.6, say: "ясно" },
    { n: "Закат", sky: ["#4a1d6b", "#fb923c"], gnd: ["#3d3a2a", "#241f1a"], wind: 0.9, say: "закат, лёгкая болтанка" },
    { n: "Ночь", sky: ["#050816", "#1b2a52"], gnd: ["#0b1220", "#05080f"], wind: 1.2, say: "ночь, боковой ветер" }
  ];
  const ITEMS = ["Шасси", "Закрылки", "Фары", "Тормоза"];

  function pilot2(done) {
    const wx = pick(WX), wrap = el("div", "lg"); stage.appendChild(wrap);
    let raf = 0, lock = false; cleanup = () => { cancelAnimationFrame(raf); lock = true; };
    let checkScore = 100;

    /* ---- этап 1: предполётный чек-лист ---- */
    function checklist() {
      hint.textContent = "Этап 1/2 · Нажимай пункты в порядке, который назвал диспетчер";
      const order = shuffle(ITEMS).slice(0, 3); let k = 0, t0 = performance.now(); const LIM = 14;
      wrap.innerHTML = "";
      wrap.appendChild(el("div", "atc", "🎧 <b>Диспетчер:</b> «Рейс 417, предпосадочная проверка: " + order.map((x, i) => (i + 1) + ") " + x.toLowerCase()).join(", ") + "»<br><small>Погода: " + wx.say + ". Нажми по порядку</small>"));
      const chk = el("div", "chk", order.map(x => "<div>○ " + x + "</div>").join("")); wrap.appendChild(chk);
      const sw = el("div", "sw"); wrap.appendChild(sw);
      shuffle(ITEMS).forEach(it => {
        const b = el("button", "", ({ "Шасси": "🛞", "Закрылки": "🪽", "Фары": "💡", "Тормоза": "🛑" })[it] + " " + it);
        b.onclick = () => {
          if (lock) return;
          if (it === order[k]) { b.classList.add("ok"); b.disabled = true; chk.children[k].className = "ok"; chk.children[k].textContent = "✓ " + it; k++; S().tap(); if (k === 3) { S().ok(); checkScore = clamp(100 - Math.max(0, (performance.now() - t0) / 1000 - 6) * 6 - (100 - checkScore), 40, 100); setTimeout(approach, 700); } }
          else { b.classList.remove("no"); void b.offsetWidth; b.classList.add("no"); checkScore = Math.max(40, checkScore - 20); S().bad(); }
        };
        sw.appendChild(b);
      });
      const tick = () => { const left = LIM - ((performance.now() - t0) / 1000) * FAST; setTime(left / LIM); if (left <= 0) { checkScore = Math.min(checkScore, 50); approach(); return; } raf = requestAnimationFrame(tick); };
      tick();
    }

    /* ---- этап 2: заход на посадку ---- */
    function approach() {
      cancelAnimationFrame(raf); if (lock) return;
      hint.textContent = "Этап 2/2 · держи зелёные шарики по центру, у полосы жми «Выровнять»";
      wrap.innerHTML = "";
      const D0 = 100, DUR = 24;                     // «дистанция» 100 → 0 за ~24 с
      let d = D0, e = 18, ev = 0, x = (Math.random() - .5) * 0.5, xv = 0, wind = 0, wt = 0;
      let sumE = 0, sumX = 0, n = 0, flared = false, fl = null, last = performance.now(), over = false, t0 = last;
      wrap.appendChild(el("div", "atc", "🎧 <b>Диспетчер:</b> «Рейс 417, ВПП 24, " + wx.say + ", посадку разрешаю»<br><small>⬆⬇ глиссада · ◀ ▶ ось полосы</small>"));
      const pfd = el("div", "pfd");
      pfd.innerHTML = "<div class='sky'></div><div class='gnd'></div><div class='rw'></div><div class='cl'></div>" +
        "<div class='hud' id='hud'></div><div class='tape l'><small>УЗЛЫ</small><b id='spd'>140</b></div><div class='tape r'><small>ФУТЫ</small><b id='alt'>0</b></div>" +
        "<div class='gs'><i id='gsd'></i></div><div class='ls'><i id='lsd'></i></div><div class='pl'>— ✈ —</div><div class='warn ok' id='wn'>ГЛИССАДА ✓</div>";
      pfd.querySelector(".sky").style.background = "linear-gradient(" + wx.sky[0] + "," + wx.sky[1] + ")";
      pfd.querySelector(".gnd").style.background = "linear-gradient(" + wx.gnd[0] + "," + wx.gnd[1] + ")";
      wrap.appendChild(pfd);
      const ctl = el("div", "ctl");
      const mk = (txt, fn) => { const b = el("button", "bt", txt); b.onclick = () => { if (!over) { fn(); S().tap(); } }; ctl.appendChild(b); return b; };
      mk("⬆ Выше", () => { ev += 7; }); mk("⬇ Ниже", () => { ev -= 7; }); mk("◀", () => { xv -= 0.22; }); mk("▶", () => { xv += 0.22; });
      const fb = el("button", "bt wide", "🛬 ВЫРАВНЯТЬ"); fb.onclick = () => { if (!over && !flared) { flared = true; fl = { d, e }; } }; ctl.appendChild(fb);
      wrap.appendChild(ctl);
      const $ = s => pfd.querySelector(s), rw = $(".rw"), cl = $(".cl"), hud = $("#hud"), alt = $("#alt"), spd = $("#spd"), gsd = $("#gsd"), lsd = $("#lsd"), wn = $("#wn");

      function frame(now) {
        if (lock) return;
        const dt = Math.min(0.05, (now - last) / 1000) * FAST; last = now;
        d -= (D0 / DUR) * dt;
        wt += dt; wind += (Math.random() - .5) * wx.wind * 0.9 * dt - wind * 0.35 * dt;
        ev += (Math.random() - .5) * wx.wind * 26 * dt;        // болтанка по высоте
        ev *= (1 - 0.8 * dt); e += ev * dt;                    // e: отклонение от глиссады (в футах)
        xv += wind * 0.9 * dt; xv *= (1 - 0.6 * dt); x += xv * dt;
        e = clamp(e, -45, 45); x = clamp(x, -1.4, 1.4);
        if (d > 8) { sumE += Math.abs(e); sumX += Math.abs(x); n++; }
        const ideal = 12 + d * 5.2;
        alt.textContent = Math.max(0, Math.round(ideal + e));
        spd.textContent = Math.round(140 - (D0 - d) * 0.12 + e * -0.1);
        hud.textContent = "ВПП 24 · " + (Math.max(0, d) * 0.016).toFixed(1) + " км";
        // перспектива полосы
        const sc = 0.18 + (1 - clamp(d / D0, 0, 1)) * 1.6, off = -x * 55 * sc + e * -0.4;
        rw.style.setProperty("--w", (62 * sc).toFixed(1) + "px"); rw.style.setProperty("--h", (170 * sc).toFixed(1) + "px");
        rw.style.transform = "translateX(calc(-50% + " + (-x * 70 * sc).toFixed(1) + "px)) translateY(" + (-e * 0.5).toFixed(1) + "px)";
        cl.style.height = (130 * sc).toFixed(1) + "px"; cl.style.transform = "translateX(calc(-50% + " + (-x * 70 * sc).toFixed(1) + "px)) translateY(" + (-e * 0.5).toFixed(1) + "px)";
        gsd.style.top = (50 + clamp(e / 45, -1, 1) * 46) + "%"; lsd.style.left = (50 + clamp(x / 1.4, -1, 1) * 46) + "%";
        const gsBad = Math.abs(e) > 18, lsBad = Math.abs(x) > 0.55;
        gsd.style.background = gsBad ? "#ff5c7a" : "#35f5a0"; lsd.style.background = lsBad ? "#ff5c7a" : "#35f5a0";
        const canFlare = d < 14 && d > 0;
        wn.className = "warn " + (gsBad || lsBad ? "no" : canFlare ? "fl" : "ok");
        wn.textContent = gsBad ? (e > 0 ? "СЛИШКОМ ВЫСОКО" : "СЛИШКОМ НИЗКО") : lsBad ? "УХОД С ОСИ" : canFlare ? "ВЫРАВНИВАЙ СЕЙЧАС!" : "ГЛИССАДА ✓";
        if (gsBad || lsBad) { if (!frame.w) { S().bad(); frame.w = 1; setTimeout(() => (frame.w = 0), 900); } }
        setTime(d / D0);
        pill.textContent = Math.round(clamp(100 - (sumE / Math.max(1, n)) * 1.6 - (sumX / Math.max(1, n)) * 40, 0, 100));
        if (flared || d <= 0) { finish(); return; }
        raf = requestAnimationFrame(frame);
      }
      function finish() {
        over = true; cancelAnimationFrame(raf);
        const avgE = sumE / Math.max(1, n), avgX = sumX / Math.max(1, n);
        let land = 100 - avgE * 1.6 - avgX * 40, msg;
        if (!flared) { land -= 35; msg = "Не выровнял: жёсткая посадка 💥"; }
        else if (fl.d > 14) { land -= 40; msg = "Выровнял слишком рано: ушёл на второй круг ↩"; }
        else { const late = fl.d; land -= Math.abs(fl.e) * 0.8 + (late < 2 ? 15 : 0); msg = Math.abs(fl.e) < 8 && Math.abs(x) < 0.4 ? "Мягкое касание 🛬 Аплодисменты в салоне!" : "Посадка прошла, но жёстковато"; }
        if (Math.abs(x) > 1) { land -= 25; msg = "Выкатился за пределы полосы ⚠"; }
        land = clamp(land, 0, 100);
        wn.className = "warn " + (land > 60 ? "ok" : "no"); wn.textContent = msg;
        land > 60 ? S().ok() : S().bad();
        const total = Math.round(0.2 * checkScore + 0.8 * land);
        pill.textContent = total;
        setTimeout(() => done(total), 2200);
      }
      raf = requestAnimationFrame(frame);
    }
    checklist();
  }
  JOBS.pil = ["✈️ Пилот", "Заход на посадку: держи глиссаду и выровняй самолёт", pilot2];
})();
