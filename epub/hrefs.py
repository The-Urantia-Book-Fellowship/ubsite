"""Where a site address lives inside the EPUB.

The stored index HTML carries site-absolute links (`/77:9.4-5`, `/i/seraphim`),
and the chips and concept blocks are drawn with the site's notion of where an
entry lives.  Every one of them is mapped here, to a file in the package and an
id in it, and anything this does not recognise -- a new href form upstream, a
paragraph that does not exist -- raises, rather than leaving a dead link in a
book nobody can patch once it is on a device.

All content documents sit side by side in OEBPS/, so a link is `file#id`.

    /N:S.P  and /N:S.P-Q    pNNN.xhtml#pN_S_P   (a range opens at its first)
    /N:S                    pNNN.xhtml#sN_S
    /N                      pNNN.xhtml
    /i/slug                 index-X.xhtml#<the headword's anchor>
    /i/slug#anchor          index-X.xhtml#anchor
    /appendix/L#anchor      app-L.xhtml#anchor
"""

from __future__ import annotations

import re

RE_HREF = re.compile(r'href="([^"]*)"')
RE_PARA = re.compile(r"^/(\d+):(\d+)\.(\d+)(?:-(\d+))?$")
RE_SEC = re.compile(r"^/(\d+):(\d+)$")
RE_PAPER = re.compile(r"^/(\d+)$")
RE_SLUG = re.compile(r"^/i/([a-z0-9-]+)(?:#([a-z0-9-]+))?$")
RE_APP = re.compile(r"^/appendix/([A-F])#([a-z0-9-]+)$")
RE_NOTE = re.compile(r"^#fn(?:ref)?(?:st)?\d+_\d+_\d+_\d+$")


def paper_file(n: int) -> str:
    return f"p{n:03d}.xhtml"


def para_id(paper: int, sec: int, n: int) -> str:
    return f"p{paper}_{sec}_{n}"


def section_id(paper: int, sec: int) -> str:
    return f"s{paper}_{sec}"


def appendix_file(letter: str) -> str:
    return f"app-{letter}.xhtml"


class Hrefs:
    """The map, built from the database before anything is drawn.

    `index_file` (slug -> file) is filled in by the index's own layout, which
    decides where each letter is split; until then an index link raises.
    """

    def __init__(self, con):
        self.paras = {(p, s, n) for p, s, n in con.execute(
            "SELECT paper_n, section_n, para_n FROM paragraph")}
        self.sections = {(p, s) for p, s in con.execute(
            "SELECT paper_n, n FROM section")}
        self.papers = {n for (n,) in con.execute("SELECT n FROM paper")}
        self.root_anchor = dict(con.execute(
            "SELECT slug, anchor FROM index_entry WHERE slug IS NOT NULL"))
        # Which headword each A-Z anchor sits under, to check a deep link lands
        # in the file that holds it.
        self.anchor_slug = dict(con.execute(
            "SELECT e.anchor, r.slug FROM index_entry e JOIN index_entry r ON r.id=e.root_id"
            " WHERE e.scope='az'"))
        self.app_anchors = {(s, a) for s, a in con.execute(
            "SELECT scope, anchor FROM index_entry WHERE scope<>'az'")}
        self.index_file: dict[str, str] = {}

    # -- the text --------------------------------------------------------------
    def para(self, paper: int, sec: int, n: int) -> str:
        if (paper, sec, n) not in self.paras:
            raise KeyError(f"no paragraph {paper}:{sec}.{n}")
        return f"{paper_file(paper)}#{para_id(paper, sec, n)}"

    def section(self, paper: int, sec: int) -> str:
        if (paper, sec) not in self.sections:
            raise KeyError(f"no section {paper}:{sec}")
        return f"{paper_file(paper)}#{section_id(paper, sec)}"

    def paper(self, paper: int) -> str:
        if paper not in self.papers:
            raise KeyError(f"no paper {paper}")
        return paper_file(paper)

    # -- the index and the appendices ------------------------------------------
    def entry(self, slug: str, anchor: str | None = None) -> str:
        """A headword (anchor None) or an entry under it."""
        if slug not in self.index_file:
            raise KeyError(f"no headword with slug {slug!r} laid out")
        if anchor is None:
            anchor = self.root_anchor[slug]
        elif self.anchor_slug.get(anchor) != slug:
            raise KeyError(f"anchor {anchor!r} is not under {slug!r}")
        return f"{self.index_file[slug]}#{anchor}"

    def appendix(self, letter: str, anchor: str) -> str:
        if (letter, anchor) not in self.app_anchors:
            raise KeyError(f"no appendix row {letter}#{anchor}")
        return f"{appendix_file(letter)}#{anchor}"

    # -- a site address --------------------------------------------------------
    def site(self, url: str) -> str:
        if m := RE_PARA.match(url):
            p, s, n, last = m.groups()
            if last is not None and (int(p), int(s), int(last)) not in self.paras:
                raise KeyError(f"range {url} runs past its section")
            return self.para(int(p), int(s), int(n))
        if m := RE_SEC.match(url):
            return self.section(int(m[1]), int(m[2]))
        if m := RE_PAPER.match(url):
            return self.paper(int(m[1]))
        if m := RE_SLUG.match(url):
            return self.entry(m[1], m[2])
        if m := RE_APP.match(url):
            return self.appendix(m[1], m[2])
        raise ValueError(f"no EPUB address for the site's {url!r}")

    def rewrite(self, html: str) -> str:
        """Every href in a stored fragment, mapped.  A note's own `#fn…` stays."""
        def sub(m):
            url = m.group(1)
            return m.group(0) if RE_NOTE.match(url) else f'href="{self.site(url)}"'
        return RE_HREF.sub(sub, html)
