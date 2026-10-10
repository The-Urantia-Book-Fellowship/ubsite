"""Draw the EPUB's cover: the site's mark and the title, on the site's paper.

    .venv/bin/python tools/make_cover.py      -> epub/cover.jpg

1600 x 2560, the proportion Kindle and Apple Books ask for.  The mark is
ubsite/static/favicon.svg in its light colours, and the title is set in UB
Goudy from the site's own subset, so the cover is the site's face, not a
lookalike.  Never the Foundation's concentric circles (CLAUDE.md §10.2).

Rendered by headless Chrome and converted by ImageMagick, as tools/make_icons.py
does.  Neither is a build dependency: run this by hand when the mark or the
wording changes, and commit the output.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC = ROOT / "ubsite" / "static"
OUT = ROOT / "epub" / "cover.jpg"
W, H = 1600, 2560
PAPER = "#f8f5f0"                     # --paper in ub.css
INK = "#1f1d1a"

PAGE = """<!doctype html><meta charset="utf-8">
<style>
@font-face {{ font-family: Goudy; src: url({fonts}/UBGoudy.woff2); }}
@font-face {{ font-family: Goudy; font-style: italic; src: url({fonts}/UBGoudy-Italic.woff2); }}
html, body {{ margin: 0; width: {w}px; height: {h}px; background: {paper}; }}
body {{ font-family: Goudy; color: {ink}; text-align: center; position: relative; }}
.frame {{ position: absolute; inset: 70px; border: 3px solid #1b4a76; }}
.inner {{ position: absolute; inset: 86px; border: 1px solid #1b4a76; }}
svg {{ position: absolute; left: 50%; top: 520px; width: 560px; height: 560px;
       margin-left: -280px; }}
h1 {{ position: absolute; left: 0; right: 0; top: 1170px; margin: 0;
      font-weight: normal; font-size: 168px; line-height: 1.1; letter-spacing: 10px; }}
p {{ position: absolute; left: 160px; right: 160px; top: 1900px; margin: 0;
     font-style: italic; font-size: 68px; line-height: 1.35; }}
</style>
<div class="frame"></div><div class="inner"></div>
{svg}
<h1>THE<br>URANTIA<br>BOOK</h1>
<p>The text, read together with its index</p>
"""


def main() -> int:
    svg = (STATIC / "favicon.svg").read_text()
    svg = re.sub(r"\s*@media.*?\}\s*\}", "", svg, flags=re.S)   # the light colours only
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        (t / "cover.html").write_text(PAGE.format(
            fonts=(STATIC / "fonts").as_uri(), w=W, h=H, paper=PAPER, ink=INK, svg=svg))
        shot = t / "cover.png"
        subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--allow-file-access-from-files",
                        f"--window-size={W},{H}", f"--screenshot={shot}",
                        (t / "cover.html").as_uri()],
                       check=True, capture_output=True)
        subprocess.run(["magick", str(shot), "-crop", f"{W}x{H}+0+0", "+repage",
                        "-strip", "-quality", "90", "-sampling-factor", "4:2:0",
                        str(OUT)], check=True)
    print(f"  {OUT.relative_to(ROOT)}  {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
