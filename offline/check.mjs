// The offline copy's check, the half that runs in Node: what the copy answers,
// made by static/offline-core.js on SQLite's WebAssembly build, exactly as the
// service worker makes it.  offline/check.py sends a job on stdin -- every
// address with the sha256 of what the server sends for it -- and reads back
// what disagreed.  Run by `python -m offline check`, never by hand.
import { createRequire } from 'node:module';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import zlib from 'node:zlib';

const require = createRequire(import.meta.url);
const job = JSON.parse(fs.readFileSync(0, 'utf8'));

const manifest = JSON.parse(fs.readFileSync(path.join(job.copy, 'manifest.json'), 'utf8'));
const raw = {};
// The translations' chunks too, each a download of its own (offline/pack.py).
const trs = manifest.translations || [];
for (const c of manifest.chunks.concat(...trs.map((t) => t.chunks))) {
  const data = zlib.gunzipSync(fs.readFileSync(path.join(job.copy, c.file)));
  const h = crypto.createHash('sha256').update(data).digest('hex').slice(0, 16);
  if (h !== c.hash) throw new Error(`${c.name}: its file holds ${h}, the manifest says ${c.hash}`);
  raw[c.name] = data;
}
// The interface's words, the copy's own /l10n.js, as the worker imports it
// before the core (sw.js): the core draws its pages' words with it.
const words = Object.keys(raw).filter((n) => n.startsWith('/l10n.js?'));
if (words.length !== 1) throw new Error(`the copy holds ${words.length} /l10n.js`);
vm.runInThisContext(raw[words[0]].toString('utf8'), { filename: words[0] });
const core = require(job.core);
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
// Every translation's database for search, as sw.js attaches those it keeps.
for (const t of trs) {
  db.exec(`ATTACH ':memory:' AS "tr-${t.key}"`);
  open(db, `tr-${t.key}`, raw[`tr-${t.key}.db`]);
}
const mem = () => new sqlite3.oo1.DB(':memory:');

// What the copy answers for an address: {status, body?, location?}, with
// `kept` the translations kept in it, all of them unless it says.
const ALL = trs.map((t) => t.key);
function answer(p, query, kept = ALL) {
  const plan = core.resolve(p, sh, job.origin, kept);
  if (plan === null) return { status: 0 };
  if (plan.search) return core.search(db, mem, sh, new URLSearchParams(query || ''), kept);
  if (plan.res) return plan.res;
  if (plan.chunks) return plan.make(plan.chunks.map(get));
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

// A section's translations with fewer of them kept: with none, the fragment's
// frame alone; with one, the frame around that one's pieces where it has the
// section, else the frame alone.  With all of them, it is the server's, above.
const frame = sh.tr ? sh.tr.frame.join('') : '';
for (const p of Object.keys(job.pages).filter((p) => p.startsWith('/tr/'))) {
  out.extras++;
  const at = p.slice(4), [pn, sn] = at.split(':');
  for (const kept of [[], ...ALL.map((k) => [k])]) {
    const got = answer(p, '', kept), x = sh.tr.order.find((t) => t.key === kept[0]);
    const piece = x && (x.secs[pn] || []).includes(+sn) && get(`tr-${x.key}-${Math.floor(+pn / 20)}`)[at];
    const want = piece ? sh.tr.frame[0] + piece[0] + piece[1] + sh.tr.frame[1] : frame;
    if (got.status !== 200 || got.body !== want)
      out.bad.push({ path: p, kept: kept.join(' ') || 'none', why: 'not its frame around what is kept' });
  }
}

// A search with fewer translations kept: each not kept has its list saying
// so, in its place among the others, wherever the server's might stand (on
// the overview, or opened whole), and the rest of the page is the server's.
const RE_TR = /<section data-tr="([a-z0-9-]+)">[\s\S]*?<\/section>/g;
function lists(body) {
  const secs = {};
  const rest = body.replace(RE_TR, (m, k) => { secs[k] = m; return ''; }).replace('<div class="trhits"></div>', '');
  return { secs, rest };
}
const NOTKEPT = globalThis.ubT('tr:notkept');
for (const x of job.extras.filter((x) => x.path === '/search' && x.status === 200 && x.body !== undefined)) {
  const q = new URLSearchParams(x.query), scope = q.get('in') || '';
  if (!(scope === '' || ALL.includes(scope)) || !/[\p{L}\p{N}]/u.test(q.get('q') || '')) continue;
  const want = lists(x.body);
  for (const kept of [[], ...ALL.map((k) => [k])]) {
    out.extras++;
    const got = answer(x.path, x.query, kept), mine = lists(got.body);
    const name = `${x.path}?${x.query}`, why = [];
    if (got.status !== 200 || mine.rest !== want.rest) why.push('not the server\'s page around the lists');
    for (const t of sh.tr.order) {
      if (kept.includes(t.key)) {
        if (mine.secs[t.key] !== want.secs[t.key]) why.push(`${t.key}: not the server's list`);
      } else if ((scope === '' || scope === t.key)
                 && !(mine.secs[t.key] || '').includes(NOTKEPT)) why.push(`${t.key}: does not say it is not kept`);
    }
    if (why.length) out.bad.push({ path: name, kept: kept.join(' ') || 'none', why: why.join('; ') });
  }
}

// Every link in every page lands: on a page of the copy, a redirect to one, a
// page saying it is read online, or a file the copy keeps.
const assets = new Set(manifest.chunks.filter(c => c.kind === 'asset').map(c => c.name));
for (const h of hrefs) {
  out.links++;
  const [pq] = h.split('#');
  const [p, query] = pq.split('?');
  if (p.startsWith('/api/')) continue;        // the API itself, which only the server answers
  if (core.HOSTED.includes(p)) {               // the server's alone, by its host
    if (assets.has(pq)) out.broken.push({ href: h, why: 'kept in the copy, though it depends on the host' });
    continue;
  }
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
