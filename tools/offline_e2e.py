"""Work offline, end to end, in Chrome: turn it on, keep a translation in it,
read and search with the network off, learn of a newer copy and take it, with
the site's newer worker,
the page reloading itself after, survive an update that fails, say offline
while the site is gone though the browser is online, and online while the
browser says offline with the site there, keep it up to date by itself, with
What's new at the end, and turn it off.

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
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The rail's link to Paper 1, as the contents chosen draw it (ub.js tocApply).
RAIL1 = """document.querySelector('.rail a[href="/1"]').textContent"""
BASE = "http://localhost:8131"
SERVER = """
import os, pathlib, sys, types
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
SAVES_DATA = """try { if (sessionStorage.getItem('ubSavesData'))
  Object.defineProperty(navigator, 'connection', { value: { saveData: true }, configurable: true }); } catch (e) {}"""

# What the page shows while an update runs, in the tab and on the icon's
# label, each line once, as it changes; in sessionStorage too, which the
# reload at its end keeps.
# An element's words as a reader of English has them: the interface is in the
# page in Russian too (ubsite/l10n.py), which CSS hides; its textContent has both.
EN = "(el => { const c = el.cloneNode(true); c.querySelectorAll('x-ru').forEach(x => x.remove()); return c.textContent; })"
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


def offline_tab(pg) -> None:
    """Open Settings at its Offline tab, which keeps the copy and the
    translations in it (base.html .offcopy, .offtr), unless it is open."""
    if not pg.is_visible("dialog.settings"):
        pg.click(".gear")
    pg.click("#set-t-offline")
    pg.wait_for_selector("dialog.settings .offcopy", state="visible")


