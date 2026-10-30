// The quiz, asked (ARCHITECTURE.md, The quiz): the British Study Edition's
// questions, one at a time, on a paper's page (/quiz/N, quiz_paper.html) and
// ten at random on the quiz's own (/quiz, quiz.html), from the questions the
// page carries in #ub-quiz (queries.quiz): each its id and the layout of its
// answers (v), the right answers as bits (m), the question and its answers as
// HTML, and what answers it (s), where the review has said.  Everything is in
// the page, so it works offline as the rest of the site does.
//
// A question with one right answer is answered by a tap on it; one with more
// says so, and is answered with Check, right only if the answers chosen are
// exactly the right ones (Tigran, 2026-10-28).  After each, the right answers
// are marked, and below them the paragraph or the study note that answers it.
// At the end, the score, and what to read again.
//
// The browser keeps, under ub_quiz beside the settings and apart from them, so
// that ↺ never clears it: the first answer it gave each question, by id and
// layout, `first` {"366.1": mask}, whatever quiz it came in; and the best score
// at one sitting of each paper, `best`, which /quiz shows beside the paper.
//
// The board (ubsite/board.py; Tigran, 2026-10-28): after a quiz, with Settings'
// Quiz board on, an offer to put a name on it.  A reader who takes it gets a
// token made here, which the board knows the line by, and the board is sent
// every first answer; after each later quiz, those not yet sent (`sent`).  The
// board marks them itself.  Nothing is sent before a reader asks, and nothing
// at all with the board off.  The board is one site's, `data-board`, which
// the other sites' pages send to across origins; offline, or with the browser
// wrongly saying so (trap 40), the send is simply tried, and what is not sent
// waits for the next quiz.  /quiz/board draws the board from there.
(function () {
  'use strict';
  var main = document.querySelector('main.quiz');
  if (!main) return;
  var T = window.ubT, BOARD = main.dataset.board || '';
  var json = document.getElementById('ub-quiz');
  var D = json ? JSON.parse(json.textContent) : null;
  var run = main.querySelector('.quizrun');
  var CIRC = '①②③④⑤⑥⑦⑧⑨';
  var KEY = 'ub_quiz';

  // ---- what the browser keeps ------------------------------------------------
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (s && s.v === 1 && s.first && s.best) {
        if (!s.sent) s.sent = {};
        return s;
      }
    } catch (e) { /* storage blocked or cleared: the quiz still runs */ }
    return { v: 1, first: {}, best: {}, sent: {} };
  }
  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* as above */ }
  }

  function bits(m) { var n = 0; for (; m; m &= m - 1) n++; return n; }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  // ---- a run: the questions asked, one at a time -------------------------------
  // R: {qs, i, res: [true|false], chosen: mask, done: answered, paper: n or
  // null for ten at random}.
  var R = null;

  function start(qs, paper) {
    R = { qs: qs, i: 0, res: [], chosen: 0, done: false, paper: paper };
    main.classList.add('running');
    ask();
  }

  function ask() {
    var q = R.qs[R.i], multi = bits(q.m) > 1;
    R.chosen = 0;
    R.done = false;
    run.innerHTML = '';
    var head = el('div', 'qhead');
    head.appendChild(el('span', null, T('Question {i} of {n}', { i: R.i + 1, n: R.qs.length })));
    var dots = el('span', 'qdots');
    dots.setAttribute('aria-hidden', 'true');
    R.qs.forEach(function (x, k) {
      dots.appendChild(el('i', k < R.res.length ? (R.res[k] ? 'r' : 'w') : k === R.i ? 'c' : ''));
    });
    head.appendChild(dots);
    run.appendChild(head);
    if (R.paper === null)
      run.appendChild(el('p', 'qof', '<a href="/' + q.p + '">' + T('Paper {n}', { n: q.p }) + '</a>'));
    var qq = el('p', 'qq', q.q);
    qq.tabIndex = -1;
    run.appendChild(qq);
    if (multi) run.appendChild(el('p', 'qhint', T('Choose every right answer, then Check.')));
    var ol = el('ol', 'qopts');
    q.a.forEach(function (a, k) {
      var b = el('button', 'qopt', '<span class="qn">' + CIRC[k] + '</span><span class="tx">' + a +
                 '</span><span class="mk" aria-hidden="true"></span>');
      b.type = 'button';
      b.dataset.k = k;
      if (multi) b.setAttribute('aria-pressed', 'false');
      var li = el('li');
      li.appendChild(b);
      ol.appendChild(li);
    });
    run.appendChild(ol);
    run.appendChild(el('div', 'qafter'));
    var acts = el('p', 'qacts');
    if (multi) {
      var check = el('button', 'pill solid qcheck', T('Check'));
      check.type = 'button';
      check.disabled = true;
      acts.appendChild(check);
    }
    run.appendChild(acts);
    qq.focus({ preventScroll: true });
    if (run.getBoundingClientRect().top < 0) run.scrollIntoView();
  }

  function choose(k) {
    if (R.done) return;
    var q = R.qs[R.i];
    if (bits(q.m) < 2) { R.chosen = 1 << k; judge(); return; }
    R.chosen ^= 1 << k;
    var b = run.querySelector('.qopt[data-k="' + k + '"]');
    b.setAttribute('aria-pressed', String(!!(R.chosen >> k & 1)));
    run.querySelector('.qcheck').disabled = !R.chosen;
  }

  function judge() {
    var q = R.qs[R.i], right = R.chosen === q.m;
    R.done = true;
    R.res.push(right);
    var s = load(), id = q.id + '.' + q.v;
    if (!(id in s.first)) { s.first[id] = R.chosen; save(s); }
    run.querySelectorAll('.qopt').forEach(function (b) {
      var k = +b.dataset.k, isR = q.m >> k & 1, was = R.chosen >> k & 1;
      b.disabled = true;
      b.classList.add(isR ? 'ok' : was ? 'bad' : 'dim');
      b.querySelector('.mk').textContent = isR ? '✓' : was ? '✗' : '';
    });
    var dot = run.querySelectorAll('.qdots i')[R.i];
    if (dot) dot.className = right ? 'r' : 'w';
    var after = run.querySelector('.qafter');
    after.appendChild(el('p', 'qverdict ' + (right ? 'r' : 'w'),
      right ? T('Right.') : bits(q.m) > 1 ? T('Not quite: the right answers are marked.')
                                          : T('Not quite: the right answer is marked.')));
    if (q.s) after.appendChild(source(q.s));
    var acts = run.querySelector('.qacts'), check = acts.querySelector('.qcheck');
    if (check) check.remove();
    // Each key a literal, as l10n.py finds them (RE_SCRIPT_KEY).
    var next = el('button', 'pill solid qnext', R.i + 1 < R.qs.length ? T('Next question') : T('See the score'));
    next.type = 'button';
    acts.appendChild(next);
    next.focus({ preventScroll: true });
  }

  // A reference, linked: a run of paragraphs, "0:3.2-8", reads 0:3.2–8.
  function refLink(ref) {
    return '<a class="qref" href="/' + esc(ref) + '">' + esc(ref).replace('-', '–') + '</a>';
  }

  // What answers a question: the passages of the text, each a paragraph's
  // words or a run of paragraphs whole, in the order ruled; a study note; or
  // (a note whose paper's notes are not yet reviewed) the paragraph.  The
  // book's words are set as the text is (.qbook, --text).
  function source(s) {
    var d = el('div', 'qsrc');
    // A note's heading names its paragraph, linked; the book's words begin with it.
    if (s.k === 'note') {
      d.appendChild(el('p', 'qk', T('Study note at {ref}', { ref: T.html(refLink(s.ref)) })));
      d.appendChild(el('p', null, '<span class="qnote">' + s.h + '</span>'));
    } else (s.p || [s]).forEach(function (x) {
      d.appendChild(el('p', null, refLink(x.ref) + ' <span class="qbook">' + x.h + '</span>'));
    });
    return d;
  }

  function next() {
    if (R.i + 1 < R.qs.length) { R.i++; ask(); } else score();
  }

  function score() {
    var r = R.res.filter(Boolean).length, n = R.qs.length;
    if (R.paper !== null) {
      var s = load();
      if (!(s.best[R.paper] >= r)) { s.best[R.paper] = r; save(s); }
    }
    run.innerHTML = '';
    var sc = el('div', 'qscore');
    sc.appendChild(el('p', 'qbig', String(r)));
    sc.appendChild(el('p', null, T('{r} of {n} right', { r: r, n: n })));
    var marks = el('p', 'qmarks');
    marks.setAttribute('aria-hidden', 'true');
    R.res.forEach(function (x) { marks.appendChild(el('span', x ? 'r' : 'w', x ? '✓' : '✗')); });
    sc.appendChild(marks);
    run.appendChild(sc);
    var missed = R.qs.filter(function (q, k) { return !R.res[k]; });
    if (!missed.length) run.appendChild(el('p', 'qall', T('Every one right.')));
    else {
      run.appendChild(el('h2', null, T('To read again')));
      var ul = el('ul', 'qmissed');
      missed.forEach(function (q) {
        ul.appendChild(el('li', null, (q.s ? refLink(q.s.ref) + ' '
                                           : '<a class="qref" href="/' + q.p + '">' + T('Paper {n}', { n: q.p }) + '</a> ') +
                                      '<span>' + q.q + '</span>'));
      });
      run.appendChild(ul);
    }
    var acts = el('p', 'qacts qend'), again = el('button', 'pill qagain', T('Again'));
    again.type = 'button';
    acts.appendChild(again);
    if (R.paper !== null) {
      acts.appendChild(el('a', 'pill', T('Back to the paper'))).href = '/' + R.paper;
      if (D.next)
        acts.appendChild(el('a', 'pill solid', T('quiz:next', { p: D.next.n, n: D.next.count }))).href = '/quiz/' + D.next.n;
    }
    acts.appendChild(el('a', 'qhome', T('All the quizzes'))).href = '/quiz';
    run.appendChild(acts);
    if (boardOn()) toBoard();
    run.querySelector('.qbig').tabIndex = -1;
    run.querySelector('.qbig').focus({ preventScroll: true });
    if (run.getBoundingClientRect().top < 0) run.scrollIntoView();
  }

  // ---- the board ------------------------------------------------------------------------
  // Quiz board, which means nothing while Quiz is off (settings.py NEEDS).
  function boardOn() {
    var g = window.ubSettings ? window.ubSettings.get() : {};
    return !!BOARD && g.quiz !== false && g.quizboard !== false;
  }
  function post(path, body) {
    return fetch(BOARD + path, { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' },
                                 body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { return { status: r.status, j: j }; }); });
  }
  // The first answers the board has not had: [id, v, mask] each.
  function unsent(s) {
    return Object.keys(s.first).filter(function (k) { return !s.sent[k]; }).map(function (k) {
      var iv = k.split('.');
      return [+iv[0], +iv[1], s.first[k]];
    });
  }
  function sentAll(s, list) {
    list.forEach(function (a) { s.sent[a[0] + '.' + a[1]] = 1; });
  }
  function placed(box, j) {
    box.innerHTML = '';
    box.appendChild(el('p', 'qplace', T('{name} is on the board, in place {p} of {n}.',
                                         { name: j.name, p: j.place || j.of, n: j.of }) +
                                       ' <a href="/quiz/board">' + T('See the board') + '</a>'));
  }
  function unreached(box) {
    box.appendChild(el('p', 'qmsg', T('The board could not be reached. Your answers are kept, and go with the next quiz you finish.')));
  }
  function toBoard() {
    var s = load(), box = el('div', 'qjoinbox qboard');
    run.appendChild(box);
    if (s.token) {
      var list = unsent(s);
      post('/quiz/board/answers', { t: s.token, a: list }).then(function (r) {
        if (r.status === 404) {          // the board has no such line: offered again
          var k = load();
          delete k.token; delete k.line; k.sent = {};
          save(k);
          box.remove();
          toBoard();
          return;
        }
        if (r.status !== 200) throw new Error(r.status);
        var k2 = load();
        sentAll(k2, list);
        save(k2);
        placed(box, r.j);
      }).catch(function () { unreached(box); });
      return;
    }
    var f = el('form', 'qjoin');
    f.appendChild(el('h2', null, T('Put your name on the board?')));
    f.appendChild(el('p', null, T('quiz:offer')));
    var row = el('p', 'namerow'), lab = el('label', 'qnamelab', T('Your name on the board'));
    lab.htmlFor = 'qname';
    var inp = el('input');
    inp.id = 'qname';
    inp.maxLength = 32;
    inp.autocomplete = 'nickname';
    inp.required = true;
    var add = el('button', 'pill solid', T('Add my name'));
    add.type = 'submit';
    row.appendChild(lab);
    row.appendChild(inp);
    row.appendChild(add);
    f.appendChild(row);
    f.appendChild(el('p', 'qsmall', T('quiz:kept')));
    var msg = el('p', 'qmsg');
    msg.setAttribute('aria-live', 'polite');
    f.appendChild(msg);
    box.appendChild(f);
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var k = load(), token = k.pending || hex16();
      k.pending = token;             // the same token if the first try fails
      save(k);
      var list = unsent({ first: k.first, sent: {} });
      add.disabled = true;
      msg.innerHTML = '';
      post('/quiz/board/join', { t: token, n: inp.value, a: list }).then(function (r) {
        add.disabled = false;
        if (r.status === 409) { msg.innerHTML = T('That name is taken: choose another.'); return; }
        if (r.status === 400 && r.j.error === 'name') {
          msg.innerHTML = T('A name is letters and digits, with spaces, full stops, hyphens or apostrophes between them, 32 at most.');
          return;
        }
        if (r.status !== 200) throw new Error(r.status);
        var k2 = load();
        k2.token = token;
        k2.line = r.j.line;
        k2.name = r.j.name;
        delete k2.pending;
        k2.sent = {};
        sentAll(k2, list);
        save(k2);
        placed(box, r.j);
      }).catch(function () { add.disabled = false; msg.innerHTML = ''; unreached(msg); });
    });
  }
  function hex16() {
    var b = new Uint8Array(16);
    crypto.getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join('');
  }
  // /quiz/board: the board as its site gives it, this browser's line marked.
  function drawBoard() {
    var box = main.querySelector('.boardrun'), me = load().line;
    fetch(BOARD + '/quiz/board/lines', { credentials: 'omit' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (j) {
      box.innerHTML = '';
      if (!j.lines.length) { box.appendChild(el('p', null, T('No one is on the board yet.'))); return; }
      var wrap = el('div', 'qtable'), t = el('table');
      t.innerHTML = '<thead><tr><th>#</th><th>' + T('Name') + '</th><th>' + T('Right the first time') +
                    '</th><th class="nar">' + T('Answered') + '</th><th class="nar">' + T('Papers') + '</th></tr></thead>';
      var tb = el('tbody');
      j.lines.forEach(function (x, i) {
        var tr = el('tr', x.id === me ? 'you' : null);
        tr.innerHTML = '<td>' + (i + 1) + '</td><td>' + esc(x.name) + '</td><td>' + x.right + '</td><td class="nar">' +
                       x.answered + '</td><td class="nar">' + x.papers + '</td>';
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      wrap.appendChild(t);
      box.appendChild(wrap);
    }).catch(function () {
      box.innerHTML = '';
      box.appendChild(el('p', 'qmsg', T('The board could not be reached.')));
    });
  }

  // ---- ten at random, and each paper's best (/quiz) -------------------------------
  function shuffle(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = a[i];
      a[i] = a[j];
      a[j] = t;
    }
    return a;
  }
  function draw() {
    var from = main.querySelector('#quizfrom').value, part = {};
    D.papers.forEach(function (p) { part[p.n] = p.part; });
    var pool = D.q.filter(function (q) { return from === '' || String(part[q.p]) === from; });
    return shuffle(pool.slice()).slice(0, 10);
  }
  function progress() {
    var s = load();
    D.papers.forEach(function (p) {
      var i = main.querySelector('.qtoc li[data-n="' + p.n + '"] i');
      if (!i || !(p.n in s.best)) return;
      i.innerHTML = T('{r} of {n}', { r: s.best[p.n], n: p.count });
      i.classList.toggle('done', s.best[p.n] === p.count);
    });
  }

  // ---- taps and keys ----------------------------------------------------------------
  if (run) run.addEventListener('click', function (ev) {
    var b = ev.target.closest('button');
    if (!b || !R) return;
    if (b.classList.contains('qopt')) choose(+b.dataset.k);
    else if (b.classList.contains('qcheck')) { if (R.chosen) judge(); }
    else if (b.classList.contains('qnext')) next();
    else if (b.classList.contains('qagain')) start(R.paper === null ? draw() : D.q, R.paper);
  });
  // 1 to 9 choose an answer; Enter checks, or goes on.
  document.addEventListener('keydown', function (ev) {
    if (!R || ev.ctrlKey || ev.metaKey || ev.altKey || /^(INPUT|SELECT|TEXTAREA)$/.test(ev.target.tagName) ||
        ev.target.closest('dialog')) return;
    var k = '123456789'.indexOf(ev.key);
    if (k >= 0 && !R.done && R.qs[R.i] && k < R.qs[R.i].a.length) { ev.preventDefault(); choose(k); }
    else if (ev.key === 'Enter' && ev.target.tagName !== 'A' && ev.target.tagName !== 'BUTTON') {
      if (!R.done && R.chosen && R.qs[R.i] && bits(R.qs[R.i].m) > 1) { ev.preventDefault(); judge(); }
      else if (R.done && run.querySelector('.qnext')) { ev.preventDefault(); next(); }
    }
  });

  if (main.classList.contains('quizboard')) { drawBoard(); return; }
  if (!D) return;
  if ('paper' in D) start(D.q, D.paper);
  else {
    progress();
    main.querySelector('#quizrnd').addEventListener('submit', function (ev) {
      ev.preventDefault();
      start(draw(), null);
    });
  }
})();
