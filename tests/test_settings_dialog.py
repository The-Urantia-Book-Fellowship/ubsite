"""Settings is in tabs, one to each group of settings.py (Tigran, 2026-10-25).

Each tab is a button of type button, since in the dialog's form any other would
close it, and controls a panel that exists; the first tab is selected, and its
panel alone is shown.  The dialog keeps one size whichever is shown by CSS
(ub.css .panels), which a browser alone can check.  Rendered through the app as
ASGI, as test_appendix_pages does.  Skipped when var/ub.db has not been built.
"""

import re
import unittest

from test_appendix_pages import DB, ROOT, get
from ubsite import app, settings

RE_DIALOG = re.compile(r'<dialog class="settings".*?</dialog>', re.S)
RE_TAB = re.compile(r'<button type="button" role="tab" id="set-t-(\w+)" aria-controls="set-p-(\w+)"\s+'
                    r'aria-selected="(true|false)" tabindex="(0|-1)"[^>]*>([^<]+)</button>')
RE_PANEL = re.compile(r'<div class="panel( on)?[^"]*" role="tabpanel"\s+id="set-p-(\w+)"'
                      r' aria-labelledby="set-t-(\w+)"')


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Tabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, _, body = get("/101:4")
        assert status == 200, status
        cls.dialog = RE_DIALOG.search(body).group(0)

    def test_a_tab_to_each_group_in_order(self):
        tabs = RE_TAB.findall(self.dialog)
        groups = settings.groups([])
        self.assertEqual([(t[0], t[4]) for t in tabs], [(g["key"], g["legend"]) for g in groups])
        self.assertEqual([t[4] for t in tabs], ["Reading", "Show", "Translations", "Listening", "Offline"])
        self.assertEqual(self.dialog.count('role="tab"'), len(groups))
        for key, controls, _, _, _ in tabs:
            self.assertEqual(key, controls)

    def test_each_tab_controls_its_panel(self):
        tabs = [t[0] for t in RE_TAB.findall(self.dialog)]
        panels = RE_PANEL.findall(self.dialog)
        self.assertEqual([p[1] for p in panels], tabs)
        for _, pid, by in panels:
            self.assertEqual(pid, by)

    def test_the_first_is_selected_and_shown_alone(self):
        tabs = RE_TAB.findall(self.dialog)
        self.assertEqual([(t[2], t[3]) for t in tabs], [("true", "0")] + [("false", "-1")] * (len(tabs) - 1))
        self.assertEqual([p[0] for p in RE_PANEL.findall(self.dialog)], [" on"] + [""] * (len(tabs) - 1))

    def test_every_setting_is_in_its_groups_panel(self):
        bodies = re.split(r'<div class="panel[ "]', self.dialog)[1:]
        for g, body in zip(settings.groups([], app.translations()), bodies):
            want = list(dict.fromkeys(it["key"] for it in g["items"]))
            got = list(dict.fromkeys(re.findall(r'name="(\w+)"', body)))
            self.assertEqual(got, want, g["key"])

    def test_the_language_first_each_choice_in_its_own(self):
        """Interface language, first in Reading (Tigran, 2026-11-10): each
        choice written in its own language and marked so, never translated,
        and the row hidden until ub.js finds the site draws both."""
        reading = re.split(r'<div class="panel[ "]', self.dialog)[1]
        self.assertEqual(list(dict.fromkeys(re.findall(r'name="(\w+)"', reading)))[:4], ["lang", "theme", "uisize", "size"])
        self.assertIn('<div class="row langrow" hidden>', reading)
        self.assertRegex(reading, r'<label lang="en"><input type="radio" name="lang" value="en"><span>English</span></label>\s*'
                                  r'<label lang="ru"><input type="radio" name="lang" value="ru"><span>Русский</span></label>')
        self.assertNotIn("Английский", reading)
        self.assertNotIn("lang", [k[0] for k in settings.KEPT])
        self.assertIn("lang", settings.SPARED)

    def test_two_sizes_interface_first(self):
        keys = [s[0] for s in settings.READING]
        self.assertLess(keys.index("uisize"), keys.index("size"))
        sizes = {s[0]: [c[0] for c in s[4]] for s in settings.READING if s[0] in ("uisize", "size")}
        self.assertEqual(sizes["uisize"], sizes["size"])

    def test_four_steps_each_kept_as_its_size(self):
        """Smaller to Largest, 90 to 125%, and Standard 100% (Tigran,
        2026-11-16).  A choice is kept as its size, so that the names may
        move again, as they have twice, and no one's text with them; and the
        names kept before read as what they meant, Smaller 100% and Larger,
        with the Largest of before 2026-10-14, 125%."""
        css = (ROOT / "ubsite/static/ub.css").read_text()
        js = (ROOT / "ubsite/static/ub.js").read_text()
        for key in ("uisize", "size"):
            s = next(s for s in settings.READING if s[0] == key)
            self.assertEqual(s[3], "100", key)
            self.assertEqual([(c[0], c[2], c[3]) for c in s[4]],
                             [("90", "Smaller", "a1"), ("100", "Standard", "a2"),
                              ("112.5", "Larger", "a3"), ("125", "Largest", "a4")], key)
        self.assertIn(":root { font-size: 100%; --ui: calc(100 / 112.5); --tx: calc(100 / 112.5); }", css)
        self.assertIn(':root[data-uisize="90"] { font-size: 90%; --ui: calc(90 / 112.5); }', css)
        self.assertIn(':root[data-uisize="112.5"] { font-size: 112.5%; --ui: 1; }', css)
        self.assertIn(':root:is([data-uisize="125"], [data-uisize="larger"]) { font-size: 125%; --ui: calc(125 / 112.5); }', css)
        self.assertIn(':root[data-size="90"] { --tx: calc(90 / 112.5); }', css)
        self.assertIn(':root:is([data-size="125"], [data-size="larger"], [data-size="largest"]) { --tx: calc(125 / 112.5); }', css)
        # No rule for a name that meant 100%: it is the default.
        self.assertNotIn('size="smaller"', css)
        self.assertNotIn('size="standard"', css)
        for cls in ("a1", "a2", "a3", "a4"):
            self.assertIn(f".seg .{cls} span {{ font-size:", css)
        self.assertIn("var was = { smaller: '100', standard: '112.5', larger: '125', largest: '125' };", js)
        self.assertIn("['size', 'uisize'].forEach(function (k) { if (was.hasOwnProperty(s[k])) s[k] = was[s[k]]; });", js)

    def test_no_fieldsets_left(self):
        self.assertNotIn("<fieldset", self.dialog)
        self.assertNotIn("<legend", self.dialog)


if __name__ == "__main__":
    unittest.main()
