"""The Bible end to end, the KJV and the Synodal, in Chrome, against the dev server.

    .venv/bin/python tools/bible_e2e.py      (after make data, with make serve running)

  - a study note's Bible reference, in its card, goes to the chapter with the
    verse tinted and arrived at;
  - with Paragraph previews on, it shows the verse in a card, Whole paper on
    and off (CLAUDE.md trap 44: the Whole paper handler rewrites book links,
    and must leave /bible alone);
  - a verse's mark opens its translators' note as a card, inside the window,
    at 1400, 390 and 320 px, in English and in Russian;
  - the home page's tile leads to /bible, and no page of it is wider than the
    window at 320 px;
  - a Bible address typed into the search box goes to its verse;
  - Width: Full widens a chapter, as it does the book's text; a book opens
    with its first letter dropped; under a verse, the paragraphs whose study
    notes cite it, each a link;
  - a tap on a verse brings down the running head, its reference a way to
    the Bible's Contents at the left, a book there opening to its chapters;
  - Page Down turns a chapter's page, as it does the book's;
  - with the Synodal shown (Settings, Texts, its subtab The Bible, which opens
    on a page of the Bible), the two in columns where the window has room, in
    the reader's order, a line naming them, the row's id on its first line;
    in a fold under each row where it has not, a tap on any opening them all,
    kept on the next page; the Synodal alone, its title rows and the Greek's
    rows, the KJV standing in, named, where the Synodal has no verse;
  - a Synodal line's running head names it by its own numbers and its book's
    Russian name; «Пс 22:1» typed into the box opens Psalm 23 with verse 1's
    fold open at the Synodal;
  - the Contents number a book's chapters as the first text does, the
    Synodal's Psalm 22 on the KJV's 23, at the left, opened from another
    book, and on the book's page; a column's × hides its text, and with the
    KJV hidden the Contents number the Synodal's.
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
    # The settings once, on the context's first page: a page after it keeps
    # what a tap on the one before changed.
    ctx.add_init_script("try { localStorage.setItem('ub_tour', 'seen'); localStorage.setItem('ub_install', 'no');"
                        " if (!localStorage.getItem('ub_settings')) localStorage.setItem('ub_settings', %s); } catch (e) {}"
                        % json.dumps(json.dumps(settings or {})))
    return ctx


def note_reference(b) -> None:
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    pg.goto(BASE + "/1:5", wait_until="networkidle")
    pg.locator('a.fn[href="#fnst1_5_3_1"]').click()
    link = pg.locator('.pop.st a[href="/bible/Isa/40:12"]')
    check(link.count() == 1, "a study note's card holds Isaiah 40:12 as a link")
    link.click()
    pg.wait_for_url("**/bible/Isa/40:12")
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
        link = pg.locator('.pop.st a[href="/bible/Isa/40:22"]')
        link.hover()
        pg.wait_for_timeout(1200)
        pv = pg.locator(".pop.pv")
        words = pv.inner_text().replace("­", "") if pv.count() else ""
        check("Isaiah 40:22" in words and "circle of the earth" in words,
              f"the preview shows Isaiah 40:22, Whole paper {'on' if whole else 'off'}")
        check(pg.locator('.pop.st a[href="/bible/Isa/40:22"]').count() == 1,
              f"and the link is as it was, Whole paper {'on' if whole else 'off'}")
        ctx.close()


def marginal_notes(b) -> None:
    for width, lang in ((1400, "en"), (390, "en"), (320, "en"), (390, "ru"), (320, "ru")):
        ctx = context(b, width, 800, {"lang": lang})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Gen/1", wait_until="networkidle")
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
        tile = pg.locator('ul.ftiles a[href="/bible"]')
        check(tile.count() == 1 and tile.is_visible(), f"the home page's tile, {width} px {lang}")
        for path in ("/", "/bible", "/bible/Psa", "/bible/Psa/119"):
            if path != "/":
                pg.goto(BASE + path, wait_until="networkidle")
            wide = pg.evaluate("document.documentElement.scrollWidth")
            check(wide <= width, f"{path} no wider than the window ({wide} px), {width} px {lang}")
        ctx.close()


def width_opening_and_cites(b) -> None:
    seen = {}
    for width in ("measure", "full"):
        # 1600 px: at 1300 the measure is already more than the room beside
        # the Contents and the margin, and Full has nothing to widen, as on
        # the book's pages.
        ctx = context(b, 1600, 800, {"width": width} if width == "full" else {})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Gen/1", wait_until="networkidle")
        seen[width] = w = pg.evaluate("document.querySelector('#v1').getBoundingClientRect().width")
        if width == "full":
            check(w > seen["measure"] + 40, f"Width Full widens a verse ({seen['measure']:.0f} to {w:.0f} px)")
        if width == "measure":
            # initial-letter sizes the letter without its font-size: ask for it.
            big = pg.evaluate("/^2\\b/.test(getComputedStyle(document.querySelector('p.kv.opening'), '::first-letter')"
                              ".initialLetter || '')")
            num = pg.evaluate("getComputedStyle(document.querySelector('p.kv.opening .vn')).display")
            check(big and num == "none", "Genesis opens with its first letter dropped, its verse number not shown")
        ctx.close()
    ctx = context(b, 390, 800)
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Isa/40:12", wait_until="networkidle")
    # An orange dot at the verse's end, its card the paragraphs, and no line
    # under the verse nor a margin beside it (Tigran, 2026-11-21).
    dot = pg.locator('#v12 a.fn[data-k="kc"]')
    check(dot.count() == 1 and dot.is_visible() and pg.locator(".ka:visible").count() == 0,
          "Isaiah 40:12 ends with the dot, and no line of study notes under it")
    dot.tap()
    pg.wait_for_timeout(400)
    card = pg.locator(".pop .body")
    check(card.count() == 1 and "1:5.3" in card.inner_text(), "its card names the paragraphs, 1:5.3 among them")
    card.locator('a[href="/1:5.3"]').tap()
    pg.wait_for_url("**/1:5.3")
    check(True, "and 1:5.3 is a link to the paragraph")
    ctx.close()
    # The dot follows the first text shown: the Synodal's line, first or alone.
    for order in ("rsb kjv", "rsb"):
        ctx = context(b, 390, 800, {"bible": order})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Isa/40", wait_until="networkidle")
        pg.wait_for_timeout(500)
        at = pg.evaluate("[...document.querySelectorAll('a.fn[data-k=\"kc\"]')].map(a => [a.closest('p').dataset.k,"
                         " a.closest('p').id, !!a.offsetParent])")
        check(at and all(x[0] == "rsb" and x[2] for x in at) and ["rsb", "v12", True] in at,
              f"{order}: the dots on the Synodal's lines ({at})")
        ctx.close()


def running_head_and_contents(b) -> None:
    # A tap on the text brings down the running head, as on the book's pages
    # (Tigran, 2026-11-21): the verse's reference, a button to the Contents,
    # the book's name, Settings and Home.
    ctx = context(b, 1300, 800)
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Mal/3", wait_until="networkidle")
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
    pg.goto(BASE + "/bible/Mal/3:6", wait_until="networkidle")
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
    pg.locator('.kjvrail li.lazy summary:has(a[data-ch="/bible/Gen"])').tap()
    pg.wait_for_timeout(700)
    n = pg.locator('.kjvrail li.lazy:has(a[data-ch="/bible/Gen"]) ol.kch a').count()
    check(n == 50, f"Genesis opens to its chapters ({n})")
    pg.go_back()
    pg.wait_for_timeout(600)
    check(pg.locator(".kjvrail.shown").count() == 0 and pg.url.endswith("/bible/Mal/3:6"),
          "Back folds the Contents again")
    ctx.close()


def search_and_keys(b) -> None:
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="networkidle")
    box = pg.locator('input[name="q"]').first
    box.fill("John 3:16")
    box.press("Enter")
    pg.wait_for_url("**/bible/Joh/3:16")
    pg.wait_for_timeout(400)
    check(pg.locator("p.kv.hit#v16").count() == 1, "John 3:16 typed into the box goes to the verse, tinted")
    pg.goto(BASE + "/bible/Psa/119", wait_until="networkidle")
    pg.mouse.click(5, 450)
    before = pg.evaluate("scrollY")
    pg.keyboard.press("PageDown")
    pg.wait_for_timeout(300)
    after = pg.evaluate("scrollY")
    check(after > before + 300, f"Page Down turns the chapter's page ({before} to {after})")
    ctx.close()


def synodal(b) -> None:
    # Columns where the window has room (800 px: no Contents' track, no
    # margin's), in the reader's order, a line naming them.
    for order in ("kjv rsb", "rsb kjv"):
        ctx = context(b, 800, 900, {"bible": order})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Psa/23", wait_until="networkidle")
        pg.wait_for_timeout(500)
        first = order.split()[0]
        cells = pg.evaluate("[...document.querySelectorAll('.krow[data-row=\"v1\"] > .bc')]"
                            ".map(c => [c.dataset.k, Math.round(c.getBoundingClientRect().left)])")
        check(len(cells) == 2 and cells[0][0] == first and cells[0][1] < cells[1][1],
              f"{order}: two columns, {first} at the left ({cells})")
        names = pg.locator(".bnames .cn b").all_inner_texts()
        check([x.upper() for x in names] == [{"kjv": "KJV", "rsb": "СИНОДАЛЬНЫЙ"}[k] for k in order.split()],
              f"{order}: a line names them ({names})")
        check(pg.evaluate("document.getElementById('v1').dataset.k") == first, f"{order}: the row's id on {first}'s line")
        check(pg.locator(".btf:visible").count() == 0, f"{order}: no fold in columns")
        heads = pg.locator(".bhds .bhd:visible h1").all_inner_texts()
        check(len(heads) == 2 and "22" in " ".join(heads) and "23" in " ".join(heads), f"{order}: each column's head ({heads})")
        ctx.close()
    # Folds where it has not: one tap opens every one, kept on the next page.
    ctx = context(b, 390, 800, {"bible": "kjv rsb"})
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Gen/1", wait_until="networkidle")
    folds = pg.locator(".btf:visible")
    n = folds.count()
    check(n == 31 and folds.first.locator(".bfold").inner_text() == "Синодальный", f"a fold under each verse ({n}), named")
    folds.nth(2).locator(".bfold").tap()
    pg.wait_for_timeout(600)
    opened = pg.locator(".btf .tr:visible").count()
    check(opened == 31, f"a tap opens them all ({opened})")
    check("И сказал Бог: да будет свет" in pg.locator('.krow[data-row="v3"] .btf .tr').inner_text().replace("\u00ad", ""),
          "Genesis 1:3's fold holds the Synodal's 1:3")
    pg.goto(BASE + "/bible/Gen/2", wait_until="networkidle")
    pg.wait_for_timeout(500)
    check(pg.locator(".btf .tr:visible").count() == pg.locator(".btf:visible").count() > 0, "and they stay open on the next page")
    ctx.close()
    # The Synodal alone: its lines first, the Greek's own rows, and the KJV's
    # 1:1 of the Song, which the Synodal has not, standing in, named.
    ctx = context(b, 390, 800, {"bible": "rsb"})
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Sol/1", wait_until="networkidle")
    pg.wait_for_timeout(500)
    v1 = pg.locator("#v1")
    check(v1.get_attribute("data-k") == "kjv" and "bstand" in v1.get_attribute("class") and v1.is_visible(),
          "the Song's 1:1, the KJV's alone, stands in")
    check(pg.locator("#v2").get_attribute("data-k") == "rsb", "the Song's 1:2 is the Synodal's 1:1")
    check(pg.locator(".btf:visible").count() == 0 and pg.locator(".bwho:visible").count() == 0,
          "no fold, and no name over the Synodal's rows, the Synodal being first")
    pg.goto(BASE + "/bible/Dan/3", wait_until="networkidle")
    check(pg.locator('[id="s3-24"]').is_visible(), "Daniel 3:24 of the Greek stands in its row")
    ctx.close()
    # The running head of a Synodal line: its own numbers, its book's name.
    ctx = context(b, 1300, 800, {"bible": "rsb kjv"})
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Psa/23", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.locator("#v1").click()
    pg.wait_for_timeout(600)
    h = pg.locator(".runhead")
    check(h.locator(".ref").inner_text() == "22:1" and "ПСАЛТИРЬ" in h.locator(".pn").inner_text().upper(),
          f"a Synodal line's head: 22:1 and Псалтирь ({h.locator('.ref').inner_text()})")
    ctx.close()
    # Settings, Texts: the Bible's subtab on a page of the Bible; a tick there
    # draws the page again in place.
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Gen/1", wait_until="networkidle")
    pg.evaluate("window.ubSettings.open('translations')")
    pg.wait_for_timeout(300)
    check(pg.locator('.txtabs [data-sub="bible"][aria-selected="true"]').count() == 1 and
          pg.locator('.txsub[data-sub="bible"]').is_visible() and not pg.locator('.txsub[data-sub="book"]').is_visible(),
          "Texts opens at its subtab The Bible on a page of the Bible")
    check(pg.locator(".btf:visible").count() == 0, "with the KJV alone, no fold")
    pg.locator('.blist li[data-b="rsb"] label').click()
    pg.wait_for_timeout(600)
    check(pg.evaluate("JSON.parse(localStorage.getItem('ub_settings')).bible") == "kjv rsb" and
          pg.locator('.krow[data-row="v1"] > .bc').count() == 2,
          "a tick shows the Synodal, in columns, the window having room for two since there is no margin's track")
    pg.locator('.txtabs [data-sub="book"]').click()
    check(pg.locator('.txsub[data-sub="book"]').is_visible(), "and the book's subtab shows the book's texts")
    ctx.close()
    # The Contents name the books in the interface's language, whichever
    # text is first; the text's own head stays its own (Tigran, 2026-11-21).
    for lang, order, want, head in (("ru", "kjv", "Малахия", "CHAPTER 3"), ("en", "rsb", "Malachi", "ГЛАВА 3"),
                                    ("ru", "rsb", "Малахия", "ГЛАВА 3"), ("en", "kjv", "Malachi", "CHAPTER 3")):
        ctx = context(b, 1300, 900, {"lang": lang, "bible": order})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Mal/3", wait_until="networkidle")
        pg.wait_for_timeout(400)
        name = pg.locator(".kjvrail li.here > details > summary a").inner_text()
        h1 = pg.locator(".kjvtop .bhd:visible h1").inner_text().upper()
        check(name == want and h1 == head, f"{lang} interface, {order} first: the Contents say {name}, the head {h1}")
        ctx.close()
    # «Пс 22:1» typed into the box: Psalm 23, verse 1's fold open at the Synodal.
    ctx = context(b, 390, 800, {"bible": "kjv rsb"})
    pg = ctx.new_page()
    pg.goto(BASE + "/", wait_until="networkidle")
    box = pg.locator('input[name="q"]').first
    box.fill("Пс 22:1")
    box.press("Enter")
    pg.wait_for_url("**/bible/Psa/23:1#tr-rsb")
    pg.wait_for_timeout(600)
    tr = pg.locator('.krow[data-row="v1"] .btf .tr')
    check(tr.count() == 1 and tr.is_visible() and "Господь" in tr.inner_text().replace("\u00ad", ""),
          "«Пс 22:1» opens Psalm 23 with verse 1's fold open at the Synodal")
    check(pg.locator(".btf .tr:visible").count() == 1, "and that fold alone")
    ctx.close()


def contents_numbers(b) -> None:
    # A name in the Contents goes to the first of what it holds, a book's to
    # its first chapter and a testament's to its first book's (Tigran,
    # 2026-11-21: "in the Contents the parent node is just a shortcut for the
    # first of its children").
    ctx = context(b, 1300, 900)
    pg = ctx.new_page()
    for name, want in (("Psalms", "/bible/Psa/1"), ("The New Testament", "/bible/Mat/1"), ("Genesis", "/bible/Gen/1")):
        pg.goto(BASE + "/bible/Mal/3", wait_until="networkidle")
        pg.locator(".kjvrail summary > a", has_text=name).first.click()
        pg.wait_for_load_state("networkidle")
        check(pg.url == BASE + want, f"{name} in the Contents goes to {want} ({pg.url[len(BASE):]})")
    ctx.close()
    # The Contents numbered as the first text numbers the book (Tigran,
    # 2026-11-21: "match the Contents to the actual books").
    vis = ("() => [...document.querySelectorAll('.kjvrail li.here > details > ol')].filter(o => o.offsetParent)"
           ".map(o => [o.className, (o.querySelector(':scope > li.here > a') || {}).textContent])")
    for order, want in (("kjv", [["kch kchk", "23"]]), ("kjv rsb", [["kch kchk", "23"]]),
                        ("rsb", [["kch kchs", "22"]]), ("rsb kjv", [["kch kchs", "22"]])):
        ctx = context(b, 1300, 900, {"bible": order})
        pg = ctx.new_page()
        pg.goto(BASE + "/bible/Psa/23", wait_until="networkidle")
        got = pg.evaluate(vis)
        check(got == want, f"{order} first: the Contents show one list, Psalm {want[0][1]} the one being read ({got})")
        ctx.close()
    ctx = context(b, 1300, 900, {"bible": "rsb"})
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Psa/116", wait_until="networkidle")
    check(pg.evaluate(vis) == [["kch kchs", "114"]], "the KJV's 116 is the Synodal's 114 and 115: 114 being read")
    pg.locator(".kjvrail ol.kchs a", has_text="115").first.click()
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(500)
    top = pg.evaluate("document.getElementById('s115-0').getBoundingClientRect().top")
    check(pg.url.endswith("/bible/Psa/116#s115-0") and 0 <= top < 450,
          f"its 115 goes to its first line, on the same page ({pg.url[len(BASE):]}, {top:.0f} px)")
    pg.locator(".kjvrail ol.kchs a", has_text="10").first.click()
    pg.wait_for_load_state("networkidle")
    check(pg.url.endswith("/bible/Psa/11"), f"its 10 is the KJV's 11 ({pg.url[len(BASE):]})")
    # Another book opened in the Contents: both lists lifted from its page.
    pg.goto(BASE + "/bible/Gen/1", wait_until="networkidle")
    pg.evaluate("document.querySelector('.kjvrail li.lazy:has(a[data-ch=\"/bible/Psa\"]) details').open = true")
    pg.wait_for_timeout(800)
    lists = pg.evaluate("[...document.querySelectorAll('.kjvrail li.lazy:has(a[data-ch=\"/bible/Psa\"]) ol')]"
                        ".map(o => [o.className, !!o.offsetParent, o.children.length, o.children[9].querySelector('a').getAttribute('href')])")
    check(lists == [["kch kchk", False, 151, "/bible/Psa/10"], ["kch kchs", True, 151, "/bible/Psa/11"]],
          f"Psalms opened from Genesis: both lists, the Synodal's shown ({lists})")
    pg.goto(BASE + "/bible/Psa", wait_until="networkidle")
    shown = pg.evaluate("[...document.querySelectorAll('ol.kchaps')].filter(o => o.offsetParent).map(o => o.className)")
    a = pg.locator("ol.kchaps.kchs a", has_text="22").first
    check(shown == ["kchaps kchs"] and a.get_attribute("href") == "/bible/Psa/23",
          f"the book's page lists the Synodal's, its 22 the KJV's 23 ({shown})")
    check(pg.locator("ol.kchaps.kchs li.cited").count() > 0, "a psalm a study note cites marked in it")
    ctx.close()
    # A column's ×: the text hidden, and with the KJV hidden, the Contents
    # number the Synodal's.
    ctx = context(b, 1400, 900, {"bible": "kjv rsb"})
    pg = ctx.new_page()
    pg.goto(BASE + "/bible/Psa/23", wait_until="networkidle")
    pg.wait_for_timeout(500)
    x = pg.locator('.bnames .bnx[data-k="kjv"]')
    check(x.count() == 1 and x.is_visible() and x.get_attribute("aria-label") == "Hide this text",
          "each column's name has its ×")
    x.click()
    pg.wait_for_timeout(600)
    check(pg.evaluate("JSON.parse(localStorage.getItem('ub_settings')).bible") == "rsb" and
          pg.locator(".bnames").count() == 0 and pg.locator(".bc").count() == 0 and
          pg.evaluate("document.getElementById('v1').dataset.k") == "rsb",
          "the KJV's × hides it: the Synodal alone, no columns")
    check(pg.evaluate(vis) == [["kch kchs", "22"]], "and the Contents number the Synodal's psalms")
    ctx.close()


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome")
        for step in (note_reference, previews, marginal_notes, home_and_contents, width_opening_and_cites,
                     running_head_and_contents, search_and_keys, synodal, contents_numbers):
            step(b)
        b.close()
    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
