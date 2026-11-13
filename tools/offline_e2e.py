"""Work offline, end to end, in Chrome: a first visit, which fetches the copy
with nothing tapped, the browser saving data or not, keep a translation in
it, read from the copy with the server not asked, read and search with the
network off, learn of a newer copy and take it, with the site's newer worker,
the page reloading itself after, survive an update that fails, say offline
while the site is gone though the browser is online, and online while the
browser says offline with the site there, keep it up to date by itself,
without a word, What's new? in the ?'s menu listing what the update brought;
and a first visit in a browser of its own, which goes on with a download that
was cut short, and reads from the copy first (2026-11-10).

    make e2e          (make offline, then .venv/bin/python tools/offline_e2e.py)

Playwright is in .venv as a dev requirement (requirements-dev.in), and drives
the system's Chrome.  It needs a built copy, which `make e2e` builds.  It
serves a scratch copy of var/offline/ from a server of its own, on
127.0.0.1:8131 with the visit counter off, so that it can make a "newer build"
by changing that copy, and leaves var/offline/ and the dev server alone.
localhost is a secure context, so the worker runs there as on the live site.
Not a gate: offline/check.py is, for every page; this shows that the worker,
the icon at the header's corner and Settings' Offline tab do what they say.
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The rail's link to Paper 1, as the contents chosen draw it (ub.js tocApply).
RAIL1 = """document.querySelector('.rail a[href="/1"]').textContent"""
BASE = "http://localhost:8131"
SERVER = """
import asyncio, os, pathlib, sys, types
os.environ["UB_VISITS"] = "off"
sys.path.insert(0, sys.argv[2])
import uvicorn
from starlette.responses import Response
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
TAG = A.OFFLINE.with_name("sw-tag")

# A newer worker, while the test has written TAG: the site's, and TAG after it.
@A.app.middleware("http")
async def newer_worker(request, call_next):
    if request.url.path != "/sw.js" or not TAG.exists():
        return await call_next(request)
    body = A.service_worker(types.SimpleNamespace(headers={})).body + TAG.read_bytes()
    return Response(body, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

# A recording's file that is not there while the test has named it in FAIL,
# each asking of it counted in ASKED; and a slow network, for any address
# asked with e2e-slow in its query (the review of 2026-11-09).
FAIL, ASKED = A.OFFLINE.with_name("audio-fail"), A.OFFLINE.with_name("audio-asked")

@A.app.middleware("http")
async def test_network(request, call_next):
    if FAIL.exists() and request.url.path == FAIL.read_text().strip():
        with ASKED.open("a") as f:
            f.write(request.url.path + "\\n")
        return Response("gone for the test\\n", status_code=404, media_type="text/plain")
    if "e2e-slow" in request.url.query:
        await asyncio.sleep(5.5)
    return await call_next(request)

uvicorn.run(A.app, host="127.0.0.1", port=8131, log_level="info")
"""
# What the newer worker adds: it says, in a cache of its own, that it was
# installed, and that it was the worker asked to fetch the copy.
NEWER = """
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open('e2e').then(function (c) { return c.put('/installed', new Response('newer')); }));
});
self.addEventListener('message', function (e) {
  if (e.data && e.data.cmd === 'get')
    e.waitUntil(caches.open('e2e').then(function (c) { return c.put('/got', new Response('get')); }));
});
"""

fails: list[str] = []
# Merritt Horn's fold in Settings' Offline tab: each voice has one, drawn alike.
MH = "dialog.settings .recvoice[data-key='mh'] "

# Work offline's icon, and the line under the copy's tick in Settings' Offline
# tab that says what the copy is.
ICON = ".top .offline"
STATE = "dialog.settings .offcopy .state"


def ok(cond, what):
    print(("  ok    " if cond else "  FAIL  ") + what)
    if not cond:
        fails.append(what)


def change(copy: pathlib.Path, edit, names=("misc",), news: bool = True) -> dict:
    """A newer build of the scratch copy: each chunk named passed through `edit`,
    renamed by its new hash, and the manifest made to say so, with a line in
    its news unless `news` is false.  Returns the last chunk changed."""
    m = json.loads((copy / "manifest.json").read_text())
    for c in m["chunks"]:
        if c["name"] not in names:
            continue
        data = json.loads(gzip.decompress((copy / c["file"]).read_bytes()))
        raw = json.dumps(edit(data), ensure_ascii=False, separators=(",", ":")).encode()
        h = hashlib.sha256(raw).hexdigest()[:16]
        gz = gzip.compress(raw, 9, mtime=0)
        (copy / "c" / f"{h}.gz").write_bytes(gz)
        c.update(file=f"c/{h}.gz", hash=h, bytes=len(gz), raw=len(raw))
        m["build"] = hashlib.sha256(m["build"].encode() + h.encode()).hexdigest()[:16]
        changed = c
    # Each newer build a day after the last, from Christmas, with one change
    # made that morning, after any copy before it, for What's new to list.
    change.n = getattr(change, "n", 0) + 1
    d = (datetime.date(2026, 12, 24) + datetime.timedelta(days=change.n)).isoformat()
    m["made"] = f"{d}T12:00:00Z"
    if news:
        m.setdefault("news", {"items": [], "earlier": False})["items"].insert(
            0, {"t": f"{d}T11:00:00Z", "d": d, "s": f"A change made for this test, number {change.n}"})
    m["bytes"] = sum(x["bytes"] for x in m["chunks"])
    (copy / "manifest.json").write_text(json.dumps(m))
    return changed


def change_tr(copy: pathlib.Path, key: str, edit) -> None:
    """A revision of one translation in the scratch copy: its first chunk
    passed through `edit` and renamed by its new hash, and the translation's
    own build and size made to say so.  The copy's build does not move."""
    m = json.loads((copy / "manifest.json").read_text())
    t = next(x for x in m["translations"] if x["key"] == key)
    c = t["chunks"][0]
    data = json.loads(gzip.decompress((copy / c["file"]).read_bytes()))
    raw = json.dumps(edit(data), ensure_ascii=False, separators=(",", ":")).encode()
    h = hashlib.sha256(raw).hexdigest()[:16]
    gz = gzip.compress(raw, 9, mtime=0)
    (copy / "c" / f"{h}.gz").write_bytes(gz)
    c.update(file=f"c/{h}.gz", hash=h, bytes=len(gz), raw=len(raw))
    t["build"] = hashlib.sha256(t["build"].encode() + h.encode()).hexdigest()[:16]
    t["bytes"] = sum(x["bytes"] for x in t["chunks"])
    (copy / "manifest.json").write_text(json.dumps(m))


# A copy as a worker before 2026-10-14 kept it: each chunk unpacked, under
# have/ in place of gz/.  Returns how many chunks it unpacked.
UNPACK = """async () => { let n = 0;
  for (const name of (await caches.keys()).filter(k => k.startsWith('ub-copy-'))) {
    const c = await caches.open(name);
    for (const req of await c.keys()) {
      const u = new URL(req.url);
      if (!u.pathname.startsWith('/offline/gz/')) continue;
      const r = await c.match(req);
      const raw = await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
      await c.put(u.pathname.replace('/gz/', '/have/'), new Response(raw));
      await c.delete(req);
      n++;
    } }
  return n; }"""
# How the copy in use keeps its chunks: {gz: n, have: n}.
KEPT = """async () => { const out = {gz: 0, have: 0};
  for (const name of (await caches.keys()).filter(k => k.startsWith('ub-copy-')))
    for (const req of await (await caches.open(name)).keys()) {
      const m = /^\/offline\/(gz|have)\//.exec(new URL(req.url).pathname);
      if (m) out[m[1]]++; }
  return out; }"""

# An hour later, as the worker counts it: the next page loaded asks the site
# whether its copy is current, as it does at most once an hour.
HOUR_LATER = """async () => { const c = await caches.open('ub-meta');
  const m = await (await c.match('/offline/meta')).json(); m.checked = 0;
  await c.put('/offline/meta', new Response(JSON.stringify(m), {headers: {'Content-Type': 'application/json'}})); }"""

# The browser saying offline, in the pages of a tab where sessionStorage says
# so, as Chrome said with the network working until it was restarted
# (2026-10-27).  The worker's word is its own, and sw.js does not ask it.
SAYS_OFFLINE = """try { if (sessionStorage.getItem('ubSaysOffline'))
  Object.defineProperty(Navigator.prototype, 'onLine', { get: () => false }); } catch (e) {}"""
# The browser saving data, in the pages of a tab where sessionStorage says so:
# the copy is then not updated by itself, and the tab offers Update now
# (offline.js saving).  The one way, since 2026-10-30, to update by hand.
# Or where the test has set a cookie saying so, which it can before a tab's
# first page (the first visit, below).
SAVES_DATA = """try { if (sessionStorage.getItem('ubSavesData') || /ubSavesData=1/.test(document.cookie))
  Object.defineProperty(navigator, 'connection', { value: { saveData: true }, configurable: true }); } catch (e) {}"""

# What the page shows while an update runs, in the tab and on the icon's
# label, each line once, as it changes; in sessionStorage too, which the
# reload at its end keeps.
# An element's words as a reader of English has them: the interface is in the
# page in Russian too (ubsite/l10n.py), which CSS hides; its textContent has both.
EN = "(el => { const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent; })"


def en(pg, sel: str) -> str:
    """The English of an element's words, the Russian stripped (EN)."""
    return pg.eval_on_selector(sel, EN).strip()
WATCH = """() => { window.shown = []; sessionStorage.shown = '[]';
  const keep = () => { for (const t of [""" + EN + """(document.querySelector('dialog.settings .offcopy .state')),
                                        document.querySelector('.top .offline').title])
    if (!window.shown.includes(t)) window.shown.push(t);
    sessionStorage.shown = JSON.stringify(window.shown); };
  new MutationObserver(keep).observe(document.body, {subtree: true, childList: true, characterData: true,
                                                     attributes: true, attributeFilter: ['title']}); }"""


def wait_state(pg, test: str, timeout: int = 30000) -> None:
    """Until the tab's line passes `test`, a JavaScript expression in t."""
    pg.wait_for_function(f"(t => {test})({EN}(document.querySelector('{STATE}')))", timeout=timeout)


def update(pg, pressed=None, timeout: int = 60000) -> None:
    """Tap Update now, which reloads the page once the copy is in, and open the
    Offline tab of the page it reloads to.  `pressed` runs at once after the tap."""
    pg.evaluate("window.ubStay = 1")
    with pg.expect_event("load", timeout=timeout):
        pg.click("dialog.settings .offcopy .get")
        if pressed:
            pressed()
    ok(not pg.evaluate("window.ubStay"), "the page reloads itself once the copy is in")
    offline_tab(pg)
    wait_state(pg, "t.startsWith('Up to date')")


