// Work offline: the service worker every page registers where one can run
// (static/offline.js), since 2026-11-10 (Tigran; until then only a reader who
// ticked the copy in Settings had it).  It keeps the copy that `make offline`
// builds (offline/), which every browser fetches by itself on its first
// visit, and answers the site's addresses from it.
//
// The copy first, while it is known to be the site's build (`sure`, below)
// and the browser says it is online: a page, a search, a stylesheet, as the
// server would send it, byte for byte and unmarked, with the server not asked
// at all, so the visit counter does not count it.  Otherwise the network
// first, as it was for every request until 2026-11-10: a copy out of date, or
// one a new worker has not asked about yet, a browser that says it is
// offline, an address the copy has no page for, and what depends on a
// translation the reader shows and does not keep (`shown`).  There the copy
// answers when the network fails, takes longer than WAIT, or the server is
// down (a 5xx), and a page it answers so says so on its footer (respond).
// What the copy does not hold -- the API, a recording not kept -- is left to
// fail; the text the browser's voice reads is in it, so that voice reads
// offline, and a recording a reader keeps, a paper, a part or a voice at a
// time, answers from a cache of its own (The recordings kept, below).
//
// The copy is kept in the Cache API, one cache per build, each chunk under
// its hash, so an update fetches only the chunks that changed, carries the
// rest over, checks each against its hash, and becomes the copy only when it
// is whole.  A chunk is kept gzipped, as it came, and unpacked when it is
// read, so the copy takes the room it took to download: unpacked, it is
// three and a half times that.  A copy knows its build; asking for /offline/manifest.json, at
// most once an hour while online, says whether the site's is another, and by
// how many bytes.  offline.js tells the reader, and has it updated by itself.
//
// Unless the reader has turned that off (Settings' Offline tab, Automatic
// updates; Tigran, 2026-11-10): the copy is then held (`pinned`, meta.auto
// false), fetched again only by Update now, and answers first whether or not
// it is the site's build, so that a reader goes on with the copy they have
// while the site moves on; until then an out-of-date copy never answered
// first, and turning the download off alone would have left every page to
// the server.  The check still asks, so the tab can say an update waits and
// what it costs.  It holds the copy, not this worker, which the browser
// replaces with whatever /sw.js the server sends: what that means is in
// DECISIONS.md, Work offline.
//
// The translations are each a download of their own, which a reader chooses
// in Settings' Offline tab (offline.js): the manifest lists them apart from the
// copy (offline/pack.py), and the worker keeps those chosen in the copy's own
// cache beside the rest, updates them with it, and joins a section's from them
// (offline-core.js, /tr/).  A copy with none is the copy as it was before.
//
// app.py serves this file with __VERSIONS__ filled in: the addresses of the
// scripts and the binary below, with their hashes.  A change to any of them
// is so a change to this file, which is what makes a browser install it anew.
'use strict';
var V = __VERSIONS__;
importScripts(V.js, V.l10n, V.core);
var T = self.ubT;               // the interface's words (ubsite/l10n.js)

var WAIT = 4000;                 // ms the network has before the copy answers
var CHECK = 3600 * 1000;         // how often to ask whether the copy is current
var META = 'ub-meta', ENGINE = 'ub-engine', COPY = 'ub-copy-', FORMAT = 2;   // offline/pack.py FORMAT
var AUDIO = 'ub-audio-';           // + a voice's key: the recording a reader keeps, by paper

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(ENGINE).then(function (c) { return c.add(V.wasm); })
    .then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.open(ENGINE).then(function (c) {
    return c.keys().then(function (ks) {
      return Promise.all(ks.filter(function (k) { return k.url !== new URL(V.wasm, location).href; })
                           .map(function (k) { return c.delete(k); }));
    });
  }).then(function () {
    // A worker new to this browser, or to the copy it finds: it may route or
    // join otherwise than the worker the copy was fetched by, so it asks the
    // site before it answers from the copy first (`sure`), at the next page's
    // check, which is not put off for the hour.
    return updateMeta(function (meta) { meta.sure = false; meta.checked = 0; });
  }).then(null, function () {}).then(function () { return self.clients.claim(); }));
});

