"""Privacy and Terms (templates/privacy.html, terms.html; Tigran, 2026-11-18,
with accounts): two pages of the server's and of the offline copy, in both
languages, linked from the footer of every page, which they show as the home
page does.  Each says when it last changed, the same day in each language.
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

from test_appendix_pages import get  # noqa: E402
from ubsite import app as site, l10n  # noqa: E402

PAGES = {"/privacy": ("Privacy", "privacy:lead"), "/terms": ("Terms of use", "terms:lead")}
# When each last changed, as its lead says it: moved with the page's words.
CHANGED = {"privacy:lead": "2026-11-24", "terms:lead": "2026-11-18"}


class Words(unittest.TestCase):
    def test_each_says_when_it_changed_in_both_languages(self):
        for key, iso in CHANGED.items():
            day, entry = l10n.date(iso), l10n.tr(key)
            with self.subTest(key=key):
                self.assertIn(str(day["en"]), str(entry["en"]))
                self.assertIn(str(day["ru"]), str(entry["ru"]))

    def test_privacy_says_where_signing_in_is_offered_and_what_then_leaves_the_browser(self):
        """Held to settings.py: the hosts the page names as having accounts
        and as having none are the hosts that do and do not; and what it says
        is kept with an account is what follows one (account.py KINDS)."""
        from ubsite import account, settings
        first, browser = (str(l10n.tr(k)["en"]) for k in ("privacy:account:1", "privacy:browser"))
        live = [h for h in settings.ACCOUNT_HOSTS if h != "localhost"]
        self.assertEqual(live, ["ubsite.sigmaai.au"])
        self.assertIn("offered at ubsite.sigmaai.au", first)
        self.assertIn("ubsite.ddns.net has no accounts", first)
        self.assertNotIn("being added", first)
        self.assertIn("not sent to the server, unless you sign in: your settings, the place you last read and your "
                      "bookmarks are then kept with your account too", browser)
        self.assertEqual(account.KINDS, ("set", "place", "mark"))
        for k in ("privacy:account:1", "privacy:browser"):
            self.assertTrue(str(l10n.tr(k)["ru"]).strip())

    def test_the_footer_links_them_in_every_page(self):
        base = (ROOT / "ubsite" / "templates" / "base.html").read_text(encoding="utf-8")
        footer = base[base.index("<footer>"):base.index("</footer>")]
        self.assertIn("<a href=\"/privacy\">{{ t('Privacy') }}</a>", footer)
        self.assertIn("<a href=\"/terms\">{{ t('Terms') }}</a>", footer)

    def test_the_offline_copy_keeps_them_and_an_older_one_says_so(self):
        pages = (ROOT / "offline" / "pages.py").read_text(encoding="utf-8")
        self.assertIn('"/privacy", "/terms"', pages)
        core = (ROOT / "ubsite" / "static" / "offline-core.js").read_text(encoding="utf-8")
        self.assertIn("if (path === '/privacy' || path === '/terms') return { res: away(sh, T('This page is read online.')) };",
                      core)


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Pages(unittest.TestCase):
    def test_each_is_a_page_in_both_languages_with_the_footer(self):
        for url, (title, lead) in PAGES.items():
            status, _, body = get(url, raw=True)
            with self.subTest(url=url):
                self.assertEqual(status, 200)
                self.assertIn('<main class="prose legal">', body)
                self.assertRegex(body, r"<title[^>]*>%s</title>" % re.escape(title))
                self.assertIn(f"<h1><x-en>{title}</x-en>", body)
                self.assertIn(str(l10n.tr(lead)["ru"]), body)
                # A word of the catalog for every sentence: none left in one language.
                main = body[body.index("<main"):body.index("</main>")]
                self.assertEqual(main.count("<x-en>"), main.count('<x-ru lang="ru">'))
                bare = re.sub(r"<x-(en|ru)\b.*?</x-\1>", "", main, flags=re.S)
                self.assertNotRegex(re.sub(r"<[^>]+>", "", bare), r"\w")

    def test_whom_to_write_to_is_named_on_both(self):
        for url in PAGES:
            body = get(url)[2]
            with self.subTest(url=url):
                self.assertIn(f'<a href="mailto:{site.CONTACT}">{site.CONTACT}</a>', body)
                self.assertNotIn("{mail}", body)

    def test_the_pages_link_each_other_and_what_they_name(self):
        terms = get("/terms")[2]
        self.assertIn('<a href="/privacy">Privacy</a>', terms)
        self.assertIn('<a href="/api">text API</a>', terms)
        self.assertIn('href="https://creativecommons.org/licenses/by-nc-sa/4.0/"', terms)
        privacy = get("/privacy")[2]
        self.assertIn('<a href="/changelog">Changelog</a>', privacy)

    def test_what_privacy_says_of_the_counter_is_what_it_keeps(self):
        """The page names the place database the counter reads, and the
        counter's table has no column for an address."""
        from ubsite import visits
        self.assertIn("dbip", visits.GEOIP.name)
        self.assertIn("DB-IP", get("/privacy")[2])
        con = sqlite3.connect(":memory:")
        con.executescript((ROOT / "ubsite" / "visits.sql").read_text(encoding="utf-8"))
        cols = {r[1] for r in con.execute("PRAGMA table_info(view)")}
        self.assertEqual(cols, {"id", "ts", "day", "visitor", "path", "query", "status", "referrer", "agent_id",
                                "place_id", "lang", "via", "hits"})

    def test_the_copy_holds_them(self):
        from offline import pages
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        misc = pages.universe(con)["misc"]
        for url in PAGES:
            self.assertIn(url, misc)


if __name__ == "__main__":
    unittest.main()
