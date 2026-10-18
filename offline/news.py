"""What's new: the site's own changes, newest first, for the copy's manifest.

A copy that is out of date offers "What's new" beside its Update button
(static/offline.js), and lists what changed after the copy was made.  The
changes are ChangeLog.md's entries for readers, those under Added, Changed,
Deprecated, Removed, Fixed and Security in a version, never For developers;
each is dated by the commit that wrote its line, as `git blame` gives it, to
compare with the copy's `made` (Tigran, 2026-10-18).  Before ChangeLog.md
began, they were the subjects of this repository's commits that touch what a
reader is sent (PATHS), and a copy made before then still sees those.  The
index's and the press's commits are never listed, their subjects being
editorial notes ("Ignore .obsidian"): offline.js says only that the text or
the index is newer, and of what date (Tigran, 2026-10-14).

Read from git here, when the copy is built, since pi5 has no .git; with no
git, there is no news.  Not in the manifest's `build`, which is what the copy
holds: a change to the news alone offers no update.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "ChangeLog.md"
# Before ChangeLog.md, what a reader is sent came from these; a commit touching
# only the notes, the tests, the tools, the EPUB, the deploy or vendor/ was
# not news to them.
PATHS = ("ubsite", "offline", "build", "data")
LIMIT = 200

FOR_READERS = {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}
FOR_DEVELOPERS = "For developers"
RE_VERSION = re.compile(r"^## \[(?:Unreleased|\d+\.\d+\.\d+)\](?: - \d{4}-\d\d-\d\d)?$")
# What's new shows an entry as text, so Markdown would show as written.
RE_MARKUP = re.compile(r"[`*\[\]<>]")


def entries(text: str) -> list[tuple[int, str]]:
    """(line, words) of each entry for readers, in the file's order.

    Raises on what What's new could not show, or would silently miss: a
    heading of a version that is neither for readers nor for developers, an
    entry that is not one line begun by "- ", or one with Markdown in it.
    A `##` that is not a version, such as where the file began, is not news.
    """
    out = []
    version = heading = None
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            version, heading = RE_VERSION.match(line), None
        elif line.startswith("### "):
            heading = line[4:].strip()
            if version and heading not in FOR_READERS | {FOR_DEVELOPERS}:
                raise ValueError(f"ChangeLog.md:{i}: {heading!r} is not a heading of Keep a"
                                 f" Changelog, nor {FOR_DEVELOPERS!r}")
        elif version and heading in FOR_READERS and line.strip():
            if not line.startswith("- "):
                raise ValueError(f"ChangeLog.md:{i}: an entry for readers is one line, begun by '- '")
            words = line[2:].strip()
            if RE_MARKUP.search(words):
                raise ValueError(f"ChangeLog.md:{i}: an entry for readers is plain text,"
                                 f" shown as written: {words!r}")
            out.append((i, words))
    return out


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=True).stdout


def _item(when: datetime.datetime, words: str) -> dict:
    t = when.astimezone(datetime.timezone.utc)
    return {"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "d": when.date().isoformat(), "s": words}


def _written() -> dict[int, datetime.datetime]:
    """When each line of ChangeLog.md was written: its commit's time, where it
    was made.  A line not yet committed is written now; -M follows a line
    moved within the file, as entries are when a release is cut."""
    try:
        out = _git("blame", "--porcelain", "-M", "--", CHANGELOG.name)
    except subprocess.CalledProcessError:   # not yet committed at all
        return {}
    when, line, commits = {}, 0, {}
    sha = None
    for row in out.splitlines():
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", row)
        if m:
            sha, line = m[1], int(m[2])
            commits.setdefault(sha, {})
        elif row.startswith("committer-time "):
            commits[sha]["time"] = int(row.split()[1])
        elif row.startswith("committer-tz "):
            tz = row.split()[1]
            sign = -1 if tz[0] == "-" else 1
            commits[sha]["tz"] = datetime.timezone(
                sign * datetime.timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])))
        elif row.startswith("\t"):
            c = commits[sha]
            when[line] = datetime.datetime.fromtimestamp(c["time"], c["tz"])
    return when


def news() -> dict:
    """{items: [{t, d, s}], earlier}: t the time an entry was written in UTC,
    d its date where it was written, s its words; `earlier` when there are
    more than LIMIT."""
    try:
        began = _git("log", "--diff-filter=A", "--format=%H", "--", CHANGELOG.name).split()
    except (OSError, subprocess.CalledProcessError):
        return {"items": [], "earlier": False}
    now = datetime.datetime.now().astimezone()
    written = _written()
    items = [_item(written.get(i, now), words)
             for i, words in entries(CHANGELOG.read_text(encoding="utf-8"))]
    # What came before the changelog: the commits before the one that began it.
    before = f"{began[-1]}^" if began else "HEAD"
    out = _git("log", f"-n{LIMIT + 1}", "--format=%cI%x1f%s", before, "--", *PATHS)
    for row in out.splitlines():
        when, _, subject = row.partition("\x1f")
        items.append(_item(datetime.datetime.fromisoformat(when), subject))
    # Newest first; lines written together keep the file's order.
    items.sort(key=lambda x: x["t"], reverse=True)
    return {"items": items[:LIMIT], "earlier": len(items) > LIMIT}
