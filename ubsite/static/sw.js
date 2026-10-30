// Work offline: the service worker a reader registers by downloading the copy
// from the menu of the icon at the header's corner (static/offline.js), and
// nobody else.  It keeps the copy that `make offline` builds (offline/), and
// answers the site's addresses from it when the network does not.
//
// Network first.  Online, every request goes to the server as if this were
// not here, so a reader sees the live site and the visit counter counts them.
// The copy answers when the network fails, takes longer than WAIT, or the
// server is down (a 5xx): a page, a search, a stylesheet, as the server would.
// What the copy does not hold -- the recordings, the API -- is left to fail;
// the text the browser's voice reads is in it, so that voice reads offline.
//
// The copy is kept in the Cache API, one cache per build, each chunk under
// its hash, so an update fetches only the chunks that changed, carries the
// rest over, checks each against its hash, and becomes the copy only when it
// is whole.  A chunk is kept gzipped, as it came, and unpacked when it is
// read, so the copy takes the room it took to download: unpacked, it is
// three and a half times that.  A copy knows its build; asking for /offline/manifest.json, at
// most once an hour while online, says whether the site's is another, and by
// how many bytes.  offline.js tells the reader, and updates when asked.
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
  }).then(function () { return self.clients.claim(); }));
});

// ---- What is kept --------------------------------------------------------
// meta: {current: build, checked: ms, latest: {build, made, text, index,
// bytes, raw, fetch, full} or null, error, tr: {key: build}}.  `fetch` is what
// an update to `latest` would download; `tr`, the translations kept, each at
// the build of its own it was fetched at.
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
  var p = metaQ.then(readMeta).then(function (m) { change(m); return writeMeta(m).then(function () { return m; }); });
  metaQ = p.catch(function () {});
  return p;
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

