// Search by meaning's page (templates/meaning.html): a question put to the
// server, and its answer set under the box (ubsite/meaning.py; app.py
// meaning_find; ARCHITECTURE.md, Search by meaning).
//
// The question is in the address, after the #: /meaning#q=…  A browser does
// not send that part, so the page asks by a POST, whose body no log keeps.
// Typed in the box, tapped among the examples, linked from elsewhere or come
// back to, a question is asked one way: the address is set, and what the
// address says is asked.  Nothing is kept in the browser but that address.
//
// It is the one search of the site that the offline copy cannot answer: the
// model that turns a question into a vector runs on the server.  The page is
// in the copy and says so when the request fails; it tries the request and
// never takes the browser's word for being offline (CLAUDE.md trap 40).
(function () {
  'use strict';
  var T = window.ubT;

  function init() {
    var main = document.querySelector('main.meaning');
    if (!main || main.dataset.mn) return;
    main.dataset.mn = '1';
    var form = main.querySelector('.mnform'), box = main.querySelector('.mnq'),
        say = main.querySelector('.mnsay'), out = main.querySelector('.mnout'),
        most = +main.dataset.most || 300, asked = null, turn = 0;

    // The question the address names; none for an address that names none,
    // or names it wrongly.
    function named() {
      var m = /^#q=(.*)$/.exec(location.hash);
      try { return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')).replace(/\s+/g, ' ').trim() : ''; }
      catch (e) { return ''; }
    }
    // What the page says under the box: words made by T(), each key written
    // out as a literal where it is used, which is how the words a script
    // needs are found (ubsite/l10n.py script_keys).
    function tell(words) {
      say.innerHTML = words || '';
      say.hidden = !words;
    }
    function refused(why) {
      return why === 'offline' ? T('meaning:offline') : why === 'none' ? T('meaning:none') :
             why === 'busy' ? T('meaning:busy') : why === 'limit' ? T('meaning:limit') :
             why === 'long' ? T('meaning:long', { n: most }) : T('meaning:failed');
    }
    function clear() {
      out.innerHTML = '';
      out.hidden = true;
    }
    // The line the page was left at, where it is come back to by Back or a
    // reload: the answer is asked for again, and the page put where it stood.
    function back() {
      var nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0],
          y = history.state && history.state.mnY;
      if (y > 0 && nav && nav.type !== 'navigate' && !back.done) scrollTo(scrollX, y);
      back.done = true;
    }
    function keep() {
      if (!asked) return;
      try { history.replaceState(Object.assign({}, history.state, { mnY: Math.round(scrollY) }), ''); } catch (e) {}
    }
    function ask() {
      var q = named(), n = ++turn, top = document.querySelector('.find input[name="q"]'),
          tick = document.querySelector('.find .bym input');
      box.value = q;
      // The header's box too, where its tick is on and so it is this search's
      // (ub.js bymGo): the question there to be changed and entered again.
      if (q && top && tick && tick.checked) top.value = q;
      main.classList.toggle('mnasked', !!q);
      if (!q) { asked = null; clear(); tell(null); return; }
      if (q === asked) return;
      if (q.length > most) { asked = null; clear(); tell(refused('long')); return; }
      tell(T('meaning:asking'));
      out.setAttribute('aria-busy', 'true');
      fetch('/meaning/find', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
                               body: JSON.stringify({ q: q }) }).then(function (r) {
        if (r.ok) return r.text().then(function (h) { return { h: h }; });
        // The app refuses in JSON, with a word; nginx, past its limit, in a page.
        return r.json().then(function (j) { return { why: j && j.error }; },
                             function () { return { why: r.status === 429 ? 'limit' : r.status === 413 ? 'long' : '' }; });
      }, function () { return { why: 'offline' }; }).then(function (got) {
        if (n !== turn) return;
        out.removeAttribute('aria-busy');
        if (got.h == null) {
          asked = null;
          clear();
          return tell(refused(got.why));
        }
        asked = q;
        out.innerHTML = got.h;
        out.hidden = false;
        tell(null);
        // ub.js: the reader's texts over the passages, their folds, the cards.
        document.dispatchEvent(new CustomEvent('ub:meaning', { detail: out }));
        back();
      });
    }

    // A question put: the address names it, and what the address names is
    // asked; the one it names already is asked again.
    function put(q) {
      var h = '#q=' + encodeURIComponent(q);
      if (!q) return;
      if (location.hash === h) { asked = null; ask(); } else location.hash = h;
    }
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      box.blur();
      put(box.value.replace(/\s+/g, ' ').trim());
    });
    // The header's box, ticked By meaning, entered on this page (ub.js bymGo).
    init.put = put;
    // An example: the one of the interface's language, which is the one shown.
    main.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a.mnex'), i, parts, q;
      if (!a) return;
      ev.preventDefault();
      parts = a.querySelectorAll('x-en, x-ru');
      q = a.textContent;
      for (i = 0; i < parts.length; i++) if (parts[i].getClientRects().length) q = parts[i].textContent;
      location.hash = '#q=' + encodeURIComponent(q.trim());
    });
    window.addEventListener('hashchange', ask);
    window.addEventListener('pagehide', keep);
    document.addEventListener('visibilitychange', function () { if (document.hidden) keep(); });
    ask();
    if (!named() && !('ontouchstart' in window)) box.focus({ preventScroll: true });
  }

  // listen.js brings a page in while a recording plays: ub.js starts it then.
  window.ubMeaning = init;
  init();
})();
