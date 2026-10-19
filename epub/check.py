"""The gates for the EPUB, read back from the file itself.

Nothing here trusts the builder's own bookkeeping: each gate opens the zip,
parses what an e-reader will parse, and holds it to the database.

1. the container: mimetype first and stored; the manifest is the zip
2. every document is well-formed XML
3. every link lands: a file in the package and an id in it; no id twice
4. round trip: each paragraph, less its reference, pilcrow and note marker,
   is paragraph.text byte for byte; each index and appendix line is
   index_entry.text
5. counts against the database: papers, sections, notes, headwords, rows,
   the chips beneath each paragraph and at each section's head, citations
6. every character the book draws is in the embedded fonts
7. the same database builds the same file, byte for byte
8. epubcheck (W3C), with no error and no warning

    python -m epub check      exit 0 only when every gate passes
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

from fontTools.ttLib import TTFont

from build.fonts import ELSEWHERE
from ubsite import queries

from . import pack

X = "{http://www.w3.org/1999/xhtml}"
EPUB = "{http://www.idpf.org/2007/ops}"
OPF = "{http://www.idpf.org/2007/opf}"
NCX = "{http://www.daisy.org/z3986/2005/ncx/}"
JAVA_PACKAGE = "openjdk-26-jre-headless"
EPUBCHECK = pathlib.Path(os.environ.get(
    "EPUBCHECK", pack.ROOT / "var/epubcheck/epubcheck-5.4.0/epubcheck.jar"))
RE_PID = re.compile(r"^p(\d+)_(\d+)_(\d+)$")


def classes(el) -> set[str]:
    return set((el.get("class") or "").split())


def para_text(el) -> str:
    """A paragraph's words as the database holds them: without the reference
    (and the space after it), the pilcrow, or a note marker's asterisk."""
    out = [el.text or ""]
    for ch in el:
        c = classes(ch)
        if "ref" in c:
            out.append((ch.tail or "")[1:] if (ch.tail or "").startswith(" ") else ch.tail or "")
            continue
        if "pc" in c or "fn" in c:
            out.append(ch.tail or "")
            continue
        out.append(para_text(ch))
        out.append(ch.tail or "")
    return "".join(out)


class Gate:
    def __init__(self):
        self.failed = 0

    def line(self, ok: bool, what: str, detail: str = ""):
        print(f"  {'ok  ' if ok else 'FAIL'}  {what}" + (f"   {detail}" if detail else ""))
        if not ok:
            self.failed += 1


