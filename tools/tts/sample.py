"""Sections of the AI voice as a listening page: the text as the site sets it,
the reading beside it, and a way to mark a problem at the moment it is heard.

    python3 -m tools.tts.sample OUT 1 30:1 30:2 144:3 144:5          # from var/tts/trial/
    python3 -m tools.tts.sample OUT --made data/audio 101 133:2      # from the whole book

A spec is a paper ("1", all its sections) or a section ("30:1").  OUT gets
index.html, the section MP3s under audio/ and the book's typeface under
fonts/, ready to publish as an artifact with those files beside it.  The page
plays as the site does -- a file per section, a paragraph highlighted as it is
read, any paragraph a place to start -- except that it carries on into the
next section, for listening at length.  Marks go to the artifact's store
(collection "marks"), where they can be read back.  Stdlib only.
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import shutil
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
AUDIO = ROOT / "var" / "audio" / "ai" / "higgs3_mature"
FONTS = ROOT / "ubsite" / "static" / "fonts"
PAGE = pathlib.Path(__file__).with_name("sample.html")


def rows(path: pathlib.Path) -> list[list[str]]:
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    return [l.split("\t") for l in lines[1:]]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("specs", nargs="+", help='a paper ("1") or a section ("30:1")')
    ap.add_argument("--made", type=pathlib.Path, default=ROOT / "var" / "tts" / "trial",
                    help="the directory holding ai.tsv and ai-files.tsv")
    ap.add_argument("--title", default="The AI Voice, Read Through")
    ap.add_argument("--lede", default="", help="HTML for the introduction")
    args = ap.parse_args(argv)

    segs: dict[str, list] = {}                      # file -> [[ref|None, start, end], ...]
    for ref, name, a, b, _sha in rows(args.made / "ai.tsv"):
        segs.setdefault(name, []).append([ref, int(a), int(b)])
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    para = dict(con.execute("SELECT ref, html FROM paragraph WHERE edition_id ="
                            " (SELECT id FROM edition WHERE code = 'press')"))
    titles = {(p, n): (t, pt) for p, n, t, pt in con.execute(
        "SELECT s.paper_n, s.n, s.title, p.title FROM section s JOIN paper p ON p.id = s.paper_id")}
    want = []
    for spec in args.specs:
        p, _, s = spec.partition(":")
        want += [(int(p), int(s))] if s else sorted(k for k in titles if k[0] == int(p))

    sections, out_audio = [], args.out / "audio"
    out_audio.mkdir(parents=True, exist_ok=True)
    for p, n in want:
        name = next((f for f in segs if f.startswith(f"paper{p:03d}/{p:03d}_{n:02d}.")), None)
        if name is None:
            print(f"{p}:{n} has not been assembled", file=sys.stderr)
            return 1
        local = f"audio/{p:03d}_{n:02d}.mp3"
        shutil.copyfile(AUDIO / name, args.out / local)
        title, paper_title = titles[(p, n)]
        sections.append({
            "id": f"s{p}-{n}", "paper": p, "n": n, "file": local,
            "heading": f"Paper {p}. {paper_title}" if n == 0 else f"{n}. {title}",
            "segs": [[r if ":" in r and "." in r else None, a, b] for r, a, b in segs[name]],
            "paras": {r: para[r] for r, _a, _b in segs[name] if "." in r},
        })
    (args.out / "fonts").mkdir(exist_ok=True)
    for f in ("UBGoudy.woff2", "UBGoudy-Italic.woff2"):
        shutil.copyfile(FONTS / f, args.out / "fonts" / f)

    body = []
    for s in sections:
        body.append(f'<section class="sec" id="{s["id"]}" aria-labelledby="{s["id"]}-h">'
                    f'<h2 id="{s["id"]}-h"><button class="go" type="button" data-sec="{s["id"]}"'
                    f' aria-label="Listen from the start of {html.escape(s["heading"])}"></button>'
                    f'{html.escape(s["heading"])}</h2>')
        for ref, _a, _b in s["segs"]:
            if ref:
                body.append(f'<p class="t" id="p{ref.replace(":", "-").replace(".", "_")}" data-ref="{ref}">'
                            f'<a class="num">{ref}</a><button class="go" type="button" data-ref="{ref}"'
                            f' aria-label="Listen from {ref}"></button>{s["paras"][ref]}</p>')
        body.append("</section>")
    data = [{k: s[k] for k in ("id", "paper", "n", "file", "heading", "segs")} for s in sections]
    page = PAGE.read_text(encoding="utf-8")
    page = (page.replace("{{TITLE}}", html.escape(args.title))
                .replace("{{LEDE}}", args.lede)
                .replace("{{BODY}}", "\n".join(body))
                .replace("{{DATA}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    (args.out / "index.html").write_text(page, encoding="utf-8")
    mb = sum(f.stat().st_size for f in out_audio.glob("*.mp3")) / 1e6
    print(f"{args.out / 'index.html'}: {len(sections)} sections, {mb:.1f} MB of audio")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