// ---- What is kept --------------------------------------------------------
// meta: {current: build, checked: ms, latest: {build, made, text, index,
// bytes, raw, fetch, full} or null, error, tr: {key: build}, audio: {queue:
// [{v, n}], error, words}}.  `fetch` is what an update to `latest` would
// download; `tr`, the translations kept, each at the build of its own it was
// fetched at; `audio`, the papers of each voice asked for and not yet whole
// (The recordings kept, below), never what is kept, which the caches say.
// `sure`: the copy is the site's build, by the last check or a download just
// ended, and this worker has asked since it took over; only then does the
// copy answer first (the fetch handler).  `shown`: the translations the
// reader shows beside the text, as the page last said (ub.js, {cmd:
// 'shown'}), the worker having no other way to Settings.  `since`: when the
// copy before the last update was made, for What's new (offline.js), which
// lists what that update brought.  `auto`: false while the reader has turned
// the updating off ({cmd: 'auto'}), and absent otherwise; kept here and
// nowhere else, since it is the page's own request the worker answers by it,
// before any script of the page has run, so no setting could say it.
function readMeta() {
  return caches.open(META).then(function (c) { return c.match('/offline/meta'); })
    .then(function (r) { return r ? r.json() : {}; });
}
function writeMeta(m) {
  return caches.open(META).then(function (c) {
    return c.put('/offline/meta', new Response(JSON.stringify(m), { headers: { 'Content-Type': 'application/json' } }));
  });
}
// Change meta, one change at a time, each on what the last one wrote.  A check
// reads meta, asks the network, and writes; a download that ended meanwhile
// must not have its `current` written back to the copy before it, whose cache
// it has just deleted.  So no one writes back a meta read before a wait.
var metaQ = Promise.resolve();
function updateMeta(change) {
  var p = metaQ.then(readMeta).then(function (m) { change(m); return writeMeta(m).then(function () { return note(m); }); });
  metaQ = p.catch(function () {});
  return p;
}
// `sure`, `shown` and whether the copy is held (`pinned`: meta.auto false) as
// meta has them, for the fetch handler, which cannot read meta for every
// request: read once per worker, in the queue, so that no change is
// overtaken, and noted again at each change.
// What a page has said since this worker started (`said`) is the word, at
// once, before meta has it: a fold asks for its section's translations as
// soon as one is ticked.
var sure = false, pinned = false, shown = null, said = null, wrote = null, knownP = null;
function note(m) {
  sure = !!m.sure;
  pinned = m.auto === false;
  wrote = Array.isArray(m.shown) ? m.shown.join(' ') : null;
  shown = said || (Array.isArray(m.shown) ? m.shown : null);
  return m;
}
function showing(tr) {
  var ks = Array.isArray(tr) ? tr.filter(function (k) { return typeof k === 'string'; }) : [];
  said = shown = ks;
  return known().then(function () {
    return wrote === ks.join(' ') ? null : updateMeta(function (meta) { meta.shown = ks; });
  }).then(function () { return null; });
}
function known() {
  if (!knownP) {
    knownP = metaQ.then(readMeta).then(note).then(null, function () {});
    metaQ = knownP;
  }
  return knownP;
}
// Where a chunk is kept, gzipped.  A copy kept before 2026-10-14 has its
// chunks unpacked, under have/: they are read as they are, and an update
// packs them again rather than fetch them.
function key(hash) { return '/offline/gz/' + hash; }
function unpackedKey(hash) { return '/offline/have/' + hash; }
function unpack(r) { return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))); }
function pack(r) { return new Response(r.body.pipeThrough(new CompressionStream('gzip'))); }

// The copy in use, read once per worker: its manifest, its shell, the chunks
// lately used, and its databases once a search wants them.
var held = null;
function copy() {
  if (held) return held;
  held = readMeta().then(function (meta) {
    if (!meta.current) return null;
    return caches.has(COPY + meta.current).then(function (ok) {
      return ok ? caches.open(COPY + meta.current) : null;
    }).then(function (cache) {
      if (!cache) return null;
      return cache.match('/offline/manifest.json').then(function (r) {
        if (!r) return null;
        return r.json().then(function (m) {
          var c = { build: m.build, made: m.made, cache: cache, manifest: m, byName: {}, byUrl: {}, chunks: {}, used: [],
                    kept: kept(m, meta) };
          m.chunks.forEach(function (x) {
            c.byName[x.name] = x;
            if (x.kind === 'asset') c.byUrl[x.name] = x;
          });
          (m.translations || []).forEach(function (t) {
            t.chunks.forEach(function (x) { c.byName[x.name] = x; });
          });
          return chunk(c, 'shell').then(function (sh) { c.shell = sh; return c; });
        });
      });
    });
  }).catch(function () { return null; });
  held.then(function (c) { if (!c) held = null; });
  return held;
}
// The translations a copy keeps: those meta names that its manifest lists, in
// the manifest's order, which is Settings'.
function kept(m, meta) {
  var tr = meta.tr || {};
  return (m.translations || []).filter(function (t) { return tr[t.key]; }).map(function (t) { return t.key; });
}
// The chunks a manifest holds for a copy keeping the translations `keys`: the
// copy's own, and each of theirs.
function wanted(m, keys) {
  return (m.translations || []).filter(function (t) { return keys.indexOf(t.key) >= 0; })
    .reduce(function (all, t) { return all.concat(t.chunks); }, m.chunks);
}
function bytes(c, name) {
  var h = c.byName[name].hash;
  return c.cache.match(key(h)).then(function (r) {
    return r ? unpack(r) : c.cache.match(unpackedKey(h)).then(function (r) {
      if (!r) throw new Error('the copy has lost ' + name);
      return r;
    });
  });
}
// A chunk of pages, parsed, the last eight kept in memory.
function chunk(c, name) {
  if (c.chunks[name]) return c.chunks[name];
  var p = c.chunks[name] = bytes(c, name).then(function (r) { return r.json(); });
  c.used.push(name);
  if (c.used.length > 8) {
    var gone = c.used.shift();
    if (gone !== 'shell') delete c.chunks[gone];
  }
  p.catch(function () { delete c.chunks[name]; });
  return p;
}

