// 15 KB budget, no dependencies. Everything here is an enhancement: the site is
// complete and correct with JavaScript off.
(function () {
  // Settings: one JSON object in localStorage, per browser, no account.  What
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
      // The text size's steps moved up one (settings.py): Largest is Larger.
      if (s.size === 'largest') s.size = 'larger';
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
    if (window.ubTr) window.ubTr(o.translations);
  }
  // The translations shown beside the text, told to the worker (sw.js, {cmd:
  // 'shown'}), which has no other way to Settings: what depends on them, a
  // section's translations and a search, it answers from its copy first only
  // where the copy keeps them all, and otherwise leaves to the server, which
  // sends every one (sw.js covered()).  With each change, before anyone hears
  // of it and asks for a section's again; and as a page loads (below, with
  // the cloud).
  function shownTo(o) {
    var sw = navigator.serviceWorker, w = sw && sw.controller;
    if (w) w.postMessage({ cmd: 'shown', tr: String(o.translations || '').split(' ').filter(Boolean) });
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
  // Each translation's browser voice, {key: name}, those not Automatic
  // (settings.py trvoices, JSON in a string).
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
    // Translation tr's voice, by its name; '' for Automatic.
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
    // Every setting but the spared (settings.py SPARED): the language.
    reset: function () {
      var s = stored(), keep = {};
      SPARED.forEach(function (k) { if (k in s) keep[k] = s[k]; });
      save(keep);
      var o = load();
      apply(o);
      for (var k in DEF) announce(k, o);
    }
  };
  // Shown again from the browser's page cache, by Back or Forward, the page
  // runs no script: what Settings changed on another page since is put on
  // this one, and announced as if changed here, where it came back in the
  // size, the theme or the columns it was left in (review of 2026-11-09);
  // with Whole paper changed, in its other unit, as the head script would.
  var shownWith = load();
  document.addEventListener('ub:settings', function (ev) { shownWith = ev.detail.all; });
  addEventListener('pageshow', function (ev) {
    if (!ev.persisted) return;
    var o = load(), was = shownWith, k, here, to;
    apply(o);
    shownWith = o;
    for (k in DEF) if (was[k] !== o[k]) announce(k, o);
    if (was.whole !== o.whole && window.ubUnit) {
      here = location.pathname + location.hash;
      to = window.ubUnit(here);
      if (to !== here) location.replace(to.replace(/#.*$/, '') + location.search + to.replace(/^[^#]*/, ''));
    }
  });

  // ◐ flips light and dark, a shortcut to the setting.
  var b = document.querySelector('.theme');
  if (b) b.addEventListener('click', function () {
    var t = load().theme;
    var dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    window.ubSettings.set('theme', dark ? 'light' : 'dark');
  });

  var gear = document.querySelector('.gear'), dlg = document.querySelector('dialog.settings');
  if (gear && dlg && dlg.showModal) {
    gear.hidden = false;
    var form = dlg.querySelector('form');
    // A menu of the browser's voices for the English, and one for each
    // translation in its language (settings.py trvoices), each shown while it
    // is ticked (Tigran, 2026-10-27).
    var bsel = form.querySelector('select[name="bvoice"]'), bopt = form.querySelector('.v-browser');
    var trvs = form.querySelector('.trvoices');
    // A browser that cannot speak is not offered its voice, nor a choice of them.
    if (bopt && !synth) {
      bopt.hidden = true;
      if (bsel) bsel.closest('label').hidden = true;
    }
    var fillVoices = function (sel, all, want) {
      sel.length = 1;
      sel.options[0].text = all.length ? T.text('Automatic: {v}', { v: all[0].name }) : T.text('Automatic');
      all.forEach(function (v) { sel.add(new Option(v.name, v.name)); });
      if (want !== undefined) sel.value = all.some(function (v) { return v.name === want; }) ? want : '';
    };
    var listVoices = function () {
      if (bsel) fillVoices(bsel, voices());
      if (!trvs) return;
      var ticked = String(load().translations || '').split(' '), m = trVoices(), any = false;
      Array.prototype.forEach.call(trvs.querySelectorAll('label[data-k]'), function (l) {
        l.hidden = ticked.indexOf(l.dataset.k) < 0;
        any = any || !l.hidden;
        fillVoices(l.querySelector('select'), voices(l.dataset.lang), m[l.dataset.k] || '');
      });
      trvs.hidden = !synth || !any;
    };
    if (trvs) trvs.addEventListener('change', function (ev) {
      var l = ev.target.closest('label[data-k]');
      if (l) window.ubSettings.setTrVoice(l.dataset.k, ev.target.value);
      resettable();
    });
    // Each control shows its setting's value; a radio group whose value has no
    // button (the voice before one is chosen) shows its first, and a menu
    // whose value is gone (a voice this device no longer has) its first.
    var fill = function () {
      listVoices();
      var o = load();
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!(el.name in DEF)) return;
        if (el.type === 'checkbox') el.checked = o[el.name] !== false;
        else if (el.type === 'radio') {
          var group = form.querySelectorAll('[name="' + el.name + '"]');
          var hit = form.querySelector('[name="' + el.name + '"][value="' + String(o[el.name]) + '"]');
          el.checked = hit ? el === hit : el === group[0];
        } else {
          el.value = String(o[el.name]);
          if (el.selectedIndex < 0) el.selectedIndex = 0;
        }
      });
      idle(o);
      trFill();
    };
    // The Translations tab (settings.py TRANSLATIONS): those shown, in the
    // reader's order, numbered, each with ↑ and ↓, then the others, by
    // language, in the order the page drew them.  A tick puts one at the end of
    // the order, or back among the others (Tigran, 2026-10-26).
    var trShown = form.querySelector('.trshown');
    var trOrder = function () {
      return String(load().translations || '').split(' ').filter(function (k) {
        return k && form.querySelector('.trlist li[data-k="' + k + '"]');
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
          if (at < 0) form.querySelector('.trother[data-lang="' + li.dataset.lang + '"]').appendChild(li);
        });
      order.forEach(function (k) { trShown.appendChild(form.querySelector('.trlist li[data-k="' + k + '"]')); });
      // A language's label goes with its list, and Other translations with the last of them.
      Array.prototype.forEach.call(form.querySelectorAll('.trother'), function (ul) {
        ul.hidden = ul.previousElementSibling.hidden = !ul.children.length;
      });
      form.querySelector('.trnone').hidden = order.length > 0;
      form.querySelector('.trothers').hidden = !form.querySelector('.trother li');
    };
    var trSet = function (order) {
      window.ubSettings.set('translations', order.join(' '));
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
    reset.addEventListener('click', function () {
      if (!window.confirm(T.text('Restore every setting to its default?'))) return;
      window.ubSettings.reset();
      fill();
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
  // phase, so first.
  if (window.ubUnit) document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a || a.origin !== location.origin) return;
    var at = a.pathname + a.hash, to = window.ubUnit(at);
    if (to !== at) a.href = to;
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
  // (#note15_3_4_0); what follows a second # is arriveTr's.
  function arrive() {
    var focus = null, m, el, i, whole = document.querySelector('article.whole');
    // At the Contents' entry again, by Back or Forward (toContents, below),
    // the place is theirs; left by a section's link, it is forgotten.
    if (contentsAt && history.state && history.state.ub === 'contents') return;
    contentsAt = null;
    try {
      m = whole && (/^#(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?(?:#.*)?$/.exec(location.hash) ||
                    /^#(?:note|fnref|fn)(?:st|tn_[a-z0-9-]+_)?(\d+)_(\d+)_(\d+)_\d+$/.exec(location.hash));
      if (m) {
        Array.prototype.forEach.call(document.querySelectorAll(HIT), function (p) { p.classList.remove('hit'); });
        for (i = +m[3]; m[3] && i <= +(m[4] || m[3]); i++) {
          el = document.getElementById(m[1] + ':' + m[2] + '.' + i);
          if (el) el.classList.add('hit');
        }
        focus = document.getElementById(m[1] + ':' + m[2] + (m[3] ? '.' + m[3] : ''));
      }
      focus = focus || (location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)))) ||
              document.querySelector('.hit');
    } catch (e) {}
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
  var HIT = 'p.t.hit, .rc p.rt.hit';
  // A search's hit in a translation, /0:1.13#tr-ud, or in a translator's
  // note, /0:5.10#notetn_ud_0_5_10_0, on the whole paper's page after the
  // place (/0#0:1.13#tr-ud): arriveTr's, and cmpHit's in columns.  Here,
  // before arrive() first runs.
  var TR_HASH = /^#(?:\d+:\d+(?:\.\d+(?:-\d+)?)?#)?(?:tr-([a-z0-9-]+)|note(tn_([a-z0-9-]+)_\d+_\d+_\d+_\d+))$/;
  ['wheel', 'touchmove', 'keydown'].forEach(function (e) {
    addEventListener(e, function () { arriveTouched = Date.now(); }, { passive: true });
  });
  arrive();
  document.addEventListener('ub:page', arrive);
  // Back on the whole paper's page from a place on it (#1:2.9, a note's
  // reference followed) to its address with no place: the marks go, and the
  // page returns to where it stood, kept in the entry's state as the place
  // was left (the click handler above), since the browser puts it back only
  // while listen.js's entries have not asked it not to (scrollRestoration).  Until 2026-11-06 arrive() ran, and scrolled to the
  // paragraph still marked.
  addEventListener('hashchange', function () {
    if (location.hash || !document.querySelector('article.whole')) return arrive();
    Array.prototype.forEach.call(document.querySelectorAll(HIT), function (p) { p.classList.remove('hit'); });
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
  var railMarkAt = null, railMarkWait = false;
  function railMark() {
    railMarkWait = false;
    var s = sectionInView(), rail = document.querySelector('.rail');
    if (!s || !rail || s === railMarkAt) return;
    // Above the text, at the Contents (toContents, below, or scrolled up by
    // hand), the mark stays on the section the reader left; only a page with
    // none marked yet takes the first.
    if (railMarkAt && s.getBoundingClientRect().top > 60) return;
    railMarkAt = s;
    // A link once clicked is in the reader's unit already (above): both are
    // compared in it.
    var want = window.ubUnit ? window.ubUnit('/' + s.id) : '/' + s.id;
    Array.prototype.forEach.call(rail.querySelectorAll('li.here > details > ol > li'), function (li) {
      var a = li.querySelector('a');
      li.classList.toggle('here', !!a && (window.ubUnit ? window.ubUnit(a.pathname + a.hash) : a.getAttribute('href')) === want);
    });
  }
  railMark();
  addEventListener('scroll', function () {
    if (railMarkWait) return;
    railMarkWait = true;
    requestAnimationFrame(railMark);
  }, { passive: true });
  document.addEventListener('ub:swap', function () { railMarkAt = null; railMark(); });

  // The left rail is the whole book (templates/_rail.html), and only the paper
  // being read comes with its sections.  Another opened there fetches its own
  // from /rail/N, asked for under the rail's version so that the browser
  // keeps them; if that fails, the paper's link is followed instead.  Listened
  // for on the document, capturing, because toggle does not bubble -- and so
  // it holds after listen.js swaps <main>.
  var railGot = {};
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
  var contentsAt = null;
  function toContents(p) {
    var b = document.querySelector('.railfold'), rail = b && b.closest('.rail'), here, shut, state;
    if (!rail) return false;
    shut = railShut(rail);
    if (phone.matches && p) {
      // Measured before the Contents open above it, as it will stand after
      // they fold again.
      state = { ub: 'contents', p: p.id, top: p.getBoundingClientRect().top, shown: !shut, href: location.href };
      if (contentsAt) history.replaceState(state, ''); else history.pushState(state, '');
      contentsAt = state;
    }
    if (shut) b.click(); else railView();
    if (phone.matches && (here = railHere(rail))) {
      scrollTo({ top: scrollY + here.getBoundingClientRect().top - innerHeight / 6, behavior: 'instant' });
      arriveTouched = Date.now();
    }
    return true;
  }
  addEventListener('popstate', function (ev) {
    var s = ev.state, was = contentsAt, rail = document.querySelector('.rail'), p;
    if (s && s.ub === 'contents') { contentsAt = s; toContents(null); return; }
    if (!was) return;
    contentsAt = null;
    // A section's link followed from the Contents fires popstate too, in
    // Chrome, for its fragment: a new address, and the place is the link's.
    // Back to the entry before is the entry's own address, which the jump
    // kept.
    if (location.href !== was.href) return;
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
  var MARKED = 'main :is(p.t.hit, p.t.named, p.t.now, .rc p.rt.hit, .rc p.rt.named, .rt.now)';
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
      if (r.height && r.top >= top && r.top < innerHeight) return { el: ms[i], y: r.top };
    }
    ps = document.querySelectorAll('main p.t[id]');
    for (i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > top + 4) { p = ps[i]; break; }
    }
    if (!p) return null;
    if (r.top >= top + 4) return { el: p, y: r.top };
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
      if (rs.length) return { el: p, node: n, at: at, y: rs[0].top };
    }
    return { el: p, y: r.top };
  }
  function placeBack(pl) {
    var y = null, q, rs;
    if (!pl || !pl.el.isConnected) return;
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
  function keepPlace(change) {
    var pl = placeNow();
    change();
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
    if (phone.matches) rail.classList.toggle('shown', shut);
    else keepPlace(function () { window.ubSettings.set('rail', shut ? 'open' : 'folded'); });
    railSync();
    if (shut) railView();
  });
  railSync();
  if (phone.addEventListener) phone.addEventListener('change', railSync);
  // A fresh load of the Contents' entry (toContents, above): here, once
  // `phone` is, which toContents asks.
  if (history.state && history.state.ub === 'contents') { contentsAt = history.state; toContents(null); }

  // The index folds (templates/_fold.html, ub.css .indexfold): its button,
  // kept as the setting 'margin' (settings.py KEPT), folds the margin to the
  // right on a wide screen, and on a phone every box of entries to its line.
  // A box's own line opens it, or folds it again, for this page only.  Folding
  // them all folds those opened too.
  function indexSync() {
    var on = load().margin !== false, b = document.querySelector('.indexfold');
    if (b) {
      b.setAttribute('aria-expanded', String(on));
      var w = on ? T.k('Fold the index away') : T.k('Show the index');
      T.attr(b, 'title', w);
      T.attr(b, 'aria-label', w);
    }
    Array.prototype.forEach.call(document.querySelectorAll('.afold'), function (x) {
      x.setAttribute('aria-expanded', String(on || x.parentNode.classList.contains('shown')));
    });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.indexfold, .afold');
    if (!b) return;
    if (b.classList.contains('indexfold'))
      return keepPlace(function () { window.ubSettings.set('margin', load().margin === false); });
    b.parentNode.classList.toggle('shown');
    indexSync();
  });
  indexSync();
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
  var TRS = [], trBy = {}, trGot = {};
  try { TRS = JSON.parse((document.getElementById('ub-translations') || {}).textContent || '[]'); } catch (e) {}
  TRS.forEach(function (x) { trBy[x.key] = x; });

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
  var tocGot = {}, tocEn = new WeakMap(), ROMAN = ['', 'I', 'II', 'III', 'IV'];
  var RE_RAILA = /^\/(?:part\/([0-9]+)|([0-9]+)(?::([0-9]+))?)$/;
  function tocTicked() {
    return String(load().translations || '').split(' ').filter(function (k) { return trBy[k]; });
  }
  function tocKey() {
    var k = load().toc || '';
    return tocTicked().indexOf(k) >= 0 ? k : '';
  }
  function tocSync() {
    var l = document.querySelector('.railtr'), sel = l && l.querySelector('select'), ks = tocTicked();
    if (!sel) return;
    l.hidden = !ks.length;
    sel.innerHTML = '<option value="">Uversa Press</option>' + ks.map(function (k) {
      return '<option value="' + k + '">' + trBy[k].label + '</option>';
    }).join('');
    sel.value = tocKey();
  }
  // Each link of `root` the rail can place by its address, in the contents
  // `d`, or the book's with none.
  function tocDraw(root, d) {
    if (!root) return;
    Array.prototype.forEach.call(root.querySelectorAll('a[href]'), function (a) {
      var m = RE_RAILA.exec(a.getAttribute('href'));
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
    if (!rail || !k) return done(null);
    if (tocGot[k]) return done(tocGot[k]);
    fetch('/rail/' + k + '?v=' + encodeURIComponent(trBy[k].toc || ''))
      .then(function (res) { if (!res.ok) throw new Error(res.status); return res.json(); })
      .then(function (d) { tocGot[k] = d; done(d); })
      .catch(function () { done(null); });
  }
  document.addEventListener('change', function (ev) {
    if (ev.target.closest && ev.target.closest('.railtr')) window.ubSettings.set('toc', ev.target.value);
  });
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'toc' || ev.detail.key === 'translations') tocApply();
  });
  document.addEventListener('ub:swap', tocApply);    // listen.js's <main>, the rail with it
  tocApply();
  function trKeys(tf) {
    var has = (tf.dataset.has || '').split(' ');
    return String(load().translations || '').split(' ').filter(function (k) {
      return trBy[k] && has.indexOf(k) >= 0;
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
  function trLines(got, k, lines) {
    var x = trBy[k], h = '', notes = '';
    Array.prototype.forEach.call(lines, function (q) {
      var t = (got.t[k] || {})[q.id], c = q.classList;
      if (t != null) h += '<p class="rt' + (c.contains('head') ? ' head' : '') + (c.contains('opening') ? ' opening' : '') +
                          '" lang="' + x.lang + '" data-k="' + k + '" data-ref="' + q.id + '">' + trLead(t) + '</p>';
      notes += (got.n[k] || {})[q.id] || '';
    });
    return { h: h, notes: notes };
  }
  // `tab`, where a search's hit names one (arriveTr), opens the fold at it in
  // place of the one last chosen, which it does not change.  Its promise is kept
  // once the fold is drawn.
  function trDraw(tf, ks, tab) {
    var panel = tf.querySelector('.tr');
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'tr';
      tf.appendChild(panel);
    }
    panel.hidden = false;
    var lines = tf.parentNode.querySelectorAll('p.t[id]'),
        refs = Array.prototype.map.call(lines, function (q) { return q.id; });
    if (!refs.length) return Promise.resolve();
    return trFetch(tf.closest('section[data-trv]'), refs[0].split('.')[0]).then(function (got) {
      if (!tf.classList.contains('open')) return;
      var want = tab || load().trtab, h = '', notes = '',
          cur = want === 'all' && ks.length > 1 ? 'all' : ks.indexOf(want) >= 0 ? want : ks[0];
      if (ks.length > 1) {
        h += '<div class="trtabs" role="group">' + ks.map(function (k) {
          return '<button type="button" data-tab="' + k + '" aria-pressed="' + (cur === k) + '">' +
                 trBy[k].label + '</button>';
        }).join('') + '<button type="button" data-tab="all" aria-pressed="' + (cur === 'all') + '">' +
                 T('All|translations') + '</button></div>';
      }
      // Each named by its short name, as its tab is: who made it, in full,
      // would take two lines on a phone, and Settings says it (Tigran,
      // 2026-10-26).
      (cur === 'all' ? ks : [cur]).forEach(function (k) {
        var x = trBy[k];
        if (cur === 'all' || ks.length === 1) h += '<p class="who">' + x.label + '</p>';
        // Every one the fold counts is in the fragment the server sends, so one
        // missing is offline, and not kept in the copy.
        if (!got.t[k]) return (h += '<p class="gap">' + T('tr:notkept') + '</p>');
        var w = trLines(got, k, lines);
        h += w.h;
        notes += w.notes;
      });
      if (card && panel.contains(card.mark)) shut(false);
      panel.innerHTML = h + (notes && '<div class="tnotes" hidden>' + notes + '</div>');
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
    tf.classList.remove('open');
    var b = tf.querySelector('.trfold'), panel = tf.querySelector('.tr');
    if (b) b.setAttribute('aria-expanded', 'false');
    if (panel) panel.hidden = true;
  }
  function trSync() {
    Array.prototype.forEach.call(document.querySelectorAll('.tf'), function (tf) {
      var ks = trKeys(tf), b = tf.querySelector('.trfold');
      if (!b) return;
      b.innerHTML = ks.length ? T('{n} translations', { n: ks.length }) : '';
      if (!tf.classList.contains('open')) return;
      if (ks.length) trDraw(tf, ks); else trShut(tf);
    });
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.trfold, .trtabs button'), tf = b && b.closest('.tf');
    if (!tf) return;
    if (b.classList.contains('trfold')) {
      if (tf.classList.contains('open')) return trShut(tf);
      tf.classList.add('open');
      b.setAttribute('aria-expanded', 'true');
      return trDraw(tf, trKeys(tf));
    }
    window.ubSettings.set('trtab', b.dataset.tab);
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
  window.ubTrRead = function (ref, k, open) {
    var art = cmpArt(), q = ref && document.getElementById(ref), row = q && q.closest('.row');
    var tf = row && row.querySelector('.tf');
    var pick = function (root) { return root && root.querySelector('p.rt[data-k="' + k + '"][data-ref="' + ref + '"]'); };
    var shutMine = function () {
      if (trMine && trMine !== tf && trMine.classList.contains('open')) trShut(trMine);
      if (trMine !== tf) trMine = null;
    };
    if (!k) {
      tf = null;
      shutMine();
      return Promise.resolve(null);
    }
    if (art && art.classList.contains('cmp')) {
      // A heading: the page's one section's (ref null), or on the whole paper's
      // page the section the ref names (listen.js isHead).
      var sec = ref && ref.indexOf('.') < 0 ? q : null;
      if (!ref || sec) return Promise.resolve((sec || art).querySelector('header.ch[data-k="' + k + '"]'));
      return Promise.resolve(pick(row));
    }
    if (!tf) return Promise.resolve(null);
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
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'translations' || ev.detail.key === 'trtab') trSync();
  });
  document.addEventListener('ub:swap', trSync);
  document.addEventListener('ub:trkept', function () { trGot = {}; trSync(); cmpDraw(); });
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

  // Compare (ROADMAP item 15, step 2; settings.py `compare`, Translations in
  // parallel columns): the page drawn again, the English and each translation
  // ticked side by side, a column each in the reader's order, a row to a
  // paragraph, which the grid aligns as it aligns a paragraph and its entries
  // (ub.css article.cmp); below 62rem each translation stands under its
  // paragraph.  A translation with no paragraph in the section has no column.
  // Over the columns a line naming each, which stays at the window's top while
  // they are in view, and under it each one's own paper and section titles, as
  // its TeX sets them (/tr/'s data-head).  Drawn from the fragment the folds
  // fetch, and again whenever what it shows changes.
  //
  // A setting since 2026-11-08 (Tigran), kept as every setting is, so that
  // every page of the book opens in it while it is on, and drawn in place,
  // the paragraph at the window's top kept there, as it is turned on or off.
  // Until then a toggle at the head of the text, at an address of its own,
  // /1:1/compare, which the tab kept as one moved about (2026-11-06); those
  // addresses go to the page's own now (app.py read_compare).  The head
  // script's class .compare hides the folds before first paint (ub.css).  In a
  // section none of the ticked translations has, the page reads as usual.  A
  // part's page draws nothing here: every translation's divider is in the
  // page, and the setting alone lays them in columns (part.html, ub.css
  // .dividers).
  var cmpN = 0;
  function cmpOn() { return load().compare === true; }
  function cmpArt() { return document.querySelector('main.reader > article'); }
  // The ticked translations that have any paragraph here, in the reader's order.
  function cmpKeys(art) {
    var has = {};
    Array.prototype.forEach.call(art.querySelectorAll('.tf[data-has]'), function (tf) {
      tf.dataset.has.split(' ').forEach(function (k) { has[k] = true; });
    });
    return String(load().translations || '').split(' ').filter(function (k) { return trBy[k] && has[k]; });
  }
  function cmpUndraw(art) {
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
    art.classList.remove('cmp');
    art.style.removeProperty('--cols');
  }
  // Draws what Settings say; its promise is kept once drawn.
  function cmpDraw() {
    var art = cmpArt(), on = cmpOn(), n = ++cmpN;
    // The folds give way, or come back (ub.css :root.compare): the head
    // script set it before first paint, and here it follows the setting, once
    // cmpGo has measured the paragraph to keep.
    document.documentElement.classList.toggle('compare', on);
    if (!art) return Promise.resolve();
    var ks = on ? cmpKeys(art) : [], secs = art.querySelectorAll('section[data-trv]');
    if (!ks.length || !secs.length) { cmpUndraw(art); return Promise.resolve(); }
    // Each section of the page in columns: the one of a section's page, or
    // every one of the whole paper's (paper.html), each with the names of
    // the columns over it, which stay at the window's top while it is in
    // view, and its own heads: the paper's over the first, and each
    // section's title over its own.  `got` is a section's /tr/ fragment, or
    // null where it could not be had.
    var draw = function (gots) {
      if (n !== cmpN || !art.isConnected) return;
      cmpUndraw(art);
      // The folds' words go, so that no note's number stands twice.
      Array.prototype.forEach.call(art.querySelectorAll('.tf.open'), trShut);
      Array.prototype.forEach.call(art.querySelectorAll('.tf .tr'), function (el) { el.remove(); });
      art.classList.add('cmp');
      art.style.setProperty('--cols', ks.length + 1);
      Array.prototype.forEach.call(secs, function (sec, j) {
        var failed = !gots[j], got = gots[j] || { t: {}, n: {}, h: {} }, grid = sec.querySelector('.grid'),
            top = sec.querySelector(':scope > .papertop') || art.querySelector(':scope > .papertop');
        if (!grid || !top) return;
        // A column's name, as Settings names a translation, and over the English
        // the book's own title, which no language translates.
        var names = '<div class="row cmpnames"><p class="cn" style="--c:1" lang="en"><b>The Urantia Book</b> (Uversa Press)</p>',
            heads = '<div class="row cmphd">';
        ks.forEach(function (k, i) {
          var x = trBy[k], g = got.h[k] || {}, c = ' style="--c:' + (i + 2) + '"', paper = j === 0;
          names += '<p class="cn"' + c + '><b lang="' + x.lang + '">' + x.title + '</b> <span class="nobreak">(' + x.label + ')</span></p>';
          heads += '<header class="papertop ch"' + c + ' data-k="' + k + '" lang="' + x.lang + '"><p class="who">' + x.label + '</p>' +
                   (paper && g.paper ? '<p class="papernum">' + g.paper + '</p>' : '') + (paper && g.title ? '<h1>' + g.title + '</h1>' : '') +
                   (paper && g.author ? '<p class="author">' + g.author + '</p>' : '') + (g.section ? '<h2>' + g.section + '</h2>' : '') +
                   // Every one counted is in the fragment the server sends, so one
                   // missing is offline, and not kept in the copy.
                   (got.t[k] ? '' : '<p class="gap">' + T(failed ? 'tr:unreachable' : 'tr:notkept') + '</p>') + '</header>';
        });
        grid.insertAdjacentHTML('afterbegin', names + '</div>' + heads + '</div>');
        var en = top.cloneNode(true);
        en.classList.add('ch');
        en.style.setProperty('--c', 1);
        grid.querySelector('.cmphd').prepend(en);
        Array.prototype.forEach.call(grid.children, function (row) {
          if (row.classList.contains('stars')) {
            row.insertAdjacentHTML('beforeend', ks.map(function (k, i) {
              return '<i class="rs" style="--c:' + (i + 2) + '" data-stars="' + row.dataset.stars + '" aria-hidden="true"></i>';
            }).join(''));
            return;
          }
          var text = row.querySelector(':scope > p.t, :scope > .verse');
          if (!text) return;
          var lines = row.querySelectorAll('p.t[id]');
          text.insertAdjacentHTML('afterend', ks.map(function (k, i) {
            var x = trBy[k], w = trLines(got, k, lines);
            return '<div class="rc" style="--c:' + (i + 2) + '" data-k="' + k + '" lang="' + x.lang + '">' +
                   (w.h && '<p class="who">' + x.label + '</p>' + w.h) +
                   (w.notes && '<div class="tnotes" hidden>' + w.notes + '</div>') + '</div>';
          }).join(''));
        });
      });
      cmpHit();
      // listen.js puts each translation's ▶ in its cells.
      document.dispatchEvent(new CustomEvent('ub:cmp', { detail: art }));
    };
    return Promise.all(Array.prototype.map.call(secs, function (sec) {
      return trFetch(sec, sec.id).then(function (got) { return got; }, function () { return null; });
    })).then(draw);
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
  // The paragraph at the window's top, kept there as the page is drawn again,
  // from its start, below the columns' names; at the page's head, the head.  A
  // paragraph is its row, with its translations under it on a phone.
  function cmpGo() {
    var at = null, rows = document.querySelectorAll('main .grid > .row:has(p.t[id])'), i, r;
    if (scrollY > 0)
      for (i = 0; i < rows.length; i++)
        if ((r = rows[i].getBoundingClientRect()).bottom > 40) { at = { el: rows[i].querySelector('p.t[id]'), top: r.top }; break; }
    return cmpDraw().then(function () {
      var row = at && at.el.isConnected && at.el.closest('.row'), names = document.querySelector('article.cmp .cmpnames'),
          floor = names && names.offsetHeight;
      if (row) scrollBy({ top: row.getBoundingClientRect().top - Math.max(floor || 0, Math.min(at.top, 120)), behavior: 'instant' });
    });
  }
  // Opened with it on: drawn, then the paragraph cited brought into view
  // again, as the rows have changed height, unless the reader has
  // scrolled meanwhile (by hand: the fonts coming in move the page too, and
  // the whole paper's columns take a while); and a translator's note's card
  // opened from its column.
  function cmpArrive() {
    if (!cmpOn()) return;
    var t = Date.now();
    cmpDraw().then(function () {
      if (arriveTouched <= t) arrive();
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
    if (drawn && cmpOn()) drawn.then(function () { if (arriveTouched <= t) arrive(); });
  });
  // Once for both settings, where ↺ announces every setting in turn: a second
  // cmpGo measured the page the first had just undrawn, and undid the place
  // it kept (review of 2026-11-09).
  var cmpSoon = false;
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key !== 'translations' && ev.detail.key !== 'compare' || cmpSoon) return;
    cmpSoon = true;
    Promise.resolve().then(function () { cmpSoon = false; cmpGo(); });
  });
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
  // a note's card, the offline menu's words; and a title set later is moved
  // to data-tip, the folds' and the cloud's as they change.  Watched only
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

  // The flags at the header's corner (base.html .langs): the interface in
  // English or in Russian, kept as the setting 'lang' (settings.py KEPT).
  // Shown only while the site draws both.
  var langs = document.querySelector('.top .langs');
  function flags() {
    if (!langs) return;
    var now = T.lang();
    each.call(langs.querySelectorAll('.flag'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.to === now));
    });
  }
  if (langs && T.bilingual) {
    langs.hidden = false;
    flags();
    langs.addEventListener('click', function (ev) {
      var b = ev.target.closest('.flag');
      if (b) window.ubSettings.set('lang', b.dataset.to);
    });
  }

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
    card = { mark: mark, el: el, host: host };
    mark.classList.add('on');
    mark.setAttribute('aria-expanded', 'true');
    place();
    el.focus({ preventScroll: true });
  }
  document.addEventListener('click', function (ev) {
    var t = ev.target, mark = t.closest && t.closest('a.fn');
    if (mark) {
      var again = card && card.mark === mark;
      hideHead();
      shut(false);
      if (again || open(mark) !== false) ev.preventDefault();
      return;
    }
    if (!card) { if (!tapHead(ev)) tapTurn(ev); return; }
    if (card.el.contains(t)) { if (t.closest('.x')) shut(true); return; }
    shut(false);
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    if (card) shut(true); else hideHead();
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
  // that is open, which stays.
  var PV = /^\/(\d+):(\d+)\.(\d+)(?:-(\d+))?$/, pv = null, pvSeq = 0, pvTimer = 0, pvHide = 0, pvPages = {};
  function pvOn() { return document.documentElement.dataset.preview === 'true'; }
  function pvLink(t) {
    var a = t && t.closest && t.closest('a[href]'), m, c;
    if (!a || a.closest('.pop.pv')) return null;
    m = PV.exec(a.getAttribute('href') || '');
    if (!m) return null;
    // In a translator's note's card, or a translation's cell: that translation's
    // paragraph (Tigran, 2026-11-07: a reader of a translation expects it).
    c = a.closest('[data-tr], p.rt[data-k]');
    return { a: a, p: m[1], s: m[2], n: +m[3], last: m[4] ? +m[4] : +m[3], tr: c ? (c.dataset.tr || c.dataset.k) : '' };
  }
  function pvPage(p, s) {
    var url = '/' + p + ':' + s;
    if (document.getElementById(p + ':' + s + '.1')) return Promise.resolve(document);
    if (!pvPages[url]) pvPages[url] = fetch(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return r.text();
    }).then(function (h) { return new DOMParser().parseFromString(h, 'text/html'); })
      .catch(function (e) { delete pvPages[url]; throw e; });
    return pvPages[url];
  }
  function pvParas(doc, r) {
    var out = [], n, p;
    for (n = r.n; n <= Math.min(r.last, r.n + 5); n++) {
      p = doc.getElementById(r.p + ':' + r.s + '.' + n);
      if (!p) break;
      p = p.cloneNode(true);
      p.removeAttribute('id');
      p.className = p.classList.contains('verse') ? 'verse' : '';
      Array.prototype.forEach.call(p.querySelectorAll('.stk, .pcm, a.fn'), function (x) { x.remove(); });
      out.push(p);
    }
    return out;
  }
  // A translation's words for the paragraphs, each with its language, as far
  // as it has them from the first; none where it lacks the first, and the
  // English stands in.
  function pvTrParas(got, r) {
    var out = [], n, h, p;
    for (n = r.n; n <= Math.min(r.last, r.n + 5); n++) {
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
    var seq = pvSeq, ref = r.p + ':' + r.s + '.' + r.n + (r.last > r.n ? '-' + r.last : ''),
        sec = document.querySelector('section[id="' + r.p + ':' + r.s + '"]'),
        words = r.tr && trBy[r.tr]
          ? trFetch(sec, r.p + ':' + r.s).then(function (got) { return pvTrParas(got, r); }, function () { return []; })
          : Promise.resolve([]);
    words.then(function (ps) {
      if (ps.length) return { ps: ps, tr: r.tr };
      return pvPage(r.p, r.s).then(function (doc) { return { ps: pvParas(doc, r), tr: '' }; });
    }).then(function (got) {
      if (seq !== pvSeq || !document.contains(r.a)) return;
      var ps = got.ps, host, el, body;
      if (!ps.length) return;
      host = r.a.closest('article') || r.a.closest('main.results') || document.body;
      el = document.createElement('div');
      el.className = 'pop pv';
      el.setAttribute('role', 'dialog');
      el.setAttribute('aria-label', ref);
      el.tabIndex = -1;
      el.innerHTML = '<span class="arrow"></span>' +
        '<button type="button" class="x" ' + T.a('aria-label', 'Close') + '>×</button>' +
        '<div class="body"><p class="pvref"><a href="/' + ref + '">' + ref + (r.last > r.n + 5 ? ' …' : '') + '</a>' +
        (got.tr ? ' <span class="pvtr">' + trBy[got.tr].label + '</span>' : '') + '</p></div>';
      body = el.querySelector('.body');
      ps.forEach(function (p) { body.appendChild(p); });
      host.appendChild(el);
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
  // Android app sends as Page Down.  With Settings' "Tap to turn the page", a
  // tap on the text goes on in the lower half of the screen and back in the
  // upper, less the band at the top, which the running head takes (tapHead,
  // below).  A screen is what the window shows, less a line: the last whole line
  // comes to the top, and going back, the first whole line to the bottom, so
  // that no line the reader picks up at is cut.
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
    var col = document.querySelector('main p.t'), pl = document.querySelector('.player'),
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
  // Only a finger's tap, or a pen's: a mouse's click selects words.  And the
  // selection as it stood before the tap, which the browser clears before the
  // tap's click (tapHead, below).
  document.addEventListener('pointerdown', function (ev) {
    touch = ev.pointerType !== 'mouse';
    selDown = !getSelection().isCollapsed;
  }, { passive: true });
  function tapTurn(ev) {
    var t = ev.target;
    if (document.documentElement.dataset.tappage !== 'true' || !touch || ev.button ||
        !t.closest || !t.closest('main') || !getSelection().isCollapsed ||
        t.closest('a, button, input, select, textarea, label, summary, nav, .rail, .a, .tf, .blanket, .marginhead, .player')) return;
    if (turn(ev.clientY < innerHeight / 2 ? -1 : 1)) ev.preventDefault();
  }

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
  // covers the text while reading.  With Tap to turn the page on, a tap turns,
  // and only the band at the window's top summons the head, naming the first
  // paragraph on the screen, as a verso's head does.  Never a tap while words
  // are selected: the long press is the system's, with its Copy and Web
  // search, and since the browser clears the selection before the tap's
  // click, it is read at pointerdown (selDown, above).  Built here from what
  // the page carries, on <body>, which listen.js never swaps.
  var head = null, headP = null, headAt = 0, headSlack = 56, BAND = 3.2;
  function clampY() {
    return Math.max(0, Math.min(scrollY, document.documentElement.scrollHeight - innerHeight));
  }
  // The paragraph tapped.  In columns a translation's own (p.rt), tinted
  // alone, never the English beside it (Tigran, 2026-11-08), and its cell's
  // first where the tap was in the cell but on none, on its name; the English
  // one of the row where it was on neither.
  function paraOf(t) {
    var cell, row;
    if (!t.closest) return null;
    return t.closest('p.t[id], .rc p.rt') ||
           ((cell = t.closest('.rc')) && cell.querySelector('p.rt')) ||
           ((row = t.closest('.grid > .row')) && row.querySelector('p.t[id]')) || null;
  }
  // The first paragraph on the screen: a verso's running head.
  function firstOnScreen() {
    var ps = document.querySelectorAll('main p.t[id]'), r;
    for (var i = 0; i < ps.length; i++) {
      r = ps[i].getBoundingClientRect();
      if (r.height && r.bottom > 0) return ps[i];
    }
    return ps[0] || null;
  }
  // The paper's head for a paragraph: the article's own, with the title (the
  // whole paper's sections have heads of their own, each the section's title
  // alone), or on a reading path the running head before the paragraph, which
  // names the paper and its title and no author.
  function headOf(p) {
    var top = document.querySelector('main article > header.papertop'), rhs, rh = null, i;
    if (top && top.querySelector('h1')) {
      return { num: top.querySelector('.papernum') ? top.querySelector('.papernum').innerHTML : '',
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
    // A translation's paragraph is kept for Back by its row's English one,
    // which has the id.
    ref.addEventListener('click', function () {
      var p = headP;
      hideHead();
      toContents(p && (p.id ? p : document.getElementById(p.dataset.ref)));
    });
    head.insertBefore(ref, head.firstChild);
    // Home and the gear together at the right: the site's mark, the header's
    // own drawing, as a link to the home page; and the gear.
    ctl = document.createElement('span');
    ctl.className = 'ctl';
    home = document.createElement('a');
    home.className = 'home';
    home.href = '/';
    T.attr(home, 'title', 'Home');
    T.attr(home, 'aria-label', 'Home');
    if (logo) home.appendChild(logo.cloneNode(true));
    ctl.appendChild(home);
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'set';
    T.attr(btn, 'aria-label', 'Settings');
    T.attr(btn, 'title', 'Settings');
    if (gear && gear.querySelector('svg')) btn.appendChild(gear.querySelector('svg').cloneNode(true));
    ctl.appendChild(btn);
    head.appendChild(ctl);
    // The header's gear opens the dialog, and its click hides the head (below);
    // never focused first, or the dialog would give the focus back to the
    // header on closing and scroll a long page to its top.
    btn.addEventListener('click', function () { if (gear) gear.click(); else hideHead(); });
    head.addEventListener('click', function (ev) { if (!ev.target.closest('a, button')) hideHead(); });
    document.body.appendChild(head);
  }
  function showHead(p) {
    var h;
    if (!p) return;
    if (!head) buildHead();
    h = headOf(p);
    if (headP) headP.classList.remove('named');
    headP = p;
    p.classList.add('named');
    head.querySelector('.ref').textContent = p.id || p.dataset.ref;
    head.querySelector('.pn').innerHTML = h.num + '<span class="tt"></span>';
    head.querySelector('.tt').textContent = h.title;
    head.querySelector('.au').textContent = h.author;
    head.hidden = false;
    headAt = clampY();
    headSlack = 2 * (parseFloat(getComputedStyle(p).lineHeight) || 28);
    // A tap is a touch of the page: arrive()'s late scroll must not undo it.
    arriveTouched = Date.now();
  }
  function hideHead() {
    clearTimeout(headSoon);
    headSoon = 0;
    if (headP) headP.classList.remove('named');
    headP = null;
    if (head) head.hidden = true;
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
  // playing starts: one thing on the page is marked.
  function unhit() {
    Array.prototype.forEach.call(document.querySelectorAll(HIT), function (p) { p.classList.remove('hit'); });
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
    var t = ev.target, tap, band, p;
    if (ev.button || (ev.detail > 1 && !touch) || selDown || !t.closest || !t.closest('main') || !getSelection().isCollapsed ||
        t.closest('a, button, input, select, textarea, label, summary, nav, .rail, .a, .tf, .cites, .blanket, .marginhead, .player, .pop, dialog') ||
        !document.querySelector('main p.t[id]')) return false;
    if (!touch && (!head || head.hidden)) {
      clearTimeout(headSoon);
      p = paraOf(t);
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
    tap = document.documentElement.dataset.tappage === 'true' && touch;
    band = ev.clientY < BAND * parseFloat(getComputedStyle(document.documentElement).fontSize);
    if (head && !head.hidden) { hideHead(); return !tap || band; }
    if (tap && !band) return false;
    showHead(tap ? firstOnScreen() : paraOf(t) || firstOnScreen());
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
  if (gear) gear.addEventListener('click', hideHead);

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
  document.addEventListener('copy', function () {
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

  // Work offline, at the header's corner where a service worker can run: an
  // icon that says whether this page is online or offline, and whether a copy
  // is kept (ub.css .top .offline), and opens Settings at its Offline tab,
  // which says what the copy is (base.html; until 2026-10-30 a menu of its
  // own, #offmenu, under the icon, and until 2026-10-14 a switch in Settings).
  // static/offline.js runs the tab, and says what the copy is on the icon,
  // then 'ub:offline'.  It is loaded on every page since 2026-11-10 (Tigran:
  // every browser keeps the copy, and reads the site from it): at once on a
  // page the worker answers for, to say whether its copy is still the site's;
  // on any other once the page has loaded and the browser is idle, to
  // register the worker and fetch the copy; and when the tab opens.  The
  // browser's own offer to install the site waits in the tab too, rather than
  // in a banner of its own.
  var cloud = document.querySelector('.top .offline'), offpanel = document.querySelector('dialog.settings .panel.offline');
  if (cloud && offpanel && 'serviceWorker' in navigator && window.isSecureContext &&
      window.HTMLDialogElement && 'showModal' in HTMLDialogElement.prototype) {
    cloud.hidden = false;
    // And Settings' tab for it: the tab and its panel.
    document.querySelectorAll('dialog.settings .offline').forEach(function (el) { el.hidden = false; });
    // Offline (data-net) is the site out of reach: the browser says so, or the
    // worker answered for this page from its copy because the network did not,
    // which sw.js writes on the footer (a page it answers first, online, is
    // the server's as it is, unmarked); after that, as the browser says, and as the worker's check of
    // the site says, which offline.js writes on the icon.  Each time the
    // browser speaks, offline.js asks at once whether the site is there, and
    // where the page starts offline: the site's answer is the last word, as
    // Chrome can say offline with the network working (2026-10-27).
    var fromCopy = document.querySelector('footer[data-copy]'), loaded = false;
    // Which site this is, on the tab's first line: the same build is at
    // ubsite.ddns.net and ubsite.sigmaai.au (and under the name in the header,
    // which base.html's head script writes).
    offpanel.querySelector('.net .host').textContent = location.host;
    // What offline.js says of the copy is cloud.ubSay, its words in each
    // language; the date sw.js writes on the footer is in each too.
    var label = function () {
      var on = cloud.dataset.net === 'on', none = cloud.dataset.have === 'none';
      var t = !on ? (none ? T.k('Offline') : T.k('Offline: reading the copy kept in this browser'))
            : cloud.ubSay || (none ? T.k('Online') : T.k('Online, with a copy kept for working offline'));
      T.attr(cloud, 'title', t);
      T.attr(cloud, 'aria-label', t);
      offpanel.querySelector('.net .conn').innerHTML = on ? T('Online') : !fromCopy ? T('Offline')
        : T('Offline · the copy of {d}', { d: { en: T.esc(fromCopy.dataset.copy),
                                                ru: T.esc(fromCopy.dataset.copyRu || fromCopy.dataset.copy) } });
    };
    var net = function (on) { cloud.dataset.net = on ? 'on' : 'off'; label(); };
    var script = function () {
      if (loaded) return;
      loaded = true;
      var sc = document.createElement('script');
      sc.src = cloud.dataset.src;
      document.head.appendChild(sc);
    };
    cloud.dataset.have = navigator.serviceWorker.controller ? 'kept' : 'none';
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
    // A tap on the icon opens Settings at that tab, as the gear opens Settings.
    cloud.addEventListener('click', function () {
      var gearBtn = document.querySelector('.gear'), tab = document.getElementById('set-t-offline');
      if (gearBtn && tab) { gearBtn.click(); tab.click(); }
    });
  }

  // Help, and the tour (static/help.js; Tigran, 2026-11-06).  The ? at the
  // corner is a menu (below; a link to /help until 2026-11-10); its data-src
  // is the tour's script, loaded here when the tour is due: never seen in this browser (localStorage
  // ub_tour), or a step kept for this tab (sessionStorage).  Not on /help,
  // which loads it itself, nor on the quiz's pages, whose keys 1-9 and Enter
  // are their own, nor on the API's page, the stats or the board, nor where
  // #listen starts the player as the page loads.  The script waits for
  // Settings or What's new to close, and for the page to be visible.
  var helpLink = document.querySelector('.top .help'), tourDue = false;
  try { tourDue = !!sessionStorage.getItem('ub_tour') || localStorage.getItem('ub_tour') !== 'seen'; } catch (e) {}
  if (helpLink && helpLink.dataset.src && tourDue && !/^\/(help$|quiz|api$|stats$)/.test(location.pathname) &&
      location.hash !== '#listen') {
    var hs = document.createElement('script');
    hs.src = helpLink.dataset.src;
    document.head.appendChild(hs);
  }

  // The ?'s menu (base.html; Tigran, 2026-11-10): a <details>, which the
  // browser opens and shuts at its mark; shut here by Escape, by a tap
  // anywhere else, and by one of its items.  Help is a link.  What's new? is
  // offline.js's dialog, what the last update brought, where Work offline can
  // run (the cloud shown), asked for by 'ub:news', which the cloud's block
  // above hears; elsewhere the link goes on to the changelog.  About is a
  // small window drawn here, as What's new's is drawn: what the site is, and
  // where its source is kept.
  if (helpLink && helpLink.tagName === 'DETAILS') {
    var shutHelp = function () { helpLink.open = false; };
    document.addEventListener('click', function (ev) {
      if (helpLink.open && !helpLink.contains(ev.target)) shutHelp();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape' || !helpLink.open) return;
      shutHelp();
      helpLink.querySelector('summary').focus();
    });
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
      } else if (a.classList.contains('whatsnew') && cloud && !cloud.hidden) {
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

  window.addEventListener('beforeinstallprompt', function (ev) {
    ev.preventDefault();
    window.ubInstall = ev;
    document.dispatchEvent(new Event('ub:installable'));
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
