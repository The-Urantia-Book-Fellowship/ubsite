"""Which reading the alignment tools work on, and in what language.

    make align VOICE=voyner        # --voice voyner; with none, Merritt Horn's (mh)

A reading is a key of sources.toml's [audio.<key>], read through
build/config.py like every source.  Each has its own transcripts,
var/align/<key>/, and its own cuts, data/audio/<key>.tsv.  One that reads a
translation (sources.toml `translation`) is heard in that translation's
language (data/translations.toml `lang`) and matched to its spoken text,
`tr_speech`; one that reads none, in English, to `speech`.  One that read
its translation as it stood before today (`edition`) is matched to the
paragraphs' words as they were (tools/align/edition.py).

Stdlib only: it runs in the aligner's venv and in the site's.
"""

from __future__ import annotations

import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
VAR = ROOT / "var" / "align"


class Voice:
    def __init__(self, key: str = "mh"):
        from build import config
        sources = config.audio()
        if key not in sources:
            raise SystemExit(f"no [audio.{key}] in the config; there are: {', '.join(sources)}")
        self.key = key
        self.src = sources[key]
        self.path = self.src["path"]
        self.translation = self.src["translation"]
        self.lang = "en"
        if self.translation:
            with open(ROOT / "data" / "translations.toml", "rb") as fh:
                self.lang = tomllib.load(fh)[self.translation]["lang"]
        self.words = VAR / key                      # Whisper's words, a JSON to a file
        # The pauses, measured once a file.  Merritt Horn's are where they were
        # before there was a second reading, and tools/align/rebase.py empties
        # that directory, so another's are beside it, not in it.
        self.silence = VAR / "silence" if key == "mh" else VAR / f"silence-{key}"
        self.tsv = ROOT / "data" / "audio" / f"{key}.tsv"
        self.partial = VAR / f"{key}-partial.tsv"   # while Whisper is still running
        self.review = VAR / f"{key}-review.tsv"

    def files(self) -> list[pathlib.Path]:
        return sorted(self.path.glob(self.src["glob"]))

    def name(self, path: pathlib.Path) -> str:
        """A file as the lists name it: its path under the reading's directory."""
        return path.relative_to(self.path).as_posix()

    def cuts(self) -> pathlib.Path:
        return self.tsv if self.tsv.exists() else self.partial

    def heard(self, rows=None) -> dict[str, list[str]]:
        """{ref: the words heard in a paragraph's segment, as tokens}, by the
        cuts given, rows of (ref, file, start_ms, end_ms, ...), or with none
        by those on record; {} where there are none yet."""
        import json
        from tools.align.align import tokens
        if rows is None:
            tsv = self.cuts()
            rows = ([l.split("\t") for l in tsv.read_text().splitlines() if l[:1].isdigit()]
                    if tsv.exists() else [])
        out, words = {}, {}
        for ref, name, a, b, *_rest in rows:
            if "." not in ref:
                continue
            if name not in words:
                at = self.words / (pathlib.Path(name).stem + ".json")
                words[name] = json.loads(at.read_text())["words"] if at.exists() else []
            a, b = int(a) / 1000, int(b) / 1000
            out[ref] = tokens(" ".join(w[2] for w in words[name] if a <= w[0] < b), self.lang)
        return out

    def text(self, con, heard: dict[str, list[str]] | None = None) -> dict[str, str]:
        """{ref: what is spoken}: a paragraph by its ref, a section's heading
        by the section's, "1:2".  The build's spoken text (build/speech.py);
        and where the reading read its translation as it stood before today
        (the config's `edition`), each paragraph's words as they were at
        whichever of the commits named is nearer what was heard in it
        (tools/align/edition.py), the headings today's.  `heard` is what was
        heard, by paragraph; with none given, by the cuts on record."""
        if self.translation:
            rows = con.execute(
                "SELECT COALESCE(p.ref, x.paper_n || ':' || x.n), s.text FROM tr_speech s"
                " JOIN section x ON x.id = s.section_id LEFT JOIN paragraph p ON p.id = s.paragraph_id"
                " WHERE s.translation = ?", (self.translation,))
        else:
            rows = con.execute(
                "SELECT COALESCE(p.ref, x.paper_n || ':' || x.n), s.text FROM speech s"
                " JOIN section x ON x.id = s.section_id LEFT JOIN paragraph p ON p.id = s.paragraph_id")
        out = dict(rows)
        if self.src.get("edition"):
            from tools.align import edition
            out.update(edition.read(self, con, self.heard() if heard is None else heard)[0])
        return out

    def word_counts(self, con) -> dict[str, int]:
        """{ref: words}, of the text the reading reads, as the gate counts them
        (build/checks/check_audio.py)."""
        if self.translation:
            return dict(con.execute(
                "SELECT p.ref, LENGTH(t.text) - LENGTH(REPLACE(t.text, ' ', '')) + 1"
                " FROM tr_paragraph t JOIN paragraph p ON p.id = t.paragraph_id"
                " WHERE t.translation = ?", (self.translation,)))
        return dict(con.execute("SELECT ref, word_count FROM paragraph"))


def take(argv: list[str]) -> tuple[Voice, list[str]]:
    """The voice `--voice KEY` names, Merritt Horn's with none, and the rest."""
    argv = list(argv)
    key = "mh"
    if "--voice" in argv:
        i = argv.index("--voice")
        key = argv[i + 1]
        del argv[i:i + 2]
    return Voice(key), argv