// SQLite, once per worker, from the binary installed with it.
var engine = null;
function sqlite() {
  if (engine) return engine;
  engine = caches.open(ENGINE).then(function (cache) {
    return cache.match(V.wasm).then(function (r) {
      return r || fetch(V.wasm).then(function (got) { cache.put(V.wasm, got.clone()); return got; });
    });
  }).then(function (r) { return r.arrayBuffer(); }).then(function (wasm) {
    return self.sqlite3InitModule({
      print: function () {}, printErr: function () {},
      instantiateWasm: function (imports, ok) {
        WebAssembly.instantiate(wasm, imports).then(function (x) { ok(x.instance, x.module); });
        return {};
      }
    });
  });
  engine.catch(function () { engine = null; });
  return engine;
}
// The copy's databases: the index's attached to the text's as `ix`, and each
// translation's it keeps as "tr-<key>" (offline/searchdb.py).  A translation
// kept by a copy made before 2026-10-26 has none, and search counts it as not
// kept.
function database(c) {
  if (c.db) return c.db;
  var trs = c.kept.filter(function (k) { return c.byName['tr-' + k + '.db']; });
  var read = function (name) { return bytes(c, name).then(function (r) { return r.arrayBuffer(); }); };
  c.db = Promise.all([sqlite(), read('text.db'), read('index.db')].concat(trs.map(function (k) {
    return read('tr-' + k + '.db');
  }))).then(function (got) {
    var s = got[0], db = new s.oo1.DB(':memory:');
    var open = function (schema, buf) {
      var b = new Uint8Array(buf), p = s.wasm.allocFromTypedArray(b);
      var rc = s.capi.sqlite3_deserialize(db.pointer, schema, p, b.length, b.length,
        s.capi.SQLITE_DESERIALIZE_FREEONCLOSE | s.capi.SQLITE_DESERIALIZE_READONLY);
      if (rc) throw new Error('SQLite could not open ' + schema + ' (' + rc + ')');
    };
    open('main', got[1]);
    db.exec("ATTACH ':memory:' AS ix");
    open('ix', got[2]);
    trs.forEach(function (k, i) {
      db.exec("ATTACH ':memory:' AS \"tr-" + k + '"');
      open('tr-' + k, got[3 + i]);
    });
    return { db: db, mem: function () { return new s.oo1.DB(':memory:'); }, kept: trs };
  });
  c.db.catch(function () { c.db = null; });
  return c.db;
}

