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
// app.py serves this file with __VERSIONS__ filled in: the addresses of the
// scripts and the binary below, with their hashes.  A change to any of them
// is so a change to this file, which is what makes a browser install it anew.
'use strict';
var V = __VERSIONS__;
importScripts(V.js, V.core);

var WAIT = 4000;                 // ms the network has before the copy answers
var CHECK = 3600 * 1000;         // how often to ask whether the copy is current
var META = 'ub-meta', ENGINE = 'ub-engine', COPY = 'ub-copy-', FORMAT = 1;

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
// bytes, raw, fetch, full} or null, error}.  `fetch` is what an update to
// `latest` would download.
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
          var c = { build: m.build, made: m.made, cache: cache, manifest: m, byName: {}, byUrl: {}, chunks: {}, used: [] };
          m.chunks.forEach(function (x) {
            c.byName[x.name] = x;
            if (x.kind === 'asset') c.byUrl[x.name] = x;
          });
          return chunk(c, 'shell').then(function (sh) { c.shell = sh; return c; });
        });
      });
    });
  }).catch(function () { return null; });
  held.then(function (c) { if (!c) held = null; });
  return held;
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
// The copy's two databases, the index's attached to the text's as `ix`.
function database(c) {
  if (c.db) return c.db;
  c.db = Promise.all([sqlite(), bytes(c, 'text.db').then(function (r) { return r.arrayBuffer(); }),
                      bytes(c, 'index.db').then(function (r) { return r.arrayBuffer(); })]).then(function (got) {
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
    return { db: db, mem: function () { return new s.oo1.DB(':memory:'); } };
  });
  c.db.catch(function () { c.db = null; });
  return c.db;
}

// ---- Answering -----------------------------------------------------------
var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
              'October', 'November', 'December'];
