"""Work offline, end to end, in Chrome: turn it on, read and search with the
network off, learn of a newer copy and take it, survive an update that fails,
and turn it off.

    ~/Software/ml/venv-browser/bin/python tools/offline_e2e.py

Needs a built copy (`make offline`).  It serves a scratch copy of var/offline/
from a server of its own, on 127.0.0.1:8131 with the visit counter off, so that
it can make a "newer build" by changing that copy, and leaves var/offline/ and
the dev server alone.  localhost is a secure context, so the worker runs there
as on the live site.  Not a gate: offline/check.py is, for every page; this
shows that the worker, the icon at the header's corner and its menu do what
they say.
"""

from __future__ import annotations

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
import os, pathlib, sys
os.environ["UB_VISITS"] = "off"
sys.path.insert(0, sys.argv[2])
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=8131, log_level="info")
"""

fails: list[str] = []

# Work offline's icon, and the line in its menu that says what the copy is.
ICON = ".top .offline"
STATE = "#offmenu .state"


def ok(cond, what):
    print(("  ok    " if cond else "  FAIL  ") + what)
    if not cond:
        fails.append(what)


def change(copy: pathlib.Path, edit, names=("misc",)) -> dict:
    """A newer build of the scratch copy: each chunk named passed through `edit`,
    renamed by its new hash, and the manifest made to say so.  Returns the
    last chunk changed."""
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
    m["made"] = "2026-12-25T12:00:00Z"
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

# What the page shows while an update runs, in the menu and on the icon's
# label, each line once, as it changes.
WATCH = """() => { window.shown = [];
  const keep = () => { for (const t of [document.querySelector('#offmenu .state').textContent,
                                        document.querySelector('.top .offline').title])
    if (!window.shown.includes(t)) window.shown.push(t); };
  new MutationObserver(keep).observe(document.body, {subtree: true, childList: true, characterData: true,
                                                     attributes: true, attributeFilter: ['title']}); }"""


def wait_state(pg, test: str, timeout: int = 30000) -> None:
    """Until the menu's line passes `test`, a JavaScript expression in t."""
    pg.wait_for_function(f"(t => {test})(document.querySelector('{STATE}').textContent)", timeout=timeout)


def menu(pg) -> None:
    """Open the icon's menu, unless it is open."""
    if not pg.is_visible("#offmenu"):
        pg.click(ICON)
    pg.wait_for_selector("#offmenu", state="visible")


def icon(pg) -> dict:
    return pg.evaluate(f"(c => ({{net: c.dataset.net, have: c.dataset.have, title: c.title,"
                       f" shown: !c.hidden}}))(document.querySelector('{ICON}'))")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        copy = pathlib.Path(tmp) / "offline"
        shutil.copytree(ROOT / "var" / "offline", copy)
        log = open(pathlib.Path(tmp) / "server.log", "w")
        srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", SERVER, str(copy), str(ROOT)],
                               stdout=log, stderr=subprocess.STDOUT, cwd=tmp)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(BASE + "/healthz", timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
            return run(copy, pathlib.Path(tmp) / "server.log")
        finally:
            srv.terminate()
            srv.wait()


def run(copy: pathlib.Path, log: pathlib.Path) -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.accept())
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        print("Turning it on")
        pg.goto(BASE + "/101:4")
        ok("Merritt Horn" in pg.inner_text(".listenrow .by"), "online, Listen reads with Merritt Horn")
        i = icon(pg)
        ok(i["shown"] and i["net"] == "on" and i["have"] == "none" and i["title"] == "Online",
           f"the icon at the header's corner says online, with no copy ({i})")
        ok(not pg.locator("dialog.settings input[name=offline]").count(), "Settings has no Offline section")
        ok(not pg.locator("#offmenu input").count(), "and the menu has no switch to turn off")
        pg.click(ICON)
        ok(pg.is_visible("#offmenu"), "the icon opens its menu")
        wait_state(pg, "t.includes('MB to download')")
        print("  " + pg.inner_text(STATE))
        t = time.time()
        pg.click("#offmenu .keep")
        wait_state(pg, "t.startsWith('Up to date')", 120000)
        print(f"  downloaded in {time.time() - t:.1f} s: " + pg.inner_text(STATE))
        ok(icon(pg)["have"] == "kept", f"the icon says a copy is kept ({icon(pg)['title']!r})")
        pg.click(ICON)
        ok(not pg.is_visible("#offmenu"), "the icon closes its menu again")
        m = json.loads((copy / "manifest.json").read_text())
        used = pg.evaluate("navigator.storage.estimate().then(e => e.usage)")
        print(f"  the browser keeps {used / 1e6:.1f} MB: {m['bytes'] / 1e6:.1f} MB gzipped, {m['raw'] / 1e6:.1f} MB unpacked")
        ok(used < m["bytes"] * 1.25, "it keeps the copy gzipped, as it came")

        # What the server sends, to hold the worker's answers to.
        want = {}
        urls = ["/101:4", "/101:4.2-3", "/i/god", "/appendix/A", "/lists/1955", "/index/G", "/", "/read",
                "/part/2", "/search?q=prayer", "/search?q=self-conscious&in=text", "/search?q=Badanon&in=notes",
                "/i/jesus/read", "/i/prayer/read/theme",
                "/rail/120?v=1", "/static/fonts/UBGoudy.woff2", "/speech/101:4", "/speech/0:0"]
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
        pg.goto(BASE + "/101:4")
        ok("Merritt Horn" in pg.inner_text(".listenrow .by"),
           "offline, Listen still names the voice Settings chose")
        pg.click(".listenrow button.listen")
        pg.wait_for_function("(document.querySelector('.player .who') || {}).textContent"
                             " && document.querySelector('.player .who').textContent.includes('connection')",
                             timeout=10000)
        pg.wait_for_timeout(1500)
        ok("connection" in pg.inner_text(".player .who") and pg.evaluate("!speechSynthesis.speaking"),
           f"and refuses to play, saying why, and the message stays ({pg.inner_text('.player .who')!r})")
        pg.click(".player button.close") if pg.locator(".player button.close").count() else None
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
        pg.click("#offmenu .get")
        wait_state(pg, "t.startsWith('Up to date')", 60000)
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
        pg.click("#offmenu .get")
        wait_state(pg, "t.startsWith('Up to date')")
        fetched = log.read_text().count("/offline/c/") - before
        ok(fetched == 1, f"the update fetched only what changed ({fetched} chunk)")
        ok(icon(pg)["have"] == "kept", "and the dot goes")
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
        pg.click("#offmenu .get")
        ok(not pg.locator("#offmenu .get").count(), "the button goes as soon as it is pressed")
        wait_state(pg, "t.startsWith('Up to date')", 60000)
        shown = pg.evaluate("window.shown")
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
        pg.click("#offmenu .get")
        wait_state(pg, "t.includes('stopped')")
        print("  " + pg.inner_text(STATE))
        ok(icon(pg)["have"] == "stale", "the icon still says an update is waiting")
        pg.keyboard.press("Escape")
        ctx.set_offline(True)
        pg.goto(BASE + "/")
        ok(pg.title() == "The Urantia Book, changed", "the copy before it still answers, whole")

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
