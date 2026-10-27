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
// A translation is read by the browser's voice too (Tigran, 2026-10-27), from
// the ▶ in its column in Compare, where each is a text of its own, read on
// from there, or chosen in the bar's list of voices: "browser:<key>", its
// paragraphs those whose row's fold has it (.tf[data-has]), its words
// /speech/<key>/<section>, its voice the one Settings gives it in its
// language (trvoices).  Which text is heard is the ▶ pressed, never a
// setting: the English's ▶ reads the English.  Its line is marked in its
// column, or with Follow along in the paragraph's fold, which opens for it
// (ub.js ubTrRead).  Carrying on stops at a section it has none of.
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
  var S = window.ubSettings, T = window.ubT;   // T: the interface's words (ubsite/l10n.js)
  if (!data || !S) return;
  var P = JSON.parse(data.textContent);  // the section the page shows; null on any other page
  // The translations (base.html's #ub-translations): {key: {lang, label, language, ...}}.
  var TRS = {};
  try {
    JSON.parse((document.getElementById('ub-translations') || {}).textContent || '[]')
      .forEach(function (x) { TRS[x.key] = x; });
  } catch (e) {}
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
  // `label` a key of ru.toml, or its words made (T.tr()).
  function button(cls, label, name) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    T.attr(b, 'aria-label', label);
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
  // Those each translation has, {key: [ids]}, by the folds under their rows.
  function trIds(root) {
    var out = {};
    Array.prototype.forEach.call(root.querySelectorAll('.tf[data-has]'), function (tf) {
      var lines = ids(tf.parentNode);
      tf.dataset.has.split(' ').forEach(function (kk) {
        out[kk] = (out[kk] || []).concat(lines);
      });
    });
    return out;
  }
  // The translation a voice reads, "browser:ud", if the site has it; else null.
  function trOf(kk) {
    var m = /^browser:(.+)$/.exec(kk || '');
    return m && TRS[m[1]] ? m[1] : null;
  }
  function ticked() { return String(S.get().translations || '').split(' ').filter(function (kk) { return TRS[kk]; }); }
  function scan() {
    // The section's title, or over an introduction, which has none, the
    // paper's: what its spoken heading reads.
    head = document.querySelector('.papertop h2') || document.querySelector('.papertop h1');
    paras = {};
    Array.prototype.forEach.call(document.querySelectorAll('p.t[id]'),
                                 function (p) { paras[p.id] = p; });
    if (P) { P.ids = ids(document); P.tr = trIds(document); }
  }
  scan();

  // The voice Settings asks for, else the first section d has.
  function choose(d) {
    var want = S.get().voice;
    if (S.get().listen === false) return null;
    if (want === 'browser' && synth) return want;
    if (want && d.voices[want]) return want;
    for (var v in d.voices) return v;
    return null;
  }
  // Offline a recording cannot be had: the voice Settings names is not changed
  // for another (Tigran, 2026-10-13), the bar says why it does not play once
  // it has failed (audio's error), and its voice menu stands beside the message.
  var NEEDS_NET = T.k('The recordings need a connection. Offline, your browser\u2019s voice can read it.');
  // Section d's voice kk; the browser's is made from its paragraphs, d.ids,
  // or a translation's, those it has.
  function voiceOf(d, kk) {
    var t = trOf(kk);
    return kk === 'browser' ? spoken(d.ids, href(d)) : t ? spoken(d.tr[t] || [], href(d), t)
                            : kk ? d.voices[kk] : null;
  }
  function href(d) { return '/' + d.paper + ':' + d.section; }
  function same(a, b) { return !!(a && b && a.paper === b.paper && a.section === b.section); }
  function rate() { var r = S.get().rate; return RATES.indexOf(r) < 0 ? 1 : r; }
  // What the bar and the lock screen call the voice, in each language: for
  // the browser's, the name of the one it speaks with, once the browser has
  // said, which is the same in both.
  // A translation's is named by its short name too: "Aivazian · Google русский".
  function vname() {
    if (V.kind !== 'browser') return word(V.label);
    var v = S.voice(V.lang, V.tr), x = V.tr && TRS[V.tr];
    var name = v ? T.same(v.name) : T.tr('Your browser\u2019s voice');
    return x ? T.tr('{a} · {b}', { a: T.html(x.label), b: name }) : name;
  }
  // A name from the database (a voice's, its credit): its words where ru.toml
  // has them (app.py puts them in l10n.js), else as it is.
  function word(s) { return T.has(s) ? T.tr(s) : T.same(s); }

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
      c.innerHTML = T(word(PV.credit));
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
      if (p0) place(p0, 0, T.k('Listen to this section'));
      return;
    }
    var first = true;
    PV.segs.forEach(function (s, i) {
      var p = s[0] && paras[s[0]];
      if (!p) return;
      if (first && PV.segs[0][0] === null) place(p, 0, T.k('Listen to this section, from its heading'));
      else place(p, i, T.tr('Listen from {r}', { r: s[0] }));
      first = false;
    });
  }
  // A press on the page's own controls: what is heard becomes what the page
  // shows, in the page's voice, or with a translation's ▶ in that one, nv
  // (kk its key).
  function start(i, nv, kk) {
    nv = nv || PV;
    kk = kk || pkey;
    if (V && V.kind !== nv.kind) { hush(); audio.pause(); }
    // Another section's files, or another voice's: they are numbered afresh.
    if (!same(D, P) || key !== kk) file = -1;
    if (V && V.tr && !nv.tr && window.ubTrRead) window.ubTrRead(null);
    D = P; V = nv; key = kk;
    unmark();
    go(i);
  }
  // A translation's ▶ in Compare, in each of its cells (ub.js 'ub:cmp'): it
  // reads that translation from that paragraph, from the heading at the
  // section's first, as the English's does.
  function trPlay(root) {
    if (!P || !P.tr || !synth) return;
    Array.prototype.forEach.call(root.querySelectorAll('.rc[data-k]'), function (rc) {
      var t = rc.dataset.k, line = rc.querySelector('p.rt[data-ref]'), x = TRS[t];
      if (!line || !x || !P.tr[t] || rc.querySelector(':scope > .playp')) return;
      var ref = line.dataset.ref;
      var b = button('playp', T.tr('Listen to {l} from {r}', { l: T.html(x.label), r: ref }), 'play');
      b.addEventListener('click', function () {
        var kk = 'browser:' + t, nv = voiceOf(P, kk), i = 0;
        if (ref !== P.ids[0])
          while (i < nv.segs.length && nv.segs[i][0] !== ref) i++;
        if (i < nv.segs.length) start(i, nv, kk);
      });
      rc.appendChild(b);                 // last: .who:first-child keeps its place (ub.css)
    });
  }
  document.addEventListener('ub:cmp', function (ev) { trPlay(ev.detail); });

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
    T.attr(bar, 'aria-label', 'Listening');
    var prev = button('prev', T.k('Back to the start of this paragraph (twice: the one before)'), 'prev');
    T.attr(prev, 'title', 'Back to the start of this paragraph (twice: the one before)');
    var tog = button('toggle', T.k('Play'), 'play');
    var nxt = button('next', T.k('Next paragraph'), 'next');
    // What is being read, and by whom.  A tap on the reference brings its
    // paragraph into view.
    var where = document.createElement('span');
    where.className = 'where';
    var at = document.createElement('button');
    at.type = 'button';
    at.className = 'at';
    T.attr(at, 'title', 'Show this paragraph');
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
      carryOn(true);
    });
    var x = button('close', T.k('Stop and close'), 'close');
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
  // lists and which is checked are current: [{html, on, pick, note}, ...], each
  // its words as HTML (T()), with {group}, a key, for a heading over the
  // entries after it.  `label` a key.
  function dropup(boxCls, btnCls, menuCls, label, entries) {
    var box = document.createElement('span');
    box.className = boxCls;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = btnCls;
    T.attr(btn, 'aria-label', label);
    btn.setAttribute('aria-haspopup', 'menu');
    btn.setAttribute('aria-expanded', 'false');
    var menu = document.createElement('div');
    menu.className = menuCls;
    menu.setAttribute('role', 'menu');
    T.attr(menu, 'aria-label', label);
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
          T.attr(into, 'aria-label', e.group);
          var h = into.appendChild(document.createElement('div'));
          h.className = 'group';
          h.setAttribute('aria-hidden', 'true');
          h.innerHTML = T(e.group);
          return;
        }
        var b = into.appendChild(document.createElement('button'));
        b.type = 'button';
        b.setAttribute('role', 'menuitemradio');
        b.setAttribute('aria-checked', String(!!e.on));
        b.innerHTML = e.html;
        if (e.note) b.appendChild(document.createElement('small')).innerHTML = e.note;
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
    return dropup('ratebox', 'rate', 'speeds', T.k('Speed'), function () {
      var now = rate();
      return RATES.map(function (r) {
        return { html: T('{r}×', { r: T.dec(r) }), on: r === now, pick: function () { S.set('rate', r); } };
      });
    });
  }
  // The voices the section being heard can be read in, as Settings lists them,
  // and each of the browser's under its own (Tigran, 2026-10-18).  Its
  // "Automatic" stays in Settings: here the voice it speaks with is checked.
  function voices() {
    var box = dropup('voicebox', 'voice', 'voices', T.k('Voice'), function () {
      var out = [];
      for (var kk in D.voices) (function (kk, v) {
        out.push({ html: T(word(v.label)), on: key === kk, pick: function () { S.set('voice', kk); hear(kk); },
                   note: v.credit ? T(word(v.credit)) : v.kind === 'synthetic' ? T('an AI voice') : '' });
      })(kk, D.voices[kk]);
      if (!synth) return out;
      var all = S.usable(), cur = key === 'browser' && S.voice();
      function browser() { S.set('voice', 'browser'); hear('browser'); }
      if (!all.length)
        out.push({ html: T('Your browser’s voice'), on: key === 'browser', pick: browser });
      else {
        out.push({ group: T.k('Your browser’s voice') });
        all.forEach(function (v) {
          out.push({ html: T.esc(v.name), on: !!cur && cur.name === v.name,
                     pick: function () { S.set('bvoice', v.name); browser(); } });
        });
      }
      // Each translation ticked that the section has, in Settings' order, over
      // the browser's voices in its language; none, where the browser has
      // listed voices and none of them in it.  Until it lists any, the
      // translation alone.
      var listed = synth.getVoices().length;
      ticked().forEach(function (t) {
        var x = TRS[t], kk = 'browser:' + t, them = S.usable(x.lang), now = key === kk && S.voice(x.lang, t);
        var name = T.tr('{a} · {b}', { a: T.html(x.label), b: x.language });
        function pick() { hear(kk); }
        if (!D.tr || !D.tr[t] || (listed && !them.length)) return;
        if (!them.length) return out.push({ html: T(name), on: key === kk, pick: pick });
        out.push({ group: name });
        them.forEach(function (v) {
          out.push({ html: T.esc(v.name), on: !!now && now.name === v.name,
                     pick: function () { S.setTrVoice(t, v.name); pick(); } });
        });
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
  // played again, as HTML (T()).  Kept, not only written: a recording that cannot be loaded
  // fires its error, then rejects play(), whose catch renders the bar, and the
  // message went with it.
  var trouble = null;
  function tell(msg) {
    trouble = msg;
    if (!bar) return;
    bar.querySelector('.at').hidden = true;
    bar.querySelector('.who').innerHTML = msg;
  }
  function render() {
    if (!bar) return;
    var tog = bar.querySelector('.toggle'), paused = !playing();
    tog.replaceChild(icon(paused ? 'play' : 'pause'), tog.firstChild);
    T.attr(tog, 'aria-label', paused ? T.k('Play') : T.k('Pause'));
    bar.querySelector('.rate').innerHTML = T('{r}×', { r: T.dec(rate()) });
    var s = k >= 0 ? V.segs[k] : null, at = bar.querySelector('.at');
    at.hidden = !s;
    if (s) at.textContent = s[0] || D.paper + ':' + D.section;
    bar.querySelector('.who').innerHTML = s ? '' : T('End of the section');
    bar.querySelector('.voice span').innerHTML = T(vname());
    var on = bar.querySelector('.onward');
    on.hidden = !(k < 0 && D.next);
    // The next section's name, as app.py makes it in each language.
    if (D.next) {
      on.href = D.next.href + '#listen';
      on.innerHTML = T('Next: {l} ›', { l: { en: T.esc(D.next.label), ru: T.esc(D.next.label_ru || D.next.label) } });
    }
    if (trouble) {
      at.hidden = true;
      bar.querySelector('.who').innerHTML = trouble;
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
    // Tried even where the browser says it is offline, which Chrome can say
    // with the network working (2026-10-27): offline indeed, the recording
    // fails at once, and the error below says it needs a connection.
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
      if (V && V.kind === 'browser') words(to.href, V.tr);
    }
    return pending.html;
  }
  // `tapped`: "Next", which goes on into a section a translation being read
  // has none of, where carrying on by itself stops (Tigran, 2026-10-27).
  function carryOn(tapped) {
    var to = D.next;
    if (!to) return finish();
    k = -1;                            // nothing more to hear here
    fetchNext().then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var json = doc.getElementById('ub-audio');
      if (!doc.querySelector('main.reader') || !json) throw new Error('not a section page');
      if (!tapped && V && V.tr && !doc.querySelector('.tf[data-has~="' + V.tr + '"]')) {
        finish();
        return tell(T('The next section is not in {l}.', { l: T.html(TRS[V.tr].label) }));
      }
      pending = null;
      // The new section's files are numbered from 0 again: forget the old one.
      file = -1;
      // A translation goes on where the next section has it; else the English.
      var t = trOf(key), kk = null;
      if (same(P, D)) {
        // The page shows the section that has ended: the next one takes its place.
        push(to.href + (CMP.test(location.pathname) ? '/compare' : ''));   // ub.js: Compare goes on
        swap(doc);
        scrollTo(0, 0);
        D = P;
        kk = t && D.tr[t] ? key : null;
        if (kk) V = voiceOf(D, kk); else { V = PV; key = pkey; }
      } else {
        // The reader is elsewhere: what is heard moves on, and the page stays.
        D = JSON.parse(json.textContent);
        D.ids = ids(doc);
        D.tr = trIds(doc);
        key = t && D.tr[t] ? key : choose(D);
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
  // A page and the same page in Compare (ub.js) are one page here: Compare
  // draws itself in place, and its own entries in the history are its own.
  var CMP = /\/compare$/;
  function bare(path, search) { return path.replace(CMP, '') + search; }
  var moved = false, visiting = 0, shown = bare(location.pathname, location.search);
  function roaming() { return !!bar && !S.get().follow; }
  // The address for what is now to be shown.  The page being left keeps its
  // scroll position, for Back.
  function push(url) {
    history.replaceState({ y: scrollY }, '');
    history.pushState(null, '', url);
    history.scrollRestoration = 'manual';
    moved = true;
    shown = bare(location.pathname, location.search);
  }
  function swap(doc) {
    document.querySelector('main').replaceWith(document.adoptNode(doc.querySelector('main')));
    // The tab's title, its element whole, with its Russian (base.html), and in
    // the reader's language (ubLang).
    var nt = doc.querySelector('title'), ot = document.querySelector('title');
    if (nt && ot) ot.replaceWith(document.adoptNode(nt));
    else document.title = doc.title;
    if (window.ubTitle) window.ubTitle();
    var q = document.querySelector('.find input'), nq = doc.querySelector('.find input');
    if (q && nq) q.value = nq.value;
    var json = doc.getElementById('ub-audio');
    P = json ? JSON.parse(json.textContent) : null;
    if (json) data.textContent = json.textContent;
    scan();
    marked = line = null;
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
      else shown = bare(location.pathname, location.search);
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
    if (bare(u.pathname, u.search) === shown && u.hash) return;   // a place on this page
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
    if (!moved || bare(location.pathname, location.search) === shown) return;
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
    if (window.ubTrRead) window.ubTrRead(null);
    shuts.forEach(function (f) { f(false); });
    if (bar) { bar.remove(); bar = null; }
    document.body.classList.remove('listening');
  }

  // Another voice, chosen in the bar's list or in Settings: what is being heard
  // goes on in it from the start of the same paragraph, playing if it was, or
  // if it was asked to and could not.  A paragraph the new voice does not read
  // (Merritt Horn's leaves a few out, data/audio/mh-unread.tsv) gives way to
  // the next one it does.  Until 2026-10-18 a new voice closed the bar.
  // `want`: the voice to go on in, else the one Settings asks for.
  function revoice(want) {
    build();
    if (!bar) return;
    var nk = want || choose(D);
    if (!nk) return close();
    if (nk === key) return render();
    var was = k >= 0 && (playing() || !!trouble), rest = k >= 0 ? V.segs.slice(k) : [];
    hush();
    audio.pause();
    if (nk === 'browser') { audio.removeAttribute('src'); audio.load(); }
    file = -1;
    V = same(D, P) && nk === pkey ? PV : voiceOf(D, nk);
    key = nk;
    // Marked again in the new voice: a translation's line, or none.
    unmark();
    if (!V.tr && window.ubTrRead) window.ubTrRead(null);
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
      tell(navigator.onLine === false ? T(NEEDS_NET)
                                      : T('The recording could not be loaded. Your browser\u2019s voice can read without it.'));
  });

  // ---- the browser's own voice -----------------------------------------------
  // It reads the spoken text (build/speech.py: numbers in words, list marks
  // spoken, brackets gone), a sentence at a time: Chrome's online voices fall
  // silent partway through a long utterance, and a sentence is where pausing
  // resumes.  Pausing is cancelling -- pause() does nothing on Android -- and
  // `gen` tells a cancelled utterance's late events from the live one's.
  var said = { parts: [], n: 0, on: false, gen: 0, u: null };
  // Section h's spoken text, the English's, or translation t's.
  function fetchWords(href, t) {
    var p = fetch('/speech' + (t ? '/' + t : '') + href, { credentials: 'same-origin' }).then(function (r) {
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
  // A section's spoken text, {map, wait}, in the English or translation tr,
  // kept for the last few: the one being heard, the one on the page, and the
  // next.
  var texts = {};
  function words(h, tr) {
    var at = (tr || '') + h, t = texts[at];
    if (t) return t;
    var old = Object.keys(texts);
    if (old.length >= 4) delete texts[old[0]];
    t = texts[at] = { map: null, wait: fetchWords(h, tr) };
    t.wait.then(function (m) { t.map = m; }, function () { if (texts[at] === t) delete texts[at]; });
    return t;
  }
  // The heading, then every paragraph of section h, ids, in the English or
  // translation tr.  Its text is fetched now, so that a tap starts it at once:
  // iOS speaks only in answer to one.  A paragraph or heading it has no words
  // for is passed over.
  function spoken(ids, h, tr) {
    var segs = [[null]].concat(ids.map(function (id) { return [id]; }));
    words(h, tr);
    return { label: 'Your browser\u2019s voice', kind: 'browser', by: 'paragraph', segs: segs,
             tr: tr || null, lang: tr ? TRS[tr].lang : 'en' };
  }
  // Pieces of a sentence or so, none longer than LONG characters (about ten
  // seconds): short sentences together, a longer one cut after the comma,
  // semicolon or dash nearest its middle.  A sentence ends where a capital
  // follows, Latin or Cyrillic, so "A.D. the" is not cut.
  var LONG = 160;
  function pieces(t) {
    var out = [], from = 0, re = /[.!?\u2026]+["'\u201d\u2019\u201c\u00bb)]*\s+(?=["'\u201c\u2018\u00ab\u201e(]?[A-Z\u0410-\u042f\u0401])/g, m, all = [];
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
    var t = words(href(D), V.tr);
    if (t.map) return begin(gen, t.map);
    t.wait.then(function (m) { if (gen === said.gen) begin(gen, m); }, function () {
      if (gen !== said.gen) return;
      hush();
      // Offline, a translation is read from its own download (Settings' Offline tab).
      tell(navigator.onLine !== false ? T('The text could not be loaded.')
           : V.tr ? T('tr:notkept') : T('Offline, this needs Work offline: the cloud at the top of the page.'));
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
    var u = new SpeechSynthesisUtterance(said.parts[said.n]), v = S.voice(V.lang, V.tr);
    // A browser that has said what voices it has, and has none in a
    // translation's language, would read it in another's.
    if (!v && V.tr && synth.getVoices().length) {
      hush();
      return tell(T('This browser has no voice for {l}.', { l: T.html(TRS[V.tr].label) }));
    }
    if (v) u.voice = v;
    u.lang = v ? v.lang : V.tr ? TRS[V.tr].lang : 'en-US';
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
      var bv = S.voice(V.lang, V.tr);
      tell(navigator.onLine === false && bv && !bv.localService
           ? T('{v} needs a connection, and this browser has no voice of its own.', { v: bv.name })
           : T('Your browser could not speak ({e}).', { e: e.error }));
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
  // A translation's line being read is marked as well, where the page shows
  // it: in its fold, which Follow along opens, or its column (ub.js
  // ubTrRead), and it is what is kept in view.
  var line = null;
  function lineMark(el) {
    if (line) line.classList.remove('now');
    line = el;
    if (el) el.classList.add('now');
  }
  function unmark() {
    if (marked) marked.classList.remove('now');
    marked = null;
    lineMark(null);
  }
  // Another text heard, from the bar's list: from the start of the same paragraph.
  function hear(kk) { if (bar && kk !== key) revoice(kk); }
  function mark() {
    var el = reading();
    if (el === marked) return;
    if (marked) marked.classList.remove('now');
    marked = el;
    lineMark(null);
    if (!el) return;
    // Not while the reader is scrolling on their own, and only when it is
    // actually leaving the screen.
    var follow = S.get().follow && Date.now() - touched >= 4000;
    // What is read is what is marked: a translation's line, or where the page
    // does not show it, its paragraph, never both (Tigran, 2026-10-27).
    if (V && V.tr && window.ubTrRead)
      return void window.ubTrRead(V.segs[k][0], V.tr, S.get().follow).then(function (got) {
        if (marked !== el) return;                 // moved on meanwhile
        if (got) lineMark(got); else el.classList.add('now');
        if (follow) into(got || el);
      });
    el.classList.add('now');
    if (follow) into(el);
  }
  function into(el) {
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
      title: D.title, artist: T.plain(vname()[T.lang()]), album: T.text('The Urantia Book'),
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
    if (what === 'bvoice' || what === 'trvoices') { relabel(); if (said.on) speakFrom(said.n); }
    // The English's voice: a translation being heard goes on in its own.
    if (what === 'voice') { if (trOf(key)) build(); else revoice(); }
    // Listening turned off stops whatever is heard, the English or a translation.
    if (what === 'listen') revoice();
    // A translation unticked while it was heard gives way to the English.
    if (what === 'translations' && trOf(key) && ticked().indexOf(trOf(key)) < 0) revoice(choose(D));
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