function day(iso) {
  var d = new Date(iso);
  return d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
}
function respond(c, r) {
  if (r.location) return Response.redirect(new URL(r.location, location).href, r.status);
  var body = r.body;
  // A page from the copy says so: ub.css draws its date in the footer.
  if (/^text\/html/.test(r.type))
    body = body.replace('\n<footer>', '\n<footer data-copy="' + day(c.made) + '">');
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
  var plan = self.ubOffline.resolve(path, c.shell);
  if (plan === null) return Promise.resolve(null);
  if (plan.res) return Promise.resolve(respond(c, plan.res));
  if (plan.search) return database(c).then(function (d) {
    return respond(c, self.ubOffline.search(d.db, d.mem, c.shell, url.searchParams));
  });
  return chunk(c, plan.chunk).then(function (data) { return respond(c, plan.make(data)); });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (/^\/(offline\/|sw\.js$|api\/|audio\/|healthz$)/.test(url.pathname)) return;
  // Nor what depends on the host: a copy kept before 2026-10-15 holds the
  // manifest and the touch icon as one host sent them.
  if (self.ubOffline.HOSTED.indexOf(url.pathname) >= 0) return;
  e.respondWith(copy().then(function (c) {
    if (!c) return fetch(req);
    var mine = function () {
      return fromCopy(c, url).then(function (r) { return r || Promise.reject(new Error('not in the copy')); });
    };
    if (self.navigator.onLine === false) return mine().catch(function () { return fetch(req); });
    return new Promise(function (resolve, reject) {
      var settled = false, timer = null;
      var fall = function (why) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        mine().then(resolve, function () { reject(why); });
      };
      timer = setTimeout(function () { fall(new Error('the network took too long')); }, WAIT);
      fetch(req).then(function (r) {
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
// {done, total} in bytes while a copy is downloading: sent to the pages as it
// is, so plain data.  The download itself is `running`.
var busy = null, running = null;
function state() {
  return Promise.all([readMeta(), copy()]).then(function (got) {
    var meta = got[0], c = got[1], m = c && c.manifest;
    return {
      have: m ? { build: m.build, made: m.made, text: m.text, index: m.index, bytes: m.bytes, raw: m.raw } : null,
      latest: meta.latest || null, checked: meta.checked || 0, busy: busy, error: meta.error || null
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
function check(force) {
  return readMeta().then(function (meta) {
    if (!force && meta.checked && Date.now() - meta.checked < CHECK) return null;
    return fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (r.status >= 500) throw away('the server answered ' + r.status);
      if (!r.ok) throw new Error('the site has no offline copy (' + r.status + ')');
      return r.json();
    }, function (err) { throw away(err); }).then(function (m) {
      return copy().then(function (c) {
        var have = {};
        if (c) c.manifest.chunks.forEach(function (x) { have[x.hash] = true; });
        var full = !c || m.format !== FORMAT || (c.manifest.format !== m.format);
        var cost = 0;
        m.chunks.forEach(function (x) { if (full || !have[x.hash]) cost += x.bytes; });
        var latest = { build: m.build, made: m.made, text: m.text, index: m.index, bytes: m.bytes,
                       raw: m.raw, fetch: cost, full: full };
        return updateMeta(function (meta) {
          meta.checked = Date.now();
          meta.latest = meta.current !== m.build ? latest : null;
        });
      });
    });
  });
}
// Fetch the site's copy into a cache of its own: each chunk this browser holds
// already, in any copy, the one in use, one before it or an update that
// stopped, is carried over, and the rest is fetched.  Then make it the copy,
// and let the others go.
function download() {
  if (running) return running;
  busy = { done: 0, total: 0 };
  running = fetch('/offline/manifest.json', { cache: 'no-cache' }).then(function (r) {
    if (!r.ok) throw new Error('the site has no offline copy (' + r.status + ')');
    return r.json();
  }).then(function (m) {
    if (m.format !== FORMAT) throw new Error('this browser has an older worker; reload the page and try again');
    // A copy turned off and on again in one page keeps its worker, which is
    // then not installed again: the engine it fetched at install is gone.
    var engine = caches.open(ENGINE).then(function (c) {
      return c.match(V.wasm).then(function (r) { return r || c.add(V.wasm); });
    });
    return Promise.all([caches.open(COPY + m.build), engine]).then(function (got) {
      var target = got[0], todo = [];
      return m.chunks.reduce(function (p, x) {
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
            if (!r.ok) throw new Error(x.name + ' could not be fetched (' + r.status + ')');
            return r.arrayBuffer();
          }).then(function (got) {
            gz = got;
            return unpack(new Response(gz)).arrayBuffer();
          }).then(function (data) {
            return crypto.subtle.digest('SHA-256', data).then(function (d) {
              var h = Array.prototype.map.call(new Uint8Array(d), function (b) {
                return (b < 16 ? '0' : '') + b.toString(16);
              }).join('').slice(0, 16);
              if (h !== x.hash) throw new Error(x.name + ' arrived damaged');
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
        return updateMeta(function (meta) {
          meta.current = m.build;
          meta.checked = Date.now();
          meta.latest = null;
          meta.error = null;
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
    return updateMeta(function (meta) { meta.error = String(err && err.message || err); }).then(tell);
  });
  return running;
}

// Everything this worker keeps, for a reader who turns Work offline off.
function remove() {
  held = null;
  return caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k === META || k === ENGINE || k.indexOf(COPY) === 0; })
                         .map(function (k) { return caches.delete(k); }));
  });
}

// offline.js asks: {cmd: 'state' | 'check' | 'get' | 'remove', force}, and the
// answer, the state, comes back on the message's port.  A check's says too
// whether it reached the site: `reached` true or false, or none where it did
// not ask, or failed otherwise (a 404: the site is there, with no copy).
self.addEventListener('message', function (e) {
  var cmd = e.data && e.data.cmd, port = e.ports && e.ports[0];
  var p = cmd === 'get' ? download()
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