// ---- Answering -----------------------------------------------------------
function respond(c, r) {
  if (r.location) return Response.redirect(new URL(r.location, location).href, r.status);
  var body = r.body;
  // A page from the copy says so: ub.css draws its date in the footer,
  // "October 18, 2026", and in Russian «18 октября 2026 г.» (static l10n.js).
  if (/^text\/html/.test(r.type)) {
    var d = T.date(c.made, true);
    body = body.replace('\n<footer>', '\n<footer data-copy="' + d.en + '"' +
                        (T.bilingual ? ' data-copy-ru="' + d.ru + '"' : '') + '>');
  }
  return new Response(body, { status: r.status, headers: { 'Content-Type': r.type } });
}
// What the copy answers for this request, or null.
function fromCopy(c, url) {
  var asset = c.byUrl[url.pathname + url.search];
  if (asset) return bytes(c, asset.name).then(function (r) {
    return new Response(r.body, { headers: { 'Content-Type': asset.type } });
  });
  var path;
  try { path = decodeURIComponent(url.pathname); } catch (e) { return Promise.resolve(null); }
  var plan = self.ubOffline.resolve(path, c.shell, location.origin, c.kept);
  if (plan === null) return Promise.resolve(null);
  if (plan.res) return Promise.resolve(respond(c, plan.res));
  if (plan.search) return database(c).then(function (d) {
    return respond(c, self.ubOffline.search(d.db, d.mem, c.shell, url.searchParams, d.kept));
  });
  if (plan.chunks) return Promise.all(plan.chunks.map(function (n) { return chunk(c, n); })).then(function (ds) {
    return respond(c, plan.make(ds));
  });
  return chunk(c, plan.chunk).then(function (data) { return respond(c, plan.make(data)); });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  // Nor the quiz's board's JSON (ubsite/board.py), which is the board's site's
  // and never kept: on that site a page asks it at its own origin.
  if (/^\/(offline\/|sw\.js$|api\/|audio\/|healthz$|quiz\/board\/)/.test(url.pathname)) return;
  // Nor what depends on the host: a copy kept before 2026-10-15 holds the
  // manifest and the touch icon as one host sent them.
  if (self.ubOffline.HOSTED.indexOf(url.pathname) >= 0) return;
  e.respondWith(copy().then(function (c) {
    if (!c) return fetch(req);
    var mine = function () {
      return fromCopy(c, url).then(function (r) { return r || Promise.reject(new Error('not in the copy')); });
    };
    // The network even where the browser says it is offline: Chrome can say so
    // with the network working, until it is restarted, and until 2026-10-27
    // every page then came from the copy (a laptop moved from Wi-Fi to a
    // cable).  Asked past the browser's cache, so that offline indeed the
    // fetch fails at once and the copy answers, not what the cache happens to
    // hold: a translation not kept says so, though it was read online.
    var net = self.navigator.onLine === false ? new Request(req, { cache: 'no-store' }) : req;
    return new Promise(function (resolve, reject) {
      var settled = false, timer = null;
      var fall = function (why) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        mine().then(resolve, function () { reject(why); });
      };
      timer = setTimeout(function () { fall(new Error('the network took too long')); }, WAIT);
      fetch(net).then(function (r) {
        if (r.status >= 500) return fall(new Error('the server answered ' + r.status));
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(r);
      }, fall);
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
// size with the translations kept (`tr`), and every translation its manifest
// lists, with its size (`trs`), for Settings' Offline tab.
function state() {
  return Promise.all([readMeta(), copy()]).then(function (got) {
    var meta = got[0], c = got[1], m = c && c.manifest;
    var mine = m ? (m.translations || []).filter(function (t) { return c.kept.indexOf(t.key) >= 0; }) : [];
    var sum = function (k) { return mine.reduce(function (n, t) { return n + t[k]; }, m[k]); };
    return {
      have: m ? { build: m.build, made: m.made, text: m.text, index: m.index, bytes: sum('bytes'), raw: sum('raw'),
                  tr: c.kept.slice(), trs: (m.translations || []).map(function (t) {
                    return { key: t.key, bytes: t.bytes, raw: t.raw };
                  }) } : null,
      latest: meta.latest || null, checked: meta.checked || 0, busy: busy, error: meta.error || null,
      words: meta.error && meta.words || null
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
  var had = {}, was = null;
  running = readMeta().then(function (meta) {
    had = meta.tr || {};
    was = meta.current || null;
    if (!want) want = Object.keys(had);
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
            return crypto.subtle.digest('SHA-256', data).then(function (d) {
              var h = Array.prototype.map.call(new Uint8Array(d), function (b) {
                return (b < 16 ? '0' : '') + b.toString(16);
              }).join('').slice(0, 16);
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
          meta.current = m.build;
          meta.checked = Date.now();
          meta.latest = null;
          meta.error = meta.words = null;
          meta.tr = {};
          trs.forEach(function (t) { meta.tr[t.key] = t.build; });
        });
      }).then(function () {
        var was = held;
        held = null;
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

// Everything this worker keeps, for a reader who turns Work offline off.
function remove() {
  held = null;
  return caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k === META || k === ENGINE || k.indexOf(COPY) === 0; })
                         .map(function (k) { return caches.delete(k); }));
  });
}

// offline.js asks: {cmd: 'state' | 'check' | 'get' | 'drop' | 'remove', force,
// tr}, and the answer, the state, comes back on the message's port.  `get`
// may name the translations to keep, `tr`, a list of their keys, and `drop`
// names the one to let go.  A check's says too
// whether it reached the site: `reached` true or false, or none where it did
// not ask, or failed otherwise (a 404: the site is there, with no copy).
self.addEventListener('message', function (e) {
  var cmd = e.data && e.data.cmd, port = e.ports && e.ports[0];
  var tr = e.data && e.data.tr;
  var p = cmd === 'get' ? download(Array.isArray(tr) ? tr.filter(function (k) { return typeof k === 'string'; }) : undefined)
        : cmd === 'drop' ? drop(String(tr))
        : cmd === 'check' ? check(!!e.data.force).then(function (asked) {
            return state().then(function (s) { if (asked) s.reached = true; return s; });
          }, function (err) {
            return state().then(function (s) { if (err && err.away) s.reached = false; return s; });
          })
        : cmd === 'remove' ? remove().then(function () { return { removed: true }; })
        : state();
  e.waitUntil(p.then(function (s) { if (port) port.postMessage(s); },
                     function (err) { if (port) port.postMessage({ error: String(err && err.message || err) }); }));
});
