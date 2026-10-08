"""The recordings -> audio_source, audio_file, audio_segment.

A recording directory is a master like the three repos: it is listed and its
files are measured, never opened for writing -- and here not even opened, since
everything this needs about a file is in data/audio/<key>-files.tsv, which
tools/audio/manifest.py made by hashing every file once.  The build checks the
directory against that list by size on every run, which is cheap, and fails on
a file the list does not name -- a source nothing claimed (CLAUDE.md §6).

Merritt Horn's reading (key 'mh') is one MP3 per section.  The naming rule
P<ppp>_<ss>.mp3 claims nearly all of them; data/audio/mh-overrides.tsv names
the three that do not follow it.  Until data/audio/mh.tsv exists -- the
aligner's output, paragraph by paragraph -- each file is one segment, played
from its start to its end.

The AI voice (key 'ai') is made here by tools/tts/book.py, one MP3 per section
under var/audio/ai/, and data/audio/ai.tsv and ai-files.tsv are its output, as
mh.tsv is the aligner's.  It is checked against its list the same way.
"""

from __future__ import annotations

import pathlib
import re

from . import config

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "audio"
# A paragraph of LOW_WORDS or more of which less than LOW_MATCH was heard, even
# after the aligner's unbatched second pass, is a place where Merritt Horn's
# reading and today's text differ -- a sentence he did not read, or one added
# since.  check_audio holds that set to data/audio/mh-low-match.tsv, exactly.
LOW_WORDS, LOW_MATCH = 10, 0.6
RE_MH = re.compile(r"^paper(\d{3})/P(\d{3})_(\d{2})(?:-(\d{2}))?\.mp3$")
RE_REF = re.compile(r"^(\d+):(\d+)(?:\.(\d+))?$")


def _tsv(path: pathlib.Path) -> tuple[list[str], list[str], list[list[str]]]:
    """(comments, header, rows) of a tab-separated file with # comment lines."""
    comments, rows = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            comments.append(line[1:].strip())
        elif line.strip():
            rows.append(line.split("\t"))
    return comments, rows[0], rows[1:]


def load_audio(con, report) -> dict[str, int]:
    """Load every recording config.audio() names.  Returns counts for `stat`."""
    stats = {}
    sources = config.audio()
    if "mh" in sources:
        stats.update(_load_mh(con, sources["mh"], 1, report))
    if "ai" in sources:
        stats.update(_load_ai(con, sources["ai"], 2, report))
    return stats


def _files_on_disk(key: str, src, files: dict, report) -> bool:
    """The directory against data/audio/<key>-files.tsv, by size: a file it
    does not list, or lists and is not there, is a hard failure."""
    if not src["present"]:
        report.hard("audio-absent", str(src["path"]), "the recordings are not where the config says")
        return False
    on_disk = {p.relative_to(src["path"]).as_posix(): p.stat().st_size
               for p in src["path"].glob("paper*/*.mp3")}
    for name in sorted(on_disk.keys() - files.keys()):
        report.hard("audio-unlisted", name, f"an MP3 data/audio/{key}-files.tsv does not list")
    for name in sorted(files.keys() - on_disk.keys()):
        report.hard("audio-missing", name, f"listed in {key}-files.tsv but not on disk")
    for name in sorted(files.keys() & on_disk.keys()):
        if files[name][0] != on_disk[name]:
            report.hard("audio-changed", name, f"{on_disk[name]:,} bytes on disk,"
                        f" {files[name][0]:,} listed")
    return True


