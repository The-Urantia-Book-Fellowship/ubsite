"""Rasterise ubsite/static/favicon.svg into the fallbacks browsers ask for by name.

    .venv/bin/python tools/make_icons.py

The SVG is the icon; Chrome, Firefox and Safari take it from the <link> in
base.html, and it carries its own dark-mode colour.  Two files are still
requested by fixed name, without any <link>:

    favicon.ico           16, 32 and 48 px, transparent, the light colours
    apple-touch-icon.png  180 px, OPAQUE on the site's paper colour -- iOS puts
                          a transparent icon on black and rounds the corners itself

Rendered by headless Chrome, so each fallback is exactly what Chrome draws from
the SVG, and assembled by ImageMagick.  Neither is a build dependency: run this
by hand when the SVG changes, and commit the outputs.
"""

from __future__ import annotations

import pathlib
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
                        "--window-size=400,400", f"--screenshot={shot}", str(t / "page.html")],
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
    tile = svg.replace('viewBox="0 0 32 32">',
                       f'viewBox="-7 -7 46 46"><rect x="-7" y="-7" width="46" height="46" fill="{PAPER}"/>')
    render(tile, 180, STATIC / "apple-touch-icon.png")
    for f in ("favicon.ico", "apple-touch-icon.png"):
        print(f"  {f:22} {(STATIC / f).stat().st_size:>6,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