// ---- The recordings kept ---------------------------------------------------
// A reader keeps a recording a paper, a part or a voice at a time (Settings'
// Offline tab, offline.js; the player's ↓, listen.js): each voice's files in
// a cache of its own, AUDIO + key, under their paths, whole, as the server
// sends them, each held to the voice's list (/offline/audio/<key>.json, the
// copy's chunk audio-<key>) by size and digest before it is kept.  Never
// versioned: a recording does not change, and an update of the copy must
// never cost a reader 7 GB.  What is kept is the caches' own word; meta.audio
// holds only the queue of papers asked for, {v: key, n: paper}, as asked.
//
// A page pumps the download, one file a message (`keep`, offline.js): a
// message's work runs inside its waitUntil, which Chrome ends after five
// minutes, and the worker's own fetches do not keep it alive, so a keep
// fetches at most one file, 27 MB at most, and answers, and the page asks
// again while the queue is not empty.  A worker stopped mid-file loses
// nothing: a file is in its cache only once it is whole and checked.
var lists = {};                      // key -> promise of the voice's list, indexed
function audioList(key) {
  if (lists[key]) return lists[key];
  var p = lists[key] = copy().then(function (c) {
    if (c && c.byName['audio-' + key]) return chunk(c, 'audio-' + key).then(function (d) { return JSON.parse(d.json); });
    return fetch('/offline/audio/' + key + '.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('no list of ' + key);
      return r.json();
    });
  }).then(function (d) {
    d.byPaper = {};
    d.papers.forEach(function (x) { d.byPaper[x.n] = x; });
    return d;
  });
  p.catch(function () { delete lists[key]; });
  return p;
}
function audioPath(key, name) { return '/audio/' + key + '/' + name; }
// The paths a voice's cache holds.
function audioHave(key) {
  return caches.has(AUDIO + key).then(function (has) {
    if (!has) return {};
    return caches.open(AUDIO + key).then(function (c) { return c.keys(); }).then(function (ks) {
      var have = {};
      ks.forEach(function (k) { have[new URL(k.url).pathname] = true; });
      return have;
    });
  });
}
function hashOf(data) {
  return crypto.subtle.digest('SHA-256', data).then(function (d) {
    return Array.prototype.map.call(new Uint8Array(d), function (b) {
      return (b < 16 ? '0' : '') + b.toString(16);
    }).join('').slice(0, 16);
  });
}
// What is kept, for the tab and the bar: for each voice with a cache or in
// the queue, the papers kept whole, those kept in part with the bytes held,
// and the bytes in all; the queue; the file under way (`busy`, plain data);
// why the last one stopped.  A voice whose list cannot be had, offline with a
// copy from before the lists, says so (`nolist`).
var audioBusy = null, audioRunning = null, audioAbort = null;
function audioState() {
  return Promise.all([readMeta(), caches.keys()]).then(function (got) {
    var a = got[0].audio || {}, queue = a.queue || [], keys = {};
    queue.forEach(function (q) { keys[q.v] = true; });
    got[1].forEach(function (n) { if (n.indexOf(AUDIO) === 0) keys[n.slice(AUDIO.length)] = true; });
    return Promise.all(Object.keys(keys).map(function (key) {
      return Promise.all([audioList(key).catch(function () { return null; }), audioHave(key)]).then(function (x) {
        var list = x[0], have = x[1], v = { kept: [], partial: {}, bytes: 0 };
        if (!list) { v.nolist = true; return [key, v]; }
        list.papers.forEach(function (p) {
          var n = 0, b = 0;
          p.files.forEach(function (f) { if (have[audioPath(key, f[0])]) { n++; b += f[1]; } });
          if (n && n === p.files.length) v.kept.push(p.n);
          else if (n) v.partial[p.n] = b;
          v.bytes += b;
        });
        return [key, v];
      });
    })).then(function (pairs) {
      var voices = {};
      pairs.forEach(function (kv) { voices[kv[0]] = kv[1]; });
      return { voices: voices, queue: queue, busy: audioBusy, error: a.error || null, words: a.words || null };
    });
  });
}
// A response read whole into a buffer of the size the list gives; `told` how
// far, every half second, for the ring in the tab.
function readAll(r, name, size, told) {
  var buf = new Uint8Array(size), at = 0, reader = r.body.getReader(), last = 0;
  var step = function () {
    return reader.read().then(function (x) {
      if (x.done) return buf.buffer;
      if (at + x.value.length > size) throw stopped(T.k('{x} arrived damaged'), { x: name });
      buf.set(x.value, at);
      at += x.value.length;
      var now = Date.now();
      if (now - last > 500) { last = now; told(at); }
      return step();
    });
  };
  return step();
}
function dequeue(q) {
  return updateMeta(function (meta) {
    var a = meta.audio || (meta.audio = { queue: [] });
    a.queue = (a.queue || []).filter(function (x) { return !(x.v === q.v && x.n === q.n); });
    a.error = a.words = null;
  });
}
// One file of the queue's first paper, fetched, checked and kept; the paper
// out of the queue once it is whole.  Not while the copy downloads: the page
// asks again after.  Two pages asking at once share the one file.
function keepOne() {
  if (audioRunning) return audioRunning;
  if (running) return tell();
  var ctl = audioAbort = new AbortController(), q, paper, file, url, missing;
  audioRunning = readMeta().then(function (meta) {
    var queue = (meta.audio || {}).queue || [];
    if (!queue.length) return null;
    q = queue[0];
    return Promise.all([audioList(q.v), audioHave(q.v)]).then(function (got) {
      paper = got[0].byPaper[q.n];
      if (!paper) return dequeue(q).then(function () { return 'again'; });
      missing = paper.files.filter(function (f) { return !got[1][audioPath(q.v, f[0])]; });
      if (!missing.length) return dequeue(q).then(function () { return 'again'; });
      file = missing[0];
      url = audioPath(q.v, file[0]);
      var held = paper.bytes - missing.reduce(function (s, f) { return s + f[1]; }, 0);
      audioBusy = { v: q.v, n: q.n, done: held, total: paper.bytes, left: missing.length, of: paper.files.length };
      tell();
      // Past the browser's cache, which must not keep a second copy of the
      // file, nor answer with a part of it kept from playing (a 206).
      return fetch(url, { cache: 'no-store', headers: { 'X-UB-Fetch': 'keep' }, signal: ctl.signal }).then(function (r) {
        if (r.status !== 200) throw stopped(T.k('{x} could not be fetched ({s})'), { x: file[0], s: r.status });
        return readAll(r, file[0], file[1], function (n) { audioBusy.done = held + n; tell(); });
      }).then(function (buf) {
        return hashOf(buf).then(function (h) {
          if (buf.byteLength !== file[1] || h !== file[2]) throw stopped(T.k('{x} arrived damaged'), { x: file[0] });
          return caches.open(AUDIO + q.v).then(function (c) {
            return c.put(url, new Response(buf, { headers: {
              'Content-Type': 'audio/mpeg', 'Content-Length': String(buf.byteLength), 'Accept-Ranges': 'bytes' } }));
          }).catch(function (e) {
            throw stopped(T.k('this browser has no room for it ({e})'), { e: String(e && e.name || e) });
          });
        });
      }).then(function () {
        return missing.length === 1 ? dequeue(q)
          : updateMeta(function (meta) { if (meta.audio) meta.audio.error = meta.audio.words = null; });
      });
    });
  }).then(function (r) {
    audioBusy = audioRunning = audioAbort = null;
    return r === 'again' ? keepOne() : tell();
  }, function (err) {
    audioBusy = audioRunning = audioAbort = null;
    if (err && err.name === 'AbortError') return tell();
    return updateMeta(function (meta) {
      var a = meta.audio || (meta.audio = { queue: [] });
      a.error = String(err && err.message || err);
      a.words = err && err.words || null;
    }).then(tell);
  });
  return audioRunning;
}
// Papers of a voice asked for: those not whole go on the queue, as asked, and
// the first file is fetched.
function keep(v, ns) {
  return Promise.all([audioList(v), audioHave(v)]).then(function (got) {
    var want = ns.filter(function (n) {
      var p = got[0].byPaper[n];
      return p && p.files.some(function (f) { return !got[1][audioPath(v, f[0])]; });
    });
    return updateMeta(function (meta) {
      var a = meta.audio || (meta.audio = { queue: [] }), q = a.queue || (a.queue = []);
      want.forEach(function (n) {
        if (!q.some(function (x) { return x.v === v && x.n === n; })) q.push({ v: v, n: n });
      });
      a.error = a.words = null;
    });
  }).then(keepOne);
}
// Papers let go: out of the queue, the one under way stopped, their files out
// of the cache, and the cache itself once it is empty.
function unkeep(v, ns) {
  if (audioAbort && audioBusy && audioBusy.v === v && ns.indexOf(audioBusy.n) >= 0) audioAbort.abort();
  return updateMeta(function (meta) {
    var a = meta.audio || (meta.audio = { queue: [] });
    a.queue = (a.queue || []).filter(function (x) { return !(x.v === v && ns.indexOf(x.n) >= 0); });
    a.error = a.words = null;
  }).then(function () { return audioRunning; }).then(function () {
    return Promise.all([audioList(v), caches.has(AUDIO + v)]);
  }).then(function (got) {
    if (!got[1]) return;
    return caches.open(AUDIO + v).then(function (c) {
      return Promise.all(ns.map(function (n) {
        var p = got[0].byPaper[n];
        return p && Promise.all(p.files.map(function (f) { return c.delete(audioPath(v, f[0])); }));
      })).then(function () { return c.keys(); }).then(function (ks) {
        if (!ks.length) return caches.delete(AUDIO + v);
      });
    });
  }).then(tell);
}
// Papers of a voice out of the queue, or the whole queue emptied, the file
// under way stopped if it is theirs; what is whole stays.
function stopAudio(v, ns) {
  var mine = function (x) { return !v || (x.v === v && ns.indexOf(x.n) >= 0); };
  if (audioAbort && audioBusy && mine(audioBusy)) audioAbort.abort();
  return updateMeta(function (meta) {
    var a = meta.audio || (meta.audio = { queue: [] });
    a.queue = (a.queue || []).filter(function (x) { return !mine(x); });
    a.error = a.words = null;
  }).then(function () { return audioRunning; }).then(tell);
}

