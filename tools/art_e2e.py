"""The home page's part pictures, in Chrome (templates/home.html, ub.css
.fpart; data/art/, tools/make_art.py; DECISIONS.md, The home page).

    .venv/bin/python tools/art_e2e.py

Not a gate: it needs Chrome.  It runs the app itself on 127.0.0.1:8140 with
the visit counter off and no offline copy to offer, so that every picture is
asked of the server and what the browser chose can be seen.

At a desk's width, a tablet's and two phones', at one, two and three device
pixels to the page's one, in English and in Russian, in the light theme and
the dark, with Settings' Foreword in Part I on and off:

  each card's picture is drawn, and is the file its screen needs: the 640 on
  an ordinary monitor, the 1280 on a dense screen;

  the card is 16:9, and the same box before its picture arrives as after, so
  nothing on the page moves as they load;

  the words are inside the card, none cut, and stand against what is under
  them at 4.5 to 1 or better, measured on the screen with the words made
  clear: the lightest pixel under each line (WCAG's least for text this size);

  what is under the pointer at a card's middle, and at its words, is its link,
  and a click goes to the part's title page (CLAUDE.md, trap 61);

  the page is no wider than its window;

and with every picture refused, the cards keep their shape and the words read
against the ground alone; and with scripts off the pictures are there.
"""

from __future__ import annotations

