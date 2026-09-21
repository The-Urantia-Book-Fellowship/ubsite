#!/usr/bin/env bash
# Push ubsite to pi5 and restart it there.
#
#   ./deploy/deploy.sh                 build the database here, ship it, restart
#   ./deploy/deploy.sh --no-data       ship code only, leave the database alone
#   ./deploy/deploy.sh --no-restart    ship, do not restart
#   UBSITE_HOST=other ./deploy/deploy.sh
#
# The three source repositories are NOT on pi5, and do not need to be: the
# database is the artifact. `make data` runs here, where the LaTeX lives, and
# var/ub.db is shipped. pi5 needs no TeX, no sources, and no build.
#
# Everything below is unprivileged. The four steps that need root are listed in
# deploy/README.md and are not run from here -- see that file for why.
set -euo pipefail

HOST="${UBSITE_HOST:-pi5}"
DEST="${UBSITE_DEST:-/home/tigran/ubsite}"
UV="${UBSITE_UV:-/home/tigran/.local/bin/uv}"   # pi5 has uv here, not /usr/local/bin
PORT="${UBSITE_PORT:-8130}"                     # 8000 and 8090 are taken on pi5
BUILD=1
RESTART=1

for arg in "$@"; do
    case "$arg" in
        --no-data)    BUILD=0 ;;
        --no-restart) RESTART=0 ;;
        *) echo "usage: $(basename "$0") [--no-data] [--no-restart]" >&2; exit 2 ;;
    esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

# Refuse to deploy this tree onto itself. libnodes learned this the hard way:
# on a box that is both the development machine and the deployment, the reflex
# `./deploy/deploy.sh` becomes an rsync --delete against a live tree.
if [ "$(hostname -s)" = "$HOST" ] && [ "$HERE" = "$DEST" ]; then
    echo "refusing: this IS $HOST:$DEST" >&2
    exit 1
fi

if [ "$BUILD" = 1 ]; then
    echo "==> building the database here"
    make data
    make check
fi

echo "==> rsync to $HOST:$DEST"
# Excluded: .venv (per-architecture, the target builds its own), var/ except the
# database, and everything only the build needs.
rsync -az --delete \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude 'var/' \
    --exclude 'export/' \
    "$HERE"/ "$HOST:$DEST"/

if [ "$BUILD" = 1 ]; then
    echo "==> shipping var/ub.db ($(du -h var/ub.db | cut -f1))"
    ssh "$HOST" "mkdir -p $DEST/var"
    # To a temp name then mv, so a half-transferred database is never the one
    # being served. mv within a filesystem is atomic.
    rsync -az --info=progress2 var/ub.db "$HOST:$DEST/var/ub.db.new"
    ssh "$HOST" "mv $DEST/var/ub.db.new $DEST/var/ub.db"
fi

echo "==> venv on $HOST"
ssh "$HOST" "cd $DEST && $UV venv --python \$(cat .python-version) >/dev/null && $UV pip sync -q requirements.txt"

if [ "$RESTART" = 1 ]; then
    echo "==> restart"
    ssh "$HOST" "sudo systemctl restart ubsite"
    echo "==> waiting for /healthz"
    for i in $(seq 1 30); do
        out=$(ssh "$HOST" "curl -sf http://127.0.0.1:$PORT/healthz" 2>/dev/null || true)
        case "$out" in
            *'"ok":true'*) echo "    $out"; echo "==> up"; exit 0 ;;
        esac
        sleep 1
    done
    echo "FAILED: /healthz did not report ok within 30s" >&2
    ssh "$HOST" "systemctl --no-pager -n 20 status ubsite" || true
    exit 1
fi
echo "==> done (not restarted)"