// ---- Answering a recording ---------------------------------------------------
// A kept file answers from its cache, online too: the recording never changes,
// and a paper kept is not fetched twice.  The player seeks with Range
// requests, and Safari will not seek without a 206 (app.py audio_file); the
// Cache API matches by URL alone, cannot hold a 206, and gives the whole file,
// so the slice is cut here from the file's Blob, which reads only what the
// player takes, the last file's Blob kept so that a seek does not read it
// again.  Anything not kept goes to the network as it did, with its own
// Range, and is never kept on the way.
var blobMemo = null;
function audioAnswer(req, path, key) {
  return caches.has(AUDIO + key).then(function (has) {
    if (!has) return fetch(req);
    return caches.open(AUDIO + key).then(function (c) { return c.match(path); }).then(function (hit) {
      if (!hit) return fetch(req);
      var range = req.headers.get('range');
      if (!range) return hit;
      var blob = blobMemo && blobMemo.path === path ? Promise.resolve(blobMemo.blob)
               : hit.blob().then(function (bl) { blobMemo = { path: path, blob: bl }; return bl; });
      return blob.then(function (bl) {
        var total = bl.size, m = /^bytes=(\d*)-(\d*)$/.exec(range.trim()), a, b;
        if (m && m[1] !== '') { a = +m[1]; b = m[2] === '' ? total - 1 : Math.min(+m[2], total - 1); }
        else if (m && m[2] !== '') { a = Math.max(0, total - +m[2]); b = total - 1; }
        if (!m || a > b || a >= total)
          return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + total } });
        return new Response(bl.slice(a, b + 1), { status: 206, headers: {
          'Content-Type': 'audio/mpeg', 'Content-Length': String(b - a + 1),
          'Content-Range': 'bytes ' + a + '-' + b + '/' + total, 'Accept-Ranges': 'bytes' } });
      });
    });
  });
}

