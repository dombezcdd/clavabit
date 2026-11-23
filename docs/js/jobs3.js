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

  const BUGS = [
    [["x = 5", "if x = 5:", "    print('ok')"], 1, "main.py", "SyntaxError: invalid syntax. Maybe you meant '==' ?"],
    [["let a = [1, 2, 3];", "for (let i = 0; i <= a.length; i++) {", "  console.log(a[i]);", "}"], 1, "app.js", "undefined на последнем шаге: i <= a.length выходит за массив"],
    [["def add(a, b):", "    return a - b", "print(add(2, 3))  # ждём 5"], 1, "calc.py", "assert add(2, 3) == 5, получили -1"],
    [["name = input()", "print('Привет, ' + nme)"], 1, "main.py", "NameError: name 'nme' is not defined"],
    [["const s = 'abc';", "s.push('d');", "console.log(s);"], 1, "app.js", "TypeError: s.push is not a function"],
    [["a = [1, 2, 3]", "print(a[3])  # третий элемент"], 1, "main.py", "IndexError: list index out of range"],
    [["import os", "print(os.getcwdd())"], 1, "main.py", "AttributeError: module 'os' has no attribute 'getcwdd'"],
    [["for i in range(3)", "    print(i)"], 0, "main.py", "SyntaxError: expected ':'"],
    [["SELEKT * FROM users", "WHERE name = 'Аня'"], 0, "query.sql", "Syntax error near 'SELEKT'"],
    [["total = 0", "for n in [1, 2, 3]:", "    total = n", "print(total)  # ждём 6"], 2, "sum.py", "assert total == 6, получили 3"],
    [["def is_even(n):", "    return n % 2 == 1", "print(is_even(4))  # ждём True"], 1, "even.py", "assert is_even(4) is True, получили False"],
    [["let list = [3, 1, 2];", "list.sort();", "console.log(list.lenght);"], 2, "app.js", "undefined: у массива нет свойства 'lenght'"],
    [["name = 'Аня'", "print('Привет, ' + name + '!)"], 1, "main.py", "SyntaxError: unterminated string literal"],
    [["for (let i = 0; i < 3; i--) {", "  console.log(i);", "}"], 0, "loop.js", "Timeout: цикл не завершается (i уменьшается)"],
    [["price = '100'", "print(price + 20)  # ждём 120"], 1, "main.py", "TypeError: can only concatenate str (not \"int\") to str"]
  ];
  const FILLS = [
    [["def square(x):", "    return ____", "print(square(4))  # 16"], 1, "x * x", ["x + x", "x * 2"], "square.py", "assert square(4) == 16"],
    [["for i in ____(3):", "    print(i)"], 0, "range", ["len", "print"], "loop.py", "нужно вывести 0 1 2"],
    [["let ok = true;", "if (!ok) {", "  alert('Ошибка');", "} ____ {", "  alert('Всё хорошо');", "}"], 3, "else", ["elif", "then"], "app.js", "SyntaxError: Unexpected token"],
    [["nums = [1, 2, 3]", "print(____(nums))  # 6"], 1, "sum", ["len", "max"], "main.py", "assert result == 6"],
    [["let a = [];", "a.____(5);", "console.log(a);  // [5]"], 1, "push", ["add", "append"], "app.js", "TypeError: a.add is not a function"],
    [["text = 'привет'", "print(text.____())  # ПРИВЕТ"], 1, "upper", ["lower", "len"], "main.py", "ждём ПРИВЕТ"],
    [["SELECT name ____ users;"], 0, "FROM", ["IN", "OF"], "query.sql", "Syntax error near 'users'"],
    [["x = 10", "while x ____ 0:", "    x -= 3"], 1, ">", ["<", "=="], "loop.py", "цикл должен идти, пока x больше нуля"]
  ];
  const PRED = [
    [["x = 3", "y = x * 2", "print(y + 1)"], "7", ["6", "9"], "main.py"],
    [["a = [1, 2, 3]", "a.append(4)", "print(len(a))"], "4", ["3", "5"], "main.py"],
    [["s = 'ab'", "print(s * 3)"], "ababab", ["ab3", "ababa"], "main.py"],
    [["n = 5", "while n > 2:", "    n -= 1", "print(n)"], "2", ["3", "1"], "main.py"],
    [["print(10 // 3)"], "3", ["3.33", "4"], "main.py"],
    [["print('5' + '5')"], "55", ["10", "5"], "main.py"],
    [["print(len('привет'))"], "6", ["7", "5"], "main.py"],
    [["console.log(1 + '2');"], "12", ["3", "NaN"], "app.js"]
  ];

  function ideHtml(lines, file, blankIdx, bugIdx, tabState) {
    const gut = lines.map((_, i) => i + 1).join("<br>");
    const src = lines.map((l, i) => {
      let h = hl(l);
      if (blankIdx === i) h = h.replace("____", "<span class='blank' id='blank'>____</span>");
      return "<span class='line' id='ln" + i + "'>" + (h || "&nbsp;") + "</span>";
    }).join("");
    const mini = lines.map((_, i) => "<i id='mm" + i + "'></i>").join("");
    return "<div class='ide'><div class='tabs'><div class='on'>" + file + " <span id='dot' class='x'>●</span></div><div>tests.py</div></div>" +
      "<div class='code'><div class='gut'>" + gut + "</div><div class='src'>" + src + "</div><div class='mini'>" + mini + "</div></div></div>";
  }

  function coder2(done) {
    const bugs = shuffle(BUGS).slice(0, 3).map(b => ({ t: "bug", lines: b[0], idx: b[1], file: b[2], err: b[3] }));
    const fills = shuffle(FILLS).slice(0, 2).map(f => ({ t: "fill", lines: f[0], idx: f[1], right: f[2], wrong: f[3], file: f[4], err: f[5] }));
    const preds = shuffle(PRED).slice(0, 2).map(p => ({ t: "pred", lines: p[0], right: p[1], wrong: p[2], file: p[3] }));
    const list = shuffle([...bugs, ...fills, ...preds]);
    const TASK = ["Прод упал после твоего коммита. Найди баг, пока не позвонил заказчик.", "Тимлид просит доделать функцию до обеда.", "Ревью кода: коллега ждёт, пока ты закончишь."];
    const PER = 12;
    let i = 0, total = 0, streak = 0, t0 = 0, raf = 0, lock = false;
    const wrap = el("div", "pg"); stage.appendChild(wrap);
    hint.textContent = "Чем быстрее ответ и длиннее серия, тем больше очков";

    function show() {
      if (i >= list.length) { cancelAnimationFrame(raf); return done(Math.min(100, Math.round(total / list.length))); }
      const r = list[i]; lock = false; wrap.innerHTML = "";
      const task = el("div", "task");
      const title = r.t === "bug" ? "🐞 Найди строку с багом" : r.t === "fill" ? "🧩 Допиши код вместо ____" : "▶ Что выведет программа?";
      task.innerHTML = "<b>Раунд " + (i + 1) + "/" + list.length + ".</b> " + pick(TASK) + "<br>" + title;
      const cb = el("div", "combo" + (streak ? "" : " off"), "серия x" + Math.max(1, streak) + " 🔥");
      const ide = el("div"); ide.innerHTML = ideHtml(r.lines, r.file, r.t === "fill" ? r.idx : -1);
      const term = el("div", "term");
      let tb;
      if (r.t === "bug") tb = "<span class='d'>$</span> pytest " + r.file + "<br><span class='r'>FAILED</span> " + esc(r.err).replace(/&nbsp;/g, " ") + "<br><span class='y'>1 failed</span>, <span class='g'>2 passed</span>";
      else if (r.t === "fill") tb = "<span class='d'>$</span> run " + r.file + "<br><span class='r'>ERROR</span> " + esc(r.err).replace(/&nbsp;/g, " ") + "<br><span class='d'>вставь недостающее слово</span>";
      else tb = "<span class='d'>$ python " + r.file + "</span><br><span class='d'>… выполняется</span>";
      term.innerHTML = "<div class='h'><span>ТЕРМИНАЛ</span><span class='d'>" + (r.file.endsWith(".js") ? "node 22" : r.file.endsWith(".sql") ? "sqlite" : "python 3.12") + "</span></div><div class='b' id='tb'>" + tb + "</div>";
      const opts = el("div", "opts");
      let options;
      if (r.t === "bug") options = r.lines.map((l, k) => ({ html: "<span class='n'>" + (k + 1) + "</span><span>" + hl(l) + "</span>", ok: k === r.idx }));
      else options = shuffle([{ html: hl(r.right), ok: true }, ...r.wrong.map(w => ({ html: hl(w), ok: false }))]);
      options = r.t === "bug" ? options : options.map(o => o);
      if (r.t === "pred") options = shuffle([{ html: esc(r.right), ok: true }, ...r.wrong.map(w => ({ html: esc(w), ok: false }))]);
      options.forEach(op => {
        const b = el("button", "o"); b.innerHTML = op.html;
        b.onclick = () => answer(b, op, r, term);
        op.node = b; opts.appendChild(b);
      });
      r.opts = options;
      const sb = el("div", "sbar"); sb.innerHTML = "<span>⎇ main · " + (r.t === "bug" ? "1 ошибка" : "в работе") + "</span><span>UTF-8</span>";
      wrap.append(task, cb, ide, term, opts, sb);
      t0 = performance.now(); cancelAnimationFrame(raf); tick();
    }
    function tick() {
      const left = PER - ((performance.now() - t0) / 1000) * FAST;
      setTime(left / PER);
      if (left <= 0 && !lock) { answer(null, null, list[i], wrap.querySelector(".term")); return; }
      raf = requestAnimationFrame(tick);
    }
    function answer(btn, op, r, term) {
      if (lock) return; lock = true; cancelAnimationFrame(raf);
      const left = clamp(PER - ((performance.now() - t0) / 1000) * FAST, 0, PER);
      const good = !!(op && op.ok);
      let pts = 0;
      if (good) { streak++; pts = (60 + 40 * (left / PER)) * (1 + Math.min(0.3, 0.1 * (streak - 1))); btn.classList.add("ok"); haptic("success"); }
      else { streak = 0; if (btn) btn.classList.add("bad"); haptic("error"); }
      pts = Math.min(100, pts);
      total += pts; pill.textContent = Math.round(total / list.length);
      const tb = wrap.querySelector("#tb");
      if (r.t === "bug") {
        const ln = wrap.querySelector("#ln" + r.idx), mm = wrap.querySelector("#mm" + r.idx);
        if (ln) { ln.classList.add(good ? "fixed" : "sel"); }
        if (mm) mm.className = "r";
        const dot = wrap.querySelector("#dot"); if (dot && good) { dot.className = "okc"; dot.textContent = "✓"; }
        tb.innerHTML += good ? "<br><span class='g'>PASSED</span> строка " + (r.idx + 1) + " исправлена, <span class='g'>3 passed</span> ✓" : "<br><span class='r'>Баг был в строке " + (r.idx + 1) + "</span>, тесты всё ещё красные";
      } else if (r.t === "fill") {
        const bl = wrap.querySelector("#blank");
        if (bl) { bl.textContent = r.right; bl.classList.add(good ? "ok" : "bad"); }
        tb.innerHTML += good ? "<br><span class='g'>OK</span> код собран, тест зелёный ✓" : "<br><span class='r'>Правильно: " + esc(r.right) + "</span>";
      } else {
        tb.innerHTML = "<span class='d'>$ python " + r.file + "</span><br>" + (good ? "<span class='g'>" + esc(r.right) + "</span><br><span class='g'>✓ угадал вывод</span>" : "<span class='y'>" + esc(r.right) + "</span><br><span class='r'>вывод был другим</span>");
      }
      const cb = wrap.querySelector(".combo"); if (cb && good) { cb.className = "combo pop"; cb.textContent = "серия x" + streak + " 🔥"; }
      if (!good && r.opts) r.opts.forEach(x => { if (x.ok && x.node) x.node.classList.add("ok"); });
      wrap.querySelectorAll(".o").forEach(n => { n.disabled = true; });
      i++; setTimeout(show, good ? 1100 : 1700);
    }
    cleanup = () => { cancelAnimationFrame(raf); };
    show();
  }
  JOBS.prg = ["💻 Программист", "Чини баги в настоящей IDE: серия ответов даёт бонус", coder2];
})();
