"use strict";
/* Программист 2.0: редактор кода с подсветкой, поиск багов и заполнение пропусков */
(function () {
  const css = document.createElement("style");
  css.textContent =
    ".ed{background:#12141f;border:1px solid #2c3050;border-radius:14px;overflow:hidden;text-align:left;box-shadow:0 6px 22px rgba(0,0,0,.35)}" +
    ".ed .tab{display:flex;align-items:center;gap:6px;padding:8px 12px;background:#1b1e30;font:12px ui-monospace,Menlo,Consolas,monospace;color:#9aa3c7}" +
    ".ed .tab i{width:10px;height:10px;border-radius:50%;display:inline-block}" +
    ".ed pre{margin:0;padding:12px 4px 12px 0;font:14px/1.6 ui-monospace,Menlo,Consolas,monospace;color:#d7dcf5;white-space:pre-wrap}" +
    ".ed .ln{display:inline-block;width:30px;text-align:right;margin-right:12px;color:#4d5580;user-select:none}" +
    ".ed .kw{color:#c792ea}.ed .st{color:#ecc48d}.ed .nm{color:#f78c6c}.ed .cm{color:#637777}" +
    ".ed .blank{display:inline-block;min-width:70px;border-bottom:2px dashed #ffcb6b;color:#ffcb6b;text-align:center}" +
    ".ed .blank.ok{border-bottom-color:#4ade80;color:#4ade80}.ed .blank.bad{border-bottom-color:#f87171;color:#f87171}" +
    ".logbox{margin-top:10px;padding:10px 12px;border-radius:12px;font:13px ui-monospace,Menlo,Consolas,monospace;background:#12141f;border:1px solid #2c3050;color:#9aa3c7;min-height:20px}" +
    ".logbox.ok{color:#4ade80;border-color:#1f6b3f}.logbox.bad{color:#f87171;border-color:#7a2b2b}" +
    ".opt.line .ln{display:inline-block;width:22px;color:#6b739c;margin-right:8px}" +
    ".opt.line.ok{outline:2px solid #4ade80}.opt.line.bad{outline:2px solid #f87171}";
  document.head.appendChild(css);

  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/ /g, "&nbsp;");
  const KW = "def|return|if|else|elif|for|in|while|let|const|var|function|import|print|console|range|True|False|true|false|SELECT|FROM|WHERE|input";
  const RE = new RegExp("(#.*|\\/\\/.*)|('[^']*'?|\"[^\"]*\"?)|\\b(" + KW + ")\\b|\\b(\\d+)\\b", "g");
  function hl(line) {
    let out = "", last = 0, m;
    RE.lastIndex = 0;
    while ((m = RE.exec(line))) {
      out += esc(line.slice(last, m.index));
      const cls = m[1] ? "cm" : m[2] ? "st" : m[3] ? "kw" : "nm";
      out += "<span class='" + cls + "'>" + esc(m[0]) + "</span>";
      last = m.index + m[0].length;
    }
    return out + esc(line.slice(last));
  }
  function editor(lines, file, blankIdx) {
    let h = "<div class='ed'><div class='tab'><i style='background:#ff5f56'></i><i style='background:#ffbd2e'></i><i style='background:#27c93f'></i>&nbsp;" + file + "</div><pre>";
    lines.forEach((l, i) => {
      h += "<span class='ln'>" + (i + 1) + "</span>" + (blankIdx === i ? hl(l).replace("____", "<span class='blank' id='blank'>____</span>") : hl(l)) + "\n";
    });
    return h + "</pre></div>";
  }

  const BUGS = [
    [["x = 5", "if x = 5:", "    print('ok')"], 1, "main.py", "SyntaxError: нужно == вместо ="],
    [["let a = [1, 2, 3];", "for (let i = 0; i <= a.length; i++) {", "  console.log(a[i]);", "}"], 1, "app.js", "undefined на последнем шаге: <= выходит за массив"],
    [["def add(a, b):", "    return a - b", "print(add(2, 3))  # ждём 5"], 1, "calc.py", "AssertionError: ждали 5, получили -1"],
    [["name = input()", "print('Привет, ' + nme)"], 1, "main.py", "NameError: имя 'nme' не определено"],
    [["const s = 'abc';", "s.push('d');", "console.log(s);"], 1, "app.js", "TypeError: у строки нет метода push"],
    [["a = [1, 2, 3]", "print(a[3])  # третий элемент"], 1, "main.py", "IndexError: индекс 3 вне списка"],
    [["import os", "print(os.getcwdd())"], 1, "main.py", "AttributeError: нет getcwdd"],
    [["for i in range(3)", "    print(i)"], 0, "main.py", "SyntaxError: пропущено двоеточие"],
    [["SELEKT * FROM users", "WHERE name = 'Аня'"], 0, "query.sql", "Syntax error near SELEKT"],
    [["total = 0", "for n in [1, 2, 3]:", "    total = n", "print(total)  # ждём 6"], 2, "sum.py", "Ждали 6, получили 3: нужно +="],
    [["def is_even(n):", "    return n % 2 == 1", "print(is_even(4))  # ждём True"], 1, "even.py", "Ждали True, получили False"],
    [["let list = [3, 1, 2];", "list.sort();", "console.log(list.lenght);"], 2, "app.js", "undefined: опечатка lenght"],
    [["name = 'Аня'", "print('Привет, ' + name + '!)"], 1, "main.py", "SyntaxError: строка не закрыта"],
    [["for (let i = 0; i < 3; i--) {", "  console.log(i);", "}"], 0, "loop.js", "Бесконечный цикл: i уменьшается"],
    [["price = '100'", "print(price + 20)  # ждём 120"], 1, "main.py", "TypeError: нельзя сложить str и int"]
  ];
  const FILLS = [
    [["def square(x):", "    return ____", "print(square(4))  # 16"], 1, "x * x", ["x + x", "x * 2"], "square.py"],
    [["for i in ____(3):", "    print(i)"], 0, "range", ["len", "print"], "loop.py"],
    [["let ok = true;", "if (!ok) {", "  alert('Ошибка');", "} ____ {", "  alert('Всё хорошо');", "}"], 3, "else", ["elif", "then"], "app.js"],
    [["nums = [1, 2, 3]", "print(____(nums))  # 6"], 1, "sum", ["len", "max"], "main.py"],
    [["let a = [];", "a.____(5);", "console.log(a);  // [5]"], 1, "push", ["add", "append"], "app.js"],
    [["text = 'привет'", "print(text.____())  # ПРИВЕТ"], 1, "upper", ["lower", "len"], "main.py"],
    [["SELECT name ____ users;"], 0, "FROM", ["IN", "OF"], "query.sql"],
    [["x = 10", "while x ____ 0:", "    x -= 3"], 1, "> ", ["< ", "== "], "loop.py"]
  ];

  function coder2(done) {
    const bugs = shuffle(BUGS).slice(0, 4).map(b => {
      const note = b[3];
      return { prompt: "🐞 <b>Сборка упала.</b> Нажми на строку с багом:" + "<div style='margin-top:8px'>" + editor(b[0], b[2]) + "</div>", line: true,
        note, options: b[0].map((l, idx) => ({ label: "<span class='ln'>" + (idx + 1) + "</span>" + hl(l), ok: idx === b[1] })) };
    });
    const fills = shuffle(FILLS).slice(0, 3).map(f => {
      const right = f[2].trim();
      return { prompt: "🧩 <b>Допиши код.</b> Что вставить вместо ____ ?<div style='margin-top:8px'>" + editor(f[0], f[4], f[1]) + "</div>", line: true,
        fill: right, options: shuffle([f[2], ...f[3]]).map(v => ({ label: hl(v.trim()), ok: v === f[2] })) };
    });
    const list = shuffle([...bugs, ...fills]);
    hint.textContent = "Править баги быстро: чем быстрее ответ, тем больше очков";
    rounds(list, 11, done);
  }
  JOBS.prg = ["💻 Программист", "Чини баги и дописывай код в редакторе", coder2];
})();
