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
(function () {
  var data = document.getElementById('ub-audio');
  var S = window.ubSettings;
  if (!data || !S) return;
  var D = JSON.parse(data.textContent);
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
  function button(cls, label, name, text) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    b.setAttribute('aria-label', label);
    b.appendChild(icon(name));
    if (text) b.appendChild(document.createTextNode(text));
    return b;
  }

  var audio = new Audio();
  audio.preload = 'none';
  var synth = window.speechSynthesis || null;
  var V = null, key = null;          // the voice in use, and its key
  var k = -1, file = -1;             // the segment being heard, and its file
  var marked = null, bar = null, controls = [], shutSpeeds = function () {};
  var head, paras;
  function scan() {
    head = document.querySelector('.papertop h2');
    paras = {};
    Array.prototype.forEach.call(document.querySelectorAll('p.t[id]'),
                                 function (p) { paras[p.id] = p; });
  }
  scan();

  // The voice Settings asks for, else the first this section has.
  function choose() {
    var want = S.get().voice;
    if (want === 'off') return null;
    if (want === 'browser' && synth) return want;
    if (want && D.voices[want]) return want;
    for (var v in D.voices) return v;
    return null;
  }
  function rate() { var r = S.get().rate; return RATES.indexOf(r) < 0 ? 1 : r; }
  // What the bar and the lock screen call the voice: for the browser's, the
  // name of the one it speaks with, once the browser has said.
  function vname() {
    if (V.kind !== 'browser') return V.label;
    var v = S.voice();
    return v ? v.name : 'Your browser\u2019s voice';
  }
  function byline() {
    var v = S.voice();
    return v ? v.name + ', your browser\u2019s voice' : 'Your browser\u2019s voice';
  }

  // ---- controls in the page ------------------------------------------------
  function build() {
    controls.forEach(function (c) { c.remove(); });
    controls = [];
    key = choose();
    V = key === 'browser' ? spoken() : key ? D.voices[key] : null;
    if (!V) return;
    var row = document.createElement('p');
    row.className = 'listenrow';
    var b = button('listen', 'Listen to this section, read by ' + vname(), 'play', 'Listen');
    b.addEventListener('click', function () { go(0); });
    var by = document.createElement('span');
    by.className = 'by';
    by.textContent = V.kind === 'browser' ? byline() : V.label;
    // Boson's licence for the AI voice: its acknowledgment, beside the audio.
    if (V.credit) {
      var c = document.createElement(V.credit_url ? 'a' : 'span');
      c.className = 'credit';
      c.textContent = V.credit;
      if (V.credit_url) { c.href = V.credit_url; c.rel = 'noopener'; c.target = '_blank'; }
      by.appendChild(document.createTextNode(' · '));
      by.appendChild(c);
    } else if (V.kind === 'synthetic') by.textContent += ' (an AI voice)';
    row.appendChild(b);
    row.appendChild(by);
    head.after(row);
    controls.push(row);
    // A paragraph can be started only once the reading is aligned to them.
    if (V.by !== 'paragraph') return;
    V.segs.forEach(function (s, i) {
      var p = s[0] && paras[s[0]];
      if (!p) return;
      // Outside the stored text, and with no text of its own: copying the
      // paragraph still returns its words exactly (CLAUDE.md §6).
      var pb = button('playp', 'Listen from ' + s[0], 'play');
      pb.addEventListener('click', function () { go(i); });
      // After the reference: on a phone the two float as a stack, reference on top.
      var num = p.querySelector('.num');
      p.insertBefore(pb, num ? num.nextSibling : p.firstChild);
      controls.push(pb);
    });
  }

  // ---- the bar ---------------------------------------------------------------
  function makeBar() {
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
    at.addEventListener('click', function () {
      var el = reading();
      touched = 0;                     // and Follow along takes over again
      if (el) show(el);
    });
    var who = document.createElement('span');
    who.className = 'who';
    where.appendChild(at);
    where.appendChild(who);
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
    [prev, tog, nxt, where, spd, on, x].forEach(function (e) { bar.appendChild(e); });
    document.body.appendChild(bar);
    document.body.classList.add('listening');
  }
  // The speed, and the list of speeds that a tap on it opens above the bar.
  function speeds() {
    var box = document.createElement('span');
    box.className = 'ratebox';
    var spd = document.createElement('button');
    spd.type = 'button';
    spd.className = 'rate';
    spd.setAttribute('aria-label', 'Speed');
    spd.setAttribute('aria-haspopup', 'menu');
    spd.setAttribute('aria-expanded', 'false');
    var menu = document.createElement('div');
    menu.className = 'speeds';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', 'Speed');
    menu.hidden = true;
    var items = RATES.map(function (r) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'menuitemradio');
      b.textContent = r + '×';
      b.addEventListener('click', function () {
        shut(true);
        S.set('rate', r);
      });
      menu.appendChild(b);
      return b;
    });
    function open() {
      var now = rate();
      items.forEach(function (b, i) { b.setAttribute('aria-checked', String(RATES[i] === now)); });
      menu.hidden = false;
      spd.setAttribute('aria-expanded', 'true');
      items[Math.max(0, RATES.indexOf(now))].focus();
      document.addEventListener('pointerdown', away, true);
    }
    // Closed by a choice, a second tap on the speed, Escape, or a tap elsewhere.
    function shut(refocus) {
      if (menu.hidden) return;
      menu.hidden = true;
      spd.setAttribute('aria-expanded', 'false');
      document.removeEventListener('pointerdown', away, true);
      if (refocus) spd.focus();
    }
    function away(ev) { if (!box.contains(ev.target)) shut(false); }
    spd.addEventListener('click', function () { if (menu.hidden) open(); else shut(true); });
    shutSpeeds = shut;
    menu.addEventListener('keydown', function (ev) {
      var i = items.indexOf(document.activeElement);
      if (ev.key === 'Escape') { ev.preventDefault(); shut(true); }
      else if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        items[(i + (ev.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus();
      } else if (ev.key === 'Tab') shut(false);
    });
    box.appendChild(spd);
    box.appendChild(menu);
    return box;
  }
  // The heading or paragraph being read, if this page has it.
  function reading() {
    var s = k >= 0 ? V.segs[k] : null;
    return s ? (s[0] ? paras[s[0]] : head) : null;
  }
  // A message in the bar in place of what is being read, until the next render.
  function tell(msg) {
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
    bar.querySelector('.who').textContent = (s ? ' · ' : 'End of the section · ') + vname();
    var on = bar.querySelector('.onward');
    on.hidden = !(k < 0 && D.next);
    if (D.next) { on.href = D.next.href + '#listen'; on.textContent = 'Next: ' + D.next.label + ' ›'; }
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = paused ? 'paused' : 'playing';
  }

  // ---- playing ---------------------------------------------------------------
  function go(i) {
    if (!V || i < 0 || i >= V.segs.length) return;
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
      return speakFrom(0);
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
    var p = audio.play();
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
  var pending = null, nextWords = null, moved = false;
  function fetchNext() {
    if (!pending && D.next) {
      pending = fetch(D.next.href, { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      });
      if (key === 'browser') nextWords = fetchWords(D.next.href);
    }
    return pending;
  }
  function carryOn() {
    var to = D.next;
    if (!to) return finish();
    k = -1;                            // nothing more to hear here
    fetchNext().then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var main = doc.querySelector('main.reader'), json = doc.getElementById('ub-audio');
      if (!main || !json) throw new Error('not a section page');
      document.querySelector('main.reader').replaceWith(document.adoptNode(main));
      data.textContent = json.textContent;
      D = JSON.parse(json.textContent);
      if (key === 'browser') words(to.href, nextWords);
      nextWords = null;
      document.title = doc.title;
      history.pushState(null, '', to.href);
      moved = true;
      pending = null;
      scrollTo(0, 0);
      scan();
      // The new section's files are numbered from 0 again: forget the old one.
      file = -1;
      marked = null;
      build();
      if (V) go(0); else finish();
    }).catch(function () {
      // Offline, or the page changed shape: the link still works.
      pending = nextWords = null;
      finish();
    });
  }
  // Back after carrying on: the address has gone back, so the page must too.
  addEventListener('popstate', function () { if (moved) location.reload(); });
  function close() {
    hush();
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    file = k = -1;
    mark();
    shutSpeeds(false);
    if (bar) { bar.remove(); bar = null; }
    document.body.classList.remove('listening');
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
    if (audio.getAttribute('src')) tell('The recording could not be loaded.');
  });

  // ---- the browser's own voice -----------------------------------------------
  // It reads the spoken text (build/speech.py: numbers in words, list marks
  // spoken, brackets gone), a sentence at a time: Chrome's online voices fall
  // silent partway through a long utterance, and a sentence is where pausing
  // resumes.  Pausing is cancelling -- pause() does nothing on Android -- and
  // `gen` tells a cancelled utterance's late events from the live one's.
  var said = { href: null, text: null, wait: null, parts: [], n: 0, on: false, gen: 0, u: null };
  function here() { return '/' + D.paper + ':' + D.section; }
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
  // The text for the section in the page, from `p` if it is already coming.
  function words(href, p) {
    said.href = href;
    said.text = null;
    said.wait = (p || fetchWords(href)).then(function (m) {
      if (said.href === href) said.text = m;
      return m;
    });
    said.wait.catch(function () {});
  }
  // The heading, then every paragraph on the page.  Its text is fetched now,
  // so that a tap starts it at once: iOS speaks only in answer to one.
  function spoken() {
    var segs = [[null]];
    Array.prototype.forEach.call(document.querySelectorAll('p.t[id]'),
                                 function (p) { segs.push([p.id]); });
    if (said.href !== here()) words(here());
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
    if (said.text) return begin(gen);
    said.wait.then(function () { if (gen === said.gen) begin(gen); }, function () {
      if (gen !== said.gen) return;
      hush();
      tell('The text could not be loaded.');
    });
  }
  function begin(gen) {
    if (!said.text) return hush();
    said.parts = pieces(said.text[V.segs[k][0] || ''] || '');
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
      if (e.error !== 'not-allowed') tell('Your browser could not speak (' + e.error + ').');
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
    var by = document.querySelector('.listenrow .by');
    if (!V || V.kind !== 'browser') return;
    if (by) by.textContent = byline();
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
    if (what === 'voice') { close(); build(); }
  });

  build();
  // Arrived from "Next" at the end of the previous section: carry on.
  if (location.hash === '#listen') {
    history.replaceState(null, '', location.pathname + location.search);
    go(0);
  }
})();