// ---- Answering -----------------------------------------------------------
function respond(c, r, fell) {
  if (r.location) return Response.redirect(new URL(r.location, location).href, r.status);
  var body = r.body;
  // A page the copy answers because the network did not (`fell`) says so:
  // ub.css draws its date in the footer, "October 18, 2026", and in Russian
  // «18 октября 2026 г.» (static l10n.js), and ub.js strikes the cloud
  // through.  One it answers first is the server's page as it is.
  if (fell && /^text\/html/.test(r.type)) {
    var d = T.date(c.made, true);
    body = body.replace('\n<footer>', '\n<footer data-copy="' + d.en + '"' +
                        (T.bilingual ? ' data-copy-ru="' + d.ru + '"' : '') + '>');
  }
  return new Response(body, { status: r.status, headers: { 'Content-Type': r.type } });
}
// Whether the copy holds every translation the reader shows: only then is
// what depends on them (offline-core.js resolve(), `tr`: a section's
// translations, a search) the same from the copy as from the server, which
// sends them all.  Not known until a page has said.
function covered(c) {
  return !!shown && shown.every(function (k) { return c.kept.indexOf(k) >= 0; });
}
// What the copy answers for this request, or null: `fell`, because the
// network did not; otherwise first, and then null too where the answer
// depends on a translation shown and not kept.
function fromCopy(c, url, fell) {
  var asset = c.byUrl[url.pathname + url.search];
  if (asset) return bytes(c, asset.name).then(function (r) {
    return new Response(r.body, { headers: { 'Content-Type': asset.type } });
  });
  var path;
  try { path = decodeURIComponent(url.pathname); } catch (e) { return Promise.resolve(null); }
  var plan = self.ubOffline.resolve(path, c.shell, location.origin, c.kept);
  if (plan === null || (!fell && plan.tr && !covered(c))) return Promise.resolve(null);
  if (plan.res) {
    // Compare's old address goes on with its query, as app.py uncompare's
    // 301 does: resolve() is given the path alone.
    var res = plan.res;
    if (res.status === 301 && res.location && url.search && res.location.indexOf('?') < 0)
      res = { status: 301, location: res.location + url.search };
    // A not-found page of its own, or one saying the address is read online,
    // is `ubWeak`: the copy holds nothing for it (the fetch handler).
    var r = respond(c, res, fell);
    r.ubWeak = !!plan.res.away || plan.res.status >= 400;
    return Promise.resolve(r);
  }
  if (plan.search) return database(c).then(function (d) {
    return respond(c, self.ubOffline.search(d.db, d.mem, c.shell, url.searchParams, d.kept), fell);
  });
  if (plan.chunks) return Promise.all(plan.chunks.map(function (n) { return chunk(c, n); })).then(function (ds) {
    return respond(c, plan.make(ds), fell);
  });
  return chunk(c, plan.chunk).then(function (data) { return respond(c, plan.make(data), fell); });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  // Nor the quiz's board's JSON (ubsite/board.py), which is the board's site's
  // and never kept: on that site a page asks it at its own origin.
  var am = /^\/audio\/([a-z0-9-]+)\//.exec(url.pathname);
  if (am) { e.respondWith(audioAnswer(req, url.pathname, am[1])); return; }
  // A recording's list, /offline/audio/<key>.json, is a page to the copy
  // (offline-core.js), not the worker's own.
  if (/^\/(offline\/(?!audio\/)|sw\.js$|api\/|audio\/|healthz$|quiz\/board\/)/.test(url.pathname)) return;
  // Nor what depends on the host: a copy kept before 2026-10-15 holds the
  // manifest and the touch icon as one host sent them.
  if (self.ubOffline.HOSTED.indexOf(url.pathname) >= 0) return;
  e.respondWith(Promise.all([copy(), known()]).then(function (got) {
    var c = got[0];
    if (!c) return fetch(req);
    // The network even where the browser says it is offline: Chrome can say so
    // with the network working, until it is restarted, and until 2026-10-27
    // every page then came from the copy (a laptop moved from Wi-Fi to a
    // cable).  Asked past the browser's cache, so that offline indeed the
    // fetch fails at once and the copy answers, not what the cache happens to
    // hold: a translation not kept says so, though it was read online.
    var net = self.navigator.onLine === false ? new Request(req, { cache: 'no-store' }) : req;
    // The copy answers a page it holds once the network has taken WAIT, and
    // anything it has once the network has failed.  Not, at WAIT, a 404 of its
    // own or a page saying the address is read online (ubWeak): until
    // 2026-11-09 those beat a slow network, and its answer was thrown away,
    // the stylesheet of a build the copy did not have yet among them, which
    // left the page unstyled (review of 2026-11-09).
    var network = function () { return new Promise(function (resolve, reject) {
      var settled = false, timer = null, asked = null, failed = null, bad = null;
      var settle = function (r) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(r);
      };
      var fall = function (now) {
        if (!asked) asked = fromCopy(c, url, true).then(null, function () { return null; });
        asked.then(function (r) {
          if (settled) return;
          if (r && (now || !r.ubWeak)) return settle(r);
          if (!now) return;
          if (bad) return settle(bad);             // the server's 5xx, where the copy has nothing
          settled = true;
          reject(failed);
        });
      };
      timer = setTimeout(function () { fall(false); }, WAIT);
      fetch(net).then(function (r) {
        if (r.status < 500) return settle(r);
        bad = r;
        failed = new Error('the server answered ' + r.status);
        fall(true);
      }, function (err) {
        failed = err;
        fall(true);
      });
    }); };
    // The copy first (2026-11-10): while it is the site's build and the
    // browser says it is online.  Not a 404 of its own, a page saying the
    // address is read online, nor what depends on a translation shown and not
    // kept: those are the network's, as before.  A browser that says it is
    // offline goes to the network as before too, where the fetch fails at
    // once and the copy answers marked: Chrome can say so with the network
    // working (above), and the site's answer is the last word.  The scripts
    // and the stylesheet go as the pages do, though their addresses name
    // their content: a page the server sends is counted as a reader's by its
    // stylesheet's fetch (visits.py), so that is the server's whenever the
    // page is.
    // And a copy the reader holds as it is (`pinned`: Automatic updates
    // turned off) answers first whatever the site's build, and a worker
    // newer than it reads it as one does offline; not a copy of another
    // format, which this worker cannot be sure to read: a change of FORMAT
    // ends a hold, and the pages are the server's until Update now.
    if (!((sure || pinned) && c.manifest.format === FORMAT && self.navigator.onLine !== false)) return network();
    return fromCopy(c, url, false).then(null, function () { return null; }).then(function (r) {
      return r && !r.ubWeak ? r : network();
    });
  }));
});

