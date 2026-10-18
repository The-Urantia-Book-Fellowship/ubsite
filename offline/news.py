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
import subprocess

from build import changelog

ROOT = changelog.ROOT
CHANGELOG = changelog.CHANGELOG
# Before ChangeLog.md, what a reader is sent came from these; a commit touching
# only the notes, the tests, the tools, the EPUB, the deploy or vendor/ was
# not news to them.
PATHS = ("ubsite", "offline", "build", "data")
LIMIT = 200


def entries(text: str) -> list[tuple[int, str]]:
    """(line, words) of each entry for readers, in the file's order: as
    build/changelog.py parses the file for the page /changelog, which raises
    on what What's new could not show, or would silently miss."""
    return [(x.line, x.words) for x in changelog.parse(text)
            if x.part == "readers" and x.kind == "entry"]


_git = changelog._git


def _item(when: datetime.datetime, words: str) -> dict:
    t = when.astimezone(datetime.timezone.utc)
    return {"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "d": when.date().isoformat(), "s": words}


def news() -> dict:
    """{items: [{t, d, s}], earlier}: t the time an entry was written in UTC,
    d its date where it was written, s its words; `earlier` when there are
    more than LIMIT."""
    try:
        began = _git("log", "--diff-filter=A", "--format=%H", "--", CHANGELOG.name).split()
    except (OSError, subprocess.CalledProcessError):
        return {"items": [], "earlier": False}
    now = datetime.datetime.now().astimezone()
    written = changelog.written()
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
