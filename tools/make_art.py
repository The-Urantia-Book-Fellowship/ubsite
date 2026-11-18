"""Make the pictures of the home page's four part cards from their masters.

    .venv/bin/python tools/make_art.py

data/art/ holds the masters as Tigran made them (data/art/README.md): four
JPEGs of 2752 x 1536, 3 MB each, which no reader is sent and which are not
committed.  This writes what the cards name (templates/home.html),

    ubsite/static/art/part<N>-<width>.webp      N 1 to 4, at each of WIDTHS

and data/art/MANIFEST.tsv, which names every master and every file made from
it by its SHA-256, size and settings; tests/test_art.py holds the served files
to it, and the masters too where they are present.

Two widths, since what a screen needs follows its pixels and not its kind
(Tigran, 2026-11-18: "the images are currently 3 MB each in size. I hope you
will prepare optimal sizes for desktop and phone").  A card is 290 to 630 CSS
pixels wide: an ordinary desk monitor, one device pixel to each, takes the 640;
a phone, three to each, and a dense laptop, two, want 720 to 1250 across and
take the 1280.  The larger is made at the lower quality: on a dense screen a
picture's pixel is a half or a third of what the eye resolves, and what a
coarser setting loses is not seen there, while the smaller is shown pixel for
pixel.  Looked at side by side with the masters at twice their size, 2026-11-18:
the thin gold lines, the star fields and Part IV's sky hold at both settings.
-sharp_yuv keeps a thin coloured line its colour.

cwebp (libwebp) does the work.  It is not a build dependency: run this by hand
when a master changes, look at the result, and commit the outputs.  A file
whose bytes did not change is left alone, so that a run with the same cwebp
moves nothing; another release of libwebp may encode otherwise, which the
manifest's own line for it, and git, will show.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MASTERS = ROOT / "data" / "art"
OUT = ROOT / "ubsite" / "static" / "art"
MANIFEST = MASTERS / "MANIFEST.tsv"

# The parts, by the master's name as it came.
PARTS = {1: "partI.jpeg", 2: "partII.jpeg", 3: "partIII.jpeg", 4: "partIV.jpeg"}
# width -> cwebp's quality (the docstring says why the larger has the lower).
WIDTHS = {640: 82, 1280: 74}
CWEBP = ["-quiet", "-m", "6", "-sharp_yuv", "-metadata", "none"]


def served(n: int, width: int) -> str:
    """The name a card's picture is served under, in ubsite/static/."""
    return f"art/part{n}-{width}.webp"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jpeg_size(data: bytes) -> tuple[int, int]:
    """A JPEG's width and height, from its frame header."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            raise ValueError("a JPEG with no marker where one is due")
        marker = data[i + 1]
        if marker == 0xFF:                      # fill bytes before a marker
            i += 1
            continue
        if 0xD0 <= marker <= 0xD9 or marker == 0x01:
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        # A frame header: SOF0 to SOF15, but not DHT (C4), JPG (C8) or DAC (CC).
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + length
    raise ValueError("a JPEG with no frame header")


def webp_size(data: bytes) -> tuple[int, int]:
    """A lossy WebP's width and height, as cwebp writes one with no metadata:
    RIFF, WEBP, and one 'VP8 ' chunk whose frame header has both."""
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP")
    if data[12:16] != b"VP8 " or data[23:26] != b"\x9d\x01\x2a":
        raise ValueError("a WebP that is not one plain lossy frame")
    width, height = struct.unpack("<HH", data[26:30])
    return width & 0x3FFF, height & 0x3FFF


def encode(cwebp: str, master: pathlib.Path, width: int, quality: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "out.webp"
        subprocess.run([cwebp, *CWEBP, "-q", str(quality), "-resize", str(width), "0", str(master), "-o", str(out)],
                       check=True)
        return out.read_bytes()


def main() -> int:
    cwebp = shutil.which("cwebp")
    if cwebp is None:
        print("make_art: cwebp is not installed (Debian and Ubuntu: the package `webp`)", file=sys.stderr)
        return 1
    version = subprocess.run([cwebp, "-version"], capture_output=True, text=True, check=True).stdout.split()[0]
    OUT.mkdir(parents=True, exist_ok=True)
    rows, made = [], 0
    for n, name in PARTS.items():
        master = MASTERS / name
        if not master.exists():
            print(f"make_art: {master.relative_to(ROOT)} is missing", file=sys.stderr)
            return 1
        data = master.read_bytes()
        w, h = jpeg_size(data)
        rows.append((f"data/art/{name}", sha(data), len(data), w, h, "-", "-"))
        for width, quality in WIDTHS.items():
            new = encode(cwebp, master, width, quality)
            ww, hh = webp_size(new)
            if ww != width:
                raise SystemExit(f"make_art: asked for {width} across, cwebp made {ww}")
            target = ROOT / "ubsite" / "static" / served(n, width)
            if not target.exists() or target.read_bytes() != new:
                target.write_bytes(new)
                made += 1
            rows.append((f"ubsite/static/{served(n, width)}", sha(new), len(new), ww, hh, name,
                         f"cwebp {' '.join(CWEBP[1:])} -q {quality} -resize {width} 0"))
    want = {ROOT / r[0] for r in rows}
    stray = sorted(p.name for p in OUT.iterdir() if p not in want)
    if stray:
        print(f"make_art: in {OUT.relative_to(ROOT)} and made from no master: {', '.join(stray)}", file=sys.stderr)
        return 1
    text = ("# The home page's part pictures: each master (data/art/README.md) and each file\n"
            "# made from it, by tools/make_art.py.  Do not edit: run the tool.\n"
            f"# cwebp {version}\n"
            "file\tsha256\tbytes\twidth\theight\tfrom\tmade by\n"
            + "".join("\t".join(str(x) for x in r) + "\n" for r in rows))
    if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != text:
        MANIFEST.write_text(text, encoding="utf-8")
    total = sum(r[2] for r in rows if r[5] != "-")
    for r in rows:
        if r[5] != "-":
            print(f"  {r[0]:42} {r[3]:>5} x {r[4]:<4} {r[2] / 1000:7.1f} KB")
    print(f"{len(rows) - len(PARTS)} files, {total / 1e6:.2f} MB in all, {made} written anew; "
          f"the masters {sum(r[2] for r in rows if r[5] == '-') / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