def _load_ai(con, src, source_id, report) -> dict[str, int]:
    """The AI voice, made by tools/tts/book.py: one MP3 per section, cut at
    every paragraph exactly, since the paragraphs were joined to make it.
    data/audio/ai.tsv carries each segment's speech_sha, the spoken text it
    was made from; check_audio fails on one that is no longer the text's."""
    if not (DATA / "ai.tsv").exists():
        report.warn("audio-ai-unmade", "data/audio/ai.tsv", "the AI voice has not been made"
                    " (make tts); the site offers Merritt Horn alone")
        return {}
    _, _, listed = _tsv(DATA / "ai-files.tsv")
    files = {name: (int(b), int(d), sha) for name, b, d, sha in listed}
    if not _files_on_disk("ai", src, files, report):
        return {}
    comments, _, rows = _tsv(DATA / "ai.tsv")
    sections = {(p, n): sid for sid, p, n in con.execute("SELECT id, paper_n, n FROM section")}
    paras = {ref: (pid, sid) for pid, sid, ref in con.execute("SELECT id, section_id, ref FROM paragraph")}
    con.execute("INSERT INTO audio_source VALUES (?,?,?,?,?,?,?,?,?)",
                (source_id, "ai", src["label"], src["kind"], src["root"], "paragraph",
                 " ".join(comments) or None, src["credit"], src["credit_url"]))
    file_id = {}
    base = con.execute("SELECT COALESCE(MAX(id), 0) FROM audio_file").fetchone()[0]
    for name in sorted(files):
        file_id[name] = base + len(file_id) + 1
        b, d, sha = files[name]
        con.execute("INSERT INTO audio_file VALUES (?,?,?,?,?,?)",
                    (file_id[name], source_id, name, b, d, sha))
    n = 0
    for ref, name, start, end, sha in rows:            # in playing order, as written
        if name not in file_id:
            report.hard("audio-ai-file", ref, f"ai.tsv uses {name}, which ai-files.tsv does not list")
            continue
        m = RE_REF.match(ref)
        if m and m.group(3) is None:
            sid, pid = sections.get((int(m.group(1)), int(m.group(2)))), None
        else:
            pid, sid = paras.get(ref, (None, None))
        if sid is None:
            report.hard("audio-ai-ref", ref, "no such paragraph or section")
            continue
        n += 1
        con.execute("INSERT INTO audio_segment (source_id, section_id, paragraph_id,"
                    " file_id, start_ms, end_ms, match, speech_sha, ord)"
                    " VALUES (?,?,?,?,?,?,NULL,?,?)",
                    (source_id, sid, pid, file_id[name], int(start), int(end), sha, n))
    return {"audio_ai_files": len(files), "audio_ai_segments": n,
            "audio_ai_seconds": sum(d for _b, d, _s in files.values()) // 1000}


def mh_files() -> dict[str, tuple[int, int, str]]:
    """data/audio/mh-files.tsv: {name: (bytes, duration_ms, sha256)}."""
    _, _, listed = _tsv(DATA / "mh-files.tsv")
    return {name: (int(b), int(d), sha) for name, b, d, sha in listed}


def mh_claims(con, files, report) -> dict[str, tuple[int, int | None]]:
    """Which section each used file reads, and from where.

    {name: (section_id, paragraph_id)}, the paragraph None when the file starts
    at the section's spoken heading.  The naming rule, then the overrides; a
    file that neither claims is a hard failure.  tools/align/align.py uses this
    too, so the build and the aligner cannot disagree about what a file holds.
    """
    _, _, ov = _tsv(DATA / "mh-overrides.tsv")
    overrides = {name: start for name, start, _why in ov}
    for name in sorted(overrides.keys() - files.keys()):
        report.hard("audio-override-unknown", name, "mh-overrides.tsv names a file"
                    " that mh-files.tsv does not list")
    sections = {(p, n): (sid, cw) for sid, p, n, cw in con.execute(
        "SELECT id, paper_n, n, combined_with FROM section")}
    paras = {ref: (pid, sid) for pid, sid, ref in con.execute(
        "SELECT id, section_id, ref FROM paragraph")}
    claims = {}
    for name in sorted(files):
        if name in overrides:
            start = overrides[name]
            if start == "-":
                continue                            # not used, on the record
            m = RE_REF.match(start)
            if not m or m.group(3) is None or start not in paras:
                report.hard("audio-override-bad", name, f"starts_at {start!r} is not a paragraph")
                continue
            pid, sid = paras[start]
            claims[name] = (sid, pid)
            continue
        m = RE_MH.match(name)
        if not m or m.group(1) != m.group(2):
            report.hard("audio-unclaimed", name, "fits no naming rule and no override")
            continue
        key = (int(m.group(2)), int(m.group(3)))
        sec = sections.get(key)
        if sec is None:
            report.hard("audio-unclaimed", name, f"no section {key[0]}:{key[1]}")
            continue
        combined = int(m.group(4)) if m.group(4) else None
        if combined != sec[1]:
            report.hard("audio-unclaimed", name, f"names {combined or 'no'} second section;"
                        f" {key[0]}:{key[1]} is combined with {sec[1] or 'none'}")
            continue
        claims[name] = (sec[0], None)
    return claims


def mh_units(con, claims) -> dict[str, list[str]]:
    """What each file holds, in reading order: {name: [ref, ...]}.

    A ref is a paragraph's ('0:12.9'), or the section's ('0:12') for its spoken
    heading.  A file runs from its claim to the next claim in the same section,
    or to the section's end: P000_12 holds 0:12 and 0:12.1-9, P000_13 0:12.10-14.
    """
    starts = {}                                     # section_id -> [(first ord, name)]
    ord_of = dict(con.execute("SELECT id, ord FROM paragraph"))
    for name, (sid, pid) in claims.items():
        starts.setdefault(sid, []).append((ord_of[pid] if pid else -1, name))
    head = {sid: f"{p}:{n}" for sid, p, n in con.execute("SELECT id, paper_n, n FROM section")}
    out = {}
    for sid, files in starts.items():
        files.sort()
        rows = con.execute("SELECT ord, ref FROM paragraph WHERE section_id=? ORDER BY ord",
                           (sid,)).fetchall()
        for i, (first, name) in enumerate(files):
            upto = files[i + 1][0] if i + 1 < len(files) else float("inf")
            out[name] = ([head[sid]] if first < 0 else []) + \
                        [ref for o, ref in rows if first <= o < upto]
    return out


def _load_mh(con, src, source_id, report) -> dict[str, int]:
    files = mh_files()

    # The directory against the list.  The build machine has the recordings;
    # a database that names a file nobody checked is not shipped.  An unlisted
    # file: rerun tools/audio/manifest.py and review the diff.
    if not _files_on_disk("mh", src, files, report):
        return {}

    claims = mh_claims(con, files, report)
    sections = {(p, n): sid for sid, p, n in con.execute(
        "SELECT id, paper_n, n FROM section")}
    paras = {ref: (pid, sid, ord_) for pid, sid, ref, ord_ in con.execute(
        "SELECT id, section_id, ref, ord FROM paragraph")}
    first_ord = dict(con.execute(
        "SELECT section_id, MIN(ord) FROM paragraph GROUP BY section_id"))

    # The aligner's paragraph boundaries, when they exist.
    aligned = DATA / "mh.tsv"
    revision, segs = None, []
    if aligned.exists():
        comments, _, rows = _tsv(aligned)
        revision = " ".join(comments) or None
        for ref, name, start, end, match in rows:
            if name not in claims:
                report.hard("audio-align-file", ref, f"mh.tsv uses {name}, which no claim covers")
                continue
            m = RE_REF.match(ref)
            if m and m.group(3) is None:
                sid = sections.get((int(m.group(1)), int(m.group(2))))
                if sid is None:
                    report.hard("audio-align-ref", ref, "no such section")
                    continue
                segs.append((sid, None, name, int(start), int(end), float(match) if match else None))
            elif ref in paras:
                pid, sid, _ = paras[ref]
                segs.append((sid, pid, name, int(start), int(end), float(match) if match else None))
            else:
                report.hard("audio-align-ref", ref, "no such paragraph")
    else:
        for name, (sid, pid) in claims.items():
            segs.append((sid, pid, name, 0, files[name][1], None))

    con.execute("INSERT INTO audio_source VALUES (?,?,?,?,?,?,?,?,?)",
                (source_id, "mh", src["label"], src["kind"], str(src["path"]),
                 "paragraph" if aligned.exists() else "section", revision,
                 src["credit"], src["credit_url"]))
    _, _, unread = _tsv(DATA / "mh-unread.tsv")
    for ref, why in unread:
        if ref not in paras:
            report.hard("audio-unread-ref", ref, "mh-unread.tsv names no such paragraph")
            continue
        con.execute("INSERT INTO audio_unread VALUES (?,?,?)", (source_id, paras[ref][0], why))
    file_id = {}
    base = con.execute("SELECT COALESCE(MAX(id), 0) FROM audio_file").fetchone()[0]
    for name in sorted(claims):
        file_id[name] = base + len(file_id) + 1
        b, d, sha = files[name]
        con.execute("INSERT INTO audio_file VALUES (?,?,?,?,?,?)",
                    (file_id[name], source_id, name, b, d, sha))
    para_ord = {pid: o for pid, _sid, o in paras.values()}

    def order(s):
        sid, pid, _name, start, _end, _m = s
        # A heading plays before its section's first paragraph.
        return (para_ord[pid] if pid else first_ord[sid] - 0.5, start)

    for i, (sid, pid, name, start, end, match) in enumerate(sorted(segs, key=order), 1):
        con.execute("INSERT INTO audio_segment (source_id, section_id, paragraph_id,"
                    " file_id, start_ms, end_ms, match, speech_sha, ord)"
                    " VALUES (?,?,?,?,?,?,?,NULL,?)",
                    (source_id, sid, pid, file_id[name], start, end, match, i))
    return {"audio_mh_files": len(claims), "audio_mh_segments": len(segs),
            "audio_mh_seconds": sum(files[n][1] for n in claims) // 1000}
