#!/usr/bin/env bash
# Push ubsite to its hosts and restart it there: pi5 (ubsite.ddns.net) and
# the VPS behind sigmaai.au (ubsite.sigmaai.au), reached by that name.  Both
# are live, and each deploy gives them the same build.
#
#   ./deploy/deploy.sh                 build the database here, ship it to both, restart
#   ./deploy/deploy.sh sigmaai.au      the same, to that host alone (or pi5 alone)
#   ./deploy/deploy.sh --no-data       ship code only, leave the database and the offline copy alone
#   ./deploy/deploy.sh --no-restart    ship, do not restart
#   ./deploy/deploy.sh --audio         also copy the AI voice (var/audio/ai, ~4 GB) first
#   ./deploy/deploy.sh --allow-dirty   ship a database built from uncommitted press files
#   UBSITE_HOSTS="pi5" ./deploy/deploy.sh
#
# The three source repositories are NOT on the hosts, and do not need to be:
# the database is the artifact. `make data` runs here, where the LaTeX lives,
# and var/ub.db is shipped. The hosts need no TeX, no sources, and no build.
#
# Everything below is unprivileged. The steps that need root are listed in
# deploy/README.md and are not run from here -- see that file for why.
set -euo pipefail

HOSTS="${UBSITE_HOSTS:-pi5 sigmaai.au}"
DEST="${UBSITE_DEST:-/home/tigran/ubsite}"
UV="${UBSITE_UV:-/home/tigran/.local/bin/uv}"   # uv lives here on both, not /usr/local/bin
PORT="${UBSITE_PORT:-8130}"                     # 8000 and 8090 are taken on pi5, 8000 on the VPS
BUILD=1
RESTART=1
AUDIO=0
ALLOW_DIRTY=0
CHOSEN=""

for arg in "$@"; do
    case "$arg" in
        --no-data)    BUILD=0 ;;
        --no-restart) RESTART=0 ;;
        --audio)      AUDIO=1 ;;
        --allow-dirty) ALLOW_DIRTY=1 ;;
        -*) echo "usage: $(basename "$0") [--no-data] [--no-restart] [--audio] [--allow-dirty] [host...]" >&2; exit 2 ;;
        *)  CHOSEN="$CHOSEN $arg" ;;
    esac
done
[ -n "$CHOSEN" ] && HOSTS="$CHOSEN"

# The address for big copies.  pi5 has a fast link of its own, pi5f; the
# VPS is reached over the internet whatever its name.
copy_host() {
    if [ -n "${UBSITE_COPY_HOST:-}" ]; then echo "$UBSITE_COPY_HOST"
    elif [ "$1" = pi5 ]; then echo pi5f
    else echo "$1"; fi
}

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

# Refuse to deploy this tree onto itself. libnodes learned this the hard way:
# on a box that is both the development machine and the deployment, the reflex
# `./deploy/deploy.sh` becomes an rsync --delete against a live tree.
for HOST in $HOSTS; do
    if [ "$(hostname -s)" = "$HOST" ] && [ "$HERE" = "$DEST" ]; then
        echo "refusing: this IS $HOST:$DEST" >&2
        exit 1
    fi
done

if [ "$BUILD" = 1 ]; then
    echo "==> building the database here"
    make data
    make check
    make offline
fi

# A dirty build: press read from a working tree that differs from the commit it
# records (build/config.py _dirty), so that commit could not build what would go
# live.  The footer said "dirty" until 2026-10-18; now /healthz alone would, so
# it is refused here unless asked for (Tigran, 2026-10-18).  Checked on what the
# database records, so a press edit made during the build counts too.
if [ "$BUILD" = 1 ]; then
    RC=0
    DIRTY="$(.venv/bin/python -m build dirty var/ub.db)" || RC=$?
    if [ "$RC" = 3 ] && [ "$ALLOW_DIRTY" = 1 ]; then
        echo "==> shipping a dirty build, as asked (--allow-dirty); /healthz will say so:"
        echo "$DIRTY"
    elif [ "$RC" = 3 ]; then
        echo "refusing: the database was built from source files that are not committed," >&2
        echo "          so the commit /healthz would name could not build it again:" >&2
        echo "$DIRTY" >&2
        echo "          Deploy once they are committed; or, if the build reads none of them," >&2
        echo "          ./deploy/deploy.sh --allow-dirty ships it as it is." >&2
        exit 1
    elif [ "$RC" != 0 ]; then
        echo "refusing: could not tell whether the database is dirty (build dirty: $RC)" >&2
        exit 1
    fi
fi

# The text API's versions (data/text/, build/versions.py).  A site syncing with
# it keeps the number it was sent, so a number that reaches a host must never be
# made again for other text.  An uncommitted ledger can be: a checkout or a
# reset throws it away, and the next build hands out the same number.
if [ -n "$(git status --porcelain -- data/text)" ]; then
    echo "refusing: data/text/ holds a text version that is not committed." >&2
    echo "          Commit it with the change that made it, then deploy." >&2
    git status --short -- data/text >&2
    exit 1
fi

# The study notes the site shows are the reviewed copies in data/study/ (build/
# study.py).  One not committed was never looked at as a whole, and a checkout
# would lose the review that the hosts are already showing.
if [ -n "$(git status --porcelain -- data/study)" ]; then
    echo "refusing: data/study/ holds reviewed notes that are not committed." >&2
    echo "          Commit the paper's review, then deploy." >&2
    git status --short -- data/study >&2
    exit 1
