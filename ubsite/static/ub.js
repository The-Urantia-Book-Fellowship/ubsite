// 15 KB budget, no dependencies. Everything here is an enhancement: the site is
// complete and correct with JavaScript off.
(function () {
  // Settings: one JSON object in localStorage, per browser, no account.  What
  // the settings are, and their defaults, is ubsite/settings.py, handed over
  // by the head script in base.html, which also applies them before first
  // paint.  This keeps them, runs the dialog, and tells listen.js of a change.
  var KEY = 'ub_settings', DEF = window.ubDefaults || {};
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
  // As the head script does: data-<key> for each value that is not its default.
  function apply(o) {
    var r = document.documentElement;
    for (var k in DEF) {
      if (o[k] === DEF[k]) delete r.dataset[k];
      else r.dataset[k] = o[k] === false ? 'off' : String(o[k]);
    }
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
    reset: function () {
      save({});
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
      bsel.options[0].text = all.length ? 'Automatic: ' + all[0].name : 'Automatic';
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
    };
    // ↺ is greyed while every setting is its default: only what differs is kept.
    var reset = form.querySelector('.reset');
    var resettable = function () { reset.disabled = !Object.keys(stored()).length; };
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
    gear.addEventListener('click', function () { fill(); resettable(); dlg.showModal(); });
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
      if (!window.confirm('Restore every setting to its default?')) return;
      window.ubSettings.reset();
      fill();
      resettable();
    });
    // A click on the backdrop closes it, as Escape does.
    dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); });
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
    b.title = shut ? 'Show the contents' : 'Fold the contents away';
    b.setAttribute('aria-label', b.title);
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
      b.title = on ? 'Fold the index away' : 'Show the index';
      b.setAttribute('aria-label', b.title);
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
  function swapped() { railSync(); indexSync(); }
  document.addEventListener('ub:swap', swapped);
  document.addEventListener('ub:settings', function (ev) {
    if (ev.detail.key === 'margin')
      Array.prototype.forEach.call(document.querySelectorAll('.afold'), function (x) {
        x.parentNode.classList.remove('shown');
      });
    swapped();
  });

  // Tooltips off (Settings): the browser draws one from a title, and no
  // stylesheet can hide it, so every title on the page is moved to data-tip,
  // where none is drawn, and back when they are turned on.  A watcher moves
  // those set later: the player's, a <main> listen.js swaps in, a paper the
  // rail fetches, the folds' and the cloud's labels as they change.  Every
  // icon keeps its aria-label, so nothing goes unnamed.
  var tipWatch = null;
  function untip(el) {
    if (!el.hasAttribute('title')) return;
    el.setAttribute('data-tip', el.getAttribute('title'));
    el.removeAttribute('title');
  }
  function tips() {
    var r = document.documentElement, each = Array.prototype.forEach;
    if (load().tips === false) {
      each.call(r.querySelectorAll('[title]'), untip);
      if (tipWatch || !window.MutationObserver) return;
      tipWatch = new MutationObserver(function (ms) {
        ms.forEach(function (m) {
          if (m.type === 'attributes') return untip(m.target);
          each.call(m.addedNodes, function (n) {
            if (n.nodeType !== 1) return;
            untip(n);
            each.call(n.querySelectorAll('[title]'), untip);
          });
        });
      });
      tipWatch.observe(r, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
    } else {
      if (tipWatch) { tipWatch.disconnect(); tipWatch = null; }
      each.call(r.querySelectorAll('[data-tip]'), function (el) {
        el.setAttribute('title', el.getAttribute('data-tip'));
        el.removeAttribute('data-tip');
      });
    }
  }
  tips();
  document.addEventListener('ub:settings', function (ev) { if (ev.detail.key === 'tips') tips(); });

  // A 1955 reading opens as a card at its ring (ub.css .pop), carrying its
  // endnote's words (section.html), which are hidden while this runs.  One
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
    el.className = 'pop';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', '1955 reading');
    el.tabIndex = -1;
    el.innerHTML = '<span class="arrow"></span>' +
      '<button type="button" class="x" aria-label="Close">×</button>' +
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
    if (!card) return;
    if (card.el.contains(t)) { if (t.closest('.x')) shut(true); return; }
    shut(false);
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && card) shut(true);
  });
  window.addEventListener('resize', place);
  document.addEventListener('ub:swap', function () { card = null; });

  // A search hit among the 1955 readings opens /93:5.8#note93_5_8_0, and
  // arrive() brings its paragraph into view: its card opens too -- if the ring
  // shows, which it does not with the readings turned off.  Not #fnref…, the
  // ring's own id, or the browser scrolls the ring's line to the top as the
  // page loads, over arrive(), and the paragraph's first lines are lost.  Here,
  // after the card's own code, which sets `card` after arrive() has run.
  // Placed again when the fonts are in and the text has reflowed.
  function arriveNote() {
    var m = /^#note(\d+_\d+_\d+_\d+)$/.exec(location.hash),
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
  // reverse, so each goes where it was.
  document.addEventListener('copy', function () {
    var sel = getSelection(), gone = [], i, r, root, w, n, k;
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
    if (gone.length) requestAnimationFrame(function () {
      for (var j = gone.length - 1; j >= 0; j--) gone[j][0].insertData(gone[j][1], '­');
    });
  });

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
    // Offline (data-net) is the site out of reach: the browser says so, or the
    // worker answered for this page from its copy, which sw.js writes on the
    // footer; after that, as the browser says, and as the worker's check of
    // the site says, which offline.js writes on the icon.  Coming online sets
    // it on, and offline.js asks at once whether the site is there.
    var fromCopy = document.querySelector('footer[data-copy]'), loaded = false;
    // Which site this is: the same build is at ubsite.ddns.net and
    // ubsite.sigmaai.au, and an app installed from either shows no address.
    menu.querySelector('.net .host').textContent = location.host;
    var label = function () {
      var on = cloud.dataset.net === 'on', none = cloud.dataset.have === 'none';
      var t = !on ? (none ? 'Offline' : 'Offline: reading the copy kept in this browser')
            : cloud.dataset.say || (none ? 'Online' : 'Online, with a copy kept for working offline');
      cloud.title = t;
      cloud.setAttribute('aria-label', t);
      menu.querySelector('.net .conn').textContent = on ? 'Online' : 'Offline' +
        (fromCopy ? ' · the copy of ' + fromCopy.dataset.copy : '');
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
