"""What's new: the site's own changes, newest first, for the copy's manifest.

A copy that is out of date offers "What's new" beside its Update button
(static/offline.js), and lists what changed after the copy was made.  The
changes are the subjects of this repository's commits that touch what a reader
is sent (PATHS), each with its time, to compare with the copy's `made`, and
its date, as `git log` gives it.  The index's and the press's commits are
never listed, their subjects being editorial notes ("Ignore .obsidian"):
offline.js says only that the text or the index is newer, and of what date
(Tigran, 2026-10-14).

Read from git here, when the copy is built, since pi5 has no .git; with no
git, there is no news.  Not in the manifest's `build`, which is what the copy
holds: a commit that changes nothing in it offers no update.
"""

from __future__ import annotations

import datetime
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
# What a reader is sent comes from these; a commit touching only the notes,
# the tests, the tools, the EPUB, the deploy or vendor/ is not news to them.
PATHS = ("ubsite", "offline", "build", "data")
LIMIT = 200


def news() -> dict:
    """{items: [{t, d, s}], earlier}: t the commit's time in UTC, d its date
    where it was made, s its subject; `earlier` when there are more than LIMIT."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", f"-n{LIMIT + 1}", "--format=%cI%x1f%s",
                              "--", *PATHS], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"items": [], "earlier": False}
    items = []
    for line in out.splitlines():
        when, _, subject = line.partition("\x1f")
        t = datetime.datetime.fromisoformat(when).astimezone(datetime.timezone.utc)
        items.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "d": when[:10], "s": subject})
    return {"items": items[:LIMIT], "earlier": len(items) > LIMIT}
