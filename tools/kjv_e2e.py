"""The King James Version end to end, in Chrome, against the dev server.

    .venv/bin/python tools/kjv_e2e.py        (after make data, with make serve running)

  - a study note's Bible reference, in its card, goes to the chapter with the
    verse tinted and arrived at;
  - with Paragraph previews on, it shows the verse in a card, Whole paper on
    and off (CLAUDE.md trap 44: the Whole paper handler rewrites book links,
    and must leave /kjv alone);
  - a verse's mark opens its translators' note as a card, inside the window,
    at 1400, 390 and 320 px, in English and in Russian;
  - the home page's tile leads to /kjv, and no page of it is wider than the
    window at 320 px;
  - a Bible address typed into the search box goes to its verse;
  - Width: Full widens a chapter, as it does the book's text; a book opens
    with its first letter dropped; under a verse, the paragraphs whose study
    notes cite it, each a link;
  - a tap on a verse brings down the running head, its reference a way to
    the Bible's Contents at the left, a book there opening to its chapters;
  - Page Down turns a chapter's page, as it does the book's.
"""

from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8130"
fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        fails.append(what)


def context(b, width: int, height: int, settings: dict | None = None):
    ctx = b.new_context(viewport={"width": width, "height": height}, has_touch=width < 600)
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no');"
                        " localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings or {})))
    return ctx


def note_reference(b) -> None:
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    pg.goto(BASE + "/1:5", wait_until="networkidle")
    pg.locator('a.fn[href="#fnst1_5_3_1"]').click()
    link = pg.locator('.pop.st a[href="/kjv/Isa/40:12"]')
    check(link.count() == 1, "a study note's card holds Isaiah 40:12 as a link")
    link.click()
    pg.wait_for_url("**/kjv/Isa/40:12")
    pg.wait_for_timeout(500)
    hit = pg.locator("p.kv.hit")
    check(hit.count() == 1 and hit.get_attribute("id") == "v12", "the chapter opens with verse 12 tinted")
    top = hit.bounding_box()["y"]
    check(0 <= top < 300, f"and arrived at, near the window's top ({top:.0f} px)")
    ctx.close()


def previews(b) -> None:
    for whole in (False, True):
        ctx = context(b, 1300, 900, {"preview": True, **({"whole": True} if whole else {})})
        pg = ctx.new_page()
        pg.goto(BASE + "/1:5", wait_until="networkidle")
        pg.locator('a.fn[href="#fnst1_5_3_1"]').first.click()
        link = pg.locator('.pop.st a[href="/kjv/Isa/40:22"]')
        link.hover()
        pg.wait_for_timeout(1200)
        pv = pg.locator(".pop.pv")
        words = pv.inner_text().replace("­", "") if pv.count() else ""
        check("Isaiah 40:22" in words and "circle of the earth" in words,
              f"the preview shows Isaiah 40:22, Whole paper {'on' if whole else 'off'}")
        check(pg.locator('.pop.st a[href="/kjv/Isa/40:22"]').count() == 1,
              f"and the link is as it was, Whole paper {'on' if whole else 'off'}")
        ctx.close()


def marginal_notes(b) -> None:
    for width, lang in ((1400, "en"), (390, "en"), (320, "en"), (390, "ru"), (320, "ru")):
        ctx = context(b, width, 800, {"lang": lang})
        pg = ctx.new_page()
        pg.goto(BASE + "/kjv/Gen/1", wait_until="networkidle")
        mark = pg.locator('a.fn[data-k="kjv"][href="#fnGen1_4"]')
        mark.scroll_into_view_if_needed()
        if width < 600:
            mark.tap()
        else:
            mark.click()
        pg.wait_for_timeout(300)
        card = pg.locator(".pop")
        box = card.bounding_box() if card.count() else None
        words = card.inner_text().replace("­", "") if card.count() else ""
        check("between the light and between the darkness" in words, f"Gen 1:4's note opens as a card, {width} px {lang}")
        check(bool(box) and box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5,
              f"inside the window, {width} px {lang}")
        wide = pg.evaluate("document.documentElement.scrollWidth")
        check(wide <= width, f"the chapter is no wider than the window ({wide} px), {width} px {lang}")
        ctx.close()


def home_and_contents(b) -> None:
    for width, lang in ((1300, "en"), (390, "en"), (320, "en"), (320, "ru")):
        ctx = context(b, width, 900, {"lang": lang})
        pg = ctx.new_page()
        pg.goto(BASE + "/", wait_until="networkidle")
        tile = pg.locator('ul.ftiles a[href="/kjv"]')
        check(tile.count() == 1 and tile.is_visible(), f"the home page's tile, {width} px {lang}")
        for path in ("/", "/kjv", "/kjv/Psa", "/kjv/Psa/119"):
            if path != "/":
                pg.goto(BASE + path, wait_until="networkidle")
            wide = pg.evaluate("document.documentElement.scrollWidth")
            check(wide <= width, f"{path} no wider than the window ({wide} px), {width} px {lang}")
        ctx.close()


