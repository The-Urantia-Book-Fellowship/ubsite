"""Does Chrome play a recording from the place it is asked for?  (2026-11-12)

A paragraph's ▶ sets the player's clock to the paragraph's cut and plays.
Where a file gives the browser no length, the browser takes one from its bit
rate, and finds a place by proportion in a file it has the wrong length of:
Григорий Войнер's 181-02.mp3, 2,180.8 s long, was taken for 2,170.6 s, and
asked for 1,962.7 s Chrome played from 1,972 s, nine seconds into the
paragraph.  Such a file is now sent with an Info frame (build/mp3.py), and
this is the test that it is enough, by ear: it sets an <audio>'s clock to
four places in each file, takes what is then played through Web Audio, and
looks for that sound in the whole file as decodeAudioData decodes it, which is
exact.  The clock and the sound must agree, to within what the measuring
itself adds, a quarter of a second, the same for every file.  How like the
file the sound taken is says how far to trust the place found: 0.8 or more,
where the next likest place in the file is 0.26 to 0.45; a place is heard up
to three times, since Web Audio now and then loses a block of the sound on
the way (2026-11-13: one place in forty at 0.56 to 0.78, the place found
right all the same).

    .venv/bin/python tools/audio/seek_e2e.py        (after make data)

It asks for the files of each reading named below: one of Merritt Horn's,
sent as it is, and of Войнер's the longest of those sent with a frame, a
short one of them, one at 192 kbit/s and one that needed no frame.  The file
the browser is sent must also be as long as the database lists it.

Playwright is in .venv as a dev requirement and drives the system's Chrome.
It runs the app itself on 127.0.0.1:8136 with the visit counter off and no
offline copy, and leaves the dev server alone.  Not a gate, like
tools/preview_e2e.py: it needs the recordings and takes two minutes;
tests/test_mp3.py holds the frame and the route to the byte.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PORT = "8136"
BASE = "http://127.0.0.1:" + PORT
FILES = ["/audio/mh/paper001/P001_01.mp3", "/audio/voyner/181-02.mp3", "/audio/voyner/136-10.mp3",
         "/audio/voyner/03-00.mp3", "/audio/voyner/01-01.mp3"]
# What the measuring adds between the clock's reading and the sound's arrival,
# and how far from it a place may be.
LATENCY, SLACK = -0.26, 0.15
fails: list[str] = []

JS = """
async ([url, fracs]) => {
  const ctx = new AudioContext({ sampleRate: 16000 });
  const raw = await (await fetch(url)).arrayBuffer();
  const bytes = raw.byteLength;
  const full = (await ctx.decodeAudioData(raw)).getChannelData(0);
  const a = new Audio(url);
  a.preload = 'auto';
  await new Promise(r => { a.addEventListener('canplay', r, { once: true }); a.load(); });
  const said = a.duration;
  const src = ctx.createMediaElementSource(a);
  const rec = ctx.createScriptProcessor(4096, 1, 1);
  let take = null;
  rec.onaudioprocess = e => { if (take) take(e.inputBuffer.getChannelData(0)); };
  src.connect(rec); rec.connect(ctx.destination);
  await ctx.resume();
  const out = { bytes, decoded: full.length / 16000, said, seeks: [] };
  for (const f of fracs) {
    const t = Math.round(f * (full.length / 16000) * 10) / 10;
    // Up to three hearings, the likest kept: a block of sound lost on its way
    // through Web Audio leaves the half second less like the file, 0.56 where
    // another hearing of the same place is 0.98, the place found being the same.
    let kept = null;
    for (let k = 0; k < 3 && !(kept && kept.corr > 0.9); k++) {
    a.pause();
    await new Promise(r => { a.addEventListener('seeked', r, { once: true }); a.currentTime = t; });
    // Three seconds from the moment the clock moves, with the clock's reading at the first block.
    const got = new Float32Array(16000 * 3); let n = 0, at = null;
    const done = new Promise(r => { take = blk => {
      if (at === null) { if (a.paused || a.currentTime <= t) return; at = a.currentTime; }
      got.set(blk.subarray(0, Math.min(blk.length, got.length - n)), n); n += blk.length;
      if (n >= got.length) { take = null; r(); }
    }; });
    await a.play();
    await done;
    a.pause();
    // Its loudest half second, looked for in the whole file within 25 s of the place.
    let best = 0, bi = 0;
    for (let i = 0; i + 8000 <= got.length; i += 800) {
      let e = 0; for (let j = i; j < i + 8000; j += 4) e += got[j] * got[j];
      if (e > best) { best = e; bi = i; }
    }
    const chunk = got.subarray(bi, bi + 8000);
    const lo = Math.max(0, Math.floor((at - 25) * 16000)), hi = Math.min(full.length - 8000, Math.floor((at + 25) * 16000));
    let top = -1, where = -1;
    const cs = new Float32Array(Math.max(0, Math.ceil((hi - lo) / 2)));
    for (let o = lo; o < hi; o += 2) {
      let s = 0, e = 0;
      for (let j = 0; j < 8000; j += 8) { s += chunk[j] * full[o + j]; e += full[o + j] * full[o + j]; }
      const c = e > 0 ? s / Math.sqrt(e) : 0;
      cs[(o - lo) / 2] = c;
      if (c > top) { top = c; where = o; }
    }
    // And the likest place that is not that one: half a second from it or more.
    let next = -1;
    for (let o = lo; o < hi; o += 2) if (Math.abs(o - where) > 8000 && cs[(o - lo) / 2] > next) next = cs[(o - lo) / 2];
    let ce = 0; for (let j = 0; j < 8000; j += 8) ce += chunk[j] * chunk[j];
    const norm = Math.sqrt(ce || 1);
    const m = { t, clock: at + bi / 16000, truly: where / 16000, corr: top / norm, next: next / norm, tries: k + 1 };
    if (!kept || m.corr > kept.corr) kept = m;
    }
    kept.tries = Math.max(kept.tries, 1);
    out.seeks.push(kept);
  }
  return out;
}
"""


def ok(cond, what):
    print(("  ok  " if cond else "  FAIL") + " " + what)
    if not cond:
        fails.append(what)


def listed() -> dict[str, tuple[int, int]]:
    """{address: (bytes as sent, duration in ms)} for the files asked for."""
    con = sqlite3.connect(f"file:{ROOT / 'var' / 'ub.db'}?mode=ro", uri=True)
    return {f"/audio/{key}/{name}": (b, d) for key, name, b, d in con.execute(
        "SELECT s.key, f.name, f.bytes + COALESCE(LENGTH(f.head), 0), f.duration_ms"
        " FROM audio_file f JOIN audio_source s ON s.id = f.source_id")}


def run() -> int:
    want = listed()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required"])
        pg = b.new_context().new_page()
        pg.goto(BASE + "/healthz")
        for url in FILES:
            if url not in want:
                ok(False, f"{url} is a file of the database's")
                continue
            r = pg.evaluate(JS, [url, [0.1, 0.5, 0.9, 0.3]])
            size, ms = want[url]
            print(f"\n{url}: {r['bytes']:,} bytes, {r['decoded']:.2f} s decoded")
            ok(r["bytes"] == size, f"it is sent as long as the database lists it ({size:,} bytes)")
            ok(abs(r["said"] - ms / 1000) < 0.06 and abs(r["decoded"] - ms / 1000) < 0.06,
               f"the browser takes it for its length: {r['said']:.2f} s, listed {ms / 1000:.2f} s")
            for s in r["seeks"]:
                late = s["truly"] - s["clock"]
                ok(s["corr"] > 0.8 and abs(late - LATENCY) <= SLACK,
                   f"asked for {s['t']:7.1f} s it plays that place: the clock's {s['clock']:8.2f} is"
                   f" {s['truly']:8.2f} of the file, {late - LATENCY:+.2f} s off (heard alike {s['corr']:.2f},"
                   f" the next likest place {s['next']:.2f})")
        b.close()
    return 1 if fails else 0


# The server with no offline copy to offer, so that no page registers the
# worker and fetches the copy (tools/runhead_e2e.py NO_COPY).
NO_COPY = """
import pathlib, sys
import uvicorn
import ubsite.app as A
A.OFFLINE = pathlib.Path(sys.argv[1])
uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def main() -> int:
    env = dict(os.environ, UB_VISITS="off")
    srv = subprocess.Popen([str(ROOT / ".venv" / "bin" / "python"), "-c", NO_COPY,
                            str(ROOT / "var" / "no-offline-copy"), PORT], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        return run()
    finally:
        srv.terminate()
        srv.wait()


if __name__ == "__main__":
    rc = main()
    print("FAILED: " + "; ".join(fails) if fails else "all good")
    sys.exit(rc)