fi

# One host: everything from here on is done once for each, with what was built above.
ship() {
    local HOST="$1"
    local COPY_HOST
    COPY_HOST="$(copy_host "$HOST")"
    echo
    echo "=== $HOST"

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

    # The visit counter's place database (`make geoip`, monthly), which the rsync
    # above skips with the rest of var/.  rsync writes a temporary file and renames
    # it, so a worker that has the old one mapped keeps reading it, and opens the new
    # one when it sees the change of mtime.  Unchanged, nothing is sent.
    local GEO=var/geoip/dbip-city-lite.mmdb
    if [ -f "$GEO" ]; then
        echo "==> $GEO ($(du -h "$GEO" | cut -f1))"
        ssh "$COPY_HOST" "mkdir -p $DEST/var/geoip"
        rsync -a "$GEO" "$COPY_HOST:$DEST/$GEO"
    else
        echo "    (no $GEO here: visits on $HOST are counted without places; make geoip)"
    fi

    if [ "$AUDIO" = 1 ]; then
        # The AI voice is made here, under var/, which the rsync above skips.  To
        # the same relative path on the host, adding and never deleting: a page
        # opened before the new database goes live still plays the files the old
        # one named.  The old files are pruned below, one deploy later.
        echo "==> AI voice to $COPY_HOST:$DEST/var/audio/ai ($(du -sh var/audio/ai | cut -f1))"
        ssh "$COPY_HOST" "mkdir -p $DEST/var/audio/ai"
        rsync -a --info=progress2 var/audio/ai/ "$COPY_HOST:$DEST/var/audio/ai/"
    fi

    if [ "$BUILD" = 1 ]; then
        # The database names every recording it will serve; the host must hold
        # exactly those files, at the path the database records -- a relative one
        # under $DEST.  By size, which is cheap and catches a missing or truncated
        # copy; the SHA-256s are in data/audio/<key>-files.tsv for when that is
        # not enough.
        local key root want have missing
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
        local LIST="SELECT s.root || '/' || f.name FROM audio_file f JOIN audio_source s ON s.id=f.source_id WHERE s.key='ai'"
        local served
        served=$(ssh "$HOST" "cd $DEST && [ -f var/ub.db ] && .venv/bin/python -c \"import sqlite3; print('\\n'.join(r[0] for r in sqlite3.connect('file:var/ub.db?mode=ro', uri=True).execute(\\\"$LIST\\\")))\" 2>/dev/null" || true)

        echo "==> shipping var/ub.db ($(du -h var/ub.db | cut -f1))"
        ssh "$HOST" "mkdir -p $DEST/var"
        # To a temp name then mv, so a half-transferred database is never the one
        # being served. mv within a filesystem is atomic.
        rsync -az --info=progress2 var/ub.db "$HOST:$DEST/var/ub.db.new"
        ssh "$HOST" "mv $DEST/var/ub.db.new $DEST/var/ub.db"

        # The offline copy (offline/, `make offline`), made from this database: its
        # chunks first, adding and never deleting, so that a reader updating from
        # the copy before still finds every chunk it was told of; then the manifest
        # that names them, by a temp name and mv.  A chunk neither this manifest
        # nor the one it replaced names is pruned, as the AI voice's files are.
        local chunks='import json, sys; d = sys.stdin.read().strip(); print("\n".join(c["file"][2:] for c in json.loads(d)["chunks"]) if d else "")'
        local before keep stale
        echo "==> offline copy ($(du -sh var/offline/c | cut -f1))"
        before=$(ssh "$HOST" "cat $DEST/var/offline/manifest.json 2>/dev/null || true" | python3 -c "$chunks")
        ssh "$HOST" "mkdir -p $DEST/var/offline/c"
        rsync -a var/offline/c/ "$HOST:$DEST/var/offline/c/"
        rsync -a var/offline/manifest.json "$HOST:$DEST/var/offline/manifest.json.new"
        ssh "$HOST" "mv $DEST/var/offline/manifest.json.new $DEST/var/offline/manifest.json"
        keep=$( { echo "$before"; python3 -c "$chunks" < var/offline/manifest.json; } | { grep -v '^$' || true; } | LC_ALL=C sort -u)
        have=$(ssh "$HOST" "ls $DEST/var/offline/c" | LC_ALL=C sort)
        stale=$(LC_ALL=C comm -23 <(echo "$have") <(echo "$keep") | grep -v '^$' || true)
        if [ -n "$stale" ]; then
            echo "    pruning $(echo "$stale" | wc -l) chunks no manifest names"
            echo "$stale" | ssh "$HOST" "cd $DEST/var/offline/c && xargs -r rm -f --"
        fi

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
        local i out
        for i in $(seq 1 30); do
            out=$(ssh "$HOST" "curl -sf http://127.0.0.1:$PORT/healthz" 2>/dev/null || true)
            case "$out" in
                *'"ok":true'*) echo "    $out"; echo "==> $HOST up"; return 0 ;;
            esac
            sleep 1
        done
        echo "FAILED: /healthz on $HOST did not report ok within 30s" >&2
        ssh "$HOST" "systemctl --no-pager -n 20 status ubsite" || true
        exit 1
    fi
    echo "==> $HOST done (not restarted)"
}

for HOST in $HOSTS; do
    ship "$HOST"
done
