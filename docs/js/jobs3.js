"use strict";
/* Программист 2.0: настоящая IDE (вкладки, подсветка, терминал pytest), баги, пропуски, «что выведет», серия ответов */
(function () {
  const css = document.createElement("style");
  css.textContent =
    ".pg{display:flex;flex-direction:column;gap:10px;height:100%;overflow:auto;padding-bottom:6px}" +
    ".pg .task{padding:10px 12px;background:#161a2d;border:1px solid #2c3050;border-radius:12px;font-size:13px;line-height:1.4;color:#d7dcf5}" +
    ".pg .task b{color:#fbbf24}.pg .task .r{color:#f87171}.pg .task .g{color:#4ade80}" +
    ".ide{border-radius:14px;overflow:hidden;border:1px solid #2c3050;background:#10131f;box-shadow:0 10px 30px rgba(0,0,0,.5);text-align:left}" +
    ".tabs{display:flex;background:#0c0e18;font:12px ui-monospace,Menlo,monospace;overflow:hidden}" +
    ".tabs div{padding:8px 12px;color:#7d86ad;border-right:1px solid #1b1f33;white-space:nowrap}.tabs .on{background:#10131f;color:#e6e9ff;border-top:2px solid #6d8cff}" +
    ".tabs .x{color:#f87171}.tabs .okc{color:#4ade80}" +
    ".code{display:flex;font:13px/1.75 ui-monospace,Menlo,Consolas,monospace;padding:8px 0;color:#d7dcf5}" +
    ".gut{width:34px;text-align:right;padding-right:10px;color:#4a5178;user-select:none;flex:none}" +
    ".src{flex:1;white-space:pre;overflow:hidden}.src .line{display:block;padding-left:6px;border-left:3px solid transparent}" +
    ".src .line.sel{background:rgba(248,113,113,.14);border-left-color:#f87171}.src .line.fixed{background:rgba(74,222,128,.12);border-left-color:#4ade80}" +
    ".mini{width:34px;padding:8px 6px;flex:none}.mini i{display:block;height:3px;border-radius:2px;background:#2f3658;margin-bottom:5px}.mini i.r{background:#7a2b2b}" +
    ".kw{color:#c792ea}.fn{color:#82aaff}.st{color:#ecc48d}.nm{color:#f78c6c}.cm{color:#5c6a8a}" +
    ".err{text-decoration:wavy underline #f87171;text-underline-offset:3px}" +
    ".blank{display:inline-block;min-width:64px;border-bottom:2px dashed #fbbf24;color:#fbbf24;text-align:center}.blank.ok{border-bottom-color:#4ade80;color:#4ade80}.blank.bad{border-bottom-color:#f87171;color:#f87171}" +
    ".term{border-radius:12px;background:#080a12;border:1px solid #2c3050;font:12px/1.6 ui-monospace,Menlo,monospace;overflow:hidden;text-align:left;color:#d7dcf5}" +
    ".term .h{background:#0c0e18;padding:6px 10px;color:#7d86ad;display:flex;justify-content:space-between}" +
    ".term .b{padding:8px 10px;min-height:64px}.term .g{color:#4ade80}.term .r{color:#f87171}.term .y{color:#fbbf24}.term .d{color:#6b739c}" +
    ".pg .opts{display:grid;gap:8px}.pg .o{background:#161a2d;border:1px solid #2c3050;border-radius:12px;padding:11px 12px;font:13px ui-monospace,Menlo,monospace;display:flex;gap:10px;color:#e6e9ff;text-align:left;width:100%}" +
    ".pg .o .n{color:#5a638d;flex:none}.pg .o.ok{border-color:#4ade80;background:#13261c}.pg .o.bad{border-color:#f87171;background:#2a1620}" +
    ".combo{align-self:flex-end;background:linear-gradient(135deg,#fbbf24,#fb7185);color:#1b1020;font-weight:800;border-radius:12px;padding:3px 10px;font-size:13px;box-shadow:0 4px 14px rgba(251,113,133,.5);transition:transform .15s}" +
    ".combo.pop{transform:scale(1.25) rotate(4deg)}.combo.off{opacity:.35;background:#2c3050;color:#9aa3c7;box-shadow:none}" +
    ".jira{background:linear-gradient(160deg,#1a1f33,#141829);border:1px solid #2c3354;border-radius:12px;padding:9px 11px;font-size:12px;box-shadow:0 0 18px #7c6bff22}" +
    ".jira .r1{display:flex;gap:6px;align-items:center;margin-bottom:5px}.jira .key{color:#7c9bff;font-weight:800}.jira .tag{font-size:10px;font-weight:800;padding:2px 6px;border-radius:5px}" +
    ".jira .hi{background:#4a1d26;color:#ff8a8a}.jira .md{background:#4a3a14;color:#fbbf24}.jira .lo{background:#1d3a2a;color:#6ee7a0}.jira .bg{background:#2a2450;color:#b4a8ff}" +
    ".jira p{color:#e6e9ff;font-size:13px;line-height:1.35;margin:0}.jira small{color:#8b93b8}" +
    ".ttl{background:#0c0e18;padding:6px 10px;display:flex;align-items:center;gap:6px;font:11px sans-serif;color:#7d86ad}.ttl i{width:9px;height:9px;border-radius:50%;display:inline-block}" +
    ".vsb{display:flex}.act{width:30px;background:#0c0e18;display:flex;flex-direction:column;gap:12px;align-items:center;padding-top:10px;font-size:13px;opacity:.85;flex:none}.ed{flex:1;min-width:0}" +
    ".bc{padding:4px 10px;font:10.5px sans-serif;color:#7d86ad}.prob{background:#0e1019;border-top:1px solid #2c3050;padding:5px 10px;font:11.5px sans-serif;color:#8b93b8}.prob b{color:#ff8a8a}.prob b.g{color:#4ade80}" +
    ".stat{background:#3b5bdb;color:#fff;font:11px sans-serif;padding:4px 10px;display:flex;gap:12px}.stat span:last-child{margin-left:auto}" +
    ".ci{display:flex;gap:5px;font-size:11px}.ci div{flex:1;text-align:center;padding:7px 2px;border-radius:9px;background:#161a2d;border:1px solid #2c3050;color:#8b93b8;transition:all .3s}" +
    ".ci .ok{border-color:#2f7d52;color:#4ade80;background:#13261c;box-shadow:0 0 10px #4ade8044}.ci .run{border-color:#fbbf24;color:#fbbf24}.ci .no{border-color:#f87171;color:#f87171;background:#2a1620}" +
    ".sbar{background:#3b5bdb;color:#fff;font-size:11px;padding:6px 12px;display:flex;justify-content:space-between;border-radius:8px}";
  document.head.appendChild(css);

  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
  const KW = "def|return|if|else|elif|for|in|while|let|const|var|function|import|True|False|true|false|SELECT|FROM|WHERE|input|and|or|not";
  const FN = "print|len|range|sum|max|min|console|log|upper|lower|append|push|sort";
  const RE = new RegExp("(#.*|\\/\\/.*)|('[^']*'?|\"[^\"]*\"?)|\\b(" + KW + ")\\b|\\b(" + FN + ")\\b|\\b(\\d+)\\b", "g");
  function hl(line, wave) {
    let out = "", last = 0, m;
    RE.lastIndex = 0;
    while ((m = RE.exec(line))) {
      out += esc(line.slice(last, m.index));
      const cls = m[1] ? "cm" : m[2] ? "st" : m[3] ? "kw" : m[4] ? "fn" : "nm";
      out += "<span class='" + cls + "'>" + esc(m[0]) + "</span>";
      last = m.index + m[0].length;
    }
    out += esc(line.slice(last));
    return wave ? "<span class='err'>" + out + "</span>" : out;
  }

  /* ===== звук и вибрация ===== */
  let AC = null;
  function beep(f, d, type, vol) {
    try {
      AC = AC || new (window.AudioContext || window.webkitAudioContext)();
      const o = AC.createOscillator(), g = AC.createGain();
      o.type = type || "square"; o.frequency.value = f; g.gain.value = vol || 0.04;
      o.connect(g); g.connect(AC.destination); o.start(); g.gain.exponentialRampToValueAtTime(0.0001, AC.currentTime + d); o.stop(AC.currentTime + d);
    } catch (e) {}
  }
  const sfx = {
    tap() { beep(660, 0.05); try { tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred("light"); } catch (e) {} },
    ok() { beep(523, 0.12); setTimeout(() => beep(784, 0.18), 110); haptic("success"); },
    bad() { beep(180, 0.3, "sawtooth", 0.05); haptic("error"); }
  };

  /* ===== программы для сборки: строки по порядку, ложные строки, тесты ===== */
  const PROGS = [
    { lvl: 0, file: "greet.py", task: "Сделай функцию приветствия", tests: ["greet('Аня') == 'Привет, Аня'"],
      code: ["def greet(name):", "    text = 'Привет, ' + name", "    return text"], fake: ["    print(text)", "    return name"] },
    { lvl: 0, file: "bigger.py", task: "Верни большее из двух чисел", tests: ["bigger(3, 7) == 7", "bigger(9, 2) == 9"],
      code: ["def bigger(a, b):", "    if a > b:", "        return a", "    return b"], fake: ["    if a < b:", "    return a"] },
    { lvl: 0, file: "double.py", task: "Удвой каждое число списка", tests: ["double([1, 2]) == [2, 4]"],
      code: ["def double(nums):", "    out = []", "    for n in nums:", "        out.append(n * 2)", "    return out"], fake: ["        out.append(n)", "    return nums"] },
    { lvl: 1, file: "evens.py", task: "Посчитай сумму чётных чисел", tests: ["sum_even([1, 2, 3, 4]) == 6"],
      code: ["def sum_even(nums):", "    total = 0", "    for n in nums:", "        if n % 2 == 0:", "            total += n", "    return total"], fake: ["        if n % 2 == 1:", "    total = 1"] },
    { lvl: 1, file: "count.py", task: "Посчитай буквы «а» в строке", tests: ["count_a('banana') == 3"],
      code: ["def count_a(s):", "    n = 0", "    for ch in s:", "        if ch == 'a':", "            n += 1", "    return n"], fake: ["        if ch != 'a':", "    n = len(s)"] },
    { lvl: 1, file: "fizz.py", task: "Fizz для чисел, кратных трём", tests: ["fizz(9) == 'Fizz'", "fizz(4) == '4'"],
      code: ["def fizz(n):", "    if n % 3 == 0:", "        return 'Fizz'", "    return str(n)"], fake: ["    if n % 3 == 1:", "    return n"] },
    { lvl: 2, file: "fact.py", task: "Посчитай факториал числа", tests: ["fact(5) == 120", "fact(1) == 1"],
      code: ["def fact(n):", "    r = 1", "    for i in range(1, n + 1):", "        r *= i", "    return r"], fake: ["    r = 0", "    for i in range(n):", "        r += i"] },
    { lvl: 2, file: "maxlist.py", task: "Найди максимум в списке", tests: ["top([4, 9, 2]) == 9"],
      code: ["def top(nums):", "    best = nums[0]", "    for n in nums:", "        if n > best:", "            best = n", "    return best"], fake: ["        if n < best:", "    best = 0"] },
    { lvl: 2, file: "pal.py", task: "Проверь, палиндром ли слово", tests: ["pal('шалаш') is True", "pal('дом') is False"],
      code: ["def pal(w):", "    rev = w[::-1]", "    if rev == w:", "        return True", "    return False"], fake: ["    rev = w", "        return False"] }
  ];
  const LV = [{ name: "Стажёр", sec: 45 }, { name: "Миддл", sec: 55 }, { name: "Сеньор", sec: 65 }];

  function coder3(done) {
    const set = [0, 1, 2].map(l => pick(PROGS.filter(p => p.lvl === l)));
    let li = 0, total = 0, raf = 0, lock = false, t0 = 0, runs = 0;
    const wrap = el("div", "pg"); stage.appendChild(wrap);
    hint.textContent = "Нажимай блоки: они встают в программу по порядку. Тапни по строке, чтобы убрать";
    cleanup = () => { cancelAnimationFrame(raf); };

    function level() {
      const P = set[li], L = LV[li], n = P.code.length;
      lock = false; runs = 0; wrap.innerHTML = "";
      const slots = new Array(n).fill(null);                   // индексы блоков в слотах
      const pool = shuffle(P.code.map((t, i) => ({ t, i, fake: false })).concat(P.fake.map((t, i) => ({ t, i: -1 - i, fake: true }))));
      const pr = ["lo'>LOW", "md'>MEDIUM", "hi'>HIGH"][li], key = "PAY-" + (100 + Math.floor(Math.random() * 900));
      const task = el("div", "jira", "<div class='r1'><span class='key'>" + key + "</span><span class='tag " + pr + "</span><span class='tag bg'>" + (li === 2 ? "Bug" : "Task") + "</span><small style='margin-left:auto'>Уровень " + (li + 1) + "/3 · " + L.name + "</small></div><p>" + P.task + ": релиз в 18:00</p><small>💬 Тимлид: «Собери функцию из блоков, лишние блоки не нужны»</small>");
      const cb = el("div", "combo off", "попыток 3 · " + L.sec + " с");
      const ide = el("div", "ide");
      ide.innerHTML = "<div class='ttl'><i style='background:#ff5f57'></i><i style='background:#febc2e'></i><i style='background:#28c840'></i><span style='margin:0 auto'>" + P.file + " — shop-backend — VS Code</span></div>";
      const vsb = el("div", "vsb"); const edc = el("div", "ed");
      vsb.append(el("div", "act", "<span>📁</span><span>🔍</span><span>⎇</span><span>🐞</span>"), edc); ide.appendChild(vsb);
      edc.innerHTML = "<div class='tabs'><div class='on'>" + P.file + " <span id='dot' class='x'>●</span></div><div>test_" + P.file + "</div></div><div class='bc'>shop › backend › " + P.file + "</div>";
      const code = el("div", "code"); const gut = el("div", "gut", P.code.map((_, i) => i + 1).join("<br>"));
      const src = el("div", "src"); code.append(gut, src); edc.appendChild(code);
      const prob = el("div", "prob", "⚠ ПРОБЛЕМЫ <b id='pc'>" + n + "</b> · пустых строк"); ide.appendChild(prob);
      const stat = el("div", "stat", "<span>⎇ fix/" + key + "</span><span id='lc'>⊗ " + n + "</span><span>Python</span>"); ide.appendChild(stat);
      const term = el("div", "term"); const tb = el("div", "b");
      term.innerHTML = "<div class='h'><span>ТЕРМИНАЛ</span><span class='d'>python 3.12</span></div>"; term.appendChild(tb);
      const pend = () => "<span class='d'>$</span> pytest " + P.file + "<br>" + P.tests.map(t => "<span class='d'>○ " + esc(t) + "</span>").join("<br>");
      tb.innerHTML = pend();
      const ci = el("div", "ci", "<div class='ok'>✓ Lint</div><div>○ Тесты</div><div>○ Build</div><div>○ Deploy</div>");
      const setCi = (st) => { [...ci.children].forEach((c, k) => { const v = st[k]; c.className = v || ""; c.textContent = ({ ok: "✓ ", run: "⏳ ", no: "✗ ", "": "○ " }[v || ""]) + ["Lint", "Тесты", "Build", "Deploy"][k] + (k === 3 && v === "ok" ? " 🚀" : ""); }); };
      const poolBox = el("div", "opts");
      const run = el("button", "o"); run.style.cssText = "justify-content:center;font-weight:800;background:#3b5bdb;border-color:#3b5bdb"; run.textContent = "▶ Запустить тесты"; run.disabled = true; run.style.opacity = .5;

      function draw() {
        src.innerHTML = ""; poolBox.innerHTML = "";
        slots.forEach((bi, si) => {
          const ln = el("span", "line", ""); ln.style.minHeight = "22px";
          if (bi == null) { ln.innerHTML = "<span class='cm'>" + esc("# строка " + (si + 1)) + "</span>"; ln.style.opacity = .55; }
          else { const b = pool.find(x => x.i === bi); ln.innerHTML = hl(b.t); ln.onclick = () => { if (lock) return; slots[si] = null; sfx.tap(); draw(); }; ln.style.cursor = "pointer"; }
          ln.id = "s" + si; src.appendChild(ln);
        });
        pool.forEach(b => {
          if (slots.includes(b.i)) return;
          const bt = el("button", "o"); bt.innerHTML = "<span>" + hl(b.t) + "</span>";
          bt.onclick = () => { if (lock) return; const k = slots.indexOf(null); if (k < 0) return; slots[k] = b.i; sfx.tap(); draw(); };
          poolBox.appendChild(bt);
        });
        const left = slots.filter(x => x == null).length;
        const pc = wrap.querySelector("#pc"); if (pc) { pc.textContent = left; pc.className = left ? "" : "g"; }
        const lc = wrap.querySelector("#lc"); if (lc) lc.textContent = left ? "⊗ " + left : "✓ 0";
        const full = slots.every(x => x != null);
        run.disabled = !full || lock; run.style.opacity = full && !lock ? 1 : .5;
      }
      run.onclick = () => {
        if (lock || !slots.every(x => x != null)) return;
        runs++; setCi(["ok", "run"]); const okAll = slots.every((bi, si) => bi === si);
        slots.forEach((bi, si) => { const ln = src.children[si]; ln.classList.remove("sel", "fixed"); ln.classList.add(bi === si ? "fixed" : "sel"); });
        if (okAll) { win(); return; }
        sfx.bad(); setCi(["ok", "no"]);
        tb.innerHTML = "<span class='d'>$</span> pytest " + P.file + "<br>" + P.tests.map(t => "<span class='r'>✗ " + esc(t) + "</span>").join("<br>") +
          "<br><span class='r'>FAILED</span> зелёные строки на месте, красные нет · попытка " + runs + "/3";
        cb.className = "combo off"; cb.textContent = "попыток " + Math.max(0, 3 - runs);
        if (runs >= 3) { give(false); return; }
        setTimeout(() => { slots.forEach((bi, si) => { if (bi !== si) slots[si] = null; }); draw(); }, 900);   // верные строки остаются
      };
      function win() { sfx.ok(); setCi(["ok", "ok", "run"]); setTimeout(() => setCi(["ok", "ok", "ok", "run"]), 500); setTimeout(() => { setCi(["ok", "ok", "ok", "ok"]); sfx.ok(); }, 1000); const dot = wrap.querySelector("#dot"); dot.className = "okc"; dot.textContent = "✓";
        tb.innerHTML = "<span class='d'>$</span> pytest " + P.file + "<br>" + P.tests.map(t => "<span class='g'>✓ " + esc(t) + "</span>").join("<br>") + "<br><span class='g'>PASSED</span> " + P.tests.length + " passed, деплой в прод 🚀";
        cb.className = "combo pop"; cb.textContent = "зелёный билд ✅"; give(true); }
      function give(ok) {
        lock = true; cancelAnimationFrame(raf); draw();
        const left = clamp(L.sec - ((performance.now() - t0) / 1000) * FAST, 0, L.sec);
        const pts = ok ? clamp(100 - (runs - 1) * 20 - 25 * (1 - left / L.sec), 35, 100) : 0;
        total += pts; pill.textContent = Math.round(total / 3);
        if (!ok) { slots.forEach((_, si) => { slots[si] = si; }); draw(); slots.forEach((_, si) => { const ln = src.children[si]; ln.classList.add("fixed"); });
          tb.innerHTML += "<br><span class='y'>Вот правильный порядок</span>"; }
        li++; setTimeout(() => (li >= 3 ? done(Math.round(total / 3)) : level()), ok ? 1500 : 2600);
      }
      function tick() {
        const left = L.sec - ((performance.now() - t0) / 1000) * FAST; setTime(left / L.sec);
        if (left <= 0 && !lock) { runs = Math.max(runs, 1); tb.innerHTML = "<span class='r'>TIMEOUT</span> время вышло, прод упал"; sfx.bad(); give(false); return; }
        raf = requestAnimationFrame(tick);
      }
      const sb = el("div", "sbar", "<span>⎇ main · собери " + n + " строк</span><span>UTF-8</span>");
      wrap.append(task, cb, ide, ci, term, poolBox, run, sb);
      draw(); t0 = performance.now(); cancelAnimationFrame(raf); tick();
    }
    level();
  }
  JOBS.prg = ["💻 Программист", "Собери программу из блоков кода: пройди тесты и задеплой", coder3];
})();