def unfold(pg) -> None:
    """The translations not shown beside the text fold away (base.html
    .offmore, 2026-11-04): opened, so that their ticks can be read and tapped."""
    if pg.locator("dialog.settings .offmore:not([hidden])").count() and \
            not pg.evaluate("document.querySelector('dialog.settings .offmore').open"):
        pg.click("dialog.settings .offmore > summary")


def offline_tab(pg) -> None:
    """Open Settings at its Offline tab, which keeps the copy and the
    translations in it (base.html .offcopy, .offtr), unless it is open."""
    if not pg.is_visible("dialog.settings"):
        pg.click(".gear")
    pg.click("#set-t-offline")
    pg.wait_for_selector("dialog.settings .offcopy", state="visible")
    unfold(pg)


def asked_for(log: pathlib.Path, path: str) -> int:
    """How many times the server has been asked for `path`, with any query
    where `path` names none, by its log, which writes a path as uvicorn
    quotes it, 102%3A3, and a query as it came."""
    at, sep, query = path.partition("?")
    return len(re.findall('"GET ' + re.escape(urllib.parse.quote(at) + sep + query) + "[ ?]", log.read_text()))


# Whether the worker's copy answers first: sw.js meta.sure.
SURE = ("async () => { const r = await (await caches.open('ub-meta')).match('/offline/meta');"
        " return r ? !!(await r.json()).sure : null; }")


# What the worker keeps under a key of its meta (sw.js): `current`, the copy's
# build; `auto`, false while Automatic updates is turned off, and absent on.
META = "async k => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())[k]"
# Automatic updates, the switch under Base (base.html .offauto).
AUTO = "dialog.settings .offcopy input.auto"


def until(pg, fn: str, want=True, timeout: int = 15000, arg=None) -> bool:
    """Wait until the page's function `fn`, which may be async, answers
    `want`.  Playwright's wait_for_function does not wait for a promise: it
    takes one as true, at once."""
    end = time.time() + timeout / 1000
    while time.time() < end:
        try:
            if pg.evaluate(fn, arg) == want:
                return True
        except Exception:                          # noqa: BLE001  the page is between two documents
            pass
        pg.wait_for_timeout(100)
    return False


# A search for a word the Russian translations have, as the server's log
# writes its address.
BOG = "/search?q=%D0%B1%D0%BE%D0%B3"


# A translation's row in it: its words, as a reader of English has them.
def tr_row(pg, key: str) -> str:
    return pg.inner_text(f"dialog.settings .offtrs li:has(input[value='{key}']) .st")


def tr_kept(pg, key: str, timeout: int = 60000) -> None:
    """Until the Offline tab says the translation `key` is kept."""
    pg.wait_for_function("k => document.querySelector(`.offtrs input[value='${k}']`).closest('li')"
                         ".querySelector('.st').textContent.startsWith('kept')", arg=key, timeout=timeout)


def icon(pg) -> dict:
    return pg.evaluate(f"(c => ({{net: c.dataset.net, have: c.dataset.have, title: c.title,"
                       f" shown: !c.hidden}}))(document.querySelector('{ICON}'))")


class Server:
    """The scratch copy's server, which a test can stop and start again, as a
    site that goes away while the browser stays online."""

    def __init__(self, copy: pathlib.Path, tmp: str):
        self.args = [str(ROOT / ".venv" / "bin" / "python"), "-c", SERVER, str(copy), str(ROOT)]
        self.tmp = tmp
        self.log = open(pathlib.Path(tmp) / "server.log", "w")
        self.proc = None

    def start(self) -> None:
        self.proc = subprocess.Popen(self.args, stdout=self.log, stderr=subprocess.STDOUT, cwd=self.tmp)
        for _ in range(50):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                return
            except OSError:
                time.sleep(0.2)

    def stop(self) -> None:
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self.proc = None


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        copy = pathlib.Path(tmp) / "offline"
        shutil.copytree(ROOT / "var" / "offline", copy)
        srv = Server(copy, tmp)
        try:
            srv.start()
            return run(copy, pathlib.Path(tmp) / "server.log", srv)
        finally:
            srv.stop()


