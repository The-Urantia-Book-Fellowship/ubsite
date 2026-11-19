#!/usr/bin/env bash
# The accounts, backed up (ubsite/account.py): each host's var/user.db, who has
# signed in there and what each keeps, is the one thing on a host that no build
# can make again and that its readers would miss.  A copy of it, made on the
# host by SQLite's own backup, is brought here to
# var/accounts/user-<host>-<date>.db and read back; and every copy here that
# is 29 days old is deleted, whichever host's.  Privacy says that copies made
# for safekeeping are deleted within 30 days, and this is what keeps its word,
# so it runs every night (deploy/README.md, Backups), and deploy.sh runs it
# before it ships anything.
#
#   ./deploy/backup-accounts.sh              every host that has accounts
#   ./deploy/backup-accounts.sh sigmaai.au   that host alone
#
# Unprivileged, here and there.  Never shipped back: a copy is put on its host
# by hand, when it must be (deploy/README.md, Backups).
set -euo pipefail
umask 077

HOSTS="${*:-${UBSITE_HOSTS:-pi5 sigmaai.au}}"
DEST="${UBSITE_DEST:-/home/tigran/ubsite}"
KEEP_DAYS=29
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$HERE/var/accounts"
mkdir -p "$OUT"

for HOST in $HOSTS; do
    if ! ssh "$HOST" "test -f $DEST/var/user.db"; then
        echo "==> $HOST has no accounts: nothing to back up"
        continue
    fi
    when="$(date +%F-%H%M%S)"
    copy="$OUT/user-$HOST-$when.db"
    ssh "$HOST" "cd $DEST && umask 077 && rm -f var/user-backup.db && .venv/bin/python -c 'import sqlite3; sqlite3.connect(\"var/user.db\").backup(sqlite3.connect(\"var/user-backup.db\"))'"
    rsync -a "$HOST:$DEST/var/user-backup.db" "$copy"
    ssh "$HOST" "rm -f $DEST/var/user-backup.db"
    chmod 600 "$copy"
    # Read back, since an untested backup is a rumour: whole, and with how
    # many accounts and things kept.  A file from before anything followed an
    # account has no table of them.
    "$HERE/.venv/bin/python" - "$copy" <<'PY'
import sqlite3
import sys

# Read as it lies, so that nothing is written beside it: no -wal, no -shm.
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1", uri=True)
said = con.execute("PRAGMA integrity_check").fetchone()[0]
if said != "ok":
    sys.exit(f"backup-accounts: {sys.argv[1]}: {said}")
users = con.execute("SELECT COUNT(*) FROM user").fetchone()[0]
kept = (con.execute("SELECT COUNT(*) FROM item WHERE value IS NOT NULL").fetchone()[0]
        if con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'item'").fetchone() else 0)
print(f"    read back whole: {users} accounts, {kept} things kept")
PY
    echo "==> $HOST's accounts, backed up: var/accounts/$(basename "$copy")"
done

# Within 30 days, as Privacy says: a copy 29 days old goes, tonight.
find "$OUT" -name 'user-*.db*' -type f -mtime +$((KEEP_DAYS - 1)) -print -delete | sed 's/^/==> deleted, 29 days old: /'
