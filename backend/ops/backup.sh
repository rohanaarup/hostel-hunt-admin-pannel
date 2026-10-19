#!/usr/bin/env bash
# Encrypted dump of the database. See RELEASE.md.
#
#   BACKUP_DATABASE_URL=...  BACKUP_AGE_PUBLIC_KEY=age1...  bash backup.sh [output-file]
#
# Needs only Docker (pg_dump 17 and age run in containers, so nothing is installed). The dump is encrypted with
# the PUBLIC key before it touches the disk: whoever finds the file cannot read it, and the private key is never
# on the server or in GitHub. Neither value is printed.
set -euo pipefail
export MSYS_NO_PATHCONV=1

: "${BACKUP_DATABASE_URL:?set BACKUP_DATABASE_URL (the Supabase session-pooler URL; it is a secret)}"
: "${BACKUP_AGE_PUBLIC_KEY:?set BACKUP_AGE_PUBLIC_KEY (starts with age1; the public half is not secret)}"
case "$BACKUP_AGE_PUBLIC_KEY" in age1*) ;; *) echo "BACKUP_AGE_PUBLIC_KEY must start with age1" >&2; exit 2;; esac

out="${1:-hh-backup-$(date -u +%Y%m%dT%H%M%SZ).dump.age}"

docker run --rm -e URL="$BACKUP_DATABASE_URL" postgres:17 \
  sh -c 'pg_dump --format=custom --no-owner --no-privileges "$URL"' \
| docker run --rm -i -e KEY="$BACKUP_AGE_PUBLIC_KEY" alpine:3.20 \
  sh -c 'apk add -q --no-cache age >/dev/null && age -r "$KEY"' > "$out"

# An empty or truncated file must never look like a backup.
size=$(wc -c < "$out" | tr -d ' ')
if [ "$size" -lt 1000 ]; then
  echo "Backup failed: output is only $size bytes." >&2
  rm -f "$out"
  exit 1
fi
echo "Wrote $out ($size bytes, encrypted)."
