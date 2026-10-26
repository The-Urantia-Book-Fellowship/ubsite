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
  function announce(k, o) {
    document.dispatchEvent(new CustomEvent('ub:settings', { detail: { key: k, all: o } }));
  }
  // The browser's own voices (Web Speech), English ones, best first: an online
  // voice (Google's in Chrome, Microsoft's "Natural" ones in Edge) or Apple's
  // Premium and Enhanced ones sound better than the rest, and the book is
  // American.  Not macOS's novelty voices.  The list can be empty until the
  // browser's voiceschanged.
  var synth = window.speechSynthesis;
  var NOVELTY = /^(Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox)\b/;
  function score(v) {
    return (/natural|neural|premium|enhanced|online/i.test(v.name) ? 4 : 0) +
           (/^Google/.test(v.name) ? 2 : 0) + (/^en[-_]US/i.test(v.lang) ? 1 : 0) + (v.default ? 0.5 : 0);
  }
  function voices() {
    if (!synth) return [];
    return synth.getVoices().filter(function (v) {
      return /^en([-_]|$)/i.test(v.lang) && !NOVELTY.test(v.name);
    }).sort(function (a, b) { return score(b) - score(a) || (a.name < b.name ? -1 : 1); });
  }

  // The voices that can speak now.  Offline, this device's own: Chrome's Google
  // voices and Edge's Natural ones are spoken by a server, and fall silent
  // without it.
  function usable() {
    var all = voices();
    if (navigator.onLine === false) {
      var here = all.filter(function (v) { return v.localService; });
      if (here.length) all = here;
    }
    return all;
  }

  window.ubSettings = {
    voices: voices,
    // What the player's list of voices offers (listen.js).
    usable: usable,
    // The browser voice Settings names, else the best there is; null with none.
    voice: function () {
      var all = usable(), want = load().bvoice;
      return all.filter(function (v) { return v.name === want; })[0] || all[0] || null;
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
    var bsel = form.querySelector('select[name="bvoice"]'), bopt = form.querySelector('.v-browser');
    // A browser that cannot speak is not offered its voice, nor a choice of them.
    if (bopt && !synth) {
      bopt.hidden = true;
      if (bsel) bsel.closest('label').hidden = true;
    }
    var listVoices = function () {
      if (!bsel) return;
      var all = voices();
      bsel.length = 1;
      bsel.options[0].text = all.length ? T.text('Automatic: {v}', { v: all[0].name }) : T.text('Automatic');
      all.forEach(function (v) { bsel.add(new Option(v.name, v.name)); });
    };
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
      trFill();
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
    // or, where it needs a value (data-is), any other.
    var idle = function (o) {
      Array.prototype.forEach.call(form.querySelectorAll('[data-needs]'), function (el) {
        var v = o[el.dataset.needs];
        var off = el.dataset.is ? String(v) !== el.dataset.is : v === 'off' || v === false;
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

  // Bring the page's focus into view.  /61:7.18 renders the whole of 61:7 with
  // paragraph 18 marked .hit, and nothing in the address says where to scroll
  // -- a #fragment would, but then the permalink would stop being the
  // citation.  A margin chip opens /i/god#e…, which the browser scrolls to
  // itself.  Either way, scroll once more when the fonts are in: UB Goudy
  // loads with font-display: swap, the text reflows, and the first scroll
  // drifts.  Not if the reader has scrolled meanwhile.  Again whenever
  // listen.js brings a page in while it plays ('ub:page').  A fragment that
  // names no element -- #note…, a 1955 reading found by search -- leaves the
  // paragraph marked .hit as the focus.
  function arrive() {
    var focus = null;
    try {
      focus = (location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)))) ||
              document.querySelector('.hit');
    } catch (e) {}
    if (!focus) return;
    focus.scrollIntoView({ block: 'start' });
    var y = window.scrollY;
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      if (window.scrollY === y) focus.scrollIntoView({ block: 'start' });
    });
  }
  arrive();
  document.addEventListener('ub:page', arrive);

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
    var n = a.getAttribute('href').slice(1);
    var put = function (html) { if (!d.querySelector('ol')) d.insertAdjacentHTML('beforeend', html); };
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
  function railView() {
    var rail = document.querySelector('.rail'), here = rail && rail.querySelector('li.here');
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
    shut = railShut(b.parentNode);
    b.setAttribute('aria-expanded', String(!shut));
    var w = shut ? T.k('Show the contents') : T.k('Fold the contents away');
    T.attr(b, 'title', w);
    T.attr(b, 'aria-label', w);
  }
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('.railfold'), rail, shut;
    if (!b) return;
    rail = b.parentNode;
    shut = railShut(rail);
    if (phone.matches) rail.classList.toggle('shown', shut);
    else window.ubSettings.set('rail', shut ? 'open' : 'folded');
    railSync();
    if (shut) railView();
  });
  railSync();
  if (phone.addEventListener) phone.addEventListener('change', railSync);

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
    if (b.classList.contains('indexfold')) return window.ubSettings.set('margin', load().margin === false);
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
  // are put hidden with its paragraph's.  Offline the fetch fails, until the
  // copy holds them: a download of their own, to come (Tigran, 2026-10-26).
  var TRS = [], trBy = {}, trGot = {};
  try { TRS = JSON.parse((document.getElementById('ub-translations') || {}).textContent || '[]'); } catch (e) {}
  TRS.forEach(function (x) { trBy[x.key] = x; });
  function trKeys(tf) {
    var has = (tf.dataset.has || '').split(' ');
    return String(load().translations || '').split(' ').filter(function (k) {
      return trBy[k] && has.indexOf(k) >= 0;
    });
  }
  function trFetch(art, sec) {
    var v = (art && art.dataset.trv) || '', key = sec + '?' + v;
    if (!trGot[key]) {
      trGot[key] = fetch('/tr/' + sec + '?v=' + encodeURIComponent(v))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (h) {
          var t = document.createElement('template'), got = { t: {}, n: {} };
          t.innerHTML = h;
          Array.prototype.forEach.call(t.content.querySelectorAll('[data-k][data-ref]'), function (d) {
            (got.t[d.dataset.k] = got.t[d.dataset.k] || {})[d.dataset.ref] = d.innerHTML;
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
  function trDraw(tf, ks) {
    var panel = tf.querySelector('.tr');
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'tr';
      tf.appendChild(panel);
    }
    panel.hidden = false;
    var lines = tf.parentNode.querySelectorAll('p.t[id]'),
        refs = Array.prototype.map.call(lines, function (q) { return q.id; });
    if (!refs.length) return;
    trFetch(tf.closest('article'), refs[0].split('.')[0]).then(function (got) {
      if (!tf.classList.contains('open')) return;
      var want = load().trtab, h = '', notes = '',
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
        // A heading in the text (0:12.10) is centred, and a paper's first
        // paragraph drops its first letter, as the English's do and each
        // translation's own TeX does (\lettrine).
        refs.forEach(function (ref, i) {
          var t = (got.t[k] || {})[ref], c = lines[i].classList;
          if (t != null) h += '<p class="rt' + (c.contains('head') ? ' head' : '') + (c.contains('opening') ? ' opening' : '') +
                              '" lang="' + x.lang + '">' + trLead(t) + '</p>';
          notes += (got.n[k] || {})[ref] || '';
        });
      });
      if (card && panel.contains(card.mark)) shut(false);
      panel.innerHTML = h + (notes && '<div class="tnotes" hidden>' + notes + '</div>');
    }, function () {
      if (tf.classList.contains('open')) panel.innerHTML = '<p class="gap">' + T('tr:unreachable') + '</p>';
    });
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
  trSync();
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'translations' || ev.detail.key === 'trtab') trSync();
  });
  document.addEventListener('ub:swap', trSync);
  function swapped() { railSync(); indexSync(); }
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
      shut(false);
      if (again || open(mark) !== false) ev.preventDefault();
      return;
    }
    if (!card) { tapTurn(ev); return; }
    if (card.el.contains(t)) { if (t.closest('.x')) shut(true); return; }
    shut(false);
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && card) shut(true);
  });
  window.addEventListener('resize', place);
  document.addEventListener('ub:swap', function () { card = null; });

  // Turning the page (Tigran, 2026-10-20).  A phone's volume keys never reach a
  // web page: Chrome keeps them for the system (ContentUiEventHandler's
  // shouldPropagateKeyEvent), and Safari has no such event.  So where the
  // book's text is, Space, Page Down and → go on a screen, and Shift+Space,
  // Page Up and ← back: from a keyboard, a page turner, or volume keys an
  // Android app sends as Page Down.  With Settings' "Tap to turn the page", a
  // tap on the text goes on in the lower half of the screen and back in the
  // upper.  A screen is what the window shows, less a line: the last whole line
  // comes to the top, and going back, the first whole line to the bottom, so
  // that no line the reader picks up at is cut.
  var EDGE = 6, touch = false;
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
  // Only a finger's tap, or a pen's: a mouse's click selects words.
  document.addEventListener('pointerdown', function (ev) { touch = ev.pointerType !== 'mouse'; },
                            { passive: true });
  function tapTurn(ev) {
    var t = ev.target;
    if (document.documentElement.dataset.tappage !== 'true' || !touch || ev.button ||
        !t.closest || !t.closest('main') || !getSelection().isCollapsed ||
        t.closest('a, button, input, select, textarea, label, summary, nav, .rail, .a, .tf, .blanket, .marginhead, .player')) return;
    if (turn(ev.clientY < innerHeight / 2 ? -1 : 1)) ev.preventDefault();
  }

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
  // is kept (ub.css .top .offline), and opens its menu (#offmenu, a popover).
  // static/offline.js runs the menu, and says what the copy is on the icon,
  // then 'ub:offline'.  It is loaded when the menu opens, or at once on a page
  // the worker answers for, to say whether its copy is still the site's.  The
  // browser's own offer to install the site waits in the menu too, rather than
  // in a banner of its own.  Until 2026-10-14 all this was in Settings.
  var cloud = document.querySelector('.top .offline'), menu = document.getElementById('offmenu');
  if (cloud && menu && 'serviceWorker' in navigator && window.isSecureContext &&
      'popover' in HTMLElement.prototype) {
    cloud.hidden = menu.hidden = false;
    // And Settings' tab for it, keeping the copy up to date by itself
    // (settings.py OFFLINE): the tab and its panel.
    document.querySelectorAll('dialog.settings .offline').forEach(function (el) { el.hidden = false; });
    // Offline (data-net) is the site out of reach: the browser says so, or the
    // worker answered for this page from its copy, which sw.js writes on the
    // footer; after that, as the browser says, and as the worker's check of
    // the site says, which offline.js writes on the icon.  Coming online sets
    // it on, and offline.js asks at once whether the site is there.
    var fromCopy = document.querySelector('footer[data-copy]'), loaded = false;
    // Which site this is: the same build is at ubsite.ddns.net and
    // ubsite.sigmaai.au, and an app installed from either shows no address.
    menu.querySelector('.net .host').textContent = location.host;
    // What offline.js says of the copy is cloud.ubSay, its words in each
    // language; the date sw.js writes on the footer is in each too.
    var label = function () {
      var on = cloud.dataset.net === 'on', none = cloud.dataset.have === 'none';
      var t = !on ? (none ? T.k('Offline') : T.k('Offline: reading the copy kept in this browser'))
            : cloud.ubSay || (none ? T.k('Online') : T.k('Online, with a copy kept for working offline'));
      T.attr(cloud, 'title', t);
      T.attr(cloud, 'aria-label', t);
      menu.querySelector('.net .conn').innerHTML = on ? T('Online') : !fromCopy ? T('Offline')
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
    if (navigator.serviceWorker.controller) script();
    // Under the icon, its right edge a little past the icon's, in the page's
    // coordinates: a popover is in the top layer, absolute to the document.
    menu.addEventListener('beforetoggle', function (ev) {
      if (ev.newState !== 'open') return;
      script();
      var r = cloud.getBoundingClientRect();
      menu.style.top = (r.bottom + window.scrollY + 8) + 'px';
      menu.style.right = Math.max(8, document.documentElement.clientWidth - r.right - 8) + 'px';
    });
  }
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