# The copy's tick: unticked and to be ticked, as with none kept.
COPY_CLEAR = "(i => !i.checked && !i.disabled)(document.querySelector('dialog.settings .offcopy input'))"


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
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        ctx = b.new_context()
        ctx.add_init_script(SAYS_OFFLINE)
        ctx.add_init_script(SAVES_DATA)
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.accept())
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("Turning it on")
        pg.goto(BASE + "/101:4")
        ok(pg.get_attribute("p.t .playp", "aria-label") == "Listen to this section, from its heading",
           "online, the first paragraph's play button starts the section")
        i = icon(pg)
        ok(i["shown"] and i["net"] == "on" and i["have"] == "none" and i["title"] == "Online",
           f"the icon at the header's corner says online, with no copy ({i})")
        host = pg.evaluate("getComputedStyle(document.querySelector('.brand .host'), '::before').content")
        ok(host == '"localhost:8131"' and not pg.inner_text(".brand .host"),
           f"the site's address stands under the name, drawn from the page's own, written by no server ({host})")
        ok(not pg.locator("#offmenu").count(), "the icon has no menu")
        pg.click(ICON)
        pg.wait_for_selector("dialog.settings .offcopy", state="visible")
        ok(pg.get_attribute("#set-t-offline", "aria-selected") == "true", "a tap on it opens Settings at the Offline tab")
        ok(pg.inner_text("dialog.settings .net .host") == "localhost:8131"
           and pg.inner_text("dialog.settings .net").lower().startswith("online"),
           "whose first line says online, and names the site from its address")
        ok(not pg.locator("dialog.settings .panel.offline input[name]").count(),
           "and which stores no setting: the copy and its translations are the worker's")
        pg.wait_for_function(COPY_CLEAR, timeout=10000)
        hint = pg.evaluate(EN + "(document.querySelector('dialog.settings .offcopy small'))")
        ok(re.search(r", about \d+\.\d MB, kept", hint), f"the copy's tick is clear, its hint saying what it costs ({hint!r})")
        m = json.loads((copy / "manifest.json").read_text())
        sizes = [tr_row(pg, t["key"]) for t in m["translations"]]
        ok(pg.evaluate("[...document.querySelectorAll('.offtrs input')].every(i => !i.disabled && !i.checked)")
           and all(x.endswith(" MB") for x in sizes)
           and "downloads the offline copy with it" in pg.inner_text("dialog.settings .offtr .why"),
           f"the translations are offered too, each with its size, a tick to download the copy with it ({sizes})")
        ud = next(t for t in m["translations"] if t["key"] == "ud")
        t = time.time()
        before = log.read_text().count("/offline/c/")
        pg.check(".offtrs input[value=ud]")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        said = pg.inner_text(STATE)
        print(f"  downloaded in {time.time() - t:.1f} s: " + said)
        ok(pg.is_checked("dialog.settings .offcopy input") and tr_row(pg, "ud").startswith("kept"),
           "a translation ticked with no copy kept downloads the copy with it, and both are ticked")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == len(m["chunks"]) + len(ud["chunks"]), f"fetching each chunk of the two once ({fetched} chunks)")
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]) + len(ud["chunks"]), f"the copy and the translation, in one cache ({kept})")
        ok(icon(pg)["have"] == "kept", f"the icon says a copy is kept ({icon(pg)['title']!r})")
        made = datetime.datetime.fromisoformat(m["made"].replace("Z", "+00:00"))
        ok(f"kept as the site was on {made:%B} {made.day}, with the text of" in said,
           "the tab says when the site was as the copy keeps it")
        ok(f"{(m['bytes'] + ud['bytes']) / 1e6:.1f} MB in this browser" in said,
           "and counts the translation in what the browser keeps")
        used = pg.evaluate("navigator.storage.estimate().then(e => e.usage)")
        print(f"  the browser keeps {used / 1e6:.1f} MB: {m['bytes'] / 1e6:.1f} MB gzipped, {m['raw'] / 1e6:.1f} MB unpacked")
        ok(used < (m["bytes"] + ud["bytes"]) * 1.25, "it keeps the copy gzipped, as it came")
        pg.keyboard.press("Escape")
        ok(not pg.is_visible("dialog.settings"), "Escape closes Settings")
        # Updated by hand, with Update now, until "Kept up to date by itself":
        # the browser saving data is the one case, besides a try that stopped,
        # where the copy is not updated by itself (offline.js saving).
        pg.evaluate("sessionStorage.setItem('ubSavesData', '1')")

        print("A translation kept in it")
        offline_tab(pg)
        pg.wait_for_function("[...document.querySelectorAll('.offtrs input')].every(i => !i.disabled)", timeout=10000)
        sizes = [tr_row(pg, t["key"]) for t in m["translations"]]
        ok(all(x.endswith(" MB") for x in sizes) and pg.is_hidden("dialog.settings .offtr .why"),
           f"with a copy kept, each is offered with its size, the one kept saying so ({sizes})")
        pg.uncheck(".offtrs input[value=ud]")
        pg.wait_for_function("document.querySelector('.offtrs input[value=ud]').closest('li')"
                             ".querySelector('.st').textContent.startsWith('kept') === false", timeout=10000)
        kept = pg.evaluate(KEPT)
        ok(kept["gz"] == len(m["chunks"]), f"unticked, it is let go, the copy staying ({kept})")
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
        ok(f"{(m['bytes'] + ud['bytes']) / 1e6:.1f} MB in this browser" in pg.inner_text(STATE),
           "the tab counts it in what the browser keeps")
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
           "opened, it shows the first in the reader's order, the USGNY's")
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

        print("Compare")
        pg.goto(BASE + "/1:1")
        pg.click(".cmphead .cmpbtn")
        pg.wait_for_selector("article.cmp .rc .rt")
        cols = pg.evaluate("[...document.querySelectorAll('article.cmp .cmphd > .ch')].map(c => c.dataset.k || 'en')")
        ok(pg.url.endswith("/1:1/compare") and cols == ["en", "urantia-ru", "ud"],
           f"Compare draws the English and each one ticked, a column each, in the reader's order ({cols})")
        ok(pg.locator(".tf").first.is_hidden(), "and the folds give way to the columns")
        pg.locator('.rc[data-k=ud] a.fn[data-k="tn"]').first.click()
        pg.wait_for_selector(".pop.tn")
        ok("Note 6" in pg.inner_text(".pop.tn"), "a translator's number in its column opens its card")
        pg.keyboard.press("Escape")
        pg.go_back()
        pg.wait_for_function("!document.querySelector('article.cmp')")
        ok(pg.url.endswith("/1:1") and pg.locator(".tf").first.is_visible(), "Back leaves it, in place")
        pg.go_forward()
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:1/compare"), "and Forward comes back to it")
        pg.click(".transport .next")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.url.endswith("/1:2/compare"), "the transport bar keeps it on")
        pg.goto(BASE + "/140:4/compare")
        pg.wait_for_selector("article.cmp .rc .rt")
        ok(pg.evaluate("[...document.querySelectorAll('article.cmp .cmphd > .ch')].map(c => c.dataset.k || 'en')")
           == ["en", "urantia-ru"], "a translation without the section has no column")

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
                "/quiz", "/quiz/32"]
        for u in urls:
            with urllib.request.urlopen(BASE + u) as r:
                want[u] = r.read()

        print("Offline")
        pg.reload()
        ok(pg.evaluate("!!navigator.serviceWorker.controller"), "the page is the worker's")
        ctx.set_offline(True)
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
        print("  " + pg.inner_text("dialog.settings .net"))
        ok(pg.inner_text("dialog.settings .net").lower().startswith("offline"), "and so does the tab's first line")
        ok(pg.inner_text("dialog.settings .net .host") == "localhost:8131", "and names the site from the copy too")
        ok(pg.is_disabled("dialog.settings .offcopy input"), "offline, the copy cannot be let go: it is all the site there is")
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
        pg.goto(BASE + "/1:2/compare")
        pg.wait_for_selector("article.cmp .rc[data-k=ud] .rt")
        ok("not in the offline copy" in pg.inner_text("article.cmp .cmphd > .ch[data-k=urantia-ru] .gap")
           and pg.locator("article.cmp .rc[data-k=urantia-ru] .rt").count() == 0,
           "Compare offline draws the one kept, and one not kept says so over its column")
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
        pg.keyboard.press("Escape")
        pg.wait_for_function("(document.querySelector('.tf.open .gap') || {}).textContent", timeout=10000)
        ok("not in the offline copy" in pg.inner_text(".tf.open .gap"), "and the folds open say so at once")
        pg.goto(BASE + "/2:1")
        pg.locator(".tf .trfold").first.click()
        pg.wait_for_selector(".tf.open .gap")
        ok("not in the offline copy" in pg.inner_text(".tf.open .gap"), "as does a fold opened after")
        pg.evaluate("ubSettings.set('translations', '')")
        pg.goto(BASE + "/search?q=101:4.2")
        ok(pg.url.endswith("/101:4.2"), f"a citation typed into the box opens it ({pg.url})")
        pg.goto(BASE + "/101")
        ok(pg.url.endswith("/101:0"), "/101 opens 101:0")
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
                             " && document.querySelector('.player .who').textContent.includes('connection')",
                             timeout=10000)
        pg.wait_for_timeout(1500)
        ok("connection" in pg.inner_text(".player .who") and pg.evaluate("!speechSynthesis.speaking"),
           f"offline, a recording refuses to play, saying why, and the message stays ({pg.inner_text('.player .who')!r})")
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
        # Offline and online again: the copy stays, out of date, and says so.
        ctx.set_offline(True)
        offline_tab(pg)
        wait_state(pg, "t.includes('once online')", 5000)
        print("  offline: " + pg.inner_text(STATE))
        ok(not pg.locator("dialog.settings .offcopy .get").count() and icon(pg)["have"] == "stale",
           "offline, the copy is still kept and still out of date, with no button to update it")
        ok(pg.is_disabled("dialog.settings .offcopy input"), "nor can it be let go, while it is all the site there is")
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
        pg.evaluate("caches.delete('e2e')")
        (copy.parent / "sw-tag").unlink()
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
        ok(f"{(m2['bytes'] + ud2['bytes']) / 1e6:.1f} MB in this browser" in pg.inner_text(STATE),
           "the tab counting it still")
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
        ok(not pg.locator("dialog.settings .offcopy .get").count() and not pg.locator("dialog.settings .offcopy .newsbtn").count()
           and pg.is_disabled("dialog.settings .offcopy input"), "and the tab offers no Update now or What's new, nor lets the copy go")
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
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.evaluate("window.ubStay = 1")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=60000)
        said = pg.inner_text("#offnews")
        print("  " + " | ".join(said.split("\n")))
        ok("just been updated" in said and f"number {change.n}" in said and f"number {change.n - 1}" in said
           and pg.locator("#offnews li").count() == 2,
           "with no tap, the copy is updated, and What's new says so, listing what changed since the copy kept")
        ok("Closing this reloads the page" in said, "saying what closing it does")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"it fetched only what changed ({fetched} chunk)")
        pg.wait_for_timeout(500)
        ok(pg.evaluate("window.ubStay") == 1, "the page waits for What's new to close")
        with pg.expect_event("load", timeout=10000):
            pg.click("#offnews .x")
        ok(not pg.evaluate("window.ubStay") and icon(pg)["have"] == "kept", "and reloads once it is closed")
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
        ctx.set_offline(False)
        pg.wait_for_selector("#offnews", state="visible", timeout=60000)
        ok(f"number {change.n}" in pg.inner_text("#offnews"), "coming online, the copy is updated by itself")
        with pg.expect_event("load", timeout=10000):
            pg.keyboard.press("Escape")
        ok(not pg.evaluate("window.ubStay"), "and Escape closes What's new, reloading the page")
        # A build with nothing for a reader in its news: updated, and nothing said.
        change(copy, lambda d: (d["pages"]["/"].update(t=">The Urantia Book, quietly"), d)[1], news=False)
        build = json.loads((copy / "manifest.json").read_text())["build"]
        pg.evaluate(HOUR_LATER)
        pg.goto(BASE + "/read")
        pg.evaluate("window.ubStay = 1")
        pg.wait_for_function("async b => (await (await (await caches.open('ub-meta')).match('/offline/meta')).json())"
                             ".current === b", arg=build, timeout=60000)
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
        pg.evaluate("delete document.hidden; delete document.visibilityState;"
                    " document.dispatchEvent(new Event('visibilitychange'))")
        pg.wait_for_selector("#offnews", state="visible", timeout=60000)
        said = pg.inner_text("#offnews")
        ok(f"number {change.n}" in said and "The next page you open is the new one" in said,
           "in view again, it is, and What's new says that the next page is the new one")
        pg.click("#offnews .x")
        pg.wait_for_timeout(1000)
        ok(pg.evaluate("window.ubStay") == 1 and pg.locator(".player").count() == 1,
           "closing it, while listening, does not reload the page")
        pg.click(".player button.close") if pg.locator(".player button.close").count() else None
        pg.keyboard.press("Escape")
        ok(not errors, f"no script errors ({errors[:2]})")

        print("Turning it off")
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        offline_tab(pg)
        pg.uncheck("dialog.settings .offcopy input")
        pg.wait_for_function(COPY_CLEAR, timeout=10000)
        ok(pg.evaluate("caches.keys().then(k => k.length)") == 0,
           "unticked, with no question asked, nothing is kept, the translation kept with it")
        ok(icon(pg)["have"] == "none", "and the icon says so")
        ok(pg.evaluate("[...document.querySelectorAll('.offtrs input')].every(i => !i.checked && !i.disabled)"),
           "and the translations are offered again, with the copy")

        print("On again in the same page, which keeps its worker")
        (copy / gone["file"]).write_bytes(kept)
        pg.check("dialog.settings .offcopy input")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/search?q=thought+adjuster")
        ok("In the text" in pg.inner_text("main"), "a search answers offline")
        ctx.set_offline(False)
        offline_tab(pg)
        pg.uncheck("dialog.settings .offcopy input")
        pg.wait_for_function(COPY_CLEAR, timeout=10000)
        ok(pg.evaluate("caches.keys().then(k => k.length)") == 0, "off: nothing is kept")
        pg.goto(BASE + "/read")
        ok(pg.evaluate("navigator.serviceWorker.getRegistration('/').then(r => !r)"), "the worker is gone")
        log_text = log.read_text()
        again = [ln for ln in log_text.splitlines() if "/offline/sqlite3.js" in ln]
        ok(any(" 304 " in ln for ln in again),
           f"the worker's scripts are asked for again as a 304 ({sum(' 304 ' in ln for ln in again)} of {len(again)})")
        b.close()
    print("ok" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
