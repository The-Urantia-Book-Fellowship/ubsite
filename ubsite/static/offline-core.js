// The offline copy's own code: what static/sw.js answers an address with,
// from the copy that offline/ built.  No DOM and no fetch, only strings and
// SQLite, so that `python -m offline check` can run this same file in Node and
// hold every page it makes to the page the server sends, byte for byte.
//
// A page is the build's shell around the page's own pieces (offline/pages.py):
// this joins them, puts a section's rail back with its section marked, and
// marks a range of paragraphs as the server does for /101:4.2-3.  Every route
// of app.py is here, with its not-found messages and its redirects.  Search
// is app.py search() again, on SQLite's WebAssembly build, with the queries
// as they stand there, and search.html drawn as Jinja draws it.
(function (root) {
  'use strict';

  var HTML = 'text/html; charset=utf-8', TEXT = 'text/plain; charset=utf-8';
  // The interface's words (ubsite/l10n.js), which the worker and the check
  // load first: the same words, drawn the same way, as the templates'.
  var T = root.ubT;
  // What the server answers by the host it is asked at (app.py SITES): the
  // app's manifest, which names the site, and the touch icon.  The copy is made
  // once for every host, so it never answers these: from it, one site's
  // installed app could be told that it was the other's.
  var HOSTED = ['/manifest.webmanifest', '/apple-touch-icon.png'];
  // The page about the text API names the address it is read at (app.py
  // api_docs), and the copy is one for every host: it is kept with API_BASE
  // there (offline/pages.py API_HOST), and given the copy's own address.
  var API_BASE = 'https://ubsite.offline.invalid/';

  // markupsafe's escape, Jinja's autoescape.
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&#34;').replace(/'/g, '&#39;');
  }
  // Jinja's urlencode for a string: urllib's quote, with "/" safe.
  function quote(s) {
    var b = new TextEncoder().encode(String(s)), out = '';
    for (var i = 0; i < b.length; i++) {
      var c = String.fromCharCode(b[i]);
      out += /[A-Za-z0-9_.\-~\/]/.test(c) ? c : '%' + (b[i] < 16 ? '0' : '') + b[i].toString(16).toUpperCase();
    }
    return out;
  }
  // The first `at` in `s` replaced by `what`, taken as it is: String.replace
  // would read a $ in it.
  function put(s, at, what) {
    var i = s.indexOf(at);
    return i < 0 ? s : s.slice(0, i) + what + s.slice(i + at.length);
  }

  function compose(sh, t, h, q, b, s) {
    var p = sh.shell;
    return p[0] + t + p[1] + h + p[2] + q + p[3] + b + p[4] + s + p[5];
  }
  function stored(sh, rec, body) {
    return compose(sh, rec.t, rec.h, '', body === undefined ? rec.b : body, rec.s);
  }
  function html(status, body) { return { status: status, type: HTML, body: body }; }
  function text(status, body) { return { status: status, type: TEXT, body: body }; }
  function redirect(to, status) { return { status: status, location: to }; }

  // templates/notfound.html, around its message and the path it names.
  function missing(sh, msg, path) {
    var m = sh.missing;
    return html(404, compose(sh, m.t, m.h, '', m.b[0] + msg + m.b[1] + esc(path) + m.b[2], m.s));
  }
  var NOPAGE = T.k('There is no page at this address.');
  // templates/offline.html: an address the copy does not hold, read online.
  function away(sh, msg) {
    var a = sh.away;
    return html(200, compose(sh, a.t, a.h, '', a.b[0] + msg + a.b[1], a.s));
  }

  // A section's page from its paper's chunk: its rail put back, its section
  // marked there, and the paragraphs focus..last marked as the server marks
  // them (templates/_para.html: " hit" ends the class, and the id follows).
  function section(sh, d, paper, sec, focus, last) {
    var rec = d.sections[sec], here = paper + ':' + sec;
    var rail = put(d.rail, '<li><a href="/' + here + '">', '<li class="here"><a href="/' + here + '">');
    var b = put(rec.b, '\u0000', rail);
    if (focus !== null)
      for (var k = focus; k <= last; k++) {
        var at = '"\n         id="' + here + '.' + k + '">';
        b = put(b, at, ' hit' + at);
      }
    return html(200, stored(sh, rec, b));
  }
  function go(ref) { return '<a href="/' + esc(ref) + '">' + esc(ref) + '</a>'; }

  var RE_REF = /^(\d+):(\d+)(?:\.(\d+)(?:-(\d+))?)?$/;

  // What the copy answers for a GET of `path` (decoded, as the server routes
  // it), in app.py's order: {res} now, {chunk, make(data)} from a chunk,
  // {chunks, make(datas)} from several, {search}, or null where the copy has no
  // say (the API, the recordings, the worker's own files), so the network's
  // failure stands.  `origin` is where the copy is read, as location.origin
  // gives it; `kept`, the keys of the translations the reader keeps in it.
  function resolve(path, sh, origin, kept) {
    var m, d;
    if (sh.miscset === undefined) {
      sh.miscset = {};
      sh.misc.forEach(function (p) { sh.miscset[p] = true; });
    }
    if (path === '/api' && sh.miscset[path]) return { chunk: 'misc', make: function (d) {
      return html(200, stored(sh, d.pages[path]).split(API_BASE).join(origin + '/'));
    } };
    if (sh.miscset[path]) return { chunk: 'misc', make: function (d) { return html(200, stored(sh, d.pages[path])); } };
    if (path === '/search') return { search: true };
    if ((m = /^\/speech\/([^\/]*[^\/0-9:][^\/]*)\/(.*)$/.exec(path))) {
      // A translation's, as the browser's voice reads it (app.py speech_tr),
      // from its own download, twenty papers to a chunk, if the reader keeps
      // it; if not, the network's failure stands, as for /rail/<key>.  A copy
      // made before 2026-10-27 has none.
      var tx = (sh.tr ? sh.tr.order : []).filter(function (x) { return x.key === m[1]; })[0],
          qm = /^([0-9]+):([0-9]+)$/.exec(m[2]), qp = qm && String(parseInt(qm[1], 10)), qs = qm && parseInt(qm[2], 10);
      if (sh.tr && (!tx || !qm || (tx.secs[qp] || []).indexOf(qs) < 0)) return { res: missing(sh, T(NOPAGE), path) };
      if (!tx || !tx.speech || (kept || []).indexOf(tx.key) < 0) return null;
      return { chunk: 'tr-' + tx.key + '-speech-' + Math.floor(+qp / 20), make: function (d) {
        return { status: 200, type: 'application/json', body: d[qp + ':' + qs] };
      } };
    }
    if ((m = /^\/speech\/(.*)$/.exec(path))) {
      // The text the browser's voice reads (app.py speech()), twenty papers to a
      // chunk (offline/pages.py SPOKEN).
      var sm = /^([0-9]+):([0-9]+)$/.exec(m[1]), sk = sm && parseInt(sm[1], 10) + ':' + parseInt(sm[2], 10);
      if (!sm || !sh.lasts[sk]) return { res: missing(sh, T(NOPAGE), path) };
      return { chunk: 'speech-' + Math.floor(parseInt(sm[1], 10) / 20), make: function (d) {
        return d[sk] === undefined ? missing(sh, T(NOPAGE), path) : { status: 200, type: 'application/json', body: d[sk] };
      } };
    }
    if ((m = /^\/tr\/(.*)$/.exec(path))) {
      // A section's translations (app.py translations_of), from those the
      // reader keeps, each a download of its own (Settings' Offline tab): each
      // one's headings, then each one's paragraphs, in Settings' order, inside
      // the fragment's frame (offline/pages.py).  With none of them kept, the
      // frame alone, which a fold reads as not in the copy.  A copy made before
      // 2026-10-26 keeps none, and leaves the network's failure standing.
      if (!sh.tr) return null;
      var tm = /^([0-9]+):([0-9]+)$/.exec(m[1]), tp = tm && String(parseInt(tm[1], 10)),
          ts = tm && parseInt(tm[2], 10), at = tp + ':' + ts;
      var has = !tm ? [] : sh.tr.order.filter(function (x) { return (x.secs[tp] || []).indexOf(ts) >= 0; });
      if (!has.length) return { res: text(404, 'No translation has this section.\n') };
      var mine = has.filter(function (x) { return (kept || []).indexOf(x.key) >= 0; });
      return { chunks: mine.map(function (x) { return 'tr-' + x.key + '-' + Math.floor(parseInt(tp, 10) / 20); }),
        make: function (ds) {
          var f = sh.tr.frame;
          return html(200, f[0] + ds.map(function (d) { return d[at][0]; }).join('') +
                           ds.map(function (d) { return d[at][1]; }).join('') + f[1]);
        } };
    }
    if (/^\/(api\/|audio\/|offline\/|healthz$|sw\.js$)/.test(path) || HOSTED.indexOf(path) >= 0) return null;
    // A copy made before 2026-10-24 does not keep it.
    if (path === '/api') return { res: away(sh, T('The page about the text API is read online.')) };
    if (path === '/stats') return { res: away(sh, T('This page is read online.')) };
    if ((m = /^\/index\/([^\/]+)$/.exec(path))) {
      var L = m[1].toUpperCase();
      if (sh.letters.indexOf(L) < 0) return { res: missing(sh, T('The index has no section headed “{l}”.', { l: m[1] }), path) };
      return { chunk: 'index-' + L, make: function (d) { return html(200, stored(sh, d.page)); } };
    }
    if ((m = /^\/i\/([^\/]+)(\/read(\/theme)?)?$/.exec(path))) {
      var slug = m[1];
      if (!Object.prototype.hasOwnProperty.call(sh.slugs, slug))
        return { res: missing(sh, T('No headword in the index has this address.'), path) };
      if (!m[2]) return { chunk: 'index-' + sh.slugs[slug], make: function (d) { return html(200, stored(sh, d.heads[slug])); } };
      // A reading path: app.py _reading_path's redirects, then the page, from
      // the chunk the shell names: [chapters, chunk].  A copy made before
      // 2026-10-14 has the chapters alone, and no paths.
      var pth = sh.paths[slug], nch = typeof pth === 'number' ? pth : pth && pth[0];
      if (pth === undefined) return { res: redirect('/i/' + slug, 307) };
      if (m[3] && nch < 2) return { res: redirect('/i/' + slug + '/read', 307) };
      if (typeof pth === 'number')
        return { res: away(sh, T('offline:path', { s: slug })) };
      var key = '/i/' + slug + (m[3] ? '/read/theme' : '/read');
      return { chunk: pth[1], make: function (d) { return html(200, stored(sh, d[key])); } };
    }
    if ((m = /^\/appendix\/([^\/]+)$/.exec(path))) {
      var a = m[1];
      if (a.toUpperCase() !== a && a.length === 1) return { res: redirect('/appendix/' + a.toUpperCase(), 301) };
      return { res: missing(sh, T('The appendices are lettered A to F.'), path) };
    }
    if ((m = /^\/part\/([0-9]+)$/.exec(path))) {
      var part = '/part/' + parseInt(m[1], 10);
      if (sh.miscset[part]) return { chunk: 'misc', make: function (d) { return html(200, stored(sh, d.pages[part])); } };
      return { res: missing(sh, T('There are four parts, I to IV.'), path) };
    }
    if ((m = /^\/rail\/([^\/0-9][^\/]*)$/.exec(path))) {
      // A translation's contents, for the left rail (app.py rail_toc), from its
      // download, if the reader keeps it; if not, the network's failure stands,
      // and the rail stays in English (ub.js tocApply).
      var tk = m[1];
      if (!sh.tr || !sh.tr.order.some(function (x) { return x.key === tk; }))
        return { res: text(404, 'No such translation.\n') };
      if ((kept || []).indexOf(tk) < 0) return null;
      return { chunk: 'tr-' + tk + '-toc', make: function (d) {
        return { status: 200, type: 'application/json', body: d.toc };
      } };
    }
    if ((m = /^\/rail\/([0-9]+)$/.exec(path))) {
      var pr = String(parseInt(m[1], 10));
      if (!sh.papers[pr]) return { res: text(404, 'No such paper.\n') };
      return { chunk: 'paper-' + pr, make: function (d) { return { status: 200, type: HTML, body: d.railsecs }; } };
    }
    // Compare's address (app.py read_compare) is the page's with /compare
    // after it, the same page; a paper's number goes to its first section in
    // Compare.
    var cm = /^(\/[^\/]+)\/compare$/.exec(path), at = cm ? cm[1] : path, then = cm ? '/compare' : '';
    if ((m = /^\/([0-9]+)$/.exec(at))) {
      var pn = parseInt(m[1], 10), secs = sh.papers[String(pn)];
      if (!secs) return { res: missing(sh, T('There is no Paper {n}. The Foreword is Paper 0, and the papers run to 196.', { n: pn }), path) };
      return { res: redirect('/' + pn + ':' + Math.min.apply(null, secs) + then, 307) };
    }
    if ((m = /^\/([^\/]+)$/.exec(at))) {
      var r = RE_REF.exec(m[1]);
      if (!r) return { res: missing(sh, T(NOPAGE), path) };
      var paper = parseInt(r[1], 10), sec = parseInt(r[2], 10);
      var focus = r[3] ? parseInt(r[3], 10) : null, last = r[4] ? parseInt(r[4], 10) : focus;
      var ss = sh.papers[String(paper)];
      if (!ss) return { res: missing(sh, T('There is no Paper {n}. The Foreword is Paper 0, and the papers run to 196.', { n: paper }), path) };
      if (ss.indexOf(sec) < 0) return { res: missing(sh, T('Paper {n} has no section {s}.', { n: paper, s: sec }), path) };
      if (focus !== null) {
        var here = paper + ':' + sec, n = sh.lasts[here], ends = [focus, last];
        for (var i = 0; i < 2; i++)
          if (!(ends[i] >= 1 && ends[i] <= n))
            return { res: missing(sh, T('There is no paragraph {p}: {s} runs from {a} to {b}.', {
              p: here + '.' + ends[i], s: here, a: T.html(go(here + '.1')), b: T.html(go(here + '.' + n)) }), path) };
        if (last < focus)
          return { res: missing(sh, T('A range runs forwards, in the order of the book: {a}, not {b}.', {
            a: T.html(go(here + '.' + last + '-' + focus)), b: here + '.' + focus + '-' + last }), path) };
      }
      return { chunk: 'paper-' + paper, make: function (d) { return section(sh, d, paper, sec, focus, last); } };
    }
    return { res: missing(sh, T(NOPAGE), path) };
  }

  // ---- The citation grammar, as much of vendor/index/cite.py as the search
  // box uses: parse(), to open a citation typed into it, and diagnose(), to
  // suggest one for a citation mistyped.
  var EN = '–', ROMAN = { I: 1, II: 2, III: 3, IV: 4, V: 5, VI: 6, VII: 7, VIII: 8, IX: 9, X: 10, XI: 11, XII: 12 };
  var SPAN = '\\d+(?:[-' + EN + ']\\d+)?', SPANLIST = SPAN + '(?:,\\s*' + SPAN + ')*';
  var RE_PARA = new RegExp('^(\\d+|F):(\\d+|[IVX]+)\\.(' + SPANLIST + ')(\\?)?$');
  var RE_SEC = new RegExp('^(\\d+|F):(' + SPANLIST + ')(secs?)(\\?)?$');
  var PITEM = '\\d+(?:\\s*[-' + EN + ']\\s*\\d+)?';
  var RE_PAPER = new RegExp('^Papers?\\s+(' + PITEM + '(?:\\s*(?:,|and)\\s*' + PITEM + ')*)' +
                            '(?:\\s*,\\s*(prematter|title page))?(\\?)?$');
  var RE_LOOKS_LIKE = /^(?:Papers?\s+\d|F[:.]|\d+\s*[:.]\s*\d)/;

  function spans(t) {
    return t.split(',').map(function (part) {
      var m = new RegExp('^(\\d+)(?:[-' + EN + '](\\d+))?$').exec(part.trim());
      var lo = parseInt(m[1], 10);
      return [lo, m[2] ? parseInt(m[2], 10) : lo];
    });
  }
  function flatten(sp) {
    var out = [];
    sp.forEach(function (s) {
      if (s[1] >= s[0]) for (var n = s[0]; n <= s[1]; n++) out.push(n);
      else out.push(s[0], s[1]);
    });
    return out;
  }
  function parse(s) {
    s = s.trim();
    if (!s) return null;
    var m = RE_PARA.exec(s);
    if (m) {
      var sec = m[2] in ROMAN ? ROMAN[m[2]] : parseInt(m[2], 10);
      return { kind: 'para', paper: m[1] === 'F' ? 0 : parseInt(m[1], 10), sec: sec, spans: spans(m[3]) };
    }
    if ((m = RE_SEC.exec(s))) return { kind: 'sec', paper: m[1] === 'F' ? 0 : parseInt(m[1], 10), spans: spans(m[2]) };
    if ((m = RE_PAPER.exec(s))) {
      var papers = [];
      m[1].split(/\s*(?:,|and)\s*/).forEach(function (item) {
        item = item.trim();
        if (!item) return;
        var parts = item.split(new RegExp('\\s*[-' + EN + ']\\s*'));
        if (parts.length === 2) for (var p = parseInt(parts[0], 10); p <= parseInt(parts[1], 10); p++) papers.push(p);
        else papers.push(parseInt(item, 10));
      });
      return { kind: 'paper', papers: papers };
    }
    return null;
  }
  function expand(c) {
    if (c.kind === 'paper') return c.papers.map(function (p) { return [p, null, null]; });
    if (c.kind === 'sec') return flatten(c.spans).map(function (s) { return [c.paper, s, null]; });
    return flatten(c.spans).map(function (n) { return [c.paper, c.sec, n]; });
  }
  var DEFECTS = [
    [/^(\d+)\.(\d+)(sec|secs)$/, '$1:$2$3'],
    [/^(\d+)\.(\d+)\.(\d+)$/, '$1:$2.$3'],
    [/^(\d+):(\d+):(\d+.*)$/, '$1:$2.$3'],
    [/^(\d+):(\d+)\.(secs?)$/, '$1:$2$3'],
    [/^(\d+:\d+secs?)\.$/, '$1'],
    [/^(\d+):(\d+)\.(\d+)secs$/, '$1:$2-$3secs'],
    [/^(\d+):(\d+)\.(\d+)\.(\d+)$/, '$1:$2.$3-$4'],
    [/^(\d+:\d+\.[\d,\s-]*\d)$/, null]
  ];
  function candidates(s) {
    var out = [], m;
    if ((m = new RegExp('^(\\d+):(\\d{2,})((?:[-,' + EN + ']\\d+)*)(\\?)?$').exec(s)))
      for (var i = 1; i < m[2].length; i++) out.push(m[1] + ':' + m[2].slice(0, i) + '.' + m[2].slice(i) + (m[3] || '') + (m[4] || ''));
    if ((m = new RegExp('^(\\d+):(\\d+(?:[-,' + EN + ']\\d+)+)(\\?)?$').exec(s))) out.push(m[1] + ':' + m[2] + 'secs' + (m[3] || ''));
    if ((m = /^(\d+):(\d+)\.(\d+)sec(\?)?$/.exec(s))) {
      out.push(m[1] + ':' + m[2] + '.' + m[3] + (m[4] || ''));
      out.push(m[1] + ':' + m[2] + 'sec' + (m[4] || ''));
    }
    return out.filter(function (c) { return parse(c) !== null; });
  }
  // The suggestions diagnose() makes, [] for none.
  function suggest(s) {
    s = s.trim();
    if (parse(s) !== null || !RE_LOOKS_LIKE.test(s)) return [];
    for (var i = 0; i < DEFECTS.length; i++) {
      var pat = DEFECTS[i][0];
      if (pat.test(s)) {
        var fixed = DEFECTS[i][1] === null ? s.replace(/,\s+/g, ',') : s.replace(pat, DEFECTS[i][1]);
        if (parse(fixed) !== null) return [fixed];
        break;
      }
    }
    return candidates(s);
  }

  // ---- Search: app.py search(), on db, which is the text's database with the
  // index's attached, and each translation's the copy keeps, as "tr-<key>"
  // (offline/searchdb.py).  mem() makes an empty in-memory database, for
  // marking the terms in what an index hit shows (app.py mark_terms).
  var RE_TERM = /"([^"]*)"?|(\S+)/g;
  var OVERVIEW = { index: 25, text: 40, notes: 10, study: 10, tr: 40 }, PER_PAGE = 100;
  var TOKENIZE = 'unicode61 remove_diacritics 2';
  var APP_OWN = " OR (e.scope IN ('B','C','D','E','F') AND e.id NOT IN (SELECT entry_id FROM appendix_head))";

  function terms(q) {
    var out = [], m;
    RE_TERM.lastIndex = 0;
    while ((m = RE_TERM.exec(q)) !== null) {
      var t = m[1], star = false;
      if (t === undefined) {
        t = m[2];
        if (/\*$/.test(t)) { t = t.replace(/\*+$/, ''); star = true; }
      }
      if (/[\p{L}\p{N}]/u.test(t)) out.push([t, star]);
    }
    return out;
  }
  function phrase(t, star) { return '"' + t.replace(/"/g, '""') + '"' + (star ? '*' : ''); }
  function ftsQuery(q) { return terms(q).map(function (t) { return phrase(t[0], t[1]); }).join(' ') || null; }
  // app.py _html: a stretch of a text from `base` on, as HTML: escaped, FTS5's
  // marks \x02 and \x03 as <mark>, a snippet's cut \x04 as an ellipsis, and the
  // text's superscripts (`at`, [[start, end], ...]) set as the page sets them.
  function supped(s, base, at) {
    var cs = Array.from(s), n = 0, opens = {}, closes = {}, any = false, out = '', i = 0;
    cs.forEach(function (c) { if ('\x02\x03\x04'.indexOf(c) < 0) n++; });
    at.forEach(function (r) {
      if (r[0] < base + n && r[1] > base) {
        opens[Math.max(r[0] - base, 0)] = true; closes[Math.min(r[1] - base, n)] = true; any = true;
      }
    });
    if (!any) return esc(s).replace(/\x02/g, '<mark>').replace(/\x03/g, '</mark>').replace(/\x04/g, '…');
    cs.forEach(function (c) {
      if (c === '\x02') out += '<mark>';
      else if (c === '\x03') out += '</mark>';
      else if (c === '\x04') out += '…';
      else {
        if (opens[i]) out += '<sup>';
        out += esc(c);
        i++;
        if (closes[i]) out += '</sup>';
      }
    });
    return out;
  }
  // app.py _snip: what highlight() or snippet() made of `text`, its
  // superscripts where `sups` (offline/searchdb.py, "start-end ...") puts them.
  function snip(s, text, sups) {
    var at = sups ? sups.split(' ').map(function (r) { return r.split('-').map(Number); }) : [], base = 0;
    if (at.length) {
      var core = s.replace(/[\x02\x03]/g, '').replace(/^\x04+|\x04+$/g, ''), k = text.indexOf(core);
      if (k < 0) throw new Error('a search hit is not in its text: ' + core.slice(0, 60));
      base = Array.from(text.slice(0, k)).length;
    }
    return supped(s, base, at);
  }

  // app.py fold and _unfold: ё read as е, as the translations' search reads
  // their text, and a snippet of it put back into the translation's own letters
  // by its place, the fold being one letter for one.
  function fold(s) { return s.replace(/ё/g, 'е').replace(/Ё/g, 'Е'); }
  function unfold(s, text) {
    if (!/[ёЁ]/.test(text)) return s;
    var core = s.replace(/[\x02\x03]/g, '').replace(/^\x04+|\x04+$/g, ''), k = fold(text).indexOf(core);
    if (k < 0) throw new Error('a search hit is not in its text: ' + core.slice(0, 60));
    var t = Array.from(text.slice(k)), i = 0;
    return Array.from(s).map(function (c) { return '\x02\x03\x04'.indexOf(c) >= 0 ? c : t[i++]; }).join('');
  }

  function markTerms(mem, texts, q, sups) {
    var ts = terms(q);
    if (!ts.length || !texts.length) return texts.map(function (t, i) { return snip(t, t, sups[i]); });
    var con = mem(), got = {};
    try {
      con.exec("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='" + TOKENIZE + "')");
      texts.forEach(function (t, i) { con.exec({ sql: 'INSERT INTO t(rowid, x) VALUES (?, ?)', bind: [i, t] }); });
      var anyq = ts.map(function (t) { return phrase(t[0], t[1]); }).join(' OR ');
      con.exec({ sql: 'SELECT rowid, highlight(t, 0, char(2), char(3)) FROM t WHERE t MATCH ?', bind: [anyq],
                 rowMode: 'array', callback: function (r) { got[r[0]] = r[1]; } });
    } finally { con.close(); }
    return texts.map(function (t, i) { return snip(i in got ? got[i] : t, t, sups[i]); });
  }
  function rows(db, sql, bind) { return db.exec({ sql: sql, bind: bind, rowMode: 'object', returnValue: 'resultRows' }); }
  function count(db, sql, bind) { return db.selectValue(sql, bind); }
  function window_(whole, kind, number, n) {
    if (!whole) return [OVERVIEW[kind], 0];
    var last = Math.max(1, Math.ceil(n / PER_PAGE));
    return [PER_PAGE, (Math.min(number, last) - 1) * PER_PAGE];
  }
  function hits(n, off, rs) {
    return { n: n, rows: rs, first: off + 1, last: off + rs.length, page: Math.floor(off / PER_PAGE) + 1,
             more: off + rs.length < n };
  }

  // app.py _tr_hits: one translation's list, from its database, attached as
  // "tr-<key>": a line to each paragraph whose words or one of whose
  // translator's notes matched, by ours, in the order of the book.
  function trHits(db, key, tq, whole, number) {
    var S = '"tr-' + key + '"';
    var hit = 'SELECT t.paragraph_id AS pid FROM ' + S + '.tr_paragraph_fts f JOIN ' + S + '.tr_paragraph t ON t.id=f.rowid' +
              ' WHERE tr_paragraph_fts MATCH ?' +
              ' UNION SELECT n.paragraph_id FROM ' + S + '.tr_note_fts f JOIN ' + S + '.tr_note n ON n.id=f.rowid' +
              ' WHERE tr_note_fts MATCH ?';
    var n = count(db, 'SELECT COUNT(*) FROM (' + hit + ')', [tq, tq]), w = window_(whole, 'tr', number, n);
    var rs = rows(db, 'SELECT h.pid, p.ref FROM (' + hit + ') h JOIN paragraph p ON p.id=h.pid' +
                      ' ORDER BY p.ord LIMIT ? OFFSET ?', [tq, tq, w[0], w[1]]);
    var ids = rs.map(function (r) { return r.pid; }), within = ids.map(function () { return '?'; }).join(',');
    var said = {}, notes = {};
    rows(db, 'SELECT t.paragraph_id AS pid, t.text, t.sups,' +
             '  snippet(tr_paragraph_fts, 0, char(2), char(3), char(4), 24) AS s' +
             ' FROM ' + S + '.tr_paragraph_fts f JOIN ' + S + '.tr_paragraph t ON t.id=f.rowid' +
             ' WHERE tr_paragraph_fts MATCH ? AND t.paragraph_id IN (' + within + ')', [tq].concat(ids)).forEach(function (r) {
      said[r.pid] = snip(unfold(r.s, r.text), r.text, r.sups);
    });
    rows(db, 'SELECT n.paragraph_id AS pid, n.text, n.sups, n.pre, n.post,' +
             '  snippet(tr_note_fts, 0, char(2), char(3), char(4), 24) AS s' +
             ' FROM ' + S + '.tr_note_fts f JOIN ' + S + '.tr_note n ON n.id=f.rowid' +
             ' WHERE tr_note_fts MATCH ? AND n.paragraph_id IN (' + within + ') ORDER BY n.num', [tq].concat(ids)).forEach(function (r) {
      (notes[r.pid] = notes[r.pid] || []).push(r.pre + snip(unfold(r.s, r.text), r.text, r.sups) + r.post);
    });
    return hits(n, w[1], rs.map(function (r) { return { ref: r.ref, s: said[r.pid], notes: notes[r.pid] || [] }; }));
  }

  // params: a URLSearchParams; kept, the keys of the translations whose
  // databases are attached.  Returns a response: the results page, or the
  // redirect a citation typed into the box gets.
  function search(db, mem, sh, params, kept) {
    var lastOf = function (k, dflt) { var all = params.getAll(k); return all.length ? all[all.length - 1] : dflt; };
    var q = lastOf('q', '').trim(), scope = lastOf('in', ''), pageNo = lastOf('page', '1');
    var jump = q ? parse(q) : null;
    if (jump !== null) {
      var tg = expand(jump);
      if (tg.length) {
        var p = tg[0][0], s = tg[0][1], n = tg[0][2];
        if (jump.kind === 'para' && jump.spans[0][1] !== n) n = n + '-' + jump.spans[0][1];
        return redirect(s === null ? '/' + p : '/' + p + ':' + s + (n !== null ? '.' + n : ''), 303);
      }
    }
    var trs = (sh.tr && sh.tr.order) || [];
    scope = (scope === 'index' || scope === 'text' || scope === 'notes' || scope === 'study' ||
             trs.some(function (x) { return x.key === scope; })) ? scope : '';
    var number = /^[0-9]+$/.test(pageNo) && parseInt(pageNo, 10) > 0 ? parseInt(pageNo, 10) : 1;
    var fq = ftsQuery(q), heads = [], idx = null, txt = null, old = null, stu = null, found = [], w, where;
    if (q && (scope === '' || scope === 'index'))
      heads = rows(db,
        "SELECT e.id, e.slug, e.headword, e.headword_html, e.scope, e.anchor, a.title AS appendix," +
        "  (SELECT n_descendants FROM entry_stats WHERE entry_id=e.id) AS kids" +
        " FROM index_entry e LEFT JOIN appendix a ON a.letter=e.scope" +
        " WHERE (e.scope='az' AND e.level=1" + APP_OWN + ")" +
        "   AND (LOWER(RTRIM(e.headword,'.')) = LOWER(?)" +
        "        OR LOWER(e.headword) LIKE LOWER(?) || '%')" +
        " ORDER BY LOWER(RTRIM(e.headword,'.')) = LOWER(?) DESC," +
        "          e.scope<>'az', e.ord" +
        " LIMIT 12", [q, q, q]);
    if (fq && (scope === '' || scope === 'index')) {
      var shown = heads.map(function (h) { return h.id; });
      where = " FROM index_entry_fts f JOIN index_entry e ON e.id=f.rowid" +
              " WHERE index_entry_fts MATCH ? AND (e.scope IN ('az','A')" + APP_OWN + ")" +
              (shown.length ? ' AND e.id NOT IN (' + shown.map(function () { return '?'; }).join(',') + ')' : '');
      var ni = count(db, 'SELECT COUNT(*)' + where, [fq].concat(shown));
      w = window_(scope === 'index', 'index', number, ni);
      var ir = rows(db,
        "SELECT e.path_plain AS path, e.path_sups, e.level, e.anchor, e.scope," +
        "  (SELECT slug FROM index_entry WHERE id=e.root_id) AS rslug," +
        "  (SELECT title FROM appendix WHERE letter=e.scope) AS appendix," +
        "  (SELECT label FROM chronology_event WHERE entry_id=e.id) AS event," +
        "  (SELECT label_sups FROM chronology_event WHERE entry_id=e.id) AS event_sups" +
        where + " ORDER BY rank LIMIT ? OFFSET ?", [fq].concat(shown, [w[0], w[1]]));
      var mk = markTerms(mem, ir.map(function (r) { return r.event || r.path; }), q,
                         ir.map(function (r) { return r.event ? r.event_sups : r.path_sups; }));
      ir.forEach(function (r, i) { r.marked = mk[i]; });
      idx = hits(ni, w[1], ir);
    }
    if (fq && (scope === '' || scope === 'text')) {
      var nt = count(db, 'SELECT COUNT(*) FROM paragraph_fts WHERE paragraph_fts MATCH ?', [fq]);
      w = window_(scope === 'text', 'text', number, nt);
      txt = hits(nt, w[1], rows(db,
        "SELECT p.ref, p.text, p.sups, snippet(paragraph_fts, 0, char(2), char(3), char(4), 24) AS s" +
        " FROM paragraph_fts f JOIN paragraph p ON p.id=f.rowid" +
        " WHERE paragraph_fts MATCH ? ORDER BY p.ord LIMIT ? OFFSET ?", [fq, w[0], w[1]]).map(function (r) {
          return { ref: r.ref, s: snip(r.s, r.text, r.sups) };
        }));
    }
    if (fq && (scope === '' || scope === 'study')) {
      where = " FROM footnote_fts x JOIN footnote f ON f.id=x.rowid" +
              " JOIN paragraph p ON p.id=f.paragraph_id" +
              " WHERE footnote_fts MATCH ? AND f.kind='study'";
      var ns = count(db, 'SELECT COUNT(*)' + where, [fq]);
      w = window_(scope === 'study', 'study', number, ns);
      stu = hits(ns, w[1], rows(db,
        "SELECT snippet(footnote_fts, 0, char(2), char(3), char(4), 24) AS s, x.reading AS text," +
        "  h.pre, h.post, h.sups" + where.replace(' WHERE', ' JOIN study_html h ON h.id=f.id WHERE') +
        " ORDER BY p.ord, f.anchor, f.ord LIMIT ? OFFSET ?", [fq, w[0], w[1]]).map(function (r) {
          return r.pre + snip(r.s, r.text, r.sups) + r.post;
        }));
    }
    // Each translation, from its database where the copy keeps it; where it
    // does not, its list says so, opened whole or on the overview of any search
    // with words in it, and shows where the reader shows the translation
    // (base.html ubTr), as the server's would.
    var tq = ftsQuery(fold(q));
    trs.forEach(function (x) {
      if (scope !== '' && scope !== x.key) return;
      if ((kept || []).indexOf(x.key) < 0) {
        if (tq || scope) found.push({ x: x, hits: null });
        return;
      }
      var got = tq ? trHits(db, x.key, tq, scope === x.key, number) : hits(0, 0, []);
      if (got.n || scope) found.push({ x: x, hits: got });
    });
    if (fq && (scope === '' || scope === 'notes')) {
      where = " FROM footnote_fts x JOIN footnote f ON f.id=x.rowid" +
              " JOIN paragraph p ON p.id=f.paragraph_id" +
              " WHERE footnote_fts MATCH ? AND f.kind='variant-1955'";
      var nn = count(db, 'SELECT COUNT(*)' + where, [fq]);
      w = window_(scope === 'notes', 'notes', number, nn);
      var nr = rows(db,
        "SELECT f.id, highlight(footnote_fts, 0, char(2), char(3)) AS reading," +
        "  snippet(footnote_fts, 1, char(2), char(3), char(4), 20) AS reasons," +
        "  x.reading AS reading_text, x.reasons AS reasons_text, h.reading_sups, h.reasons_sups," +
        "  h.pre, h.post, h.mid, h.tail, h.card" + where.replace(' WHERE', ' JOIN note_html h ON h.id=f.id WHERE') +
        " ORDER BY p.ord, f.ord LIMIT ? OFFSET ?", [fq, w[0], w[1]]);
      old = hits(nn, w[1], nr.map(function (r) {
        var line = r.pre + snip(r.reading, r.reading_text, r.reading_sups) +
                   (r.reasons.indexOf('\x02') >= 0
                    ? r.mid + snip(r.reasons, r.reasons_text, r.reasons_sups) + r.tail : r.post);
        return { line: line, card: r.card };
      }));
    }
    var body = draw(q, scope, heads, idx, txt, old, stu, found, q ? suggest(q) : []);
    // The title piece begins inside its tag (offline/pages.py cut): a search's
    // has no Russian of its own, being what was typed.
    return html(200, compose(sh, '>' + esc(q), sh.search.h, esc(q), body, sh.search.s));
  }

  // templates/search.html's body, whitespace and all.
  function draw(q, scope, heads, idx, txt, old, stu, found, didyou) {
    var uq = quote(q);
    function count(h) {
      return '<span>' + (h.first > 1 || h.more
        ? (scope ? T('({a:,}–{b:,} of {n:,})', { a: h.first, b: h.last, n: h.n }) : T('({b} of {n:,})', { b: h.last, n: h.n }))
        : T('({n:,})', { n: h.n })) + '</span>';
    }
    function more(h, name, all) {
      var mid;
      if (scope) mid = (h.first > 1 || h.more
        ? '<nav class="pager">\n  ' +
          (h.first > 1 ? '<a href="/search?q=' + uq + '&amp;in=' + name + '&amp;page=' + (h.page - 1) + '">' + T('Earlier') + '</a>' : '') + '\n  ' +
          (h.more ? '<a class="next" href="/search?q=' + uq + '&amp;in=' + name + '&amp;page=' + (h.page + 1) + '">' + T('Later') + '</a>' : '') +
          '\n</nav>' : '') + '\n';
      else mid = h.more ? '<p class="more"><a href="/search?q=' + uq + '&amp;in=' + name + '">' + T(all, { n: h.n }) + '</a></p>' : '';
      return '\n' + mid + '\n';
    }
    var o = '<main class="prose results">\n<h1>' + esc(q) + '</h1>\n';
    if (scope) o += '<p class="hint"><a href="/search?q=' + uq + '">' + T('All results for “{q}”', { q: q }) + '</a></p>';
    o += '\n';
    if (didyou.length)
      o += '<p class="didyou">' + T('Did you mean') + '\n  ' + didyou.map(function (c) {
        return '<a href="/search?q=' + quote(c) + '">' + esc(c) + '</a>';
      }).join(' ' + T('or') + ' ') + '?</p>';
    o += '\n';
    if (heads.length) {
      o += '<section' + (scope ? '' : ' class="ix"') + '><h2>' + T('Headwords') + '</h2>\n<ul class="hits heads-hit">';
      heads.forEach(function (h) {
        o += '<li>';
        if (h.slug) o += '<a href="/i/' + esc(h.slug) + '">' + h.headword_html + '</a>\n  ' +
                         (h.kids ? '<span>' + T('{n} subentries', { n: h.kids }) + '</span>' : '');
        else o += '<a href="/appendix/' + esc(h.scope) + '#' + esc(h.anchor) + '">' + h.headword_html + '</a>\n  ' +
                  '<span>' + T('Appendix {x}, {title}', { x: h.scope, title: h.appendix }) + '</span>';
        o += '</li>';
      });
      o += '</ul></section>';
    }
    o += '\n';
    if (scope === '' || scope === 'index') {
      o += '<section' + (scope ? '' : ' class="ix"') + '><h2>' + T('In the index') + ' ' + (idx ? count(idx) : '<span>(0)</span>') + '</h2>\n';
      if (idx && idx.rows.length) {
        o += '<ul class="hits">';
        idx.rows.forEach(function (e) {
          o += '<li>';
          if (e.rslug) o += '<a href="/i/' + esc(e.rslug) + (e.level > 1 ? '#' + esc(e.anchor) : '') + '">' + e.marked + '</a>';
          else o += '<a class="app" href="/appendix/' + esc(e.scope) + '#' + esc(e.anchor) + '"><span class="lbl">' +
                    esc(e.appendix) + '</span> ' + e.marked + '</a>';
          o += '</li>';
        });
        o += '</ul>\n' + more(idx, 'index', T.k('Show all {n:,} index entries')) + '\n';
      } else o += '<p class="none">' + T('nothing') + '</p>';
      o += '</section>';
    }
    o += '\n';
    if (scope === '' || scope === 'text') {
      o += '<section><h2>' + T('In the text') + ' ' + (txt ? count(txt) : '<span>(0)</span>') + '</h2>\n';
      if (txt && txt.rows.length) {
        o += '<ul class="hits">';
        txt.rows.forEach(function (t) { o += '<li><a href="/' + esc(t.ref) + '">' + esc(t.ref) + '</a> ' + t.s + '</li>'; });
        o += '</ul>\n' + more(txt, 'text', T.k('Show all {n:,} paragraphs')) + '\n';
      } else o += '<p class="none">' + T('nothing') + '</p>';
      o += '</section>';
    }
    o += '\n';
    if (stu && stu.rows.length)
      o += '<section' + (scope ? '' : ' class="bystudy"') + '><h2>' + T('In the study notes') + ' ' + count(stu) + '</h2>\n' +
           '<ul class="hits stl">' + stu.rows.join('') + '</ul>\n' + more(stu, 'study', T.k('Show all {n:,} notes')) +
           '\n</section>';
    else if (scope === 'study')
      o += '<section><h2>' + T('In the study notes') + ' <span>(0)</span></h2><p class="none">' + T('nothing') + '</p></section>';
    o += '\n\n';
    // A translation's list, as search.html's tr_list draws it, or, where the
    // copy does not keep the translation, its heading and a line saying so.
    function trList(e) {
      var x = e.x, h = e.hits,
          s = '<section data-tr="' + x.key + '"><h2><bdi lang="' + x.lang + '">' + esc(x.title) + '</bdi> <span class="nobreak">(' + x.label + ')</span>';
      if (!h) return s + '</h2>\n<p class="none">' + T('tr:notkept') + '</p></section>';
      s += ' ' + count(h) + '</h2>\n';
      if (h.rows.length)
        s += '<ul class="hits">' + h.rows.map(function (r) {
          return '<li><a href="/' + esc(r.ref) + '#tr-' + x.key + '">' + esc(r.ref) + '</a>' +
                 (r.s ? ' <span lang="' + x.lang + '">' + r.s + '</span>' : '') + r.notes.join('') + '</li>';
        }).join('') + '</ul>\n' + more(h, x.key, T.k('Show all {n:,} paragraphs')) + '\n';
      else s += '<p class="none">' + T('nothing') + '</p>';
      return s + '</section>';
    }
    if (scope && found.length) o += trList(found[0]);
    else if (found.length) o += '<div class="trhits">' + found.map(trList).join('') + '</div>';
    o += '\n';
    if (old && old.rows.length) {
      o += '<section' + (scope ? '' : ' class="by1955"') + '><h2>' + T('In the 1955 readings') + ' ' + count(old) + '</h2>\n' +
           '<ul class="hits old">' + old.rows.map(function (r) { return r.line; }).join('') + '</ul>\n' +
           more(old, 'notes', T.k('Show all {n:,} readings')) + '\n' +
           '<section class="notes" ' + T.a('aria-label', 'The 1955 readings') + '>\n      <h3>' + T('The 1955 readings') + '</h3>\n      ' +
           old.rows.map(function (r) { return r.card + '\n      '; }).join('') + '\n    </section>' + '\n</section>';
    } else if (scope === 'notes')
      o += '<section><h2>' + T('In the 1955 readings') + ' <span>(0)</span></h2><p class="none">' + T('nothing') + '</p></section>';
    return o + '\n</main>';
  }

  var api = { resolve: resolve, search: search, compose: compose, quote: quote, esc: esc, parse: parse, suggest: suggest,
              HOSTED: HOSTED };
  root.ubOffline = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof self !== 'undefined' ? self : globalThis);
