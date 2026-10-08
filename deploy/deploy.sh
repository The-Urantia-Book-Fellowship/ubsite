#!/usr/bin/env bash
# Push ubsite to pi5 and restart it there.
#
#   ./deploy/deploy.sh                 build the database here, ship it, restart
#   ./deploy/deploy.sh --no-data       ship code only, leave the database alone
#   ./deploy/deploy.sh --no-restart    ship, do not restart
#   ./deploy/deploy.sh --audio         also copy the AI voice (var/audio/ai, ~4 GB) first
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
COPY_HOST="${UBSITE_COPY_HOST:-pi5f}"           # pi5's address on the fast link, for big copies
BUILD=1
RESTART=1
AUDIO=0

for arg in "$@"; do
    case "$arg" in
        --no-data)    BUILD=0 ;;
        --no-restart) RESTART=0 ;;
        --audio)      AUDIO=1 ;;
        *) echo "usage: $(basename "$0") [--no-data] [--no-restart] [--audio]" >&2; exit 2 ;;
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

if [ "$AUDIO" = 1 ]; then
    # The AI voice is made here, under var/, which the rsync above skips.  To
    # the same relative path on pi5, adding and never deleting: a page opened
    # before the new database goes live still plays the files the old one
    # named.  The old files are pruned below, one deploy later.
    echo "==> AI voice to $COPY_HOST:$DEST/var/audio/ai ($(du -sh var/audio/ai | cut -f1))"
    ssh "$COPY_HOST" "mkdir -p $DEST/var/audio/ai"
    rsync -a --info=progress2 var/audio/ai/ "$COPY_HOST:$DEST/var/audio/ai/"
fi

if [ "$BUILD" = 1 ]; then
    # The database names every recording it will serve; pi5 must hold exactly
    # those files, at the path the database records -- a relative one under
    # $DEST.  By size, which is cheap and catches a missing or truncated copy;
    # the SHA-256s are in data/audio/<key>-files.tsv for when that is not enough.
    for key in $(sqlite3 var/ub.db "SELECT key FROM audio_source ORDER BY id"); do
        root=$(sqlite3 var/ub.db "SELECT root FROM audio_source WHERE key='$key'")
        case "$root" in /*) ;; *) root="$DEST/$root" ;; esac
        echo "==> recordings ($key) on $HOST at $root"
        want=$(sqlite3 -separator ' ' var/ub.db \
            "SELECT f.name, f.bytes FROM audio_file f JOIN audio_source s ON s.id=f.source_id
              WHERE s.key='$key'" | LC_ALL=C sort)
        # A missing directory is an empty list, reported below, not a silent
        # exit: under pipefail a failing ssh would end the script here.
        have=$(ssh "$HOST" "{ cd '$root' 2>/dev/null && find . -name '*.mp3' -printf '%P %s\n'; } || true" | LC_ALL=C sort)
        missing=$(LC_ALL=C comm -23 <(echo "$want") <(echo "$have") | head -5)
        if [ -n "$missing" ]; then
            echo "FAILED: $HOST lacks, or has a different size of, recordings the database serves:" >&2
            echo "$missing" >&2
            [ "$key" = ai ] && echo "(./deploy/deploy.sh --audio copies the AI voice)" >&2
            exit 1
        fi
        echo "    $(echo "$want" | wc -l) files present"
    done

    # The AI files the database being replaced names: kept through this
    # deploy for pages already open, pruned at the next.
    LIST="SELECT s.root || '/' || f.name FROM audio_file f JOIN audio_source s ON s.id=f.source_id WHERE s.key='ai'"
    served=$(ssh "$HOST" "cd $DEST && [ -f var/ub.db ] && .venv/bin/python -c \"import sqlite3; print('\\n'.join(r[0] for r in sqlite3.connect('file:var/ub.db?mode=ro', uri=True).execute(\\\"$LIST\\\")))\" 2>/dev/null" || true)

    echo "==> shipping var/ub.db ($(du -h var/ub.db | cut -f1))"
    ssh "$HOST" "mkdir -p $DEST/var"
    # To a temp name then mv, so a half-transferred database is never the one
    # being served. mv within a filesystem is atomic.
    rsync -az --info=progress2 var/ub.db "$HOST:$DEST/var/ub.db.new"
    ssh "$HOST" "mv $DEST/var/ub.db.new $DEST/var/ub.db"

    # Prune: an AI file neither the new database nor the one it replaced names.
    # grep exits 1 when it passes nothing, as it does while there are no AI
    # files at all; under pipefail that would end the script, before the restart.
    keep=$( { echo "$served"; sqlite3 var/ub.db "$LIST"; } | { grep -v '^$' || true; } | LC_ALL=C sort -u)
    have=$(ssh "$HOST" "cd $DEST && { [ ! -d var/audio/ai ] || find var/audio/ai -name '*.mp3'; }" | LC_ALL=C sort)
    stale=$(LC_ALL=C comm -23 <(echo "$have") <(echo "$keep") | grep -v '^$' || true)
    if [ -n "$stale" ]; then
        echo "==> pruning $(echo "$stale" | wc -l) AI files no database names"
        echo "$stale" | ssh "$HOST" "cd $DEST && xargs -r rm -f --"
    fi
fi

echo "==> venv on $HOST"
# Created once, then only synced: uv 0.12 refuses to create a venv over an
# existing one, so an unconditional `uv venv` failed every deploy but the first.
ssh "$HOST" "cd $DEST && { [ -x .venv/bin/python ] || $UV venv --python \$(cat .python-version) >/dev/null; } && $UV pip sync -q requirements.txt"

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