def run(con, path: pathlib.Path) -> int:
    g = Gate()
    print(f"== epub: {path} ==")
    data = path.read_bytes()
    z = zipfile.ZipFile(io.BytesIO(data))
    infos = z.infolist()

    # 1. the container ---------------------------------------------------------
    first = infos[0]
    g.line(first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
           and z.read("mimetype") == b"application/epub+zip",
           "mimetype is the first entry, stored, and says application/epub+zip")
    opf = ET.fromstring(z.read("OEBPS/package.opf"))
    manifest = {i.get("href"): i for i in opf.iter(f"{OPF}item")}
    in_zip = {i.filename.removeprefix("OEBPS/") for i in infos
              if i.filename.startswith("OEBPS/")} - {"package.opf"}
    g.line(set(manifest) == in_zip, f"the manifest names every file in the package ({len(in_zip)})",
           f"unlisted {sorted(in_zip - set(manifest))[:5]} missing {sorted(set(manifest) - in_zip)[:5]}"
           if set(manifest) != in_zip else "")

    # 2. well-formed ----------------------------------------------------------
    docs: dict[str, ET.Element] = {}
    bad = []
    for href, item in manifest.items():
        if item.get("media-type") in ("application/xhtml+xml", "application/x-dtbncx+xml"):
            try:
                docs[href] = ET.fromstring(z.read(f"OEBPS/{href}"))
            except ET.ParseError as e:
                bad.append(f"{href}: {e}")
    g.line(not bad, f"{len(docs)} documents are well-formed XML", "; ".join(bad[:3]))

    # 3. links ----------------------------------------------------------------
    ids: dict[str, set[str]] = {}
    dup = []
    for name, root in docs.items():
        seen = set()
        for el in root.iter():
            i = el.get("id")
            if i is not None:
                if i in seen:
                    dup.append(f"{name}#{i}")
                seen.add(i)
        ids[name] = seen
    g.line(not dup, "no id is used twice in a document", ", ".join(dup[:5]))
    links = dead = 0
    deads = []
    for name, root in docs.items():
        for el in root.iter():
            for attr in ("href", "src"):
                h = el.get(attr)
                if h is None or el.tag == f"{X}link" and h == "epub.css":
                    continue
                links += 1
                f, _, frag = h.partition("#")
                f = f or name
                if f not in manifest or (frag and frag not in ids.get(f, set())):
                    dead += 1
                    deads.append(f"{name} -> {h}")
    g.line(dead == 0, f"{links:,} links land on a file and an id in the package",
           f"{dead} dead: " + ", ".join(deads[:4]) if dead else "")

    # 4. round trip -------------------------------------------------------------
    texts = {(p, s, n): t for p, s, n, t in con.execute(
        "SELECT paper_n, section_n, para_n, text FROM paragraph")}
    seen_p, off = set(), []
    papers = sections = notes = noterefs = 0
    chips_para = chips_blanket = 0
    # A paper's notes stand after all its text, in the order of their markers:
    # one under its paragraph KOReader drew twice on a page.
    misplaced = []
    for name, root in docs.items():
        if not re.match(r"^p\d{3}\.xhtml$", name):
            continue
        refs, asides, text_after = [], [], False
        for el in root.iter():
            c = classes(el)
            if el.tag == f"{X}section" and "paper" in c:
                papers += 1
            elif el.tag == f"{X}section" and "sec" in c:
                sections += 1
                for b in el.iter(f"{X}div"):
                    if "blanket" in classes(b):
                        chips_blanket += sum(1 for _ in b.iter(f"{X}a"))
            elif el.tag == f"{X}aside" and el.get(f"{EPUB}type") == "footnote":
                notes += 1
                asides.append(el.get("id"))
            elif el.tag == f"{X}a" and el.get(f"{EPUB}type") == "noteref":
                noterefs += 1
                refs.append((el.get("href") or "").lstrip("#"))
            elif el.tag == f"{X}p" and "t" in c:
                text_after = text_after or bool(asides)
                m = RE_PID.match(el.get("id") or "")
                key = tuple(map(int, m.groups())) if m else None
                seen_p.add(key)
                if key not in texts or para_text(el) != texts[key]:
                    off.append(el.get("id"))
        if text_after or asides != refs:
            misplaced.append(name)
        for p in root.iter(f"{X}section"):
            if "sec" not in classes(p):
                continue
            for el in p:
                if el.tag == f"{X}p" and "ix" in classes(el):
                    chips_para += sum(1 for _ in el.iter(f"{X}a"))
    g.line(not off and seen_p == set(texts),
           f"{len(seen_p):,} of {len(texts):,} paragraphs round-trip to the stored text",
           f"{len(off)} differ, e.g. {off[:4]}; {len(set(texts) - seen_p)} missing" if off or seen_p != set(texts) else "")

    entries = {(s, a): t for s, a, t in con.execute(
        "SELECT CASE WHEN scope='az' THEN 'az' ELSE scope END, anchor, text FROM index_entry")}
    found, eoff = set(), []
    for name, root in docs.items():
        scope = ("az" if name.startswith("index-") else
                 name[4] if name.startswith("app-") else None)
        if scope is None:
            continue
        for el in root.iter():
            i = el.get("id")
            if i is None or (scope, i) not in entries:
                continue
            found.add((scope, i))
            if "".join(el.itertext()) != entries[(scope, i)]:
                eoff.append(f"{name}#{i}")
    g.line(not eoff and found == set(entries),
           f"{len(found):,} of {len(entries):,} index and appendix entries round-trip",
           f"{len(eoff)} differ, e.g. {eoff[:4]}; {len(set(entries) - found)} missing"
           if eoff or found != set(entries) else "")

    # 5. counts -----------------------------------------------------------------
    def count(q):
        return con.execute(q).fetchone()[0]
    g.line(papers == count("SELECT COUNT(*) FROM paper"), f"papers {papers}")
    g.line(sections == count("SELECT COUNT(*) FROM section"), f"sections {sections:,}")
    n_notes = count("SELECT COUNT(*) FROM footnote")
    g.line(notes == noterefs == n_notes, f"notes {notes}, 1955 readings and study notes,"
           f" each with its marker ({noterefs})")
    g.line(not misplaced, "every note stands at its paper's end, in the order of its marker",
           ", ".join(misplaced[:4]))
    heads = sum(1 for n, r in docs.items() if n.startswith("index-")
                for el in r.iter(f"{X}h2") if "l1" in classes(el))
    g.line(heads == count("SELECT COUNT(*) FROM index_entry WHERE scope='az' AND level=1"),
           f"headwords {heads:,}")
    want_para = want_blanket = 0
    for p, s in con.execute("SELECT paper_n, n FROM section"):
        rows = queries.section(con, p, s)
        want_para += sum(map(len, rows["citers"].values()))
        want_blanket += len(rows["blanket"]) + len(rows["paperwide"])
    g.line(chips_para == want_para, f"chips beneath paragraphs {chips_para:,}",
           f"the site has {want_para:,}" if chips_para != want_para else "")
    g.line(chips_blanket == want_blanket, f"chips at section heads {chips_blanket:,}",
           f"the site has {want_blanket:,}" if chips_blanket != want_blanket else "")
    cits = sum(1 for n, r in docs.items() if n.startswith(("index-", "app-"))
               for el in r.iter(f"{X}a") if "cit" in classes(el))
    want = sum(h.count('class="cit"') for (h,) in con.execute("SELECT text_html FROM index_entry"))
    g.line(cits == want, f"citations linked into the text {cits:,}",
           f"the database has {want:,}" if cits != want else "")

    # 6. fonts ------------------------------------------------------------------
    M = "{http://www.w3.org/1998/Math/MathML}"

    def goudy(el):
        """The text an element draws in UB Goudy: all of it but a <pre>, a
        study note's math (in Garamond-Math) and its Greek or Hebrew (in the
        reader's own font, as on the site: build/fonts.py SCRIPTS)."""
        if el.tag == f"{X}pre" or el.tag.startswith(M) or "lang" in classes(el):
            return
        yield el.text or ""
        for ch in el:
            yield from goudy(ch)
            yield ch.tail or ""
    drawn: set[str] = set()
    maths: list[str] = []
    for name, root in docs.items():
        body = root.find(f"{X}body")
        if body is not None:
            drawn.update("".join(goudy(body)))
            maths += [ET.tostring(m, encoding="unicode").replace("ns0:", "").replace(":ns0", "")
                      for m in body.iter(f"{M}math")]
    drawn = {c for c in drawn if unicodedata.category(c) not in ("Cc", "Zl", "Zp")}
    for face in ("fonts/UBGoudy.otf", "fonts/UBGoudy-Italic.otf"):
        font = TTFont(io.BytesIO(z.read(f"OEBPS/{face}")))
        have = {chr(c) for t in font["cmap"].tables for c in t.cmap}
        # What the site draws in another face on purpose (build/fonts.py), as
        # 42:5.1's γ, which the reader's own serif draws here.
        miss = sorted(drawn - have - set(ELSEWHERE))
        g.line(not miss, f"{face}: every one of the {len(drawn)} characters drawn",
               " ".join(f"{c} U+{ord(c):04X}" for c in miss[:12]))
    # The math as a browser draws it, its single letters in their italic.
    from build.texmath import drawn as math_drawn
    want = set().union(*(math_drawn(m) for m in maths))
    font = TTFont(io.BytesIO(z.read("OEBPS/fonts/GaramondMath.otf")))
    have = {chr(c) for t in font["cmap"].tables for c in t.cmap}
    miss = sorted(want - have)
    g.line(not miss, f"fonts/GaramondMath.otf: every one of the {len(want)} characters"
           f" of {len(maths)} expressions", " ".join(f"{c} U+{ord(c):04X}" for c in miss[:12]))

    # 7. determinism ------------------------------------------------------------
    files, info = pack.files(con)
    g.line(pack.zipped(files, info["date"]) == data,
           "the database builds this file again, byte for byte")

    # 8. epubcheck --------------------------------------------------------------
    g.line(*epubcheck(path))
    print("epub: " + ("every gate passes" if not g.failed else f"{g.failed} gate(s) FAIL"))
    return 1 if g.failed else 0


def epubcheck(path: pathlib.Path) -> tuple[bool, str, str]:
    java = shutil.which("java")
    if java is None:
        return False, "epubcheck", f"no java: sudo apt install {JAVA_PACKAGE}"
    if not EPUBCHECK.exists():
        return False, "epubcheck", f"no {EPUBCHECK}: `make epub` fetches it (EPUBCHECK= names another)"
    with tempfile.TemporaryDirectory() as tmp:
        report = pathlib.Path(tmp) / "report.json"
        subprocess.run([java, "-jar", str(EPUBCHECK), str(path), "--json", str(report)],
                       capture_output=True, text=True)
        if not report.exists():
            return False, "epubcheck", "wrote no report"
        r = json.loads(report.read_text())
    msgs = [m for m in r.get("messages", [])
            if m.get("severity") in ("FATAL", "ERROR", "WARNING")]
    ver = r.get("checker", {}).get("checkerVersion", "?")
    detail = "; ".join(
        f"{m['severity']} {m['ID']} {m['message'][:90]}"
        + (f" ({m['locations'][0].get('path')}:{m['locations'][0].get('line')})"
           if m.get("locations") else "") for m in msgs[:5])
    return not msgs, f"epubcheck {ver}: {len(msgs)} errors and warnings", detail
