// Listening, on a section page.  Loaded only where the page carries #ub-audio.
//
// Every voice arrives in one shape: a list of files and a list of segments,
// [ref, file, start_ms, end_ms] in reading order, ref null for the spoken
// heading.  Both readings have one file per section, its paragraphs stretches
// of it, but this plays a queue of segments and never needs to know how they
// are filed: consecutive segments in one file play straight through, and the
// next file is loaded when one ends.
//
// The browser's own voice has no files: the browser speaks the text itself
// (`speakFrom`), the spoken text of build/speech.py, fetched from
// /speech/<section> once that voice is chosen.  It plays the same list of
// segments, a paragraph each, so marking, "Next" and carrying on are shared.
//
// Playback stops at the end of the section, and "Next" offers the following
// one -- unless Settings says to carry on, when it goes on by itself, across
// papers, through the book.  Either way the next section is brought into this
// page rather than loaded as a new one (`carryOn`): a new page would need a
// tap of its own before a browser lets it play, iOS above all, and with the
// screen locked it would never load.
//
// With Follow along off, the reader may go anywhere on the site while it plays:
// while the bar is open the site's own links are followed in this page too
// (`visit`), so the page changes and the reading does not.  This page's section
// (`P`) and the section being heard (`D`) are then two different things.
(function () {
  var data = document.getElementById('ub-audio');
  var S = window.ubSettings;
  if (!data || !S) return;
  var P = JSON.parse(data.textContent);  // the section the page shows; null on any other page
  var D = null;                          // the section being heard
  var RATES = [0.8, 0.9, 1, 1.1, 1.25, 1.5];
  var NS = 'http://www.w3.org/2000/svg';
  var ICON = { play: 'M4.5 2.5v11l9-5.5z', pause: 'M4 2.5h3v11H4zM9.5 2.5h3v11h-3z',
               prev: 'M3 2.5h2v11H3zM13.5 2.5v11L5.5 8z', next: 'M11 2.5h2v11h-2zM2.5 2.5v11l8-5.5z',
               close: 'M4 4l8 8M12 4l-8 8' };

  function icon(name) {
    var s = document.createElementNS(NS, 'svg'), p = document.createElementNS(NS, 'path');
    s.setAttribute('viewBox', '0 0 16 16');
    s.setAttribute('aria-hidden', 'true');
    s.setAttribute('focusable', 'false');
    p.setAttribute('d', ICON[name]);
    if (name === 'close') p.setAttribute('class', 'stroke');
    s.appendChild(p);
    return s;
  }
  function button(cls, label, name) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    b.setAttribute('aria-label', label);
    b.appendChild(icon(name));
    return b;
  }

  var audio = new Audio();
  audio.preload = 'none';
  var synth = window.speechSynthesis || null;
  var V = null, key = null;          // the voice being heard, and its key
  var PV = null, pkey = null;        // the voice the page's own controls start
  var k = -1, file = -1;             // the segment being heard, and its file
  var marked = null, bar = null, controls = [], shuts = [];
  var head, paras;
  // The ids of the paragraphs in root, in reading order.
  function ids(root) {
    return Array.prototype.map.call(root.querySelectorAll('p.t[id]'), function (p) { return p.id; });
  }
  function scan() {
    // The section's title, or over an introduction, which has none, the
    // paper's: what its spoken heading reads.
    head = document.querySelector('.papertop h2') || document.querySelector('.papertop h1');
    paras = {};
    Array.prototype.forEach.call(document.querySelectorAll('p.t[id]'),
                                 function (p) { paras[p.id] = p; });
    if (P) P.ids = ids(document);
  }
  scan();

  // The voice Settings asks for, else the first section d has.
  function choose(d) {
    var want = S.get().voice;
    if (want === 'off') return null;
    if (want === 'browser' && synth) return want;
    if (want && d.voices[want]) return want;
    for (var v in d.voices) return v;
    return null;
  }
  // Offline a recording cannot be had: the voice Settings names is not changed
  // for another (Tigran, 2026-10-13), the bar says why it does not play, and
  // its voice menu stands beside the message.
  var NEEDS_NET = 'The recordings need a connection. Offline, your browser\u2019s voice can read it.';
  // Section d's voice kk; the browser's is made from its paragraphs, d.ids.
  function voiceOf(d, kk) {
    return kk === 'browser' ? spoken(d.ids, href(d)) : kk ? d.voices[kk] : null;
  }
  function href(d) { return '/' + d.paper + ':' + d.section; }
  function same(a, b) { return !!(a && b && a.paper === b.paper && a.section === b.section); }
  function rate() { var r = S.get().rate; return RATES.indexOf(r) < 0 ? 1 : r; }
  // What the bar and the lock screen call the voice: for the browser's, the
  // name of the one it speaks with, once the browser has said.
  function vname() {
    if (V.kind !== 'browser') return V.label;
    var v = S.voice();
    return v ? v.name : 'Your browser\u2019s voice';
  }

  // ---- controls in the page ------------------------------------------------
  // A play button beside each paragraph, the first paragraph's reading the
  // section's heading first.  Until 2026-10-18 a Listen button under the head
  // did that, and Tigran took it out as the first paragraph's twin.
  function build() {
    controls.forEach(function (c) { c.remove(); });
    controls = [];
    if (!P) return;
    pkey = choose(P);
    PV = voiceOf(P, pkey);
    if (!PV) return;
    // Boson's licence for the AI voice: its acknowledgment, wherever the voice
    // is offered or plays.  Under the head, where the Listen button stood.
    if (PV.credit) {
      var row = document.createElement('p'), c = document.createElement(PV.credit_url ? 'a' : 'span');
      row.className = 'voicecredit';
      c.textContent = PV.credit;
      if (PV.credit_url) { c.href = PV.credit_url; c.rel = 'noopener'; c.target = '_blank'; }
      row.appendChild(c);
      head.parentNode.appendChild(row);
      controls.push(row);
    }
    function place(p, i, label) {
      // Outside the stored text, and with no text of its own: copying the
      // paragraph still returns its words exactly (CLAUDE.md §6).
      var pb = button('playp', label, 'play');
      pb.addEventListener('click', function () { start(i); });
      // Under the reference, in the stack at the paragraph's start (_para.html).
      var num = p.querySelector('.num'), stk = p.querySelector('.stk') || p;
      stk.insertBefore(pb, num ? num.nextSibling : stk.firstChild);
      controls.push(pb);
    }
    // A paragraph can be started only once the reading is aligned to them;
    // until then the first paragraph's button starts the section.
    if (PV.by !== 'paragraph') {
      var p0 = document.querySelector('p.t[id]');
      if (p0) place(p0, 0, 'Listen to this section');
      return;
    }
    var first = true;
    PV.segs.forEach(function (s, i) {
      var p = s[0] && paras[s[0]];
      if (!p) return;
      if (first && PV.segs[0][0] === null) place(p, 0, 'Listen to this section, from its heading');
      else place(p, i, 'Listen from ' + s[0]);
      first = false;
    });
  }
  // A press on the page's own controls: what is heard becomes what the page shows.
  function start(i) {
    if (V && V.kind !== PV.kind) { hush(); audio.pause(); }
    // Another section's files, or another voice's: they are numbered afresh.
    if (!same(D, P) || key !== pkey) file = -1;
    D = P; V = PV; key = pkey;
    go(i);
  }

  // ---- the bar ---------------------------------------------------------------
  var voiceMenu = null;
  function makeBar() {
    // Chrome on Android names its voices only a moment after a page first asks
    // for them, and with a recording playing nothing has: ask now, so that the
    // list of voices has them by the time it is opened (voiceschanged, below).
    if (synth) synth.getVoices();
    shuts = [];
    bar = document.createElement('div');
    bar.className = 'player';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Listening');
    var prev = button('prev', 'Back to the start of this paragraph (twice: the one before)', 'prev');
    prev.title = prev.getAttribute('aria-label');
    var tog = button('toggle', 'Play', 'play');
    var nxt = button('next', 'Next paragraph', 'next');
    // What is being read, and by whom.  A tap on the reference brings its
    // paragraph into view.
    var where = document.createElement('span');
    where.className = 'where';
    var at = document.createElement('button');
    at.type = 'button';
    at.className = 'at';
    at.title = 'Show this paragraph';
    at.addEventListener('click', function () { toReading(true); });
    var who = document.createElement('span');
    who.className = 'who';
    where.appendChild(at);
    where.appendChild(who);
    // With the voice beside it, after a dot; on a phone, under it (ub.css).
    var mid = document.createElement('span');
    mid.className = 'mid';
    mid.appendChild(where);
    mid.appendChild(voiceMenu = voices());
    var spd = speeds();
    var on = document.createElement('a');
    on.className = 'onward';
    on.hidden = true;
    // A tap on "Next" brings the section in here too; the link remains for a
    // new tab, where #listen starts it.
    on.addEventListener('click', function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) return;
      ev.preventDefault();
      carryOn();
    });
    var x = button('close', 'Stop and close', 'close');
    prev.addEventListener('click', back);
    nxt.addEventListener('click', forward);
    tog.addEventListener('click', toggle);
    x.addEventListener('click', close);
    [prev, tog, nxt, mid, spd, on, x].forEach(function (e) { bar.appendChild(e); });
    document.body.appendChild(bar);
    document.body.classList.add('listening');
  }
  // A button in the bar and the list a tap on it opens above the bar: the
  // speed, the voice.  entries() is asked each time it opens, so that what it
  // lists and which is checked are current: [{text, on, pick, note}, ...],
  // with {group} for a heading over the entries after it.
  function dropup(boxCls, btnCls, menuCls, label, entries) {
    var box = document.createElement('span');
    box.className = boxCls;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = btnCls;
    btn.setAttribute('aria-label', label);
    btn.setAttribute('aria-haspopup', 'menu');
    btn.setAttribute('aria-expanded', 'false');
    var menu = document.createElement('div');
    menu.className = menuCls;
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', label);
    menu.hidden = true;
    var items = [];
    // The entries, drawn afresh; the index of the one checked.
    function fill() {
      menu.textContent = '';
      items = [];
      var into = menu, at = 0;
      entries().forEach(function (e) {
        if (e.group) {
          into = menu.appendChild(document.createElement('div'));
          into.setAttribute('role', 'group');
          into.setAttribute('aria-label', e.group);
          var h = into.appendChild(document.createElement('div'));
          h.className = 'group';
          h.setAttribute('aria-hidden', 'true');
          h.textContent = e.group;
          return;
        }
        var b = into.appendChild(document.createElement('button'));
        b.type = 'button';
        b.setAttribute('role', 'menuitemradio');
        b.setAttribute('aria-checked', String(!!e.on));
        b.textContent = e.text;
        if (e.note) b.appendChild(document.createElement('small')).textContent = e.note;
        b.addEventListener('click', function () {
          shut(true);
          e.pick();
        });
        if (e.on) at = items.length;
        items.push(b);
      });
      return at;
    }
    function open() {
      var at = fill();
      menu.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      if (items.length) items[at].focus();
      document.addEventListener('pointerdown', away, true);
    }
    // Drawn again while open: the browser's voices can arrive after it opened.
    box.refill = function () {
      if (menu.hidden) return;
      var had = menu.contains(document.activeElement), at = fill();
      if (had && items.length) items[at].focus();
    };
    // Closed by a choice, a second tap on its button, Escape, or a tap elsewhere.
    function shut(refocus) {
      if (menu.hidden) return;
      menu.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      document.removeEventListener('pointerdown', away, true);
      if (refocus) btn.focus();
    }
    function away(ev) { if (!box.contains(ev.target)) shut(false); }
    btn.addEventListener('click', function () { if (menu.hidden) open(); else shut(true); });
    shuts.push(shut);
    menu.addEventListener('keydown', function (ev) {
      var i = items.indexOf(document.activeElement);
      if (ev.key === 'Escape') { ev.preventDefault(); shut(true); }
      else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        items[(i + (ev.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus();
      } else if (ev.key === 'Tab') shut(false);
    });
    box.appendChild(btn);
    box.appendChild(menu);
    return box;
  }
  function speeds() {
    return dropup('ratebox', 'rate', 'speeds', 'Speed', function () {
      var now = rate();
      return RATES.map(function (r) {
        return { text: r + '×', on: r === now, pick: function () { S.set('rate', r); } };
      });
    });
  }
  // The voices the section being heard can be read in, as Settings lists them,
  // and each of the browser's under its own (Tigran, 2026-10-18).  Its
  // "Automatic" stays in Settings: here the voice it speaks with is checked.
  function voices() {
    var box = dropup('voicebox', 'voice', 'voices', 'Voice', function () {
      var out = [];
      for (var kk in D.voices) (function (kk, v) {
        out.push({ text: v.label, on: key === kk, pick: function () { S.set('voice', kk); },
                   note: v.credit || (v.kind === 'synthetic' ? 'an AI voice' : '') });
      })(kk, D.voices[kk]);
      if (!synth) return out;
      var all = S.usable(), cur = key === 'browser' && S.voice();
      function browser() { if (S.get().voice !== 'browser') S.set('voice', 'browser'); }
      if (!all.length)
        return out.concat({ text: 'Your browser’s voice', on: key === 'browser', pick: browser });
      out.push({ group: 'Your browser’s voice' });
      all.forEach(function (v) {
        out.push({ text: v.name, on: !!cur && cur.name === v.name,
                   pick: function () { S.set('bvoice', v.name); browser(); } });
      });
      return out;
    });
    // The name in a span of its own, which a long one runs out of (ub.css).
    box.firstChild.appendChild(document.createElement('span'));
    return box;
  }
  // The heading or paragraph being read, if this page has it.  A reference is
  // unique in the book, so on another page paras[ref] is simply not there.
  function reading() {
    var s = k >= 0 ? V.segs[k] : null;
    return !s ? null : s[0] ? paras[s[0]] || null : same(P, D) ? head : null;
  }
  // A message in the bar in place of what is being read, until something is
  // played again.  Kept, not only written: a recording that cannot be loaded
  // fires its error, then rejects play(), whose catch renders the bar, and the
  // message went with it.
  var trouble = null;
  function tell(msg) {
    trouble = msg;
    if (!bar) return;
    bar.querySelector('.at').hidden = true;
    bar.querySelector('.who').textContent = msg;
  }
  function render() {
    if (!bar) return;
    var tog = bar.querySelector('.toggle'), paused = !playing();
    tog.replaceChild(icon(paused ? 'play' : 'pause'), tog.firstChild);
    tog.setAttribute('aria-label', paused ? 'Play' : 'Pause');
    bar.querySelector('.rate').textContent = rate() + '×';
    var s = k >= 0 ? V.segs[k] : null, at = bar.querySelector('.at');
    at.hidden = !s;
    if (s) at.textContent = s[0] || D.paper + ':' + D.section;
    bar.querySelector('.who').textContent = s ? '' : 'End of the section';
    bar.querySelector('.voice span').textContent = vname();
    var on = bar.querySelector('.onward');
    on.hidden = !(k < 0 && D.next);
    if (D.next) { on.href = D.next.href + '#listen'; on.textContent = 'Next: ' + D.next.label + ' ›'; }
    if (trouble) {
      at.hidden = true;
      bar.querySelector('.who').textContent = trouble;
    }
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = paused ? 'paused' : 'playing';
  }

  // ---- playing ---------------------------------------------------------------
  // Segment i, played -- or with `quiet`, made ready, for play() to start.
  function go(i, quiet) {
    if (!V || i < 0 || i >= V.segs.length) return;
    trouble = null;
    if (!bar) {
      makeBar();
      // The paragraph the page was opened at has served its purpose: from now
      // on the mark is what is being read.
      Array.prototype.forEach.call(document.querySelectorAll('p.t.hit'),
                                   function (p) { p.classList.remove('hit'); });
    }
    k = i;
    if (V.kind === 'browser') {
      mark();
      meta();
      // The last paragraph, with the next section to come: fetch it now.
      if (i === V.segs.length - 1 && S.get().onward) fetchNext();
      if (!quiet) return speakFrom(0);
      said.n = 0;
      return render();
    }
    if (navigator.onLine === false) {
      tell(NEEDS_NET);
      return render();
    }
    var s = V.segs[i], t = s[2] / 1000;
    if (file !== s[1]) {
      file = s[1];
      audio.src = V.files[file];
      audio.preload = 'auto';
    }
    audio.defaultPlaybackRate = audio.playbackRate = rate();
    // Before the metadata is in, currentTime cannot be set everywhere; seek
    // once it arrives.
    if (audio.readyState >= 1) audio.currentTime = t;
    else audio.addEventListener('loadedmetadata', function f() {
      audio.removeEventListener('loadedmetadata', f);
      audio.currentTime = t;
    });
    mark();
    meta();
    var p = quiet ? null : audio.play();
    if (p && p.catch) p.catch(render);   // autoplay refused: the bar waits for a tap
    render();
  }
  function playing() { return V && V.kind === 'browser' ? said.on : !audio.paused; }
  function play() {
    if (k < 0) return go(0);
    if (V.kind === 'browser') { if (!said.on) speakFrom(said.n); } else audio.play();
  }
  function pause() { if (V && V.kind === 'browser') hush(); else audio.pause(); }
  function toggle() { if (k >= 0 && playing()) pause(); else play(); }
  // Once: this paragraph again, from its beginning, wherever in it the reading
  // is.  Twice in quick succession: the one before -- and each further quick
  // press one more.  Timed here, since a double tap is not reliably a dblclick
  // on a touch screen.
  var lastBack = 0;
  function back() {
    var now = Date.now(), again = now - lastBack < 400;
    lastBack = now;
    if (!V) return;
    if (k < 0) return go(V.segs.length - 1);
    go(again && k > 0 ? k - 1 : k);
  }
  // Ten seconds either way from the headphones; a sentence, for the browser's voice.
  function skip(d) {
    if (V && V.kind === 'browser') {
      if (k >= 0) speakFrom(Math.max(0, Math.min(said.n + d, said.parts.length - 1)));
    } else audio.currentTime = Math.max(0, audio.currentTime + 10 * d);
  }
  function forward() { if (k >= 0 && k + 1 < V.segs.length) go(k + 1); }
  function finish() {
    k = -1;
    mark();
    render();
  }
  // The end of the section: stop, or carry on if Settings says so.
  function done() {
    if (S.get().onward && D.next) carryOn(); else finish();
  }

  // ---- on into the next section, in this page --------------------------------
  var pending = null;                // {href, html}: the next section's page, coming
  function fetchNext() {
    var to = D.next;
    if (!to) return null;
    if (!pending || pending.href !== to.href) {
      // X-UB-Fetch tells the visit counter a page fetched ahead from one loaded.
      pending = { href: to.href, html: fetch(to.href, { credentials: 'same-origin',
                                                        headers: { 'X-UB-Fetch': 'next' } }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }) };
      pending.html.catch(function () {});
      if (key === 'browser') words(to.href);
    }
    return pending.html;
  }
  function carryOn() {
    var to = D.next;
    if (!to) return finish();
    k = -1;                            // nothing more to hear here
    fetchNext().then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var json = doc.getElementById('ub-audio');
      if (!doc.querySelector('main.reader') || !json) throw new Error('not a section page');
      pending = null;
      // The new section's files are numbered from 0 again: forget the old one.
      file = -1;
      if (same(P, D)) {
        // The page shows the section that has ended: the next one takes its place.
        push(to.href);
        swap(doc);
        scrollTo(0, 0);
        D = P; V = PV; key = pkey;
      } else {
        // The reader is elsewhere: what is heard moves on, and the page stays.
        D = JSON.parse(json.textContent);
        D.ids = ids(doc);
        key = choose(D);
        V = voiceOf(D, key);
      }
      if (V) go(0); else finish();
    }).catch(function () {
      // Offline, or the page changed shape: the link still works.
      pending = null;
      finish();
    });
  }

  // ---- moving about while listening -------------------------------------------
  // Leaving the page would stop the reading, so while the bar is open and Follow
  // along is off, the site's own pages are fetched and swapped in instead
  // (every page has one <main>).  With Follow along on, a link loads its page
  // as ever, and playing stops.  Anything that goes wrong falls back to that.
  var moved = false, visiting = 0, shown = location.pathname + location.search;
  function roaming() { return !!bar && !S.get().follow; }
  // The address for what is now to be shown.  The page being left keeps its
  // scroll position, for Back.
  function push(url) {
    history.replaceState({ y: scrollY }, '');
    history.pushState(null, '', url);
    history.scrollRestoration = 'manual';
    moved = true;
    shown = location.pathname + location.search;
  }
  function swap(doc) {
    document.querySelector('main').replaceWith(document.adoptNode(doc.querySelector('main')));
    document.title = doc.title;
    var q = document.querySelector('.find input'), nq = doc.querySelector('.find input');
    if (q && nq) q.value = nq.value;
    var json = doc.getElementById('ub-audio');
    P = json ? JSON.parse(json.textContent) : null;
    if (json) data.textContent = json.textContent;
    scan();
    marked = null;
    build();
    mark();
    document.dispatchEvent(new CustomEvent('ub:swap'));   // ub.js: the rail's place
  }
  // Show url in this page: pushed as a new address, or (from Back) restored to y.
  // `then` runs once it is in.
  function visit(url, isNew, y, then) {
    var n = ++visiting, hash = new URL(url, location.href).hash;
    fetch(url, { credentials: 'same-origin', headers: { 'X-UB-Fetch': 'swap' } }).then(function (r) {
      if (!/text\/html/.test(r.headers.get('content-type') || '')) throw new Error('not a page');
      return r.text().then(function (html) { return { url: r.url || url, html: html }; });
    }).then(function (got) {
      if (n !== visiting) return;      // overtaken by a later one
      var doc = new DOMParser().parseFromString(got.html, 'text/html');
      if (!doc.querySelector('main')) throw new Error('not a page');
      // A redirect (/101 to /101:0, a citation searched for) lands at its real address.
      if (isNew) push(got.url.split('#')[0] + hash);
      else shown = location.pathname + location.search;
      swap(doc);
      if (y != null) scrollTo(0, y);
      else {
        scrollTo(0, 0);
        document.dispatchEvent(new CustomEvent('ub:page'));   // ub.js: to the paragraph cited
      }
      if (then) then();
    }).catch(function () {
      if (n !== visiting) return;
      history.scrollRestoration = 'auto';
      if (isNew) location.href = url; else location.reload();
    });
  }
  var SKIP = /^\/(static|audio|speech|healthz|favicon|apple-touch-icon)\b/;
  document.addEventListener('click', function (ev) {
    if (!roaming() || ev.defaultPrevented || ev.button || ev.metaKey || ev.ctrlKey ||
        ev.shiftKey || ev.altKey) return;
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || a.target || a.hasAttribute('download')) return;
    var u = new URL(a.href, location.href);
    if (u.origin !== location.origin || SKIP.test(u.pathname)) return;
    if (u.pathname + u.search === shown && u.hash) return;   // a place on this page
    ev.preventDefault();
    visit(u.href, true);
  });
  document.addEventListener('submit', function (ev) {
    var f = ev.target;
    if (!roaming() || ev.defaultPrevented || !f.matches || !f.matches('form.find')) return;
    ev.preventDefault();
    visit(f.action + '?' + new URLSearchParams(new FormData(f)), true);
  });
  // Back and Forward: the address has changed, so the page must too -- in the
  // page while listening, else by loading it.
  addEventListener('popstate', function (ev) {
    if (!moved || location.pathname + location.search === shown) return;
    if (bar) visit(location.href, false, ev.state ? ev.state.y : null);
    else { history.scrollRestoration = 'auto'; location.reload(); }
  });
  // What is being read, into view: from its own page, fetched, if this is
  // another.  Only if it is leaving the screen, unless `always`.
  function toReading(always) {
    touched = 0;                       // and Follow along takes over again
    if (k < 0) return;
    var el = reading();
    if (!el) return visit(href(D), true, null, function () { var e = reading(); if (e) show(e); });
    var r = el.getBoundingClientRect();
    if (always || r.top < 40 || r.bottom > innerHeight - 80) show(el);
  }
  function close() {
    hush();
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    file = k = -1;
    mark();
    shuts.forEach(function (f) { f(false); });
    if (bar) { bar.remove(); bar = null; }
    document.body.classList.remove('listening');
  }

  // Another voice, chosen in the bar's list or in Settings: what is being heard
  // goes on in it from the start of the same paragraph, playing if it was, or
  // if it was asked to and could not.  A paragraph the new voice does not read
  // (Merritt Horn's leaves a few out, data/audio/mh-unread.tsv) gives way to
  // the next one it does.  Until 2026-10-18 a new voice closed the bar.
  function revoice() {
    build();
    if (!bar) return;
    var nk = choose(D);
    if (!nk) return close();
    if (nk === key) return render();
    var was = k >= 0 && (playing() || !!trouble), rest = k >= 0 ? V.segs.slice(k) : [];
    hush();
    audio.pause();
    if (nk === 'browser') { audio.removeAttribute('src'); audio.load(); }
    file = -1;
    V = same(D, P) ? PV : voiceOf(D, nk);
    key = nk;
    if (k < 0) return render();
    for (var j = 0; j < rest.length; j++)
      for (var i = 0; i < V.segs.length; i++)
        if (V.segs[i][0] === rest[j][0]) return go(i, !was);
    finish();
  }

  // The segment that holds the playhead, within the file now loaded.
  function locate() {
    var t = audio.currentTime * 1000;
    for (var i = 0; i < V.segs.length; i++) {
      var s = V.segs[i];
      if (s[1] === file && t >= s[2] && t < s[3]) return i;
    }
    return k;
  }
  audio.addEventListener('timeupdate', function () {
    if (k < 0 || !V) return;
    var i = locate();
    if (i !== k) { k = i; mark(); render(); }
    // Past the last paragraph a file holds: a recording may run on into
    // silence, or into a second reading of the next section.  Move on.
    var s = V.segs[k], nx = V.segs[k + 1];
    if (audio.currentTime * 1000 >= s[3] && (!nx || nx[1] !== file)) {
      if (nx) go(k + 1);
      else { audio.pause(); done(); }
      return;
    }
    // Into the last paragraph, with the next section to come: fetch it now.
    if (!nx && S.get().onward) fetchNext();
  });
  audio.addEventListener('ended', function () {
    if (k < 0) return;
    if (k + 1 < V.segs.length && V.segs[k + 1][1] !== file) go(k + 1);
    else done();
  });
  audio.addEventListener('play', render);
  audio.addEventListener('pause', render);
  audio.addEventListener('error', function () {
    if (audio.getAttribute('src'))
      tell(navigator.onLine === false ? NEEDS_NET
                                      : 'The recording could not be loaded. Your browser\u2019s voice can read without it.');
  });

  // ---- the browser's own voice -----------------------------------------------
  // It reads the spoken text (build/speech.py: numbers in words, list marks
  // spoken, brackets gone), a sentence at a time: Chrome's online voices fall
  // silent partway through a long utterance, and a sentence is where pausing
  // resumes.  Pausing is cancelling -- pause() does nothing on Android -- and
  // `gen` tells a cancelled utterance's late events from the live one's.
  var said = { parts: [], n: 0, on: false, gen: 0, u: null };
  function fetchWords(href) {
    var p = fetch('/speech' + href, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (j) {
      var m = {};
      j.segs.forEach(function (s) { m[s[0] || ''] = s[1]; });   // '' the heading
      return m;
    });
    p.catch(function () {});
    return p;
  }
  // A section's spoken text, {map, wait}, kept for the last few sections: the
  // one being heard, the one on the page, and the next.
  var texts = {};
  function words(h) {
    var t = texts[h];
    if (t) return t;
    var old = Object.keys(texts);
    if (old.length >= 4) delete texts[old[0]];
    t = texts[h] = { map: null, wait: fetchWords(h) };
    t.wait.then(function (m) { t.map = m; }, function () { if (texts[h] === t) delete texts[h]; });
    return t;
  }
  // The heading, then every paragraph of section h, ids.  Its text is fetched
  // now, so that a tap starts it at once: iOS speaks only in answer to one.
  function spoken(ids, h) {
    var segs = [[null]].concat(ids.map(function (id) { return [id]; }));
    words(h);
    return { label: 'Your browser\u2019s voice', kind: 'browser', by: 'paragraph', segs: segs };
  }
  // Pieces of a sentence or so, none longer than LONG characters (about ten
  // seconds): short sentences together, a longer one cut after the comma,
  // semicolon or dash nearest its middle.  A sentence ends where a capital
  // follows, so "A.D. the" is not cut.
  var LONG = 160;
  function pieces(t) {
    var out = [], from = 0, re = /[.!?]+["'\u201d\u2019)]*\s+(?=["'\u201c\u2018(]?[A-Z])/g, m, all = [];
    while ((m = re.exec(t))) { all.push(t.slice(from, m.index + m[0].length)); from = re.lastIndex; }
    all.push(t.slice(from));
    all.forEach(function cut(s) {
      s = s.trim();
      if (!s) return;
      if (s.length <= LONG) return void out.push(s);
      var mid = s.length / 2, at = -1, re = /[,;:\u2014\u2013] ?/g, m;
      while ((m = re.exec(s)))
        if (m.index > 20 && m.index < s.length - 20 &&
            (at < 0 || Math.abs(m.index - mid) < Math.abs(at - mid))) at = m.index + 1;
      if (at < 0) at = s.lastIndexOf(' ', mid);
      if (at < 20) return void out.push(s);
      cut(s.slice(0, at));
      cut(s.slice(at));
    });
    return out.reduce(function (a, s) {
      var n = a.length;
      if (n && a[n - 1].length + 1 + s.length <= LONG) a[n - 1] += ' ' + s; else a.push(s);
      return a;
    }, []);
  }
  // Paragraph k, from its nth piece.
  function speakFrom(n) {
    var gen = ++said.gen;
    said.on = true;
    said.n = n;
    hold(true);
    render();
    var t = words(href(D));
    if (t.map) return begin(gen, t.map);
    t.wait.then(function (m) { if (gen === said.gen) begin(gen, m); }, function () {
      if (gen !== said.gen) return;
      hush();
      tell(navigator.onLine === false ? 'Offline, this needs Work offline: the cloud at the top of the page.' : 'The text could not be loaded.');
    });
  }
  function begin(gen, m) {
    said.parts = pieces(m[V.segs[k][0] || ''] || '');
    if (synth.speaking || synth.pending) {
      // Safari can drop an utterance spoken straight after a cancel.
      synth.cancel();
      setTimeout(function () { if (gen === said.gen) utter(gen); }, 50);
    } else utter(gen);
  }
  function utter(gen) {
    if (said.n >= said.parts.length) {               // the paragraph is done
      if (k + 1 < V.segs.length) return go(k + 1);
      hush();
      return done();
    }
    var u = new SpeechSynthesisUtterance(said.parts[said.n]), v = S.voice();
    if (v) u.voice = v;
    u.lang = v ? v.lang : 'en-US';
    u.rate = rate();
    u.onend = function () {
      if (gen !== said.gen) return;
      said.n++;
      utter(gen);
    };
    u.onerror = function (e) {
      if (gen !== said.gen || e.error === 'interrupted' || e.error === 'canceled') return;
      hush();
      // Refused before a tap (arriving by "#listen"): the bar waits for one.
      if (e.error === 'not-allowed') return;
      // Chrome's Google voices and Edge's Natural ones are spoken by a server.
      var bv = S.voice();
      tell(navigator.onLine === false && bv && !bv.localService
           ? bv.name + ' needs a connection, and this browser has no voice of its own.'
           : 'Your browser could not speak (' + e.error + ').');
    };
    said.u = u;                     // Chrome drops the events of an utterance nothing holds
    synth.speak(u);
  }
  function hush() {
    said.gen++;
    said.on = false;
    if (synth && (synth.speaking || synth.pending)) synth.cancel();
    hold(false);
    render();
  }
  // The screen stays on while the browser speaks: a phone that locks it stops
  // the speech, which, unlike a recording, cannot play on with it off.
  var lock = null;                  // a promise of the screen wake lock
  function hold(on) {
    if (on && !lock && navigator.wakeLock && document.visibilityState === 'visible') {
      var p = lock = navigator.wakeLock.request('screen');
      p.then(function (l) {
        l.addEventListener('release', function () { if (lock === p) lock = null; });
      }, function () { if (lock === p) lock = null; });
    } else if (!on && lock) {
      var q = lock;
      lock = null;
      q.then(function (l) { l.release(); }, function () {});
    }
  }
  // Out of sight, a phone may silence the speech and drop the wake lock; back
  // in sight, take up the sentence again.
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible' || !said.on) return;
    hold(true);
    if (!synth.speaking && !synth.pending) speakFrom(said.n);
  });
  // The browser names its voices only once it has them.
  function relabel() {
    if (voiceMenu) voiceMenu.refill();
    if (!V || V.kind !== 'browser') return;
    render();
    if (k >= 0) meta();
  }
  if (synth && synth.addEventListener) synth.addEventListener('voiceschanged', relabel);

  // ---- following along -------------------------------------------------------
  var touched = 0;
  ['wheel', 'touchmove', 'keydown'].forEach(function (e) {
    addEventListener(e, function () { touched = Date.now(); }, { passive: true });
  });
  function mark() {
    var el = reading();
    if (el === marked) return;
    if (marked) marked.classList.remove('now');
    marked = el;
    if (!el) return;
    el.classList.add('now');
    // Not while the reader is scrolling on their own, and only when it is
    // actually leaving the screen.
    if (!S.get().follow || Date.now() - touched < 4000) return;
    var r = el.getBoundingClientRect();
    if (r.top < 40 || r.bottom > innerHeight - 80) show(el);
  }
  // A paragraph taller than most of the screen is brought in by its first line;
  // centred, its beginning would be off the top.
  function show(el) {
    el.scrollIntoView({ block: el.getBoundingClientRect().height > innerHeight * 0.6 ? 'start' : 'center',
                        behavior: 'smooth' });
  }

  // ---- the lock screen and headphones --------------------------------------
  function meta() {
    if (!('mediaSession' in navigator) || !window.MediaMetadata) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: D.title, artist: vname(), album: 'The Urantia Book',
      artwork: [{ src: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' }]
    });
  }
  if ('mediaSession' in navigator) {
    var ms = navigator.mediaSession;
    [['play', play], ['pause', pause],
     ['previoustrack', back], ['nexttrack', forward], ['stop', close],
     ['seekbackward', function () { skip(-1); }], ['seekforward', function () { skip(1); }]
    ].forEach(function (h) { try { ms.setActionHandler(h[0], h[1]); } catch (e) {} });
  }

  document.addEventListener('ub:settings', function (ev) {
    var what = ev.detail.key;
    if (what === 'rate') {
      audio.playbackRate = audio.defaultPlaybackRate = rate();
      if (said.on) speakFrom(said.n);             // the sentence again, at the new speed
      render();
    }
    if (what === 'bvoice') { relabel(); if (said.on) speakFrom(said.n); }
    if (what === 'voice') revoice();
    // Following again, from another page: back to the reading.
    if (what === 'follow' && S.get().follow) toReading(false);
  });

  build();
  // Arrived from "Next" at the end of the previous section: carry on.
  if (location.hash === '#listen') {
    history.replaceState(null, '', location.pathname + location.search);
    if (PV) start(0);
  }
})();
