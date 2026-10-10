"""python -m epub build | check   (see epub/__init__.py)"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time

from . import book, pack

DB = pack.ROOT / "var" / "ub.db"


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m epub")
    ap.add_argument("cmd", choices=["build", "check"])
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--out", default=str(pack.OUT))
    a = ap.parse_args()
    out = pack.pathlib.Path(a.out)
    if a.cmd == "build":
        t = time.time()
        con = book.connect(pack.pathlib.Path(a.db))
        files, info = pack.files(con)
        pack.write(pack.zipped(files, info["date"]), out)
        size = out.stat().st_size
        print(f"{out.relative_to(pack.ROOT) if out.is_relative_to(pack.ROOT) else out}:"
              f" {info['documents']} documents, {len(files)} files,"
              f" {sum(map(len, files.values())) / 1e6:.1f} MB unpacked,"
              f" {size / 1e6:.1f} MB  ({time.time() - t:.1f} s)")
        print(f"sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
        return 0
    from . import check
    return check.run(book.connect(pack.pathlib.Path(a.db)), out)


if __name__ == "__main__":
    sys.exit(main())
