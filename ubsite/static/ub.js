// 15 KB budget, no dependencies. Everything here is an enhancement: the site is
// complete and correct with JavaScript off.
(function () {
  // Settings: one JSON object in localStorage, per browser; a reader signed in
  // has them kept with the account too, all but the device's own, and the
  // same on every device (static/account.js, which runs only then).  What
  // the settings are, and their defaults, is ubsite/settings.py, handed over
  // by the head script in base.html, which also applies them before first
  // paint.  This keeps them, runs the dialog, and tells listen.js of a change.
  // DEF is this site's defaults, what is stored is what differs from them, and
  // ↺ restores them; the data- attributes say where a value differs from
  // settings.py's own, BASE, which the CSS is written against (SITE_DEFAULTS).
  var KEY = 'ub_settings', DEF = window.ubDefaults || {}, BASE = window.ubBase || DEF,
      SPARED = window.ubSpared || [];
  // The interface's words (ubsite/l10n.js, loaded before this).
  var T = window.ubT;
  function stored() {
    var s = {};
    try {
      s = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
      // The theme was once kept on its own.
      if (!('theme' in s) && localStorage.getItem('ub_theme')) s.theme = localStorage.getItem('ub_theme');
      // A size is kept as itself since 2026-11-16 (settings.py), and the
      // names kept before read as what they meant: Smaller 100%, which is
      // Standard now, Standard 112.5%, and Larger, with the Largest of
      // before 2026-10-14, 125%.  The head script leaves them as they are,
      // and ub.css reads them the same.
      var was = { smaller: '100', standard: '112.5', larger: '125', largest: '125' };
      ['size', 'uisize'].forEach(function (k) { if (was.hasOwnProperty(s[k])) s[k] = was[s[k]]; });
      // Off was once a voice, the English's; it is Listening controls now
      // (settings.py `listen`, 2026-10-27).
      if (s.voice === 'off') { delete s.voice; s.listen = false; }
    } catch (e) {}
    return s;
  }
  function load() {
    var s = stored(), o = {};
    for (var k in DEF) o[k] = k in s ? s[k] : DEF[k];
    return o;
  }
  function save(s) {
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
      localStorage.removeItem('ub_theme');
    } catch (e) {}
  }
  // As the head script does: data-<key> for each value that is not settings.py's
  // default, and the language resolved (ubLang).
  function apply(o) {
    var r = document.documentElement;
    for (var k in DEF) {
      if (o[k] === BASE[k]) delete r.dataset[k];
      else r.dataset[k] = o[k] === false ? 'off' : String(o[k]);
    }
    if (window.ubLang) window.ubLang(r, o.lang);
    if (window.ubTr) window.ubTr(o.translations, o.english);
  }
  // The translations shown beside the text, told to the worker (sw.js, {cmd:
  // 'shown'}), which has no other way to Settings: what depends on them, a
  // section's translations and a search, it answers from its copy first only
  // where the copy keeps them all, and otherwise leaves to the server, which
  // sends every one (sw.js covered()).  With each change, before anyone hears
  // of it and asks for a section's again; and as a page loads (below, with
  // Work offline).
  function shownTo(o) {
    var sw = navigator.serviceWorker, w = sw && sw.controller, tr = String(o.translations || '').split(' ').filter(Boolean);
    // The Bible's Synodal too, where its pages show it (settings.py `bible`):
    // its lines and its list in search are the copy's only where it keeps it.
    if (String(o.bible || '').split(' ').indexOf('rsb') >= 0) tr.push('rsb');
    if (w) w.postMessage({ cmd: 'shown', tr: tr });
  }
  function announce(k, o) {
    shownTo(o);
    document.dispatchEvent(new CustomEvent('ub:settings', { detail: { key: k, all: o } }));
  }
  // The browser's own voices (Web Speech) in a language, English unless
  // another is asked for (a translation's, read aloud: listen.js), best
  // first: an online voice (Google's in Chrome, Microsoft's "Natural" ones in
  // Edge) or Apple's Premium and Enhanced ones sound better than the rest, and
  // the book is American, a Russian translation Russia's.  Not macOS's
  // novelty voices.  The list can be empty until the browser's voiceschanged.
  var synth = window.speechSynthesis;
  var NOVELTY = /^(Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox)\b/;
  var HOME = { en: 'US' };
  function score(v, lang) {
    return (/natural|neural|premium|enhanced|online/i.test(v.name) ? 4 : 0) + (/^Google/.test(v.name) ? 2 : 0) +
           (new RegExp('^' + lang + '[-_]' + (HOME[lang] || lang.toUpperCase()), 'i').test(v.lang) ? 1 : 0) +
           (v.default ? 0.5 : 0);
  }
  function voices(lang) {
    lang = lang || 'en';
    if (!synth) return [];
    var re = new RegExp('^' + lang + '([-_]|$)', 'i');
    return synth.getVoices().filter(function (v) {
      return re.test(v.lang) && !NOVELTY.test(v.name);
    }).sort(function (a, b) { return score(b, lang) - score(a, lang) || (a.name < b.name ? -1 : 1); });
  }

  // The voices that can speak now.  Offline, this device's own: Chrome's Google
  // voices and Edge's Natural ones are spoken by a server, and fall silent
  // without it.
  function usable(lang) {
    var all = voices(lang);
    if (navigator.onLine === false) {
      var here = all.filter(function (v) { return v.localService; });
      if (here.length) all = here;
    }
    return all;
  }
  // Each translation's voice, {key: name}, those not its default (settings.py
  // trvoices, JSON in a string): a browser voice's name, or "browser", the
  // browser's own choice, where the default is a recording of it.
  function trVoices() {
    try { return JSON.parse(load().trvoices || '{}') || {}; } catch (e) { return {}; }
  }

  window.ubSettings = {
    voices: voices,
    // What the player's list of voices offers (listen.js).
    usable: usable,
    // The browser voice Settings names, else the best there is; null with
    // none.  The English's, or with `tr` that translation's, in its language.
    voice: function (lang, tr) {
      var all = usable(lang), want = tr ? trVoices()[tr] : load().bvoice;
      return all.filter(function (v) { return v.name === want; })[0] || all[0] || null;
    },
    // What the reader chose for translation tr: '' its default, which is a
    // recording of it where there is one (listen.js trKey), a browser voice's
    // name, or "browser".
    trChoice: function (tr) { return trVoices()[tr] || ''; },
    // Translation tr's voice, by its name; '' for its default.
    setTrVoice: function (tr, name) {
      var m = trVoices();
      if (name) m[tr] = name; else delete m[tr];
      window.ubSettings.set('trvoices', Object.keys(m).length ? JSON.stringify(m) : '');
    },
    get: load,
    set: function (k, v) {
      // Only what differs from its default is kept, so a default changed in
      // settings.py reaches everyone who never chose otherwise.
      var s = stored();
      if (v === DEF[k]) delete s[k]; else s[k] = v;
      save(s);
      var o = load();
      apply(o);
      announce(k, o);
    },
    // Several at once, {key: value}, each announced once all are kept: the
    // texts' order is two settings, the translations and the English's place
    // (settings.py TRANSLATIONS), and whoever hears of one must find the
    // other as it is to be.
    setAll: function (m) {
      var s = stored(), k, o;
      for (k in m) if (k in DEF) { if (m[k] === DEF[k]) delete s[k]; else s[k] = m[k]; }
      save(s);
      o = load();
      apply(o);
      for (k in m) if (k in DEF) announce(k, o);
    },
    // Every setting but the spared (settings.py SPARED): the language.
    reset: function () {
      var s = stored(), keep = {};
      SPARED.forEach(function (k) { if (k in s) keep[k] = s[k]; });
      save(keep);
      var o = load();
      apply(o);
      for (var k in DEF) announce(k, o);
    },
    // For a reader signed in (static/account.js): what is stored, as it is,
    // which is what an exchange with the account compares, load() filling in
    // the defaults; and what an exchange brought, {key: its value, or null
    // for its default}, kept and put on the page as a change made on another
    // page is (shown, below).  Whoever shows the settings hears 'ub:brought'.
    kept: stored,
    take: function (ch) {
      var s = stored(), k;
      for (k in ch) {
        if (!(k in DEF)) continue;
        if (ch[k] === null || ch[k] === DEF[k]) delete s[k];
        else if (typeof ch[k] === typeof DEF[k]) s[k] = ch[k];
      }
      save(s);
      shown();
      document.dispatchEvent(new Event('ub:brought'));
    }
  };
  // Shown again from the browser's page cache, by Back or Forward, the page
  // runs no script: what Settings changed on another page since is put on
  // this one, and announced as if changed here, where it came back in the
  // size, the theme or the columns it was left in (review of 2026-11-09);
  // with Whole paper changed, in its other unit, as the head script would.
  // And what an exchange with the reader's account brought from another
  // device (take, above) is put on the page by the same steps, the whole
  // paper's page then left at the section being read.
  var shownWith = load();
  document.addEventListener('ub:settings', function (ev) { shownWith = ev.detail.all; });
  function shown() {
    var o = load(), was = shownWith, k, s, here, to;
    apply(o);
    shownWith = o;
    for (k in DEF) if (was[k] !== o[k]) announce(k, o);
    if (was.whole !== o.whole && window.ubUnit) {
      s = sectionInView();
      here = location.pathname + (s ? '#' + s.id : location.hash);
      to = window.ubUnit(here);
      if (to !== location.pathname + location.hash)
        location.replace(to.replace(/#.*$/, '') + location.search + to.replace(/^[^#]*/, ''));
    }
  }
  addEventListener('pageshow', function (ev) { if (ev.persisted) shown(); });

  // The half-disc beside the gear flips light and dark, a shortcut to
  // Settings' Theme (Tigran, 2026-11-18; it was in the header until
  // 2026-11-10).  From System it goes to the other of what the device shows,
  // and Settings alone gives System back.
  var themeBtn = document.querySelector('.top .theme');
  if (themeBtn) {
    themeBtn.hidden = false;
    themeBtn.addEventListener('click', function () {
      var t = load().theme;
      var dark = t === 'dark' || (t !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
      window.ubSettings.set('theme', dark ? 'light' : 'dark');
    });
  }

  // Full screen, after the half-disc (base.html .fscreen; Tigran,
  // 2026-11-21: "especially useful on the phone in our webapk"): the page
  // fills the screen, the browser's bars gone, and on a phone the system's.
  // Shown only where the browser can put a page in full screen, which an
  // iPhone cannot.  The browser leaves full screen as any new page loads,
  // and only a tap or a key may enter it, so the choice is kept on the
  // device (ub_full, a key of its own and no setting, which no account
  // carries: the phone's full screen is not the desktop's), and on each new
  // page the first tap on a touch screen brings it back (asked, Tigran chose
  // that over a switch each page loses): not one on a link, which is leaving
  // the page anyway, nor a mouse's, the desktop having F11, which lasts from
  // page to page, and Chrome there saying "Press Esc to exit full screen" at
  // every entry.  A tap on the text that brings it back does only that,
  // without the running head.  The button, Back or Esc ends it for good:
  // any end the page did not ask for is taken as the reader's, unless the
  // page is being left or hidden within a moment of it (a new page loading,
  // which ends it as the browser commits to the new one; another app).  A
  // whole paper is one page, and a recording playing swaps pages without
  // loading them (listen.js), so those keep it.
  var fsBtn = document.querySelector('.top .fscreen'), fsRoot = document.documentElement, FS = 'ub_full',
      fsLeaving = false, fsTimer = 0, fsSwallow = false;
  var fsNow = function () { return !!(document.fullscreenElement || document.webkitFullscreenElement); };
  var fsWant = function (v) {
    try {
      if (v === undefined) return localStorage.getItem(FS) === '1';
      if (v) localStorage.setItem(FS, '1'); else localStorage.removeItem(FS);
    } catch (e) {}
    return false;
  };
  var fsGo = function () {
    var r;
    try {
      r = fsRoot.requestFullscreen ? fsRoot.requestFullscreen({ navigationUI: 'hide' }) : fsRoot.webkitRequestFullscreen();
    } catch (e) {}
    if (r && r.catch) r.catch(function () {});
  };
  var fsBack = function () {
    var r;
    try { r = document.exitFullscreen ? document.exitFullscreen() : document.webkitExitFullscreen(); } catch (e) {}
    if (r && r.catch) r.catch(function () {});
  };
  if (fsBtn && (document.fullscreenEnabled || document.webkitFullscreenEnabled)) {
    fsBtn.hidden = false;
    fsBtn.addEventListener('click', function () {
      if (fsNow()) { fsWant(false); fsBack(); } else { fsWant(true); fsGo(); }
    });
    var fsChange = function () {
      var on = fsNow();
      fsBtn.setAttribute('aria-pressed', String(on));
      clearTimeout(fsTimer);
      if (!on && fsWant()) fsTimer = setTimeout(function () {
        if (!fsLeaving && !document.hidden && !fsNow()) fsWant(false);
      }, 1500);
    };
    document.addEventListener('onfullscreenchange' in document ? 'fullscreenchange' : 'webkitfullscreenchange', fsChange);
    addEventListener('pagehide', function () { fsLeaving = true; clearTimeout(fsTimer); });
    addEventListener('pageshow', function (ev) { if (ev.persisted) { fsLeaving = false; fsChange(); } });
    document.addEventListener('visibilitychange', function () { if (document.hidden) clearTimeout(fsTimer); });
    document.addEventListener('pointerup', function (ev) {
      var t = ev.target;
      if (ev.pointerType === 'mouse' || fsNow() || !fsWant() || !t.closest || t.closest('a[href], .fscreen')) return;
      fsGo();
      fsSwallow = !t.closest('button, summary, label, input, select, textarea, details, dialog, [role], [tabindex]');
      setTimeout(function () { fsSwallow = false; }, 600);
    }, true);
    document.addEventListener('click', function (ev) {
      if (!fsSwallow) return;
      fsSwallow = false;
      ev.stopPropagation();
      ev.preventDefault();
    }, true);
  }

  var gear = document.querySelector('.gear'), dlg = document.querySelector('dialog.settings');
  if (gear && dlg && dlg.showModal) {
    gear.hidden = false;
    var form = dlg.querySelector('form');
    // The voices (settings.py `voice`, base.html .setvoices): a menu against
    // each text, the English first, then each translation while it is ticked
    // (Tigran, 2026-10-27 and 2026-11-13).  The page draws a menu with the
    // recordings of its text (option[data-rec]); here the browser's voices in
    // its language go in after them by name, the best first, each once.
    // Until the browser has listed any voice, one entry stands for them all,
    // "Your browser's voice" (option.any); a browser that cannot speak has
    // the recordings alone, and no menu for a text that has none.
    var vrows = form.querySelector('.setvoices');
    var listVoices = function () {
      if (!vrows) return;
      var o = load(), ticked = String(o.translations || '').split(' '), m = trVoices();
      var listed = synth ? synth.getVoices().length : 0, some = false;
      Array.prototype.forEach.call(vrows.querySelectorAll('label[data-k]'), function (l) {
        var k = l.dataset.k, sel = l.querySelector('select'), any = sel.querySelector('option.any');
        var recs = sel.querySelectorAll('option[data-rec]'), all = voices(l.dataset.lang);
        Array.prototype.slice.call(sel.querySelectorAll('option[data-v]')).forEach(function (x) { sel.removeChild(x); });
        all.forEach(function (v) {
          var x = new Option(v.name, v.name);
          x.setAttribute('data-v', '');
          sel.add(x);
        });
        any.hidden = any.disabled = !synth || listed > 0;
        // The text's row: a translation's while it is ticked, the English's
        // while it is shown (2026-11-20: the voices follow the Texts), and
        // either while there is anything to choose.
        l.hidden = (!!k && ticked.indexOf(k) < 0) || (!k && texts().indexOf('up') < 0) ||
                   (!recs.length && (!synth || (listed && !all.length)));
        some = some || !l.hidden;
        // What reads it now: a recording, the first unless the English's is
        // another; or the browser's voice named, else its best, the first
        // (a name this device has not is the best too, never the recording).
        var w = k ? m[k] || '' : o.voice === 'browser' ? o.bvoice || 'browser' : '';
        var rec = k ? recs[0] : sel.querySelector('option[data-rec][value="' + o.voice + '"]') || recs[0];
        if (synth && (w || !rec) && (all.length || !any.disabled))
          sel.value = all.some(function (v) { return v.name === w; }) ? w : all.length ? all[0].name : any.value;
        else if (rec) rec.selected = true;
      });
      // The English first, where it is shown, then the translations shown,
      // by language and within it by short name, as the player's list has
      // them (Tigran, 2026-11-20: "In the list of voices English should be
      // the first"; "the translations should be in some canonical
      // (alphabetical by label?) order, not necessarily matching the 'show'
      // order"; "but grouped by language!"), whatever their order among the
      // texts.
      ticked.filter(function (k) { return trBy[k]; }).sort(voiceOrder).forEach(function (k) {
        var l = vrows.querySelector('label[data-k="' + k + '"]');
        if (l) vrows.appendChild(l);
      });
      vrows.hidden = !some;
    };
    // A pick is kept as what it is: a recording, the text's first being its
    // default and so nothing stored, or a voice by its name.  The English
    // text's is two settings, the voice and which of the browser's; only
    // what changes is set, the player going on in the voice chosen at each.
    if (vrows) vrows.addEventListener('change', function (ev) {
      var l = ev.target.closest('label[data-k]');
      if (!l) return;
      var opt = ev.target.options[ev.target.selectedIndex], named = opt.hasAttribute('data-v'), o = load();
      if (l.dataset.k) window.ubSettings.setTrVoice(l.dataset.k, opt.value);
      else {
        // The first recording is what '' means, where '' is the default.
        var first = ev.target.querySelector('option[data-rec]');
        var v = named ? 'browser' : opt === first && DEF.voice === '' ? '' : opt.value;
        if (named && o.bvoice !== opt.value) window.ubSettings.set('bvoice', opt.value);
        if (o.voice !== v) window.ubSettings.set('voice', v);
      }
      resettable();
    });
    // Each control shows its setting's value; a radio group whose value has no
    // button shows its first, and a menu whose value is gone its first.  The
    // voices' menus are filled and set above, having no setting's name.
    // The interface's language, a row only where the site draws both
    // (l10n.py BILINGUAL), as the flags are shown (below).
    var langRow = form.querySelector('.langrow');
    if (langRow && T.bilingual) langRow.hidden = false;
    var fill = function () {
      listVoices();
      var o = load();
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!(el.name in DEF)) return;
        if (el.type === 'checkbox') el.checked = o[el.name] !== false;
        else if (el.type === 'radio') {
          // The language before one is chosen, "auto", is the one in effect.
          var v = el.name === 'lang' && o.lang === 'auto' ? T.lang() : o[el.name];
          var group = form.querySelectorAll('[name="' + el.name + '"]');
          var hit = form.querySelector('[name="' + el.name + '"][value="' + String(v) + '"]');
          el.checked = hit ? el === hit : el === group[0];
        } else {
          el.value = String(o[el.name]);
          if (el.selectedIndex < 0) el.selectedIndex = 0;
        }
      });
      idle(o);
      trFill();
      bFill();
    };
    // The Texts tab (settings.py TRANSLATIONS): those shown, in the reader's
    // order, numbered, each with ↑ and ↓, then the others, by language, in
    // the order the page drew them.  A tick puts one at the end of the order,
    // or back among the others (Tigran, 2026-10-26).  The English a row like
    // the rest since 2026-11-20, "up", which texts() puts in its place; the
    // last one shown is never hidden, its × greyed.
    var trShown = form.querySelector('.trshown');
    var trOrder = function () {
      return texts().filter(function (k) {
        return form.querySelector('.trlist li[data-k="' + k + '"]');
      });
    };
    var trFill = function () {
      if (!trShown) return;
      var order = trOrder();
      Array.prototype.slice.call(form.querySelectorAll('.trlist li[data-k]'))
        .sort(function (x, y) { return x.dataset.i - y.dataset.i; })
        .forEach(function (li) {
          var at = order.indexOf(li.dataset.k);
          li.querySelector('input').checked = at >= 0;
          li.querySelector('.up').disabled = at <= 0;
          li.querySelector('.down').disabled = at < 0 || at === order.length - 1;
          li.querySelector('.drop').disabled = at < 0 || order.length < 2;
          if (at < 0) form.querySelector('.trother[data-lang="' + li.dataset.lang + '"]').appendChild(li);
        });
      order.forEach(function (k) { trShown.appendChild(form.querySelector('.trlist li[data-k="' + k + '"]')); });
      // A language's label goes with its list, and Other translations with the last of them.
      Array.prototype.forEach.call(form.querySelectorAll('.trother'), function (ul) {
        ul.hidden = ul.previousElementSibling.hidden = !ul.children.length;
      });
      form.querySelector('.trothers').hidden = !form.querySelector('.trother li');
    };
    // The place kept (keepPlace): with the translations open under every
    // paragraph, one ticked or unticked changes the page's height by screens.
    // Two settings, the translations in order and the English's place among
    // them, set together (setAll).
    var trSet = function (order) {
      keepPlace(function () { window.ubSettings.setAll(textsOf(order)); });
      fill();                          // and Listening's menus of their voices
      resettable();
    };
    if (trShown) {
      // Each row's first place, to go back to when it is unticked.
      Array.prototype.forEach.call(form.querySelectorAll('.trlist li[data-k]'), function (li, i) {
        li.dataset.lang = li.closest('.trlist').dataset.lang;
        li.dataset.i = i;
      });
      form.addEventListener('change', function (ev) {
        var el = ev.target;
        if (el.type !== 'checkbox' || !el.closest('.trlist')) return;
        var order = trOrder().filter(function (k) { return k !== el.value; });
        if (el.checked) order.push(el.value);
        // The last one shown stays.
        if (!order.length) { el.checked = true; return; }
        trSet(order);
      });
      form.addEventListener('click', function (ev) {
        var b = ev.target.closest('.trlist .up, .trlist .down, .trlist .drop');
        if (!b || b.disabled) return;
        // × hides it: the card itself is not a switch once shown (Tigran, 2026-10-26).
        if (b.classList.contains('drop')) {
          var gone = b.closest('li').dataset.k;
          trSet(trOrder().filter(function (k) { return k !== gone; }));
          return (form.querySelector('.trshown .drop') || form.querySelector('.trother li[data-k="' + gone + '"] input')).focus();
        }
        var k = b.closest('li').dataset.k, order = trOrder(), i = order.indexOf(k), j = i + (b.classList.contains('up') ? -1 : 1);
        if (i < 0 || j < 0 || j >= order.length) return;
        order[i] = order[j];
        order[j] = k;
        trSet(order);
        b.disabled ? b.closest('li').querySelector('input').focus() : b.focus();
      });
    }
    // The Bible's list (settings.py `bible`; base.html .blist): its versions
    // shown, in the reader's order, numbered, each with ↑, ↓ and ×, then the
    // others; a tick puts one at the end of the order, and the last one shown
    // stays, as the book's texts do (trFill).  Its own, for the book's finds
    // its rows by .trlist and data-k.
    // The Texts tab's subtabs, the book's texts and the Bible's (base.html
    // .txtabs; Tigran, 2026-11-21): one list shown at a time, the Bible's on
    // a page of the Bible, the book's elsewhere, until a tap chooses.
    var txTabs = form.querySelector('.txtabs');
    var txShow = function (k) {
      Array.prototype.forEach.call(txTabs.querySelectorAll('button[data-sub]'), function (b) {
        b.setAttribute('aria-selected', b.dataset.sub === k ? 'true' : 'false');
      });
      Array.prototype.forEach.call(form.querySelectorAll('.txsub'), function (d) { d.hidden = d.dataset.sub !== k; });
    };
    if (txTabs) {
      txTabs.addEventListener('click', function (ev) {
        var b = ev.target.closest('button[data-sub]');
        if (b) txShow(b.dataset.sub);
      });
      txShow(/^\/bible(\/|$)/.test(location.pathname) ? 'bible' : 'book');
    }
    var bShown = form.querySelector('.bshown');
    var bOrder = function () {
      var ks = String(load().bible || 'kjv').split(' ').filter(function (k) {
        return k && form.querySelector('.blist li[data-b="' + k + '"]');
      });
      return ks.length ? ks : ['kjv'];
    };
    var bFill = function () {
      if (!bShown) return;
      var order = bOrder(), other = form.querySelector('.bother');
      Array.prototype.slice.call(form.querySelectorAll('.blist li[data-b]'))
        .sort(function (x, y) { return x.dataset.i - y.dataset.i; })
        .forEach(function (li) {
          var at = order.indexOf(li.dataset.b);
          li.querySelector('input').checked = at >= 0;
          li.querySelector('.up').disabled = at <= 0;
          li.querySelector('.down').disabled = at < 0 || at === order.length - 1;
          li.querySelector('.drop').disabled = at < 0 || order.length < 2;
          if (at < 0) other.appendChild(li);
        });
      order.forEach(function (k) { bShown.appendChild(form.querySelector('.blist li[data-b="' + k + '"]')); });
      other.hidden = !other.children.length;
    };
    var bSet = function (order) {
      window.ubSettings.set('bible', order.join(' '));
      bFill();
      resettable();
    };
    if (bShown) {
      Array.prototype.forEach.call(form.querySelectorAll('.blist li[data-b]'), function (li, i) { li.dataset.i = i; });
      form.addEventListener('change', function (ev) {
        var el = ev.target;
        if (el.type !== 'checkbox' || !el.closest('.blist')) return;
        var order = bOrder().filter(function (k) { return k !== el.value; });
        if (el.checked) order.push(el.value);
        if (!order.length) { el.checked = true; return; }
        bSet(order);
      });
      form.addEventListener('click', function (ev) {
        var b = ev.target.closest('.blist .up, .blist .down, .blist .drop');
        if (!b || b.disabled) return;
        if (b.classList.contains('drop')) {
          var gone = b.closest('li').dataset.b;
          bSet(bOrder().filter(function (k) { return k !== gone; }));
          return (form.querySelector('.bshown .drop') || form.querySelector('.bother li[data-b="' + gone + '"] input')).focus();
        }
        var k = b.closest('li').dataset.b, order = bOrder(), i = order.indexOf(k), j = i + (b.classList.contains('up') ? -1 : 1);
        if (i < 0 || j < 0 || j >= order.length) return;
        order[i] = order[j];
        order[j] = k;
        bSet(order);
        b.disabled ? b.closest('li').querySelector('input').focus() : b.focus();
      });
    }
    // ↺ is greyed while every setting is its default: only what differs is
    // kept.  The language it spares does not count.
    var reset = form.querySelector('.reset');
    var resettable = function () {
      reset.disabled = !Object.keys(stored()).some(function (k) { return SPARED.indexOf(k) < 0; });
    };
    // A setting that means nothing while the one it needs is off (settings.py
    // NEEDS) is shown, greyed, and cannot be changed: 'off', or a switch's false,
    // or a list's '', none ticked; or, where it needs a value (data-is), any other.
    // And a setting whose own needs are not met greys those that need it.
    var unmet = function (o, el) {
      var v = o[el.dataset.needs];
      if (el.dataset.is ? String(v) !== el.dataset.is : v === 'off' || v === false || v === '') return true;
      var dep = form.querySelector('[data-needs] [name="' + el.dataset.needs + '"]');
      return !!dep && unmet(o, dep.closest('[data-needs]'));
    };
    var idle = function (o) {
      Array.prototype.forEach.call(form.querySelectorAll('[data-needs]'), function (el) {
        var off = unmet(o, el);
        el.classList.toggle('idle', off);
        Array.prototype.forEach.call(el.querySelectorAll('input, select'), function (c) { c.disabled = off; });
      });
    };
    if (synth && synth.addEventListener) synth.addEventListener('voiceschanged', function () {
      if (dlg.open) fill();
    });
    // The page stays still behind it (ub.css), keeping its scrollbar's room
    // only where it has a scrollbar to lose: an overlay one takes none, and a
    // page shorter than the window has none.
    gear.addEventListener('click', function () {
      fill();
      resettable();
      document.documentElement.style.setProperty('--sbw', (window.innerWidth - document.documentElement.clientWidth) + 'px');
      dlg.showModal();
    });
    // Ctrl+, opens Settings from any page, as it opens an application's
    // preferences, and closes it again (Tigran, 2026-10-20).  On a Mac, ⌘, is
    // the browser's own and never reaches the page.  Or where the comma is, on
    // a keyboard that writes no Latin there: on a Russian one it is б, as
    // Ctrl+X below takes the key where X is.
    document.addEventListener('keydown', function (ev) {
      if (!(ev.key === ',' || (ev.code === 'Comma' && !/^[\x20-\x7e]$/.test(ev.key))) ||
          !ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey) return;
      ev.preventDefault();
      if (dlg.open) dlg.close(); else gear.click();
    });
    // A value takes its default's type: a switch is true or false, the speed a number.
    form.addEventListener('change', function (ev) {
      var el = ev.target, d = DEF[el.name];
      if (!(el.name in DEF)) return;
      window.ubSettings.set(el.name, typeof d === 'boolean' ? el.checked
                                     : typeof d === 'number' ? parseFloat(el.value) : el.value);
      idle(load());
      resettable();
    });
    // It stands beside ×, so it asks first (Tigran, 2026-10-14).
    // Signed in, the settings that follow the account go back to their
    // defaults on every device, and the question says so.
    reset.addEventListener('click', function () {
      var kept = form.querySelector('.kept');
      if (!window.confirm(kept && kept.dataset.acct === 'in'
                          ? T.text('reset:account?') : T.text('Restore every setting to its default?'))) return;
      keepPlace(function () { window.ubSettings.reset(); });
      fill();
      resettable();
    });
    // What an exchange with the reader's account brought (ubSettings.take),
    // while the dialog is open: its controls as the settings now are.
    document.addEventListener('ub:brought', function () {
      if (!dlg.open) return;
      fill();
      idle(load());
      resettable();
    });
    // A click on the backdrop closes it, as Escape does.
    dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });
    // Opened by Ctrl+, there was no focus to give back, and Chrome left it in
    // the closed dialog, where Space and End did nothing to the page.
    dlg.addEventListener('close', function () {
      if (dlg.contains(document.activeElement)) document.activeElement.blur();
    });
    // Settings' Whole paper changed (settings.py `whole`, base.html ubUnit):
    // the page is shown again in the other unit once the dialog is closed,
    // so that other settings can be changed first -- a section's page as the
    // whole paper's, at its section, and the whole paper's as the page of the
    // section being read.
    var unitChanged = false;
    document.addEventListener('ub:settings', function (ev) { if (ev.detail.key === 'whole') unitChanged = true; });
    dlg.addEventListener('close', function () {
      if (!unitChanged || !window.ubUnit) return;
      unitChanged = false;
      var s = sectionInView(), here = location.pathname + (s ? '#' + s.id : location.hash),
          to = window.ubUnit(here);
      if (to !== location.pathname + location.hash) location.replace(to);
    });
    // A tab to each group (Tigran, 2026-10-25), opened by a click, or by ←, →,
    // Home and End among those shown.  From anywhere in the dialog, not only
    // from the tabs, as a tablist would have it: the dialog opens with × in
    // focus, and keys that did nothing there seemed broken (Tigran, the same
    // day).  Not on a menu, whose own keys they all are, nor the arrows on a
    // radio button: Theme's still go from Light to Dark.  The focus goes to the tab, so that
    // it is never left on a panel now hidden.  The dialog opens again at the
    // tab it was closed at, until the page is left.
    var tabs = form.querySelector('.tabs');
    var show = function (t) {
      Array.prototype.forEach.call(tabs.children, function (b) {
        var on = b === t;
        b.setAttribute('aria-selected', on ? 'true' : 'false');
        b.tabIndex = on ? 0 : -1;
        document.getElementById(b.getAttribute('aria-controls')).classList.toggle('on', on);
      });
      // The Offline tab's translations are the offline menu's to say (offline.js).
      if (t.id === 'set-t-offline') document.dispatchEvent(new Event('ub:offtab'));
    };
    tabs.addEventListener('click', function (ev) {
      var t = ev.target.closest('[role="tab"]');
      if (t) show(t);
    });
    // Settings opened from elsewhere, at a tab: the home page's bar opens it
    // at Offline (offline.js barState), and so does the install banner where
    // the browser has no offer of its own to make.
    window.ubSettings.open = function (tab) {
      var t = tab && document.getElementById('set-t-' + tab);
      if (!dlg.open) gear.click();
      if (t) show(t);
    };
    dlg.addEventListener('keydown', function (ev) {
      if (!dlg.open || ev.ctrlKey || ev.altKey || ev.metaKey || ev.shiftKey || ev.defaultPrevented ||
          ev.target.closest('select') || (/^Arrow/.test(ev.key) && ev.target.type === 'radio')) return;
      var all = Array.prototype.filter.call(tabs.children, function (b) { return !b.hidden; });
      var i = all.indexOf(tabs.querySelector('[aria-selected="true"]')), n = all.length;
      var to = { ArrowRight: i + 1, ArrowLeft: i - 1 + n, Home: 0, End: n - 1 }[ev.key];
      if (i < 0 || to === undefined) return;
      ev.preventDefault();
      show(all[to % n]);
      all[to % n].focus();
    });
  }

  // Whole paper (base.html ubUnit): a link to the book is put in the reader's
  // unit as it is clicked -- the rail's /15 to /15:0 with the setting off,
  // the rail's and a paragraph's /15:3 to /15#15:3 with it on, which on the
  // paper's own page is a place on it, and scrolls -- before listen.js or the
  // browser follows it, so that no page is asked for twice.  In the capture
  // phase, so first.  The link stays as it was put, and the address the page
  // gave it is kept (`hrefWas`) for what tells a link by that address: the
  // Contents drawn as a translation gives them (tocDraw, below) knew a
  // section's link as /0:6 alone, and left one that had been followed, by
  // then /0#0:6, in English among the translation's titles (Tigran,
  // 2026-11-18, on his phone, which reads the whole paper).
  var hrefWas = new WeakMap();
  if (window.ubUnit) document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || a.origin !== location.origin) return;
    var at = a.pathname + a.hash, to = window.ubUnit(at);
    if (to !== at) {
      if (!hrefWas.has(a)) hrefWas.set(a, a.getAttribute('href'));
      a.href = to;
    }
    // A place on this page, the whole paper's (/1#1:2.9, a note's reference):
    // where the page stands is kept in the entry's state, for Back (the
    // hashchange below).
    if (to.split('#')[0] === location.pathname && to.indexOf('#') > 0)
      try { history.replaceState(Object.assign({}, history.state, { ubY: scrollY }), ''); } catch (e) {}
  }, true);

  // Bring the page's focus into view.  /61:7.18 renders the whole of 61:7 with
  // paragraph 18 marked .hit, and nothing in the address says where to scroll
  // -- a #fragment would, but then the permalink would stop being the
  // citation.  A margin chip opens /i/god#e…, which the browser scrolls to
  // itself.  Either way, scroll once more when the fonts are in: UB Goudy
  // loads with font-display: swap, the text reflows, and the first scroll
  // drifts.  Not if the reader has scrolled meanwhile.  Again whenever
  // listen.js brings a page in while it plays ('ub:page'), and whenever the
  // hash changes, a section's link on the whole paper's page.  A fragment that
  // names no element -- #note…, a 1955 reading found by search -- leaves the
  // paragraph marked .hit as the focus.  On the whole paper's page
  // (paper.html) the place after # is a section's or a paragraph's address,
  // as ubUnit makes it, a range marked as the section's page marks it
  // (/15:3.4-6 as /15#15:3.4-6), or a card's, which names its paragraph
  // (#note15_3_4_0); what follows a second # is arriveTr's.  `again` is the
  // page placed once more, the columns drawn, and no new arrival: the marks
  // are not made again, nor counted again (hitLater, below).
  function arrive(again) {
    var focus = null, m, el, i, whole = document.querySelector('article.whole');
    // On the chart of the personalities an address names a card, which
    // cosmo.js brings into its own window: never the page to it.
    if (document.querySelector('main.cosmo')) return;
    // At the Contents' entry again, by Back or Forward (toContents, below),
    // the place is theirs; left by a section's link, it is forgotten.
    if (contentsAt && history.state && history.state.ub === 'contents') return;
    contentsAt = null;
    try {
      m = whole && (/^#(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?(?:#.*)?$/.exec(location.hash) ||
                    /^#(?:note|fnref|fn)(?:st|tn_[a-z0-9-]+_)?(\d+)_(\d+)_(\d+)_\d+$/.exec(location.hash));
      if (m && !again) {
        unhit();
        for (i = +m[3]; m[3] && i <= +(m[4] || m[3]); i++) {
          el = document.getElementById(m[1] + ':' + m[2] + '.' + i);
          if (el) el.classList.add('hit');
        }
      }
      if (m) focus = document.getElementById(m[1] + ':' + m[2] + (m[3] ? '.' + m[3] : ''));
      focus = focus || (location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)))) ||
              document.querySelector('.hit');
    } catch (e) {}
    if (!again) hitLater();
    // A translation's hit in its column, once Compare has drawn it.
    focus = cmpHit() || focus;
    if (!focus) return;
    // Placed now, again a frame on, and once the fonts are in, unless the
    // reader has scrolled meanwhile: by hand, since the browser itself moves
    // the page as what is above the focus changes height (scroll anchoring),
    // so the scroll position says nothing.  In columns, under their names,
    // which stay at the window's top and are two to six lines of the small
    // type tall, by the width and how many columns (2026-11-08: they covered
    // the paragraph's first line); on a phone they are not shown.
    var t = Date.now(), put = function () {
      if (arriveTouched > t) return;
      var art = focus.closest && focus.closest('article.cmp'), names = art && art.querySelector('.cmpnames'),
          floor = names && names.offsetHeight;
      focus.scrollIntoView({ block: 'start' });
      if (floor) scrollBy({ top: focus.getBoundingClientRect().top - floor - 12, behavior: 'instant' });
    };
    put();
    requestAnimationFrame(put);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(put);
  }
  var arriveTouched = 0;
  // The paragraph marked as the place the page opened at: the English, or in
  // columns a translation's, where a search's hit in it opened the page (cmpHit).
  var HIT = 'p.t.hit, .rc p.rt.hit, p.kv.hit';
  // And let go of by itself, five seconds after it was arrived at (seven
  // until 2026-11-23, Tigran: "Seven is too much"), fading
  // (ub.css .hitgo) for most of one more (Tigran, 2026-11-19: "to unhighlight
  // it you have to tap it twice ... which is not very convenient.  On the
  // other hand, not highlighting it at all is also not good.  So, how about we
  // make the highlight disappear after, say, 7 seconds?").  A paragraph
  // tapped (p.t.named) keeps its tint: only this mark goes by itself.  In a
  // tab not shown, a reference opened in the background, counted from when it
  // is shown.  Again from the start at each new arrival; a tap lets go of it
  // sooner (unhit, which ends the count too).
  var HIT_HOLD = 5000, hitTimer = 0, hitWaits = false;
  function hitLater() {
    clearTimeout(hitTimer);
    hitTimer = 0;
    hitWaits = false;
    if (!document.querySelector(HIT)) return;
    if (document.hidden) { hitWaits = true; return; }
    hitTimer = setTimeout(function () {
      Array.prototype.forEach.call(document.querySelectorAll(HIT), function (p) { p.classList.add('hitgo'); });
      hitTimer = setTimeout(unhit, 800);
    }, HIT_HOLD);
  }
  document.addEventListener('visibilitychange', function () {
    if (hitWaits && !document.hidden) hitLater();
  });
  // A search's hit in a translation, /0:1.13#tr-ud, or in a translator's
  // note, /0:5.10#notetn_ud_0_5_10_0, on the whole paper's page after the
  // place (/0#0:1.13#tr-ud): arriveTr's, and cmpHit's in columns.  Here,
  // before arrive() first runs.
  var TR_HASH = /^#(?:\d+:\d+(?:\.\d+(?:-\d+)?)?#)?(?:tr-([a-z0-9-]+)|note(tn_([a-z0-9-]+)_\d+_\d+_\d+_\d+))$/;
  ['wheel', 'touchmove', 'keydown'].forEach(function (e) {
    addEventListener(e, function () { arriveTouched = Date.now(); }, { passive: true });
  });
  arrive();
  document.addEventListener('ub:page', function () { arrive(); });
  // Back on the whole paper's page from a place on it (#1:2.9, a note's
  // reference followed) to its address with no place: the marks go, and the
  // page returns to where it stood, kept in the entry's state as the place
  // was left (the click handler above), since the browser puts it back only
  // while listen.js's entries have not asked it not to (scrollRestoration).  Until 2026-11-06 arrive() ran, and scrolled to the
  // paragraph still marked.
  addEventListener('hashchange', function () {
    if (location.hash || !document.querySelector('article.whole')) return arrive();
    unhit();
    var s = history.state;
    if (s && s.ubY != null) { scrollTo({ top: s.ubY, behavior: 'instant' }); arriveTouched = Date.now(); }
  });

  // The whole paper's page (paper.html): the section being read, the last
  // whose top is above the window's top, less a line -- where Settings' Whole
  // paper turned off lands, and what the rail marks, as a section's page has
  // its own marked, following the page as it scrolls.
  function sectionInView() {
    var secs = document.querySelectorAll('article.whole > section[id]'), at = secs[0] || null;
    for (var i = 1; i < secs.length; i++)
      if (secs[i].getBoundingClientRect().top <= 60) at = secs[i]; else break;
    return at;
  }
  var railMarkAt = null, railMarkWait = false, railMarkP = null;
  function railMark() {
    railMarkWait = false;
    var s = sectionInView(), r;
    if (!s || !document.querySelector('.rail')) return;
    // A paragraph in hand holds the mark while it is on the screen
    // (railMarkOf, below).
    if (railMarkP) {
      r = railMarkP.isConnected && railMarkP.getBoundingClientRect();
      if (r && r.height && r.bottom > 0 && r.top < innerHeight) return;
      railMarkP = null;
    }
    if (s === railMarkAt) return;
    // Above the text, at the Contents (toContents, below, or scrolled up by
    // hand), the mark stays on the section the reader left; only a page with
    // none marked yet takes the first.
    if (railMarkAt && s.getBoundingClientRect().top > 60) return;
    railMarkAt = s;
    railPut(s);
  }
  // The rail's mark put on the whole paper's section `s`.
  function railPut(s) {
    var rail = document.querySelector('.rail');
    if (!rail) return;
    // A link once clicked is in the reader's unit already (above): both are
    // compared in it.
    var want = window.ubUnit ? window.ubUnit('/' + s.id) : '/' + s.id;
    Array.prototype.forEach.call(rail.querySelectorAll('li.here > details > ol > li'), function (li) {
      var a = li.querySelector('a');
      li.classList.toggle('here', !!a && (window.ubUnit ? window.ubUnit(a.pathname + a.hash) : a.getAttribute('href')) === want);
    });
  }
  // A paragraph in hand, named in the running head (showHead, below), is the
  // place being read, and the mark is its section's, whatever stands at the
  // window's top: a wide window has the end of one section at its top and the
  // next under it, and with 0:6.2 named there, and its reference followed to
  // the Contents, they marked section 5 (Tigran, 2026-11-18).  It holds the
  // mark while it is on the screen, the head up or not, and once it has
  // scrolled off the mark is the window's again (railMark), which above the
  // text, at a phone's Contents, leaves it where it is; and it is put again
  // as the Contents open at an entry of the history, a page loaded afresh
  // having marked by the window alone (toContents).  A translation's
  // paragraph is in its section as the English is, in a column or a fold.
  // Nothing on a section's own page, whose mark is the page's.
  function railMarkOf(p) {
    var s = p && p.closest && p.closest('article.whole > section[id]');
    if (!s) return;
    railMarkP = p;
    railMarkAt = s;
    railPut(s);
  }
  railMark();
  addEventListener('scroll', function () {
    if (railMarkWait) return;
    railMarkWait = true;
    requestAnimationFrame(railMark);
  }, { passive: true });
  document.addEventListener('ub:swap', function () { railMarkAt = railMarkP = null; railMark(); });

  // The left rail is the whole book (templates/_rail.html), and only the paper
  // being read comes with its sections.  Another opened there fetches its own
  // from /rail/N, asked for under the rail's version so that the browser
  // keeps them; if that fails, the paper's link is followed instead.  Listened
  // for on the document, capturing, because toggle does not bubble -- and so
  // it holds after listen.js swaps <main>.
  var railGot = {};
  // A book of the Bible's Contents (templates/_biblerail.html) opens to its
  // chapters, lifted from the book's own page (data-ch; its link goes to its
  // first chapter), which the offline copy keeps with them; if that fails,
  // the book's link is followed.
  document.addEventListener('toggle', function (ev) {
    var d = ev.target, li = d.parentNode, a, put;
    if (d.tagName !== 'DETAILS' || !d.open || !li || !li.classList || !li.classList.contains('lazy') ||
        d.querySelector('ol') || !li.closest('.kjvrail') || !(a = d.querySelector('summary a'))) return;
    put = function (html) { if (!d.querySelector('ol')) d.insertAdjacentHTML('beforeend', html); };
    var src = a.dataset.ch || a.pathname;
    if (railGot[src]) return put(railGot[src]);
    fetch(src, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (h) {
        // Each of its lists, a book the Synodal numbers otherwise having two,
        // the KJV's and the Synodal's, which ub.css shows by the first text.
        var lists = new DOMParser().parseFromString(h, 'text/html').querySelectorAll('ol.kchaps'), ol = '';
        if (!lists.length) throw new Error('no chapters');
        Array.prototype.forEach.call(lists, function (l) {
          ol += '<ol class="kch' + (l.classList.contains('kchk') ? ' kchk' : l.classList.contains('kchs') ? ' kchs' : '') + '">';
          Array.prototype.forEach.call(l.querySelectorAll('a'), function (x) {
            ol += '<li><a href="' + x.getAttribute('href') + '">' + x.textContent + '</a></li>';
          });
          ol += '</ol>';
        });
        railGot[src] = ol;
        put(railGot[src]);
      })
      .catch(function () { location.href = a.href; });
  }, true);
  document.addEventListener('toggle', function (ev) {
    var d = ev.target, li = d.parentNode;
    if (d.tagName !== 'DETAILS' || !d.open || !li || !li.classList || !li.classList.contains('lazy') ||
        d.querySelector('ol')) return;
    var rail = li.closest('.rail'), a = d.querySelector('summary a');
    if (!rail || !a) return;
    // The paper's number from where its link goes, whatever the unit: the
    // click handler above makes /4 into /4:0 with Whole paper off, and
    // /rail/4:0, asked for since, is no page, so the page was left (review
    // of 2026-11-09).
    var n = (/^\/(\d+)/.exec(a.pathname) || [])[1];
    if (!n) return;
    var put = function (html) {
      if (d.querySelector('ol')) return;
      d.insertAdjacentHTML('beforeend', html);
      var k = tocKey();
      if (k && tocGot[k]) tocDraw(d.querySelector('ol'), tocGot[k]);
    };
    if (railGot[n]) return put(railGot[n]);
    fetch('/rail/' + n + '?v=' + encodeURIComponent(rail.dataset.v || ''))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) { railGot[n] = html; put(html); })
      .catch(function () { location.href = a.href; });
  }, true);

  // The paper being read, into the rail's view: a sixth of the way down, so
  // the papers before it show too.  Only while the rail scrolls by itself,
  // beside the text; on a phone it is a block of the page and is left alone.
  // By the rail's scrollTop, never scrollIntoView, which would move the page
  // as well.  Again when the fonts are in, as arrive() does, unless the reader
  // has scrolled the rail meanwhile; and whenever listen.js swaps <main>.
  // The paper being read in the rail: the Foreword stands there twice, on its
  // own and in Part I (templates/_rail.html), and the one shown is the one to
  // scroll to.
  function railHere(rail) {
    var all = rail.querySelectorAll('li.here');
    for (var i = 0; i < all.length; i++) if (all[i].offsetParent !== null) return all[i];
    return all[0] || null;
  }
  function railView() {
    var rail = document.querySelector('.rail'), here = rail && railHere(rail);
    if (!here) return;
    var place = function () {
      if (rail.scrollHeight <= rail.clientHeight) return;
      rail.scrollTop += here.getBoundingClientRect().top - rail.getBoundingClientRect().top -
                        rail.clientHeight / 6;
    };
    place();
    var t = rail.scrollTop;
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      if (rail.scrollTop === t && rail.isConnected) place();
    });
  }
  railView();
  document.addEventListener('ub:swap', railView);

  // The Contents from the running head (Tigran, 2026-11-01; tapHead, below):
  // shut, opened as their own button opens them (above), and the paper being
  // read brought into view.  On a wide screen the rail scrolls to it
  // (railView); on a phone, where the rail is a block at the top of the page,
  // the page scrolls so that the paper stands a sixth of the way down the
  // window, as railView places it in the rail, its sections under it and the
  // one being read marked.  Nothing on a page with no Contents, a reading path.
  // On a phone the jump is a step in the history, at the same address, so
  // that Back undoes it (Tigran, the same day, finding Back at the home page,
  // the page before): the paragraph `p` left goes back to where it stood, the
  // Contents folded again if they were, and Forward opens them again.  While
  // the entry is the current one `contentsAt` is its state; a section's link
  // followed from the Contents leaves it for a new address (popstate, below,
  // and arrive() by history.state).  A fresh load of the entry, Back from
  // another page without the page cache, opens them again from history.state.
  // From a translation's paragraph they open as that translation gives its
  // contents (`k`, its key; Tigran, 2026-11-17: "it would be nice to switch
  // automatically to that translation's variant of Contents.  Currently it
  // goes to the English (UVERSA PRESS) always"), as the list at their head
  // would draw them, which shows it: for this opening, `tocOver` (below), the
  // reader's own choice there, `toc`, being left as it is, so that from an
  // English paragraph they open as chosen, the book's unless another was.  It
  // is in the entry's state, for Forward to it, and Back lets go of it.  The
  // paper is placed again once the translation's titles are in, a title of
  // more lines having moved it.
  var contentsAt = null;
  function toContents(p, k) {
    var b = document.querySelector('.railfold'), rail = b && b.closest('.rail'), shut, state, drawn, t;
    if (!rail) return false;
    shut = railShut(rail);
    k = k && (k === 'up' || tocTicked().indexOf(k) >= 0) ? k : null;
    if (phone.matches && p) {
      // Measured before the Contents open above it, as it will stand after
      // they fold again.
      state = { ub: 'contents', p: p.id, top: p.getBoundingClientRect().top, shown: !shut, href: location.href, k: k || '' };
      if (contentsAt) history.replaceState(state, ''); else history.pushState(state, '');
      contentsAt = state;
    }
    // The section marked is the paragraph's they were opened from (railMarkOf,
    // above), at an entry of the history the one its state names.
    railMarkOf(p || (contentsAt && document.getElementById(contentsAt.p)));
    if (tocOver !== k) { tocOver = k; drawn = tocApply(); }
    var place = function () {
      var here = phone.matches && railHere(rail);
      if (!here) return;
      scrollTo({ top: scrollY + here.getBoundingClientRect().top - innerHeight / 6, behavior: 'instant' });
      arriveTouched = Date.now();
    };
    if (shut) b.click(); else railView();
    place();
    t = arriveTouched;
    // Unless the reader has moved the page meanwhile.
    if (drawn) drawn.then(function () { if (arriveTouched === t && rail.isConnected) { railView(); place(); } });
    return true;
  }
  // The place the address names, gone to as a link to it goes: on the whole
  // paper's page a section's or a paragraph's, which arrive() finds; with
  // none, a section's own page or the paper's from its top, the page's top
  // with the Contents folded, as a phone's page opens.
  function toPlace() {
    var rail = document.querySelector('.rail');
    if (!location.hash) {
      if (rail && phone.matches && rail.classList.contains('shown')) { rail.classList.remove('shown'); railSync(); }
      scrollTo({ top: 0, behavior: 'instant' });
    }
    arrive();
  }
  // The section being read, tapped in the Contents the reference opened
  // (Tigran, 2026-11-17: "I stay where I was, but I expected to jump to the
  // start of this section, as it would if I tap on some other section").  Its
  // link is the address the entry already has, /101#101:4 on the whole
  // paper's page reached by that link, so the browser only replaces the
  // entry: it fires popstate with no state and no hashchange, at the same
  // address, which below is Back, and the paragraph was put back where it
  // stood; and a section's own page, /101:4, is loaded again with the entry's
  // state kept, and opened the Contents again from it.  So such a link is
  // made a step of its own here, as a link to another section is one: the
  // place gone to, Back the Contents again and Back again the paragraph.  Its
  // state says so, for Forward to it from the Contents, which is a popstate
  // at the same address too.  Only the Contents' own links, and only at their
  // entry: anywhere else the browser's own way is right.  Capturing, so
  // before listen.js, which follows a link itself while it plays.
  document.addEventListener('click', function (ev) {
    var a = contentsAt && ev.target.closest && ev.target.closest('.rail a[href]'), to;
    if (!a || ev.defaultPrevented || ev.button || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey ||
        a.target || a.hasAttribute('download') || a.origin !== location.origin) return;
    // In the reader's unit, whichever form the link has by now (the Whole
    // paper handler, above, rewrites it as it is clicked).
    to = a.pathname + a.hash;
    if (window.ubUnit) to = window.ubUnit(to);
    if (to !== location.pathname + location.hash || a.search !== location.search) return;
    ev.preventDefault();
    try { history.pushState({ ub: 'place' }, '', location.href); } catch (e) {}
    contentsAt = null;
    toPlace();
  }, true);
  addEventListener('popstate', function (ev) {
    var s = ev.state, was = contentsAt, rail = document.querySelector('.rail'), p;
    if (s && s.ub === 'contents') { contentsAt = s; toContents(null, s.k); return; }
    if (!was) return;
    contentsAt = null;
    // Forward from the Contents to the step a link to their own address made
    // (above): the place, not Back.
    if (s && s.ub === 'place') { toPlace(); return; }
    // A section's link followed from the Contents fires popstate too, in
    // Chrome, for its fragment: a new address, and the place is the link's.
    // Back to the entry before is the entry's own address, which the jump
    // kept.
    if (location.href !== was.href) return;
    // Back: the Contents are the reader's own choice again (toContents).
    if (tocOver) { tocOver = null; tocApply(); }
    if (rail && !was.shown && rail.classList.contains('shown')) { rail.classList.remove('shown'); railSync(); }
    p = document.getElementById(was.p);
    if (!p) return;
    // Now, and again over the next frames: the browser puts back the offset
    // it kept, before popstate, and as the Contents fold above the paragraph
    // its scroll anchoring moves the page once more, a frame on.
    var place = function () { scrollTo({ top: scrollY + p.getBoundingClientRect().top - was.top, behavior: 'instant' }); };
    place();
    requestAnimationFrame(function () { place(); requestAnimationFrame(place); });
    setTimeout(place, 120);
    arriveTouched = Date.now();
  });
  document.addEventListener('ub:swap', function () { contentsAt = null; });

  // The place being read, kept as a fold changes the text's width (Tigran,
  // 2026-11-08: unfolding the index at 44:1.13 took him a screen and more
  // away, to scroll back to the paragraph by hand).  The browser keeps no
  // place as the column narrows or widens: the scroll position stays, and the
  // text above reflows.  So the place is taken before the change and brought
  // back to the same height after it: a paragraph marked on the screen (the
  // one the page opened at, the one tapped, the one being read aloud), its
  // top; or else the line at the window's top, by the letter there, so that a
  // paragraph begun above the window is kept at the line being read.  At the
  // page's top the page stays at its top.  Columns keep their own (cmpGo).
  // The line at the window's top is a translation's as often as not, with
  // the translations open under every paragraph (trAll, below; 2026-11-20):
  // kept by its letter as the English is; and since such a line may be drawn
  // again by the change, or folded away with every other, the fold's own
  // line, which stays, is taken with it (`alt`), for placeBack to go by then;
  // and the English over it, for when the fold goes too, its last
  // translation unticked.
  //
  // And the line kept by what it is, its paragraph's address and its text,
  // and how far into it the place stood, its letter and its height: a
  // paragraph's first text, where it is not the English, is drawn anew as
  // the order of the texts or the columns change (ftxPut, 2026-11-20), and
  // the line taken is then gone; placeBack finds the same paragraph in the
  // same text, or in the one now first.
  function placeAlt(pl) {
    var tf = pl.el.closest('.tf'), b = tf && tf.querySelector('.trfold'), row = tf && tf.closest('.row'),
        en = row && row.querySelector('p.t[id]'), r, q;
    if (b) pl.alt = { el: b, y: b.getBoundingClientRect().top, alt: en && { el: en, y: en.getBoundingClientRect().top } };
    if ((pl.ref = pl.el.id || pl.el.dataset.ref || '')) {
      pl.k = pl.el.dataset.k || 'up';
      r = pl.el.getBoundingClientRect();
      pl.f = r.height ? (pl.y - r.top) / r.height : 0;
      if (pl.node && pl.el.contains(pl.node)) {
        q = document.createRange();
        q.setStart(pl.el, 0);
        q.setEnd(pl.node, pl.at);
        pl.off = q.toString().length;
      }
    }
    return pl;
  }
  // The line of paragraph `ref` in text k as the page now has it, shown;
  // else the paragraph's own line, its first text's.
  function placeAgain(pl) {
    var all = document.querySelectorAll(pl.k === 'up' ? 'main p.t:not(.rt)[id="' + pl.ref + '"], main p.t:not(.rt)[data-ref="' + pl.ref + '"], main .tf p.rt[data-k="up"][data-ref="' + pl.ref + '"]'
                                                     : 'main p[data-k="' + pl.k + '"][data-ref="' + pl.ref + '"]'), i;
    for (i = 0; i < all.length; i++) if (all[i].getClientRects().length) return all[i];
    all = document.getElementById(pl.ref);
    return all && all.getClientRects().length ? all : null;
  }
  var MARKED = 'main :is(p.t.hit, p.t.named, p.t.now, .rc p.rt.hit, .rc p.rt.named, .tf p.rt.named, .rt.now)';
  function placeNow() {
    var ms = document.querySelectorAll(MARKED), ps, i, r, p = null, c, n, at, q, rs, top = 0, over;
    if (scrollY <= 0) return null;
    // What stands over the text at the window's top, Compare's names stuck
    // there and the running head: the line read is the first under them.
    // The probe at 6 px found the names, and the place fell back to the
    // paragraph's top (review of 2026-11-09).
    over = Array.prototype.slice.call(document.querySelectorAll('main article.cmp .cmpnames'));
    if (head && !head.hidden) over.push(head);
    over.forEach(function (el) {
      var b = el.getBoundingClientRect();
      if (b.height && b.top <= 1 && b.bottom > top) top = b.bottom;
    });
    for (i = 0; i < ms.length; i++) {
      r = ms[i].getBoundingClientRect();
      if (r.height && r.top >= top && r.top < innerHeight) return placeAlt({ el: ms[i], y: r.top });
    }
    ps = document.querySelectorAll('main :is(p.t[id], .tf.open p.rt)');
    for (i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > top + 4) { p = ps[i]; break; }
    }
    if (!p) return null;
    if (r.top >= top + 4) return placeAlt({ el: p, y: r.top });
    c = document.caretPositionFromPoint ? document.caretPositionFromPoint(r.left + r.width / 2, top + 6) : null;
    if (c) { n = c.offsetNode; at = c.offset; }
    else if (document.caretRangeFromPoint && (c = document.caretRangeFromPoint(r.left + r.width / 2, top + 6))) {
      n = c.startContainer; at = c.startOffset;
    }
    if (n && n.nodeType === 3 && n.length && p.contains(n)) {
      at = Math.min(at, n.length - 1);
      q = document.createRange();
      q.setStart(n, at);
      q.setEnd(n, at + 1);
      rs = q.getClientRects();
      if (rs.length) return placeAlt({ el: p, node: n, at: at, y: rs[0].top });
    }
    return placeAlt({ el: p, y: r.top });
  }
  // What is gone from the page, or has no box, says nothing of where the page
  // should stand: measured, it stood at the window's top, and the page went
  // up by the whole of its height.  A fold's line stands in for its words.
  function placeBack(pl) {
    var y = null, q, rs, el, w, n, off, r;
    if (!pl) return;
    if (!pl.el.isConnected || !pl.el.getClientRects().length) {
      el = pl.ref && placeAgain(pl);
      if (!el) return placeBack(pl.alt);
      // The same text's line, by its letter; another's, by how far down it.
      r = el.getBoundingClientRect();
      y = r.top + (pl.f || 0) * r.height;
      if (pl.off != null && (el.dataset.k || 'up') === pl.k) {
        w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        for (off = pl.off, n = w.nextNode(); n && off > n.length; n = w.nextNode()) off -= n.length;
        if (n && off < n.length) {
          q = document.createRange();
          q.setStart(n, off);
          q.setEnd(n, off + 1);
          rs = q.getClientRects();
          if (rs.length) y = rs[0].top;
        }
      }
      if (Math.abs(y - pl.y) >= 1) scrollBy({ top: y - pl.y, behavior: 'instant' });
      return;
    }
    if (pl.node && pl.node.isConnected && pl.at < pl.node.length) {
      q = document.createRange();
      q.setStart(pl.node, pl.at);
      q.setEnd(pl.node, pl.at + 1);
      rs = q.getClientRects();
      if (rs.length) y = rs[0].top;
    }
    if (y === null) y = pl.el.getBoundingClientRect().top;
    if (Math.abs(y - pl.y) >= 1) scrollBy({ top: y - pl.y, behavior: 'instant' });
  }
  // Held there while the page settles, frame by frame: what was drawn asks
  // for a typeface not yet here, the Cyrillic of a translation first shown,
  // and as it comes in the lines break again, the English's too, and the
  // browser moves the page to keep what it takes for the place, which is
  // another line.  For a third of a second, and as long after a typeface was
  // last on its way, two and a half seconds at the most; and let go as soon
  // as the reader moves the page, or the page is taken elsewhere (arrive): by
  // what is done (arriveTouched), not by where the page is, which the browser
  // has just changed.  One place at a time: a later one ends an earlier.
  var holdN = 0;
  function placeHold(pl, t) {
    var busy = t, n = ++holdN;
    requestAnimationFrame(function hold() {
      var now = Date.now();
      if (n !== holdN || arriveTouched > t) return;
      placeBack(pl);
      if (document.fonts && document.fonts.status === 'loading') busy = now;
      if (now - busy < 300 && now - t < 2500) requestAnimationFrame(hold);
    });
  }
  // `placeKept` is the place while the change is made, for what the change
  // sets off to keep the same one: a fold that turns the page into columns,
  // or out of them (cmpGo), which taking the place again, after the fold,
  // would keep by another letter of the line, a line off as often as not.
  // `at`, where given, is the place to keep, a line the reader tapped that
  // stays on the page whatever the change (a box of entries' own, below).
  var placeKept = null;
  function keepPlace(change, at) {
    var pl = at || placeNow();
    placeKept = pl;
    try { change(); } finally { placeKept = null; }
    if (!pl) return;
    placeBack(pl);
    // Again a frame on, when what the change set off has been drawn.
    requestAnimationFrame(function () { placeBack(pl); });
    arriveTouched = Date.now();
  }

  // The button at the rail's head folds it (ub.css .railfold).  On a wide
  // screen away to the left, kept as the setting 'rail' (settings.py KEPT); on
  // a phone up to its one line, which every page starts as, so a class on the
  // rail opens it for this page only.  The button says which it would do.
  var phone = matchMedia('(max-width: 62rem)');
  function railShut(rail) {
    return phone.matches ? !rail.classList.contains('shown') : load().rail === 'folded';
  }
  function railSync() {
    var b = document.querySelector('.railfold'), shut;
    if (!b) return;
    shut = railShut(b.closest('.rail'));
    b.setAttribute('aria-expanded', String(!shut));
    var w = shut ? T.k('Show the contents') : T.k('Fold the contents away');
    T.attr(b, 'title', w);
    T.attr(b, 'aria-label', w);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.railfold'), rail, shut;
    if (!b) return;
    rail = b.closest('.rail');
    shut = railShut(rail);
    // On a phone the Contents open above the text, where the button is.
    if (phone.matches) {
      // Open from the running head's reference (toContents, above), their
      // line is the way back to the paragraph left, as Back is, which was
      // the only way: a tap on the section being read goes to its start now,
      // and the line only folded them, leaving the page wherever that put
      // it (Tigran, 2026-11-17: "simply tapping on the \"CONTENTS\" line
      // should bring me back"; a little cross at their corner was his first
      // thought).  The line stays at the window's top while they are open
      // (ub.css), so it is always at hand.
      if (!shut && contentsAt) { history.back(); return; }
      rail.classList.toggle('shown', shut);
      // Folded from within them, the line itself stays in view, the text
      // under it: the page is as long as they were shorter.
      if (!shut && rail.getBoundingClientRect().top < 0) {
        scrollBy({ top: rail.getBoundingClientRect().top, behavior: 'instant' });
        arriveTouched = Date.now();
      }
    } else keepPlace(function () { window.ubSettings.set('rail', shut ? 'open' : 'folded'); });
    railSync();
    if (shut) railView();
  });
  railSync();
  if (phone.addEventListener) phone.addEventListener('change', railSync);

  // The index folds (templates/_fold.html, ub.css .indexfold): its button,
  // kept as the setting 'margin' (settings.py KEPT), folds the margin to the
  // right on a wide screen, and on a phone every box of entries to its line.
  // On a phone a box's own line is the same switch (Tigran, 2026-11-21:
  // "folding/unfolding the index entries under one paragraph should
  // fold/unfold them everywhere and persist"): a tap on it opens every box or
  // folds them all, on every page from then on, and the line, which every box
  // keeps open or folded, stays where it stood.  Until then it opened its own
  // box for that page alone (`.shown`), and Continue reading came back to the
  // paragraph with it folded again.  On a wide screen the only line is the
  // columns' box of many entries (cmpDraw, .cmpfold), the index being shown
  // there, which opens for that page as before.
  function indexSync() {
    var on = load().margin !== false, b = document.querySelector('.indexfold');
    if (b) {
      b.setAttribute('aria-expanded', String(on));
      var w = on ? T.k('Fold the index away') : T.k('Show the index');
      T.attr(b, 'title', w);
      T.attr(b, 'aria-label', w);
    }
    // On a phone every box as the index is; in columns on a wide screen a box
    // of many lines is folded to its line though the index is shown (cmpDraw,
    // .cmpfold), and opened for the page (.shown).
    Array.prototype.forEach.call(document.querySelectorAll('.afold'), function (x) {
      var box = x.parentNode;
      x.setAttribute('aria-expanded', String(phone.matches ? on : (on && !box.classList.contains('cmpfold')) || box.classList.contains('shown')));
    });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.indexfold, .afold');
    if (!b) return;
    if (b.classList.contains('indexfold'))
      return keepPlace(function () { window.ubSettings.set('margin', load().margin === false); });
    if (phone.matches && b.getClientRects().length)
      return keepPlace(function () { window.ubSettings.set('margin', load().margin === false); },
                       { el: b, y: b.getBoundingClientRect().top });
    b.parentNode.classList.toggle('shown');
    indexSync();
  });
  // Whatever changed it, a tap here or Restore the defaults: each line says
  // which way it goes.
  document.addEventListener('ub:settings', function (ev) { if (ev.detail.key === 'margin') indexSync(); });
  indexSync();
  if (phone.addEventListener) phone.addEventListener('change', indexSync);
  // A row's translations, folded under it (ROADMAP item 15, step 2; templates/
  // _fold.html trfold).  Its line says how many of those ticked in Settings it
  // has; opened, it shows them, in the reader's order, one at a time in tabs or
  // All, stacked, each named, fetched with the rest of the section's the first
  // time one is opened (/tr/<paper>:<section>, under the article's version, as
  // /rail/N is), and kept for the page.  The tab chosen opens the next fold
  // (settings.py KEPT `trtab`).  A translator's note opens as a card at its
  // number, as a study note does (open(), below), from the fold, where its words
  // are put hidden with its paragraph's.  Offline they come from the copy, each
  // translation a download of its own, chosen in Settings' Offline tab
  // (offline.js), which tells the folds when what it keeps changes
  // (`ub:trkept`): one ticked here and not kept there says so in its tab.
  // A fold's line opens the translations under every paragraph, and folds
  // them all again, and they stay so: on the next page, in the next session,
  // and for a reader signed in on every device (settings.py KEPT `tropen`,
  // which follows the account, as the tab does; Tigran, 2026-11-20: "Folding
  // or unfolding a single paragraph's translations should affect all
  // paragraphs and this state should be preserved globally").  Until then a
  // line opened its own paragraph's, for that page, and Continue reading
  // came back to the paragraph with the translations folded again.
  // `trOpen` is what this page shows, every fold open or every fold shut:
  // the setting's as the page begins, then a tap's here, or a change's from
  // outside (below).  A tap asks it and never the setting as stored, which a
  // browser that keeps nothing never changes, and another tab may have.
  // `trTap` is true while a tap here changes a setting, whose listener then
  // leaves the folds to the tap.
  var TRS = [], trBy = {}, trGot = {}, trOpen = load().tropen === true, trTap = false;
  try { TRS = JSON.parse((document.getElementById('ub-translations') || {}).textContent || '[]'); } catch (e) {}
  TRS.forEach(function (x) { trBy[x.key] = x; });

  // The texts shown, in the reader's order (Tigran, 2026-11-20: the English
  // one of them, "not singling out English as special, even though it is the
  // original"): "up" the English, put in among the translations ticked at its
  // place (base.html ubTexts, settings.py TRANSLATIONS), and the translations
  // the site has.  Never none: the English, which stands wherever no text
  // shown has a paragraph.  Each paragraph's first text of these is set where
  // the English stood, and the rest are in columns beside it where the window
  // has room, and in its fold where it has not (cmpDraw).
  function texts() {
    var o = load(), ks = window.ubTexts ? window.ubTexts(o.translations, o.english)
                                        : ['up'].concat(String(o.translations || '').split(' '));
    ks = ks.filter(function (k) { return k === 'up' || trBy[k]; });
    return ks.length ? ks : ['up'];
  }
  // The order of the translations in a list of voices: by language, as
  // Settings' Texts groups them, and within one by short name (2026-11-20).
  function voiceOrder(a, b) {
    var x = trBy[a], y = trBy[b];
    return x.lang < y.lang ? -1 : x.lang > y.lang ? 1 : x.label.localeCompare(y.label, 'en');
  }
  // The two settings an order is, {translations, english}.
  function textsOf(order) {
    var up = order.indexOf('up');
    return { translations: order.filter(function (k) { return k !== 'up'; }).join(' '),
             english: up < 0 ? 'off' : up ? String(up) : '' };
  }
  // A text's names, the English's as the columns name it, its short name the
  // press's, as a translation's is its own (data/translations.toml label).
  var UP = { key: 'up', label: 'Uversa Press', lang: 'en' };
  function txt(k) { return k === 'up' ? UP : trBy[k]; }

  // The contents in a translation (Tigran, 2026-10-27).  The list on the
  // rail's line (templates/_rail.html) offers the book, as Compare names it,
  // and each translation ticked, by its short name, in Settings' order; the
  // choice, kept as `toc` (settings.py KEPT), draws the rail as that one gives
  // its contents, from /rail/<key> (app.py toc_of): its parts', papers' and
  // sections' titles, and the rail's own words in its language, «0. Введение»,
  // «Часть I.», «9 и 10.».  What it has not stays in English, greyed (.untr),
  // and what it writes in capitals is set in small capitals (.caps).  The
  // English of each link is kept, to be put back.  The head script set
  // data-toc before first paint, which keeps the tree unseen until it is drawn
  // (ub.css), and .tocready shows it, drawn or not: offline, a translation not
  // kept leaves the rail in English.
  // `tocOver` is a translation's key while the Contents stand as the running
  // head's reference opened them from that translation's paragraph
  // (toContents, above): drawn in it and named so in the list, with `toc`
  // not changed; a choice in the list, another opening, Back or a new page
  // ends it.
  var tocGot = {}, tocEn = new WeakMap(), ROMAN = ['', 'I', 'II', 'III', 'IV'], tocOver = null;
  var RE_RAILA = /^\/(?:part\/([0-9]+)|([0-9]+)(?::([0-9]+))?)$/;
  function tocTicked() {
    return String(load().translations || '').split(' ').filter(function (k) { return trBy[k]; });
  }
  // The contents chosen: a translation's key, or '' for the book's own.  Not
  // chosen (`toc` ''), the first text's (texts(), 2026-11-20), which is the
  // book's own while the English is first; "up" is the book's chosen.
  function tocKey() {
    var k = tocOver || load().toc || texts()[0];
    return tocTicked().indexOf(k) >= 0 ? k : '';
  }
  function tocSync() {
    var l = document.querySelector('.railtr'), sel = l && l.querySelector('select'), ks = tocTicked();
    if (!sel) return;
    l.hidden = !ks.length;
    sel.innerHTML = '<option value="up">Uversa Press</option>' + ks.map(function (k) {
      return '<option value="' + k + '">' + trBy[k].label + '</option>';
    }).join('');
    sel.value = tocKey() || 'up';
  }
  // Each link of `root` the rail can place by its address, in the contents
  // `d`, or the book's with none.  By the address the rail gave it, which a
  // link once clicked no longer has (hrefWas, above): in the reader's unit a
  // section's is /0#0:6, which is no address of the rail's, and a paper's
  // /15:0, which is its introduction's.
  function tocDraw(root, d) {
    if (!root) return;
    Array.prototype.forEach.call(root.querySelectorAll('a[href]'), function (a) {
      var m = RE_RAILA.exec(hrefWas.get(a) || a.getAttribute('href'));
      if (!m) return;
      if (!tocEn.has(a)) tocEn.set(a, a.innerHTML);
      var en = tocEn.get(a), h = null, caps, k;
      a.classList.remove('untr');
      a.removeAttribute('lang');
      if (!d) { a.innerHTML = en; return; }
      var put = function (title, kind) {
        return d.caps[kind].indexOf(k) >= 0 ? '<span class="caps">' + title + '</span>' : title;
      };
      if (m[1]) {                                    // a part
        k = m[1];
        if (d.parts[k] != null) h = d.words.part.replace('{r}', ROMAN[+k]) + ' ' + put(d.parts[k], 'parts');
      } else if (m[3] === undefined) {               // a paper; the Foreword has no number
        k = m[2];
        if (d.papers[k] != null) h = (k === '0' ? '' : k + '. ') + put(d.papers[k], 'papers');
      } else if (m[3] === '0') {                     // a paper's introduction, named by us
        if (d.papers[m[2]] != null) h = d.words.intro;
      } else {
        k = m[2] + ':' + m[3];
        var two = /^([0-9]+) and ([0-9]+)\./.exec(a.textContent);   // 139's "9 and 10"
        if (d.sections[k] != null)
          h = (two ? d.words.and.replace('{a}', two[1]).replace('{b}', two[2]) : m[3]) + '. ' +
              put(d.sections[k], 'sections');
      }
      if (h == null) {
        a.innerHTML = en;
        a.classList.add('untr');
      } else {
        a.innerHTML = h;
        a.lang = d.lang;
      }
    });
  }
  function tocApply() {
    var r = document.documentElement, rail = document.querySelector('.rail'), k = tocKey();
    var done = function (d) {
      if (tocKey() !== k) return;                   // chosen again meanwhile
      tocDraw(rail, d);
      r.classList.add('tocready');
    };
    tocSync();
    // A promise, kept once they are drawn, for what places the rail after.
    if (!rail || !k) { done(null); return Promise.resolve(); }
    if (tocGot[k]) { done(tocGot[k]); return Promise.resolve(); }
    return fetch('/rail/' + k + '?v=' + encodeURIComponent(trBy[k].toc || ''))
      .then(function (res) { if (!res.ok) throw new Error(res.status); return res.json(); })
      .then(function (d) { tocGot[k] = d; done(d); })
      .catch(function () { done(null); });
  }
  document.addEventListener('change', function (ev) {
    if (!ev.target.closest || !ev.target.closest('.railtr')) return;
    // The reader's choice, which ends what a reference opened them in; drawn
    // here too, the choice being no change where it is what was kept.
    // The first text's chosen is no choice: the contents follow the first,
    // whichever it comes to be.
    tocOver = null;
    window.ubSettings.set('toc', ev.target.value === texts()[0] ? '' : ev.target.value);
    tocApply();
  });
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'toc' || ev.detail.key === 'translations' || ev.detail.key === 'english') tocApply();
  });
  // listen.js's <main>, the rail with it: a new page, as the reader chose.
  document.addEventListener('ub:swap', function () { tocOver = null; tocApply(); });
  tocApply();
  // A fresh load of the Contents' entry (toContents, above): here, once
  // `phone` is, which toContents asks, and the translations and their
  // contents, which it may open in.
  if (history.state && history.state.ub === 'contents') { contentsAt = history.state; toContents(null, history.state.k); }
  // The texts a row's fold holds, in the reader's order: those shown that the
  // row has, the English among them where it is shown, but the row's first
  // text, which stands over the fold (firstOf, below).  A head's fold (.tfh,
  // trHeads) holds those its section has but the text of the head over it,
  // which is its first row's (ftxHeads).
  function trKeys(tf) {
    var has = (tf.dataset.has || '').split(' '), row = tf.parentNode, ks = texts(), first;
    if (tf.classList.contains('tfh')) row = row.querySelector(':scope > .grid > .row');
    first = row && row.classList && row.classList.contains('row') ? firstOf(row, ks, null) : 'up';
    return ks.filter(function (k) {
      return k !== first && (k === 'up' || has.indexOf(k) >= 0);
    });
  }
  // `sec` is the section's address, `el` its element, section[data-trv],
  // which carries the version (templates/_text.html textof).
  function trFetch(el, sec) {
    var v = (el && el.dataset.trv) || '', key = sec + '?' + v;
    if (!trGot[key]) {
      trGot[key] = fetch('/tr/' + sec + '?v=' + encodeURIComponent(v))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (h) {
          var t = document.createElement('template'), got = { t: {}, n: {}, h: {} };
          t.innerHTML = h;
          Array.prototype.forEach.call(t.content.querySelectorAll('[data-k][data-ref]'), function (d) {
            (got.t[d.dataset.k] = got.t[d.dataset.k] || {})[d.dataset.ref] = d.innerHTML;
          });
          // Its titles, which Compare heads its columns with.
          Array.prototype.forEach.call(t.content.querySelectorAll('[data-k][data-head]'), function (d) {
            (got.h[d.dataset.k] = got.h[d.dataset.k] || {})[d.dataset.head] = d.innerHTML;
          });
          Array.prototype.forEach.call(t.content.querySelectorAll('aside[data-k][data-of]'), function (d) {
            var at = got.n[d.dataset.k] = got.n[d.dataset.k] || {};
            at[d.dataset.of] = (at[d.dataset.of] || '') + d.outerHTML;
          });
          return got;
        });
      trGot[key].catch(function () { delete trGot[key]; });
    }
    return trGot[key];
  }
  // A table row's words and its figure, as _para.html splits the English's.
  function trLead(h) {
    var r = h.split('<span class="leader"></span>');
    return r.length === 2 ? '<span class="leadrow"><span class="lab">' + r[0] + '</span><span class="fig">' +
                            '<span class="leader"></span>' + r[1] + '</span></span>' : h;
  }
  // One translation's words for the lines of a row, as a fold and Compare both
  // draw them, {h, notes}: a heading in the text (0:12.10) centred, and a
  // paper's first paragraph its first letter dropped, as the English's are and
  // as each translation's own TeX sets them (\lettrine); and the notes of those
  // lines, which their numbers open as cards.
  // In columns (`stk`) a paragraph's first line is set as the English's is,
  // p.t, with a stack at its start for its ▶ and the time it takes to hear
  // (listen.js trPlay), and no reference, which is the first column's
  // (Tigran, 2026-11-20: "maybe then we should do with the other columns
  // what we do with the first, i.e. place the playback triangle inside the
  // paragraph ... But with the paragraph reference you made the correct
  // decision to display it only against the first column"); its ▶ stood in
  // the gap before the column until then, with no time.
  function trLines(got, k, lines, stk) {
    var x = trBy[k], h = '', notes = '';
    Array.prototype.forEach.call(lines, function (q, i) {
      var ref = q.id || q.dataset.ref, t = (got.t[k] || {})[ref], c = q.classList, s = stk && i === 0;
      if (t != null) h += '<p class="' + (s ? 't rt' : 'rt') + (c.contains('head') ? ' head' : '') + (c.contains('opening') ? ' opening' : '') +
                          '" lang="' + x.lang + '" data-k="' + k + '" data-ref="' + ref + '">' + (s ? '<span class="stk"></span>' : '') +
                          trLead(t) + '</p>';
      notes += (got.n[k] || {})[ref] || '';
    });
    return { h: h, notes: notes };
  }
  // The English's lines for a fold, as a translation's are drawn there: each
  // a p.rt with its address as data-ref, without the stack at its start,
  // which is the row's, and without an id, which stays the row's (no id
  // stands twice); its marks, the 1955 rings and the study notes' numbers,
  // open their cards from here too.
  function enFold(lines) {
    var h = '';
    lines.forEach(function (q) {
      var c = q.cloneNode(true), cls = ['opening', 'head', 'pc'].filter(function (n) { return q.classList.contains(n); });
      Array.prototype.forEach.call(c.querySelectorAll('.stk, .ftxwho'), function (el) { el.remove(); });
      Array.prototype.forEach.call(c.querySelectorAll('[id]'), function (el) { el.removeAttribute('id'); });
      h += '<p class="rt' + (cls.length ? ' ' + cls.join(' ') : '') + '" lang="en" data-k="up" data-ref="' + refOf(q) + '">' + c.innerHTML + '</p>';
    });
    return h;
  }
  // The tab a fold of `ks` is drawn at: the one asked for, or the one last
  // chosen (`trtab`), where the fold has it; else its first.
  function trTab(ks, tab) {
    var want = tab || load().trtab;
    return want === 'all' && ks.length > 1 ? 'all' : ks.indexOf(want) >= 0 ? want : ks[0];
  }
  function trUnfold(tf) {
    var b = tf.querySelector('.trfold');
    tf.classList.add('open');
    if (b) b.setAttribute('aria-expanded', 'true');
  }
  // `tab`, where a search's hit names one (arriveTr), opens the fold at it in
  // place of the one last chosen, which it does not change.  Its promise is kept
  // once the fold is drawn.
  function trDraw(tf, ks, tab) {
    var panel = tf.querySelector('.tr'), head = tf.classList.contains('tfh'), sec = tf.closest('section[data-trv]');
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'tr';
      tf.appendChild(panel);
    }
    panel.hidden = false;
    var lines = head ? [] : enLines(tf.parentNode), refs = lines.map(refOf);
    if (!head && !refs.length) return Promise.resolve();
    return trFetch(sec, head ? sec.id : refs[0].split('.')[0]).then(function (got) {
      if (!tf.classList.contains('open')) return;
      var cur = trTab(ks, tab), h = '', notes = '';
      // A line that names one translation says so, `data-play`: listen.js
      // puts that translation's ▶ at its start ('ub:trfold', below).  Not a
      // head's: a section is heard from its heading by the English's ▶.
      var play = function (k) { return head ? '' : ' data-play="' + k + '"'; };
      if (ks.length > 1) {
        h += '<div class="trtabs" role="group"' + (cur === 'all' ? '' : play(cur)) + '>' + ks.map(function (k) {
          return '<button type="button" data-tab="' + k + '" aria-pressed="' + (cur === k) + '">' +
                 txt(k).label + '</button>';
        }).join('') + '<button type="button" data-tab="all" aria-pressed="' + (cur === 'all') + '">' +
                 T('All|translations') + '</button></div>';
      }
      // Each named by its short name, as its tab is: who made it, in full,
      // would take two lines on a phone, and Settings says it (Tigran,
      // 2026-10-26).
      (cur === 'all' ? ks : [cur]).forEach(function (k) {
        var x = txt(k);
        if (cur === 'all' || ks.length === 1) h += '<p class="who"' + play(k) + '>' + x.label + '</p>';
        // The English, where it is no paragraph's first text, is folded too
        // (Tigran, 2026-11-20), from the page's own.
        if (k === 'up') return (h += head ? enHead(tf) : enFold(lines));
        // Every one the fold counts is in the fragment the server sends, so one
        // missing is offline, and not kept in the copy.
        if (!got.t[k]) return (h += '<p class="gap">' + T('tr:notkept') + '</p>');
        if (head) return (h += trHead(tf, k, got.h[k] || {}));
        var w = trLines(got, k, lines);
        h += w.h;
        notes += w.notes;
      });
      if (card && panel.contains(card.mark)) shut(false);
      // The running head of a paragraph here goes with it (tapHead, below).
      if (headP && panel.contains(headP)) hideHead();
      panel.innerHTML = h + (notes && '<div class="tnotes" hidden>' + notes + '</div>');
      document.dispatchEvent(new CustomEvent('ub:trfold', { detail: panel }));   // listen.js: its ▶
    }, function () {
      if (tf.classList.contains('open')) panel.innerHTML = '<p class="gap">' + T('tr:unreachable') + '</p>';
    });
  }
  // A search's hit in a translation opens /0:1.13#tr-ud, and one in a
  // translator's note /0:5.10#notetn_ud_0_5_10_0 (templates/search.html): the
  // paragraph marked .hit, which arrive() brings into view, its fold open at
  // that translation, if the reader shows it, and the note's card.  Placed
  // again when the fonts are in and the text has reflowed, as arriveNote()
  // places a study note's.
  function arriveTr() {
    if (cmpOn()) return;                                   // in their columns (cmpHit, cmpArrive)
    var m = TR_HASH.exec(location.hash),
        hit = m && document.querySelector('p.t.hit'), row = hit && hit.closest('.row'),
        tf = row && row.querySelector('.tf'), k = m && (m[1] || m[3]), b = tf && tf.querySelector('.trfold');
    if (!b || trKeys(tf).indexOf(k) < 0) return;
    tf.classList.add('open');
    b.setAttribute('aria-expanded', 'true');
    trDraw(tf, trKeys(tf), k).then(function () {
      var mark = m[2] && document.getElementById('fnref' + m[2]);
      if (!mark || !tf.contains(mark)) return;
      shut(false);
      open(mark);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
        if (card && card.mark === mark) place();
      });
    }, function () {});
  }
  function trShut(tf) {
    if (card && tf.contains(card.mark)) shut(false);
    if (headP && tf.contains(headP)) hideHead();
    tf.classList.remove('open');
    var b = tf.querySelector('.trfold'), panel = tf.querySelector('.tr');
    if (b) b.setAttribute('aria-expanded', 'false');
    if (panel) panel.hidden = true;
  }
  // Each fold's line says how many it holds, and a fold that is open is drawn
  // again, at the tab now chosen, or shut where none is left to show.  Only a
  // fold of the text's (data-has): Help's example of one is words (help.html).
  // The heads' folds made first, where the page has none yet (trHeads).
  // A promise, kept once those drawn again are drawn.
  function trSync() {
    var draws = [];
    trHeads();
    Array.prototype.forEach.call(document.querySelectorAll('.tf[data-has]'), function (tf) {
      var ks = trKeys(tf), b = tf.querySelector('.trfold');
      if (!b) return;
      // "2 texts" where the English is among them (2026-11-20).
      b.innerHTML = !ks.length ? '' : ks.indexOf('up') < 0 ? T('{n} translations', { n: ks.length }) : T('{n} texts', { n: ks.length });
      if (!tf.classList.contains('open')) return;
      if (ks.length) draws.push(trDraw(tf, ks)); else trShut(tf);
    });
    return Promise.all(draws);
  }
  // Every fold of the page opened, where the reader has them open (trOpen)
  // and the page is not in columns.  Each section's translations are had
  // first, all of them (trFetch, a request to a section, as the columns ask),
  // so that the folds open in one step and the page is put back once; then
  // every fold with a translation the reader shows, not yet open.  Asked
  // again once they are had: the page may have gone into columns meanwhile,
  // where no fold is drawn and a note's number would stand twice, or the
  // reader may have folded them.  A fold already open is left as it is, a
  // search's hit's at its own translation (arriveTr).  Where a section's
  // could not be had, or a fold would show nothing of what it holds, it
  // stays shut: offline, with a translation not kept, the page does not say
  // so under every paragraph, and the fold tapped does (the click, below).
  // A promise of how many it opened.
  function trAll() {
    var art = cmpArt(), n = cmpN, secs, shutIn = function (sec) {
      return Array.prototype.filter.call(sec.querySelectorAll('.tf[data-has]:not(.open)'), function (tf) {
        return trKeys(tf).length;
      });
    };
    if (!trOpen || !art || cmpOn()) return Promise.resolve(0);
    secs = Array.prototype.filter.call(art.querySelectorAll('section[data-trv]'), function (sec) { return shutIn(sec).length; });
    if (!secs.length) return Promise.resolve(0);
    return Promise.all(secs.map(function (sec) {
      return trFetch(sec, sec.id).then(function (got) { return got; }, function () { return null; });
    })).then(function (gots) {
      var draws = [];
      if (n !== cmpN || !trOpen || cmpIs || !art.isConnected) return 0;
      secs.forEach(function (sec, j) {
        var got = gots[j];
        if (got) shutIn(sec).forEach(function (tf) {
          // The English is the page's own, never in the fragment: a fold at
          // its tab opens too, which it did not until 2026-11-21, so that with
          // a translation first and the folds at Uversa Press only the fold
          // tapped opened.
          var ks = trKeys(tf), cur = trTab(ks);
          if (!(cur === 'all' ? ks : [cur]).some(function (k) { return k === 'up' || got.t[k]; })) return;
          trUnfold(tf);
          draws.push(trDraw(tf, ks));
        });
      });
      // They are all the reader's now: the reading shuts none of them (ubTrRead).
      if (draws.length) trMine = null;
      return Promise.all(draws).then(function () { return draws.length; });
    });
  }
  // The place while every fold opens, shuts, or is drawn again, the page
  // above it growing or shrinking by screens: a fold's own line, which the
  // reader tapped, kept where it stands; or, with no tap, the line at the
  // window's top (placeNow).  The line and never its .tf, which on a phone
  // with the index folded has no box (base.html ubTr, display: contents).
  function trPlace(tf) {
    var b = tf && tf.querySelector('.trfold');
    return b && b.getClientRects().length ? { el: b, y: b.getBoundingClientRect().top } : placeNow();
  }
  // And put back: at once, where what the change did is done; again once
  // `job` is kept, the folds drawn, and held while a typeface comes in; a
  // note's card, which stands by its mark, with it.  `own` is a tap here,
  // the reader's own move, which an arrival still under way gives way to; a
  // change from outside is none, and counts no page as read (rpEngage).
  function trKeep(pl, job, own) {
    var t = Date.now();
    if (own) arriveTouched = t;
    placeBack(pl);
    return job.then(function (got) {
      if (arriveTouched <= t) {
        placeBack(pl);
        if (pl) placeHold(pl, t);
      }
      if (card) place();
      return got;
    }, function () {});
  }
  // Every fold, as the page now has them.
  function trTurn(pl, own) {
    if (cmpOn()) return Promise.resolve(0);
    if (!trOpen) Array.prototype.forEach.call(document.querySelectorAll('.tf.open'), trShut);
    return trKeep(pl, trOpen ? trAll() : Promise.resolve(0), own);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.trfold, .trtabs button[data-tab]'), tf = b && b.closest('.tf');
    if (!tf) return;
    var ks = trKeys(tf), pl = trPlace(tf), want;
    // Help's example of a fold has none to show, and is no control.
    if (!ks.length) return;
    if (b.classList.contains('trfold')) {
      want = !tf.classList.contains('open');
      // The one tapped at once, and it says why where it has nothing to show.
      if (want) { trUnfold(tf); trDraw(tf, ks); } else trShut(tf);
      // As the page already has them, this one stood alone: opened by a
      // search's hit or by the reading with the rest shut, or left shut with
      // the rest open, its words not to be had.  Open, the rest are tried again.
      if (want === trOpen) return void (want && trKeep(pl, trAll(), true));
      trOpen = want;
      trTap = true;
      try { window.ubSettings.set('tropen', want); } finally { trTap = false; }
      return void trTurn(pl, true);
    }
    // A tab: every open fold is drawn again at it (trSync), which is every
    // fold of the page where they are open.
    trTap = true;
    try { window.ubSettings.set('trtab', b.dataset.tab); } finally { trTap = false; }
    trKeep(pl, trSync().then(trAll), true);
  });
  // The line a translation's voice is reading (listen.js; Tigran, 2026-10-27),
  // for it to mark: in Compare its column's, else the fold's under the
  // paragraph, where the fold shows that translation.  With `open` (Follow
  // along), a fold that is shut is opened at it, as a search's hit opens one,
  // without changing the tab last chosen, and the fold the reading opened
  // before is shut again; a fold the reader opened is never shut.  ref null is
  // the heading, which only Compare gives a translation; k null shuts the fold
  // the reading opened.  A promise of the element, or of null.
  var trMine = null;
  // Since 2026-11-20 any text may be a paragraph's first, set where the
  // English stood (ftxPut), the English among those in a fold or a column:
  // k "up" is the English, and the line read may be the row's first, its
  // own line; a text's head on the page is its own (.ftxhd, .ch).  For the
  // English shown nowhere, the row's first line, what the reader has of it.
  window.ubTrRead = function (ref, k, open) {
    var art = cmpArt(), q = ref && document.getElementById(ref), row = q && q.closest('.row');
    var tf = row && row.querySelector('.tf');
    var pick = function (root) {
      var all = root ? root.querySelectorAll('p[data-k="' + k + '"][data-ref="' + ref + '"]') : [], i;
      for (i = 0; i < all.length; i++) if (all[i].getClientRects().length) return all[i];
      return null;
    };
    var shutMine = function () {
      // With every fold open none is the reading's own to shut.
      if (trOpen) { trMine = null; return; }
      if (trMine && trMine !== tf && trMine.classList.contains('open')) trShut(trMine);
      if (trMine !== tf) trMine = null;
    };
    if (!k) {
      tf = null;
      shutMine();
      return Promise.resolve(null);
    }
    // A heading: the page's one section's (ref null), or on the whole paper's
    // page the section the ref names (listen.js isHead).
    // A head's own, its column's, or in its fold where that is open (trHeads).
    var sec = ref && ref.indexOf('.') < 0 ? q : null;
    if (art && (!ref || sec)) {
      var hs = (sec || art).querySelectorAll('header:is(.ch, .ftxhd)[data-k="' + k + '"], .tfh.open header.fhd[data-k="' + k + '"]'), h;
      for (h = 0; h < hs.length; h++) if (hs[h].getClientRects().length) return Promise.resolve(hs[h]);
      return Promise.resolve(null);
    }
    if (art && art.classList.contains('cmp')) return Promise.resolve(pick(row));
    // The row's first text, or the English shown in no fold of its own.
    var own = pick(row);
    if (own && !(tf && tf.contains(own))) { shutMine(); return Promise.resolve(own); }
    if (!tf || (k === 'up' && trKeys(tf).indexOf(k) < 0)) return Promise.resolve(k === 'up' && q && q.getClientRects().length ? q : null);
    if (tf.classList.contains('open')) {
      shutMine();
      // Its own fold, at another translation: a voice chosen anew.
      if (tf === trMine && !pick(tf))
        return trDraw(tf, trKeys(tf), k).then(function () { return pick(tf); }, function () { return null; });
      return Promise.resolve(pick(tf));
    }
    if (!open || trKeys(tf).indexOf(k) < 0) return Promise.resolve(null);
    shutMine();
    trMine = tf;
    tf.classList.add('open');
    tf.querySelector('.trfold').setAttribute('aria-expanded', 'true');
    return trDraw(tf, trKeys(tf), k).then(function () { return pick(tf); }, function () { return null; });
  };
  trSync();
  arriveTr();
  document.addEventListener('ub:page', arriveTr);
  // A change from outside a tap here: Settings' list of translations; and
  // what an exchange with the reader's account brought from another device,
  // a page shown again from the browser's cache, or Restore the defaults,
  // the folds open or shut and their tab, the line at the window's top kept.
  document.addEventListener('ub:settings', function (ev) {
    var k = ev.detail.key;
    if (k === 'translations' || k === 'english') trSync();
    if (trTap) return;
    // In columns there is no fold to draw; nor is there with every one shut.
    if (k === 'trtab' && !cmpOn() && (trOpen || document.querySelector('.tf.open'))) trKeep(trPlace(), trSync().then(trAll));
    if (k === 'tropen' && (ev.detail.all.tropen === true) !== trOpen) {
      trOpen = ev.detail.all.tropen === true;
      trTurn(trPlace());
    }
  });
  document.addEventListener('ub:swap', function () { trSync(); });
  document.addEventListener('ub:trkept', function () { trGot = {}; trSync(); cmpDraw(); });
  // Among the search results, the text's list, the English's, in its place
  // among the translations' where the English is not first (Tigran,
  // 2026-11-20: "Follow the order, hide with it"): put in their column
  // (.trhits), which takes the English's place on the page, and each stands
  // in the reader's order by the head script's rule (base.html ubTr), or
  // with the English hidden is not shown there, as an unticked one.  Not
  // with "Translations in search results" off, which hides that column, nor
  // where no translation found anything and it is not there; and back where
  // it stood when the English comes first again.  On the overview alone: a
  // list opened whole is the only one.
  var srAt = null;
  function srOrder() {
    var main = document.querySelector('main.results'), en = main && main.querySelector('section[data-tr="up"]'),
        box = main && main.querySelector('.trhits'), o = load(), up;
    if (!en || !box || main.querySelector(':scope > .hint')) return;
    up = texts().indexOf('up');
    if (up !== 0 && o.trsearch !== false) {
      if (en.parentNode === box) return;
      srAt = box.nextSibling;
      main.insertBefore(box, en);
      box.appendChild(en);
    } else if (en.parentNode === box) {
      main.insertBefore(en, box);
      main.insertBefore(box, srAt);
    }
  }
  srOrder();
  document.addEventListener('ub:swap', srOrder);
  document.addEventListener('ub:settings', function (ev) {
    if (/^(translations|english|trsearch)$/.test(ev.detail.key)) srOrder();
  });
  // A search the copy answered (sw.js) says of a translation it does not keep
  // that it is not kept (offline-core.js trList, .notkept), in a list no one
  // sees until that translation is shown.  Ticked now, online, the page is
  // asked for again once Settings closes: the worker has heard (shownTo), and
  // leaves it to the server, which lists every translation.
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key !== 'translations' || navigator.onLine === false) return;
    if (!String(ev.detail.all.translations || '').split(' ').some(function (k) {
      return k && document.querySelector('.trhits > section[data-tr="' + k + '"] > .notkept');
    })) return;
    var dlg = document.querySelector('dialog.settings[open]');
    if (dlg) dlg.addEventListener('close', function () { location.reload(); }, { once: true });
    else location.reload();
  });

  // Compare (ROADMAP item 15, step 2), the translations in parallel columns:
  // the page drawn again, the English and each translation ticked side by
  // side, a column each in the reader's order, a row to a paragraph, which
  // the grid aligns as it aligns a paragraph and its entries (ub.css
  // article.cmp).  A translation with no paragraph in the section has no
  // column.  Over the columns a line naming each, which stays at the window's
  // top while they are in view, and under it each one's own paper and section
  // titles, as its TeX sets them (/tr/'s data-head).  Drawn from the fragment
  // the folds fetch, and again whenever what it shows changes.
  //
  // Wherever the window has room for the columns, and nowhere else (Tigran,
  // 2026-11-16: "on the wide enough screen translations should be shown in
  // parallel columns anyway and on the narrow screens they should be shown
  // sequentially", and not a phone against a desktop: a tablet at a smaller
  // text may fit two, and a wide screen with the Contents and the index open
  // none).  Room is every column at least --mincol wide (cmpFits, below);
  // all of them or none; and without room the folds, as they were with the
  // setting off.  Decided again as the window, a fold of the Contents or the
  // index, a size or the typeface changes, and the page drawn in place, the
  // paragraph at the window's top kept there (cmpCheck, cmpGo).
  //
  // Until then a setting, Translations in parallel columns (`compare`,
  // 2026-11-08), under 62rem each translation under its paragraph; and before
  // it a toggle at the head of the text, at an address of its own,
  // /1:1/compare, which the tab kept as one moved about (2026-11-06); those
  // addresses go to the page's own (app.py read_compare).  The class .compare
  // hides the folds (ub.css): the head script sets it before first paint
  // where the last page read was in columns, in a window as wide (ub_cols,
  // cmpDraw), and here it is put right.  In a section none of the ticked
  // translations has, the page reads as usual.  A part's page draws nothing
  // here: every translation's divider is in the page, and the class alone
  // lays them in columns (part.html, ub.css .dividers).
  var cmpN = 0, cmpIs = null, cmpW = innerWidth;
  function cmpArt() { return document.querySelector('main.reader > article'); }
  // The texts shown that this page has, in the reader's order: the English,
  // which every page has, where it is shown, and each translation ticked that
  // has any paragraph here, or on a part's page whose divider it has.
  function cmpKeys(art) {
    var has = { up: true };
    Array.prototype.forEach.call(art.querySelectorAll('.tf[data-has]'), function (tf) {
      tf.dataset.has.split(' ').forEach(function (k) { has[k] = true; });
    });
    Array.prototype.forEach.call(art.querySelectorAll(':scope > .dividers > .divider[data-k]'), function (d) {
      has[d.dataset.k] = true;
    });
    return texts().filter(function (k) { return has[k]; });
  }
  // Whether n columns have room on this page.  What they need is the
  // stylesheet's own sum, asked of a probe put in the article for the asking
  // (ub.css .cprobe): each column its least, the gaps, and on a wide screen
  // the margin beside them where the index is shown.  What there is, is taken
  // from boxes that are the same in columns and out of them, so that the
  // answer cannot turn on itself: the window, less the frame's padding, its
  // first track and gap where it has two, which is the Contents (16rem, as
  // wide as Full makes it, or nothing folded), and the article's own padding,
  // where a folded index keeps its chevron.  Not the article's width, which
  // Measured holds to the text's.
  function cmpFits(art, n) {
    var frame = art.parentNode, fs = getComputedStyle(frame), as = getComputedStyle(art),
        tracks = fs.gridTemplateColumns.split(' '), probe = document.createElement('div'), need,
        px = function (v) { return parseFloat(v) || 0; };
    probe.className = 'cprobe';
    probe.style.setProperty('--n', n);
    art.appendChild(probe);
    need = probe.getBoundingClientRect().width;
    probe.remove();
    return frame.parentNode.clientWidth - px(fs.paddingLeft) - px(fs.paddingRight) -
           (tracks.length > 1 ? px(tracks[0]) + px(fs.columnGap) : 0) -
           px(as.paddingLeft) - px(as.paddingRight) >= need - .5;
  }
  // Decided from the page as it now is, and kept: asked before the first
  // drawing too (arriveTr, above, which runs before these lines do, so that
  // nothing is yet null).  Columns are two texts or more, each with room.
  function cmpDecide() {
    var art = cmpArt(), ks = art ? cmpKeys(art) : [];
    cmpW = innerWidth;
    return (cmpIs = ks.length > 1 && cmpFits(art, ks.length));
  }
  function cmpOn() { return cmpIs == null ? cmpDecide() : cmpIs; }

  // Each paragraph's first text (Tigran, 2026-11-20): the first of the texts
  // shown, in the reader's order, that has it, set where the English stood,
  // unfolded, the others in columns beside it or in its fold; where the
  // first of all has not the paragraph, the next that has it stands in, its
  // short name over it; and where none has it, the English, shown or not.
  // So a reader of Russian alone may put a Russian translation first, and
  // fold the English away or hide it.  The English is the server's, the
  // rest are drawn here from the section's fragment (trFetch), as the
  // columns and the folds draw them.
  //
  // The paragraph's address goes with its first text: the line drawn carries
  // it as its id, p.t as the English's does, with the reference over it,
  // and the English's line gives it up for data-ref, so that whatever finds
  // a paragraph by its address or among main p.t[id], the place being read,
  // an address arrived at, the running head, a bookmark's ribbon, the tour,
  // finds the line the reader sees.  Where the English is first, which it
  // is unless a reader moves it, nothing here is drawn.
  //
  // The English of a row, its paragraph or its block of verse as the server
  // set it, and its lines.
  function enOf(row) { return row.querySelector(':scope > p.t:not(.rt), :scope > .verse:not(.ftx)'); }
  function enLines(row) {
    var en = enOf(row);
    return !en ? [] : en.classList.contains('verse') ? Array.prototype.slice.call(en.querySelectorAll(':scope > p.t')) : [en];
  }
  function refOf(q) { return q.id || q.dataset.ref; }
  // A row's first text among `ks`: the first that has every line of the
  // row, by its section's fragment `got`, from which a translation the copy
  // does not keep is missing; the English where none has.  Without the
  // fragment, by what the page says the row has (.tf[data-has]); and once
  // drawn, what was drawn.
  function firstOf(row, ks, got) {
    var refs = enLines(row).map(refOf), tf = row.querySelector(':scope > .tf[data-has]'),
        has = tf ? tf.dataset.has.split(' ') : [], i, k;
    if (!got && row.dataset.ftx) return row.dataset.ftx;
    for (i = 0; i < ks.length; i++) {
      k = ks[i];
      if (k === 'up') return k;
      if (got ? refs.length && refs.every(function (r) { return got.t[k] && got.t[k][r] != null; }) : has.indexOf(k) >= 0) return k;
    }
    return 'up';
  }
  // Translation k set as a row's first text, after the English: its lines as
  // the English's are, each with its reference in a stack at its start, its
  // classes, and its address as its id; and its translator's notes, for
  // their cards.  The English's lines give up their ids first, so that none
  // stands twice, and the mark the page opened at goes with the address.
  // `who`: its short name over it, where it stands in for the first of all.
  function ftxPut(row, k, got, who) {
    var en = enOf(row), lines = enLines(row), x = trBy[k], h = '', notes = '',
        verse = en.classList.contains('verse');
    lines.forEach(function (q, i) {
      var ref = refOf(q), c = q.classList, w = i === 0 && who,
          cls = ['opening', 'head', 'verse', 'setoff', 'hit'].filter(function (n) { return c.contains(n); });
      h += '<p class="t rt' + (verse ? '' : ' ftx') + (cls.length ? ' ' + cls.join(' ') : '') + (w ? ' ftxw' : '') +
           '" lang="' + x.lang + '" data-k="' + k + '" data-ref="' + ref + '" id="' + ref + '"><span class="stk"><span class="num">' +
           ref + '</span>' + (w ? '<span class="ftxwho" data-who="' + x.label + '"></span>' : '') + '</span>' +
           trLead(got.t[k][ref]) + '</p>';
      notes += (got.n[k] || {})[ref] || '';
      c.remove('hit');
      q.removeAttribute('id');
      q.dataset.ref = ref;
      q.dataset.k = 'up';
    });
    en.insertAdjacentHTML('afterend', (verse ? '<div class="verse ftx" data-k="' + k + '" lang="' + x.lang + '">' + h + '</div>' : h) +
                                      (notes ? '<div class="tnotes ftx" hidden>' + notes + '</div>' : ''));
    row.dataset.ftx = k;
    return row.querySelector(':scope > .ftx');
  }
  // The English standing in, named over its first line.
  function enWho(row) {
    var q = enLines(row)[0], stk = q && q.querySelector(':scope > .stk');
    if (!stk) return;
    q.classList.add('ftxw');
    stk.insertAdjacentHTML('beforeend', '<span class="ftxwho" data-who="' + UP.label + '"></span>');
  }
  // A translation's titles, `g` its section's (/tr/'s data-head), as its TeX
  // sets them: the paper's number, title and author where `paper`, and the
  // section's title where `sect`.  The inside of a head, which the first
  // text's (ftxHead), a column's (cmpDraw) and a head's fold (trHead) each
  // put in a header of their own.
  function headInner(g, paper, sect) {
    return (paper && g.paper ? '<p class="papernum">' + g.paper + '</p>' : '') + (paper && g.title ? '<h1>' + g.title + '</h1>' : '') +
           (paper && g.author ? '<p class="author">' + g.author + '</p>' : '') + (sect && g.section ? '<h2>' + g.section + '</h2>' : '');
  }
  // A section's head in its first text, where that is a translation: the
  // paper's number, title and author over a paper's first section, and the
  // section's title, as its TeX sets them (/tr/'s data-head), in place of
  // the English's, which goes (.enoff).  `top` is the English's head.
  function ftxHead(top, k, g, paper) {
    var x = trBy[k], whole = !!top.closest('article.whole'), sect = !paper || !whole;
    top.insertAdjacentHTML('afterend', '<header class="papertop ftxhd" data-k="' + k + '" lang="' + x.lang + '">' +
      headInner(g, paper, sect) + '</header>');
    top.classList.add('enoff');
  }
  // The other texts' titles, in a fold under the head of the page and under
  // each section's own on the whole paper's (Tigran, 2026-11-21: "only the
  // first text shows the paper and section titles, the rest show only the
  // text of each paragraph"; asked, a fold as a paragraph's, opening and
  // folding with every other, at the tab chosen).  One to a section, made
  // here and not by the server, so that no stored page moves: under the
  // English's own head where the section has one (the whole paper's, after
  // the first text's beside it, ftxHead), else first in the section, under
  // the page's (a section's page, or the introduction of a whole paper).  It
  // holds whatever translations have a paragraph in the section, which are
  // those with its titles (queries.translated); and, as a row's fold, the
  // English where another text is the head's first (trKeys).  Where none is
  // ticked, the head's fold goes with the folds' line (base.html ubTr).
  function trHeads() {
    var art = cmpArt();
    if (!art) return;
    Array.prototype.forEach.call(art.querySelectorAll(':scope > section[data-trv]'), function (sec) {
      var tf = sec.querySelector(':scope > .tfh'), has = [], own;
      Array.prototype.forEach.call(sec.querySelectorAll(':scope > .grid > .row > .tf[data-has]'), function (x) {
        x.dataset.has.split(' ').forEach(function (k) { if (k && has.indexOf(k) < 0) has.push(k); });
      });
      if (!has.length) { if (tf) tf.remove(); return; }
      if (!tf) {
        tf = document.createElement('div');
        tf.className = 'tf tfh';
        tf.innerHTML = '<button class="trfold" type="button" aria-expanded="false"></button>';
        own = sec.querySelectorAll(':scope > header.papertop');
        if (own.length) own[own.length - 1].after(tf); else sec.prepend(tf);
      }
      tf.dataset.has = has.join(' ');
    });
  }
  // What a head's fold stands under: its section's own head, the English's,
  // or the page's; and whether that heads a paper, a section, or both.
  function headUnder(tf) {
    var sec = tf.parentNode, own = sec.querySelector(':scope > header.papertop:not(.ftxhd)'),
        whole = !!sec.closest('article.whole');
    return { en: own || sec.parentNode.querySelector(':scope > header.papertop:not(.ftxhd)'),
             paper: !own, sect: !!own || !whole };
  }
  // A translation's titles in a head's fold, set as a head is, smaller.
  function trHead(tf, k, g) {
    var at = headUnder(tf);
    return '<header class="fhd" data-k="' + k + '" lang="' + trBy[k].lang + '">' + headInner(g, at.paper, at.sect) + '</header>';
  }
  // The English's, from the page's own head, without its ids or marks.
  function enHead(tf) {
    var at = headUnder(tf), c = at.en && at.en.cloneNode(true);
    if (!c) return '';
    Array.prototype.forEach.call(c.querySelectorAll('[id]'), function (el) { el.removeAttribute('id'); });
    Array.prototype.forEach.call(c.querySelectorAll('.now'), function (el) { el.classList.remove('now'); });
    return '<header class="fhd" data-k="up" lang="en">' + c.innerHTML + '</header>';
  }
  // All of it taken away: the English as the server set it.
  function ftxUndraw(art) {
    if (card && card.mark.closest('.ftx')) shut(false);
    if (headP && headP.closest('.ftx')) hideHead();
    Array.prototype.forEach.call(art.querySelectorAll('.grid > .row[data-ftx]'), function (row) {
      var hit = Array.prototype.map.call(row.querySelectorAll(':scope > .ftx .hit, :scope > .ftx.hit'), function (q) { return q.id; });
      Array.prototype.forEach.call(row.querySelectorAll(':scope > .ftx'), function (el) { el.remove(); });
      enLines(row).forEach(function (q) {
        if (q.dataset.ref) { q.id = q.dataset.ref; delete q.dataset.ref; }
        delete q.dataset.k;
        if (hit.indexOf(q.id) >= 0) q.classList.add('hit');
      });
      delete row.dataset.ftx;
    });
    Array.prototype.forEach.call(art.querySelectorAll('.ftxwho, .ftxhd'), function (el) { el.remove(); });
    Array.prototype.forEach.call(art.querySelectorAll('.ftxw, .enoff'), function (el) { el.classList.remove('ftxw', 'enoff'); });
    Array.prototype.forEach.call(art.querySelectorAll('.grid > .row > :is(p.t, .verse)[style]'), function (el) {
      el.style.removeProperty('--c');
      if (!el.getAttribute('style')) el.removeAttribute('style');
    });
  }
  // Each row's first text set where it is not the English, and the English
  // let go of where it is shown in no column of its own: the folds' page,
  // `ks` the texts shown in their order, and `cols` null; in columns, the
  // texts of the columns, each its own, the first text in its column.
  // Over a run of rows in a section whose first text stands in for the
  // first of all, its short name, in the folds alone, the columns being
  // named.  A section with no fragment keeps the English.
  function ftxRows(art, secs, gots, ks, cols) {
    Array.prototype.forEach.call(secs, function (sec, j) {
      var got = gots[j], grid = sec.querySelector('.grid'), lead = texts()[0], prev = lead;
      if (!grid) return;
      Array.prototype.forEach.call(grid.children, function (row) {
        if (!row.classList.contains('row') || !enOf(row)) return;
        var first = got ? firstOf(row, cols || ks, got) : 'up', en = enOf(row), el = null,
            who = !cols && first !== lead && first !== prev;
        prev = first;
        if (first !== 'up') {
          el = ftxPut(row, first, got, who);
          if (!cols || cols.indexOf('up') < 0) en.classList.add('enoff');
        } else if (who) enWho(row);
        if (cols) {
          if (el) el.style.setProperty('--c', cols.indexOf(first) + 1);
          if (cols.indexOf('up') > 0) en.style.setProperty('--c', cols.indexOf('up') + 1);
        }
        row.dataset.ftx = first;
      });
    });
  }
  // The page's head in the first text where its first row's is a
  // translation, on the folds' page: over a section's page the paper's and
  // the section's, over the whole paper's the paper's, and each section's
  // title over its own.
  function ftxHeads(art, secs, gots) {
    Array.prototype.forEach.call(secs, function (sec, j) {
      var got = gots[j], row = sec.querySelector('.grid > .row[data-ftx]'), k = row && row.dataset.ftx,
          top = sec.querySelector(':scope > .papertop') || (j === 0 && art.querySelector(':scope > .papertop'));
      if (!got || !k || k === 'up' || !top || !got.h[k]) return;
      ftxHead(top, k, got.h[k], top.parentNode === art);
      if (j === 0 && top.parentNode !== art && art.querySelector(':scope > .papertop'))
        ftxHead(art.querySelector(':scope > .papertop'), k, got.h[k], true);
    });
  }
  // Whether a text other than the English comes first: a translation before
  // the English, or the English hidden; and then on every page of the text,
  // where the English stands in for one the page has not, named so.
  function ftxAny() { return texts()[0] !== 'up'; }
  // Painted: the English the head script held back before first paint where
  // another text comes first (base.html ubTr) is shown or let go of now.
  function ftxReady() { document.documentElement.classList.add('ftxready'); }

  function cmpUndraw(art) {
    ftxUndraw(art);
    if (!art.classList.contains('cmp')) return;
    if (card && card.mark.closest('.rc')) shut(false);
    // The running head naming a translation's paragraph goes with it, which
    // it went on naming, detached (review of 2026-11-09).
    if (headP && headP.closest('.rc') && art.contains(headP)) hideHead();
    Array.prototype.forEach.call(art.querySelectorAll('.rc p.rt.hit'), function (rt) {
      var p = document.getElementById(rt.dataset.ref);
      if (p) p.classList.add('hit');
    });
    Array.prototype.forEach.call(art.querySelectorAll('.cmpnames, .cmphd, .rc, .stars > .rs'), function (el) {
      el.remove();
    });
    Array.prototype.forEach.call(art.querySelectorAll('.blanket.cmpfold'), function (el) { el.classList.remove('cmpfold'); });
    art.classList.remove('cmp', 'cmpnoen');
    art.style.removeProperty('--cu');
    indexSync();
  }
  // Draws what the page has room for; its promise is kept once drawn.
  function cmpDraw() {
    var art = cmpArt(), on = cmpDecide(), n = ++cmpN;
    // The folds give way, or come back (ub.css :root.compare): the head
    // script guessed it before first paint, and here it follows the page,
    // once cmpGo has measured the paragraph to keep.
    document.documentElement.classList.toggle('compare', on);
    if (!art) { ftxReady(); return Promise.resolve(); }
    var ks = cmpKeys(art), secs = art.querySelectorAll('section[data-trv]');
    // The frame is told how many, which Measured makes it wide enough for
    // (ub.css --textw), once the columns are drawn, or on a part's page at
    // once.
    if (on) art.parentNode.style.setProperty('--cols', ks.length);
    else art.parentNode.style.removeProperty('--cols');
    // And the next page's first paint, how wide a window this one was in
    // columns in (base.html): a page of the text that has a translation,
    // which is what was asked about; a part's page has more room, having no
    // margin, and says nothing of the next.
    if (secs.length && ks.length > 1) try {
      if (on) localStorage.setItem('ub_cols', innerWidth); else localStorage.removeItem('ub_cols');
    } catch (e) {}
    // Not in columns, the folds: open under every paragraph where the reader
    // has them so (trAll), as the page loads, as listen.js brings one in, as
    // the columns give way in a window made narrower, and as a translation is
    // ticked.  How many it opened, for whoever places the page after.  Where
    // the English is first, nothing else is drawn; where another text is,
    // that first, once every section's fragment is had.
    if (!secs.length || (!on && !ftxAny())) {
      cmpUndraw(art);
      ftxReady();
      return trAll();
    }
    // Each section of the page in columns: the one of a section's page, or
    // every one of the whole paper's (paper.html), each with its own heads:
    // the paper's over the first, and each section's title over its own.
    // The names of the columns stand once, over them all (below).  `got` is
    // a section's /tr/ fragment, or null where it could not be had.
    var draw = function (gots) {
      if (n !== cmpN || !art.isConnected) return 0;
      cmpUndraw(art);
      // The folds' words go, so that no note's number stands twice; and with
      // them those of a fold whose texts are now others (trKeys).
      Array.prototype.forEach.call(art.querySelectorAll('.tf.open'), trShut);
      Array.prototype.forEach.call(art.querySelectorAll('.tf .tr'), function (el) { el.remove(); });
      if (!on) {
        ftxRows(art, secs, gots, ks, null);
        ftxHeads(art, secs, gots);
        bmPaint();
        ftxReady();
        // listen.js puts each first text's ▶ under its reference, as in columns.
        document.dispatchEvent(new CustomEvent('ub:cmp', { detail: art }));
        return 1;
      }
      art.classList.add('cmp');
      art.classList.toggle('cmpnoen', ks.indexOf('up') < 0);
      art.style.setProperty('--cu', ks.indexOf('up') + 1);
      // A column's name: a text's short name, the English's the press's, as
      // the rail's list of contents has them (tocSync), and no longer the
      // work's title before it, «Урантийские документы (Aivazian)» (Tigran,
      // 2026-11-15: "no need for the name of the book as it is obvious", and
      // what a translation calls itself is in Settings' Texts); and its ×,
      // which stops showing it (Tigran, 2026-11-10; below), the English's
      // too since 2026-11-20, when it became a text like the rest.
      // One row to the page, the article's own child, as the Index's button
      // is (.marginhead), so that it stays at the window's top down the whole
      // paper: a row in each section's grid stayed only while that section
      // was in view, and the next section's came up the page under it
      // (Tigran, 2026-11-15: "we keep the header showing what each column is,
      // so there is no need to print it at the end of each section").  A grid
      // of its own, with the text's tracks (ub.css article.cmp .grid).
      var names = '<div class="grid cmpnames">' + ks.map(function (k, i) {
            return '<p class="cn" style="--c:' + (i + 1) + '"><b lang="en">' + txt(k).label + '</b>' +
                   '<button type="button" class="cnx" data-k="' + k + '" ' +
                   T.a('aria-label', 'Hide this text') + ' ' + T.a('title', 'Hide this text') + '>×</button></p>';
          }).join('') + '</div>';
      art.querySelector(':scope > section').insertAdjacentHTML('beforebegin', names);
      ftxRows(art, secs, gots, ks, ks);
      Array.prototype.forEach.call(secs, function (sec, j) {
        var failed = !gots[j], got = gots[j] || { t: {}, n: {}, h: {} }, grid = sec.querySelector('.grid'),
            top = sec.querySelector(':scope > .papertop') || art.querySelector(':scope > .papertop');
        if (!grid || !top) return;
        var heads = '<div class="row cmphd">';
        ks.forEach(function (k, i) {
          if (k === 'up') return;
          var x = trBy[k], g = got.h[k] || {}, c = ' style="--c:' + (i + 1) + '"', paper = j === 0;
          heads += '<header class="papertop ch"' + c + ' data-k="' + k + '" lang="' + x.lang + '"><p class="who">' + x.label + '</p>' +
                   headInner(g, paper, true) +
                   // Every one counted is in the fragment the server sends, so one
                   // missing is offline, and not kept in the copy.
                   (got.t[k] ? '' : '<p class="gap">' + T(failed ? 'tr:unreachable' : 'tr:notkept') + '</p>') + '</header>';
        });
        grid.insertAdjacentHTML('afterbegin', heads + '</div>');
        // The section's box of what the whole paper or section cites stands
        // in the margin beside these heads (ub.css), where one of many lines
        // would put the text far under its title, 193's 27 a screen under
        // it: of five lines or more it is folded to its own line, how many
        // entries it holds, which opens it, as every box is on a phone
        // (Tigran, 2026-11-15: "let's turn them all into a fold, i.e. where
        // 5 or more lines are present", "folded by default, of course").
        var box = sec.querySelector(':scope > .blanket');
        if (box) box.classList.toggle('cmpfold', box.querySelectorAll(':scope > ul > li').length >= 5);
        if (ks.indexOf('up') >= 0) {
          var en = top.cloneNode(true);
          en.classList.add('ch');
          en.dataset.k = 'up';
          en.style.setProperty('--c', ks.indexOf('up') + 1);
          grid.querySelector('.cmphd').prepend(en);
        }
        Array.prototype.forEach.call(grid.children, function (row) {
          if (row.classList.contains('stars')) {
            row.insertAdjacentHTML('beforeend', ks.map(function (k, i) {
              return k === 'up' ? '' : '<i class="rs" style="--c:' + (i + 1) + '" data-stars="' + row.dataset.stars + '" aria-hidden="true"></i>';
            }).join(''));
            return;
          }
          var text = row.querySelector(':scope > .ftx') || enOf(row);
          if (!text || !row.classList.contains('row')) return;
          var lines = enLines(row), first = row.dataset.ftx;
          // The tnotes of the first text, which follow it, stay next to it.
          if (text.nextElementSibling && text.nextElementSibling.matches('.tnotes.ftx')) text = text.nextElementSibling;
          text.insertAdjacentHTML('afterend', ks.map(function (k, i) {
            if (k === 'up' || k === first) return '';
            var x = trBy[k], w = trLines(got, k, lines, true);
            return '<div class="rc" style="--c:' + (i + 1) + '" data-k="' + k + '" lang="' + x.lang + '">' +
                   (w.h && '<p class="who">' + x.label + '</p>' + w.h) +
                   (w.notes && '<div class="tnotes" hidden>' + w.notes + '</div>') + '</div>';
          }).join(''));
        });
      });
      indexSync();
      cmpHit();
      bmPaint();
      ftxReady();
      // listen.js puts each translation's ▶ in its cells.
      document.dispatchEvent(new CustomEvent('ub:cmp', { detail: art }));
      return 0;
    };
    return Promise.all(Array.prototype.map.call(secs, function (sec) {
      return trFetch(sec, sec.id).then(function (got) { return got; }, function () { return null; });
    })).then(function (gots) {
      var drew = draw(gots);
      if (on || n !== cmpN) return drew;
      // The folds, now that each row's first text is known (trKeys).
      return trSync().then(trAll).then(function (opened) { return drew + opened; });
    });
  }
  // A search's hit in a translation (#tr-ud, or a translator's note's,
  // templates/search.html), in columns: the paragraph marked is that
  // translation's, in its column, never the English beside it (Tigran,
  // 2026-11-08), where the column has it; where it has not, the English
  // keeps the mark.  Moved, never made, so a mark let go of stays so as the
  // columns are drawn again; and back on the English as they go (cmpUndraw).
  // The first so marked, which arrive() brings into view, or null.
  function cmpHit() {
    var m = TR_HASH.exec(location.hash), k = m && (m[1] || m[3]), art = document.querySelector('main article.cmp');
    if (!k || !art) return null;
    Array.prototype.forEach.call(art.querySelectorAll('p.t.hit'), function (p) {
      var row = p.closest('.row'), rt = row && row.querySelector('.rc[data-k="' + k + '"] p.rt[data-ref="' + p.id + '"]');
      if (!rt) return;
      p.classList.remove('hit');
      rt.classList.add('hit');
    });
    return art.querySelector('.rc p.rt.hit');
  }
  // The place being read, kept as the page is drawn again, in columns or out
  // of them: the line at the window's top, by the letter there, or a
  // paragraph marked on the screen, as a fold of the Contents or the index
  // keeps it (placeNow, placeBack), since it is such a fold, or the window
  // made wider, that now turns the page into columns, in the middle of a
  // paragraph as often as not (2026-11-16); `kept` is the place such a fold
  // took before it changed anything (keepPlace).  Until then the paragraph
  // at the window's top was put there from its start, which was enough for
  // a switch in Settings.  A line that stood where the columns' names now
  // stand is brought out from under them; a mark in a translation's column,
  // which goes with the column, is kept by the English beside it, and so is
  // a line in a fold, which goes as the columns come; and at the page's top
  // the page stays there.
  function cmpGo(kept) {
    var pl = kept || placeNow(), cell = pl && pl.el.closest('.rc, .tf'), row = cell && pl.el.closest('.row'), en = row && row.querySelector('p.t[id]'),
        enAt = en && placeAlt({ el: en, y: en.getBoundingClientRect().top });
    // A column's cell goes whatever is drawn; a fold's line only as the
    // columns come, and where the page stays in folds it keeps the place
    // itself, or its fold's own line does (placeAlt).
    if (enAt && cell.classList.contains('rc')) pl = enAt;
    return cmpDraw().then(function () {
      var names = document.querySelector('article.cmp .cmpnames'), floor = names ? names.offsetHeight + 2 : 0, t = Date.now();
      if (enAt && cmpIs) pl = enAt;
      if (!pl) return;
      if (pl.y < floor) pl.y = floor;
      placeBack(pl);
      // And held there while the page settles (placeHold).
      placeHold(pl, t);
    });
  }
  // The line at the window's top, kept in the page's entry in the history as
  // the reader moves the page and as the page is left (2026-11-20), for when
  // it is loaded again from that entry: by Back or Forward where the
  // browser's page cache has not kept it whole, by a reload, or a phone's tab
  // put back after the browser let it go.  The browser puts the page back
  // where it stood, but by its height as first drawn, before the folds open
  // under every paragraph (trAll) or the columns are drawn, and then keeps
  // whatever that height shows: on a phone with the folds open, three
  // paragraphs on (measured in Chrome that day: 101:4.3 came back as
  // 101:4.6).  So the line is kept by what it is, a paragraph or a
  // translation's line in a fold, and how high it stood, and put back once
  // the page is drawn (cmpArrive, below).  Where nothing is drawn late the
  // browser's own is right, and nothing is done.  Not listen.js's own entries,
  // which keep a place of their own.
  var RE_AT = /^\d+:\d+\.\d+$/, atWait = 0;
  function atNow() {
    if (scrollY <= 0) return { top: true };
    var ps = document.querySelectorAll('main :is(p.t[id], .tf.open p.rt[data-ref])'), r;
    for (var i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > 4) return { ref: ps[i].id || ps[i].dataset.ref, k: ps[i].id ? '' : ps[i].dataset.k, y: r.top };
    }
    return null;
  }
  function atKeep() {
    clearTimeout(atWait);
    atWait = 0;
    if (!document.querySelector('main.reader article p.t[id]')) return;
    try { history.replaceState(Object.assign({}, history.state, { ubAt: atNow() }), ''); } catch (e) {}
  }
  addEventListener('scroll', function () { if (!atWait) atWait = setTimeout(atKeep, 400); }, { passive: true });
  addEventListener('pagehide', atKeep);
  document.addEventListener('visibilitychange', function () { if (document.hidden) atKeep(); });
  // True where the page is loaded again from its entry, and is put back.
  function atBack() {
    var s = history.state && history.state.ubAt, el = null, pl,
        nav = window.performance && performance.getEntriesByType ? performance.getEntriesByType('navigation')[0] : null;
    if (!s || !nav || !/^(back_forward|reload)$/.test(nav.type)) return false;
    if (s.top) { scrollTo({ top: 0, behavior: 'instant' }); return true; }
    if (!RE_AT.test(s.ref || '') || typeof s.y !== 'number') return false;
    if (s.k && /^[a-z0-9-]+$/.test(s.k)) el = document.querySelector('main .tf.open p.rt[data-k="' + s.k + '"][data-ref="' + s.ref + '"]');
    el = el || document.getElementById(s.ref);
    if (!el) return false;
    pl = { el: el, y: s.y };
    placeBack(pl);
    placeHold(pl, Date.now());
    return true;
  }
  // Opened with it on: drawn, then the paragraph cited brought into view
  // again, as the rows have changed height, unless the reader has
  // scrolled meanwhile (by hand: the fonts coming in move the page too, and
  // the whole paper's columns take a while); and a translator's note's card
  // opened from its column.
  function cmpArrive() {
    var t = Date.now();
    cmpDraw().then(function (opened) {
      // Not in columns, the class the head script guessed is gone, and the
      // page is where arrive() put it; unless the folds opened under every
      // paragraph, which moved it as the columns do (Continue reading, a
      // reference followed: the paragraph come to, under the folds above it).
      if (!cmpIs && !opened) return;
      // Loaded again from its entry, where it stood (atBack, above).
      if (arriveTouched <= t && !atBack()) arrive(true);
      if (card) place();
      var m = /^#note(tn_[a-z0-9-]+_\d+_\d+_\d+_\d+)$/.exec(location.hash),
          mark = m && document.getElementById('fnref' + m[1]);
      if (!mark || !mark.closest('.rc')) return;
      shut(false);
      open(mark);
    });
  }
  cmpArrive();
  // A page listen.js swaps in is drawn in columns too, and once drawn, which
  // moves the paragraph cited as the rows grow, arrived at again, as
  // cmpArrive does for a page loaded: arrive() ran on ub:page before the
  // columns were there (review of 2026-11-09).
  var cmpSwapped = null;
  document.addEventListener('ub:swap', function () { cmpSwapped = cmpDraw(); });
  document.addEventListener('ub:page', function () {
    var drawn = cmpSwapped, t = Date.now();
    cmpSwapped = null;
    if (drawn) drawn.then(function (opened) { if ((cmpIs || opened) && arriveTouched <= t) arrive(true); });
  });
  // A column's ×, at its name's corner, takes that translation out of those
  // shown, as Settings' Translations does, and the columns are drawn again
  // without it, the place kept (below); a copy kept offline keeps it.  On the
  // document, since listen.js swaps <main>.
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('article.cmp .cmpnames .cnx'), order;
    if (!b) return;
    order = texts().filter(function (k) { return k !== b.dataset.k; });
    if (order.length) window.ubSettings.setAll(textsOf(order));
  });
  // Asked again when what the room rests on has changed, and the page drawn
  // again only where the answer has: in place, the paragraph at the window's
  // top kept (cmpGo).
  function cmpCheck(kept) {
    var was = cmpIs;
    if (cmpDecide() !== was) cmpGo(kept);
  }
  // Once for all the settings, where ↺ announces every setting in turn: a
  // second cmpGo measured the page the first had just undrawn, and undid the
  // place it kept (review of 2026-11-09).  The list of translations draws
  // the page again whatever the answer, its columns being other columns; a
  // setting the room rests on, the folds of the Contents and the index, the
  // index itself, the two sizes, the width and the typeface, only where the
  // answer changes.
  var cmpSoon = false, cmpMust = false,
      CMP_ROOM = { rail: 1, margin: 1, index: 1, size: 1, uisize: 1, width: 1, face: 1 };
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'translations' || ev.detail.key === 'english') cmpMust = true;
    else if (!CMP_ROOM.hasOwnProperty(ev.detail.key)) return;
    if (cmpSoon) return;
    cmpSoon = true;
    // The place a fold's button took before it changed the setting.
    var kept = placeKept;
    Promise.resolve().then(function () {
      var must = cmpMust;
      cmpSoon = cmpMust = false;
      if (must) cmpGo(kept); else cmpCheck(kept);
    });
  });
  // The window: as it is made wider or narrower, or a tablet turned, once a
  // frame; not as it grows taller, which is all a phone's address bar going
  // away is.  The typeface come in, in whose characters a column's least is
  // counted.  And a page come back to from the history, in a window that may
  // have changed since.
  var cmpTick = 0;
  addEventListener('resize', function () {
    if (innerWidth === cmpW || cmpTick) return;
    cmpTick = requestAnimationFrame(function () { cmpTick = 0; cmpCheck(null); });
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (cmpIs != null) cmpCheck(null); });
  addEventListener('pageshow', function (ev) { if (ev.persisted) cmpCheck(null); });

  // ---- The Bible's texts (Tigran, 2026-11-21: the Synodal "in parallel
  // columns with KJV and generally treated the same way as we do the Urantia
  // Book's texts (folding, ordering, offline, etc)") ----------------------------
  // A chapter's page (templates/bible_chapter.html) is a list of rows,
  // .krow, each the verses of the KJV and the Synodal that are the same
  // words, and carries each row's base line, the KJV's where the row has one,
  // else the Synodal's; the Synodal's lines for the rest are the fragment,
  // /bible/tr/<Abbr>/<c> (bibFetch).  The texts shown, in the reader's order,
  // are `bible` (settings.py): each row's first that it has stands where the
  // base line stood, carrying the row's id; the rest stand in columns beside
  // it where the window has room for them all (cmpFits, the book's own
  // measure), and in a fold under it where it has not, a tap on any fold
  // opening or folding them all, the book's folds' one state (`tropen`).
  // Where none of those shown has a row, the line that has it stands in, the
  // KJV's named (.bstand), the Synodal's runs named by the page (.bwho).  Its
  // own names, all `bib`, for ub.js is one function (trap 42).  The book's
  // drawing (cmpDraw, trAll) finds nothing of these and leaves them alone.
  var bibArt = document.querySelector('main.reader.bible > article.biblech'), BIB = [], bibBy = {},
      bibGot = null, bibCols = null, bibBase = null, bibW = innerWidth, bibHeadMark = null;
  try { BIB = JSON.parse((document.getElementById('ub-bible') || {}).textContent || '[]'); } catch (e) {}
  BIB.forEach(function (x) { bibBy[x.key] = x; });
  function bibTexts() {
    var ks = String(load().bible || 'kjv').split(' ').filter(function (k) { return bibBy[k]; });
    return ks.length ? ks : ['kjv'];
  }
  // The rows, each with its base lines kept as the page drew them, once.
  function bibRows() {
    if (bibBase) return bibBase;
    bibBase = Array.prototype.map.call(bibArt.querySelectorAll('.kverses > .krow'), function (row) {
      var lines = Array.prototype.filter.call(row.children, function (el) { return el.dataset.k && !el.matches('.btf'); });
      return { row: row, id: row.dataset.row, k: lines.length ? lines[0].dataset.k : 'kjv', lines: lines,
               ka: row.querySelector(':scope > .ka'), tf: row.querySelector(':scope > .btf'),
               who: row.querySelector(':scope > .bwho'), mark: row.querySelector('a.fn[data-k="kc"]') };
    });
    return bibBase;
  }
  // The other version's lines, by row, and its head and notes; null where the
  // page has none to fetch or it cannot be had (offline, not kept).
  function bibFetch() {
    var v = bibArt.dataset.trv;
    if (!v) return Promise.resolve(null);
    if (!bibGot) {
      bibGot = fetch('/bible/tr/' + bibArt.dataset.abbr + '/' + bibArt.dataset.c + '?v=' + encodeURIComponent(v))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (h) {
          var t = document.createElement('template'), got = { rows: {}, notes: {}, head: null };
          t.innerHTML = h;
          Array.prototype.forEach.call(t.content.querySelectorAll('.brt[data-row]'), function (d) {
            got.rows[d.dataset.row] = Array.prototype.slice.call(d.children);
          });
          Array.prototype.forEach.call(t.content.querySelectorAll('aside[data-of]'), function (d) {
            (got.notes[d.dataset.of] = got.notes[d.dataset.of] || []).push(d);
          });
          got.head = t.content.querySelector('.bhd[data-k]');
          got.headNote = t.content.querySelector('.btrs > aside.note:not([data-of])');
          return got;
        });
      bibGot.catch(function () { bibGot = null; });
    }
    return bibGot.catch(function () { return null; });
  }
  // The versions this page has, in the reader's order: a base line's, and
  // the fragment's where the page names one (data-has).
  function bibShown() {
    var has = {};
    bibRows().forEach(function (r) { has[r.k] = true; });
    (bibArt.dataset.has || '').split(' ').forEach(function (k) { if (k) has[k] = true; });
    return bibTexts().filter(function (k) { return has[k]; });
  }
  function bibKeep(change) {
    // The row at the window's top, kept where it stands (a fold's opening or
    // the columns' drawing moves every row below it).
    var top = null, at = 0;
    bibRows().some(function (r) {
      var b = r.row.getBoundingClientRect();
      if (b.bottom > 0) { top = r.row; at = b.top; return true; }
      return false;
    });
    return Promise.resolve(change()).then(function () {
      if (top && top.getBoundingClientRect().top !== at && scrollY > 0)
        scrollBy(0, top.getBoundingClientRect().top - at);
    });
  }
  // A version's lines for a row, fresh: the base's are the page's own, the
  // other's clones of the fragment's.
  function bibLines(r, k, got) {
    if (k === r.k) return r.lines;
    return got && got.rows[r.id] ? got.rows[r.id].map(function (el) { return el.cloneNode(true); }) : [];
  }
  function bibNotes(r, got) {
    if (!got || !got.notes[r.id]) return null;
    var d = document.createElement('div');
    d.className = 'tnotes';
    d.hidden = true;
    got.notes[r.id].forEach(function (a) { d.appendChild(a.cloneNode(true)); });
    return d;
  }
  // The row's id on its first line shown, which arrive(), the running head
  // and the place find it by; a line that gives it up keeps it in data-rid.
  function bibId(r, first) {
    var hit = r.lines.some(function (el) { return el.classList.contains('hit'); });
    r.row.querySelectorAll('[id="' + r.id + '"]').forEach(function (el) { if (el !== first) { el.dataset.rid = r.id; el.removeAttribute('id'); } });
    if (first) first.id = r.id;
    // The tint of a verse the address names goes with it (as ftxPut's .hit).
    r.row.querySelectorAll('[data-drawn].hit, .bc .hit').forEach(function (el) { if (el !== first) el.classList.remove('hit'); });
    if (first && hit) first.classList.add('hit');
  }
  function bibDraw() {
    if (!bibArt) return Promise.resolve();
    var ks = bibShown(), cols = ks.length > 1 && cmpFits(bibArt, ks.length), want = ks.indexOf('rsb') >= 0;
    bibCols = cols;
    bibW = innerWidth;
    return (want ? bibFetch() : Promise.resolve(null)).then(function (got) {
      var main = bibArt.parentNode, top = bibArt.querySelector('.kjvtop'), heads, names;
      bibArt.classList.toggle('bcmp', !!cols);
      if (cols) main.style.setProperty('--cols', ks.length); else main.style.removeProperty('--cols');
      // The heads: the base's the page's, the other's the fragment's.
      heads = top.querySelector('.bhds');
      if (!heads) {
        heads = document.createElement('div');
        heads.className = 'bhds';
        top.querySelector('.bhd').before(heads);
        heads.appendChild(top.querySelector('.bhd'));
        if (got && got.head) {
          heads.appendChild(got.head.cloneNode(true));
          if (got.headNote) heads.appendChild(got.headNote.cloneNode(true));
        }
      } else if (got && got.head && !heads.querySelector('.bhd[data-k="rsb"]')) {
        heads.appendChild(got.head.cloneNode(true));
        if (got.headNote) heads.appendChild(got.headNote.cloneNode(true));
      }
      var hk = Array.prototype.map.call(heads.querySelectorAll('.bhd[data-k]'), function (h) { return h.dataset.k; }),
          hfirst = ks.filter(function (k) { return hk.indexOf(k) >= 0; })[0] || hk[0];
      Array.prototype.forEach.call(heads.querySelectorAll('.bhd[data-k]'), function (h) {
        var i = ks.indexOf(h.dataset.k);
        h.style.setProperty('--c', i + 1);
        h.hidden = cols ? i < 0 : h.dataset.k !== hfirst;
        h.style.order = i < 0 ? 9 : i;
      });
      heads.style.display = cols ? '' : 'block';
      // The line naming the columns, at the window's top, each name with its
      // ×, which stops showing that text, as the book's columns have (Tigran,
      // 2026-11-21: "where are the crosses to hide a text column, like for
      // UB?"; below).
      names = bibArt.querySelector('.bnames');
      if (names) names.remove();
      if (cols) {
        names = document.createElement('div');
        names.className = 'krow bnames';
        names.innerHTML = ks.map(function (k, i) {
          return '<p class="cn" style="--c:' + (i + 1) + '"><b lang="' + bibBy[k].lang + '">' + bibBy[k].label + '</b>' +
                 '<button type="button" class="bnx" data-k="' + k + '" ' +
                 T.a('aria-label', 'Hide this text') + ' ' + T.a('title', 'Hide this text') + '>×</button></p>';
        }).join('');
        bibArt.querySelector('.kverses').prepend(names);
      }
      bibRows().forEach(function (r) {
        var row = r.row, has = {}, mine = [], first;
        // Undrawn: every cell and every drawn line out, the base's lines back.
        Array.prototype.forEach.call(row.querySelectorAll(':scope > .bc, :scope > [data-drawn]'), function (el) { el.remove(); });
        if (r.tf) { var p = r.tf.querySelector('.tr'); if (p) p.remove(); }
        r.lines.forEach(function (el) { el.classList.remove('bstand'); el.removeAttribute('data-who'); row.insertBefore(el, r.ka || r.tf || null); });
        ['kjv', 'rsb'].forEach(function (k) { if (k === r.k || (got && got.rows[r.id])) has[k] = true; });
        ks.forEach(function (k) { if (has[k]) mine.push(k); });
        first = mine[0] || r.k;
        r.mine = mine;
        r.first = first;
        if (cols) {
          ks.forEach(function (k, i) {
            var cell = document.createElement('div'), ls = has[k] ? bibLines(r, k, got) : [];
            cell.className = 'bc';
            cell.dataset.k = k;
            cell.style.setProperty('--c', i + 1);
            ls.forEach(function (el) { cell.appendChild(el); });
            if (k !== r.k) { var n = bibNotes(r, got); if (n) cell.appendChild(n); }
            row.insertBefore(cell, r.ka || r.tf || null);
          });
          // The base's lines a column the reader does not show: out.
          if (ks.indexOf(r.k) < 0) r.lines.forEach(function (el) { el.remove(); });
          bibId(r, row.querySelector('.bc [data-ref]'));
        } else {
          // The first text in the base line's place, the base's lines out
          // where it is another's.
          if (first !== r.k) {
            r.lines.forEach(function (el) { el.remove(); });
            bibLines(r, first, got).forEach(function (el) {
              el.dataset.drawn = '1';
              row.insertBefore(el, r.ka || r.tf || null);
            });
            var n = bibNotes(r, got);
            if (n) { n.dataset.drawn = '1'; row.insertBefore(n, r.ka || r.tf || null); }
          }
          // A KJV line standing in where the reader's first is another, named.
          var lead = row.querySelector(':scope > p.kv[data-k], :scope > p.kvh[data-k]');
          if (lead && first === 'kjv' && ks[0] !== 'kjv') {
            lead.classList.add('bstand');
            lead.dataset.who = bibBy.kjv.label;
          }
          bibId(r, lead);
        }
      });
      // The orange dot of a verse the study notes cite, at the end of the
      // row's first text shown, whichever it is (bible_chapter.html), and a
      // chapter's at its first head's.
      bibRows().forEach(function (r) {
        if (!r.mark) return;
        // In columns the first cell with a verse, the cells being in the
        // reader's order; else the row's own lines, the first text's.
        var cell = cols ? Array.prototype.filter.call(r.row.querySelectorAll(':scope > .bc'), function (c) {
              return c.querySelector(':scope > p.kv'); })[0] : r.row,
            ls = cell ? cell.querySelectorAll(':scope > p.kv') : [];
        if (ls.length) ls[ls.length - 1].appendChild(r.mark);
      });
      if (bibHeadMark === null) bibHeadMark = top.querySelector('a.fn[data-k="kc"]') || false;
      if (bibHeadMark) {
        var h1 = heads.querySelector('.bhd[data-k="' + hfirst + '"] h1') || heads.querySelector('.bhd h1');
        if (h1) h1.appendChild(bibHeadMark);
      }
      bibFolds(got);
      document.documentElement.classList.add('bibready');
    });
  }
  // The folds: each row's other texts shown, under it, open or shut with all
  // the rest (trOpen); in columns none.
  function bibFolds(got) {
    var ks = bibShown();
    bibRows().forEach(function (r) {
      var tf = r.tf, b = tf && tf.querySelector('.bfold'), others, panel;
      if (!tf) return;
      others = (r.mine || []).filter(function (k) { return k !== r.first; });
      tf.hidden = !others.length || !!bibCols;
      if (tf.hidden) return;
      b.textContent = others.map(function (k) { return bibBy[k].label; }).join(', ');
      b.setAttribute('aria-expanded', trOpen ? 'true' : 'false');
      panel = tf.querySelector('.tr');
      // Shut with the rest, but for the one an address opened (#tr-rsb).
      var open = trOpen || tf.dataset.one === '1';
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (!open) { if (panel) panel.hidden = true; return; }
      if (!panel) { panel = document.createElement('div'); panel.className = 'tr'; tf.appendChild(panel); }
      panel.hidden = false;
      panel.innerHTML = '';
      others.forEach(function (k) {
        // Each named where the fold holds more than one, as the book's are.
        if (others.length > 1) {
          var who = document.createElement('p');
          who.className = 'who';
          who.textContent = bibBy[k].label;
          panel.appendChild(who);
        }
        bibLines(r, k, got).forEach(function (el) {
          var c = el === r.lines[0] || r.lines.indexOf(el) >= 0 ? el.cloneNode(true) : el;
          c.removeAttribute('id');
          panel.appendChild(c);
        });
        if (k !== r.k) { var n = bibNotes(r, got); if (n) panel.appendChild(n); }
      });
    });
    ks = null;
  }
  if (bibArt) {
    // A search's hit in the Synodal, or its numbers typed in the search box,
    // arrive at /bible/Psa/23:1#tr-rsb: the row's fold opened at it, where
    // the Synodal is no first text and the page is in folds.
    if (location.hash === '#tr-rsb') {
      var hitRow = bibArt.querySelector('.krow:has(> .hit)'), hitTf = hitRow && hitRow.querySelector(':scope > .btf');
      if (hitTf) hitTf.dataset.one = '1';
    }
    bibDraw();
    // A column's ×: that text out of those shown, as Settings' Texts takes
    // it out, and the page drawn again without it (ub:settings, below).
    bibArt.addEventListener('click', function (ev) {
      var x = ev.target.closest && ev.target.closest('.bnames .bnx');
      if (!x) return;
      var order = bibTexts().filter(function (k) { return k !== x.dataset.k; });
      if (order.length) window.ubSettings.set('bible', order.join(' '));
    });
    bibArt.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('.bfold');
      if (!b) return;
      ev.preventDefault();
      var want = b.getAttribute('aria-expanded') !== 'true';
      Array.prototype.forEach.call(bibArt.querySelectorAll('.btf[data-one]'), function (x) { delete x.dataset.one; });
      trOpen = want;
      trTap = true;
      try { window.ubSettings.set('tropen', want); } finally { trTap = false; }
      bibKeep(function () { return bibFetch().then(bibFolds); });
    });
    document.addEventListener('ub:settings', function (ev) {
      var k = ev.detail.key;
      if (k === 'bible') return void bibKeep(bibDraw);
      if (k === 'tropen' && (ev.detail.all.tropen === true) !== trOpen) {
        trOpen = ev.detail.all.tropen === true;
        bibKeep(function () { return bibFetch().then(bibFolds); });
      }
      if ((k === 'margin' || k === 'index' || k === 'width' || k === 'uisize' || k === 'size') && bibShown().length > 1 &&
          (bibShown().length > 1 && cmpFits(bibArt, bibShown().length)) !== bibCols) bibKeep(bibDraw);
    });
    var bibTick = 0;
    addEventListener('resize', function () {
      if (innerWidth === bibW || bibTick) return;
      bibTick = requestAnimationFrame(function () {
        bibTick = 0;
        var n = bibShown().length;
        if ((n > 1 && cmpFits(bibArt, n)) !== bibCols) bibKeep(bibDraw);
      });
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      var n = bibShown().length;
      if ((n > 1 && cmpFits(bibArt, n)) !== bibCols) bibKeep(bibDraw);
    });
  }
  // Part I is open in the Foreword's rail for the Foreword's sake (templates/
  // _rail.html), and its line of script shuts it where Settings puts the
  // Foreword before the parts; a rail swapped in runs no script.
  function railForeword() {
    var d = document.querySelector('.rail li.fwhere > details');
    if (d && document.documentElement.dataset.foreword === 'off') d.removeAttribute('open');
  }
  function swapped() { railSync(); indexSync(); railForeword(); }
  document.addEventListener('ub:swap', swapped);
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'margin')
      Array.prototype.forEach.call(document.querySelectorAll('.afold'), function (x) {
        x.parentNode.classList.remove('shown');
      });
    swapped();
  });

  // The interface in English or Russian (ubsite/l10n.py).  Its words are in
  // the page in both, and CSS shows the reader's; an attribute cannot hold
  // both, so the Russian stands beside it, data-ru-<name>, and here it is put
  // in place, the English kept as data-en-<name> and put back for English.  A
  // title's place is data-tip while Tooltips are off (below).  An <option>'s
  // words and the tab's title have theirs in data-ru.  The book's own marks
  // carry their labels in the stored text (build/render.py), so theirs are
  // found here by what they are: a pilcrow's title, a 1955 ring's and a study
  // note's name.  Run on the whole page at load and when the language
  // changes, and on whatever is added to it after (watch).
  var NAMES = ['title', 'aria-label', 'placeholder'], each = Array.prototype.forEach;
  var MARKS = [['.pcm', 'title', function () { return T.tr('a new group begins here, as in the 1955 printing'); }],
               ['a.fn[data-k="1955"]', 'aria-label', function () { return T.tr('1955 reading'); }],
               ['a.fn[data-k="st"]', 'aria-label', function (el) { return T.tr('Note {n}', { n: +el.dataset.n }); }],
               ['a.fn[data-k="tn"]', 'aria-label', function (el) { return T.tr('Note {n}', { n: +el.dataset.n }); }]];
  var SPOKEN = NAMES.map(function (n) { return '[data-ru-' + n + ']'; }).concat('option[data-ru]').join(',');
  function within(root, sel) {
    var out = Array.prototype.slice.call(root.querySelectorAll(sel));
    if (root.matches && root.matches(sel)) out.unshift(root);
    return out;
  }
  function speak(root) {
    if (!T.bilingual) return;
    var ru = T.lang() === 'ru';
    MARKS.forEach(function (m) {
      each.call(within(root, m[0] + ':not([data-ru-' + m[1] + '])'), function (el) {
        el.setAttribute('data-ru-' + m[1], T.plain(m[2](el).ru));
      });
    });
    each.call(within(root, SPOKEN), function (el) {
      if (el.tagName === 'OPTION') {
        if (!el.hasAttribute('data-en')) el.setAttribute('data-en', el.text);
        el.text = el.getAttribute(ru ? 'data-ru' : 'data-en');
        return;
      }
      NAMES.forEach(function (n) {
        var to = el.getAttribute('data-ru-' + n);
        if (to === null) return;
        var at = n === 'title' && !el.hasAttribute('title') && el.hasAttribute('data-tip') ? 'data-tip' : n;
        if (!el.hasAttribute('data-en-' + n)) el.setAttribute('data-en-' + n, el.getAttribute(at) || '');
        el.setAttribute(at, ru ? to : el.getAttribute('data-en-' + n));
      });
    });
    if (root === document && window.ubTitle) window.ubTitle();
  }
  // Tooltips off (Settings): the browser draws one from a title, and no
  // stylesheet can hide it, so every title on the page is moved to data-tip,
  // where none is drawn, and back when they are turned on.  Every icon keeps
  // its aria-label, so nothing goes unnamed.
  function untip(el) {
    if (!el.hasAttribute('title')) return;
    el.setAttribute('data-tip', el.getAttribute('title'));
    el.removeAttribute('title');
  }
  function tips() {
    var r = document.documentElement;
    if (load().tips === false) each.call(r.querySelectorAll('[title]'), untip);
    else each.call(r.querySelectorAll('[data-tip]'), function (el) {
      el.setAttribute('title', el.getAttribute('data-tip'));
      el.removeAttribute('data-tip');
    });
    watching();
  }
  // What is added to the page later is spoken and untipped as it comes: the
  // player's controls, a <main> listen.js swaps in, a paper the rail fetches,
  // a note's card, the Offline tab's words; and a title set later is moved
  // to data-tip, the folds' as they change.  Watched only
  // while there is something to do: both languages drawn, or Tooltips off.
  var watch = null;
  function watching() {
    var off = load().tips === false, need = T.bilingual || off, r = document.documentElement;
    if (!need || !window.MutationObserver) {
      if (watch) { watch.disconnect(); watch = null; }
      return;
    }
    if (watch) return;
    watch = new MutationObserver(function (ms) {
      var off = load().tips === false;
      ms.forEach(function (m) {
        if (m.type === 'attributes') { if (off) untip(m.target); return; }
        each.call(m.addedNodes, function (n) {
          if (n.nodeType !== 1) return;
          speak(n);
          if (off) { untip(n); each.call(n.querySelectorAll('[title]'), untip); }
        });
      });
    });
    watch.observe(r, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
  }
  speak(document);
  tips();
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'tips') tips();
    if (ev.detail.key === 'lang') { speak(document); flags(); }
  });

  // The list of languages at the header's corner (base.html .langmenu;
  // Tigran, 2026-11-21, where two flags stood from 2026-10-25): the interface
  // in English or in Russian, kept as the setting 'lang' (settings.py KEPT).
  // Closed it shows the flag of the language in effect, which the stylesheet
  // draws; open, the one in effect is pressed.  An item chosen shuts it.
  // Shown only while the site draws both.
  var langMenu = document.querySelector('.top .langmenu');
  function flags() {
    if (!langMenu) return;
    var now = T.lang();
    each.call(langMenu.querySelectorAll('.langitems button'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.to === now));
    });
  }
  if (langMenu && T.bilingual) {
    langMenu.hidden = false;
    flags();
    menuShuts(langMenu);
    langMenu.querySelector('.langitems').addEventListener('click', function (ev) {
      var b = ev.target.closest('button[data-to]');
      if (!b) return;
      langMenu.open = false;
      window.ubSettings.set('lang', b.dataset.to);
    });
  }
  // On a phone (ub.css, under 40rem) the controls stand beside the name
  // where they fit: where they would take the controls to a line of their
  // own, the line is first drawn closer (.tight), and then one thing after
  // another is left out, Settings doing what each does: the account's mark
  // (.noacct; 2026-11-18), the language (.nolang; the flags from 2026-11-17
  // until the list, 2026-11-21, and on no phone from 2026-11-10 until
  // then), the half-disc of light or dark (.notheme; back on 2026-11-18, and
  // not to make a header of two lines one of three), and last full screen
  // (.nofull; 2026-11-21, "especially useful on the phone").  Where the gear
  // and the ? alone do not fit beside the name, the controls have a line of
  // their own, and everything stands on it.  Asked again as the window, the
  // language, a size or the typeface changes, as full screen comes or goes,
  // and as each face comes in: the Cyrillic one is fetched only when a page
  // turned into Russian first asks for it, and the line measured in the face
  // standing in for it, wider, had left the language out at 430 px at
  // Largest, where it fits (found 2026-11-21).  Measured with nothing
  // painted between, so nothing is seen to move.
  var ctlTop = document.querySelector('.top'), ctlName = ctlTop && ctlTop.querySelector('.brand'),
      ctlBox = ctlTop && ctlTop.querySelector('.ctl'), ctlPhone = matchMedia('(max-width: 40rem)'),
      CTL_OUT = ['noacct', 'nolang', 'notheme', 'nofull'];
  var ctlFit = function () {
    if (!ctlName || !ctlBox) return;
    var below = function () { return ctlBox.getBoundingClientRect().top >= ctlName.getBoundingClientRect().bottom - 1; },
        all = ['tight'].concat(CTL_OUT), i;
    // The account's mark gives way first, the language never to it (Tigran,
    // 2026-11-18, of the flags: "so that the flags are always there, in all
    // combinations"); Settings' foot says who is signed in, and leads to the
    // account.  On a line of their own the controls have room again.
    DOMTokenList.prototype.remove.apply(ctlTop.classList, all);
    if (!ctlPhone.matches || !below()) return;
    ctlTop.classList.add('tight');
    for (i = 0; i < CTL_OUT.length; i++) {
      if (!below()) return;
      ctlTop.classList.add(CTL_OUT[i]);
    }
    if (below()) DOMTokenList.prototype.remove.apply(ctlTop.classList, all);
  };
  ctlFit();
  addEventListener('resize', ctlFit);
  document.addEventListener('ub:settings', ctlFit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(ctlFit);
  if (document.fonts && document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', ctlFit);

  // A 1955 reading opens as a card at its ring (ub.css .pop), carrying its
  // endnote's words (section.html), which are hidden while this runs, and a
  // study note at its number the same way, its card .st, and a translator's
  // in a fold, .tn, its words hidden there with its paragraph's.  One
  // card at a time, under the line and scrolling with it; the ring again, its
  // ×, Escape or a click elsewhere closes it.  Listened for on the document,
  // so it holds after listen.js swaps <main>.
  var card = null;
  function shut(back) {
    if (!card) return;
    card.el.remove();
    card.mark.classList.remove('on');
    card.mark.setAttribute('aria-expanded', 'false');
    if (back) card.mark.focus();
    card = null;
  }
  function place() {
    if (!card) return;
    var H = card.host.getBoundingClientRect(), M = card.mark.getBoundingClientRect();
    var x = M.left + M.width / 2 - H.left;
    var left = Math.min(Math.max(x - 36, 8), H.width - card.el.offsetWidth - 8);
    card.el.style.left = left + 'px';
    card.el.style.top = (M.bottom - H.top + 6) + 'px';
    card.el.querySelector('.arrow').style.left = (x - left - 6) + 'px';
  }
  // A finger's drag on a card is the card's (Tigran, 2026-11-12: on his phone,
  // dragging on past the end of a long note moved the text under it).  The
  // words are held by overscroll-behavior (ub.css .pop .body), which Chrome
  // honours wherever it was tried, but the strip above them, the ×'s, is not
  // part of what scrolls, and a drag begun there moved the page.  So a
  // stroke's first move decides it, once: where the words can scroll that way
  // the browser has the stroke, as ever; where they cannot, at their end, in
  // a card too short to scroll, or on the strip, the stroke is cancelled, and
  // being no scroll at all it passes to nothing, whatever the browser makes
  // of the stylesheet.  Two fingers are the browser's, a pinch, and so is a
  // stroke while words are selected, a long press and its drag.  On the card
  // alone, never the document: no other touch on the page waits for script.
  function popTouch(el) {
    var body = el.querySelector('.body'), x0 = 0, y0 = 0, mine = null;
    el.addEventListener('touchstart', function (ev) {
      x0 = ev.touches[0].clientX; y0 = ev.touches[0].clientY; mine = null;
    }, { passive: true });
    el.addEventListener('touchmove', function (ev) {
      var t = ev.touches[0], dx = t.clientX - x0, dy = t.clientY - y0;
      if (ev.touches.length > 1 || !getSelection().isCollapsed) return;
      if (mine === null) {
        if (!dx && !dy) return;
        mine = body.contains(ev.target) && (Math.abs(dy) >= Math.abs(dx)
          ? (dy > 0 ? body.scrollTop > 1 : body.scrollHeight - body.clientHeight - body.scrollTop > 1)
          : (dx > 0 ? body.scrollLeft > 1 : body.scrollWidth - body.clientWidth - body.scrollLeft > 1));
      }
      if (!mine && ev.cancelable) ev.preventDefault();
    }, { passive: false });
  }
  function open(mark) {
    var note = document.getElementById(mark.getAttribute('href').slice(1)),
        host = mark.closest('article') || mark.closest('main.results');
    if (!note || !host) return false;
    var el = document.createElement('div');
    el.className = { st: 'pop st', tn: 'pop tn' }[mark.dataset.k] || 'pop';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', mark.getAttribute('aria-label') || T.text('1955 reading'));
    el.tabIndex = -1;
    if (note.dataset.k) el.dataset.tr = note.dataset.k;   // a translator's: which (pvLink)
    el.innerHTML = '<span class="arrow"></span>' +
      '<button type="button" class="x" ' + T.a('aria-label', 'Close') + '>×</button>' +
      '<div class="body">' + note.innerHTML + '</div>';
    host.appendChild(el);
    popTouch(el);
    card = { mark: mark, el: el, host: host };
    mark.classList.add('on');
    mark.setAttribute('aria-expanded', 'true');
    place();
    el.focus({ preventScroll: true });
  }
  document.addEventListener('click', function (ev) {
    var t = ev.target, mark = t.closest && t.closest('a.fn'), num = t.closest && t.closest(NUM);
    if (mark) {
      var again = card && card.mark === mark;
      hideHead();
      shut(false);
      if (again || open(mark) !== false) ev.preventDefault();
      return;
    }
    // A paragraph's reference copies its link (copyLink, below), and is no tap
    // on the text: the running head stays as it was.  Not a second click,
    // which selects the reference, for Ctrl+X, nor the end of a drag.
    if (num && bmRef(num.closest('p.t'))) {
      if (ev.button || ev.detail > 1 || !getSelection().isCollapsed) return;
      if (card) shut(false);
      copyLink(bmRef(num.closest('p.t')), num);
      return;
    }
    if (!card) { tapHead(ev); return; }
    if (card.el.contains(t)) { if (t.closest('.x')) shut(true); return; }
    shut(false);
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    // A card, else the list of bookmarks, else the running head and its bar.
    if (card) shut(true); else if (bmSheet && !bmSheet.hidden) bmShut(true); else hideHead();
  });
  window.addEventListener('resize', place);
  document.addEventListener('ub:swap', function () { card = null; });

  // Paragraph previews (settings.py `preview`; Tigran, 2026-11-07, for
  // checking the study notes' references on a desktop).  With the switch on,
  // a link to a paragraph of the book, /12:4.14 or /15:2.3-8, wherever it
  // stands (a note's card or endnote, a 1955 card, an index entry, a search
  // result), shows the paragraph itself in a card of the notes' kind where
  // the pointer rests, and on a touch a tap shows it instead of going there,
  // the reference at the card's head going.  The paragraph is lifted from its
  // section's page, this one where the section is on it, else fetched once
  // and kept, which offline the worker answers from the copy; its number,
  // 1955 page, pilcrow, note numbers and rings go, so a preview carries the
  // words alone and opens nothing further.  One at a time, over any note card
  // that is open, which stays.  A range is shown whole, the card scrolling
  // (Tigran, 2026-11-11: 30:4.1-8, the seven stages of the ascent, stopped at
  // the fifth; six paragraphs at most until then, with "…" at the head).
  // The address is read in both its forms, /30:4.1-8 as the server writes it
  // and /30#30:4.1-8 as ubUnit makes it with Whole paper on: the Whole paper
  // handler, above, has the click first and rewrites the link, so that until
  // 2026-11-12 a tap with Whole paper on found no paragraph in it and went
  // there (Tigran, on his phone), and a reference once followed never showed
  // its preview under the pointer again.
  var PV = /^\/(\d+)(?::|#\1:)(\d+)\.(\d+)(?:-(\d+))?$/, pv = null, pvSeq = 0, pvTimer = 0, pvHide = 0, pvPages = {};
  // A verse of the King James Version, or a run of them (build/bibleref.py
  // makes a study note's references so, 2026-11-21): the verses in the card,
  // from the chapter's page.  A chapter alone, /bible/Psa/23, has none.
  var PVK = /^\/bible\/([1-3]?[A-Z][a-z]{1,2})\/(\d+):(\d+)(?:-(\d+))?$/;
  function pvOn() { return document.documentElement.dataset.preview === 'true'; }
  function pvLink(t) {
    var a = t && t.closest && t.closest('a[href]'), m, c;
    // Not the bar at the foot's (base.html .fbar): Continue reading and a
    // bookmark's row are ways to a place, not references in a text, and a
    // card for one, drawn in the page under the window's foot, made the page
    // taller, so that a scrollbar came and went as the pointer crossed the
    // bar and the page jumped sideways (Tigran, 2026-11-17, with Paragraph
    // previews on); and on a phone a tap there would have shown the card
    // and gone nowhere.
    // Nor the home page's passage of the moment (home.html .fpass): its
    // reference is the way to the paragraph whose words are already shown.
    if (!a || a.closest('.pop.pv, .fbar, .fpass')) return null;
    m = PV.exec(a.getAttribute('href') || '');
    if (!m) {
      m = PVK.exec(a.getAttribute('href') || '');
      return m && { a: a, kjv: m[1], c: m[2], n: +m[3], last: m[4] ? +m[4] : +m[3], tr: '' };
    }
    // In a translator's note's card, or a translation's cell: that translation's
    // paragraph (Tigran, 2026-11-07: a reader of a translation expects it).
    // The English, "up", where it is folded or listed among the texts
    // (2026-11-20), is the English's paragraph, as everywhere else.
    c = a.closest('[data-tr], p.rt[data-k]');
    c = c ? c.dataset.tr || c.dataset.k : '';
    return { a: a, p: m[1], s: m[2], n: +m[3], last: m[4] ? +m[4] : +m[3], tr: c === 'up' ? '' : c };
  }
  function pvPage(p, s) {
    if (document.getElementById(p + ':' + s + '.1')) return Promise.resolve(document);
    return pvFetch('/' + p + ':' + s);
  }
  // A page, fetched once, parsed: offline the worker answers from the copy.
  function pvFetch(url) {
    if (!pvPages[url]) pvPages[url] = fetch(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return r.text();
    }).then(function (h) { return new DOMParser().parseFromString(h, 'text/html'); })
      .catch(function (e) { delete pvPages[url]; throw e; });
    return pvPages[url];
  }
  function pvParas(doc, r) {
    var out = [], n, p;
    for (n = r.n; n <= r.last; n++) {
      // The English's line, whichever text is first on this page and has
      // the address as its id (ftxPut).
      p = doc.getElementById(r.p + ':' + r.s + '.' + n);
      if (p && p.classList.contains('rt')) p = doc.querySelector('p.t:not(.rt)[data-ref="' + p.id + '"]');
      if (!p) break;
      p = p.cloneNode(true);
      p.removeAttribute('id');
      p.className = p.classList.contains('verse') ? 'verse' : '';
      Array.prototype.forEach.call(p.querySelectorAll('.stk, .pcm, a.fn'), function (x) { x.remove(); });
      out.push(p);
    }
    return out;
  }
  // A chapter's verses, from its page (templates/bible_chapter.html): each
  // KJV p.kv, without its number and its note's mark; with the book's name as
  // the page has it, for the card's head.  The KJV's, as a preview of the
  // book's paragraphs is the English's, whatever the reader shows.
  function pvVerses(doc, r) {
    var out = [], n, p, book = doc.querySelector('.kup a[href^="/bible/"]:last-child');
    for (n = r.n; n <= r.last; n++) {
      p = doc.getElementById('v' + n);
      if (!p || !p.classList.contains('kv') || p.dataset.k !== 'kjv') break;
      p = p.cloneNode(true);
      p.removeAttribute('id');
      p.className = '';
      Array.prototype.forEach.call(p.querySelectorAll('.vn, a.fn'), function (x) { x.remove(); });
      out.push(p);
    }
    // The breadcrumb names the book in both languages (x-en, x-ru: trap 33);
    // the card is the KJV's, and names it in English.
    book = book && (book.querySelector('x-en') || book);
    return { ps: out, tr: '', name: book ? book.textContent : r.kjv };
  }
  // A translation's words for the paragraphs, each with its language, as far
  // as it has them from the first; none where it lacks the first, and the
  // English stands in.
  function pvTrParas(got, r) {
    var out = [], n, h, p;
    for (n = r.n; n <= r.last; n++) {
      h = (got.t[r.tr] || {})[r.p + ':' + r.s + '.' + n];
      if (h == null) break;
      p = document.createElement('p');
      p.lang = trBy[r.tr].lang;
      p.innerHTML = h;
      Array.prototype.forEach.call(p.querySelectorAll('a.fn'), function (x) { x.remove(); });
      out.push(p);
    }
    return out;
  }
  // More than one: each begins with its number in its section, small and
  // raised, as a verse's in a Bible (Tigran, 2026-11-11, once a range was
  // shown whole); drawn from data-n (ub.css .pvn), as the pilcrow is drawn,
  // so that copying the words never takes a number along.  They run from the
  // first, pvParas and pvTrParas stopping at the first one missing.
  function pvNumber(ps, r) {
    if (ps.length > 1) ps.forEach(function (p, i) {
      var s = document.createElement('sup');
      s.className = 'pvn';
      s.dataset.n = r.n + i;
      p.insertBefore(s, p.firstChild);
    });
    return ps;
  }
  function pvShut() {
    clearTimeout(pvTimer); clearTimeout(pvHide); pvTimer = pvHide = 0; pvSeq++;
    if (pv) { pv.el.remove(); pv = null; }
  }
  function pvPlace() {
    if (!pv) return;
    var H = pv.host.getBoundingClientRect(), M = pv.a.getBoundingClientRect(),
        x = M.left + M.width / 2 - H.left,
        left = Math.min(Math.max(x - 36, 8), H.width - pv.el.offsetWidth - 8);
    pv.el.style.left = left + 'px';
    pv.el.style.top = (M.bottom - H.top + 6) + 'px';
    pv.el.querySelector('.arrow').style.left = (x - left - 6) + 'px';
  }
  function pvOpen(r, byTouch) {
    pvShut();
    var seq = pvSeq, ref = r.kjv ? '' : r.p + ':' + r.s + '.' + r.n + (r.last > r.n ? '-' + r.last : ''),
        href = r.kjv ? '/bible/' + r.kjv + '/' + r.c + ':' + r.n + (r.last > r.n ? '-' + r.last : '') : '/' + ref,
        sec = !r.kjv && document.querySelector('section[id="' + r.p + ':' + r.s + '"]'),
        words = r.tr && trBy[r.tr]
          ? trFetch(sec, r.p + ':' + r.s).then(function (got) { return pvTrParas(got, r); }, function () { return []; })
          : Promise.resolve([]);
    (r.kjv ? pvFetch('/bible/' + r.kjv + '/' + r.c).then(function (doc) { return pvVerses(doc, r); })
     : words.then(function (ps) {
      if (ps.length) return { ps: ps, tr: r.tr };
      return pvPage(r.p, r.s).then(function (doc) { return { ps: pvParas(doc, r), tr: '' }; });
    })).then(function (got) {
      if (seq !== pvSeq || !document.contains(r.a)) return;
      // A verse's reference as the KJV's page names its book: Isaiah 40:22.
      if (r.kjv) ref = got.name + ' ' + r.c + ':' + r.n + (r.last > r.n ? '–' + r.last : '');
      var ps = pvNumber(got.ps, r), host, el, body;
      if (!ps.length) return;
      host = r.a.closest('article') || r.a.closest('main.results') || document.body;
      el = document.createElement('div');
      el.className = 'pop pv';
      el.setAttribute('role', 'dialog');
      el.setAttribute('aria-label', ref);
      el.tabIndex = -1;
      el.innerHTML = '<span class="arrow"></span>' +
        '<button type="button" class="x" ' + T.a('aria-label', 'Close') + '>×</button>' +
        '<div class="body"><p class="pvref"><a href="' + href + '">' + ref + '</a>' +
        (got.tr ? ' <span class="pvtr">' + trBy[got.tr].label + '</span>' : '') + '</p></div>';
      body = el.querySelector('.body');
      ps.forEach(function (p) { body.appendChild(p); });
      host.appendChild(el);
      popTouch(el);
      pv = { a: r.a, el: el, host: host, touch: byTouch };
      pvPlace();
      if (byTouch) el.focus({ preventScroll: true });
    }).catch(function () {});
  }
  function pvHideSoon() {
    clearTimeout(pvHide);
    pvHide = setTimeout(function () { if (pv && !pv.touch) pvShut(); }, 300);
  }
  // A mouse's rest: 350 ms on the link; off it, or off the card, 300 ms more,
  // so that the card can be crossed into and scrolled.  A finger's or a pen's
  // pointerover is a tap's, which the click below takes.
  document.addEventListener('pointerover', function (ev) {
    if (ev.pointerType !== 'mouse' || !pvOn()) return;
    var r = pvLink(ev.target);
    if (pv && (pv.el.contains(ev.target) || (r && r.a === pv.a))) { clearTimeout(pvHide); return; }
    if (!r) return;
    clearTimeout(pvTimer);
    pvTimer = setTimeout(function () { if (pvOn()) pvOpen(r, false); }, 350);
  });
  document.addEventListener('pointerout', function (ev) {
    if (ev.pointerType !== 'mouse') return;
    var r = pvLink(ev.target), to = ev.relatedTarget;
    if (r && !(to && r.a.contains(to))) clearTimeout(pvTimer);
    if (!pv || pv.touch) return;
    if ((pv.el.contains(ev.target) && !(to && pv.el.contains(to))) ||
        (r && r.a === pv.a && !(to && r.a.contains(to)))) pvHideSoon();
  });
  // A tap (touch, as pointerdown set it): the card instead of the page, which
  // the reference at its head reaches; the same tap again, a tap elsewhere,
  // its × or Escape closes it.  In the capture phase, before the cards' own
  // handler, so that a tap elsewhere closes the preview alone and a note card
  // under it stays.
  document.addEventListener('click', function (ev) {
    if (!pvOn()) return;
    var t = ev.target, r;
    if (pv && pv.el.contains(t)) { if (t.closest('.x')) pvShut(); return; }
    r = pvLink(t);
    if (r && touch && !ev.button && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey && !ev.altKey) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      if (pv && pv.a === r.a) pvShut(); else pvOpen(r, true);
      return;
    }
    if (pv && pv.touch) { pvShut(); ev.stopImmediatePropagation(); if (!t.closest('a[href]')) ev.preventDefault(); }
  }, true);
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && pv) { pvShut(); ev.stopImmediatePropagation(); }
  }, true);
  window.addEventListener('resize', pvPlace);
  document.addEventListener('ub:swap', pvShut);
  document.addEventListener('ub:settings', function (ev) { if (ev.detail.key === 'preview' && !pvOn()) pvShut(); });

  // Turning the page (Tigran, 2026-10-20).  A phone's volume keys never reach a
  // web page: Chrome keeps them for the system (ContentUiEventHandler's
  // shouldPropagateKeyEvent), and Safari has no such event.  So where the
  // book's text is, Space, Page Down and → go on a screen, and Shift+Space,
  // Page Up and ← back: from a keyboard, a page turner, or volume keys an
  // Android app sends as Page Down.  A tap never turns it: Settings' "Tap to
  // turn the page", which made a tap on the lower half of the screen go on
  // and one on the upper half back, is gone since 2026-11-17 (Tigran), a tap
  // on a paragraph being what names it, for the running head and the bar at
  // the foot (tapHead, below).  A screen is what the window shows, less a
  // line: the last whole line comes to the top, and going back, the first
  // whole line to the bottom, so that no line the reader picks up at is cut.
  var EDGE = 6, touch = false, selDown = false;
  // The line of text crossing y, as the box of one of its letters, or null.
  function lineAt(x, y) {
    var c = document.caretPositionFromPoint ? document.caretPositionFromPoint(x, y) : null,
        n, at, q = document.createRange(), i, j, rs;
    if (c) { n = c.offsetNode; at = c.offset; }
    else if (document.caretRangeFromPoint && (c = document.caretRangeFromPoint(x, y))) {
      n = c.startContainer; at = c.startOffset;
    }
    if (!n || n.nodeType !== 3 || !n.length) return null;
    // The letter after the caret, or at a line's end the one before it.
    for (j = Math.min(at, n.length - 1); j >= Math.max(0, Math.min(at, n.length) - 1); j--) {
      q.setStart(n, j);
      q.setEnd(n, j + 1);
      rs = q.getClientRects();
      for (i = 0; i < rs.length; i++) if (rs[i].height && rs[i].top <= y && y <= rs[i].bottom) return rs[i];
    }
    return null;
  }
  // The first line wholly between lo and hi, looking from y by step: past the
  // space between paragraphs, and past a line cut at the edge.
  function whole(x, y, step, lo, hi) {
    for (var k = 0, L; k < 80 && y >= lo - 1 && y <= hi + 1; k++) {
      L = lineAt(x, y);
      if (L && L.top >= lo - 1 && L.bottom <= hi + 1) return L;
      y = L ? (step < 0 ? L.top - 1 : L.bottom + 1) : y + step;
    }
    return null;
  }
  function turn(dir) {
    var col = document.querySelector('main :is(p.t, p.kv)[id]'), pl = document.querySelector('.player'),
        lo = EDGE, hi = innerHeight - EDGE, x, L, d;
    if (!col) return false;
    // Not under the player, while it is open.
    if (pl && pl.offsetParent) hi = Math.min(hi, pl.getBoundingClientRect().top - EDGE);
    x = col.getBoundingClientRect();
    x = x.left + x.width / 2;
    L = dir > 0 ? whole(x, hi, -4, lo, hi) : whole(x, lo, 4, lo, hi);
    d = L ? (dir > 0 ? L.top - lo : L.bottom - hi) : 0;
    // No line to keep, or one so near that the page would hardly move: most of
    // a screen, as the browser goes.
    if (d * dir < (hi - lo) / 3) d = dir * (hi - lo) * .9;
    scrollBy({ top: d, behavior: 'instant' });
    // Back, a line cut at the top goes, so that the first line is whole.
    if (dir < 0 && (L = lineAt(x, lo)) && L.top < lo - 1) scrollBy({ top: L.bottom + 1 - lo, behavior: 'instant' });
    return true;
  }
  document.addEventListener('keydown', function (ev) {
    var k = ev.key, t = ev.target, dir;
    if (ev.defaultPrevented || ev.altKey || ev.ctrlKey || ev.metaKey) return;
    dir = k === 'PageDown' || (k === 'ArrowRight' && !ev.shiftKey) || (k === ' ' && !ev.shiftKey) ? 1
        : k === 'PageUp' || (k === 'ArrowLeft' && !ev.shiftKey) || (k === ' ' && ev.shiftKey) ? -1 : 0;
    if (!dir || (t.closest && t.closest('input, textarea, select, button, summary, [contenteditable], dialog, [popover], .pop, .player'))) return;
    if (turn(dir)) ev.preventDefault();
  });
  // Home goes to the home page, from any page (Tigran, 2026-11-20: "We have
  // Ctl+Home and Ctl+End go to the top and to the bottom of the page
  // respectively. So, why not map Home button to go to the home page? It
  // should work even on the mobile, if there is a keyboard connected").
  // Ctrl+Home stays the browser's, to the page's top, and so does Home on the
  // home page itself.  By the header's own link, clicked: so the key does
  // what a click on the mark does, and while a recording plays listen.js
  // swaps the home page in and the reading goes on.  Not in a field, where
  // Home moves the caret, nor in a row of tabs, a menu or a dialog, whose own
  // key it is (Settings' tabs, the changelog's, which take it first).
  document.addEventListener('keydown', function (ev) {
    var t = ev.target, a;
    if (ev.key !== 'Home' || ev.defaultPrevented || ev.repeat ||
        ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey ||
        document.querySelector('dialog[open], main.front') ||
        (t.closest && t.closest('input, textarea, select, [contenteditable], [role="tablist"], [role="menu"], [role="listbox"], [popover], .pop, .player'))) return;
    ev.preventDefault();
    a = document.querySelector('header a.brand');
    if (a) a.click(); else location.assign('/');
  });
  // Only a finger's tap, or a pen's: a mouse's click selects words.  And the
  // selection as it stood before the tap, which the browser clears before the
  // tap's click (tapHead, below).
  document.addEventListener('pointerdown', function (ev) {
    touch = ev.pointerType !== 'mouse';
    selDown = !getSelection().isCollapsed;
  }, { passive: true });
  // In a translations' fold, and not on a paragraph of a translation there:
  // on its tabs, a name, a note's card or the room about them, where a tap is
  // no tap on the text.
  function inFold(t) { return !!t.closest('.tf') && !t.closest('.tf p.rt'); }
  // The running head on demand (Tigran, 2026-10-31).  Reading on a phone, the
  // whole paper on one page and the paragraph references off, the header a
  // paper up the page, a reader had no way to Settings, to the reference of
  // the paragraph in hand, or to the paper's name.  The book gives all three
  // in its running heads: the first paragraph on the page at the outer corner,
  // the author centred on a verso, PAPER 101 – THE REAL NATURE OF RELIGION on
  // a recto.  So a tap on the text brings the running head down over the top
  // of the window (ub.css .runhead): the tapped paragraph's reference, the
  // paper's number and title, and its author, and the gear; since 2026-11-01
  // Home beside the gear, and the reference a button to the Contents
  // (toContents, above).  Not a link to the paragraph, as the one beside it
  // once was: a tap on that would only mark it as the page's opening place
  // (Tigran, 2026-10-31).  The paragraph is tinted as a
  // search hit is (p.t.named) rather than given its reference in its place, a
  // float that would re-set its first two lines under the finger.  The next
  // tap takes it away, as do Escape, a card opening, Settings opening, a new
  // page, a turn of the window, and two lines of scrolling, so that it never
  // covers the text while reading.  Never a tap while words
  // are selected: the long press is the system's, with its Copy and Web
  // search, and since the browser clears the selection before the tap's
  // click, it is read at pointerdown (selDown, above).  Built here from what
  // the page carries, on <body>, which listen.js never swaps.
  var head = null, headP = null, headAt = 0, headSlack = 56;
  function clampY() {
    return Math.max(0, Math.min(scrollY, document.documentElement.scrollHeight - innerHeight));
  }
  // The paragraph tapped.  In columns a translation's own (p.rt), tinted
  // alone, never the English beside it (Tigran, 2026-11-08), and its cell's
  // first where the tap was in the cell but on none, on its name; the English
  // one of the row where it was on neither.  And a translation's own in the
  // fold under a paragraph, which is how a phone shows one (Tigran,
  // 2026-11-17: "on the phone tapping a translation's paragraph does
  // nothing, but on the desktop it highlights it and displays the page
  // header menu, just like for English"): the fold was no place for a tap at
  // all, its tabs and names being controls (inFold, above).  And where the tap was on no
  // paragraph's row, on a section's title or in the room about it, the next
  // paragraph down the page from where it fell (`y`, the tap's height in the
  // window), which under a title is its section's first, and under a
  // translation's title in columns that translation's: never the first on
  // the screen, which above a title is a paragraph of the section before
  // (Tigran, 2026-11-15: "clicking on the section title highlights one of
  // the paragraphs of the previous section").  In columns that paragraph is
  // the one of the column the tap fell in (`x`, its place across the window;
  // paraCol): in the room between two sections, above a translation's title
  // or over the paper's head, and in a row beside or above a cell, it named
  // the English one whichever column it was in (Tigran, 2026-11-18: "selects
  // the following English paragraph, even when clicked above Russian section
  // title").
  function paraOf(t, y, x) {
    var cell, row;
    if (!t.closest) return null;
    return t.closest('p.t[id], p.t[data-ref], .rc p.rt, .tf p.rt, p.kv[id], p.kv[data-ref]') ||
           ((cell = t.closest('.rc')) && cell.querySelector('p.rt')) ||
           paraCol((row = t.closest('.grid > .row')) && row.querySelector('p.t[id]'), x) || paraUnder(t, y, x);
  }
  function paraUnder(t, y, x) {
    var ch = t.closest('.cmphd > .ch[data-k]'), sec = ch && ch.closest('section'),
        own = sec && sec.querySelector('.rc[data-k="' + ch.dataset.k + '"] p.rt'), ps, i, r;
    if (own) return own;
    if (!(y >= 0)) return null;
    ps = document.querySelectorAll('main :is(p.t, p.kv)[id]');
    for (i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > y) return paraCol(ps[i], x);
    }
    return null;
  }
  // In columns, the paragraph `p` (the row's line with the id, its first
  // text's) as the column `x` is in has it: the column x is across, or in
  // the nearer half of the room before it, measured left to right, a row
  // being a subgrid whose own column-gap says nothing, whichever text stands
  // there, the English too since it may stand anywhere (2026-11-20); a
  // verse's line by its reference; else `p` itself, for the margin past the
  // last column, a column that has not the paragraph, and a page not in
  // columns.
  function paraCol(p, x) {
    var row = p && p.closest('article.cmp .grid > .row'), cols, edge = 0, at = null, i, r, ref;
    if (!row || !(x >= 0)) return p;
    ref = refOf(p);
    cols = Array.prototype.filter.call(row.querySelectorAll(':scope > :is(p.t, .verse, .rc[data-k])'), function (c) {
      return c.getBoundingClientRect().width;
    }).sort(function (a, b) { return a.getBoundingClientRect().left - b.getBoundingClientRect().left; });
    for (i = 0; i < cols.length; i++) {
      r = cols[i].getBoundingClientRect();
      if (!i || x >= (edge + r.left) / 2) at = cols[i];
      edge = r.right;
    }
    if (!at || x >= edge) return p;
    if (at.matches('p.t')) return at;
    return at.querySelector('p[data-ref="' + ref + '"], p[id="' + ref + '"]') || at.querySelector('p.rt, p.t') || p;
  }
  // The first paragraph on the screen: a verso's running head.
  function firstOnScreen() {
    var ps = document.querySelectorAll('main :is(p.t, p.kv)[id]'), r;
    for (var i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      // Or the one before, its translations open at the window's top (foldOver).
      if (r.height && r.bottom > 0) return foldOver(ps[i - 1], 0) || ps[i];
    }
    return ps[0] || null;
  }
  // The paper's title for a paragraph: where a translation is its first
  // text, the line with its address, the translation's, as the page draws
  // its head (ftxHead) or in columns (2026-11-20: Continue reading and a
  // bookmark name the paper in the text read first); else the English's, as
  // it was for a translation's line in a fold or a column.
  function titleOf(p) {
    var k = p && p.id && p.dataset.k, h = k && k !== 'up' &&
            document.querySelector('main article :is(header.ftxhd, header.ch)[data-k="' + k + '"] h1');
    return h ? h.textContent : headOf(p).title;
  }
  // The paper's head for a paragraph: the article's own, with the title (the
  // whole paper's sections have heads of their own, each the section's title
  // alone), or on a reading path the running head before the paragraph, which
  // names the paper and its title and no author.
  function headOf(p) {
    var top = document.querySelector('main article > header.papertop'), rhs, rh = null, i,
        bible = p && p.classList && p.classList.contains('kv') && p.closest('article[data-book]');
    // A verse of the Bible: its book's name in its version's language
    // (templates/bible_chapter.html).
    if (bible) return { num: '', title: p.dataset.k === 'rsb' && bible.dataset.bookRu || bible.dataset.book, author: '' };
    if (top && top.querySelector('h1')) {
      // The number in a <b>, as a translation's is (headTr): the dash before
      // the title is drawn only after an element (ub.css .runhead .tt), and
      // the book's PAPER 101 is words alone since it stopped being the
      // interface's x-en and x-ru (2026-11-22).
      return { num: top.querySelector('.papernum') ? '<b>' + top.querySelector('.papernum').innerHTML + '</b>' : '',
               title: top.querySelector('h1').textContent,
               author: top.querySelector('.author') ? top.querySelector('.author').textContent : '' };
    }
    rhs = document.querySelectorAll('main .rh-paper');
    for (i = 0; i < rhs.length; i++)
      if (rhs[i].compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING) rh = rhs[i];
    return { num: rh ? rh.innerHTML : '', title: '', author: '' };
  }
  function buildHead() {
    var ref, ctl, home, btn, logo = document.querySelector('.brand .logo');
    head = document.createElement('div');
    head.className = 'runhead';
    head.hidden = true;
    head.setAttribute('role', 'region');
    T.attr(head, 'aria-label', 'Running head');
    head.innerHTML = '<div class="mid"><p class="pn"></p><p class="au"></p></div>';
    // The reference, a button to the Contents (toContents, above; Tigran,
    // 2026-11-01), with the Contents' chevron after it (ub.css); its name is
    // the reference itself.
    ref = document.createElement('button');
    ref.type = 'button';
    ref.className = 'ref';
    T.attr(ref, 'title', 'Show in the contents');
    // A paragraph is kept for Back by its row's line with the id, its first
    // text's (ftxPut); the Contents open in the text tapped, the English's
    // where the English is not first.
    ref.addEventListener('click', function () {
      var p = headP;
      hideHead();
      toContents(p && (p.id ? p : document.getElementById(p.dataset.ref)), p && p.dataset.k || '');
    });
    head.insertBefore(ref, head.firstChild);
    // The gear and Home together at the right: the gear first, as it is the
    // first of the header's controls (Tigran, 2026-11-17: "normally the
    // Settings icon is the leftmost in the top panel, but when I tap on the
    // paragraph it is displayed rightmost.  Let's make it leftmost at all
    // times"; the mark stood before it until then); and the site's mark, the
    // header's own drawing, as a link to the home page.
    ctl = document.createElement('span');
    ctl.className = 'ctl';
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'set';
    T.attr(btn, 'aria-label', 'Settings');
    T.attr(btn, 'title', 'Settings');
    if (gear && gear.querySelector('svg')) btn.appendChild(gear.querySelector('svg').cloneNode(true));
    ctl.appendChild(btn);
    home = document.createElement('a');
    home.className = 'home';
    home.href = '/';
    T.attr(home, 'title', 'Home');
    T.attr(home, 'aria-label', 'Home');
    if (logo) home.appendChild(logo.cloneNode(true));
    ctl.appendChild(home);
    head.appendChild(ctl);
    // The header's gear opens the dialog, and its click hides the head (below);
    // never focused first, or the dialog would give the focus back to the
    // header on closing and scroll a long page to its top.
    btn.addEventListener('click', function () { if (gear) gear.click(); else hideHead(); });
    head.addEventListener('click', function (ev) { if (!ev.target.closest('a, button')) hideHead(); });
    document.body.appendChild(head);
  }
  // The head's words: the paper's number, as HTML, its title and its author,
  // in `lang` where they are a translation's.
  function headSay(h, lang) {
    var mid = head.querySelector('.mid');
    if (lang) mid.lang = lang; else mid.removeAttribute('lang');
    head.querySelector('.pn').innerHTML = h.num + '<span class="tt"></span>';
    head.querySelector('.tt').textContent = h.title;
    head.querySelector('.au').textContent = h.author;
  }
  // A translation's paragraph has the paper's head as that translation has
  // it, ТЕКСТ 101 – ПОДЛИННАЯ СУЩНОСТЬ РЕЛИГИИ and its author, never the
  // English (Tigran, 2026-11-17: "the page header is from English even on the
  // Russian text -- that is a bug too"): from the section's /tr/ fragment,
  // which the paragraph itself was drawn from (trFetch, its promise kept, so
  // the words are there before the head is painted); what the translation
  // has not, a number over its Foreword or the Foundation's author, is not
  // put in from the English.  Empty until then, and the English only where
  // the fragment cannot be had.
  function headTr(p) {
    var k = p.dataset.k, sec = p.closest('section[data-trv]'), en = headOf(p);
    var text = function (html) { var d = document.createElement('div'); d.innerHTML = html || ''; return d.textContent; };
    headSay({ num: '', title: '', author: '' }, trBy[k] && trBy[k].lang);
    trFetch(sec, p.dataset.ref.split('.')[0]).then(function (got) {
      var g = got.h[k];
      if (headP !== p) return;
      if (!g) return headSay(en);
      // The number in an element of its own, as the English's is (headOf):
      // the dash before the title is drawn where one comes before it (ub.css
      // .runhead .tt).
      headSay({ num: g.paper ? '<b>' + g.paper + '</b>' : '', title: text(g.title), author: text(g.author) },
              trBy[k] && trBy[k].lang);
    }, function () { if (headP === p) headSay(en); });
  }
  function showHead(p) {
    if (!p) return;
    if (!head) buildHead();
    if (headP) headP.classList.remove('named');
    headP = p;
    p.classList.add('named');
    // A verse's reference as its version numbers it, 1:4, the Synodal's 22:1
    // on the KJV's Psalm 23 (data-ref); a title's, its chapter.
    head.querySelector('.ref').textContent = p.classList.contains('kv')
      ? (p.dataset.ref || '').replace(/:0$/, '') : p.id || p.dataset.ref;
    if (p.dataset.k && p.dataset.k !== 'up' && p.dataset.ref && !p.classList.contains('kv')) headTr(p);
    else headSay(headOf(p));
    head.hidden = false;
    headAt = clampY();
    headSlack = 2 * (parseFloat(getComputedStyle(p).lineHeight) || 28);
    // A tap is a touch of the page: arrive()'s late scroll must not undo it.
    arriveTouched = Date.now();
    // The Contents mark its section, on the whole paper's page (railMarkOf,
    // above).
    railMarkOf(p);
    // And the bar at the foot, with Bookmark this paragraph (barUp, below),
    // which a verse of the Bible is not.
    if (!p.classList.contains('kv')) barUp();
  }
  function hideHead() {
    clearTimeout(headSoon);
    headSoon = 0;
    if (headP) headP.classList.remove('named');
    headP = null;
    if (head) head.hidden = true;
    barDown();
  }
  // The tour's (help.js): the head shown for a paragraph at once, as a tap
  // shows it, and hidden.  Not by a click the tour makes, which a mouse's DBL
  // holds back since 2026-11-08: the step lit the paragraph, and the head came
  // after, unlit, and could stay over the next step (review of 2026-11-09).
  window.ubHead = {
    show: function (p) {
      clearTimeout(headSoon);
      headSoon = 0;
      unhit();
      showHead(p || firstOnScreen());
      headBy = Date.now();
    },
    hide: hideHead
  };
  // A tap on the text also lets go of the paragraph the page opened at
  // (p.t.hit: the server's mark on a section's page, arrive()'s on the whole
  // paper's), which stayed tinted beside the one named and had no other way
  // to be let go of (Tigran, 2026-10-31), as listen.js lets go of it when
  // playing starts: one thing on the page is marked.  Since 2026-11-19 it goes
  // by itself too (hitLater, above), whose count and fade end here.
  function unhit() {
    clearTimeout(hitTimer);
    hitTimer = 0;
    hitWaits = false;
    Array.prototype.forEach.call(document.querySelectorAll(HIT + ', .hitgo'), function (p) { p.classList.remove('hit', 'hitgo'); });
  }
  // True when the tap was the head's: to show it, or to hide it.  Not a
  // mouse's second click, a double-click; a finger's quick second tap, which
  // Chrome counts the same, is the tap that hides it.  A mouse's click hides
  // the head at once, but shows it only after a moment, DBL, which the second
  // press of a double-click cancels (mousedown, below): a double-click selects
  // a word, for Ctrl+X, and should do nothing else.  Until 2026-11-08 its
  // first click showed the head and tinted the paragraph, and at the page's
  // top the head stayed over the search box Ctrl+X had filled (Tigran: "the
  // first part of the double-click is interpreted as a tap").
  var headSoon = 0, headBy = 0, DBL = 350;
  function tapHead(ev) {
    var t = ev.target, p;
    if (ev.button || (ev.detail > 1 && !touch) || selDown || !t.closest || !t.closest('main') || !getSelection().isCollapsed || inFold(t) ||
        t.closest('a, button, input, select, textarea, label, summary, nav, .rail, .a, .cites, .blanket, .marginhead, .player, .pop, dialog') ||
        !document.querySelector('main :is(p.t, p.kv)[id]')) return false;
    if (!touch && (!head || head.hidden)) {
      clearTimeout(headSoon);
      p = paraOf(t, ev.clientY, ev.clientX);
      headSoon = setTimeout(function () {
        headSoon = 0;
        if (!getSelection().isCollapsed) return;
        // Not a paragraph the page has left meanwhile, by a page turned, the
        // text scrolled or a place on it followed from the rail: it named one
        // off the screen, and stopped arrive() placing the page (review of
        // 2026-11-09).
        var r = p && p.isConnected && p.getBoundingClientRect();
        if (r && (r.bottom <= 0 || r.top >= innerHeight)) return;
        unhit();
        showHead(p && p.isConnected ? p : firstOnScreen());
        headBy = Date.now();
      }, DBL);
      return true;
    }
    unhit();
    if (head && !head.hidden) { hideHead(); return true; }
    showHead(paraOf(t, ev.clientY, ev.clientX) || firstOnScreen());
    return true;
  }
  // The second press of a mouse's double-click, or the third of a triple
  // click: the first click's head is never shown, or, where the double-click
  // was slower than DBL and it was, it goes again.
  document.addEventListener('mousedown', function (ev) {
    if (ev.detail < 2) return;
    clearTimeout(headSoon);
    headSoon = 0;
    if (headP && Date.now() - headBy < 1000) hideHead();
  }, true);
  addEventListener('scroll', function () {
    if (headP && Math.abs(clampY() - headAt) > headSlack) hideHead();
  }, { passive: true });
  addEventListener('resize', hideHead);
  document.addEventListener('ub:swap', hideHead);

  // The reading place (Tigran, 2026-11-17; DECISIONS.md, The home page): the
  // paragraph this browser last had at the top of the screen on a page of the
  // text, kept in localStorage `ub_place` with its paper's title, the time and
  // the text's version, for Continue reading in the bar at the foot (base.html
  // .fbar, window.ubBar).  No setting, so Restore the defaults leaves it, and
  // nothing of it reaches the server, but for a reader signed in, whose
  // account keeps it (static/account.js, which is told as it is written,
  // 'ub:kept', and sends it as the page is left).  A page counts as read
  // once the reader has stayed on it RP_DWELL, or has moved it, by the wheel,
  // a finger or a key, or is listening: a glance at a search's hit, or at a
  // place an index entry cites, and Back, moves nothing.  From then the place
  // follows the page as it scrolls, and is put down once more as the page is
  // left.  While
  // something is heard it is the paragraph being heard (p.t.now, which
  // listen.js marks, and which is not asked anything: trap 51), a
  // translation's too, by the paragraph it translates; and that paragraph
  // stays the place once the player is shut, for as long as any of it is on
  // the screen (Tigran, 2026-11-17: "if I was listening and paused (but also
  // got rid of the audio player at the bottom for some reason), then I would
  // want to resume from that paragraph and not from the one that happens to
  // be at the top of the view").  On a section's page and the whole paper's;
  // not on a reading path, which is another order than the book's, nor on a
  // part's title page.
  var RP = 'ub_place', RP_DWELL = 5000, rpOn = false, rpSaid = '', rpTimer = 0, rpWait = 0, rpLast = null, rpAsk = 0;
  function rpText() { return !!document.querySelector('main.reader article:not(.partpage) p.t[id]'); }
  // The paragraph being heard: the one listen.js marks, or, where it marks a
  // translation's line, in its fold or its column, the paragraph that is of.
  function rpNow() {
    var el = document.body.classList.contains('listening') && document.querySelector('main.reader :is(p.t.now[id], p.rt.now)');
    return !el ? null : el.id ? el : document.getElementById(el.dataset.ref || '');
  }
  // The paragraph whose translations, open in the fold under it, stand across
  // height y of the window: it is the one being read there, in translation,
  // and not the next, whose first line may be a screen below.  With the folds
  // open under every paragraph that is where a phone's window mostly stands
  // (2026-11-20), and Continue reading came back a paragraph on.  By the
  // fold's words, the .tf itself having no box on a phone with the index
  // folded.  `q` is the paragraph before the first that reaches below y.
  function foldOver(q, y) {
    var row = q && q.closest('.row'), panel = row && row.querySelector(':scope > .tf.open > .tr'),
        b = panel && panel.getBoundingClientRect();
    return b && b.height && b.top <= y && b.bottom > y ? row.querySelector('p.t[id]') : null;
  }
  // The paragraph heard, or the one last heard while it is on the screen;
  // else the first paragraph with a line of its own showing under what stands
  // over the text, the columns' names; at the page's very top, the first.
  function rpPara() {
    var now = rpNow(), ps, i, r, top = 0, names;
    if (now) return (rpLast = now);
    if (rpLast) {
      r = rpLast.isConnected && rpLast.getBoundingClientRect();
      if (r && r.height && r.bottom > 0 && r.top < innerHeight) return rpLast;
      rpLast = null;
    }
    names = document.querySelector('main article.cmp .cmpnames');
    if (names && (r = names.getBoundingClientRect()).height && r.top <= 1) top = r.bottom;
    ps = document.querySelectorAll('main.reader article:not(.partpage) p.t[id]');
    for (i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > top + 24) return foldOver(ps[i - 1], top + 24) || ps[i];
    }
    return ps[ps.length - 1] || null;
  }
  function rpSave() {
    var p, bar = document.querySelector('.fbar');
    if (!rpOn || !rpText()) return;
    p = rpPara();
    if (!p || p.id === rpSaid) return;
    try {
      localStorage.setItem(RP, JSON.stringify({ ref: p.id, title: titleOf(p), at: Date.now(),
                                                v: bar && bar.dataset.tv || '' }));
      rpSaid = p.id;
    } catch (e) { return; }
    if (window.ubBar) window.ubBar();
    document.dispatchEvent(new CustomEvent('ub:kept', { detail: 'place' }));
  }
  function rpEngage() { if (!rpOn && rpText()) { rpOn = true; rpSave(); } }
  // The page as it is come to, or brought in by listen.js: not read yet,
  // unless it is being heard.
  function rpBegin() {
    clearTimeout(rpTimer);
    rpSaid = '';
    rpOn = false;
    rpLast = null;
    if (!rpText()) return;
    if (document.body.classList.contains('listening')) return rpEngage();
    rpTimer = setTimeout(function tick() {
      if (document.hidden) rpTimer = setTimeout(tick, RP_DWELL); else rpEngage();
    }, RP_DWELL);
  }
  addEventListener('scroll', function () {
    // The reader's own scroll is reading; arrive()'s, to the paragraph an
    // address names, is not.
    if (!rpOn && Date.now() - arriveTouched < 1500) rpEngage();
    if (!rpOn || rpWait) return;
    rpWait = setTimeout(function () { rpWait = 0; rpSave(); }, 400);
  }, { passive: true });
  document.addEventListener('visibilitychange', function () { if (document.hidden) rpSave(); });
  addEventListener('pagehide', rpSave);
  // Back to a page the browser kept whole: the place is this page's again,
  // and on a page with the bar, the bar's words are the place as it now is.
  addEventListener('pageshow', function (ev) {
    if (!ev.persisted) return;
    rpSaid = '';
    rpSave();
    if (window.ubBar) window.ubBar();
  });
  addEventListener('storage', function (ev) { if (ev.key === RP && window.ubBar) window.ubBar(); });
  document.addEventListener('ub:swap', function () { rpBegin(); if (window.ubBar) window.ubBar(); });
  // Heard, the page need not move, Follow along being off, or the paragraph
  // long: asked as the player opens and as its mark moves on (body.listening
  // and .now, listen.js's own marks, watched here, every class the page
  // changes, once to a turn), and now and then while it is open.
  function rpHeard() { if (document.body.classList.contains('listening')) { rpEngage(); rpSave(); } }
  if (window.MutationObserver)
    new MutationObserver(function () { if (!rpAsk) rpAsk = setTimeout(function () { rpAsk = 0; rpHeard(); }, 0); })
      .observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });
  setInterval(rpHeard, 3000);
  rpBegin();

  // Bookmarks (Tigran, 2026-11-17; DECISIONS.md, The home page): paragraphs
  // the reader marks by hand, kept in localStorage `ub_marks`, each with its
  // paper's title, its opening words, the time and the text's version; no
  // setting, as the reading place is none, and as it is, kept with the
  // account of a reader signed in (static/account.js).  One construct with
  // Continue reading: the bar at the foot (base.html .fbar) has the list's
  // button at its right end, a ribbon and their number, where there is one,
  // and on a
  // page of the text it comes with the running head, at a tap on a paragraph
  // (showHead, above), with Bookmark this paragraph in Continue reading's
  // place.  A bookmarked paragraph has a ribbon in the margin, a class here
  // and a drawing in ub.css (p.t.bmk), so no page's markup knows of it.
  // The list is in the book's order; a row goes to its paragraph, and its ×
  // removes it at once, the row staying, pale, with Undo, until the list is
  // shut (his rulings, the same day).  A translation's paragraph named marks
  // the paragraph it translates: a bookmark is a place in the book.  What
  // the browser keeps is followed only where it is a paragraph's reference.
  var BM = 'ub_marks', RE_REF = /^(\d+):(\d+)\.(\d+)$/, fbar = document.querySelector('.fbar'),
      bmMark = fbar && fbar.querySelector('.fmark'), bmList = fbar && fbar.querySelector('.flist'),
      bmSheet = fbar && fbar.querySelector('.fsheet'), bmGone = [],
      BM_X = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg>';
  function bmOrder(a, b) {
    var x = RE_REF.exec(a.ref), y = RE_REF.exec(b.ref);
    return x[1] - y[1] || x[2] - y[2] || x[3] - y[3];
  }
  function bmAll() {
    var m = null;
    try { m = JSON.parse(localStorage.getItem(BM) || 'null'); } catch (e) {}
    if (!Array.isArray(m)) return [];
    return m.filter(function (x) { return x && typeof x.ref === 'string' && RE_REF.test(x.ref); }).sort(bmOrder);
  }
  function bmPut(m) {
    try {
      if (m.length) localStorage.setItem(BM, JSON.stringify(m.sort(bmOrder))); else localStorage.removeItem(BM);
    } catch (e) { return; }
    bmSync();
    // Said for a reader signed in, whose account keeps them (account.js).
    document.dispatchEvent(new CustomEvent('ub:kept', { detail: 'mark' }));
  }
  function bmAt(m, ref) {
    for (var i = 0; i < m.length; i++) if (m[i].ref === ref) return i;
    return -1;
  }
  // The reference of a paragraph, the text's or a translation's.
  function bmRef(p) {
    var r = p && (p.id || p.dataset.ref) || '';
    return RE_REF.test(r) ? r : '';
  }
  // Its paper's title: the page's head, or on a reading path the line that
  // names the paper before it, "Paper 101 · The Real Nature of Religion".
  function bmTitle(p) {
    var t = titleOf(p), rhs, rh = null, i, a;
    if (t) return t;
    rhs = document.querySelectorAll('main .rh-paper');
    for (i = 0; i < rhs.length; i++)
      if (rhs[i].compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING) rh = rhs[i];
    a = rh && rh.querySelector('a');
    // Its words after "Paper 101 \u00b7 ", one text since the line is the book's
    // own words, "Paper", in either language (path.html, 2026-11-22).
    return a && a.lastChild && a.lastChild.nodeType === 3
      ? a.lastChild.data.replace(/^\s*(Paper \d+)?[\s\u00b7]+/, '').trim() : '';
  }
  // Its opening words, twelve, as Ctrl+X takes a selection's (clean, below):
  // without the reference, the play button and a card open in it.
  function bmWords(p) {
    var w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT), n, out = '', words;
    for (n = w.nextNode(); n && out.length < 600; n = w.nextNode())
      if (!n.parentNode.closest('.stk, button, .pop')) out += n.data;
    words = clean(out).split(' ');
    return words.length > 12 ? words.slice(0, 12).join(' ').replace(/[\s,;:.\u2014\u2013-]+$/, '') + '\u2026' : words.join(' ');
  }
  // The ribbons: every bookmarked paragraph the page has, and no other.
  function bmPaint() {
    var has = {}, ps = document.querySelectorAll('main p.t[id]'), i;
    bmAll().forEach(function (x) { has[x.ref] = true; });
    for (i = 0; i < ps.length; i++) ps[i].classList.toggle('bmk', has[ps[i].id] === true);
  }
  // The button that sets one, as the paragraph the head names stands.
  function bmPress() {
    var ref = bmRef(headP);
    if (bmMark) bmMark.setAttribute('aria-pressed', ref && bmAt(bmAll(), ref) >= 0 ? 'true' : 'false');
  }
  // The rows, the kept and those removed since the list was opened, together
  // in the book's order.  Made of what the browser keeps, as text.
  function bmRows() {
    var ul = bmSheet.querySelector('ul'), rib = bmList.querySelector('svg');
    ul.textContent = '';
    bmAll().concat(bmGone).sort(bmOrder).forEach(function (x) {
      var gone = bmGone.indexOf(x) >= 0, li = document.createElement('li'), a = document.createElement('a'),
          row = document.createElement('span'), r = document.createElement('span'), t = document.createElement('span'),
          q = document.createElement('span'), b = document.createElement('button');
      a.className = 'fgoto';
      a.href = '/' + x.ref;
      row.className = 'frow';
      r.className = 'fr';
      t.className = 'ft';
      q.className = 'fq';
      r.textContent = x.ref;
      t.textContent = typeof x.title === 'string' ? x.title : '';
      if (rib) row.appendChild(rib.cloneNode(true));
      row.appendChild(r);
      row.appendChild(t);
      a.appendChild(row);
      if (gone) q.innerHTML = T('Removed'); else q.textContent = typeof x.q === 'string' ? x.q : '';
      a.appendChild(q);
      li.appendChild(a);
      b.type = 'button';
      b.dataset.ref = x.ref;
      if (gone) {
        li.className = 'fgone';
        a.tabIndex = -1;
        a.setAttribute('aria-disabled', 'true');
        b.className = 'fundo';
        b.innerHTML = T('Undo');
      } else {
        b.className = 'fx';
        T.attr(b, 'aria-label', 'Remove this bookmark');
        b.innerHTML = BM_X;
      }
      li.appendChild(b);
      ul.appendChild(li);
    });
    // Its button stays while the list is open, the last one removed too.
    bmList.hidden = false;
  }
  function bmOpen() {
    bmGone = [];
    bmRows();
    bmSheet.hidden = false;
    bmList.setAttribute('aria-expanded', 'true');
  }
  // `back`: the focus to the list's button, where it was in the list (Escape).
  function bmShut(back) {
    if (!bmSheet || bmSheet.hidden) return;
    if (back && bmSheet.contains(document.activeElement)) bmList.focus({ preventScroll: true });
    bmSheet.hidden = true;
    bmList.setAttribute('aria-expanded', 'false');
    bmGone = [];
    if (window.ubBar) window.ubBar();
  }
  // Everything that shows the bookmarks, as they now are.
  function bmSync() {
    if (window.ubBar) window.ubBar();
    bmPaint();
    bmPress();
    if (bmSheet && !bmSheet.hidden) bmRows();
  }
  // The bar on a page of the text: up with the running head, for the
  // paragraph it names, and down with it, the list too.
  var barAt = 0, BAR_SOON = 400;
  function barUp() {
    if (!bmMark) return;
    if (!fbar.classList.contains('fup')) barAt = Date.now();
    bmMark.hidden = false;
    if (fcopy) fcopy.hidden = false;
    fbar.classList.add('fup');
    bmPress();
  }
  function barDown() {
    if (!bmMark || !fbar.classList.contains('fup')) return;
    bmShut();
    fbar.classList.remove('fup');
    bmMark.hidden = true;
    if (fcopy) fcopy.hidden = true;
  }
  if (bmMark && bmList && bmSheet) {
    // The bar comes up under the finger where the paragraph tapped was low on
    // the screen, and the next tap, meant for the text, to take the bars
    // away, would land on it: on its ground that is what it does, as a tap on
    // the running head's does; and in the moment after the bar rose, on its
    // buttons too, the second of a quick pair of taps, which never meant
    // them (found by tools/runhead_e2e.py, 2026-11-17, whose second tap low
    // on the screen set a bookmark).  First of the bar's handlers, so that
    // no button hears such a tap.
    fbar.addEventListener('click', function (ev) {
      if (!fbar.classList.contains('fup')) return;
      if (Date.now() - barAt >= BAR_SOON && ev.target.closest('a, button, .fsheet')) return;
      ev.stopPropagation();
      ev.preventDefault();
      hideHead();
    }, true);
    bmMark.addEventListener('click', function () {
      var p = headP, ref = bmRef(p), m, i;
      if (!ref) return;
      m = bmAll();
      i = bmAt(m, ref);
      if (i >= 0) m.splice(i, 1);
      else m.push({ ref: ref, title: bmTitle(p), q: bmWords(p), at: Date.now(), v: fbar.dataset.tv || '' });
      bmPut(m);
    });
    bmList.addEventListener('click', function () { if (bmSheet.hidden) bmOpen(); else bmShut(); });
    bmSheet.addEventListener('click', function (ev) {
      var b = ev.target.closest('button[data-ref]'), m, i;
      // A row followed: the list goes, and the head and the bar with it where
      // the place is on this page.  The link is the paragraph's own address,
      // which the Whole paper handler has put in the reader's unit by now.
      if (!b) { if (ev.target.closest('a.fgoto')) { bmShut(); hideHead(); } return; }
      m = bmAll();
      if (b.classList.contains('fundo')) {
        for (i = 0; i < bmGone.length; i++) if (bmGone[i].ref === b.dataset.ref) break;
        if (i === bmGone.length) return;
        if (bmAt(m, b.dataset.ref) < 0) m.push(bmGone[i]);
        bmGone.splice(i, 1);
      } else {
        i = bmAt(m, b.dataset.ref);
        if (i < 0) return;
        bmGone.push(m.splice(i, 1)[0]);
      }
      bmPut(m);
      // The button pressed is gone with its row: the focus to the one in its place.
      b = bmSheet.querySelector('button[data-ref="' + b.dataset.ref + '"]');
      if (b) b.focus({ preventScroll: true });
    });
    // A click anywhere else shuts the list; by the path the click took, the
    // row's own button being out of the page by now.
    document.addEventListener('click', function (ev) {
      if (bmSheet.hidden) return;
      var path = ev.composedPath ? ev.composedPath() : null;
      if (path ? path.indexOf(fbar) < 0 : !fbar.contains(ev.target)) bmShut();
    });
    addEventListener('storage', function (ev) { if (ev.key === BM) bmSync(); });
    addEventListener('pageshow', function (ev) { if (ev.persisted) bmSync(); });
    document.addEventListener('ub:swap', bmPaint);
    bmPaint();
  }
  // What an exchange with the reader's account brought from another device
  // (static/account.js): the bookmarks and the place as the browser now
  // keeps them, wherever they show.
  document.addEventListener('ub:brought', bmSync);
  if (gear) gear.addEventListener('click', hideHead);

  // A paragraph's link (Tigran, 2026-11-19: "we definitely need a way to save
  // a stable reference to the current paragraph, which can be sent outside"):
  // its address on this site, /101:2.3, which opens it whatever the reader's
  // unit, put on the clipboard as plain text.  A translation's paragraph gives
  // the paragraph it translates, as a bookmark does (bmRef).  Two ways in: a
  // click or a tap on the paragraph's reference, where references are shown
  // (the notes' click listener, above, which has every click on the text),
  // and Copy link in the bar at the foot, with them shown or not (base.html
  // .fcopy), copying on a phone too, not the phone's Share (his choice, the
  // same day).  The clipboard's own call in a secure context; elsewhere, the
  // dev server at a LAN address, or where the call is refused, the browser's
  // copy command, whose event the soft hyphens' listener (below) fills with
  // the address.  A note over what was pressed says it was done, the only
  // sign on a phone, where the bar's button is its drawing alone.
  var NUM = 'main p.t > .stk > span.num', copyNext = null, fcopy = fbar && fbar.querySelector('.fcopy'),
      lnote = document.createElement('div'), lnoteGo = 0;
  lnote.className = 'lnote';
  lnote.setAttribute('role', 'status');
  document.body.appendChild(lnote);
  function copyLink(ref, el) {
    var url = location.origin + '/' + ref;
    function old() {
      copyNext = url;
      try { document.execCommand('copy'); } catch (e) {}
      // The event came and took the address, or nothing was copied.
      if (copyNext === null) copySaid(el);
      copyNext = null;
    }
    if (navigator.clipboard && window.isSecureContext)
      navigator.clipboard.writeText(url).then(function () { copySaid(el); }, old);
    else old();
  }
  // Over the thing pressed, or under it at the window's top, and inside the
  // window; gone after a moment, the words with it.
  function copySaid(el) {
    var r = el.getBoundingClientRect(), w, h, y;
    clearTimeout(lnoteGo);
    lnote.classList.remove('lon');
    lnote.innerHTML = T('Link copied');
    w = lnote.offsetWidth;
    h = lnote.offsetHeight;
    y = r.top - h - 6;
    if (y < 6) y = r.bottom + 6;
    lnote.style.left = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2)) + 'px';
    lnote.style.top = y + 'px';
    lnote.classList.add('lon');
    lnoteGo = setTimeout(function () { lnote.classList.remove('lon'); lnote.textContent = ''; }, 1600);
  }
  if (fcopy) fcopy.addEventListener('click', function () {
    var ref = bmRef(headP);
    if (ref) copyLink(ref, fcopy);
  });
  // The reference says what a click does, where the pointer rests on it: set
  // the first time, so that no page's markup carries it.  Tooltips off, the
  // watcher (tips, above) takes it away as it comes.
  document.addEventListener('mouseover', function (ev) {
    var n = ev.target.closest && ev.target.closest(NUM);
    if (n && !n.hasAttribute('title') && !n.hasAttribute('data-tip') && bmRef(n.closest('p.t')))
      T.attr(n, 'title', 'Copy link to this paragraph');
  });

  // A search hit among the 1955 readings opens /93:5.8#note93_5_8_0, and
  // arrive() brings its paragraph into view: its card opens too -- if the ring
  // shows, which it does not with the readings turned off.  Not #fnref…, the
  // ring's own id, or the browser scrolls the ring's line to the top as the
  // page loads, over arrive(), and the paragraph's first lines are lost.  Here,
  // after the card's own code, which sets `card` after arrive() has run.
  // Placed again when the fonts are in and the text has reflowed.
  function arriveNote() {
    var m = /^#note((?:st)?\d+_\d+_\d+_\d+)$/.exec(location.hash),
        mark = m && document.getElementById('fnref' + m[1]);
    if (!mark || !mark.matches('a.fn') || !mark.offsetParent) return;
    shut(false);
    open(mark);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      if (card && card.mark === mark) place();
    });
  }
  arriveNote();
  document.addEventListener('ub:page', arriveNote);

  // The soft hyphens that let a line break where the book breaks (ub.css p.t)
  // are not text, but Chrome copies them, and a pasted paragraph would carry
  // an invisible character in every long word.  So they leave the selected
  // text while the browser copies it, and come back before the next paint.
  // The copy is then the browser's own, as plain text and as HTML with its
  // styles (the red letter, the face), exactly as from a page without them.
  // One deleteData per hyphen, which a selection's ends follow; put back in
  // reverse, so each goes where it was.  A list's label, floated in a box of
  // its own (ub.css .mark), drops the space after it from the copy, so for the
  // same moment the page is .copying, and the labels stand in the line.
  // But a paragraph's link, copied by the copy command (copyLink, above), is
  // the address alone.
  document.addEventListener('copy', function (ev) {
    if (copyNext !== null) {
      ev.clipboardData.setData('text/plain', copyNext);
      ev.preventDefault();
      copyNext = null;
      return;
    }
    var sel = getSelection(), gone = [], i, r, root, w, n, k, html = document.documentElement;
    html.classList.add('copying');
    for (i = 0; i < sel.rangeCount; i++) {
      r = sel.getRangeAt(i);
      root = r.commonAncestorContainer;
      w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (n = root.nodeType === 3 ? root : w.nextNode(); n; n = w.nextNode()) {
        if (!r.intersectsNode(n)) continue;
        for (k = n.data.indexOf('­'); k >= 0; k = n.data.indexOf('­', k)) {
          n.deleteData(k, 1);
          gone.push([n, k]);
        }
      }
    }
    requestAnimationFrame(function () {
      html.classList.remove('copying');
      for (var j = gone.length - 1; j >= 0; j--) gone[j][0].insertData(gone[j][1], '­');
    });
  });

  // Ctrl+X searches (Tigran, 2026-10-23): the words selected go into the
  // search box, or with none selected the box is simply found, and either way
  // the page goes up to it and it takes the focus, ready for Enter.  The words
  // are what the page draws of the selection, without the soft hyphens, which
  // the search would read as a break in the word, and without a paragraph's
  // reference, ▶ and 1955 page (.stk), which a triple click takes along and
  // which would find nothing; unless that was all there was, when the
  // reference opens its paragraph.  A space where the block changes.  Inside a
  // field Ctrl+X is still Cut; on the page there is nothing to cut.  Escape in
  // the box, while it still has the focus Ctrl+X gave it, goes back: what the
  // box held, the place, the selection (Tigran's choice).
  function clean(s) { return s.replace(/[\u00ad\u2060\u200b]/g, '').replace(/\s+/g, ' ').trim(); }
  function chosen() {
    var sel = getSelection(), out = '', last = null, i, r, root, w, n, b;
    for (i = 0; i < sel.rangeCount; i++) {
      r = sel.getRangeAt(i);
      root = r.commonAncestorContainer;
      w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (n = root.nodeType === 3 ? root : w.nextNode(); n; n = w.nextNode()) {
        if (!r.intersectsNode(n) || !n.parentNode.getClientRects().length ||
            n.parentNode.closest('.stk, button')) continue;
        b = n.parentNode.closest('p, li, dt, dd, td, th, h1, h2, h3, h4, div, summary');
        out += (b === last ? '' : ' ') + n.data.slice(n === r.startContainer ? r.startOffset : 0,
                                                     n === r.endContainer ? r.endOffset : n.length);
        last = b;
      }
    }
    return clean(out) || clean(sel.toString());
  }
  var box = document.querySelector('.find input'), back = null;
  if (box) {
    document.addEventListener('keydown', function (ev) {
      var t = ev.target, sel = getSelection(), words = '', i;
      // Or where X is, on a keyboard that writes no Latin letters (Armenian,
      // Russian): the browser's Cut is there too.
      if (!(/^x$/i.test(ev.key) || (ev.code === 'KeyX' && !/^[a-z]$/i.test(ev.key))) ||
          !ev.ctrlKey || ev.altKey || ev.shiftKey || ev.metaKey || ev.repeat || ev.defaultPrevented ||
          (t.closest && t.closest('input, textarea, select, [contenteditable]')) ||
          document.querySelector('dialog[open]')) return;
      ev.preventDefault();
      // The running head goes, or at the page's top, where going up to the
      // box hardly scrolls, it stays over the box (Tigran, 2026-11-08).
      hideHead();
      back = { value: box.value, y: scrollY, ranges: [] };
      for (i = 0; i < sel.rangeCount; i++) back.ranges.push(sel.getRangeAt(i).cloneRange());
      if (!sel.isCollapsed) words = chosen();
      if (words) box.value = words;
      scrollTo({ top: 0, behavior: 'instant' });
      box.focus({ preventScroll: true });
      if (words) box.setSelectionRange(words.length, words.length); else box.select();
    });
    box.addEventListener('keydown', function (ev) {
      var b = back, sel = getSelection();
      if (ev.key !== 'Escape' || !b) return;
      ev.preventDefault();
      box.value = b.value;
      box.blur();
      scrollTo({ top: b.y, behavior: 'instant' });
      sel.removeAllRanges();
      b.ranges.forEach(function (r) {
        if (r.startContainer.isConnected && r.endContainer.isConnected) sel.addRange(r);
      });
    });
    box.addEventListener('blur', function () { back = null; });
  }

  // Work offline, where a service worker can run: Settings' Offline tab,
  // which says whether this page is online or offline, and what the copy is
  // (base.html; until 2026-10-30 a menu of its own, #offmenu, and until
  // 2026-10-14 a switch in Settings).  Until 2026-11-17 a cloud at the
  // header's corner said both and opened the tab (Tigran: "its functions are
  // duplicated in the Settings => Offline menu"); what it held of the page's
  // state is on the tab's panel, data-net here and data-have in offline.js.
  // static/offline.js runs the tab, and says what the copy is on the panel,
  // then 'ub:offline'.  It is loaded on every page since 2026-11-10 (Tigran:
  // every browser keeps the copy, and reads the site from it): at once on a
  // page the worker answers for, to say whether its copy is still the site's;
  // on any other once the page has loaded and the browser is idle, to
  // register the worker and fetch the copy; and when the tab opens.  The
  // browser's own offer to install the site waits in the tab too, rather than
  // in a banner of its own.
  // A reader's account (ubsite/account.py; Tigran, 2026-11-18), on a host
  // that has accounts (settings.py ACCOUNT_HOSTS, which base.html hands the
  // page, a stored page being the same on every host).  At the header's
  // corner a menu, as the ?'s is: with no one signed in, why one would and
  // the button that goes to Google; signed in, the account's picture, and in
  // the menu who, with Sign out and Delete my account.  And at Settings'
  // foot, where the dialog says where the settings are kept, the same said
  // in a line.  Not a tab, a sixth running past the dialog's edge on a phone,
  // and not a page, but for a sign-in that went wrong (/account).
  //
  // Who is signed in is what the browser keeps of it, localStorage ub_who,
  // the server's answer at /account/me as /account/done wrote it: a page is
  // read from the offline copy and asks the server nothing, so it cannot be
  // told any other way.  It is a note and no more: the server knows a reader
  // by a cookie no script can read, and takes nothing a script says.  The
  // head script's ubMe() draws it, before the header is painted; here is what
  // the buttons do, and the note put right each time the menu is opened.
  var acctKept = document.querySelector('dialog.settings .kept'), acctMenu = document.querySelector('.top .acctmenu');
  if (acctKept && (window.ubAcct || []).indexOf(location.hostname) >= 0 && window.fetch) {
    var acctWho = function () {
      try {
        var w = JSON.parse(localStorage.getItem('ub_who') || 'null');
        return w && typeof w === 'object' && typeof w.email === 'string' ? w : null;
      } catch (e) { return null; }
    };
    var acctKeep = function (me) {
      try {
        if (me) localStorage.setItem('ub_who', JSON.stringify(me)); else localStorage.removeItem('ub_who');
      } catch (e) {}
    };
    // What follows the account (static/account.js, its address on the menu):
    // run for a reader who is signed in, and for no other, as offline.js is
    // run only where Work offline can be.
    // Not on the pages a sign-in passes through (/account/welcome,
    // /account/done), which are left at once: the page come back to runs it.
    var acctRun = false, acctFollow = function () {
      if (acctRun || !acctMenu || !acctMenu.dataset.src || !acctWho() || /^\/account\//.test(location.pathname)) return;
      acctRun = true;
      var sc = document.createElement('script');
      sc.src = acctMenu.dataset.src;
      document.head.appendChild(sc);
    };
    var acctLine = function () {
      acctKept.dataset.acct = acctWho() ? 'in' : 'out';
      // The menu, its mark and every name (base.html ubMe); and one more
      // control beside the name, or another, so the controls are fitted again.
      if (window.ubMe) window.ubMe();
      ctlFit();
      acctFollow();
      // Said for account.js, which asks the server what the account keeps.
      document.dispatchEvent(new Event('ub:who'));
    };
    acctLine();
    addEventListener('storage', function (ev) { if (ev.key === 'ub_who') acctLine(); });
    addEventListener('pageshow', function (ev) { if (ev.persisted) acctLine(); });
    // Where the reader is, to come back to once signed in: the paragraph
    // being read, the whole paper's too, whose address has a # in it.  On the
    // account's own page, where the server says the reader came from.
    var acctHere = function (box) {
      return (box && box.dataset.next) ||
        (/^\/account(\/|$)/.test(location.pathname) ? '/' : location.pathname + location.search + location.hash);
    };
    var acctGo = function (box) { location.assign('/account/login?next=' + encodeURIComponent(acctHere(box))); };
    var acctPost = function (path, body) {
      return fetch(path, { method: 'POST', credentials: 'same-origin', cache: 'no-store',
                           headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
        .then(function (r) { if (!r.ok) throw r; return r.json(); });
    };
    // The server's word on who is signed in: 401, no one.  The network
    // failing changes nothing.
    var acctAsk = function () {
      return fetch('/account/me', { credentials: 'same-origin', cache: 'no-store' }).then(function (r) {
        if (r.status === 401) { acctKeep(null); return null; }
        return r.ok ? r.json().then(acctKeep) : null;
      }).catch(function () {}).then(acctLine);
    };
    var acctShut = function () { if (acctMenu) acctMenu.open = false; };
    var acctDone = function () { acctKeep(null); acctLine(); };
    // Signed out of a computer that is not one's own (the box under Sign
    // out): what followed the account is taken out of this browser too, by
    // the script that keeps it in step (account.js forget), and the page
    // read again as it then is.
    var acctClear = function () {
      acctKeep(null);
      if (window.ubFollow) window.ubFollow.forget(); else acctLine();
    };
    document.addEventListener('click', function (ev) {
      var t = ev.target.closest && ev.target.closest('a.acctlink, .acct button'), box, me = acctWho(), dlg;
      if (acctMenu && acctMenu.open && !acctMenu.contains(ev.target)) acctShut();
      if (!t) return;
      if (t.matches('a.acctlink')) {
        // Settings' foot.  Signed out, straight to Google and back here;
        // signed in, to the menu at the corner, or, where a narrow phone
        // has left the menu out, to the account's page.
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) return;
        ev.preventDefault();
        if (!me) return acctGo(null);
        if (!acctMenu || !acctMenu.getClientRects().length) {
          return location.assign('/account?next=' + encodeURIComponent(acctHere(null)));
        }
        dlg = t.closest('dialog');
        if (dlg && dlg.open) dlg.close();
        acctMenu.open = true;
        acctMenu.querySelector('summary').focus();
        return;
      }
      box = t.closest('.acct');
      var said = box.querySelector('.acct-say'), also = box.querySelector('.acct-clear'),
          failed = function () { said.innerHTML = T('That did not work. Please try again in a moment.'); said.hidden = false; };
      said.hidden = true;
      if (t.classList.contains('acct-go')) acctGo(box);
      else if (t.classList.contains('acct-bye')) {
        // What has not reached the account yet goes first (account.js);
        // then signed out, the browser left as it is, or, the box ticked,
        // what followed the account taken out of it too.
        (window.ubFollow ? window.ubFollow.flush() : Promise.resolve()).then(function () {
          return acctPost('/account/logout');
        }).then(also && also.checked ? acctClear : acctDone, failed);
      } else if (t.classList.contains('acct-del') && me && window.confirm(T.text('acct:delete?'))) {
        // The account gone, the browser keeps what it has, as no one's: a
        // later sign-in begins from it.
        acctPost('/account/delete', { email: me.email }).then(function () {
          try { localStorage.removeItem('ub_sync'); } catch (e) {}
          acctDone();
        }, failed);
      }
    });
    // From account.js: the reader would not have another account's things
    // replaced by this one's, and is signed out again ('out'); or the server
    // says the session has ended ('gone').
    document.addEventListener('ub:acct', function (ev) {
      if (ev.detail === 'out') acctPost('/account/logout').then(acctDone, acctDone);
      else if (ev.detail === 'gone') acctDone();
    });
    if (acctMenu) {
      // Opened, the menu asks the server who is signed in, and says what it
      // answers, and what the account keeps is brought at once, whenever it
      // was last asked for (account.js); shut by Escape, and by a tap
      // anywhere else (above).
      acctMenu.addEventListener('toggle', function () {
        if (!acctMenu.open) return;
        acctAsk();
        if (window.ubFollow && acctWho()) window.ubFollow.now();
      });
      document.addEventListener('keydown', function (ev) {
        if (ev.key !== 'Escape' || !acctMenu.open) return;
        acctShut();
        acctMenu.querySelector('summary').focus();
      });
    }
    // The account's own page asks as it loads, as the menu does when opened.
    if (document.querySelector('main .acct')) acctAsk();
    // A session and nothing kept here of whose it is: Safari clears what a
    // script keeps after seven days unvisited and leaves the server's
    // cookies (CLAUDE.md, trap 23), one of which a script may read and says
    // only that there is a session (app.py _acct_in).  The server is asked
    // who, once, and the corner says so.
    else if (!acctWho() && /(?:^|;\s*)ub_in=1(?:;|$)/.test(document.cookie)) acctAsk();
  }

  var offpanel = document.querySelector('dialog.settings .panel.offline');
  if (offpanel && 'serviceWorker' in navigator && window.isSecureContext &&
      window.HTMLDialogElement && 'showModal' in HTMLDialogElement.prototype) {
    // Settings' tab for it: the tab and its panel.
    document.querySelectorAll('dialog.settings .offline').forEach(function (el) { el.hidden = false; });
    // Offline (data-net) is the site out of reach: the browser says so, or the
    // worker answered for this page from its copy because the network did not,
    // which sw.js writes on the footer (a page it answers first, online, is
    // the server's as it is, unmarked); after that, as the browser says, and as the worker's check of
    // the site says, which offline.js writes on the panel.  Each time the
    // browser speaks, offline.js asks at once whether the site is there, and
    // where the page starts offline: the site's answer is the last word, as
    // Chrome can say offline with the network working (2026-10-27).
    var fromCopy = document.querySelector('footer[data-copy]'), loaded = false;
    // Which site this is, on the tab's first line: the same build is at
    // ubsite.ddns.net and ubsite.sigmaai.au (and under the name in the header,
    // which base.html's head script writes).
    offpanel.querySelector('.net .host').textContent = location.host;
    // The tab's first line: online, or offline, with the date of the copy
    // where the page is from it, which sw.js writes on the footer in each
    // language.
    var label = function () {
      offpanel.querySelector('.net .conn').innerHTML = offpanel.dataset.net === 'on' ? T('Online') : !fromCopy ? T('Offline')
        : T('Offline · the copy of {d}', { d: { en: T.esc(fromCopy.dataset.copy),
                                                ru: T.esc(fromCopy.dataset.copyRu || fromCopy.dataset.copy) } });
    };
    var net = function (on) { offpanel.dataset.net = on ? 'on' : 'off'; label(); };
    var script = function () {
      if (loaded) return;
      loaded = true;
      var sc = document.createElement('script');
      sc.src = offpanel.dataset.src;
      document.head.appendChild(sc);
    };
    offpanel.dataset.have = navigator.serviceWorker.controller ? 'kept' : 'none';
    net(navigator.onLine !== false && !fromCopy);
    window.addEventListener('online', function () { net(true); });
    window.addEventListener('offline', function () { net(false); });
    document.addEventListener('ub:offline', label);
    var atRest = function () {
      if (window.requestIdleCallback) window.requestIdleCallback(script, { timeout: 4000 });
      else setTimeout(script, 1000);
    };
    if (navigator.serviceWorker.controller) script();
    else if (document.readyState === 'complete') atRest();
    else window.addEventListener('load', atRest);
    // And by Settings' Offline tab, whose words are its to say.
    document.addEventListener('ub:offtab', script);
    // And by What's new?, in the ?'s menu (below): offline.js's dialog, opened
    // at once where the script is in, and as it ends where it is not yet.
    document.addEventListener('ub:news', function () {
      if (window.ubOfflineUI && window.ubOfflineUI.news) return window.ubOfflineUI.news();
      window.ubNewsDue = true;
      script();
    });
    // The translations shown, to the worker (shownTo, above): as the page
    // loads, and when a worker takes it over.
    shownTo(load());
    navigator.serviceWorker.addEventListener('controllerchange', function () { shownTo(load()); });
  }

  // Help, and the tour (static/help.js; Tigran, 2026-11-06).  The ? at the
  // corner is a menu (below; a link to /help until 2026-11-10); its data-src
  // is the tour's script, loaded here when the tour is due: never seen in this browser (localStorage
  // ub_tour), or a step kept for this tab (sessionStorage).  Not on /help,
  // which loads it itself, nor on the quiz's pages, whose keys 1-9 and Enter
  // are their own, nor on the API's page, the stats or the board, nor on the
  // chart of the personalities, which a reader sent there came to see, nor where
  // #listen starts the player as the page loads.  The script waits for
  // Settings or What's new to close, and for the page to be visible.
  var helpLink = document.querySelector('.top .help'), tourDue = false;
  try { tourDue = !!sessionStorage.getItem('ub_tour') || localStorage.getItem('ub_tour') !== 'seen'; } catch (e) {}
  if (helpLink && helpLink.dataset.src && tourDue && !/^\/(help$|quiz|api$|stats$|cosmology$)/.test(location.pathname) &&
      location.hash !== '#listen') {
    var hs = document.createElement('script');
    hs.src = helpLink.dataset.src;
    document.head.appendChild(hs);
  }

  // The ?'s menu (base.html; Tigran, 2026-11-10): a <details>, which the
  // browser opens and shuts at its mark; shut here by Escape, by a tap
  // anywhere else, and by one of its items.  Help is a link.  What's new? is
  // offline.js's dialog, what the last update brought, where Work offline can
  // run (its tab shown), asked for by 'ub:news', which Work offline's block
  // above hears; elsewhere the link goes on to the changelog.  About is a
  // small window drawn here, as What's new's is drawn: what the site is, and
  // where its source is kept.
  // A menu at the header's corner, a <details> (the ?'s, the list of
  // languages): shut by a tap anywhere else, and by Escape, which gives its
  // mark the focus back.  The account's menu has its own, doing more.
  function menuShuts(d) {
    document.addEventListener('click', function (ev) {
      if (d.open && !d.contains(ev.target)) d.open = false;
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape' || !d.open) return;
      d.open = false;
      d.querySelector('summary').focus();
    });
  }
  if (helpLink && helpLink.tagName === 'DETAILS') {
    var shutHelp = function () { helpLink.open = false; };
    menuShuts(helpLink);
    var aboutDlg = null;
    var openAbout = function () {
      if (!aboutDlg) {
        var url = helpLink.dataset.repo || '';
        aboutDlg = document.createElement('dialog');
        aboutDlg.id = 'about';
        aboutDlg.className = 'offnews about';
        aboutDlg.setAttribute('aria-labelledby', 'about-title');
        aboutDlg.innerHTML = '<div class="bar"><h2 id="about-title">' + T('About this site') + '</h2>' +
          '<button type="button" class="x" ' + T.a('aria-label', 'Close') + ' ' + T.a('title', 'Close') +
          '><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></svg></button></div>' +
          '<p>' + T('about:1') + '</p>' +
          (url ? '<p class="repo">' + T('about:repo', { a: T.html('<a href="' + T.esc(url) + '" rel="noopener">' +
                                                                T.esc(url.replace(/^https?:\/\//, '')) + '</a>') }) + '</p>' : '') +
          '<p class="all"><a href="/help#about">' + T('about:more') + '</a></p>';
        document.body.appendChild(aboutDlg);
        aboutDlg.addEventListener('click', function (ev) {
          var r = aboutDlg.getBoundingClientRect();
          if (ev.target.closest('.x') || (ev.target === aboutDlg && (ev.clientX < r.left || ev.clientX > r.right ||
                                                                     ev.clientY < r.top || ev.clientY > r.bottom)))
            aboutDlg.close();
        });
      }
      if (!aboutDlg.open) aboutDlg.showModal();
    };
    helpLink.querySelector('.helpitems').addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a');
      if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
      shutHelp();
      if (a.classList.contains('about') && window.HTMLDialogElement) {
        ev.preventDefault();
        openAbout();
      } else if (a.classList.contains('whatsnew') && offpanel && !offpanel.hidden) {
        ev.preventDefault();
        document.dispatchEvent(new Event('ub:news'));
      }
    });
  }
  // The changelog's tabs (templates/changelog.html; Tigran, 2026-11-06: the
  // lists under Added, Changed, Removed and Fixed had grown long).  Each
  // release's headings become a row of tabs, For developers' among them,
  // built here from the headings themselves with how many entries each
  // holds, and one part is shown at a time, the first first; so the page carries the file's words and nothing
  // more, and without scripts it is the file as written.  ←, →, Home and End
  // move among a row's tabs, as Settings' do.
  var tabRows = [];
  Array.prototype.forEach.call(document.querySelectorAll('.changelog .parts'), function (parts) {
    var secs = Array.prototype.filter.call(parts.children, function (s) { return s.matches('section.part') && s.querySelector('h3, summary'); });
    if (secs.length < 2) return;
    var bar = document.createElement('div'), tabs = [];
    bar.className = 'ctabs';
    bar.setAttribute('role', 'tablist');
    secs.forEach(function (s, i) {
      var b = document.createElement('button'), n = s.querySelectorAll('li').length;
      b.type = 'button';
      b.setAttribute('role', 'tab');
      b.id = 'cl-t-' + tabRows.length + '-' + i;
      s.id = s.id || ('cl-p-' + tabRows.length + '-' + i);
      s.setAttribute('role', 'tabpanel');
      s.setAttribute('aria-labelledby', b.id);
      b.setAttribute('aria-controls', s.id);
      b.innerHTML = s.querySelector('h3, summary').innerHTML + (n ? ' <small>' + n + '</small>' : '');
      // For developers keeps its fold for the page without scripts: open here, its tab the heading.
      var fold = s.querySelector('details.dev');
      if (fold) fold.open = true;
      bar.appendChild(b);
      tabs.push(b);
    });
    function show(t) {
      tabs.forEach(function (b, i) {
        var on = b === t;
        b.setAttribute('aria-selected', on ? 'true' : 'false');
        b.tabIndex = on ? 0 : -1;
        secs[i].classList.toggle('on', on);
      });
    }
    bar.addEventListener('click', function (ev) {
      var t = ev.target.closest('[role="tab"]');
      if (t) show(t);
    });
    bar.addEventListener('keydown', function (ev) {
      if (ev.ctrlKey || ev.altKey || ev.metaKey || ev.shiftKey) return;
      var i = tabs.indexOf(bar.querySelector('[aria-selected="true"]')), n = tabs.length;
      var to = { ArrowRight: i + 1, ArrowLeft: i - 1 + n, Home: 0, End: n - 1 }[ev.key];
      if (i < 0 || to === undefined) return;
      ev.preventDefault();
      show(tabs[to % n]);
      tabs[to % n].focus();
    });
    parts.classList.add('tabbed');
    parts.insertBefore(bar, parts.firstChild);
    tabRows.push(bar);
    show(tabs[0]);
  });

  // The offer to install the site as an app: Settings' Offline tab has its
  // button (offline.js), and the home page a line over its header (base.html
  // .appban; Tigran's design, 2026-11-17), in a browser's tab and never in
  // the app.  ub_install, a key of its own and no setting, says what is
  // known: 'offered', the browser made its offer here, so the head script
  // shows the line before anything is drawn next time; 'no', its cross was
  // tapped, for good; 'done', installed.  On an iPhone or iPad, which makes
  // no offer, the line is shown until its cross is tapped, and Install opens
  // Settings at Offline, which says how.
  var appBan = document.querySelector('.appban'), APP = 'ub_install',
      appIn = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  var appKnown = function () { try { return localStorage.getItem(APP); } catch (e) { return null; } };
  var appKeep = function (v) {
    try { if (v) localStorage.setItem(APP, v); else localStorage.removeItem(APP); } catch (e) {}
  };
  var appRoot = document.documentElement;
  var appShow = function (on) {
    if (on) appRoot.dataset.install = appRoot.dataset.install || '1';
    else delete appRoot.dataset.install;
  };
  window.addEventListener('beforeinstallprompt', function (ev) {
    ev.preventDefault();
    window.ubInstall = ev;
    if (appBan && !appIn && appKnown() !== 'no') {
      appKeep('offered');
      if (location.pathname === '/') appShow(true);
    }
    document.dispatchEvent(new Event('ub:installable'));
  });
  window.addEventListener('appinstalled', function () {
    window.ubInstall = null;
    appKeep('done');
    appShow(false);
    document.dispatchEvent(new Event('ub:installable'));
  });
  if (appBan) {
    appBan.querySelector('.abgo').addEventListener('click', function () {
      var offer = window.ubInstall;
      if (!offer) return window.ubSettings.open && window.ubSettings.open('offline');
      offer.prompt();
      offer.userChoice.then(function (c) {
        // The offer is spent either way.  Taken, 'done'; refused in the
        // browser's own dialog, the line goes until the browser offers again.
        window.ubInstall = null;
        appKeep(c && c.outcome === 'accepted' ? 'done' : null);
        appShow(false);
        document.dispatchEvent(new Event('ub:installable'));
      });
    });
    appBan.querySelector('.abno').addEventListener('click', function () {
      appKeep('no');
      appShow(false);
    });
    // Shown by the head script's guess, and the offer has not come: it is
    // not coming (installed since, or refused in the browser's dialog).
    if (appRoot.dataset.install === '1') setTimeout(function () {
      if (window.ubInstall || appRoot.dataset.install !== '1') return;
      appKeep(null);
      appShow(false);
    }, 4000);
  }

  // The chart of the personalities (cosmology.html), brought in by listen.js
  // while it plays: its script, which a <main> swapped in leaves unrun, loaded
  // here, or run again for the new <main> (static/cosmo.js).
  document.addEventListener('ub:swap', function () {
    var chart = document.querySelector('main.cosmo'), js;
    if (!chart) return;
    if (window.ubCosmo) return window.ubCosmo();
    js = document.createElement('script');
    js.src = chart.dataset.src;
    document.head.appendChild(js);
  });
  // Unit conversions (units.html) the same way (static/units.js); listen.js,
  // which every section's page names, is left alone (CLAUDE.md trap 51).
  document.addEventListener('ub:swap', function () {
    var page = document.querySelector('main.units'), js;
    if (!page) return;
    if (window.ubUnits) return window.ubUnits();
    js = document.createElement('script');
    js.src = page.dataset.src;
    document.head.appendChild(js);
  });

  // A reading path's fold, folded from the line below it (path.html): its
  // line above then stands where this one stood, so the paragraph after it
  // stays where the reader was.  On the document, as listen.js swaps <main>.
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button.foldup'), d, y;
    if (!b) return;
    d = b.closest('details');
    y = b.getBoundingClientRect().top;
    d.open = false;
    window.scrollBy({ top: d.querySelector('summary').getBoundingClientRect().top - y,
                      behavior: 'instant' });
  });
})();
