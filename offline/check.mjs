// The offline copy's check, the half that runs in Node: what the copy answers,
// made by static/offline-core.js on SQLite's WebAssembly build, exactly as the
// service worker makes it.  offline/check.py sends a job on stdin -- every
// address with the sha256 of what the server sends for it -- and reads back
// what disagreed.  Run by `python -m offline check`, never by hand.
import { createRequire } from 'node:module';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const require = createRequire(import.meta.url);
const job = JSON.parse(fs.readFileSync(0, 'utf8'));
const core = require(job.core);

const manifest = JSON.parse(fs.readFileSync(path.join(job.copy, 'manifest.json'), 'utf8'));
const raw = {};
for (const c of manifest.chunks) {
  const data = zlib.gunzipSync(fs.readFileSync(path.join(job.copy, c.file)));
  const h = crypto.createHash('sha256').update(data).digest('hex').slice(0, 16);
  if (h !== c.hash) throw new Error(`${c.name}: its file holds ${h}, the manifest says ${c.hash}`);
  raw[c.name] = data;
}
const chunk = {};
const get = (name) => chunk[name] || (chunk[name] = JSON.parse(raw[name].toString('utf8')));
const sh = get('shell');

// SQLite, as sw.js starts it: the classic script, the binary handed over.
const warn = console.warn;
console.warn = () => {};                       // OPFS, which needs a browser, says it cannot be had
const init = require(path.join(job.engine, 'sqlite3.js'));
const wasm = fs.readFileSync(path.join(job.engine, 'sqlite3.wasm'));
const sqlite3 = await init({ print() {}, printErr() {},
  instantiateWasm(imports, ok) { WebAssembly.instantiate(wasm, imports).then(r => ok(r.instance, r.module)); return {}; } });
console.warn = warn;
function open(db, schema, bytes) {
  const p = sqlite3.wasm.allocFromTypedArray(new Uint8Array(bytes));
  const rc = sqlite3.capi.sqlite3_deserialize(db.pointer, schema, p, bytes.length, bytes.length,
    sqlite3.capi.SQLITE_DESERIALIZE_FREEONCLOSE | sqlite3.capi.SQLITE_DESERIALIZE_READONLY);
  if (rc) throw new Error(`deserialize ${schema}: ${rc}`);
}
const db = new sqlite3.oo1.DB(':memory:');
open(db, 'main', raw['text.db']);
db.exec("ATTACH ':memory:' AS ix");
open(db, 'ix', raw['index.db']);
const mem = () => new sqlite3.oo1.DB(':memory:');

// What the copy answers for an address: {status, body?, location?}.
function answer(p, query) {
  const plan = core.resolve(p, sh);
  if (plan === null) return { status: 0 };
  if (plan.search) return core.search(db, mem, sh, new URLSearchParams(query || ''));
  if (plan.res) return plan.res;
  return plan.make(get(plan.chunk));
}
const sha = (s) => crypto.createHash('sha256').update(s, 'utf8').digest('hex');

// Where two texts first part, with a little of each.
function where(a, b) {
  let i = 0;
  while (i < a.length && a[i] === b[i]) i++;
  return { at: i, want: a.slice(Math.max(0, i - 60), i + 100), got: b.slice(Math.max(0, i - 60), i + 100) };
}

const out = { pages: 0, extras: 0, bad: [], links: 0, broken: [] };
const hrefs = new Set();
for (const [p, want] of Object.entries(job.pages)) {
  out.pages++;
  const got = answer(p, '');
  if (got.status !== 200 || sha(got.body) !== want) {
    out.bad.push({ path: p, status: got.status, why: 'not the page the server sends' });
    continue;
  }
  for (const m of got.body.matchAll(/\shref="(\/[^"\/][^"]*|\/)"/g)) hrefs.add(m[1].replace(/&amp;/g, '&'));
}
for (const x of job.extras) {
  out.extras++;
  const got = answer(x.path, x.query);
  const name = x.path + (x.query ? '?' + x.query : '');
  if (got.status !== x.status) { out.bad.push({ path: name, status: got.status, want: x.status }); continue; }
  if (x.location !== undefined && got.location !== x.location) {
    out.bad.push({ path: name, location: got.location, want: x.location }); continue;
  }
  if (x.sha !== undefined && sha(got.body) !== x.sha) {
    out.bad.push({ path: name, why: 'not the page the server sends', ...(x.body ? where(x.body, got.body) : {}) });
  }
}

// Every link in every page lands: on a page of the copy, a redirect to one, a
// page saying it is read online, or a file the copy keeps.
const assets = new Set(manifest.chunks.filter(c => c.kind === 'asset').map(c => c.name));
for (const h of hrefs) {
  out.links++;
  const [pq] = h.split('#');
  const [p, query] = pq.split('?');
  if (assets.has(pq) || p.startsWith('/static/')) {
    if (!assets.has(pq)) out.broken.push({ href: h, why: 'not kept in the copy' });
    continue;
  }
  let dec;
  try { dec = decodeURIComponent(p); } catch (e) { out.broken.push({ href: h, why: 'not a URL' }); continue; }
  const got = answer(dec, query);
  if (!(got.status === 200 || (got.status >= 300 && got.status < 400)))
    out.broken.push({ href: h, status: got.status });
}
process.stdout.write(JSON.stringify(out));
