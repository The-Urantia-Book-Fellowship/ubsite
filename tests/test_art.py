"""The home page's part pictures (Tigran's four, 2026-11-17; data/art/,
tools/make_art.py; DECISIONS.md, The home page): each of the four part cards
shows its picture, made at two widths, of which the browser takes the one its
screen needs.  The masters are 3 MB each and not committed; what is served is,
and data/art/MANIFEST.tsv names both by SHA-256.

These hold the static facts: the served files are the manifest's, and the
masters too where they are present; every card names its picture at each width,
with the hash of its content and the size the file has; the offline copy is to
hold every one (offline/pack.py ART); and the stylesheet draws the card as the
tests of a browser found it right (tools/art_e2e.py, which is not a gate).
Rendered through the app as ASGI, as test_appendix_pages does.
"""

import hashlib
import importlib.util
import re
import unittest

from test_appendix_pages import DB, ROOT, get

STATIC = ROOT / "ubsite" / "static"
MANIFEST = ROOT / "data" / "art" / "MANIFEST.tsv"
CSS = (STATIC / "ub.css").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location("make_art", ROOT / "tools" / "make_art.py")
make_art = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_art)


def rows() -> list[dict]:
    lines = [l for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


class TheFiles(unittest.TestCase):
    def test_the_manifest_names_four_masters_and_each_at_every_width(self):
        got = rows()
        masters = [r for r in got if r["from"] == "-"]
        self.assertEqual([r["file"] for r in masters], [f"data/art/{n}" for n in make_art.PARTS.values()])
        served = [r["file"] for r in got if r["from"] != "-"]
        self.assertEqual(served, [f"ubsite/static/{make_art.served(n, w)}"
                                  for n in make_art.PARTS for w in make_art.WIDTHS])
        for r in masters:
            self.assertEqual((r["width"], r["height"]), ("2752", "1536"), r["file"])

    def test_the_served_files_are_the_manifest_s(self):
        """A master changed and the tool not run, or a served file put there by
        hand, fails here: each file's bytes, size and dimensions are the
        manifest's, and nothing else is in the directory."""
        want = {r["file"]: r for r in rows() if r["from"] != "-"}
        for rel, r in want.items():
            with self.subTest(file=rel):
                data = (ROOT / rel).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), r["sha256"])
                self.assertEqual(len(data), int(r["bytes"]))
                self.assertEqual(make_art.webp_size(data), (int(r["width"]), int(r["height"])))
                self.assertEqual(r["width"], re.search(r"-(\d+)\.webp$", rel).group(1))
        self.assertEqual(sorted(p.relative_to(ROOT).as_posix() for p in (STATIC / "art").iterdir()), sorted(want))

    def test_the_masters_where_present_are_the_manifest_s(self):
        """They are not committed (.gitignore), so a clone has none; where one
        is, it is the file the served ones were made from."""
        for r in rows():
            path = ROOT / r["file"]
            if r["from"] == "-" and path.exists():
                with self.subTest(file=r["file"]):
                    data = path.read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), r["sha256"])
                    self.assertEqual(make_art.jpeg_size(data), (int(r["width"]), int(r["height"])))
        self.assertIn("data/art/*.jpeg", (ROOT / ".gitignore").read_text())

    def test_no_reader_is_sent_megabytes(self):
        # 0.47 MB at measurement, 2026-11-18, for all eight; a master is 3 MB.
        sizes = [int(r["bytes"]) for r in rows() if r["from"] != "-"]
        self.assertLess(sum(sizes), 800_000)
        self.assertLess(max(sizes), 160_000)

    def test_the_offline_copy_is_to_hold_every_one(self):
        from offline import pack
        self.assertEqual(pack.ART, sorted(make_art.served(n, w) for n in make_art.PARTS for w in make_art.WIDTHS))


@unittest.skipUnless(DB.exists(), "var/ub.db has not been built")
class TheCards(unittest.TestCase):
    def setUp(self):
        self.raw = get("/", raw=True)[2]
        self.toc = re.search(r'<ol class="front-toc">.*?</ol>', self.raw, re.S).group(0)

    def test_every_part_s_card_has_its_picture_at_both_widths(self):
        cards = re.findall(r'<a class="fpart fp(\d)" href="/part/(\d)">\s*(<img [^>]*>)', self.toc)
        self.assertEqual([(a, b) for a, b, _ in cards], [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")])
        sizes = {r["file"]: (r["width"], r["height"]) for r in rows()}
        for n, _, img in cards:
            with self.subTest(part=n):
                def address(w):
                    name = make_art.served(int(n), w)
                    return f"/static/{name}?v={hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]}"
                small, large = (address(w) for w in make_art.WIDTHS)
                self.assertIn(f'src="{small}"', img)
                self.assertIn(f'srcset="{small} 640w, {large} 1280w"', img)
                # The larger file's own size, so that the box is the picture's
                # shape before it arrives; and no words of its own, the link's
                # being the card's name.
                w, h = sizes[f"ubsite/static/{make_art.served(int(n), 1280)}"]
                self.assertIn(f'width="{w}" height="{h}"', img)
                self.assertIn('alt=""', img)
                self.assertRegex(img, r'sizes="\(max-width: 40rem\) calc\(100vw - 2rem\), ')

    def test_the_words_are_the_page_s_in_a_shade_of_their_own(self):
        caps = re.findall(r'<span class="fcap">(.*?)</span></a>', self.toc, re.S)
        self.assertEqual(len(caps), 4)
        for cap in caps:
            self.assertRegex(cap, r'^<span class="pn">.*?</span>\s*<span class="lbl">.*?</span>\s*<span class="range')
        # The Foreword's own row, shown with Foreword in Part I off, has no picture.
        row = re.search(r'<li class="foreword fwout">.*?</li>', self.toc, re.S).group(0)
        self.assertNotIn("<img", row)
        self.assertNotIn("fpart", row)

    def test_only_the_home_page_has_them(self):
        for url in ("/part/1", "/read", "/1:1", "/help"):
            self.assertNotIn("/static/art/", get(url, raw=True)[2], url)


class TheStylesheet(unittest.TestCase):
    def test_the_card_is_its_picture_s_shape_and_clips_nothing(self):
        rule = re.search(r"\.front-toc \.fpart \{([^}]*)\}", CSS).group(1)
        self.assertIn("aspect-ratio: 16 / 9;", rule)
        self.assertIn("isolation: isolate;", rule)
        # A box that clips has no least height of its content's, and would
        # cut a long name's first line.
        self.assertNotIn("overflow", rule)
        self.assertRegex(CSS, r"\.fpart \.fpic \{[^}]*z-index: -1;[^}]*object-fit: cover;")

    def test_each_part_has_a_ground_under_its_picture(self):
        for n in make_art.PARTS:
            self.assertRegex(CSS, r"\.fp%d \{ --fground: #[0-9a-f]{6}; \}" % n)

    def test_the_words_shade_is_as_tall_as_the_words(self):
        rule = re.search(r"\.fpart \.fcap \{([^}]*)\}", CSS).group(1)
        self.assertIn("linear-gradient(to top,", rule)
        self.assertIn("calc(100% - 2.75rem)", rule)
        self.assertIn("padding: 2.75rem 1rem", rule)


if __name__ == "__main__":
    unittest.main()
