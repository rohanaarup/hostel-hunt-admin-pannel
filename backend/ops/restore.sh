#!/usr/bin/env bash
# Restores an encrypted dump (made by backup.sh) into a database. See RELEASE.md.
#
#   AGE_IDENTITY_FILE=/path/to/private-key.txt \
#   RESTORE_CONFIRM=not-production \
#   bash restore.sh hh-backup-....dump.age "postgres://...target..."
#
# It DROPS and recreates every object in the target database before loading, so it refuses to run unless you set
# RESTORE_CONFIRM=not-production to say, in your own words, that the target is staging or a scratch database.
set -euo pipefail
export MSYS_NO_PATHCONV=1

dump="${1:?usage: restore.sh <dump.age> <target database url>}"
target="${2:?usage: restore.sh <dump.age> <target database url>}"
: "${AGE_IDENTITY_FILE:?set AGE_IDENTITY_FILE to the file holding your age private key}"
if [ "${RESTORE_CONFIRM:-}" != "not-production" ]; then
  echo "Refusing: this overwrites the target database. Set RESTORE_CONFIRM=not-production once you are sure it is not production." >&2
  exit 2
fi
[ -f "$dump" ] || { echo "No such file: $dump" >&2; exit 2; }
[ -f "$AGE_IDENTITY_FILE" ] || { echo "No such key file: $AGE_IDENTITY_FILE" >&2; exit 2; }

docker run --rm -i -v "$AGE_IDENTITY_FILE":/key:ro alpine:3.20 \
  sh -c 'apk add -q --no-cache age >/dev/null && age -d -i /key' < "$dump" \
| docker run --rm -i -e URL="$target" postgres:17 \
  sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$URL"' || status=$?
# pg_restore exits 1 when it only skipped something harmless (for example a setting an older server does not know).
# Whether the copy is complete is decided by verify_restore.py, not by this exit code.
if [ "${status:-0}" -gt 1 ]; then echo "pg_restore failed (exit $status)." >&2; exit "$status"; fi
[ "${status:-0}" -eq 1 ] && echo "pg_restore reported warnings (see above); check them, then run verify_restore.py." >&2
echo "Restore finished. Now run: python backend/ops/verify_restore.py <source url> <restored url>"