import os
import pathlib
import struct
import subprocess
import sys
import time
import urllib.request
import zlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8140
BASE = f"http://127.0.0.1:{PORT}"
CHROME = "/usr/bin/google-chrome"
fails: list[str] = []


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def png_rgb(data: bytes) -> list[tuple[int, int, int]]:
    """The pixels of an 8-bit RGB or RGBA PNG that is not interlaced, which is
    what Chrome writes a screenshot as.  No imaging library is in .venv."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    i, idat = 8, b""
    w = h = bpp = 0
    while i < len(data):
        n, kind = struct.unpack(">I4s", data[i:i + 8])
        body = data[i + 8:i + 8 + n]
        if kind == b"IHDR":
            w, h, depth, colour, _, _, lace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and colour in (2, 6) and lace == 0, (depth, colour, lace)
            bpp = 3 if colour == 2 else 4
        elif kind == b"IDAT":
            idat += body
        i += 12 + n
    raw, stride, out, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += [(line[x], line[x + 1], line[x + 2]) for x in range(0, stride, bpp)]
        prev = line
    return out


def lum(r: int, g: int, b: int) -> float:
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r / 255) + 0.7152 * f(g / 255) + 0.0722 * f(b / 255)


# Each card as drawn: its box, its picture's, the file taken, and its words.
CARDS = """() => [...document.querySelectorAll('.front-toc .fpart')].map(a => {
    const box = e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; },
      i = a.querySelector('img'), vis = e => e.getClientRects().length > 0,
      words = [...a.querySelectorAll('.fcap > span')].filter(vis).map(s => {
        const r = document.createRange(); r.selectNodeContents(s); const b = r.getBoundingClientRect(), cs = getComputedStyle(s);
        return {cls: s.className.split(' ')[0], box: [b.left, b.top, b.right, b.bottom], cut: s.scrollWidth > s.clientWidth + 1,
                alpha: +(cs.color.match(/[\\d.]+(?=\\))/) || [1])[0] || 1,
                rgba: cs.color}; });
    return {href: a.getAttribute('href'), box: box(a), img: box(i), drawn: i.complete && i.naturalWidth > 0,
            file: (i.currentSrc.match(/part\\d-\\d+\\.webp/) || [''])[0], words: words,
            radius: getComputedStyle(a).borderRadius}; })"""
# What is under a point, as the link it is in.
UNDER = "([x, y]) => { const e = document.elementFromPoint(x, y), a = e && e.closest('a'); return a ? a.getAttribute('href') : null; }"
OVER = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


def fresh(b, w: int, h: int, dpr: float, lang: str, theme: str, foreword: bool = True, **more):
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, service_workers="block",
                        color_scheme=theme, **more)
    kept = {"lang": lang}
    if not foreword:
        kept["foreword"] = "off"
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_settings', '%s'); } catch (e) {}"
                        % __import__("json").dumps(kept))
    return ctx


def alpha_of(rgba: str) -> float:
    """The opacity of a computed colour: rgba(255, 255, 255, 0.88), or rgb(...)."""
    parts = rgba[rgba.index("(") + 1:rgba.rindex(")")].replace("/", ",").split(",")
    return float(parts[3]) if len(parts) > 3 else 1.0


def contrast(pg, cards) -> float:
    """The least ratio of any line of words on any card against the lightest
    pixel under it, the words made clear for the photograph."""
    tag = pg.add_style_tag(content=".fpart .fcap > span { color: transparent !important; text-shadow: none !important; }"
                                   " .fbar { visibility: hidden !important; }")
    least = 99.0
    for i in range(len(cards)):
        pg.locator(".front-toc .fpart").nth(i).scroll_into_view_if_needed()
        now = pg.evaluate(CARDS)[i]
        # Where each line is now, the card brought into view; its own colour as
        # it was before the words were made clear.
        for wd, was in zip(now["words"], cards[i]["words"]):
            x0, y0, x1, y1 = wd["box"]
            shot = pg.screenshot(clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
            light = max(lum(*px) for px in png_rgb(shot))
            a = alpha_of(was["rgba"])
            text = a * 1.0 + (1 - a) * light          # the words' white at their opacity, over that ground
            least = min(least, (text + 0.05) / (light + 0.05))
    tag.evaluate("e => e.remove()")
    return least


def look(b, w: int, h: int, dpr: float, lang: str, theme: str, foreword: bool = True) -> None:
    say = f"[{w} px, {dpr:g}x, {lang}, {theme}{'' if foreword else ', Foreword on its own'}] "
    ctx = fresh(b, w, h, dpr, lang, theme, foreword)
    pg = ctx.new_page()
    asked: list[str] = []
    pg.on("request", lambda r: asked.append(r.url) if "/static/art/" in r.url else None)
    pg.goto(BASE + "/", wait_until="networkidle")
    cards = pg.evaluate(CARDS)
    ok([c["href"] for c in cards] == ["/part/1", "/part/2", "/part/3", "/part/4"] and all(c["drawn"] for c in cards),
       say + "four cards, each to its part, each picture drawn")
    # A card of w CSS pixels wants w * dpr across: the 640 where that is enough.
    want = [f"part{n}-{640 if (c['box'][2] - c['box'][0]) * dpr <= 640 else 1280}.webp" for n, c in enumerate(cards, 1)]
    ok([c["file"] for c in cards] == want and len(asked) == 4,
       say + f"the file its screen needs, and no other asked for: {cards[0]['file']}")
    shape = [(c["box"][2] - c["box"][0]) / (c["box"][3] - c["box"][1]) for c in cards]
    filled = all(max(abs(c["box"][k] - c["img"][k]) for k in range(4)) < 0.6 for c in cards)
    ok(all(abs(s - 16 / 9) < 0.02 for s in shape) and filled,
       say + f"each card 16:9 and its picture edge to edge ({cards[0]['box'][2] - cards[0]['box'][0]:.0f} x {cards[0]['box'][3] - cards[0]['box'][1]:.0f})")
    inside = all(c["box"][0] - 0.5 <= wd["box"][0] and wd["box"][2] <= c["box"][2] + 0.5
                 and c["box"][1] - 0.5 <= wd["box"][1] and wd["box"][3] <= c["box"][3] + 0.5 and not wd["cut"]
                 for c in cards for wd in c["words"])
    lines = [len(c["words"]) for c in cards]
    ok(inside and lines == [3, 3, 3, 3], say + "the part, the name and one range on each, inside the card, none cut")
    least = contrast(pg, cards)
    ok(least >= 4.5, say + f"the words against the lightest pixel under them: {least:.1f} to 1 at the least")
    ok(pg.evaluate(OVER) <= 0, say + "the page no wider than its window")
    under = []
    for i, c in enumerate(cards):
        pg.locator(".front-toc .fpart").nth(i).scroll_into_view_if_needed()
        c = pg.evaluate(CARDS)[i]
        mid = [(c["box"][0] + c["box"][2]) / 2, (c["box"][1] + c["box"][3]) / 2]
        top = [c["box"][0] + 12, c["box"][1] + 12]
        name = next(wd for wd in c["words"] if wd["cls"] == "lbl")["box"]
        under.append([pg.evaluate(UNDER, pt) for pt in (mid, top, [(name[0] + name[2]) / 2, (name[1] + name[3]) / 2])])
    ok(under == [[c["href"]] * 3 for c in cards], say + "under the pointer at a card's middle, its corner and its name: its link")
    ctx.close()


def run() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)

        print("Every screen")
        for w, h, dpr in ((1280, 900, 1), (1280, 900, 2), (820, 1100, 2), (390, 844, 3), (390, 844, 2), (320, 640, 2)):
            for lang in ("en", "ru"):
                look(b, w, h, dpr, lang, "light")
        look(b, 1280, 900, 1, "en", "dark")
        look(b, 390, 844, 3, "ru", "dark")
        look(b, 1280, 900, 1, "en", "light", foreword=False)
        look(b, 390, 844, 3, "ru", "light", foreword=False)

        print("Nothing moves as the pictures arrive, and a click goes to the part")
        ctx = fresh(b, 390, 844, 3, "ru", "light")
        pg = ctx.new_page()
        held: list = []
        pg.route("**/static/art/**", lambda route: held.append(route))
        pg.goto(BASE + "/", wait_until="domcontentloaded")
        pg.wait_for_timeout(600)
        before = pg.evaluate(CARDS)
        tiles = pg.evaluate("document.querySelector('.ftiles').getBoundingClientRect().top + scrollY")
        ok(len(held) == 4 and not any(c["drawn"] for c in before), "four pictures asked for and held back")
        for route in held:
            route.continue_()
        pg.wait_for_function("[...document.querySelectorAll('.fpart img')].every(i => i.complete && i.naturalWidth > 0)")
        after = pg.evaluate(CARDS)
        ok([c["box"] for c in before] == [c["box"] for c in after]
           and tiles == pg.evaluate("document.querySelector('.ftiles').getBoundingClientRect().top + scrollY"),
           "every card's box, and what stands under the cards, where they were before the pictures came")
        pg.locator(".front-toc .fpart").nth(2).click()
        pg.wait_for_url("**/part/3")
        ok(pg.url.endswith("/part/3"), "a click on the third card goes to Part III's title page")
        ctx.close()

        print("With every picture refused")
        ctx = fresh(b, 390, 844, 2, "ru", "light")
        pg = ctx.new_page()
        pg.route("**/static/art/**", lambda route: route.abort())
        pg.goto(BASE + "/", wait_until="networkidle")
        cards = pg.evaluate(CARDS)
        shape = [(c["box"][2] - c["box"][0]) / (c["box"][3] - c["box"][1]) for c in cards]
        ok(not any(c["drawn"] for c in cards) and all(abs(s - 16 / 9) < 0.02 for s in shape), "the cards keep their shape")
        least = contrast(pg, cards)
        ok(least >= 4.5, f"and the words read against the ground alone: {least:.1f} to 1 at the least")
        ctx.close()

        print("Scripts off")
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/", wait_until="networkidle")
        shots = [pg.locator(".front-toc .fpart img").nth(i).screenshot() for i in range(4)]
        ok(pg.locator(".front-toc .fpart img").count() == 4 and all(len(set(png_rgb(s))) > 500 for s in shots),
           "the four pictures are there, each a picture and no flat ground")
        ctx.close()
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer (tools/runhead_e2e.py NO_COPY).
NO_COPY = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main() -> int:
    env = dict(os.environ, UB_VISITS="off", UB_MEANING="off")
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", NO_COPY,
                            str(ROOT / "var" / "no-offline-copy"), str(PORT)], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
