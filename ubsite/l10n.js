// The interface's words for the scripts, as ubsite/l10n.py gives them to the
// templates: for ub.js, listen.js and offline.js in a page, and for sw.js and
// offline-core.js in the worker and in Node (offline/check.mjs), so that what
// the offline copy draws is what the server sends, byte for byte.  app.py
// serves this at /l10n.js, the entries of ubsite/ru.toml that the scripts name
// put in place of __CATALOG__, under a hash of what it sends (l10n_url()).
//
// A script names an entry by its English, as a literal app.py can find:
// T('…'), T.text('…'), T.tr('…'), T.k('…'), T.a('name', '…') or
// T.attr(el, 'name', '…').  A
// value for a placeholder is a number, a string (escaped), T.html(s) for HTML
// already, or {en, ru} for words made in each language (T.tr(), T.date()).
//
//   T(key, p)            the words, <x-en>…</x-en><x-ru lang="ru">…</x-ru>,
//                        as l10n.t(); CSS shows the reader's language
//   T.text(key, p)       plain text in the page's language: confirm(), the
//                        lock screen, a menu's option
//   T.attr(el, n, key, p) attribute n in the page's language, with both
//                        kept beside it, data-en-n and data-ru-n, for ub.js to
//                        turn when the language does
(function (root) {
  'use strict';
  var L10N = __CATALOG__;
  var W = L10N.words, BI = L10N.bilingual, LANGS = ['en', 'ru'];
  var MONTHS = {
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
         'October', 'November', 'December'],
    ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября',
         'октября', 'ноября', 'декабря']
  };

  // l10n.plural and l10n.group, which tests/test_l10n.py holds these to.
  function plural(n, lang) {
    n = Math.abs(n);
    if (lang === 'en') return n === 1 ? 0 : 1;
    if (n % 10 === 1 && n % 100 !== 11) return 0;
    if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return 1;
    return 2;
  }
  function group(n, lang) {
    var s = String(Math.abs(n));
    if (lang === 'en' || s.length >= 5)
      s = s.replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'en' ? ',' : ' ');
    return (n < 0 ? '-' : '') + s;
  }
  // markupsafe's escape, Jinja's autoescape.
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&#34;').replace(/'/g, '&#39;');
  }
  // HTML as text: its tags out, its entities read.
  var ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—' };
  function text(h) {
    return String(h).replace(/<[^>]*>/g, '').replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, function (m, e) {
      if (e[0] === '#') return String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
      return e in ENT ? ENT[e] : m;
    });
  }
  function fill(words, lang, p) {
    return words.replace(/\{(\w+)(:,)?\}/g, function (m, name, grouped) {
      if (!(name in p)) throw new Error('no value for {' + name + '} in ' + words);
      var v = p[name];
      if (v !== null && typeof v === 'object') return 'html' in v ? v.html : v[lang];
      if (typeof v === 'number' && Number.isInteger(v)) return grouped ? group(v, lang) : String(v);
      return esc(v);
    });
  }
  // The words of `key` in each language, {en, ru}, its placeholders filled.
  function tr(key, p) {
    var e = W[key], out = {};
    if (!e) throw new Error('ru.toml has no ' + JSON.stringify(key) + ' for the scripts');
    p = p || {};
    LANGS.forEach(function (lang) {
      var words = e[lang], rule = lang;
      if (words === null || words === undefined) { words = e.en; rule = 'en'; }
      if (Array.isArray(words)) words = words[plural(p.n, rule)];
      out[lang] = fill(words, lang, p);
    });
    return out;
  }
  function made(key, p) { return typeof key === 'string' ? tr(key, p) : key; }
  // The page's language: what base.html's head script put on <html>.
  function lang() {
    var r = typeof document !== 'undefined' && document.documentElement;
    return BI && r && r.getAttribute('data-lang') === 'ru' ? 'ru' : 'en';
  }

  function T(key, p) {
    var w = made(key, p);
    return !BI || w.en === w.ru ? w.en : '<x-en>' + w.en + '</x-en><x-ru lang="ru">' + w.ru + '</x-ru>';
  }
  T.tr = tr;
  T.text = function (key, p) { return text(made(key, p)[lang()]); };
  T.attr = function (el, name, key, p) {
    var w = made(key, p), en = text(w.en), ru = text(w.ru);
    if (BI && en !== ru) {
      el.setAttribute('data-en-' + name, en);
      el.setAttribute('data-ru-' + name, ru);
    } else {
      el.removeAttribute('data-en-' + name);
      el.removeAttribute('data-ru-' + name);
    }
    el.setAttribute(name, lang() === 'ru' ? ru : en);
  };
  // An attribute as the templates write it (l10n.ta()): name="English", and
  // data-ru-name="Русский" for ub.js to set.
  T.a = function (name, key, p) {
    var w = made(key, p), en = esc(text(w.en)), ru = esc(text(w.ru));
    return name + '="' + en + '"' + (BI && en !== ru ? ' data-ru-' + name + '="' + ru + '"' : '');
  };
  // A key named where it is not yet looked up, so that app.py finds it.
  T.k = function (key) { return key; };
  T.has = function (key) { return Object.prototype.hasOwnProperty.call(W, key); };
  T.html = function (s) { return { html: String(s) }; };
  T.same = function (s) { var h = esc(s); return { en: h, ru: h }; };
  T.num = function (n) { return { en: group(n, 'en'), ru: group(n, 'ru') }; };
  T.dec = function (x) { return { en: String(x), ru: String(x).replace('.', ',') }; };
  // "October 18, 2026", «18 октября 2026 г.», from a time's UTC fields; without
  // the year, "October 18", «18 октября».
  T.date = function (iso, year) {
    var d = new Date(iso), m = d.getUTCMonth(), n = d.getUTCDate(), y = d.getUTCFullYear();
    return { en: MONTHS.en[m] + ' ' + n + (year ? ', ' + y : ''),
             ru: n + ' ' + MONTHS.ru[m] + (year ? ' ' + y + ' г.' : '') };
  };
  T.lang = lang;
  T.bilingual = BI;
  T.esc = esc;
  T.plain = text;
  T.plural = plural;
  T.group = group;
  root.ubT = T;
  if (typeof module !== 'undefined' && module.exports) module.exports = T;
})(typeof self !== 'undefined' ? self : globalThis);
