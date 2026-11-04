"""data/uf/MANIFEST.tsv names every Foundation release sources.toml reads.

The zips are never committed (the repository is public; the Foundation's
permission is to show the text), so the manifest is what a fresh clone has to
go by: each zip's name, digest and text id must be what sources.toml holds the
build to, or the two would drift apart unnoticed.  Read from the files alone,
never through build.config, which needs the zips themselves.
"""

import csv
import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
UF = ROOT / "data" / "uf"


class Manifest(unittest.TestCase):
    def setUp(self):
        with open(ROOT / "sources.toml", "rb") as f:
            self.sources = {k: v for k, v in tomllib.load(f).items() if isinstance(v, dict) and "zip" in v}
        with open(UF / "MANIFEST.tsv", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        self.manifest = {r["file"]: r for r in rows}
        self.assertEqual(len(rows), len(self.manifest), "a zip is listed twice")

    def test_every_zip_is_in_data_uf_and_in_the_manifest(self):
        self.assertTrue(self.sources, "sources.toml names no zip")
        for key, cfg in self.sources.items():
            path = pathlib.PurePosixPath(cfg["zip"])
            self.assertEqual(path.parent.as_posix(), "data/uf", f"{key}: the zip lies outside data/uf/")
            self.assertIn(path.name, self.manifest, f"{key}: {path.name} is not in data/uf/MANIFEST.tsv")
            row = self.manifest[path.name]
            self.assertEqual(row["sha256"], cfg["sha256"], f"{key}: the manifest's digest is not sources.toml's")
            self.assertEqual(row["text_id"], cfg["text_id"], f"{key}: the manifest's text id is not sources.toml's")
            self.assertRegex(row["downloaded"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(row["from"].startswith("https://"), f"{key}: where it came from is not an address")

    def test_the_manifest_names_nothing_else(self):
        named = {pathlib.PurePosixPath(c["zip"]).name for c in self.sources.values()}
        self.assertEqual(set(self.manifest), named, "the manifest lists a zip sources.toml does not read")

    def test_the_zips_are_ignored(self):
        self.assertIn("data/uf/*.zip", (ROOT / ".gitignore").read_text().split())


if __name__ == "__main__":
    unittest.main()
