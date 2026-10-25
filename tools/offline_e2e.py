"""Work offline, end to end, in Chrome: turn it on, read and search with the
network off, learn of a newer copy and take it, with the site's newer worker,
the page reloading itself after, survive an update that fails, say offline
while the site is gone though the browser is online, keep it up to date by
itself, with What's new at the end, and turn it off.

    make e2e          (make offline, then .venv/bin/python tools/offline_e2e.py)

Playwright is in .venv as a dev requirement (requirements-dev.in), and drives
the system's Chrome.  It needs a built copy, which `make e2e` builds.  It
serves a scratch copy of var/offline/ from a server of its own, on
127.0.0.1:8131 with the visit counter off, so that it can make a "newer build"
by changing that copy, and leaves var/offline/ and the dev server alone.
localhost is a secure context, so the worker runs there as on the live site.
Not a gate: offline/check.py is, for every page; this shows that the worker,
the icon at the header's corner and its menu do what they say.
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

# Work offline's icon, and the line in its menu that says what the copy is.
ICON = ".top .offline"
STATE = "#offmenu .state"


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

# What the page shows while an update runs, in the menu and on the icon's
# label, each line once, as it changes; in sessionStorage too, which the
# reload at its end keeps.
WATCH = """() => { window.shown = []; sessionStorage.shown = '[]';
  const keep = () => { for (const t of [document.querySelector('#offmenu .state').textContent,
                                        document.querySelector('.top .offline').title])
    if (!window.shown.includes(t)) window.shown.push(t);
    sessionStorage.shown = JSON.stringify(window.shown); };
  new MutationObserver(keep).observe(document.body, {subtree: true, childList: true, characterData: true,
                                                     attributes: true, attributeFilter: ['title']}); }"""


def wait_state(pg, test: str, timeout: int = 30000) -> None:
    """Until the menu's line passes `test`, a JavaScript expression in t."""
    pg.wait_for_function(f"(t => {test})(document.querySelector('{STATE}').textContent)", timeout=timeout)


def update(pg, pressed=None, timeout: int = 60000) -> None:
    """Tap Update now, which reloads the page once the copy is in, and open the
    menu of the page it reloads to.  `pressed` runs at once after the tap."""
    pg.evaluate("window.ubStay = 1")
    with pg.expect_event("load", timeout=timeout):
        pg.click("#offmenu .get")
        if pressed:
            pressed()
    ok(not pg.evaluate("window.ubStay"), "the page reloads itself once the copy is in")
    menu(pg)
    wait_state(pg, "t.startsWith('Up to date')")