// ---- Keeping it current --------------------------------------------------
// {done, total} in bytes while a copy is downloading, with `adding`, the
// translations it fetches that were not kept, and `copy`, whether the copy
// itself is updated too: sent to the pages as it is, so plain data.  The
// download itself is `running`.
var busy = null, running = null;
// What the copy is: its build, its date, the text's and the index's, and its
// own size, without the translations kept (`tr`), and every translation its
// manifest lists, with its size (`trs`), for Settings' Offline tab, which
// says each on its own row.  Until 2026-11-10 the copy's size counted the
// translations kept, 74.4 MB under Base over three rows of their own, which a
// reader would add to it (Tigran).
function state() {
  return Promise.all([readMeta(), copy(), audioState()]).then(function (got) {
    var meta = got[0], c = got[1], m = c && c.manifest;
    return {
      have: m ? { build: m.build, made: m.made, text: m.text, index: m.index, bytes: m.bytes, raw: m.raw,
                  tr: c.kept.slice(), trs: (m.translations || []).map(function (t) {
                    return { key: t.key, bytes: t.bytes, raw: t.raw };
                  }) } : null,
      latest: meta.latest || null, checked: meta.checked || 0, sure: !!meta.sure, since: meta.since || null,
      auto: meta.auto !== false, busy: busy, error: meta.error || null,
      words: meta.error && meta.words || null, audio: got[2]
    };
  });
}
function tell() {
  return state().then(function (s) {
    return self.clients.matchAll({ includeUncontrolled: true }).then(function (cs) {
      cs.forEach(function (cl) { cl.postMessage({ ubOffline: s }); });
      return s;
    });
  });
}
// Whether the site's copy is another than ours, and what fetching it would
// cost: the chunks we do not have, by hash.  Null if it was asked within the
// hour and so not asked again.  It fails `away` where the site could not be
// reached, as the fetch handler counts it: the network failed, or the server
// answered 5xx.  offline.js then says offline, whatever the browser says.
function away(why) {
  var e = new Error(String(why && why.message || why));
  e.away = true;
  return e;
}
// Why a download stopped, as the menu says it (offline.js): its words in both
// languages beside the message, by their key in ru.toml.
function stopped(key, p) {
  var w = T.tr(key, p), e = new Error(T.plain(w.en));
  e.words = w;
  return e;
}
function check(force) {
  return readMeta().then(function (meta) {
    if (!force && meta.checked && Date.now() - meta.checked < CHECK) return null;
    return fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (r.status >= 500) throw away('the server answered ' + r.status);
      if (!r.ok) throw stopped(T.k('the site has no offline copy ({s})'), { s: r.status });
      return r.json();
    }, function (err) { throw away(err); }).then(function (m) {
      return copy().then(function (c) {
        var have = {}, keys = c ? c.kept : [];
        if (c) wanted(c.manifest, keys).forEach(function (x) { have[x.hash] = true; });
        var full = !c || m.format !== FORMAT || (c.manifest.format !== m.format);
        var cost = 0;
        wanted(m, keys).forEach(function (x) { if (full || !have[x.hash]) cost += x.bytes; });
        var latest = { build: m.build, made: m.made, text: m.text, index: m.index, bytes: m.bytes,
                       raw: m.raw, fetch: cost, full: full };
        return updateMeta(function (meta) {
          // Out of date where the copy is another build, or a translation kept
          // has a build of its own that is not the site's, or has gone.
          var tr = meta.tr || {}, by = {};
          (m.translations || []).forEach(function (t) { by[t.key] = t.build; });
          meta.checked = Date.now();
          meta.latest = meta.current !== m.build || Object.keys(tr).some(function (k) { return by[k] !== tr[k]; })
            ? latest : null;
          // The copy is the site's, said by the site just now: it answers
          // first until a check says otherwise (the fetch handler).
          meta.sure = !meta.latest && !full;
        });
      });
    });
  });
}
// Fetch the site's copy into a cache of its own, with the translations `want`
// (their keys; those kept until now, if it is not given): each chunk this
// browser holds already, in any copy, the one in use, one before it or an
// update that stopped, is carried over, and the rest is fetched.  Then make it
// the copy, and let the others go.  Where the copy's build has not moved, as
// when a translation is chosen, the cache is the copy's own, and only what it
// lacks is fetched; what it holds and no longer wants is let go, a
// translation's chunks from before it was revised.
function download(want) {
  if (running) return running;
  busy = { done: 0, total: 0, adding: [], copy: false };
  var had = {}, was = null, wasMade = null;
  running = readMeta().then(function (meta) {
    had = meta.tr || {};
    was = meta.current || null;
    if (!want) want = Object.keys(had);
    return copy();
  }).then(function (c) {
    wasMade = c ? c.made : null;
    return fetch('/offline/manifest.json', { cache: 'no-cache' });
  }).then(function (r) {
    if (!r.ok) throw stopped(T.k('the site has no offline copy ({s})'), { s: r.status });
    return r.json();
  }).then(function (m) {
    if (m.format !== FORMAT) throw stopped(T.k('this browser has an older worker; reload the page and try again'));
    var trs = (m.translations || []).filter(function (t) { return want.indexOf(t.key) >= 0; });
    var all = wanted(m, want), keep = {};
    all.forEach(function (x) { keep[x.hash] = true; });
    busy.adding = trs.filter(function (t) { return !had[t.key]; }).map(function (t) { return t.key; });
    busy.copy = was !== m.build;
    // A copy turned off and on again in one page keeps its worker, which is
    // then not installed again: the engine it fetched at install is gone.
    var engine = caches.open(ENGINE).then(function (c) {
      return c.match(V.wasm).then(function (r) { return r || c.add(V.wasm); });
    });
    return Promise.all([caches.open(COPY + m.build), engine]).then(function (got) {
      var target = got[0], todo = [];
      return all.reduce(function (p, x) {
        return p.then(function () {
          return target.match(key(x.hash)).then(function (here) {
            if (here) return;
            return caches.match(key(x.hash)).then(function (had) {
              if (had) return target.put(key(x.hash), had);
              return caches.match(unpackedKey(x.hash)).then(function (old) {
                if (old) return target.put(key(x.hash), pack(old));
                todo.push(x);
                busy.total += x.bytes;
              });
            });
          });
        });
      }, Promise.resolve()).then(function () {
        tell();
        var i = 0;
        var next = function () {
          if (i >= todo.length) return Promise.resolve();
          var x = todo[i++];
          var gz;
          return fetch('/offline/' + x.file).then(function (r) {
            if (!r.ok) throw stopped(T.k('{x} could not be fetched ({s})'), { x: x.name, s: r.status });
            return r.arrayBuffer();
          }).then(function (got) {
            gz = got;
            return unpack(new Response(gz)).arrayBuffer();
          }).then(function (data) {
            return hashOf(data).then(function (h) {
              if (h !== x.hash) throw stopped(T.k('{x} arrived damaged'), { x: x.name });
              return target.put(key(x.hash), new Response(gz));
            });
          }).then(function () {
            busy.done += x.bytes;
            tell();
            return next();
          });
        };
        return Promise.all([next(), next(), next(), next()]);
      }).then(function () {
        return target.put('/offline/manifest.json', new Response(JSON.stringify(m),
                                                                 { headers: { 'Content-Type': 'application/json' } }));
      }).then(function () {
        return target.keys().then(function (ks) {
          return Promise.all(ks.filter(function (k) {
            var h = /^\/offline\/(?:gz|have)\/([0-9a-f]+)$/.exec(new URL(k.url).pathname);
            return h && !keep[h[1]];
          }).map(function (k) { return target.delete(k); }));
        });
      }).then(function () {
        return updateMeta(function (meta) {
          if (was && was !== m.build && wasMade) meta.since = wasMade;
          meta.current = m.build;
          meta.checked = Date.now();
          meta.latest = null;
          meta.sure = true;
          meta.error = meta.words = null;
          meta.tr = {};
          trs.forEach(function (t) { meta.tr[t.key] = t.build; });
        });
      }).then(function () {
        var was = held;
        held = null;
        lists = {};
        if (was) was.then(function (c) { if (c && c.db) c.db.then(function (d) { d.db.close(); }, function () {}); });
        return caches.keys().then(function (ks) {
          return Promise.all(ks.filter(function (k) { return k.indexOf(COPY) === 0 && k !== COPY + m.build; })
                               .map(function (k) { return caches.delete(k); }));
        });
      });
    });
  }).then(function () {
    busy = running = null;
    return tell();
  }, function (err) {
    busy = running = null;
    return updateMeta(function (meta) {
      meta.error = String(err && err.message || err);
      meta.words = err && err.words || null;
    }).then(tell);
  });
  return running;
}

