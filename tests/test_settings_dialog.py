"""Settings is in tabs, one to each group of settings.py (Tigran, 2026-10-25).

Each tab is a button of type button, since in the dialog's form any other would
close it, and controls a panel that exists; the first tab is selected, and its
panel alone is shown.  The dialog keeps one size whichever is shown by CSS
(ub.css .panels), which a browser alone can check.  Rendered through the app as
ASGI, as test_appendix_pages does.  Skipped when var/ub.db has not been built.
"""

import re
import unittest

from test_appendix_pages import DB, get
from ubsite import settings

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
        self.assertEqual([t[4] for t in tabs], ["Reading", "Show", "Listening", "Offline"])
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
        for g, body in zip(settings.groups([]), bodies):
            want = list(dict.fromkeys(it["key"] for it in g["items"]))
            got = list(dict.fromkeys(re.findall(r'name="(\w+)"', body)))
            self.assertEqual(got, want, g["key"])

    def test_no_fieldsets_left(self):
        self.assertNotIn("<fieldset", self.dialog)
        self.assertNotIn("<legend", self.dialog)


if __name__ == "__main__":
    unittest.main()
