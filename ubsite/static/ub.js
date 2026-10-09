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

  window.ubSettings = {
    // The browser voice Settings names, else the best there is; null with none.
    voices: voices,
    voice: function () {
      var all = voices(), want = load().bvoice;
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
    // A browser that cannot speak is not offered its voice.
    if (bopt && !synth) bopt.hidden = true;
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
    // A setting that means nothing while the one it needs is off (settings.py
    // NEEDS) is shown, greyed, and cannot be changed.
    var idle = function (o) {
      Array.prototype.forEach.call(form.querySelectorAll('[data-needs]'), function (el) {
        var off = o[el.dataset.needs] === 'off';
        el.classList.toggle('idle', off);
        Array.prototype.forEach.call(el.querySelectorAll('input, select'), function (c) { c.disabled = off; });
      });
    };
    if (synth && synth.addEventListener) synth.addEventListener('voiceschanged', function () {
      if (dlg.open) fill();
    });
    gear.addEventListener('click', function () { fill(); dlg.showModal(); });
    // A value takes its default's type: a switch is true or false, the speed a number.
    form.addEventListener('change', function (ev) {
      var el = ev.target, d = DEF[el.name];
      if (!(el.name in DEF)) return;
      window.ubSettings.set(el.name, typeof d === 'boolean' ? el.checked
                                     : typeof d === 'number' ? parseFloat(el.value) : el.value);
      idle(load());
    });
    form.querySelector('.reset').addEventListener('click', function () {
      window.ubSettings.reset();
      fill();
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
  // listen.js brings a page in while it plays ('ub:page').
  function arrive() {
    var focus = null;
    try {
      focus = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1)))
                            : document.querySelector('.hit');
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
})();