// A translation let go, from Settings' Offline tab: its chunks out of the
// copy, and out of meta.  Not while a download runs, whose end would write
// meta again.
function drop(k) {
  if (running) return Promise.reject(new Error('a download is under way'));
  return copy().then(function (c) {
    return updateMeta(function (meta) {
      if (meta.tr) delete meta.tr[k];
      meta.checked = 0;                // the next check asks again, without it
    }).then(function () {
      held = null;
      lists = {};
      var t = c && (c.manifest.translations || []).filter(function (x) { return x.key === k; })[0];
      if (!t) return;
      var keep = {};
      wanted(c.manifest, c.kept.filter(function (x) { return x !== k; })).forEach(function (x) { keep[x.hash] = true; });
      return Promise.all(t.chunks.filter(function (x) { return !keep[x.hash]; }).map(function (x) {
        return Promise.all([c.cache.delete(key(x.hash)), c.cache.delete(unpackedKey(x.hash))]);
      }));
    });
  }).then(tell);
}

// The updating turned off or on, from Settings' Offline tab (offline.js):
// meta.auto false while it is off, and gone while it is on, as in a browser
// that never asked.  Every page open hears (tell), and updates by itself
// again where it was turned on with an update waiting (offline.js keepUp).
function setAuto(on) {
  return updateMeta(function (meta) {
    if (on) delete meta.auto;
    else meta.auto = false;
  }).then(tell);
}

// offline.js asks: {cmd: 'state' | 'check' | 'get' | 'drop' | 'keep' |
// 'unkeep' | 'stop' | 'shown' | 'news' | 'auto', force, tr, voice, papers,
// on}, and the answer, the state, comes back on the message's port; `news`
// answers with the copy's own list of what changed (its manifest's `news`),
// for What's new, with the server not asked.  `get` may name the translations
// to keep, `tr`, a list of their keys, and `drop` names the one to let go;
// `shown`, from ub.js, names those the reader shows beside the text, written
// only where they have changed.  There is no `remove` since 2026-11-10: the
// copy is every browser's, let go only by the browser's own site data.
// `keep` names a voice and its papers to keep, or nothing, to fetch the next
// file of the queue; `unkeep` a voice and papers to let go.  A check's says
// too whether it reached the site: `reached` true or false, or none where it
// did not ask, or failed otherwise (a 404: the site is there, with no copy).
// `auto` turns the updating on or off (`on`).  A command keeps its name and
// its meaning for ever, and the state its fields: a copy held is of a build
// before this worker's, and its pages' offline.js asks as that build asked,
// Update now (`get`) above all (tests/test_offline.py holds the list).
self.addEventListener('message', function (e) {
  var cmd = e.data && e.data.cmd, port = e.ports && e.ports[0];
  var tr = e.data && e.data.tr, voice = e.data && e.data.voice, ns = e.data && e.data.papers;
  ns = Array.isArray(ns) ? ns.map(Number).filter(function (n) { return Number.isInteger(n) && n >= 0; }) : [];
  var p = cmd === 'get' ? download(Array.isArray(tr) ? tr.filter(function (k) { return typeof k === 'string'; }) : undefined)
        : cmd === 'drop' ? drop(String(tr))
        : cmd === 'keep' ? (voice ? keep(String(voice), ns) : keepOne()).then(state)
        : cmd === 'unkeep' ? unkeep(String(voice), ns).then(state)
        : cmd === 'stop' ? stopAudio(voice ? String(voice) : null, ns).then(state)
        : cmd === 'check' ? check(!!e.data.force).then(function (asked) {
            return state().then(function (s) { if (asked) s.reached = true; return s; });
          }, function (err) {
            return state().then(function (s) { if (err && err.away) s.reached = false; return s; });
          })
        : cmd === 'shown' ? showing(tr)
        : cmd === 'auto' ? setAuto(e.data.on !== false)
        : cmd === 'news' ? copy().then(function (c) { return (c && c.manifest.news) || { items: [], earlier: false }; })
        : state();
  e.waitUntil(p.then(function (s) { if (port) port.postMessage(s); },
                     function (err) { if (port) port.postMessage({ error: String(err && err.message || err) }); }));
});