def width_opening_and_cites(b) -> None:
    for width in ("measure", "full"):
        ctx = context(b, 1300, 800, {"width": width} if width == "full" else {})
        pg = ctx.new_page()
        pg.goto(BASE + "/kjv/Gen/1", wait_until="networkidle")
        w = pg.evaluate("document.querySelector('.kverses').getBoundingClientRect().width")
        # Full: the window less the rail, its gap and the padding.
        check(w < 800 if width == "measure" else w > 900, f"Width {width}: the verses {w:.0f} px wide")
        if width == "measure":
            # initial-letter sizes the letter without its font-size: ask for it.
            big = pg.evaluate("/^2\\b/.test(getComputedStyle(document.querySelector('p.kv.opening'), '::first-letter')"
                              ".initialLetter || '')")
            num = pg.evaluate("getComputedStyle(document.querySelector('p.kv.opening .vn')).display")
            check(big and num == "none", "Genesis opens with its first letter dropped, its verse number not shown")
        ctx.close()
    ctx = context(b, 390, 800)
    pg = ctx.new_page()
    pg.goto(BASE + "/kjv/Isa/40:12", wait_until="networkidle")
    line = pg.locator("#v12 + p.kvc")
    check(line.count() == 1 and line.is_visible() and "1:5.3" in line.inner_text(),
          "under Isaiah 40:12, the paragraphs whose notes cite it, 1:5.3 among them")
    line.locator('a[href="/1:5.3"]').click()
    pg.wait_for_url("**/1:5.3")
    check(True, "and 1:5.3 is a link to the paragraph")
    ctx.close()


def running_head_and_contents(b) -> None:
    # A tap on the text brings down the running head, as on the book's pages
    # (Tigran, 2026-11-21): the verse's reference, a button to the Contents,
    # the book's name, Settings and Home.
    ctx = context(b, 1300, 800)
    pg = ctx.new_page()
    pg.goto(BASE + "/kjv/Mal/3", wait_until="networkidle")
    pg.locator("#v6").click()
    pg.wait_for_timeout(700)
    h = pg.locator(".runhead")
    check(h.is_visible() and h.locator(".ref").inner_text() == "3:6" and "MALACHI" in h.locator(".pn").inner_text().upper(),
          "a click on a verse: the head names 3:6 and Malachi")
    check(h.locator(".ctl .set").count() == 1 and h.locator('.ctl a.home[href="/"]').count() == 1,
          "with Settings and Home at its right")
    check(pg.locator("#v6.named").count() == 1, "and the verse is tinted")
    check(pg.locator(".fbar.fup").count() == 0, "and no bar of bookmarks, which a verse is not")
    ctx.close()
    ctx = context(b, 390, 800)
    pg = ctx.new_page()
    pg.goto(BASE + "/kjv/Mal/3:6", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.locator("#v8").tap()
    pg.wait_for_timeout(400)
    check(pg.locator(".runhead .ref").inner_text() == "3:8", "a tap on a phone: the head names 3:8")
    pg.locator(".runhead .ref").tap()
    pg.wait_for_timeout(700)
    here = pg.locator(".kjvrail li.here > details > summary a")
    y = here.bounding_box()["y"]
    check(pg.locator(".kjvrail.shown").count() == 1 and here.inner_text() == "Malachi" and 80 < y < 200,
          f"its reference opens the Contents, Malachi a sixth of the way down ({y:.0f} px)")
    pg.locator('.kjvrail li.lazy summary:has(a[href="/kjv/Gen"])').tap()
    pg.wait_for_timeout(700)
    n = pg.locator('.kjvrail li.lazy:has(a[href="/kjv/Gen"]) ol.kch a').count()
    check(n == 50, f"Genesis opens to its chapters ({n})")
    pg.go_back()
    pg.wait_for_timeout(600)
    check(pg.locator(".kjvrail.shown").count() == 0 and pg.url.endswith("/kjv/Mal/3:6"),
          "Back folds the Contents again")
    ctx.close()


def search_and_keys(b) -> None:
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="networkidle")
    box = pg.locator('input[name="q"]').first
    box.fill("John 3:16")
    box.press("Enter")
    pg.wait_for_url("**/kjv/Joh/3:16")
    pg.wait_for_timeout(400)
    check(pg.locator("p.kv.hit#v16").count() == 1, "John 3:16 typed into the box goes to the verse, tinted")
    pg.goto(BASE + "/kjv/Psa/119", wait_until="networkidle")
    pg.mouse.click(5, 450)
    before = pg.evaluate("scrollY")
    pg.keyboard.press("PageDown")
    pg.wait_for_timeout(300)
    after = pg.evaluate("scrollY")
    check(after > before + 300, f"Page Down turns the chapter's page ({before} to {after})")
    ctx.close()


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        for step in (note_reference, previews, marginal_notes, home_and_contents, width_opening_and_cites,
                     running_head_and_contents, search_and_keys):
            step(b)
        b.close()
    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