def run(copy: pathlib.Path, log: pathlib.Path, srv: Server) -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        ctx = b.new_context()
        ctx.add_init_script(SAYS_OFFLINE)
        ctx.add_init_script(SAVES_DATA)
        # A fresh context is a first visit, which the tour would meet (help.js).
        ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        pg = ctx.new_page()
        accept = lambda d: d.accept()
        pg.on("dialog", accept)
        asked = []
        pg.on("dialog", lambda d: asked.append(d.message))
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("A first visit, the browser saving data")
        # Saving data or not, the copy is fetched by itself (Tigran,
        # 2026-11-10: 49 MB is not too much); saving data only holds back the
        # updates after it, which this test then takes by hand, with Update now.
        ctx.add_cookies([{"name": "ubSavesData", "value": "1", "url": BASE}])
        pg.goto(BASE + "/101:4")
        pg.evaluate("sessionStorage.setItem('ubSavesData', '1')")
        ctx.clear_cookies()
        ok(pg.get_attribute("p.t .playp", "aria-label") == "Listen to this section, from its heading",
           "online, the first paragraph's play button starts the section")
        i = icon(pg)
        ok(i["shown"] and i["net"] == "on" and not pg.locator("footer[data-copy]").count()
           and not pg.evaluate("!!navigator.serviceWorker.controller"),
           f"the first page is the server's, with no worker yet; the icon at the header's corner says online ({i['title']!r})")
        host = pg.evaluate("getComputedStyle(document.querySelector('.brand .host'), '::before').content")
        ok(host == '"localhost:8131"' and not pg.inner_text(".brand .host"),
           f"the site's address stands under the name, drawn from the page's own, written by no server ({host})")
        ok(not pg.locator("#offmenu").count(), "the icon has no menu")
        pg.click(ICON)
        pg.wait_for_selector("dialog.settings .offcopy", state="visible")
        unfold(pg)
        ok(pg.get_attribute("#set-t-offline", "aria-selected") == "true", "a tap on it opens Settings at the Offline tab")
        ok(pg.inner_text("dialog.settings .net .host") == "localhost:8131"
           and pg.inner_text("dialog.settings .net").lower().startswith("online"),
           "whose first line says online, and names the site from its address")
        ok(not pg.locator("dialog.settings .panel.offline input[name]").count(),
           "and which stores no setting: the copy and its translations are the worker's")
        m = json.loads((copy / "manifest.json").read_text())
        t = time.time()
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        said = pg.inner_text(STATE)
        print(f"  downloaded in {time.time() - t:.1f} s: " + said)
        hint = pg.evaluate(EN + "(document.querySelector('dialog.settings .offcopy .hint'))")
        ok(not pg.locator("dialog.settings .offcopy input:not(.auto)").count()
           and not pg.locator("dialog.settings .offcopy button").count()
           and hint.startswith("The whole site, which this browser keeps"),
           f"the copy, Base, has no tick and no button: it came by itself, with nothing tapped, the browser saving data ({hint!r})")
        ok(pg.is_checked(AUTO) and pg.is_enabled(AUTO) and pg.evaluate(META, "auto") is None,
           "Automatic updates stands under it, on, with nothing kept of it until it is turned off")
        fetched = log.read_text().count("/offline/c/")
        ok(fetched == len(m["chunks"]), f"fetching each of its chunks once, and no translation's ({fetched} chunks)")
        sizes = [tr_row(pg, t["key"]) for t in m["translations"]]
        ok(pg.evaluate("[...document.querySelectorAll('.offtrs input')].every(i => !i.disabled && !i.checked)")
           and all(x.endswith(" MB") for x in sizes),
           f"the translations are offered, each with its size, for the reader to choose ({sizes})")
        ud = next(t for t in m["translations"] if t["key"] == "ud")
        before = log.read_text().count("/offline/c/")
        pg.check(".offtrs input[value=ud]")
        tr_kept(pg, "ud")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        said = pg.inner_text(STATE)
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == len(ud["chunks"]), f"a translation ticked is fetched at once, its chunks alone ({fetched} chunks)")
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]) + len(ud["chunks"]), f"the copy and the translation, in one cache ({kept})")
        ok(icon(pg)["have"] == "kept", f"the icon says a copy is kept ({icon(pg)['title']!r})")
        made = datetime.datetime.fromisoformat(m["made"].replace("Z", "+00:00"))
        ok(f"kept as the site was on {made:%B} {made.day}, with the text of" in said,
           "the tab says when the site was as the copy keeps it")
        # Base's size is Base's alone: the translation's is on its own row
        # (Tigran, 2026-11-10; until then the line counted it too, and a
        # reader would add the rows to it).
        ok(f"{m['bytes'] / 1e6:.1f} MB in this browser" in said
           and tr_row(pg, "ud") == f"kept, {ud['bytes'] / 1e6:.1f} MB",
           f"and says the copy's own size, the translation's on its own row ({tr_row(pg, 'ud')})")
        used = pg.evaluate("navigator.storage.estimate().then(e => e.usage)")
        print(f"  the browser keeps {used / 1e6:.1f} MB: {m['bytes'] / 1e6:.1f} MB gzipped, {m['raw'] / 1e6:.1f} MB unpacked")
        ok(used < (m["bytes"] + ud["bytes"]) * 1.25, "it keeps the copy gzipped, as it came")
        ok("asks the server only for what it does not hold" in said, "and that the site reads from it")
        # The copy first (2026-11-10): a page it holds comes from it, the
        # server not asked, and is the server's page, with no mark on it.
        ok(pg.evaluate(SURE) is True, "the copy just fetched is the site's, and answers first")
        pg.keyboard.press("Escape")
        ok(not pg.is_visible("dialog.settings"), "Escape closes Settings")
        n = asked_for(log, "/102:3")
        pg.goto(BASE + "/102:3")
        ok(asked_for(log, "/102:3") == n and pg.locator("p.t[id='102:3.1']").count() == 1
           and pg.evaluate("!!navigator.serviceWorker.controller"),
           f"online, the next page is read from the copy, and the server is not asked for it ({pg.title()!r})")
        ok(not pg.locator("footer[data-copy]").count() and icon(pg)["net"] == "on",
           "it is the server's page, unmarked, and the icon says online")
        n = asked_for(log, "/search?q=mercy")
        pg.goto(BASE + "/search?q=mercy")
        ok(asked_for(log, "/search?q=mercy") == n and "In the text" in pg.inner_text("main"),
           "and so is a search, with no translation shown that the copy lacks")
        n = asked_for(log, "/static/ub.css")
        pg.reload()
        ok(asked_for(log, "/static/ub.css") == n, "nor is the stylesheet asked for")
        pg.goto(BASE + "/101:4")
        pg.keyboard.press("Escape")
        ok(not pg.is_visible("dialog.settings"), "Escape closes Settings")
        # Updated by hand, with Update now, until "Kept up to date by itself":
        # the browser saving data is the one case, besides a try that stopped,
        # where the copy is not updated by itself (offline.js saving).

        print("A translation kept in it")
        offline_tab(pg)
        pg.wait_for_function("[...document.querySelectorAll('.offtrs input')].every(i => !i.disabled)", timeout=10000)
        sizes = [tr_row(pg, t["key"]) for t in m["translations"]]
        ok(all(x.endswith(" MB") for x in sizes) and pg.is_hidden("dialog.settings .offtr .why"),
           f"with a copy kept, each is offered with its size, the one kept saying so ({sizes})")
        # Unticking one asks first (Tigran, 2026-11-10); cancelled, nothing is
        # let go and the tick comes back.
        asked.clear()
        pg.remove_listener("dialog", accept)
        pg.once("dialog", lambda d: d.dismiss())
        pg.click(".offtrs input[value=ud]")
        pg.on("dialog", accept)
        print(f"  asked: {asked[0] if asked else None!r}")
        ok(asked and asked[0] == "This deletes Урантийские документы (Aivazian) from this browser, "
                                 f"{ud['bytes'] / 1e6:.1f} MB. To have it again, you would tick it and download it anew.",
           "unticking a translation asks first, naming it and what it takes")
        pg.wait_for_timeout(300)
        ok(pg.is_checked(".offtrs input[value=ud]") and tr_row(pg, "ud").startswith("kept")
           and pg.evaluate(KEPT)["gz"] == len(m["chunks"]) + len(ud["chunks"]),
           "and cancelled, the tick comes back and the translation stays")
        pg.uncheck(".offtrs input[value=ud]")
        pg.wait_for_function("document.querySelector('.offtrs input[value=ud]').closest('li')"
                             ".querySelector('.st').textContent.startsWith('kept') === false", timeout=10000)
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]), f"accepted, it is let go, the copy staying ({kept})")
        # Its chunks come from the browser's own cache now, so the server's log
        # cannot count them: the copy's cache can.
        pg.check(".offtrs input[value=ud]")
        tr_kept(pg, "ud")
        print("  " + tr_row(pg, "ud"))
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]) + len(ud["chunks"]),
           f"ticked again, it is downloaded at once, into the copy's own cache, beside the rest ({kept})")
        ok(not pg.is_checked(".offtrs input[value=urantia-ru]"), "the other is not kept")
        wait_state(pg, "t.startsWith('Up to date')")
        ok(f"{m['bytes'] / 1e6:.1f} MB in this browser" in pg.inner_text(STATE)
           and tr_row(pg, "ud") == f"kept, {ud['bytes'] / 1e6:.1f} MB",
           "the copy's line still says its own size, and the translation's row its own")
        pg.keyboard.press("Escape")

        print("Translations beside the text")
        pg.goto(BASE + "/1:1")
        ok(not pg.locator(".tf").first.is_visible(), "none is shown until a reader ticks one")
        pg.evaluate("ubSettings.set('translations', 'urantia-ru ud')")
        pg.goto(BASE + "/1:1")
        ok(pg.locator(".tf .trfold").first.inner_text() == "2 translations",
           f"ticked, a fold under each paragraph says how many ({pg.locator('.tf .trfold').first.inner_text()!r})")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .rt")
        # Its words, without the soft hyphens of its own hyphenation.
        words = lambda i: pg.evaluate("i => document.querySelectorAll('.tf.open .rt')[i].textContent"
                                      ".replace(/\u00ad/g, '')", i)
        ok("Из всех имен, под которыми" in words(0),
           "opened, it shows the first in the reader's order, the USGNY's, which the copy does not keep:"
           " the section's translations are the server's while one shown is not kept")
        pg.locator(".tf.open .trtabs button[data-tab=ud]").click()
        pg.wait_for_function("document.querySelector('.tf.open .rt').textContent.includes('Из всех имён')")
        ok(True, "a tab shows another, Aivazian's")
        pg.locator(".tf .trfold").nth(1).click()
        pg.wait_for_function("document.querySelectorAll('.tf.open .rt').length > 1")
        ok("Всеобщий Отец никогда" in words(1), "and the next fold opens at the tab chosen")
        fold = pg.locator(".grid > .row:has(p.t[id='1:1.3']) .tf")
        fold.locator(".trfold").click()
        fold.locator('.tr a.fn[data-k="tn"]').first.click()
        pg.wait_for_selector(".pop.tn")
        card = pg.evaluate("(() => { const c = document.querySelector('.pop.tn'), x = c.cloneNode(true);"
                           " x.querySelectorAll('x-ru').forEach(e => e.remove());"
                           " return x.textContent.replace(/­/g, ''); })()")
        ok("Note 6" in card and "Английское слово you" in card and "(Aivazian)" in card,
           "a translator's number opens its note as a card, which names the translation")
        pg.keyboard.press("Escape")
        ok(pg.locator(".pop").count() == 0, "and Escape closes it")
        pg.goto(BASE + "/140:4")
        ok(pg.locator(".tf .trfold").first.inner_text() == "1 translation",
           "a section one of them lacks counts the other alone")

        print("Compare")                                          # a setting since 2026-11-08
        pg.goto(BASE + "/1:1")
        ok(pg.locator(".cmphead, .cmpbtn").count() == 0, "no button at the head of the text")
        pg.click(".gear")
        pg.click("#set-t-translations")
        ok(pg.is_enabled("dialog.settings input[name=compare]"),
           "Translations in parallel columns, under the list, can be ticked while one is")
        pg.check("dialog.settings input[name=compare]")
        pg.wait_for_selector("article.cmp .rc .rt")
        pg.keyboard.press("Escape")
        cols = pg.evaluate("[...document.querySelectorAll('article.cmp .cmphd > .ch')].map(c => c.dataset.k || 'en')")
        ok(pg.url.endswith("/1:1") and cols == ["en", "urantia-ru", "ud"],
           f"ticked, the page is drawn again in place, the English and each one ticked a column each, in the reader's order ({cols})")
        ok(pg.locator(".tf").first.is_hidden(), "and the folds give way to the columns")
        pg.locator('.rc[data-k=ud] a.fn[data-k="tn"]').first.click()
        pg.wait_for_selector(".pop.tn")
        ok("Note 6" in pg.inner_text(".pop.tn"), "a translator's number in its column opens its card")
        pg.keyboard.press("Escape")
        pg.click(".transport .next")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:2"), f"the transport bar's next section opens in it ({pg.url})")
        pg.goto(BASE + "/140:4")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.evaluate("[...document.querySelectorAll('article.cmp .cmphd > .ch')].map(c => c.dataset.k || 'en')")
           == ["en", "urantia-ru"], "a translation without the section has no column")

        print("Compare kept as one moves about")                  # Tigran, 2026-11-06; a setting since 2026-11-08
        pg.goto(BASE + "/1:1")
        pg.wait_for_selector("article.cmp .rc .rt")
        pg.fill("form.find input", "Father")
        pg.press("form.find input", "Enter")
        pg.wait_for_selector("main.results")
        hit = pg.evaluate("[...document.querySelectorAll('main.results ul.hits a')].map(a => a.getAttribute('href'))"
                          ".find(h => /^\\/\\d+:\\d+\\.\\d+$/.test(h))")
        pg.click(f'main.results a[href="{hit}"]')
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith(hit), f"a search hit opens its paragraph in Compare ({pg.url})")
        pg.goto(BASE + "/1:0")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:0"), f"so does an address typed into the tab ({pg.url})")
        # The study note citing 1:2.9 (data/study/001.toml), opened at its number.
        note = pg.evaluate("document.querySelector('[id^=fnst] a[href=\"/1:2.9\"]').closest('[id^=fnst]').id")
        pg.click(f'a.fn[href="#{note}"]')
        pg.wait_for_selector(".pop.st")
        pg.click('.pop.st a[href="/1:2.9"]')
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:2.9") and pg.locator("p.t.hit").count() == 1,
           f"a study note's reference opens its paragraph in Compare ({pg.url})")
        pg.fill("form.find input", "1:4.2")
        pg.press("form.find input", "Enter")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:4.2"), f"and a citation typed into the box, past the server's redirect ({pg.url})")
        pg.goto(BASE + "/1:3.2/compare")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:3.2") and pg.locator("p.t.hit").count() == 1,
           f"an old Compare address goes to the page's own ({pg.url})")
        pg.evaluate("ubSettings.set('whole', true)")
        pg.goto(BASE + "/1")
        pg.wait_for_selector("article.cmp .cmphd")
        pg.click(f'a.fn[href="#{note}"]')
        pg.wait_for_selector(".pop.st")
        pg.click('.pop.st a[href="/1:2.9"]')
        pg.wait_for_function("document.getElementById('1:2.9').classList.contains('hit')")   # arrive(), on hashchange
        ok(pg.url.endswith("/1#1:2.9") and pg.locator("p.t.hit").count() == 1,
           f"on the whole paper's page a note's reference is a place on it, in Compare ({pg.url})")
        pg.go_back()
        pg.wait_for_function("!location.hash && !document.querySelector('p.t.hit')")
        top = pg.evaluate("(() => { const r = [...document.querySelectorAll('main p.t[id]')]"
                          ".find(p => p.getBoundingClientRect().bottom > 40); return r ? r.id : null; })()")
        ok(pg.url.endswith("/1") and top == "1:0.1",
           f"and Back returns to where the page stood, the mark gone (Tigran, 2026-11-06; {pg.url}, {top})")
        pg.evaluate("ubSettings.set('whole', false)")
        pg.goto(BASE + "/1:4")
        pg.wait_for_selector("article.cmp .rc .rt")
        pg.click(".gear")                     # scrolled to by the click: the page's place is set after
        pg.click("#set-t-translations")
        pg.evaluate("scrollTo(0, document.getElementById('1:4.3').closest('.row').getBoundingClientRect().top + scrollY - 10)")
        pg.uncheck("dialog.settings input[name=compare]")             # off: the pages after expect it so
        pg.wait_for_function("!document.querySelector('article.cmp')")
        pg.keyboard.press("Escape")
        top = pg.evaluate("(() => { const r = [...document.querySelectorAll('main p.t[id]')]"
                          ".find(p => p.getBoundingClientRect().bottom > 40); return r ? r.id : null; })()")
        ok(pg.locator(".tf").first.is_visible() and top == "1:4.3",
           f"unticked, the folds are back and the paragraph at the top stays there ({top})")
        pg.reload()
        pg.wait_for_selector("main.reader")
        ok(pg.locator("article.cmp").count() == 0, "and a reload leaves it off")
        pg.evaluate("ubSettings.set('translations', '')")
        pg.click(".gear")
        pg.click("#set-t-translations")
        ok(pg.is_disabled("dialog.settings input[name=compare]"),
           f"with none ticked its switch is greyed ({pg.url}, {pg.evaluate('ubSettings.get().translations')!r},"
           f" {pg.get_attribute('dialog.settings label:has(input[name=compare])', 'class')!r})")
        pg.keyboard.press("Escape")
        pg.evaluate("ubSettings.set('translations', 'urantia-ru ud')")

        print("The contents in a translation")
        pg.goto(BASE + "/1:1")
        opts = pg.evaluate("[...document.querySelectorAll('.railtr option')].map(o => o.textContent)")
        ok(pg.is_visible(".railtr select") and opts == ["Uversa Press", "USGNY", "Aivazian"],
           f"the rail's line offers the book and each one ticked, in the reader's order ({opts})")
        pg.select_option(".railtr select", "ud")
        pg.wait_for_function("""document.querySelector('.rail a[href="/1"]').textContent.includes('Всеобщий Отец')""")
        part = pg.inner_text('.rail a[href="/part/1"]')
        ok(part.startswith("Часть I. Центральная"), f"chosen, the rail is that one's contents ({part!r})")
        ok(pg.locator(".rail a.untr").count() > 0 and "Introduction" not in pg.inner_text('.rail a[href="/1:0"]'),
           "what it has not stays in English, greyed, and a paper's introduction is «0. Введение»")
        pg.goto(BASE + "/1:2")
        pg.wait_for_selector(":root.tocready")
        ok("Всеобщий Отец" in pg.evaluate(RAIL1), "and stays chosen from page to page")
        pg.select_option(".railtr select", "")
        pg.wait_for_function("""document.querySelector('.rail a[href="/1"]').textContent.includes('The Universal Father')""")
        ok(pg.locator(".rail a.untr").count() == 0, "Uversa Press puts the book's contents back")

        # What the server sends, to hold the worker's answers to.
        want = {}
        urls = ["/101:4", "/101:4.2-3", "/i/god", "/appendix/A", "/lists/1955", "/index/G", "/", "/read",
                "/part/2", "/search?q=prayer", "/search?q=self-conscious&in=text", "/search?q=Badanon&in=notes",
                "/i/jesus/read", "/i/prayer/read/theme",
                "/rail/120?v=1", "/static/fonts/UBGoudy.woff2", "/speech/101:4", "/speech/0:0", "/changelog",
                "/quiz", "/quiz/32", "/101"]
        for u in urls:
            with urllib.request.urlopen(BASE + u) as r:
                want[u] = r.read()

        print("Keeping a recording")
        # Paper 161, the smallest: four files, 16.6 MB, from this machine's
        # copy of the DVD (sources.toml audio.mh), kept in a cache of its own,
        # one file a message (sw.js, The recordings kept).
        pg.goto(BASE + "/101:4")
        offline_tab(pg)
        pg.click("dialog.settings .recvoice[data-key='mh'] > summary .rname")
        pg.wait_for_selector("dialog.settings .recvoice[data-key='mh'] .recpart", timeout=15000)
        ok(pg.locator(MH + ".recpart").count() == 4 and pg.locator(MH + ".recrow").count() == 197,
           "Merritt Horn's reading opens to its four parts and 197 papers")
        # Each voice has its fold (2026-11-12): Григорий Войнер's reading of
        # USGNY under Merritt Horn's, its tree under that translation's titles.
        VR = "dialog.settings .recvoice[data-key='voyner'] "
        pg.wait_for_selector(VR + ".recpart", state="attached", timeout=15000)
        ok(pg.locator("dialog.settings .recvoice").count() == 2
           and en(pg, VR + "> summary .rname") == "Grigory Voyner" and en(pg, VR + "> summary .rpt") == "· USGNY"
           and en(pg, VR + "> summary .rmeta") == "154 h · 4.48 GB",
           f"the Russian reading has its fold, named with its translation ({en(pg, VR + '> summary .w')!r}, {en(pg, VR + '> summary .rmeta')!r})")
        ok(pg.locator(VR + ".recpart").count() == 4 and pg.locator(VR + ".recrow").count() == 197
           and "Отец Всего Сущего" in pg.evaluate(f"document.querySelector(\"{VR}.recrow[data-n='1'] .rname\").textContent"),
           "with its four parts and 197 papers, under the translation's titles")
        ok(en(pg, "dialog.settings .recvoice[data-key='mh'] > summary .rmeta") == "121 h · 6.98 GB",
           "its row says its hours and size")
        pg.click("dialog.settings .recvoice[data-key='mh'] .recpart[data-first='120'] > summary .rname")
        row = "dialog.settings .recvoice[data-key='mh'] .recrow[data-n='161'] .keep"
        ok(pg.get_attribute(row, "data-st") == "none" and pg.get_attribute(row, "title") == "Keep Paper 161 offline (17 MB)",
           f"Paper 161's row offers to keep it ({pg.get_attribute(row, 'title')!r})")
        # Its third file not there: the download stops, and asks for it once,
        # where it asked again at once, for ever (review of 2026-11-09), and the
        # tab offers to try again, which, the file back, keeps the paper.
        gone = "/audio/mh/paper161/P161_02.mp3"
        fail, tries = copy.with_name("audio-fail"), copy.with_name("audio-asked")
        fail.write_text(gone)
        pg.click(row)
        pg.wait_for_selector("dialog.settings .offrec .why .recagain", timeout=120000)
        pg.wait_for_timeout(3000)
        n = len(tries.read_text().split()) if tries.exists() else 0
        ok(n == 1, f"a file that fails is asked for once, not again and again ({n} times in 3 s)")
        ok(en(pg, "dialog.settings .offrec .why").startswith("The download stopped: paper161/P161_02.mp3 could not be fetched (404). Try again"),
           f"and the tab says why, with Try again ({en(pg, 'dialog.settings .offrec .why')!r})")
        fail.unlink()
        pg.click("dialog.settings .offrec .why .recagain")
        pg.wait_for_function(f"document.querySelector(\"{row}\").dataset.st === 'kept'", timeout=120000)
        kept = pg.evaluate("caches.open('ub-audio-mh').then(c => c.keys()).then(ks => ks.map(k => new URL(k.url).pathname).sort())")
        ok(kept == [f"/audio/mh/paper161/P161_0{i}.mp3" for i in range(4)], f"its four files are in the cache ({kept})")
        ok(pg.get_attribute(row, "title") == "Kept, 17 MB; tap to let go"
           and en(pg, "dialog.settings .recvoice[data-key='mh'] .recpart[data-first='120'] > summary .rst") == "1 of 77 papers"
           and en(pg, "dialog.settings .recvoice[data-key='mh'] > summary .rst") == "1 of 197 papers kept, 17 MB",
           "the row, its part and the voice say so")
        ok(en(pg, "dialog.settings .recstate").startswith("17 MB kept in this browser; room for about"),
           f"and the block counts it against the browser's room ({en(pg, 'dialog.settings .recstate')!r})")
        ok(not pg.evaluate("[...document.querySelectorAll('dialog.settings .offtrs li')].length") == 0
           and pg.get_attribute("dialog.settings .offmore", "hidden") is None,
           "the translations not shown beside the text fold away under a line")
        pg.keyboard.press("Escape")

        print("Offline")
        pg.reload()
        ok(pg.evaluate("!!navigator.serviceWorker.controller"), "the page is the worker's")
        # A slow network, 5.5 s, past the worker's WAIT of 4: an address the copy
        # holds nothing for is the network's to answer, however long it takes,
        # where until 2026-11-09 the copy's own 404 or "read online" answered at
        # 4 s and the site's was thrown away (a stylesheet of a newer build).
        got = pg.evaluate("Promise.all(['/static/ub.css?v=e2e-slow', '/quiz/board?e2e-slow=1'].map(u =>"
                          " fetch(u).then(r => r.text().then(t => [r.status, t.includes('read online')]))))")
        ok(got == [[200, False], [200, False]], f"a slow network's answer is waited for where the copy has none ({got})")
        ctx.set_offline(True)
        probe = ("async (a) => { try { const r = await fetch(a[0], a[1] ? {headers: {Range: a[1]}} : {});"
                 " const b = await r.arrayBuffer(); return [r.status, r.headers.get('content-range'), b.byteLength]; }"
                 " catch (e) { return ['rejected']; } }")
        f = "/audio/mh/paper161/P161_00.mp3"
        ok(pg.evaluate(probe, [f, None]) == [200, None, 1163180], "offline, a kept file answers whole")
        ok(pg.evaluate(probe, [f, "bytes=100-199"]) == [206, "bytes 100-199/1163180", 100]
           and pg.evaluate(probe, [f, "bytes=0-"]) == [206, "bytes 0-1163179/1163180", 1163180],
           "a range of it is cut from the cache, 206 with its Content-Range, as a seek asks")
        ok(pg.evaluate(probe, [f, "bytes=5000000-"]) == [416, "bytes */1163180", 0], "a range past its end is 416")
        ok(pg.evaluate(probe, ["/audio/mh/paper101/P101_04.mp3", None]) == ["rejected"], "a file not kept fails, as before")
        pg.goto(BASE + "/161:1")
        pg.locator("p.t .playp").first.click()
        pg.wait_for_timeout(4000)
        ok(pg.get_attribute(".player .toggle", "aria-label") == "Pause" and not pg.inner_text(".player .who"),
           f"offline, the kept paper plays ({pg.get_attribute('.player .toggle', 'aria-label')}, {pg.inner_text('.player .who')!r})")
        ok(pg.get_attribute(".player .keep", "data-st") == "kept" and pg.is_disabled(".player .keep"),
           "and the bar's ↓ shows it kept, a sign and no more")
        # From wherever it has got to: the heading is 3.79 s long, and whether
        # it is over after those four seconds is how soon the playing began
        # (this asked for 161:1.1 until 2026-11-12, and failed when it began at once).
        onto = "161:1.2" if pg.inner_text(".player .at") == "161:1.1" else "161:1.1"
        pg.click(".player .next")
        pg.wait_for_timeout(4000)
        ok(pg.get_attribute(".player .toggle", "aria-label") == "Pause" and pg.inner_text(".player .at") == onto
           and not pg.inner_text(".player .who"),
           f"the next paragraph plays on, its seek answered from the cache ({pg.get_attribute('.player .toggle', 'aria-label')},"
           f" {pg.inner_text('.player .at')!r}, {pg.inner_text('.player .who')!r})")
        pg.click(".player button.close")
        for u in urls:
            got = pg.evaluate("u => fetch(u).then(r => r.arrayBuffer()).then(b => Array.from(new Uint8Array(b)))", u)
            # The one thing the worker adds: the footer's note of the copy's date,
            # in Russian too (2026-10-25).
            got = re.sub(rb'\n<footer data-copy="[^"]*"(?: data-copy-ru="[^"]*")?>', b"\n<footer>", bytes(got))
            if u.startswith("/search?q=prayer"):
                # And among a search's lists, urantia-ru's, ticked and not kept,
                # saying it is not searched, which the server never sends.
                got, n = re.subn(rb'<div class="trhits"><section data-tr="urantia-ru">.*?not in the offline copy'
                                 rb'.*?</section></div>', b"", got, flags=re.S)
                ok(n == 1, "a search offline says a translation ticked and not kept is not searched")
            ok(got == want[u], f"{u}: as the server sends it ({len(got):,} bytes)")
        t = time.time()
        pg.goto(BASE + "/search?q=thought+adjuster")
        print(f"  a first search, the engine starting: {(time.time() - t) * 1000:.0f} ms")
        ok("In the text" in pg.inner_text("main"), "a search answers offline")
        t = time.time()
        pg.goto(BASE + "/search?q=morontia+mota")
        print(f"  a second: {(time.time() - t) * 1000:.0f} ms")
        # The translations among the results (2026-10-26): ud kept, urantia-ru not.
        pg.goto(BASE + "/search?q=%D0%BE%D0%B1%D1%8A%D0%B5%D0%B4%D0%B8%D0%BD%D0%B5%D0%BD%D0%BD%D1%8B%D0%BC")
        shown = pg.evaluate("[...document.querySelectorAll('.trhits > section')].filter(s => s.offsetParent)"
                            ".sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)"
                            ".map(s => s.dataset.tr)")
        ok(shown == ["urantia-ru", "ud"], f"a search lists each translation shown, in the reader's order ({shown})")
        ok("объединённым" in pg.inner_text(".trhits [data-tr=ud]"), "the one kept, from its own database, ё found by е")
        ok("not in the offline copy" in pg.inner_text(".trhits [data-tr=urantia-ru]"), "and one not kept says so")
        pg.locator(".trhits [data-tr=ud] li a").first.click()
        pg.wait_for_selector(".tf.open .rt")
        ok(pg.url.endswith("#tr-ud") and "объединённым" in words(0),
           "a hit opens its paragraph, with the fold at that translation")
        # The quiz (2026-10-28): a paper's questions asked and answered offline,
        # and what the browser keeps of it, which /quiz then shows.
        pg.goto(BASE + "/quiz/32")
        pg.wait_for_selector(".qopt")
        pg.locator(".qopt").nth(1).click()
        ok(pg.locator(".qopt.ok").count() == 1 and pg.locator(".qverdict.r").count() == 1,
           "a quiz is asked and answered offline")
        kept = pg.evaluate("JSON.parse(localStorage.getItem('ub_quiz')).first")
        ok(kept.get("366.1") == 2, f"its first answer kept, by id and layout ({kept})")
        pg.goto(BASE + "/quiz/board")
        ok("read online" in pg.inner_text("main"), "the quiz's board is said to be read online")
        pg.goto(BASE + "/101:4.2-3")
        ok(pg.locator("p.t.hit").count() == 2, "/101:4.2-3 marks two paragraphs")
        i = icon(pg)
        ok(i["net"] == "off" and i["have"] == "kept", f"the icon says offline ({i['title']!r})")
        pg.click(ICON)
        pg.wait_for_selector("dialog.settings .offcopy", state="visible")
        unfold(pg)
        print("  " + pg.inner_text("dialog.settings .net"))
        ok(pg.inner_text("dialog.settings .net").lower().startswith("offline"), "and so does the tab's first line")
        ok(pg.inner_text("dialog.settings .net .host") == "localhost:8131", "and names the site from the copy too")
        hosted = pg.evaluate("Promise.all(['/manifest.webmanifest', '/apple-touch-icon.png'].map(u =>"
                             " fetch(u).then(r => r.status, () => 'none')))")
        ok(hosted == ["none", "none"], f"the app's manifest and touch icon are the server's alone ({hosted})")
        tab = pg.evaluate("fetch('/static/favicon-burgundy.svg').then(r => r.status, () => 'none')")
        ok(tab == 200, f"but the other site's tab icon is in the copy ({tab})")
        pg.keyboard.press("Escape")
        ok(not pg.is_visible("dialog.settings"), "Escape closes Settings")
        ok("offline copy of" in pg.evaluate("getComputedStyle(document.querySelector('footer'), '::before').content"),
           "the footer says the page is from the offline copy")
        pg.evaluate("ubSettings.set('toc', 'ud')")
        pg.goto(BASE + "/1:1")
        pg.wait_for_selector(":root.tocready")
        ok("Всеобщий Отец" in pg.evaluate(RAIL1), "offline, the contents of the one kept draw the rail")
        pg.evaluate("ubSettings.set('toc', 'urantia-ru')")
        pg.goto(BASE + "/1:1")
        pg.wait_for_selector(":root.tocready")
        ok("The Universal Father" in pg.evaluate(RAIL1), "and one not kept leaves the rail in English")
        pg.evaluate("ubSettings.set('toc', '')")
        pg.evaluate("ubSettings.set('compare', true)")
        pg.goto(BASE + "/1:2")
        pg.wait_for_selector("article.cmp .rc[data-k=ud] .rt")
        ok("not in the offline copy" in pg.inner_text("article.cmp .cmphd > .ch[data-k=urantia-ru] .gap")
           and pg.locator("article.cmp .rc[data-k=urantia-ru] .rt").count() == 0,
           "Compare offline draws the one kept, and one not kept says so over its column")
        pg.goto(BASE + "/1:3/compare")
        pg.wait_for_selector("article.cmp .rc[data-k=ud] .rt")
        ok(pg.url.endswith("/1:3"), f"offline too an old Compare address goes to the page's own, the worker answering it ({pg.url})")
        pg.evaluate("ubSettings.set('compare', false)")           # off: the folds below
        pg.wait_for_function("!document.querySelector('article.cmp')")
        pg.goto(BASE + "/1:1")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .rt")
        ok("Из всех имён" in words(0), "a fold shows the translation kept, at the tab chosen")
        pg.locator(".tf.open .trtabs button[data-tab=urantia-ru]").click()
        pg.wait_for_selector(".tf.open .gap")
        ok("not in the offline copy" in pg.inner_text(".tf.open .gap"), "one not kept says so in its tab")
        pg.locator(".tf.open .trtabs button[data-tab=ud]").click()
        fold = pg.locator(".grid > .row:has(p.t[id='1:1.3']) .tf")
        fold.locator(".trfold").click()
        fold.locator('.tr a.fn[data-k="tn"]').first.click()
        pg.wait_for_selector(".pop.tn")
        ok("Note 6" in pg.inner_text(".pop.tn"), "and its notes open as cards")
        pg.keyboard.press("Escape")
        offline_tab(pg)
        ok("can be let go" in pg.inner_text("dialog.settings .offtr .why")
           and pg.is_disabled(".offtrs input[value=urantia-ru]") and pg.is_enabled(".offtrs input[value=ud]"),
           "offline, the Offline tab lets one kept go, and offers none to download")
        pg.uncheck(".offtrs input[value=ud]")
        pg.wait_for_function("document.querySelector('.offtrs input[value=ud]').closest('li')"
                             ".querySelector('.st').textContent.startsWith('kept') === false", timeout=10000)
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]), f"unticked, offline too, it is let go ({kept})")
        ok(asked and "You are offline: it can be downloaded again only once you are online." in asked[-1],
           f"asked first, saying that offline it cannot be had again until online ({(asked or [''])[-1][-75:]!r})")
        pg.keyboard.press("Escape")
        pg.wait_for_function("(document.querySelector('.tf.open .gap') || {}).textContent", timeout=10000)
        ok("not in the offline copy" in pg.inner_text(".tf.open .gap"), "and the folds open say so at once")
        pg.goto(BASE + "/2:1")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .gap")
        ok("not in the offline copy" in pg.inner_text(".tf.open .gap"), "as does a fold opened after")
        pg.evaluate("ubSettings.set('translations', '')")
        pg.goto(BASE + "/search?q=1:4.2")                # the search box's own example
        ok(pg.url.endswith("/1:4.2"), f"a citation typed into the box opens it ({pg.url})")
        pg.goto(BASE + "/101")
        ok(pg.url.endswith("/101:0"), "/101 opens 101:0")
        # Whole paper (2026-10-30): the setting on, a section's address opens
        # the whole paper at that section, joined offline from the sections'
        # pieces (offline/pages.py holes), its rail's section links scroll,
        # and off again, the paper's address opens the section being read.
        pg.evaluate("ubSettings.set('whole', true)")
        pg.goto(BASE + "/101:4")
        ok(pg.url.endswith("/101#101:4"), f"with Whole paper on, /101:4 opens the whole paper at its section ({pg.url})")
        ok(pg.locator("article.whole > section[id]").count() == 11 and pg.locator("main p.t").count() == 115,
           "the whole of Paper 101 is on the page, from the copy")
        ok(pg.evaluate("document.querySelector('.transport').children.length") == 2, "with the two paper buttons alone")
        ok(pg.evaluate("Math.abs(document.getElementById('101:4').getBoundingClientRect().top) < 80"),
           "scrolled to section 4")
        pg.evaluate("window.ubStay = 1")
        pg.click('.rail a[href="/101:6"]')
        pg.wait_for_function("location.hash === '#101:6'")
        # The link clicked is in the reader's unit now, /101#101:6 (ub.js).
        ok(pg.evaluate("window.ubStay") == 1 and pg.evaluate("document.querySelector('.rail li.here > details li.here a').getAttribute('href')") == "/101#101:6",
           "a section's link in the rail scrolls the page, and the rail marks the section")
        pg.goto(BASE + "/101:4.2-3")
        ok(pg.url.endswith("/101#101:4.2-3") and pg.locator("p.t.hit").count() == 2, "/101:4.2-3 marks its two paragraphs on the whole paper's page")
        # Compare on the whole paper, every section in columns, a translation
        # ticked and not kept saying so in each section's head: Paper 1, which
        # Aivazian's has (it ends at Paper 43), let go above.
        pg.evaluate("ubSettings.set('translations', 'ud')")
        pg.evaluate("ubSettings.set('compare', true)")
        pg.goto(BASE + "/1")
        pg.wait_for_selector("article.cmp .cmphd")
        ok(pg.locator("article.cmp .cmphd").count() == 8 and pg.locator("article.cmp .cmpnames").count() == 8,
           "Compare sets every section of the whole of Paper 1 in columns")
        ok(pg.locator("article.cmp .cmphd .gap").count() == 8, "each section's head says the translation is not kept")
        pg.evaluate("ubSettings.set('compare', false)")
        pg.wait_for_function("!document.querySelector('article.cmp')")
        pg.evaluate("ubSettings.set('translations', '')")
        pg.evaluate("ubSettings.set('whole', false)")
        pg.goto(BASE + "/read")                  # from another page: the same page's hash alone loads nothing
        pg.goto(BASE + "/101#101:5")
        ok(pg.url.endswith("/101:5"), f"off again, the whole paper's address opens the section it names ({pg.url})")
        pg.goto(BASE + "/i/humor/read")
        ok(pg.title().startswith("humor") and pg.locator("main p.t").count() > 3, "a reading path reads offline")
        pg.goto(BASE + "/i/humor/read/theme")
        ok("theme" in pg.title(), "and by theme")
        pg.goto(BASE + "/i/no-such-headword")
        ok("No headword" in pg.inner_text("main"), "an address the index lacks says so")
        pg.goto(BASE + "/api")
        ok(f"GET {BASE}/api/v1/text?since=0" in pg.inner_text("main") and "offline.invalid" not in pg.content(),
           "the page about the text API reads offline, naming the address it is read at")
        pg.goto(BASE + "/101:4")
        pg.locator("p.t .playp").first.click()
        pg.wait_for_function("(document.querySelector('.player .who') || {}).textContent"
                             " && document.querySelector('.player .who').textContent.includes('not kept')",
                             timeout=10000)
        pg.wait_for_timeout(1500)
        ok("not kept offline" in pg.inner_text(".player .who") and pg.evaluate("!speechSynthesis.speaking")
           and pg.get_attribute(".player .keep", "data-st") == "none",
           f"offline, a recording not kept refuses to play, saying where it is kept, and the message stays ({pg.inner_text('.player .who')!r})")
        ok(pg.inner_text(".player .voice") == "Merritt Horn", "and the bar still names the voice Settings chose")
        pg.click(".player .voice")
        pg.locator(".player .voices [role=group] button,"
                   " .player .voices button:has-text('Your browser\u2019s voice')").first.click()
        pg.wait_for_function("JSON.parse(localStorage.ub_settings || '{}').voice === 'browser'", timeout=5000)
        pg.wait_for_timeout(500)
        ok("connection" not in pg.inner_text(".player .who") and pg.inner_text(".player .voice") != "Merritt Horn",
           f"its voice menu turns to the browser's voice in place ({pg.inner_text('.player .voice')!r})")
        pg.click(".player button.close") if pg.locator(".player button.close").count() else None
        pg.evaluate("ubSettings.set('voice', '')")
        pg.evaluate("document.querySelectorAll('nav.rail li.lazy details')[40].open = true")
        pg.wait_for_selector("nav.rail li.lazy details[open] ol a", state="attached", timeout=5000)
        ok(True, "the rail opens another paper from the copy")
        offline_tab(pg)
        pg.click("dialog.settings .recvoice[data-key='mh'] > summary .rname")
        pg.wait_for_selector("dialog.settings .recvoice[data-key='mh'] .recpart", timeout=15000)
        pg.click("dialog.settings .recvoice[data-key='mh'] .recpart[data-first='120'] > summary .rname")
        pg.wait_for_selector("dialog.settings .recvoice[data-key='mh'] .recrow[data-n='161']", timeout=15000)
        ok(pg.get_attribute("dialog.settings .recvoice[data-key='mh'] .recrow[data-n='160'] .keep", "disabled") is not None
           and pg.get_attribute("dialog.settings .recvoice[data-key='mh'] .recrow[data-n='161'] .keep", "disabled") is None,
           "offline, a paper not kept cannot be asked for, and one kept can be let go")
        pg.click("dialog.settings .recvoice[data-key='mh'] .recrow[data-n='161'] .keep")
        until(pg, "() => caches.keys().then(ks => !ks.some(k => k.startsWith('ub-audio-')))", True, 10000)
        ok(asked and asked[-1].startswith("This deletes 1 paper of Merritt Horn from this browser, 17 MB.")
           and pg.get_attribute("dialog.settings .recvoice[data-key='mh'] .recrow[data-n='161'] .keep", "data-st") == "none",
           f"asked first, and let go, its cache goes with its last file ({(asked or [''])[-1][:60]!r})")
        pg.keyboard.press("Escape")
        ok(not errors, f"no script errors ({errors[:2]})")

        print("A copy kept unpacked, as before 2026-10-14")
        n = pg.evaluate(UNPACK)
        ok(n == len(m["chunks"]), f"{n} chunks unpacked under have/")
        for u, words in (("/150:1", "Evangelistic Corps"), ("/i/love/read", "love")):
            pg.goto(BASE + u)
            ok(words in pg.title() or words in pg.inner_text("main"), f"offline, {u} reads from it")
        ctx.set_offline(False)
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, packed"), d)[1])
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        before = log.read_text().count("/offline/c/")
        # What's new opens over Settings, a dialog over a dialog, and closes
        # back to it.
        pg.click("dialog.settings .offcopy .newsbtn")
        pg.wait_for_selector("#offnews", state="visible")
        ok(pg.is_visible("dialog.settings .offcopy .get"), "What's new opens over the tab")
        pg.click("#offnews .x")
        ok(pg.is_hidden("#offnews") and pg.is_visible("dialog.settings"), "and its × closes it, back to the tab")
        update(pg)
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"an update packs what it has rather than fetch it ({fetched} chunk fetched)")
        kept = pg.evaluate(KEPT)
        ok(kept == {"gz": len(m["chunks"]), "have": 0}, f"and keeps the new copy gzipped ({kept})")
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, packed", "offline, the copy is the newer one")

        print("A newer copy")
        ctx.set_offline(False)
        changed = change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, changed"), d)[1])
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        # What's new: the change made after this copy, and none before it.
        pg.click("dialog.settings .offcopy .newsbtn")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=5000)
        said = pg.inner_text("#offnews")
        print("  " + " | ".join(said.split("\n")))
        ok(f"A change made for this test, number {change.n}" in said and f"December {24 + change.n}" in said
           and pg.locator("#offnews li").count() == 1,
           "What's new lists the change made after the copy, and nothing older")
        ok(pg.is_visible("dialog.settings .offcopy .get"), "with the tab and its Update button still open beneath it")
        pg.click("#offnews .x")
        ok(pg.is_hidden("#offnews") and pg.is_visible("dialog.settings"), "its × closes it, and only it")
        pg.keyboard.press("Escape")
        pg.reload()
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=5000)
        print("  " + icon(pg)["title"])
        ok(pg.evaluate(f"getComputedStyle(document.querySelector('{ICON} .dot')).display") != "none",
           "after a reload, the icon's dot says an update is waiting")
        ok(not pg.is_visible("dialog.settings") and not pg.locator(".offnote").count(),
           "and nothing else does until the tab is opened")
        n = asked_for(log, "/102:4")
        pg.goto(BASE + "/102:4")
        ok(asked_for(log, "/102:4") == n + 1 and pg.evaluate(SURE) is False and not pg.locator("footer[data-copy]").count(),
           "a copy out of date does not answer first: the page is the server's")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=5000)
        # Offline and online again: the copy stays, out of date, and says so.
        ctx.set_offline(True)
        offline_tab(pg)
        wait_state(pg, "t.includes('once online')", 5000)
        print("  offline: " + pg.inner_text(STATE))
        ok(not pg.locator("dialog.settings .offcopy .get").count() and icon(pg)["have"] == "stale",
           "offline, the copy is still kept and still out of date, with no button to update it")
        ctx.set_offline(False)
        pg.wait_for_selector("dialog.settings .offcopy .get", timeout=10000)
        ok(pg.evaluate("caches.keys().then(k => k.some(n => n.startsWith('ub-copy-')))"),
           "online again, the copy is still kept, and the Update button is back")
        before = log.read_text().count("/offline/c/")
        # The site has a newer worker too, which no page loaded since has seen.
        (copy.parent / "sw-tag").write_text(NEWER)
        update(pg)
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"the update fetched only what changed ({fetched} chunk)")
        ok(icon(pg)["have"] == "kept", "and the dot goes")
        said = pg.evaluate("caches.open('e2e').then(c => Promise.all(['/installed', '/got'].map(u =>"
                           " c.match(u).then(r => r && r.text()))))")
        ok(said == ["newer", "get"], f"the site's newer worker came with it, and fetched the copy ({said})")
        ok(pg.evaluate(SURE) is True, "and the copy it fetched answers first again")
        pg.evaluate("caches.delete('e2e')")
        (copy.parent / "sw-tag").unlink()
        pg.keyboard.press("Escape")
        # The worker changed again (the tag gone): the one that takes over
        # asks the site before it answers from a copy another worker fetched.
        # The site's word on its copy is kept from it meanwhile (the manifest a
        # 404), so that the page's own check does not say it first.
        fail.write_text("/offline/manifest.json")
        pg.goto(BASE + "/read")
        ok(until(pg, SURE, False, 30000), "a worker new to the copy takes over, and does not answer from it yet")
        n = asked_for(log, "/102:5")
        pg.goto(BASE + "/102:5")
        ok(asked_for(log, "/102:5") == n + 1 and not pg.locator("footer[data-copy]").count(),
           "until it has asked, a page is the server's")
        fail.unlink()
        offline_tab(pg)
        wait_state(pg, "t.startsWith('Up to date')")
        until(pg, SURE, True)
        pg.keyboard.press("Escape")
        n = asked_for(log, "/102:6")
        pg.goto(BASE + "/102:6")
        ok(asked_for(log, "/102:6") == n, "a worker new to the copy asks the site, and then answers from it first")
        offline_tab(pg)
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, changed", "offline, the copy is the newer one")

        print("A larger update")
        ctx.set_offline(False)
        papers = [f"paper-{n}" for n in range(197)]
        change(copy, lambda d: (d.update(x=1), d)[1], papers)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        pg.evaluate(WATCH)
        before = log.read_text().count("/offline/c/")
        update(pg, lambda: ok(not pg.locator("dialog.settings .offcopy .get").count(), "the button goes as soon as it is pressed"))
        shown = pg.evaluate("JSON.parse(sessionStorage.shown)")
        steps = [t for t in shown if t.startswith("Updating: ")]
        print(f"  {len(steps)} steps shown: {steps[:2]} … {steps[-1:]}")
        ok(len(steps) >= 3, "the tab shows the update going on")
        ok(any(t.startswith("Updating the offline copy: ") for t in shown), "and so does the icon's label")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == len(papers), f"it fetched only what changed ({fetched} chunks)")
        pg.keyboard.press("Escape")

        print("A translation kept, and revised")
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        pg.wait_for_function("!document.querySelector('.offtrs input[value=ud]').disabled", timeout=10000)
        pg.check(".offtrs input[value=ud]")
        tr_kept(pg, "ud")
        pg.keyboard.press("Escape")
        change_tr(copy, "ud", lambda d: (d.__setitem__("1:1", [d["1:1"][0],
                                                               d["1:1"][1].replace("Из всех имён", "ИСПРАВЛЕНО Из всех имён", 1)]), d)[1])
        m2 = json.loads((copy / "manifest.json").read_text())
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        ok(True, "a revision of a translation kept puts the copy out of date, though its own build is the same")
        before = log.read_text().count("/offline/c/")
        update(pg)
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"the update fetches only its chunk revised ({fetched})")
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m2["chunks"]) + len(ud["chunks"]), f"and lets the one before it go ({kept})")
        ud2 = next(t for t in m2["translations"] if t["key"] == "ud")
        ok(f"{m2['bytes'] / 1e6:.1f} MB in this browser" in pg.inner_text(STATE)
           and tr_row(pg, "ud") == f"kept, {ud2['bytes'] / 1e6:.1f} MB",
           "the copy's line saying its own size still, and the translation's row the revision's")
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.evaluate("ubSettings.set('translations', 'ud')")
        pg.goto(BASE + "/1:1")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .rt")
        ok("ИСПРАВЛЕНО" in pg.evaluate("document.querySelector('.tf.open .rt').textContent"),
           "offline, the fold reads the revision")
        pg.evaluate("ubSettings.set('translations', '')")
        ctx.set_offline(False)

        print("An update that fails")
        ctx.set_offline(False)
        gone = change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, again"), d)[1])
        kept = (copy / gone["file"]).read_bytes()
        (copy / gone["file"]).unlink()
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        pg.evaluate("window.ubStay = 1")
        pg.click("dialog.settings .offcopy .get")
        wait_state(pg, "t.includes('stopped')")
        print("  " + pg.inner_text(STATE))
        ok(icon(pg)["have"] == "stale", "the icon still says an update is waiting")
        ok(pg.evaluate("window.ubStay") == 1, "and the page is not reloaded")
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, changed", "the copy before it still answers, whole")

        print("The site gone, the browser online")
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        ok(pg.is_visible("dialog.settings .offcopy .get"), "with the site there, Update now is offered")
        pg.keyboard.press("Escape")
        srv.stop()
        offline_tab(pg)
        wait_state(pg, "t.includes('once online')", 10000)
        print("  " + pg.inner_text("dialog.settings .net") + ": " + pg.inner_text(STATE))
        i = icon(pg)
        ok(i["net"] == "off" and i["have"] == "stale", f"a page from the site, which then went: the icon says offline ({i['title']!r})")
        ok(not pg.locator("dialog.settings .offcopy .get").count() and not pg.locator("dialog.settings .offcopy .newsbtn").count(),
           "and the tab offers no Update now or What's new")
        pg.keyboard.press("Escape")
        pg.reload()
        ok(pg.locator("footer[data-copy]").count() == 1, "a page loaded now comes from the copy")
        pg.evaluate(WATCH)
        offline_tab(pg)
        pg.wait_for_timeout(1500)
        i = icon(pg)
        ok(i["net"] == "off" and "once online" in pg.inner_text(STATE), f"and says offline ({i['title']!r})")
        ok(not any("Update now" in t for t in pg.evaluate("window.shown")) and not pg.locator("dialog.settings .offcopy .get").count(),
           "with Update now never offered")
        ok(pg.inner_text("dialog.settings .net").lower().startswith("offline"), "and the tab's first line says offline")
        pg.keyboard.press("Escape")
        srv.start()
        offline_tab(pg)
        pg.wait_for_selector("dialog.settings .offcopy .get", timeout=10000)
        i = icon(pg)
        ok(i["net"] == "on" and pg.inner_text("dialog.settings .net").lower().startswith("online"),
           f"the site back, a page from the copy says online, and Update now is back ({i['title']!r})")
        pg.keyboard.press("Escape")

        print("The browser saying offline, the site there")
        pg.evaluate("sessionStorage.setItem('ubSaysOffline', '1')")
        pg.goto(BASE + "/read")
        ok(pg.evaluate("navigator.onLine") is False, "the browser says offline")
        ok(not pg.locator("footer[data-copy]").count(), "a page loaded comes from the site all the same")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.net === 'on'", timeout=10000)
        offline_tab(pg)
        pg.wait_for_selector("dialog.settings .offcopy .get", timeout=10000)
        ok(pg.inner_text("dialog.settings .net").lower().startswith("online"),
           f"and without the tab opened the icon says online, and the tab offers Update now ({icon(pg)['title']!r})")
        pg.keyboard.press("Escape")
        pg.evaluate("sessionStorage.removeItem('ubSaysOffline')")

        print("Kept up to date by itself")
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        # The browser no longer saving data, from the next page on.
        pg.evaluate("sessionStorage.removeItem('ubSavesData')")
        # The update that stopped above, tapped, is not made by itself again
        # within the hour.
        tries = log.read_text().count(gone["file"])
        pg.reload()
        ok(pg.evaluate("!(navigator.connection && navigator.connection.saveData)"), "the browser saves no data now")
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        pg.wait_for_timeout(1500)
        ok(log.read_text().count(gone["file"]) == tries and pg.is_visible("dialog.settings .offcopy .get"),
           "an update that stopped is not made by itself again within the hour, and Update now offers it")
        pg.keyboard.press("Escape")
        # A newer build: a page loaded starts the update with no tap, and What's
        # new opens at its end, with what changed since the copy kept: this
        # build's change, and the one that stopped's.
        (copy / gone["file"]).write_bytes(kept)
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, by itself"), d)[1])
        before = log.read_text().count("/offline/c/")
        build = json.loads((copy / "manifest.json").read_text())["build"]
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.evaluate("window.ubStay = 1")
        ok(until(pg, "async b => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())"
                     ".current === b", True, 60000, build), "with no tap, the copy is updated")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"it fetched only what changed ({fetched} chunk)")
        pg.wait_for_timeout(1000)
        ok(pg.evaluate("window.ubStay") == 1 and pg.is_hidden("#offnews") and not pg.locator("dialog[open]").count()
           and icon(pg)["have"] == "kept",
           "without a word: no What's new opens by itself, and the page is not reloaded (Tigran, 2026-11-10)")
        # What's new? is in the ?'s menu, and lists what the update brought:
        # this build's change, and the one that stopped's.
        pg.click(".top .help > summary")
        pg.click(".top .helpitems a.whatsnew")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=10000)
        said = pg.inner_text("#offnews")
        print("  " + " | ".join(said.split("\n")))
        ok("New since December" in said and f"number {change.n}" in said and f"number {change.n - 1}" in said
           and pg.locator("#offnews li").count() == 2,
           "What's new?, in the ?'s menu, lists what changed since the copy kept before")
        n = asked_for(log, "/offline/manifest.json")
        pg.click("#offnews .x")
        pg.click(".top .help > summary")
        pg.click(".top .helpitems a.whatsnew")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=10000)
        ok(asked_for(log, "/offline/manifest.json") == n, "from the copy's own list, the server not asked")
        pg.click("#offnews .x")
        pg.wait_for_timeout(500)
        ok(pg.evaluate("window.ubStay") == 1 and pg.is_hidden("#offnews"), "and closing it reloads nothing")
        ctx.set_offline(True)
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, by itself", "offline, the copy is the newer one")
        # Out of date while offline: coming online updates it.
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, online again"), d)[1])
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.startsWith('Up to date')")
        pg.keyboard.press("Escape")
        pg.evaluate("window.ubStay = 1")
        build = json.loads((copy / "manifest.json").read_text())["build"]
        ctx.set_offline(False)
        ok(until(pg, "async b => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())"
                     ".current === b", True, 60000, build) and pg.evaluate("window.ubStay") == 1 and pg.is_hidden("#offnews"),
           "coming online, the copy is updated by itself, without a word")
        # A build with nothing for a reader in its news: updated, and nothing said.
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, quietly"), d)[1], news=False)
        build = json.loads((copy / "manifest.json").read_text())["build"]
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.evaluate("window.ubStay = 1")
        until(pg, "async b => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())"
                  ".current === b", True, 60000, build)
        pg.wait_for_timeout(1000)
        ok(pg.evaluate("window.ubStay") == 1 and pg.is_hidden("#offnews") and icon(pg)["have"] == "kept",
           "with nothing listed for it, the copy is updated without a word, and the page not reloaded")
        # While listening, and with the page out of view: nothing until it is in
        # view again; then What's new, and closing it does not stop the reading.
        # The build is made newer once the page is up, so that coming online
        # finds it, not the page's load.
        pg.goto(BASE + "/101:4")
        pg.locator("p.t .playp").first.click()
        pg.wait_for_selector(".player", timeout=5000)
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, listening"), d)[1])
        pg.evaluate("window.ubStay = 1")
        before = log.read_text().count("/offline/c/")
        pg.evaluate("Object.defineProperty(document, 'hidden', {value: true, configurable: true});"
                    " Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});"
                    " dispatchEvent(new Event('online'))")
        pg.wait_for_timeout(1500)
        ok(log.read_text().count("/offline/c/") == before, "out of view, the copy is not updated by itself")
        build = json.loads((copy / "manifest.json").read_text())["build"]
        pg.evaluate("delete document.hidden; delete document.visibilityState;"
                    " document.dispatchEvent(new Event('visibilitychange'))")
        ok(until(pg, "async b => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())"
                     ".current === b", True, 60000, build), "in view again, it is")
        pg.wait_for_timeout(1000)
        ok(pg.evaluate("window.ubStay") == 1 and pg.locator(".player").count() == 1 and pg.is_hidden("#offnews"),
           "without a word, and the reading goes on")
        pg.click(".player button.close") if pg.locator(".player button.close").count() else None
        pg.keyboard.press("Escape")
        ok(not errors, f"no script errors ({errors[:2]})")

        print("Automatic updates turned off")
        # Tigran, 2026-11-10: a reader keeps the copy they have.  Off, nothing
        # is fetched by itself, and the copy answers first though the site has
        # another build, until Update now; what it is, is the worker's, so
        # Restore the defaults leaves it.
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        wait_state(pg, "t.startsWith('Up to date')")
        held = pg.evaluate(META, "current")
        pg.click(AUTO)
        ok(until(pg, META, False, 15000, "auto") and not pg.is_checked(AUTO), "turned off, the worker keeps it so")
        pg.click("#set-t-show")
        pg.check("dialog.settings input[name=pages]")
        pg.click("dialog.settings .reset")
        ok(until(pg, "() => ubSettings.get().pages === false"), "Restore the defaults puts the settings back")
        offline_tab(pg)
        pg.wait_for_timeout(300)
        ok(pg.evaluate(META, "auto") is False and not pg.is_checked(AUTO),
           "and leaves Automatic updates off: it is the worker's, not a setting")
        pg.keyboard.press("Escape")
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, held back"), d)[1])
        build = json.loads((copy / "manifest.json").read_text())["build"]
        before = log.read_text().count("/offline/c/")
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=10000)
        pg.wait_for_timeout(1500)
        ok(log.read_text().count("/offline/c/") == before and pg.evaluate(META, "current") == held != build,
           f"a newer build is not fetched by itself ({icon(pg)['title']!r})")
        ok(pg.evaluate(SURE) is False, "the copy is known not to be the site's build")
        n = asked_for(log, "/102:7")
        pg.goto(BASE + "/102:7")
        ok(asked_for(log, "/102:7") == n and pg.locator("p.t[id='102:7.1']").count() == 1
           and not pg.locator("footer[data-copy]").count(),
           "and still answers first: the server is not asked for a page it holds, which is unmarked")
        n = asked_for(log, "/")
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, listening" and asked_for(log, "/") == n,
           f"the page is the copy's, as it was kept, not the site's ({pg.title()!r})")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=10000)
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        ok(pg.is_visible("dialog.settings .offcopy .get") and pg.is_visible("dialog.settings .offcopy .newsbtn")
           and icon(pg)["net"] == "on" and not pg.is_checked(AUTO),
           "the icon says an update is waiting, and the tab offers Update now and What's new")
        pg.click("dialog.settings .offcopy .newsbtn")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=10000)
        ok(f"number {change.n}" in pg.inner_text("#offnews") and pg.locator("#offnews li").count() == 1,
           "What's new lists what the update would bring, before it is taken")
        pg.click("#offnews .x")
        # A translation's download would update the copy too: asked first.
        asked.clear()
        pg.remove_listener("dialog", accept)
        pg.once("dialog", lambda d: d.dismiss())
        pg.click(".offtrs input[value=urantia-ru]")
        pg.on("dialog", accept)
        pg.wait_for_timeout(500)
        print(f"  asked: {asked[0] if asked else None!r}")
        ok(asked and asked[0].startswith("The offline copy is out of date, and Automatic updates are off: ")
           and not pg.is_checked(".offtrs input[value=urantia-ru]") and log.read_text().count("/offline/c/") == before
           and pg.evaluate(META, "current") == held,
           "a translation ticked asks first, since its download would update the copy; cancelled, nothing is fetched")
        ctx.set_offline(True)
        wait_state(pg, "t.includes('can be updated once online')", 10000)
        ok(not pg.locator("dialog.settings .offcopy .get").count(),
           "offline, the tab says it can be updated once online, not that it updates by itself")
        ctx.set_offline(False)
        pg.wait_for_selector("dialog.settings .offcopy .get", timeout=10000)
        update(pg)
        ok(pg.evaluate(META, "current") == build and pg.evaluate(META, "auto") is False and not pg.is_checked(AUTO)
           and log.read_text().count("/offline/c/") == before + 1,
           "Update now brings the site's build, what changed alone, and the switch stays off")
        pg.keyboard.press("Escape")
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, held again"), d)[1])
        held, build = build, json.loads((copy / "manifest.json").read_text())["build"]
        before = log.read_text().count("/offline/c/")
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=10000)
        pg.wait_for_timeout(1500)
        ok(log.read_text().count("/offline/c/") == before and pg.evaluate(META, "current") == held,
           "nor is the build after that fetched by itself")
        # Turned on again with an update waiting: fetched at once, with no tap
        # on Update now, without a word and with no reload, as any made by itself.
        offline_tab(pg)
        wait_state(pg, "t.includes('changed since')")
        pg.evaluate("window.ubStay = 1")
        pg.click(AUTO)
        ok(until(pg, META, build, 60000, "current") and pg.evaluate(META, "auto") is None,
           "turned on again, the update waiting is fetched at once, and the worker keeps nothing of the switch")
        wait_state(pg, "t.startsWith('Up to date')")
        ok(pg.is_checked(AUTO) and pg.evaluate("window.ubStay") == 1 and pg.is_hidden("#offnews")
           and log.read_text().count("/offline/c/") == before + 1,
           "by itself: the page is not reloaded, and nothing is said")
        pg.keyboard.press("Escape")
        ok(not errors, f"no script errors ({errors[:2]})")

        print("The bar's ↓")
        ctx.set_offline(False)
        pg.goto(BASE + "/161:1")
        pg.locator("p.t .playp").first.click()
        pg.wait_for_selector(".player .keep[data-st='none']", timeout=10000)
        pg.click(".player .keep")
        pg.wait_for_function("document.querySelector('.player .keep').dataset.st === 'kept'", timeout=120000)
        ok(pg.evaluate("caches.open('ub-audio-mh').then(c => c.keys()).then(ks => ks.length)") == 4,
           "the bar's ↓ keeps the paper being heard")
        pg.click(".player button.close")
        offline_tab(pg)
        ok(not pg.locator("dialog.settings .offcopy input:not(.auto)").count()
           and not pg.locator("dialog.settings .offcopy button").count(),
           "and nothing in the tab lets the copy go")
        pg.keyboard.press("Escape")
        ok(not errors, f"no script errors ({errors[:2]})")
        ctx.close()

        print("A first visit")
        # A browser of its own, saving no data: the copy is fetched with
        # nothing tapped, once the page has loaded (Tigran, 2026-11-10).
        (copy / gone["file"]).write_bytes(kept)
        m = json.loads((copy / "manifest.json").read_text())
        ctx = b.new_context()
        ctx.add_init_script(SAYS_OFFLINE)
        ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); } catch (e) {}")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        before = log.read_text().count("/offline/c/")
        pg.goto(BASE + "/101:4")
        ok(not pg.evaluate("!!navigator.serviceWorker.controller") and not pg.locator("footer[data-copy]").count(),
           "the first page is the server's, with no worker yet")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'busy'", timeout=20000)
        print("  " + icon(pg)["title"])
        ok(True, "with nothing tapped, the copy starts downloading, and the icon says so")
        # The worker stopped half way, as the browser stops one whose page has
        # gone, or whose message has run five minutes: the next page goes on
        # with the download, with what it had.
        until(pg, "() => caches.keys().then(async ks => { for (const k of ks) if (k.startsWith('ub-copy-'))"
                  " return (await (await caches.open(k)).keys()).length > 60; return false; })", True, 60000)
        cdp = ctx.new_cdp_session(pg)
        cdp.send("ServiceWorker.enable")
        cdp.send("ServiceWorker.stopAllWorkers")
        pg.wait_for_timeout(1000)
        first = log.read_text().count("/offline/c/") - before
        ok(0 < first < len(m["chunks"]) and pg.evaluate("caches.open('ub-meta').then(c => c.match('/offline/meta'))"
                                                        ".then(r => r ? r.json() : {}).then(x => !x.current)"),
           f"the worker stopped part of the way through, with no copy yet ({first} of {len(m['chunks'])} chunks)")
        pg.goto(BASE + "/101:5")
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'kept'", timeout=120000)
        fetched = log.read_text().count("/offline/c/") - before
        ok(len(m["chunks"]) <= fetched <= len(m["chunks"]) + 4,
           f"the next page goes on with it by itself, fetching only what it lacked ({fetched} fetches for {len(m['chunks'])} chunks)")
        ok(pg.evaluate(SURE) is True and pg.evaluate(KEPT)["gz"] == len(m["chunks"]), "and the copy is whole, and answers first")
        n = asked_for(log, "/101:6")
        pg.goto(BASE + "/101:6")
        ok(asked_for(log, "/101:6") == n and not pg.locator("footer[data-copy]").count() and icon(pg)["net"] == "on",
           "the page after is read from the copy, the server not asked, unmarked")
        offline_tab(pg)
        wait_state(pg, "t.startsWith('Up to date')")
        ok(pg.evaluate("[...document.querySelectorAll('.offtrs input')].every(i => !i.checked && !i.disabled)"),
           "no translation came with it: each is offered, for the reader to choose")
        pg.keyboard.press("Escape")
        pg.click(".top .help > summary")
        pg.click(".top .helpitems a.whatsnew")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=10000)
        said = en(pg, "#offnews .since")
        days = pg.locator("#offnews h3").count()
        ok(said == "The latest changes:" and 1 <= days <= 3,
           f"What's new?, with a copy never yet updated, lists the latest changes ({said!r}, {days} days)")
        pg.click("#offnews .x")
        # A translation shown and not kept: what depends on it is the server's.
        pg.evaluate("ubSettings.set('translations', 'urantia-ru')")
        n, t0 = asked_for(log, BOG), asked_for(log, "/tr/1:1")
        pg.goto(BASE + BOG)
        ok(asked_for(log, BOG) == n + 1 and not pg.locator(".notkept").count()
           and pg.locator(".trhits [data-tr=urantia-ru] li").count() > 0,
           "with a translation shown that the copy does not keep, a search is the server's")
        pg.goto(BASE + "/1:1")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .rt")
        ok(asked_for(log, "/tr/1:1") == t0 + 1 and "Из всех имен" in pg.evaluate("document.querySelector('.tf.open .rt').textContent.replace(/\u00ad/g, '')"),
           "and so are a section's translations, which the fold shows")
        # Kept, they come from the copy.
        offline_tab(pg)
        pg.check(".offtrs input[value=urantia-ru]")
        tr_kept(pg, "urantia-ru")
        pg.keyboard.press("Escape")
        n, t0 = asked_for(log, BOG), asked_for(log, "/tr/1:2")
        pg.goto(BASE + BOG)
        ok(asked_for(log, BOG) == n and pg.locator(".trhits [data-tr=urantia-ru] li").count() > 0,
           "kept, the search is the copy's, the translation's hits with it")
        pg.goto(BASE + "/1:2")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .rt")
        ok(asked_for(log, "/tr/1:2") == t0, "and the fold's translations are the copy's")
        # One more ticked on a search the copy answered, which says of it that
        # it is not kept: the page is asked for again, of the server.
        pg.goto(BASE + BOG)
        n = asked_for(log, BOG)
        ok(pg.locator(".trhits [data-tr=uf-ru] > .notkept").count() == 1 and pg.locator(".trhits [data-tr=uf-ru]").is_hidden(),
           "the copy's search says of one not kept that it is not, in a list not shown")
        with pg.expect_event("load", timeout=10000):
            pg.evaluate("ubSettings.set('translations', 'urantia-ru uf-ru')")
        ok(asked_for(log, BOG) == n + 1 and not pg.locator(".notkept").count()
           and pg.locator(".trhits [data-tr=uf-ru] li").count() > 0,
           "a translation ticked on a search the copy answered has the page again from the server, with its hits")
        pg.evaluate("ubSettings.set('translations', '')")
        # The site gone, the browser online: the site goes on, from the copy.
        srv.stop()
        pg.goto(BASE + "/101:7")
        ok(pg.locator("p.t[id='101:7.1']").count() == 1 and not pg.locator("footer[data-copy]").count(),
           "with the server gone, the site goes on: a page from the copy as before")
        pg.goto(BASE + "/stats")
        ok(pg.locator("footer[data-copy]").count() == 1 and "read online" in pg.inner_text("main"),
           "and a page the copy does not hold says it is read online, marked as the copy's")
        offline_tab(pg)
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.net === 'off'", timeout=10000)
        ok(pg.inner_text("dialog.settings .net").lower().startswith("offline"), "the tab, asking the site, says offline")
        pg.keyboard.press("Escape")
        srv.start()
        ok(not errors, f"no script errors ({errors[:2]})")
        log_text = log.read_text()
        again = [ln for ln in log_text.splitlines() if "/offline/sqlite3.js" in ln]
        ok(any(" 304 " in ln for ln in again),
           f"the worker's scripts are asked for again as a 304 ({sum(' 304 ' in ln for ln in again)} of {len(again)})")
        b.close()
    print("ok" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
