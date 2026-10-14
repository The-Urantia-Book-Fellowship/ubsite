"""Rasterise ubsite/static/favicon.svg into the fallbacks browsers ask for by name.

    .venv/bin/python tools/make_icons.py

The SVG is the icon; Chrome, Firefox and Safari take it from the <link> in
base.html, and it carries its own dark-mode colour.  Two files are still
requested by fixed name, without any <link>:

    favicon.ico           16, 32 and 48 px, transparent, the light colours
    apple-touch-icon.png  180 px, OPAQUE on the site's paper colour -- iOS puts
                          a transparent icon on black and rounds the corners itself

and two more are named by /manifest.webmanifest, for a reader who installs the
site as an app (Read offline, in Settings):

    icon-192.png, icon-512.png   the touch icon's tile, at the sizes the
                                 manifest asks for

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
        subprocess.run(["magick", str(shot), "-crop", f"{size}x{size}+0+0", "+repage", str(out)],
                       check=True)


def main() -> int:
    svg = (STATIC / "favicon.svg").read_text()
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        pngs = []
        for n in (16, 32, 48):
            render(svg, n, t / f"{n}.png")
            pngs.append(str(t / f"{n}.png"))
        # TrueColorAlpha, or ImageMagick palettises an image this short of colours
        # and keeps a 1-bit mask: every antialiased edge goes hard.
        subprocess.run(["magick", *pngs, "-type", "TrueColorAlpha",
                        str(STATIC / "favicon.ico")], check=True)

    # The touch icon: the same drawing at about 70% on an opaque paper square.
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) \1"', svg)
    if not m:
        raise SystemExit("make_icons: favicon.svg needs a square viewBox starting at 0 0")
    n = float(m.group(1))
    p = round(n * 0.22, 2)
    tile = svg.replace(m.group(0) + ">",
                       f'viewBox="{-p:g} {-p:g} {n + 2 * p:g} {n + 2 * p:g}">'
                       f'<rect x="{-p:g}" y="{-p:g}" width="{n + 2 * p:g}" height="{n + 2 * p:g}" fill="{PAPER}"/>')
    render(tile, 180, STATIC / "apple-touch-icon.png")
    for n in (192, 512):
        render(tile, n, STATIC / f"icon-{n}.png")
    for f in ("favicon.ico", "apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        print(f"  {f:22} {(STATIC / f).stat().st_size:>6,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
