// The tour (Tigran, 2026-11-06): what the page can do, shown on the page
// itself, one control at a time, each lit and left live, with a card beside
// it; and the Help page's buttons, which start it (templates/help.html).
//
// It starts by itself on a reader's first visit, wherever they land: its
// first card is the welcome, and on a page without the book's text "Open the
// book" goes to LAND and the tour goes on there.  Skip, × or Done ends it
// for good (localStorage ub_tour = 'seen', written as the welcome is
// answered, so that it never comes twice); "Take the tour" on /help starts
// it again.  While it is on, the step is kept for the tab (sessionStorage),
// so a lit link followed, Back, or the hop from the home page resumes it.
//
// Drawn on <body> by this script alone, like the running head and What's
// new, so no template names it and no stored page of the offline copy moves
// with it: four shields dim the page around the lit control and take every
// tap outside it, a ring stands on it, and the card goes below it, above it,
// beside it, or on a phone as a sheet at the window's foot.  What the lit
// control opens stays clear: a note's card under the line (ub.js .pop) is
// taken into the hole, and the tour's card moves out of its way; Settings
// opens in the top layer and the player above the shields.  → and Enter go
// on, ← back, Escape ends it; in a field the keys are the field's.
//
// Loaded on demand by ub.js from the ?'s data-src when the tour is due, and
// by /help itself.  Every word is in both languages (ru.toml, tour:*).
(function () {
  'use strict';
  var T = window.ubT;
  var LAND = '/1:1', HELP = '/help', KEY = 'ub_tour';
  var onHelp = location.pathname === HELP;
  var phone = matchMedia('(max-width: 62rem)');
  function get(store) { try { return window[store].getItem(KEY); } catch (e) { return null; } }
  function put(store, v) { try { if (v === null) window[store].removeItem(KEY); else window[store].setItem(KEY, v); } catch (e) {} }

  // ---- the steps ---------------------------------------------------------
  // Keyed by name, never by index, so that a step kept by an older build
  // cannot point at the wrong one.  `at` is the control to light, a selector
  // or a function; a control the page lacks (the index off, Listening off,
  // no worker for the cloud, no note on the page) is stepped over, and the
  // count is the page's own.  `ch` is the Help page's chapter.
  function drawn(el) { return el && !el.hidden && el.getClientRects().length ? el : null; }
  function lit(sel) {
    var els = document.querySelectorAll(sel);
    for (var i = 0; i < els.length; i++) if (drawn(els[i])) return els[i];
    return null;
  }
  var STEPS = [
    { k: 'welcome' },
    { k: 'chips', ch: 'index', title: 'tour:chips:title', text: 'tour:chips', at: function () {
        return (phone.matches && lit('.grid > .row > .a .afold')) || lit('.grid > .row > .a .chips') || lit('.grid > .row > .a'); } },
    { k: 'cited', ch: 'index', title: 'tour:cited:title', text: 'tour:cited', at: '.blanket' },
    { k: 'search', ch: 'moving', title: 'tour:search:title', text: 'tour:search', at: '.top .find input' },
    { k: 'contents', ch: 'moving', title: 'tour:contents:title', text: 'tour:contents', at: function () {
        return (phone.matches && lit('.rail .railhead')) || lit('.rail'); } },
    { k: 'transport', ch: 'moving', title: 'tour:transport:title', text: 'tour:transport', at: '.transport' },
    { k: 'runhead', ch: 'moving', title: 'tour:runhead:title', text: 'tour:runhead', at: 'main p.t[id]', enter: showHead, leave: hideHead },
    { k: 'listen', ch: 'listening', title: 'tour:listen:title', text: 'tour:listen', at: 'main p.t[id] .playp' },
    { k: 'notes', ch: 'notes', title: 'tour:notes:title', text: 'tour:notes', at: 'main a.fn' },
    { k: 'gear', ch: 'settings', title: 'tour:gear:title', text: 'tour:gear', at: '.top .gear' },
    { k: 'cloud', ch: 'offline', title: 'tour:cloud:title', text: 'tour:cloud', at: '.top .offline' },
    { k: 'help', ch: '', title: 'tour:help:title', text: 'tour:help', at: '.top a.help', last: true }
  ];
  // The words, named here as literals so that the catalog carries them
  // (ubsite/l10n.py script_keys).
  var WORDS = {
    'tour:chips:title': T.k('tour:chips:title'), 'tour:chips': T.k('tour:chips'),
    'tour:cited:title': T.k('tour:cited:title'), 'tour:cited': T.k('tour:cited'),
    'tour:search:title': T.k('tour:search:title'), 'tour:search': T.k('tour:search'),
    'tour:contents:title': T.k('tour:contents:title'), 'tour:contents': T.k('tour:contents'),
    'tour:transport:title': T.k('tour:transport:title'), 'tour:transport': T.k('tour:transport'),
    'tour:runhead:title': T.k('tour:runhead:title'), 'tour:runhead': T.k('tour:runhead'),
    'tour:listen:title': T.k('tour:listen:title'), 'tour:listen': T.k('tour:listen'),
    'tour:notes:title': T.k('tour:notes:title'), 'tour:notes': T.k('tour:notes'),
    'tour:gear:title': T.k('tour:gear:title'), 'tour:gear': T.k('tour:gear'),
    'tour:cloud:title': T.k('tour:cloud:title'), 'tour:cloud': T.k('tour:cloud'),
    'tour:help:title': T.k('tour:help:title'), 'tour:help': T.k('tour:help')
  };
  function target(s) {
    if (!s.at) return null;
    return typeof s.at === 'function' ? s.at() : lit(s.at);
  }
  function available() {
    return STEPS.filter(function (s) { return !s.at || target(s); });
  }
  function onBook() { return !!document.querySelector('main p.t[id]'); }

  // The running head, shown for real as a tap on the text shows it (ub.js
  // tapHead), and lit; hidden again as the step is left.
  function showHead(p) {
    if (!p) return null;
    p.scrollIntoView({ block: 'center', behavior: 'instant' });
    p.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 10, clientY: innerHeight / 2 }));
    return drawn(document.querySelector('.runhead')) || p;
  }
  function hideHead() {
    var head = document.querySelector('.runhead');
    if (head && !head.hidden) head.click();
  }

  // ---- drawing -------------------------------------------------------------
  var ui = null, cur = null, list = [], raf = 0, PAD = 6;
  function el(cls, html) {
    var d = document.createElement('div');
    d.className = cls;
    if (html) d.innerHTML = html;
    return d;
  }
  function build() {
    if (ui) return;
    ui = { shields: [el('tour-shield'), el('tour-shield'), el('tour-shield'), el('tour-shield')],
           ring: el('tour-ring'), card: el('tour-card') };
    ui.card.setAttribute('role', 'dialog');
    ui.card.setAttribute('aria-modal', 'false');
    ui.card.setAttribute('aria-labelledby', 'tour-title');
    ui.shields.forEach(function (s) {
      s.addEventListener('click', function (ev) { ev.preventDefault(); });
      document.body.appendChild(s);
    });
    document.body.appendChild(ui.ring);
    document.body.appendChild(ui.card);
    document.addEventListener('keydown', onKey, true);
    addEventListener('scroll', schedule, { passive: true });
    addEventListener('resize', schedule);
    document.addEventListener('ub:swap', swapped);
    document.addEventListener('ub:settings', schedule);
    // A card opening under the lit control, the player appearing, the rail
    // folding: the page moved under the tour, so it is placed again.
    ui.mo = new MutationObserver(schedule);
    ui.mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'class'] });
  }
  function teardown() {
    if (!ui) return;
    ui.shields.forEach(function (s) { s.remove(); });
    ui.ring.remove();
    ui.card.remove();
    document.removeEventListener('keydown', onKey, true);
    removeEventListener('scroll', schedule);
    removeEventListener('resize', schedule);
    document.removeEventListener('ub:swap', swapped);
    document.removeEventListener('ub:settings', schedule);
    ui.mo.disconnect();
    ui = null;
  }
  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(function () { raf = 0; place(); });
  }
  // listen.js swapped <main>: the lit control is gone with it, so the step is
  // shown again on the new page, or the next one it has.
  function swapped() { if (cur) show(cur.step.k); }
  function rectOf(e) {
    var r = e.getBoundingClientRect();
    return { l: r.left - PAD, t: r.top - PAD, r: r.right + PAD, b: r.bottom + PAD };
  }
  function box(s, l, t, w, h) {
    s.style.left = l + 'px'; s.style.top = t + 'px';
    s.style.width = Math.max(0, w) + 'px'; s.style.height = Math.max(0, h) + 'px';
  }
  function place() {
    if (!ui || !cur) return;
    var W = innerWidth, H = innerHeight, c = ui.card, t = cur.el, r, q;
    if (!t) {                                   // the welcome: all dimmed, the card centred
      box(ui.shields[0], 0, 0, W, H);
      ui.shields.slice(1).forEach(function (s) { box(s, 0, 0, 0, 0); });
      ui.ring.style.display = 'none';
      c.classList.add('centre'); c.classList.remove('sheet');
      return;
    }
    if (!document.contains(t)) { swapped(); return; }
    if (!drawn(t)) { next(); return; }
    r = rectOf(t);
    ui.ring.style.display = '';
    box(ui.ring, r.l, r.t, r.r - r.l, r.b - r.t);
    // What the lit control opened stays clear too: a note's card under the
    // line.  The hole takes it in; the ring stays on the control.
    var pop = lit('.pop');
    if (pop) {
      q = rectOf(pop);
      r = { l: Math.min(r.l, q.l), t: Math.min(r.t, q.t), r: Math.max(r.r, q.r), b: Math.max(r.b, q.b) };
    }
    box(ui.shields[0], 0, 0, W, r.t);                 // above
    box(ui.shields[1], 0, r.b, W, H - r.b);           // below
    box(ui.shields[2], 0, r.t, r.l, r.b - r.t);       // left
    box(ui.shields[3], r.r, r.t, W - r.r, r.b - r.t); // right
    c.classList.remove('centre');
    var ch = c.offsetHeight, cw = c.offsetWidth, gap = 12, top, left,
        tall = r.b - r.t > H * .6, wide = r.r - r.l > W * .6;
    if (!tall && r.b + gap + ch < H) top = r.b + gap;              // below
    else if (!tall && r.t - gap - ch > 0) top = r.t - gap - ch;    // above
    else top = null;
    if (top !== null) {
      // Under a wide control (the running head, the transport bar) the card
      // is centred on it; otherwise it starts at the control's left edge.
      left = wide ? (r.l + r.r) / 2 - cw / 2 : r.l;
    } else if (W - r.r > cw + gap + 8) {                           // beside a tall one, at the right
      left = r.r + gap; top = Math.max(8, Math.min(r.t + 40, H - ch - 8));
    } else if (r.l > cw + gap + 8) {                               // or at the left
      left = r.l - gap - cw; top = Math.max(8, Math.min(r.t + 40, H - ch - 8));
    } else { c.classList.add('sheet'); return; }                   // a phone: a sheet at the foot
    c.classList.remove('sheet');
    c.style.left = Math.max(8, Math.min(left, W - cw - 8)) + 'px';
    c.style.top = top + 'px';
  }

  // ---- the card ----------------------------------------------------------------
  var X = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg>';
  function render() {
    var s = cur.step, i = list.indexOf(s), n = list.length, first = i === 1, last = s.last || i === n - 1,
        book = onBook(), h, logo, qi, p;
    h = '<button type="button" class="x" ' + T.a('aria-label', 'Close') + ' ' + T.a('title', 'Close') + '>' + X + '</button>';
    if (s.k === 'welcome') {
      logo = document.querySelector('.brand .logo');
      qi = document.querySelector('.top a.help svg');
      h += (logo ? logo.outerHTML.replace('class="logo"', 'class="logo mark"') : '') +
           '<h2 id="tour-title">' + T('Welcome|tour') + '</h2>' +
           '<p>' + T('tour:welcome', { q: T.html(qi ? '<span class="qi">' + qi.outerHTML + '</span>' : '?') }) + '</p>' +
           (book ? '' : '<p class="tip">' + T('tour:welcome:open') + '</p>') +
           '<p class="btns"><button type="button" class="pill solid go">' + (book ? T('Begin|tour') : T('Open the book')) + '</button>' +
           '<button type="button" class="skip">' + T('Skip the tour') + '</button></p>' +
           '<p class="tip">' + T('tour:keys') + '</p>';
      ui.card.className = 'tour-card welcome';
    } else {
      h += '<p class="k">' + T('{a} of {b}|tour', { a: i, b: n - 1 }) + '</p>' +
           '<h2 id="tour-title">' + T(WORDS[s.title]) + '</h2><p>' + T(WORDS[s.text]) + '</p>' +
           (s.ch ? '<p class="more"><a href="' + HELP + '#' + s.ch + '">' + T('More in Help') + ' ›</a></p>' : '') +
           '<p class="btns">' + (first ? '' : '<button type="button" class="pill prev">' + T('Back|tour') + '</button>') +
           '<button type="button" class="pill solid go">' + (last ? T('Done|tour') : T('Next|tour')) + '</button>' +
           (last ? '' : '<button type="button" class="skip">' + T('Skip the tour') + '</button>') + '</p>';
      ui.card.className = 'tour-card';
    }
    ui.card.innerHTML = h;
    ui.card.querySelector('.go').addEventListener('click', function () {
      if (s.k === 'welcome') begin(); else if (last) end(true); else next();
    });
    p = ui.card.querySelector('.prev'); if (p) p.addEventListener('click', back);
    p = ui.card.querySelector('.skip'); if (p) p.addEventListener('click', function () { end(true); });
    ui.card.querySelector('.x').addEventListener('click', function () { end(true); });
    ui.card.querySelector('.go').focus({ preventScroll: true });
  }
  function begin() {
    put('localStorage', 'seen');
    if (onBook()) { next(); return; }
    put('sessionStorage', 'chips');
    location.href = LAND;
  }

  // ---- moving ------------------------------------------------------------------
  function show(k) {
    build();
    list = available();
    var s = null, i, j;
    for (i = 0; i < list.length; i++) if (list[i].k === k) s = list[i];
    if (!s) {                                   // a step this page lacks: the next it has
      for (j = 0; j < STEPS.length && STEPS[j].k !== k; j++) {}
      for (i = j + 1; i < STEPS.length && !s; i++) if (list.indexOf(STEPS[i]) >= 0) s = STEPS[i];
      if (!s) { end(false); return; }
    }
    if (cur && cur.step.leave && cur.step !== s) cur.step.leave();
    var t = target(s);
    if (s.enter) t = s.enter(t) || t;
    cur = { step: s, el: t };
    put('sessionStorage', s.k);
    if (t && !s.enter) {
      var r = t.getBoundingClientRect();
      if (r.top < 0 || r.bottom > innerHeight) t.scrollIntoView({ block: 'center', behavior: 'instant' });
    }
    render();
    place();
    requestAnimationFrame(place);
  }
  function next() {
    var i = list.indexOf(cur.step);
    if (i < 0 || i >= list.length - 1) { end(true); return; }
    show(list[i + 1].k);
  }
  function back() {
    var i = list.indexOf(cur.step);
    if (i > 0) show(list[i - 1].k);
  }
  function end(byReader) {
    if (cur && cur.step.leave) cur.step.leave();
    if (byReader) put('localStorage', 'seen');
    put('sessionStorage', null);
    cur = null;
    teardown();
  }
  function onKey(ev) {
    if (!cur) return;
    var t = ev.target;
    // Keys in a field, a dialog (Settings opened from the lit gear), the player
    // or a note's card are theirs: Escape closes those, not the tour.
    if (t.closest && t.closest('input, select, textarea, dialog, .player, .pop')) return;
    if (ev.key === 'Escape') {
      if (lit('.pop')) return;                  // ub.js shuts the card
      ev.preventDefault(); ev.stopPropagation(); end(true); return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'ArrowRight' || ev.key === 'Enter') {
      ev.preventDefault(); ev.stopPropagation();
      if (cur.step.k === 'welcome') begin(); else if (cur.step.last) end(true); else next();
    } else if (ev.key === 'ArrowLeft') { ev.preventDefault(); ev.stopPropagation(); back(); }
  }
  window.ubTour = { start: function (k) { show(k || 'welcome'); }, stop: function () { end(false); } };

  // ---- the Help page's buttons -------------------------------------------------
  // "Take the tour" and "Show me" go to the page of the book the reader came
  // from, if that is where they came from, else to LAND, with the step kept
  // for the tab; the page is the reference, not a stop, so a step kept is let go.
  if (onHelp) {
    put('sessionStorage', null);
    var from = LAND;
    try {
      var ref = new URL(document.referrer);
      if (ref.origin === location.origin && /^\/\d+(?::\d+(?:\.\d+(?:-\d+)?)?)?(?:\/compare)?$/.test(ref.pathname)) from = ref.pathname;
    } catch (e) {}
    document.querySelectorAll('.showme, .tourstart').forEach(function (b) {
      b.addEventListener('click', function () {
        put('sessionStorage', b.dataset.tour || 'welcome');
        location.href = from;
      });
    });
    return;
  }

  // ---- starting by itself ------------------------------------------------------
  // Due: never seen, or a step kept for this tab.  Not over Settings or
  // What's new (after they close), not while the page is hidden or the
  // player is open, and a moment after load, so that arrive() has placed the page.
  var want = get('sessionStorage') || (get('localStorage') !== 'seen' ? 'welcome' : null);
  function start() {
    if (!want || cur) return;
    var open = document.querySelector('dialog[open]');
    if (open) { open.addEventListener('close', start, { once: true }); return; }
    if (document.visibilityState !== 'visible') { document.addEventListener('visibilitychange', start, { once: true }); return; }
    if (document.body.classList.contains('listening')) return;
    show(want);
  }
  if (want) setTimeout(start, 600);
})();
