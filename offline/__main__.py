"""python -m offline build | check   (see offline/__init__.py)"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m offline")
    ap.add_argument("cmd", choices=["build", "check"])
    a = ap.parse_args()
    from . import site  # noqa: F401  -- first: it turns the visit counter off
    from ubsite import app as A
    if a.cmd == "build":
        from . import pack
        t = time.time()
        m = pack.build(A.db())
        kinds: dict[str, list[int]] = {}
        for c in m["chunks"]:
            k = kinds.setdefault(c["kind"], [0, 0, 0])
            k[0] += 1
            k[1] += c["bytes"]
            k[2] += c["raw"]
        print(f"var/offline/: build {m['build']}, {m['counts']['pages']:,} pages,"
              f" {len(m['chunks'])} chunks ({time.time() - t:.1f} s)")
        for k, (n, gz, raw) in kinds.items():
            print(f"  {k:6} {n:4}  {gz / 1e6:6.2f} MB to download and keep, {raw / 1e6:6.2f} MB unpacked")
        print(f"  total        {m['bytes'] / 1e6:6.2f} MB to download and keep, {m['raw'] / 1e6:6.2f} MB unpacked")
        return 0
    from . import check
    return check.run(A.db())


if __name__ == "__main__":
    sys.exit(main())
