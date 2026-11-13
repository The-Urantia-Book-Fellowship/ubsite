"""The recordings -> audio_source, audio_file, audio_segment.

A recording directory is a master like the three repos: it is listed and its
files are measured, never opened for writing -- and here not even opened, since
everything this needs about a file is in data/audio/<key>-files.tsv, which
tools/audio/manifest.py made by hashing every file once.  The build checks the
directory against that list by size on every run, which is cheap, and fails on
a file the list does not name -- a source nothing claimed (CLAUDE.md §6).

A human reading is one MP3 per section, and every one is loaded the same way,
by its key (the config's [audio.<key>]): Merritt Horn's ('mh'), of the English
text, and Григорий Войнер's ('voyner'), of the translation urantia-ru.  Its
naming rule, the source's `name`, claims nearly all its files;
data/audio/<key>-overrides.tsv names those that do not follow it (Merritt
Horn's three, and Войнер's 7-07.mp3).  Until data/audio/<key>.tsv exists --
the aligner's output, paragraph by paragraph -- each file is one segment,
played from its start to its end.  <key>-unread.tsv names the paragraphs the
reading leaves out.

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
# after the aligner's unbatched second pass, is a place where the reading and
# today's text differ -- a sentence not read, or one added or reworded since.
# check_audio holds that set to data/audio/<key>-low-match.tsv, exactly.
LOW_WORDS, LOW_MATCH = 10, 0.6
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
    """Load every recording config.audio() names, in the config's order,
    which is the order they are listed in.  Returns counts for `stat`."""
    stats = {}
    for source_id, (key, src) in enumerate(config.audio().items(), 1):
        if src["kind"] == "synthetic":
            stats.update(_load_ai(con, src, source_id, report))
        else:
            stats.update(_load_human(con, key, src, source_id, report))
    return stats


def _files_on_disk(key: str, src, files: dict, report) -> bool:
    """The directory against data/audio/<key>-files.tsv, by size: a file it
    does not list, or lists and is not there, is a hard failure."""
    if not src["present"]:
        report.hard("audio-absent", str(src["path"]), "the recordings are not where the config says")
        return False
    on_disk = {p.relative_to(src["path"]).as_posix(): p.stat().st_size
               for p in src["path"].glob(src["glob"])}
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
                    " (make tts); the site goes without it")
        return {}
    _, _, listed = _tsv(DATA / "ai-files.tsv")
    files = {name: (int(b), int(d), sha) for name, b, d, sha in listed}
    if not _files_on_disk("ai", src, files, report):
        return {}
    comments, _, rows = _tsv(DATA / "ai.tsv")
    sections = {(p, n): sid for sid, p, n in con.execute("SELECT id, paper_n, n FROM section")}
    paras = {ref: (pid, sid) for pid, sid, ref in con.execute("SELECT id, section_id, ref FROM paragraph")}
    con.execute("INSERT INTO audio_source VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, "ai", src["label"], src["kind"], src["root"], "paragraph",
                 " ".join(comments) or None, src["credit"], src["credit_url"], None))
    file_id = {}
    base = con.execute("SELECT COALESCE(MAX(id), 0) FROM audio_file").fetchone()[0]
    for name in sorted(files):
        file_id[name] = base + len(file_id) + 1
        b, d, sha = files[name]
        con.execute("INSERT INTO audio_file (id, source_id, name, bytes, duration_ms, sha256)"
                    " VALUES (?,?,?,?,?,?)", (file_id[name], source_id, name, b, d, sha))
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


def _optional(path: pathlib.Path) -> list[list[str]]:
    """A list's rows, or none where a reading has no such list."""
    return _tsv(path)[2] if path.exists() else []


def files(key: str) -> dict[str, tuple[int, int, str]]:
    """data/audio/<key>-files.tsv: {name: (bytes, duration_ms, sha256)}."""
    _, _, listed = _tsv(DATA / f"{key}-files.tsv")
    return {name: (int(b), int(d), sha) for name, b, d, sha in listed}


