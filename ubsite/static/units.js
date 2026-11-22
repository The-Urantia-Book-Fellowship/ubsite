// Unit conversions (templates/units.html; queries.units, build/units.py from
// data/units.toml).  A table to each kind of measure, a row to each unit, and
// every row a field: what is typed in any converts into all the others of its
// table (Tigran, 2026-11-22: "calculator should work in both directions, of
// course").  The sizes are the build's, in the page (script.ucdata), each a
// scale and an offset in its table's base, base = (value + offset) x scale;
// nothing is worked out here but that.
//
//   the row typed in is the table's source, tinted, and the others are written
//   from it as it is typed; leaving it writes it as the others are written;
//   what does not read as a number is marked and changes nothing.
//
//   the address names the source, #jday=3, so that a conversion can be sent:
//   read as the page opens, and written in place as it is typed, adding no
//   step to the history.  An example under a table is such a link, which a
//   tap puts in the table here; a same-address link fires nothing of its own
//   (CLAUDE.md trap 64).
//
//   a value is written as queries.unit_number writes it, which
//   tests/test_units.py holds this to: twelve significant digits, grouped as
//   the site groups a number in the reader's language, and from 10^15 or
//   under 10^-6 as 1.35 × 10^15, a power written out (UB Goudy has no
//   superscript digits but ¹²³).  Typed, a number may have spaces, a comma
//   for a point in Russian, an exponent, e, or × 10^ as written here (x, X, *
//   or · for the ×), 10^27 alone, or × 10⁻⁷ as pasted from elsewhere.  A
//   number, and no sum: 7*5280 is not worked out.
//
//   the time is also said in Urantia years, days, hours, minutes and seconds,
//   the year of 365¼ days (57:0.1).
//
// Nothing is kept in the browser and nothing is a setting.  Run once for a
// <main>, and again by ub.js for one listen.js brings in while it plays.
(function () {
  'use strict';
  var T = window.ubT, S = null, YEAR = 31557600, SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';

  function lang() { return T.lang(); }

  // queries.unit_number, digit for digit.
  function fmt(x, lg) {
    if (x === 0) return '0';
    if (!isFinite(x)) return '–';
    var m = Math.abs(x).toExponential(11).split('e'), d = m[0].replace('.', ''), e = +m[1];
    var sign = x < 0 ? '−' : '', point = lg === 'ru' ? ',' : '.', whole, frac;
    if (e >= 15 || e < -6) {
      d = d.replace(/0+$/, '');
      return sign + d[0] + (d.length > 1 ? point + d.slice(1) : '') + ' × 10^' + String(e).replace('-', '−');
    }
    if (e >= 0) {
      whole = (d + '000000000000000').slice(0, e + 1);
      frac = d.slice(e + 1);
    } else {
      whole = '0';
      frac = new Array(-e).join('0') + d;
    }
    frac = frac.replace(/0+$/, '');
    if (lg === 'en' || whole.length >= 5)
      whole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, lg === 'en' ? ',' : ' ');
    return sign + whole + (frac ? point + frac : '');
  }

  // What the reader typed, as a number; NaN where it is none.
  function parse(s, lg) {
    s = String(s).replace(/[\s\u00a0\u202f\u2009]/g, '').replace(/[−–]/g, '-').replace(/^([+-]?)10\^/, '$11e');
    s = s.replace(/[×x*·]10\^?([⁻-]?[⁰¹²³⁴-⁹\d]+)$/i, function (m, ex) {
      return 'e' + ex.replace(/[⁰¹²³⁴-⁹⁻]/g, function (c) { return c === '⁻' ? '-' : String(SUP.indexOf(c)); });
    });
    s = lg === 'ru' ? s.replace(/,/g, '.') : s.replace(/,/g, '');
    return /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(s) ? parseFloat(s) : NaN;
  }

  // A value as the address writes it.
  function plain(v) { return String(v).replace('e+', 'e'); }

  function rowsOf(g) { return S.main.querySelectorAll('section[data-g="' + g + '"] tr[data-u]'); }
  function rowOf(k) { return S.main.querySelector('tr[data-u="' + k + '"]'); }

  // The table g with its source, the unit k at the value v, written whole:
  // every row but the one being typed in, which keeps what was typed.
  function put(g, k, v, typing) {
    var u = S.units[k], base = (v + u[2]) * u[1], lg = lang();
    S.at[g] = { k: k, v: v, base: base };
    Array.prototype.forEach.call(rowsOf(g), function (tr) {
      var o = S.units[tr.dataset.u], inp = tr.querySelector('input');
      tr.classList.toggle('ucsrc', tr.dataset.u === k);
      if (typing && tr.dataset.u === k) return;
      inp.value = fmt(tr.dataset.u === k ? v : base / o[1] - o[2], lg);
      inp.removeAttribute('aria-invalid');
    });
    if (g === 'time') said(base);
  }

  // The time in Urantia years, days, hours, minutes and seconds.
  function said(sec) {
    var p = S.main.querySelector('.ucut'), ms, parts = [], y, d, h, m, s, ws;
    if (!p) return;
    if (!(sec >= 0.0005 && sec * 1000 < 9e15)) { p.innerHTML = ''; return; }
    ms = Math.round(sec * 1000);
    y = Math.floor(ms / (YEAR * 1000)); ms -= y * YEAR * 1000;
    d = Math.floor(ms / 86400000); ms -= d * 86400000;
    h = Math.floor(ms / 3600000); ms -= h * 3600000;
    m = Math.floor(ms / 60000); ms -= m * 60000;
    s = ms / 1000;
    if (y) parts.push(T.tr('units:y', { n: y }));
    if (d) parts.push(T.tr('units:d', { n: d }));
    if (h) parts.push(T.tr('units:h', { n: h }));
    if (m) parts.push(T.tr('units:m', { n: m }));
    if (s) parts.push(s === Math.floor(s) ? T.tr('units:s', { n: s })
                                          : T.tr('units:s-frac', { s: { en: fmt(s, 'en'), ru: fmt(s, 'ru') } }));
    ws = { en: parts.map(function (x) { return x.en; }).join(', '),
           ru: parts.map(function (x) { return x.ru; }).join(', ') };
    p.innerHTML = parts.length ? T('units:in-urantia', { t: ws }) : '';
  }

  // The address's #unit=value, or null.
  function named(hash) {
    var m = /^#([a-z][a-z0-9]*)=(.+)$/.exec(hash || ''), v;
    if (!m || !S.units[m[1]]) return null;
    v = parse(decodeURIComponent(m[2]), 'en');
    return isNaN(v) ? null : { k: m[1], v: v };
  }

  function mark(k, v) {
    try { history.replaceState(history.state, '', '#' + k + '=' + plain(v)); } catch (e) {}
  }

  function typed(inp) {
    var tr = inp.closest('tr[data-u]'), k = tr.dataset.u, u = S.units[k], v = parse(inp.value, lang());
    if (inp.value.trim() === '' || inp.value.trim() === '-') { inp.removeAttribute('aria-invalid'); return; }
    // Nothing is colder than absolute zero, the temperatures' base.
    if (isNaN(v) || !isFinite(v) || (u[0] === 'temperature' && (v + u[2]) * u[1] < 0)) {
      inp.setAttribute('aria-invalid', 'true');
      return;
    }
    inp.removeAttribute('aria-invalid');
    put(u[0], k, v, true);
    mark(k, v);
  }

  // A figure of the text put in its table, and the row the book gives it in
  // too, where it does, lit a moment.
  function example(a) {
    var x = named(a.getAttribute('href')), to, tr;
    if (!x) return false;
    put(S.units[x.k][0], x.k, x.v, false);
    mark(x.k, x.v);
    to = a.dataset.to && rowOf(a.dataset.to);
    Array.prototype.forEach.call(S.main.querySelectorAll('tr.ucto'), function (r) { r.classList.remove('ucto'); });
    tr = to || rowOf(x.k);
    if (to) {
      to.classList.add('ucto');
      setTimeout(function () { to.classList.remove('ucto'); }, 2600);
    }
    tr.scrollIntoView({ block: 'center', behavior: 'smooth' });
    return true;
  }

  // Every table written again, from its source: the language changed.
  function again() {
    Object.keys(S.at).forEach(function (g) { var a = S.at[g]; put(g, a.k, a.v, false); });
  }

  function init() {
    var main = document.querySelector('main.units'), data, x, nav;
    if (!main) return;
    try { data = JSON.parse(main.querySelector('script.ucdata').textContent); } catch (e) { return; }
    S = { main: main, units: data.units, at: {} };
    Object.keys(data.start).forEach(function (g) { put(g, data.start[g][0], data.start[g][1], false); });
    x = named(location.hash);
    if (x) {
      put(S.units[x.k][0], x.k, x.v, false);
      // Come to by its address, and not brought back by a reload or Back,
      // which put the page where it was left (ub.js atBack).
      nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
      if (!nav || nav.type === 'navigate') rowOf(x.k).scrollIntoView({ block: 'center' });
    }
    main.addEventListener('input', function (ev) {
      if (ev.target.matches('tr[data-u] input')) typed(ev.target);
    });
    main.addEventListener('change', function (ev) {
      var t = ev.target, tr = t.closest('tr[data-u]'), a;
      if (!tr || t.getAttribute('aria-invalid')) return;
      a = S.at[S.units[tr.dataset.u][0]];
      if (a && a.k === tr.dataset.u) t.value = fmt(a.v, lang());
    });
    main.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && ev.target.matches('tr[data-u] input')) ev.target.blur();
    });
    main.addEventListener('click', function (ev) {
      var a = ev.target.closest('a.ucgo');
      if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) return;
      if (example(a)) ev.preventDefault();
    });
  }

  document.addEventListener('ub:settings', function (ev) {
    if (S && S.main.isConnected && ev.detail && ev.detail.key === 'lang') again();
  });
  window.addEventListener('hashchange', function () {
    var x = S && S.main.isConnected && named(location.hash);
    if (x) put(S.units[x.k][0], x.k, x.v, false);
  });
  window.ubUnits = init;
  init();
})();
