"""The recordings' compact copy (2026-11-22): Opus, mono, in WebM.

Tigran heard the samples on 2026-11-21 and ruled: Merritt Horn at 16 kbps,
Григорий Войнер at 14, one set for every reader, streamed and kept offline,
with no choice offered; the MP3s stay on the server for a browser that cannot
play Opus and for pages from before; and a reader who kept the MP3s keeps
them.  These hold the parts that need no browser: the config, the build's
refusals (made on a scratch directory), the database, the route against the
files on disk, the page's word that a voice has a copy, the listen counter's
names, and the scripts' one test of the browser.  tools/offline_e2e.py and
tools/audio/seek_e2e.py drive the rest in Chrome.
"""

import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from test_offline import DB, ROOT, call

sys.path.insert(0, str(ROOT))
from build import audio, config, problems  # noqa: E402

STATIC = ROOT / "ubsite" / "static"


class Config(unittest.TestCase):
    def test_each_human_reading_has_its_rate_and_its_directory(self):
        a = config.audio()
        self.assertEqual({k: v["compact"] and (v["compact"]["kbps"], v["compact"]["root"]) for k, v in a.items()},
                         {"mh": (16, "var/audio/compact/mh"), "voyner": (14, "var/audio/compact/voyner"), "ai": None})

    def test_a_copy_is_made_inside_the_project(self):
        self.assertEqual(config._compact({"kbps": 16, "path": "var/audio/compact/x"})["path"],
                         (ROOT / "var/audio/compact/x").resolve())
        for bad in ("/Audio/Urantia/x", "../elsewhere", "var/../../x"):
            with self.assertRaises(SystemExit):
                config._compact({"kbps": 16, "path": bad})

    def test_the_name_is_the_file_s_with_webm_for_mp3(self):
        self.assertEqual(audio.compact_name("paper133/P133_02.mp3"), "paper133/P133_02.webm")
        self.assertEqual(audio.compact_name("139-09-10.mp3"), "139-09-10.webm")
        self.assertIsNone(audio.compact_name("x.wav"))