def info_frames(key: str, listed, report) -> dict[str, tuple[int, bytes, str]]:
    """data/audio/<key>-frames.tsv: {name: (where it goes, the Info frame, the
    SHA-256 of the file sent with it)},
    for each file that is sent with one (build/mp3.py says why).  The list is
    tools/audio/manifest.py's, from the files themselves; the frame is made
    here, and held to the duration the list of files gives: a frame that told
    a player another length than the cuts were made on would be worse than none."""
    from . import mp3
    out = {}
    for name, at, frames, size, header, sent in _optional(DATA / f"{key}-frames.tsv"):
        if name not in listed:
            report.hard("audio-frames-unknown", name, f"{key}-frames.tsv names a file"
                        f" that {key}-files.tsv does not list")
            continue
        try:
            head = mp3.info_frame(bytes.fromhex(header), int(frames), int(size))
        except ValueError as e:
            report.hard("audio-frames-bad", name, str(e))
            continue
        f = mp3.frame(head, 0)
        if round(int(frames) * f.samples * 1000 / f.hz) != listed[name][1] \
                or not 0 <= int(at) <= listed[name][0] - int(size):
            report.hard("audio-frames-length", name, f"{frames} frames in {size} bytes from byte {at}"
                        f" are not the {listed[name][1]} ms and {listed[name][0]} bytes listed")
            continue
        out[name] = (int(at), head, sent)
    return out


def unread(key: str) -> dict[str, str]:
    """data/audio/<key>-unread.tsv: {ref: why}, the paragraphs not read."""
    return {ref: why for ref, why in _optional(DATA / f"{key}-unread.tsv")}


def claims(con, key: str, src, files, report) -> dict[str, tuple[int, int | None]]:
    """Which section each used file reads, and from where.

    {name: (section_id, paragraph_id)}, the paragraph None when the file starts
    at the section's spoken heading.  The overrides, then the source's naming
    rule (the config's `name`); a file that neither claims is a hard failure.
    tools/align/align.py uses this too, so the build and the aligner cannot
    disagree about what a file holds.
    """
    overrides = {name: start for name, start, _why in _optional(DATA / f"{key}-overrides.tsv")}
    for name in sorted(overrides.keys() - files.keys()):
        report.hard("audio-override-unknown", name, f"{key}-overrides.tsv names a file"
                    f" that {key}-files.tsv does not list")
    if not src["name"]:
        report.hard("audio-no-rule", key, "the config gives this reading no `name`,"
                    " the rule by which a file names its section")
        return {}
    rule = re.compile(src["name"])
    sections = {(p, n): (sid, cw) for sid, p, n, cw in con.execute(
        "SELECT id, paper_n, n, combined_with FROM section")}
    paras = {ref: (pid, sid) for pid, sid, ref in con.execute(
        "SELECT id, section_id, ref FROM paragraph")}
    out = {}
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
            out[name] = (sid, pid)
            continue
        m = rule.match(name)
        # Filed in a folder to a paper, the folder is the paper's.
        if not m or ("folder" in rule.groupindex and int(m.group("folder")) != int(m.group("paper"))):
            report.hard("audio-unclaimed", name, "fits no naming rule and no override")
            continue
        at = (int(m.group("paper")), int(m.group("section")))
        sec = sections.get(at)
        if sec is None:
            report.hard("audio-unclaimed", name, f"no section {at[0]}:{at[1]}")
            continue
        combined = int(m.group("with")) if "with" in rule.groupindex and m.group("with") else None
        if combined != sec[1]:
            report.hard("audio-unclaimed", name, f"names {combined or 'no'} second section;"
                        f" {at[0]}:{at[1]} is combined with {sec[1] or 'none'}")
            continue
        out[name] = (sec[0], None)
    # Two files for one place: one of them is a second encode, to be left out
    # by name (Войнер's 7-07.mp3 would otherwise have needed 7:7 twice).
    seen = {}
    for name, at in out.items():
        if at in seen:
            report.hard("audio-claimed-twice", name, f"reads what {seen[at]} reads")
        seen[at] = name
    return out