def menu(pg) -> None:
    """Open the icon's menu, unless it is open."""
    if not pg.is_visible("#offmenu"):
        pg.click(ICON)
    pg.wait_for_selector("#offmenu", state="visible")


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
        ok(not pg.locator("dialog.settings input[name=offline]").count(), "Settings has no Offline section")
        ok(not pg.locator("#offmenu input").count(), "and the menu has no switch to turn off")
        pg.click(ICON)
        ok(pg.is_visible("#offmenu"), "the icon opens its menu")
        ok(pg.inner_text("#offmenu .net .host") == "localhost:8131", "which names the site, from its address")
        wait_state(pg, "t.includes('MB to download')")
        print("  " + pg.inner_text(STATE))
        t = time.time()
        pg.click("#offmenu .keep")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        said = pg.inner_text(STATE)
        print(f"  downloaded in {time.time() - t:.1f} s: " + said)
        ok(icon(pg)["have"] == "kept", f"the icon says a copy is kept ({icon(pg)['title']!r})")
        pg.click(ICON)
        ok(not pg.is_visible("#offmenu"), "the icon closes its menu again")
        m = json.loads((copy / "manifest.json").read_text())
        made = datetime.datetime.fromisoformat(m["made"].replace("Z", "+00:00"))
        ok(f"kept as the site was on {made:%B} {made.day}, with the text of" in said,
           "the menu says when the site was as the copy keeps it")
        used =pg.evaluate("navigator.storage.estimate().then(e => e.usage)")
        print(f"  the browser keeps {used / 1e6:.1f} MB: {m['bytes'] / 1e6:.1f} MB gzipped, {m['raw'] / 1e6:.1f} MB unpacked")
        ok(used < m["bytes"] * 1.25, "it keeps the copy gzipped, as it came")
        ok(pg.evaluate("!document.querySelector('dialog.settings fieldset.offline').hidden"),
           "Settings offers to keep it up to date by itself, where Work offline can run")
        # Updated by hand, with Update now, until "Kept up to date by itself".
        pg.evaluate("ubSettings.set('autoupdate', false)")

        # What the server sends, to hold the worker's answers to.
        want = {}
        urls = ["/101:4", "/101:4.2-3", "/i/god", "/appendix/A", "/lists/1955", "/index/G", "/", "/read",
                "/part/2", "/search?q=prayer", "/search?q=self-conscious&in=text", "/search?q=Badanon&in=notes",
                "/i/jesus/read", "/i/prayer/read/theme",
                "/rail/120?v=1", "/static/fonts/UBGoudy.woff2", "/speech/101:4", "/speech/0:0", "/changelog"]
        for u in urls:
            with urllib.request.urlopen(BASE + u) as r:
                want[u] = r.read()

        print("Offline")
        pg.reload()
        ok(pg.evaluate("!!navigator.serviceWorker.controller"), "the page is the worker's")
        ctx.set_offline(True)
        for u in urls:
            got = pg.evaluate("u => fetch(u).then(r => r.arrayBuffer()).then(b => Array.from(new Uint8Array(b)))", u)
            # The one thing the worker adds: the footer's note of the copy's date.
            got = re.sub(rb'\n<footer data-copy="[^"]*">', b"\n<footer>", bytes(got))
            ok(got == want[u], f"{u}: as the server sends it ({len(got):,} bytes)")
        t = time.time()
        pg.goto(BASE + "/search?q=thought+adjuster")
        print(f"  a first search, the engine starting: {(time.time() - t) * 1000:.0f} ms")
        ok("In the text" in pg.inner_text("main"), "a search answers offline")
        t = time.time()
        pg.goto(BASE + "/search?q=morontia+mota")
        print(f"  a second: {(time.time() - t) * 1000:.0f} ms")
        pg.goto(BASE + "/101:4.2-3")
        ok(pg.locator("p.t.hit").count() == 2, "/101:4.2-3 marks two paragraphs")
        i = icon(pg)
        ok(i["net"] == "off" and i["have"] == "kept", f"the icon says offline ({i['title']!r})")
        pg.click(ICON)
        print("  " + pg.inner_text("#offmenu .net"))
        ok(pg.inner_text("#offmenu .net").lower().startswith("offline"), "and so does its menu")
        ok(pg.inner_text("#offmenu .net .host") == "localhost:8131", "and names the site from the copy too")
        hosted = pg.evaluate("Promise.all(['/manifest.webmanifest', '/apple-touch-icon.png'].map(u =>"
                             " fetch(u).then(r => r.status, () => 'none')))")
        ok(hosted == ["none", "none"], f"the app's manifest and touch icon are the server's alone ({hosted})")
        tab = pg.evaluate("fetch('/static/favicon-burgundy.svg').then(r => r.status, () => 'none')")
        ok(tab == 200, f"but the other site's tab icon is in the copy ({tab})")
        pg.keyboard.press("Escape")
        ok(not pg.is_visible("#offmenu"), "Escape closes the menu")
        ok("offline copy of" in pg.evaluate("getComputedStyle(document.querySelector('footer'), '::before').content"),
           "the footer says the page is from the offline copy")
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
                   " .player .voices button:text-is('Your browser\u2019s voice')").first.click()
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
        change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, packed"), d)[1])
        pg.goto(BASE + "/read")
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        before = log.read_text().count("/offline/c/")
        # With What's new open, the reload waits for it to close.  Tapping
        # Update now beneath it closes it first; from the keyboard, it stays.
        pg.click("#offmenu .newsbtn")
        pg.wait_for_selector("#offnews", state="visible")
        pg.evaluate("window.ubStay = 1")
        pg.focus("#offmenu .get")
        pg.keyboard.press("Enter")
        wait_state(pg, "t.startsWith('Up to date')", 60000)
        pg.wait_for_timeout(500)
        ok(pg.evaluate("window.ubStay") == 1 and pg.is_visible("#offnews"),
           "with What's new open, the page is not reloaded when the update ends")
        with pg.expect_event("load", timeout=10000):
            pg.click("#offnews .x")
        ok(not pg.evaluate("window.ubStay"), "but once it is closed")
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
        changed = change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, changed"), d)[1])
        pg.goto(BASE + "/read")
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        # What's new: the change made after this copy, and none before it.
        pg.click("#offmenu .newsbtn")
        pg.wait_for_function("document.querySelector('#offnews .days li')", timeout=5000)
        said = pg.inner_text("#offnews")
        print("  " + " | ".join(said.split("\n")))
        ok(f"A change made for this test, number {change.n}" in said and f"December {24 + change.n}" in said
           and pg.locator("#offnews li").count() == 1,
           "What's new lists the change made after the copy, and nothing older")
        ok(pg.is_visible("#offmenu .get"), "with the menu and its Update button still open beneath it")
        pg.click("#offnews .x")
        ok(pg.is_hidden("#offnews") and pg.is_visible("#offmenu"), "its × closes it, and only it")
        pg.keyboard.press("Escape")
        pg.reload()
        pg.wait_for_function(f"document.querySelector('{ICON}').dataset.have === 'stale'", timeout=5000)
        print("  " + icon(pg)["title"])
        ok(pg.evaluate(f"getComputedStyle(document.querySelector('{ICON} .dot')).display") != "none",
           "after a reload, the icon's dot says an update is waiting")
        ok(not pg.is_visible("#offmenu") and not pg.locator(".offnote").count(),
           "and nothing else does until the menu is opened")
        # Offline and online again: the copy stays, out of date, and says so.
        ctx.set_offline(True)
        menu(pg)
        wait_state(pg, "t.includes('once online')", 5000)
        print("  offline: " + pg.inner_text(STATE))
        ok(not pg.locator("#offmenu .get").count() and icon(pg)["have"] == "stale",
           "offline, the copy is still kept and still out of date, with no button to update it")
        ok(pg.is_hidden("#offmenu p.remove"), "nor one to remove it, while it is all the site there is")
        ctx.set_offline(False)
        pg.wait_for_selector("#offmenu .get", timeout=10000)
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
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        print("  " + pg.inner_text(STATE))
        pg.evaluate(WATCH)
        before = log.read_text().count("/offline/c/")
        update(pg, lambda: ok(not pg.locator("#offmenu .get").count(), "the button goes as soon as it is pressed"))
        shown = pg.evaluate("JSON.parse(sessionStorage.shown)")
        steps = [t for t in shown if t.startswith("Updating: ")]
        print(f"  {len(steps)} steps shown: {steps[:2]} … {steps[-1:]}")
        ok(len(steps) >= 3, "the menu shows the update going on")
        ok(any(t.startswith("Updating the offline copy: ") for t in shown), "and so does the icon's label")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == len(papers), f"it fetched only what changed ({fetched} chunks)")
        pg.keyboard.press("Escape")

        print("An update that fails")
        ctx.set_offline(False)
        gone = change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, again"), d)[1])
        kept = (copy / gone["file"]).read_bytes()
        (copy / gone["file"]).unlink()
        pg.goto(BASE + "/read")
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        pg.evaluate("window.ubStay = 1")
        pg.click("#offmenu .get")
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
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        ok(pg.is_visible("#offmenu .get"), "with the site there, Update now is offered")
        pg.keyboard.press("Escape")
        srv.stop()
        menu(pg)
        wait_state(pg, "t.includes('once online')", 10000)
        print("  " + pg.inner_text("#offmenu .net") + ": " + pg.inner_text(STATE))
        i = icon(pg)
        ok(i["net"] == "off" and i["have"] == "stale", f"a page from the site, which then went: the icon says offline ({i['title']!r})")
        ok(not pg.locator("#offmenu .get").count() and not pg.locator("#offmenu .newsbtn").count()
           and pg.is_hidden("#offmenu p.remove"), "and the menu offers no Update now, What's new or Remove")
        pg.keyboard.press("Escape")
        pg.reload()
        ok(pg.locator("footer[data-copy]").count() == 1, "a page loaded now comes from the copy")
        pg.evaluate(WATCH)
        menu(pg)
        pg.wait_for_timeout(1500)
        i = icon(pg)
        ok(i["net"] == "off" and "once online" in pg.inner_text(STATE), f"and says offline ({i['title']!r})")
        ok(not any("Update now" in t for t in pg.evaluate("window.shown")) and not pg.locator("#offmenu .get").count(),
           "with Update now never offered")
        ok(pg.inner_text("#offmenu .net").lower().startswith("offline"), "and the menu's first line says offline")
        pg.keyboard.press("Escape")
        srv.start()
        menu(pg)
        pg.wait_for_selector("#offmenu .get", timeout=10000)
        i = icon(pg)
        ok(i["net"] == "on" and pg.inner_text("#offmenu .net").lower().startswith("online"),
           f"the site back, a page from the copy says online, and Update now is back ({i['title']!r})")
        pg.keyboard.press("Escape")

        print("Kept up to date by itself")
        ctx.set_offline(False)
        pg.goto(BASE + "/read")
        pg.evaluate("ubSettings.set('autoupdate', true)")
        # The update that stopped above, tapped, is not made by itself again
        # within the hour.
        tries = log.read_text().count(gone["file"])
        pg.reload()
        menu(pg)
        wait_state(pg, "t.includes('changed since')")
        pg.wait_for_timeout(1500)
        ok(log.read_text().count(gone["file"]) == tries and pg.is_visible("#offmenu .get"),
           "an update that stopped is not made by itself again within the hour, and Update now offers it")
        pg.keyboard.press("Escape")
        # A newer build: a page loaded starts the update with no tap, and What's
        # new opens at its end, over the menu, with what changed since the copy
        # kept: this build's change, and the one that stopped's.
        (copy / gone["file"]).write_bytes(kept)
        change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, by itself"), d)[1])
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
        ok("Closing this reloads the page" in said and pg.is_visible("#offmenu"), "over the menu, saying what closing it does")
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
        change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, online again"), d)[1])
        pg.goto(BASE + "/read")
        menu(pg)
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
        change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, quietly"), d)[1], news=False)
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
        pg.evaluate("ubSettings.set('autoupdate', false)")
        change(copy, lambda d: (d["pages"]["/"].update(t="The Urantia Book, listening"), d)[1])
        pg.goto(BASE + "/101:4")
        pg.locator("p.t .playp").first.click()
        pg.wait_for_selector(".player", timeout=5000)
        pg.evaluate("ubSettings.set('autoupdate', true); window.ubStay = 1")
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
        menu(pg)
        pg.click("#offmenu .drop")
        wait_state(pg, "t.includes('MB to download')")
        ok(pg.evaluate("caches.keys().then(k => k.length)") == 0, "nothing is kept")
        ok(icon(pg)["have"] == "none", "and the icon says so")

        print("On again in the same page, which keeps its worker")
        (copy / gone["file"]).write_bytes(kept)
        menu(pg)
        pg.click("#offmenu .keep")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/search?q=thought+adjuster")
        ok("In the text" in pg.inner_text("main"), "a search answers offline")
        ctx.set_offline(False)
        menu(pg)
        pg.click("#offmenu .drop")
        wait_state(pg, "t.includes('MB to download')")
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
