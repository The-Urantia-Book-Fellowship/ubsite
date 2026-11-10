"""Help, and the tour (templates/help.html, static/help.js, the ? in the
header; Tigran, 2026-11-06): the page in both languages with every chapter,
the ? a link on every page with the script to load, the drawings one source,
the tour built by script alone, and what the offline copy keeps.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
DB = ROOT / "var" / "ub.db"
TEMPLATES = ROOT / "ubsite" / "templates"
STATIC = ROOT / "ubsite" / "static"
HELP_JS = (STATIC / "help.js").read_text(encoding="utf-8")
CHROME = (TEMPLATES / "_chrome.html").read_text(encoding="utf-8")
CHAPTERS = ["text", "index", "moving", "search", "listening", "notes", "translations", "settings",
            "offline", "quiz", "russian", "keys", "about"]


class Static(unittest.TestCase):
    def test_help_is_a_menu_in_the_shell_with_its_script(self):
        """A <details> since 2026-11-10, each item a link, so that it opens and
        goes somewhere with JavaScript off (a link to /help alone before)."""
        base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        head, _, _ = base.partition("</dialog>")
        self.assertRegex(head, r'<details class="help" data-src="\{\{ asset\(\'help\.js\'\) \}\}" data-repo="\{\{ repo \}\}">\n'
                               r'    <summary \{\{ ta\(\'aria-label\', \'Help\'\) \}\}')
        menu = head[head.index('<details class="help"'):head.index('</header>')]
        self.assertEqual(re.findall(r'<a (?:class="\w+" )?href="([^"]+)">', menu), ["/help", "/changelog", "/help#about"])
        # After the flags, the last thing in the header: the corner on both layouts.
        self.assertRegex(head, r'</details>\n</header>')
        self.assertLess(head.index('<span class="langs"'), head.index('<details class="help"'))
        # One dialog in the shell: offline/pages.py cut() takes the first </dialog>.
        self.assertEqual(base.count("<dialog"), 1)

    def test_tour_is_built_by_script_alone(self):
        for path in TEMPLATES.glob("*.html"):
            self.assertNotIn("tour-card", path.read_text(encoding="utf-8"), path.name)
        css = (STATIC / "ub.css").read_text(encoding="utf-8")
        self.assertIn(".tour-shield, .tour-ring, .tour-card", css[css.index("@media print"):])

    def test_steps_are_keyed_by_name_and_the_page_shows_them(self):
        steps = re.findall(r"\{ k: '(\w+)'", HELP_JS)
        self.assertEqual(steps, ["welcome", "chips", "cited", "search", "contents", "transport", "runhead",
                                 "listen", "notes", "gear", "cloud", "help"])
        page = (TEMPLATES / "help.html").read_text(encoding="utf-8")
        for k in re.findall(r"showme\('(\w+)'\)", page):
            self.assertIn(k, steps)
        for ch in re.findall(r"ch: '(\w+)'", HELP_JS):
            self.assertIn(ch, CHAPTERS)

    def test_script_names_its_words_as_literals(self):
        from ubsite import l10n
        keys = l10n.script_keys([HELP_JS])
        for k in ("tour:welcome", "tour:chips", "tour:help:title", "Skip the tour", "Open the book", "{a} of {b}|tour"):
            self.assertIn(k, keys)
        for k in keys:
            l10n.tr(k, **{s: 1 for s in re.findall(r"\{(\w+)", k)}) if "{" in k else l10n.tr(k) if not k.startswith("tour:welcome") else None
        self.assertNotIn('T("', HELP_JS)

    def test_player_icons_are_one_source(self):
        listen = (STATIC / "listen.js").read_text(encoding="utf-8")
        m = re.search(r"var ICON = \{(.*?)\};", listen, re.S)
        theirs = dict(re.findall(r"(\w+): '([^']+)'", m.group(1)))
        ours = dict(re.findall(r"'(\w+)': '([^']+)'", re.search(r"player_paths = \{(.*?)\}", CHROME, re.S).group(1)))
        self.assertEqual(ours, theirs)
        keep = re.search(r"none: '<svg[^>]*><path d=\"([^\"]+)\"", listen).group(1)
        self.assertIn(f'd="{keep}"', CHROME)

    def test_the_offline_copy_keeps_it(self):
        from offline import pack
        from ubsite import app
        self.assertIn("help.js", pack.ASSETS)
        self.assertIn("help.js", app.L10N_SCRIPTS)
        core = (STATIC / "offline-core.js").read_text(encoding="utf-8")
        self.assertIn("if (path === '/help') return { res: away(sh, T('The Help page is read online.')) };", core)
        pages = (ROOT / "offline" / "pages.py").read_text(encoding="utf-8")
        self.assertIn('"/help"', pages)

    def test_fonts_excuse_the_arrows_the_keys_draw(self):
        from build import fonts
        self.assertIn("←", fonts.ELSEWHERE)
        self.assertIn("→", fonts.ELSEWHERE)

    def test_integration_names_help_among_the_controls_that_stay(self):
        text = (ROOT / "INTEGRATION.md").read_text(encoding="utf-8")
        self.assertIn("Help", text[text.index("The reader's own controls stay"):][:300])


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class Pages(unittest.TestCase):
    def test_help_page_has_every_chapter_and_its_examples(self):
        from test_appendix_pages import get
        status, _, body = get("/help")
        self.assertEqual(status, 200)
        for ch in CHAPTERS:
            self.assertIn(f'<section id="{ch}">', body)
        self.assertIn("<title>Help</title>", body)     # English alone here; test_l10n holds the Russian
        self.assertIn('class="pill solid tourstart"', body)
        self.assertIn('data-tour="chips"', body)
        # The examples are the site's own markup on 11:7.
        self.assertIn('<ul class="chips">', body)
        self.assertIn('<aside class="blanket">', body)
        self.assertIn('data-k="1955"', body)
        self.assertIn('data-k="st"', body)
        self.assertIn('<aside class="note" id="fn11_7_3_0">', body)
        self.assertIn('<nav class="transport"', body)
        self.assertIn('<div class="player"', body)
        for have in ("none", "kept", "busy", "stale"):
            self.assertIn(f'data-have="{have}"', body)
        self.assertIn('/static/help.js?v=', body)
        # The ? is on this page too, and on the text's.
        self.assertIn('<details class="help" data-src=', body)
        self.assertNotIn("tour-card", body)

    def test_every_page_carries_the_help_menu_and_its_script(self):
        from test_appendix_pages import get
        from ubsite.app import REPO
        for path in ("/", "/101:4", "/i/humor", "/quiz", "/nothing"):
            body = get(path)[2]
            self.assertRegex(body, r'<details class="help" data-src="/static/help\.js\?v=\w+" data-repo="'
                                   + re.escape(REPO) + r'">\s*<summary aria-label="Help"[^>]* title="Help, What’s new, About"', path)
            for item in ('<a href="/help">', '<a class="whatsnew" href="/changelog">', '<a class="about" href="/help#about">'):
                self.assertIn(item, body, path)

    def test_help_is_a_misc_page_of_the_copy(self):
        from offline import pages
        con = sqlite3.connect(DB)
        self.assertIn("/help", pages.universe(con)["misc"])

    def test_stats_count_it_as_its_own_kind(self):
        from ubsite import stats
        self.assertEqual(stats.page_kind("/help"), ("help", ""))
        self.assertIn("help", stats.KIND_LABEL)


if __name__ == "__main__":
    unittest.main()
