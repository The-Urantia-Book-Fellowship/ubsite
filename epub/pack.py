"""The documents, packaged: OPF, navigation, fonts, cover, and the zip.

Deterministic by construction, so that the same database gives the same file
byte for byte: the zip's entries are sorted and stamped with the sources' own
date, the modification time is that date too, and nothing reads the clock.
A rebuild that changes nothing changes no byte, and a reader that already
holds the book sees an update only when there is one.
"""

from __future__ import annotations

import io
import pathlib
import uuid
import zipfile

from fontTools.ttLib import TTFont

from . import book

ROOT = book.ROOT
HERE = book.HERE
FONTS = ROOT / "ubsite" / "static" / "fonts"
COVER = HERE / "cover.jpg"
OUT = ROOT / "var" / "epub" / "the-urantia-book.epub"

# One identifier for every build, so that Apple Books and Kobo take a new
# build for a new version of the same book -- keeping the reader's place,
# highlights and notes -- rather than a second copy beside the first.
UID = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "https://ubsite.ddns.net/epub/the-urantia-book"))

FACES = [("UBGoudy.woff2", "fonts/UBGoudy.otf"),
         ("UBGoudy-Italic.woff2", "fonts/UBGoudy-Italic.otf")]

MEDIA = {".xhtml": "application/xhtml+xml", ".css": "text/css", ".otf": "font/otf",
         ".jpg": "image/jpeg", ".ncx": "application/x-dtbncx+xml"}


def otf(woff2: pathlib.Path) -> bytes:
    """The site's subset, unwrapped.  WOFF2 holds a CFF font losslessly, and
    an e-reader is surer of OpenType than of WOFF2."""
    font = TTFont(str(woff2), recalcTimestamp=False)
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _number(toc) -> int:
    """Each NCX entry its id, and its playOrder, depth first from 1.

    Two entries that open the same place share a playOrder, as the NCX
    requires -- "Index" and its first letter, "Appendices" and Appendix A --
    but never an id.  Returns the depth of the tree.
    """
    orders: dict[str, int] = {}
    count = 0

    def walk(nodes) -> int:
        nonlocal count
        depth = 0
        for n in nodes:
            count += 1
            n["id"] = f"n{count}"
            n["order"] = orders.setdefault(n["href"], len(orders) + 1)
            if n["kids"]:
                depth = max(depth, walk(n["kids"]))
        return depth + 1
    return walk(toc)


def files(con) -> tuple[dict[str, bytes], dict]:
    """Every file of the package, by its path in the zip, and some figures."""
    docs, meta = book.documents(con)
    e = book.env(book.H.Hrefs(con))
    src = meta["sources"]
    date = max(s["date"] for s in src.values())

    out: dict[str, bytes] = {}
    for d in docs:
        out[f"OEBPS/{d.name}"] = d.xhtml.encode("utf-8")
    out["OEBPS/epub.css"] = (HERE / "epub.css").read_bytes()
    for woff2, name in FACES:
        out[f"OEBPS/{name}"] = otf(FONTS / woff2)
    if not COVER.exists():
        raise FileNotFoundError(f"{COVER}: run tools/make_cover.py")
    out["OEBPS/cover.jpg"] = COVER.read_bytes()

    depth = _number(meta["toc"])
    out["OEBPS/nav.xhtml"] = e.get_template("nav.xhtml").render(
        toc=meta["toc"], landmarks=meta["landmarks"]).encode("utf-8")
    out["OEBPS/toc.ncx"] = e.get_template("toc.ncx").render(
        uid=UID, depth=depth, toc=meta["toc"]).encode("utf-8")

    items = [{"id": "nav", "href": "nav.xhtml", "properties": "nav"},
             {"id": "ncx", "href": "toc.ncx"},
             {"id": "css", "href": "epub.css"},
             {"id": "cover-image", "href": "cover.jpg", "properties": "cover-image"},
             *({"id": pathlib.PurePath(n).stem.replace(".", "-"), "href": n} for _, n in FACES)]
    spine = []
    for d in docs:
        i = {"id": "x-" + d.name.removesuffix(".xhtml"), "href": d.name,
             "properties": d.properties, "linear": d.linear}
        items.append(i)
        spine.append(i)
    for i in items:
        i["type"] = MEDIA[pathlib.PurePath(i["href"]).suffix]
        i.setdefault("properties", "")
    labels = {"press": "The Uversa Press text", "index": "The Uversa Press index"}
    out["OEBPS/package.opf"] = e.get_template("package.opf").render(
        uid=UID, date=date, modified=f"{date}T00:00:00Z", items=items, spine=spine,
        sources=[f"{labels.get(k, k)}, commit {s['commit']} of {s['date']}"
                 + (", with uncommitted changes" if s["dirty"] else "")
                 for k, s in sorted(src.items())]).encode("utf-8")
    out["META-INF/container.xml"] = e.get_template("container.xml").render().encode("utf-8")
    return out, {"date": date, "documents": len(docs)}


def zipped(out: dict[str, bytes], date: str) -> bytes:
    """The zip, mimetype first and stored, then everything else, sorted."""
    stamp = tuple(int(x) for x in date.split("-")) + (0, 0, 0)

    def info(name, compress):
        z = zipfile.ZipInfo(name, date_time=stamp)
        z.compress_type = compress
        z.external_attr = 0o644 << 16
        z.create_system = 3
        return z
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(info("mimetype", zipfile.ZIP_STORED), b"application/epub+zip")
        for name in sorted(out):
            z.writestr(info(name, zipfile.ZIP_DEFLATED), out[name], compresslevel=9)
    return buf.getvalue()


def write(data: bytes, path: pathlib.Path) -> None:
    """Into var/epub/, by way of a temporary name: a failed build leaves the
    last good book where it was."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
