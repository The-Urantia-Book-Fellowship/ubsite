"""Snapshot the SRT Committee's page: data/srt/considerations.html.

    .venv/bin/python -m tools.srt.snapshot          (make srt-snapshot)

The Fellowship publishes the committee's reason for every change to the 1955
text (sources.toml [srt]).  The page is mostly the site's own frame -- its
menus, recent blog posts, upcoming gatherings -- which changes weekly, and two
tables, which hold the entries: Frontmatter and Foreword and Papers.  This keeps
those two tables exactly as served, and nothing else, so that a refresh shows
as a diff of the entries alone.  The header records where and when, and the
SHA-256 of the whole page as fetched.

Run it on purpose, review the diff, and commit it.  `make data` reads the
snapshot and never the network.
"""

from __future__ import annotations

import datetime
import hashlib
import re
import sys
import urllib.request

from build import config

# The entries' tables; the page lays itself out with others ("WaLayoutTable").
TABLE = re.compile(r'<table border="1" cellspacing="0" cellpadding="2">.*?</table>', re.S)
EXPECT = 2


def main(argv: list[str]) -> int:
    src = config.srt()
    req = urllib.request.Request(src["url"], headers={"User-Agent": "ubsite srt-snapshot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    page = raw.decode("utf-8")
    tables = TABLE.findall(page)
    if len(tables) != EXPECT:
        print(f"srt-snapshot: {len(tables)} entry tables on the page, expected {EXPECT};"
              " the page has changed its layout -- nothing written", file=sys.stderr)
        return 1
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = ("<!-- The SRT Committee's considerations and changes to the 1955 text, as the\n"
            "     Fellowship's site publishes them: the page's two tables of entries,\n"
            "     exactly as served, and nothing else of the page.  Made by\n"
            "     tools/srt/snapshot.py (make srt-snapshot); never edit it by hand.\n"
            f"     url:     {src['url']}\n"
            f"     fetched: {when}\n"
            f"     sha256:  {hashlib.sha256(raw).hexdigest()}  (the whole page)\n"
            "-->\n")
    out = src["path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(head + "\n\n".join(tables) + "\n", encoding="utf-8")
    rows = sum(t.count("<tr>") for t in tables)
    print(f"{out.relative_to(config.ROOT)}: {len(tables)} tables, {rows} rows,"
          f" {out.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