def units(con, claims, translation: str | None = None) -> dict[str, list[str]]:
    """What each file holds, in reading order: {name: [ref, ...]}.

    A ref is a paragraph's ('0:12.9'), or the section's ('0:12') for its spoken
    heading.  A file runs from its claim to the next claim in the same section,
    or to the section's end: P000_12 holds 0:12 and 0:12.1-9, P000_13 0:12.10-14.
    A translation's reading holds the paragraphs that translation has.
    """
    starts = {}                                     # section_id -> [(first ord, name)]
    ord_of = dict(con.execute("SELECT id, ord FROM paragraph"))
    for name, (sid, pid) in claims.items():
        starts.setdefault(sid, []).append((ord_of[pid] if pid else -1, name))
    head = {sid: f"{p}:{n}" for sid, p, n in con.execute("SELECT id, paper_n, n FROM section")}
    has = None if translation is None else {pid for (pid,) in con.execute(
        "SELECT paragraph_id FROM tr_paragraph WHERE translation = ?", (translation,))}
    out = {}
    for sid, names in starts.items():
        names.sort()
        rows = con.execute("SELECT ord, ref, id FROM paragraph WHERE section_id=? ORDER BY ord",
                           (sid,)).fetchall()
        for i, (first, name) in enumerate(names):
            upto = names[i + 1][0] if i + 1 < len(names) else float("inf")
            out[name] = ([head[sid]] if first < 0 else []) + \
                        [ref for o, ref, pid in rows if first <= o < upto and (has is None or pid in has)]
    return out


def _load_human(con, key: str, src, source_id: int, report) -> dict[str, int]:
    """A human reading, a file per section: Merritt Horn's, Григорий Войнер's."""
    if not (DATA / f"{key}-files.tsv").exists():
        report.hard("audio-unlisted", key, f"no data/audio/{key}-files.tsv:"
                    f" .venv/bin/python -m tools.audio.manifest {key}")
        return {}
    listed = files(key)
    tr = src["translation"]
    if tr and not con.execute("SELECT 1 FROM translation WHERE key = ?", (tr,)).fetchone():
        report.hard("audio-translation", key, f"reads {tr!r}, a translation this build does not have")
        return {}

    # The directory against the list.  The build machine has the recordings;
    # a database that names a file nobody checked is not shipped.  An unlisted
    # file: rerun tools/audio/manifest.py and review the diff.
    if not _files_on_disk(key, src, listed, report):
        return {}

    claimed = claims(con, key, src, listed, report)
    sections = {(p, n): sid for sid, p, n in con.execute(
        "SELECT id, paper_n, n FROM section")}
    paras = {ref: (pid, sid, ord_) for pid, sid, ref, ord_ in con.execute(
        "SELECT id, section_id, ref, ord FROM paragraph")}
    first_ord = dict(con.execute(
        "SELECT section_id, MIN(ord) FROM paragraph GROUP BY section_id"))

    # The aligner's paragraph boundaries, when they exist.
    aligned = DATA / f"{key}.tsv"
    revision, segs = None, []
    if aligned.exists():
        comments, _, rows = _tsv(aligned)
        revision = " ".join(comments) or None
        for ref, name, start, end, match in rows:
            if name not in claimed:
                report.hard("audio-align-file", ref, f"{key}.tsv uses {name}, which no claim covers")
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
        for name, (sid, pid) in claimed.items():
            segs.append((sid, pid, name, 0, listed[name][1], None))

    con.execute("INSERT INTO audio_source VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, key, src["label"], src["kind"], str(src["path"]),
                 "paragraph" if aligned.exists() else "section", revision,
                 src["credit"], src["credit_url"], tr))
    for ref, why in unread(key).items():
        if ref not in paras:
            report.hard("audio-unread-ref", ref, f"{key}-unread.tsv names no such paragraph")
            continue
        con.execute("INSERT INTO audio_unread VALUES (?,?,?)", (source_id, paras[ref][0], why))
    file_id = {}
    base = con.execute("SELECT COALESCE(MAX(id), 0) FROM audio_file").fetchone()[0]
    heads = info_frames(key, listed, report)
    for name in sorted(claimed):
        file_id[name] = base + len(file_id) + 1
        b, d, sha = listed[name]
        at, head, sent = heads.get(name, (None, None, None))
        con.execute("INSERT INTO audio_file (id, source_id, name, bytes, duration_ms, sha256,"
                    " head_at, head, sent_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                    (file_id[name], source_id, name, b, d, sha, at, head, sent))
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
    return {f"audio_{key}_files": len(claimed), f"audio_{key}_segments": len(segs),
            f"audio_{key}_seconds": sum(listed[n][1] for n in claimed) // 1000}
