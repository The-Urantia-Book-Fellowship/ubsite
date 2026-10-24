"""Rasterise ubsite/static/favicon.svg into the fallbacks browsers ask for by name.

    .venv/bin/python tools/make_icons.py

The SVG is the icon; Chrome, Firefox and Safari take it from the <link> in
base.html, and it carries its own dark-mode colour.  Two files are still
requested by fixed name, without any <link>:

    favicon.ico           16, 32 and 48 px, transparent, the light colours
    apple-touch-icon.png  180 px, OPAQUE on the site's paper colour -- iOS puts
                          a transparent icon on black and rounds the corners itself

and two more are named by /manifest.webmanifest, for a reader who installs the
site as an app (the cloud's menu):

    icon-192.png, icon-512.png   the touch icon's tile, at the sizes the
                                 manifest asks for

The same build is live at two addresses, and an app installed from each looked
the same, as did a tab of each (Tigran, 2026-10-15).  So every icon is drawn
again for each variant in VARIANTS, with the book in another colour:
favicon-<variant>.svg and .ico, apple-touch-icon-<variant>.png and
icon-<size>-<variant>.png.  app.py SITES says which host takes which.  The
header's mark and the home page's logo are the same on every host.

Rendered by headless Chrome, so each fallback is exactly what Chrome draws from
the SVG, and assembled by ImageMagick.  Neither is a build dependency: run this
by hand when the SVG changes, and commit the outputs.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC = ROOT / "ubsite" / "static"
PAPER = "#f8f5f0"                     # --paper in ub.css
BOOK = ("#1b4a76", "#84afdc")         # the book's colours in favicon.svg, light and dark
# Each variant's book, light and dark.  Burgundy is ubsite.ddns.net's since
# 2026-10-24, ubsite.sigmaai.au being the main site, and was ubsite.sigmaai.au's
# until then: the site's other colour (the red letter's), chosen by Tigran from
# a comparison with green, the two colours swapped, and a lighter blue
# (https://claude.ai/artifact/1LdhRdAb9kPoQb5CkGY4B6).  Its dark colour is lifted
# from it as the blue's is in oklch: +0.34 lightness, chroma x0.89.
VARIANTS = {"burgundy": ("#7a2230", "#e58c92")}


def render(svg: str, size: int, out: pathlib.Path) -> None:
    """Draw ``svg`` at size x size with Chrome, cropped to exactly that."""
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        (t / "icon.svg").write_text(svg)
        (t / "page.html").write_text(
            '<!doctype html><body style="margin:0;background:transparent">'
            f'<img src="icon.svg" width="{size}" height="{size}" style="display:block">')
        shot = t / "shot.png"
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--default-background-color=00000000",
                        "--blink-settings=preferredColorScheme=1",      # light: the deep blue
                        f"--window-size={max(400, size)},{max(400, size)}", f"--screenshot={shot}",
                        str(t / "page.html")],
                       check=True, capture_output=True)
        drawn = t / "drawn.png"
        subprocess.run(["magick", str(shot), "-crop", f"{size}x{size}+0+0", "+repage", str(drawn)],
                       check=True)
        # ImageMagick stamps a PNG with the time it was written, so a drawing
        # that did not change would still be a new file, and an installed app
        # would be told its icon had.  Kept unless a pixel differs.
        if out.exists() and subprocess.run(["magick", "compare", "-metric", "AE", str(out), str(drawn), "null:"],
                                           capture_output=True).returncode == 0:
            return
        out.write_bytes(drawn.read_bytes())


def ico(svg: str, out: pathlib.Path) -> None:
    """The tab's icon for a browser that takes no SVG: 16, 32 and 48 px."""
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        pngs = []
        for n in (16, 32, 48):
            render(svg, n, t / f"{n}.png")
            pngs.append(str(t / f"{n}.png"))
        # TrueColorAlpha, or ImageMagick palettises an image this short of colours
        # and keeps a 1-bit mask: every antialiased edge goes hard.
        subprocess.run(["magick", *pngs, "-type", "TrueColorAlpha", str(out)], check=True)


def main() -> int:
    svg = (STATIC / "favicon.svg").read_text()
    if any(svg.count(c) != 2 for c in BOOK):
        raise SystemExit(f"make_icons: favicon.svg should colour the book and its edge {BOOK[0]}, "
                         f"and {BOOK[1]} in dark mode")
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) \1"', svg)
    if not m:
        raise SystemExit("make_icons: favicon.svg needs a square viewBox starting at 0 0")
    made = []
    for variant, colours in [("", BOOK), *VARIANTS.items()]:
        suffix = f"-{variant}" if variant else ""
        drawn = svg.replace(BOOK[0], colours[0]).replace(BOOK[1], colours[1])
        if variant:
            first, rest = drawn.split("\n", 1)
            drawn = (f"{first}\n  <!-- favicon.svg with a {variant} book, written by tools/make_icons.py:"
                     f" edit that, not this. -->\n{rest}")
            out = STATIC / f"favicon{suffix}.svg"
            if not out.exists() or out.read_text() != drawn:
                out.write_text(drawn)
            made.append(out.name)
        ico(drawn, STATIC / f"favicon{suffix}.ico")
        made.append(f"favicon{suffix}.ico")

        # The touch icon: the same drawing at about 70% on an opaque paper square.
        n = float(m.group(1))
        p = round(n * 0.22, 2)
        tile = drawn.replace(m.group(0) + ">",
                             f'viewBox="{-p:g} {-p:g} {n + 2 * p:g} {n + 2 * p:g}">'
                             f'<rect x="{-p:g}" y="{-p:g}" width="{n + 2 * p:g}" height="{n + 2 * p:g}" fill="{PAPER}"/>')
        for name, n in ((f"apple-touch-icon{suffix}.png", 180), (f"icon-192{suffix}.png", 192),
                        (f"icon-512{suffix}.png", 512)):
            render(tile, n, STATIC / name)
            made.append(name)
    for f in made:
        print(f"  {f:31} {(STATIC / f).stat().st_size:>6,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
