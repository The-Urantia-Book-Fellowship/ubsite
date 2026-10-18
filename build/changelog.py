"""ChangeLog.md into the database, for the page /changelog (Tigran, 2026-10-18).

The page is the file as written, every block of it in its order: its title,
the paragraphs that open it, each version with its headings and entries, and
where the file began.  It adds only each entry's date in a version, which the
file does not say: the day the commit that wrote its line was made, as `git
blame` gives it, or today for a line not yet committed.  The hosts have no
.git, so the dates are made here and shipped with the rest; offline/news.py
dates What's new by the same.

The file's Markdown is made HTML here, the little it uses: `code`, *emphasis*,
**strong**, [links](url) and bare URLs, with straight quotes curled.  Anything
else fails the build rather than show as written, and so does an entry for
readers with any Markdown at all, since What's new shows those as text.
"""

from __future__ import annotations

import dataclasses
import datetime
import html
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "ChangeLog.md"

FOR_READERS = {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}
FOR_DEVELOPERS = "For developers"
RE_VERSION = re.compile(r"^## \[(Unreleased|\d+\.\d+\.\d+)\](?: - (\d{4}-\d\d-\d\d))?$")
# What's new shows an entry for readers as text, so Markdown would show as written.
RE_MARKUP = re.compile(r"[`*\[\]<>]")
RE_INLINE = re.compile(r"`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)\s]+)\)|(https?://[^\s<>()]*[^\s<>().,;:!?])")


@dataclasses.dataclass
class Line:
    line: int                 # in ChangeLog.md, from 1
    part: str                 # 'intro', 'readers', 'developers' or 'began'
    version: str | None       # 'Unreleased' or '1.2.0'; None outside a version
    released: str | None      # the version's date, YYYY-MM-DD
    heading: str | None       # the ### it stands under, or is; None above any
    kind: str                 # 'h1', 'h2', 'h3', 'para' or 'entry'
    words: str                # as the file has it, Markdown and all, but a
                              # version's heading: 'Unreleased', '1.2.0 – October 30, 2026'


def parse(text: str) -> list[Line]:
    """Every block of the file, a heading, a paragraph or an entry, in its order.

    Raises on what the page or What's new could not show, or would silently
    miss: a version's heading that is neither for readers nor for developers,
    anything in a version but an entry under one, an entry for readers with
    Markdown in it, an entry above every heading.
    """
    out: list[Line] = []
    part, version = "intro", None
    released = heading = None
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            out.append(Line(i, part, None, None, None, "h1", line[2:].strip()))
        elif line.startswith("## "):
            m = RE_VERSION.match(line)
            version, released, heading = (m[1], m[2], None) if m else (None, None, None)
            part = "readers" if m else "began"
            name = (f"{m[1]} \N{EN DASH} {us_date(m[2])}" if m[2] else m[1]) if m else line[3:].strip()
            out.append(Line(i, part, version, released, None, "h2", name))
        elif line.startswith("### "):
            heading = line[4:].strip()
            if version and heading not in FOR_READERS | {FOR_DEVELOPERS}:
                raise ValueError(f"ChangeLog.md:{i}: {heading!r} is not a heading of Keep a"
                                 f" Changelog, nor {FOR_DEVELOPERS!r}")
            mine = "developers" if heading == FOR_DEVELOPERS else ("readers" if version else "began")
            out.append(Line(i, mine, version, released, heading, "h3", heading))
        elif line.startswith("- "):
            if heading is None:
                raise ValueError(f"ChangeLog.md:{i}: an entry stands under a '###' heading")
            words = line[2:].strip()
            mine = "developers" if heading == FOR_DEVELOPERS else ("readers" if version else "began")
            if mine == "readers" and RE_MARKUP.search(words):
                raise ValueError(f"ChangeLog.md:{i}: an entry for readers is plain text,"
                                 f" shown as written: {words!r}")
            out.append(Line(i, mine, version, released, heading, "entry", words))
        elif version:
            raise ValueError(f"ChangeLog.md:{i}: a version holds only entries, each one line"
                             f" begun by '- ', under a heading")
        else:
            out.append(Line(i, part, None, None, heading, "para", line.strip()))
    return out


def us_date(iso: str) -> str:
    """"October 30, 2026": a date in words in the American order, as the site
    writes every one (Tigran, 2026-10-18; app.py us_date)."""
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def inline(words: str, where: str = "ChangeLog.md") -> str:
    """The file's Markdown as HTML: `code`, *emphasis*, **strong**, [links](url)
    and bare URLs, as Obsidian shows them."""
    out, at = [], 0

    def plain(s: str) -> str:
        if re.search(r"[`*\[\]]", s):
            raise ValueError(f"{where}: Markdown the page cannot draw: {s!r}")
        return html.escape(curl(s), quote=False)

    for m in RE_INLINE.finditer(words):
        out.append(plain(words[at:m.start()]))
        at = m.end()
        if m[1] is not None:
            out.append(f"<code>{html.escape(m[1], quote=False)}</code>")
        elif m[2] is not None:
            out.append(f"<strong>{plain(m[2])}</strong>")
        elif m[3] is not None:
            out.append(f"<i>{plain(m[3])}</i>")
        elif m[4] is not None:
            out.append(f'<a href="{html.escape(m[5])}">{plain(m[4])}</a>')
        else:
            out.append(f'<a href="{html.escape(m[6])}">{html.escape(m[6], quote=False)}</a>')
    out.append(plain(words[at:]))
    return "".join(out)


def curl(s: str) -> str:
    """Straight quotes made curly, as the book sets them: Goudy draws a straight
    " as a closing one, so "Updating the site" opened with ”.  Never in code."""
    s = re.sub(r'(^|[\s(—–-])"', "\\1“", s).replace('"', "”")
    return re.sub(r"(^|[\s(—–-])'", "\\1‘", s).replace("'", "’")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=True).stdout


def written() -> dict[int, datetime.datetime]:
    """When each line of ChangeLog.md was written: its commit's time, where it
    was made.  A line not yet committed is not here; -M follows a line moved
    within the file, as entries are when a release is cut."""
    try:
        out = _git("blame", "--porcelain", "-M", "--", CHANGELOG.name)
    except (OSError, subprocess.CalledProcessError):   # no git, or not yet committed
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


def load(con) -> int:
    """Fill `changelog`; the number of blocks it holds."""
    lines = parse(CHANGELOG.read_text(encoding="utf-8"))
    when, now = written(), datetime.datetime.now().astimezone()
    rows = []
    for x in lines:
        h = inline(x.words, f"ChangeLog.md:{x.line}")
        rows.append((x.line, x.part, x.version, x.released, x.heading, x.kind, h,
                     html.unescape(re.sub(r"<[^>]+>", "", h)),
                     when.get(x.line, now).date().isoformat()))
    con.executemany("INSERT INTO changelog VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)