class Refusals(unittest.TestCase):
    """build/audio.py _compact, on a directory and a list made here."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        self.data, self.dir = t / "data", t / "copy"
        self.data.mkdir()
        (self.dir / "paper001").mkdir(parents=True)
        self.src = {"compact": {"kbps": 16, "root": "var/audio/compact/t", "path": self.dir}}
        # Two masters the site uses, and one it leaves out.
        self.listed = {"paper001/P001_00.mp3": (1000, 60000, "a" * 64), "paper001/P001_01.mp3": (2000, 90000, "b" * 64),
                       "paper001/P001_99.mp3": (10, 1000, "c" * 64)}
        self.claimed = {"paper001/P001_00.mp3": (1, None), "paper001/P001_01.mp3": (2, None)}
        self.rows = [["paper001/P001_00.webm", 100, 60010, "d" * 64, "a" * 64],
                     ["paper001/P001_01.webm", 200, 89950, "e" * 64, "b" * 64]]

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self):
        lines = ["# made here", "file\tbytes\tduration_ms\tsha256\tmaster_sha256"]
        lines += ["\t".join(map(str, r)) for r in self.rows]
        (self.data / "t-compact.tsv").write_text("\n".join(lines) + "\n")
        for name, b, *_ in self.rows:
            if not (self.dir / name).exists():
                (self.dir / name).write_bytes(bytes(b))
        report = problems.Report()
        with mock.patch.object(audio, "DATA", self.data):
            out = audio._compact("t", self.src, self.listed, self.claimed, report)
        return out, sorted((p.code, p.where) for p in report.problems)

    def test_all_well(self):
        out, said = self.run_it()
        self.assertEqual(said, [])
        self.assertEqual(out["paper001/P001_01.mp3"], ("paper001/P001_01.webm", 200, 89950, "e" * 64, "b" * 64))
        self.assertEqual(set(out), set(self.claimed))

    def test_no_compact_copy_in_the_config_is_none(self):
        self.src = {"compact": None}
        self.assertEqual(self.run_it(), ({}, []))

    def test_a_list_not_made(self):
        report = problems.Report()
        with mock.patch.object(audio, "DATA", self.data):
            self.assertEqual(audio._compact("t", self.src, self.listed, self.claimed, report), {})
        self.assertEqual([p.code for p in report.problems], ["audio-compact-unmade"])

    def test_a_copy_of_a_master_since_changed(self):
        self.rows[1][4] = "f" * 64
        out, said = self.run_it()
        self.assertEqual(said, [("audio-compact-stale", "paper001/P001_01.webm")])
        self.assertNotIn("paper001/P001_01.mp3", out)

    def test_a_copy_of_another_length(self):
        self.rows[0][2] = 60081
        self.assertEqual(self.run_it()[1], [("audio-compact-length", "paper001/P001_00.webm")])

    def test_a_copy_missing_unlisted_changed_or_unused(self):
        (self.dir / "paper001" / "P001_02.webm").write_bytes(b"x")            # on the disk, in no list
        self.rows.append(["paper001/P001_99.webm", 5, 1000, "9" * 64, "c" * 64])  # of a file left out
        self.rows[1][1] = 201                                                  # the list says 201, the disk 200
        (self.dir / "paper001" / "P001_01.webm").write_bytes(bytes(200))
        self.assertEqual(self.run_it()[1], [("audio-compact-changed", "paper001/P001_01.webm"),
                                            ("audio-compact-unlisted", "paper001/P001_02.webm"),
                                            ("audio-compact-unused", "paper001/P001_99.webm")])
        self.rows = self.rows[:1]
        (self.dir / "paper001" / "P001_01.webm").unlink()
        (self.dir / "paper001" / "P001_02.webm").unlink()
        (self.dir / "paper001" / "P001_99.webm").unlink()
        self.assertEqual(self.run_it()[1], [("audio-compact-missing", "paper001/P001_01.mp3")])


@unittest.skipUnless(DB.exists(), "var/ub.db not built")
class Stored(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cls.con.row_factory = sqlite3.Row

    def test_every_file_of_both_readings_has_its_copy(self):
        for key, n in (("mh", 1627), ("voyner", 1624)):
            self.assertEqual(self.con.execute(
                "SELECT COUNT(*) FROM audio_compact c JOIN audio_file f ON f.id = c.file_id"
                " JOIN audio_source s ON s.id = f.source_id WHERE s.key = ?", (key,)).fetchone()[0], n, key)
        self.assertEqual(dict(self.con.execute("SELECT key, compact_root FROM audio_source")),
                         {"mh": "var/audio/compact/mh", "voyner": "var/audio/compact/voyner"}
                         | ({"ai": None} if self.con.execute("SELECT 1 FROM audio_source WHERE key = 'ai'").fetchone() else {}))

    def test_the_lists_are_the_database_s(self):
        # data/audio/<key>-compact.tsv, committed, is what the build loaded.
        for key in ("mh", "voyner"):
            _, head, rows = audio._tsv(audio.DATA / f"{key}-compact.tsv")
            self.assertEqual(head, ["file", "bytes", "duration_ms", "sha256", "master_sha256"])
            stored = {r["name"]: (r["bytes"], r["duration_ms"], r["sha256"]) for r in self.con.execute(
                "SELECT c.* FROM audio_compact c JOIN audio_file f ON f.id = c.file_id"
                " JOIN audio_source s ON s.id = f.source_id WHERE s.key = ?", (key,))}
            self.assertEqual(stored, {f: (int(b), int(d), sha) for f, b, d, sha, _m in rows})

    def test_a_page_says_which_voices_have_a_copy_and_keeps_the_files_addresses(self):
        from ubsite import app
        a = app.section_audio(self.con, self.con.execute(
            "SELECT id FROM section WHERE paper_n = 1 AND n = 1").fetchone()[0])
        self.assertTrue(a["mh"]["compact"] and a["voyner"]["compact"])
        self.assertTrue(all(u.endswith(".mp3") for v in a.values() for u in v["files"]))
        self.assertNotIn("compact", a.get("ai", {}))
        # The whole paper's page passes it on (app.py whole_audio).
        texts = [{"section": {"paper_n": 1, "n": 1}, "audio": a}]
        self.assertTrue(app.whole_audio(texts)["voyner"]["compact"])

    def test_the_listen_counter_knows_a_copy_s_section(self):
        from ubsite import stats
        names = stats.audio_sections(self.con)
        self.assertEqual((names["paper001/P001_02.mp3"], names["paper001/P001_02.webm"]), ("1:2", "1:2"))
        self.assertEqual((names["139-09-10.mp3"], names["139-09-10.webm"]), ("139:9", "139:9"))


@unittest.skipUnless(DB.exists() and all(v["compact"]["path"].is_dir() for k, v in config.audio().items()
                                         if v["compact"]), "the compact copy is not on this machine")
class Served(unittest.TestCase):
    def test_a_copy_is_sent_whole_and_by_range_as_listed(self):
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        for key, name in (("mh", "paper001/P001_01.webm"), ("voyner", "139-09-10.webm")):
            b, sha = con.execute("SELECT c.bytes, c.sha256 FROM audio_compact c JOIN audio_file f ON f.id = c.file_id"
                                 " JOIN audio_source s ON s.id = f.source_id WHERE s.key = ? AND c.name = ?",
                                 (key, name)).fetchone()
            url = f"/audio/{key}/{name}"
            status, h, whole = call(url)
            self.assertEqual((status, len(whole), h["content-type"]), (200, b, "audio/webm"), url)
            self.assertEqual(hashlib.sha256(whole).hexdigest(), sha)
            self.assertEqual(whole, (config.audio()[key]["compact"]["path"] / name).read_bytes())
            self.assertEqual(h["cache-control"], "public, max-age=31536000, immutable")
            for lo, hi in ((0, 99), (b - 10, b + 10), (b // 2, b // 2 + 5000)):
                status, h, part = call(url, headers={"range": f"bytes={lo}-{hi}"})
                self.assertEqual((status, part), (206, whole[lo:min(hi, b - 1) + 1]), (url, lo, hi))
            # The MP3 at its own address as before.
            self.assertEqual(call(url[:-5] + ".mp3", headers={"range": "bytes=0-9"})[1]["content-type"], "audio/mpeg")

    def test_the_offline_list_gives_each_copy_as_sent(self):
        d = json.loads(call("/offline/audio/voyner.json")[2])
        name, _b, _h, cb, ch = d["papers"][139]["files"][-1]
        self.assertEqual(name, "139-12.mp3")
        whole = call("/audio/voyner/139-12.webm")[2]
        self.assertEqual((len(whole), hashlib.sha256(whole).hexdigest()[:16]), (cb, ch))


class Scripts(unittest.TestCase):
    TYPE = """canPlayType('audio/webm; codecs="opus"')"""

    def test_the_player_and_the_offline_tab_ask_the_browser_alike(self):
        # One test of the browser, the same in both, so that a browser keeps
        # the form it plays.
        for f in ("listen.js", "offline.js"):
            self.assertIn(self.TYPE, (STATIC / f).read_text(), f)

    def test_the_player_asks_for_the_copy_where_the_voice_has_one(self):
        src = (STATIC / "listen.js").read_text()
        self.assertIn("return OPUS && v.compact ? u.replace(/\\.mp3$/, '.webm') : u;", src)
        self.assertIn("audio.src = srcOf(V, file);", src)
        self.assertNotRegex(src, r"audio\.src = V\.files")

    def test_no_function_is_declared_twice(self):
        # CLAUDE.md trap 42: in one script a second declaration replaces the
        # first, with no error.  The worker's `wanted`, the chunks a copy
        # needs, was replaced by the compact copy's first draft of a function
        # of that name (2026-11-22), and every download stopped at once.
        for f in ("sw.js", "listen.js", "offline.js", "ub.js"):
            names = re.findall(r"^\s*function ([A-Za-z_$][\w$]*)", (STATIC / f).read_text(), re.M)
            self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [], f)

    def test_the_worker_names_a_copy_as_the_app_does(self):
        src = (STATIC / "sw.js").read_text()
        self.assertIn("path.slice(0, -4) + '.webm'", src)
        self.assertIn("e.data.form === 'webm' ? 'webm' : null", src)
        # No form of a file hard-coded where a kept file is answered or put.
        self.assertEqual(re.findall(r"'Content-Type': 'audio/mpeg'", src), [])


if __name__ == "__main__":
    unittest.main()
