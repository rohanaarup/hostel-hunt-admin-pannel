"""
Guard for scripts that destroy data (reset_db.py, reset_db_auto.py).

A reset is allowed only when the database host is local AND the caller passed
the explicit confirmation flag. The default database mode points at a remote
Postgres, so running a reset script with nothing configured must never drop it.
"""
import sys

LOCAL_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})
CONFIRM_FLAG = '--i-understand-this-drops-all-tables'


class ResetRefused(Exception):
    pass


def check_reset_allowed(host, confirmed):
    if not host or host not in LOCAL_HOSTS:
        raise ResetRefused(
            "Refusing to reset: the configured database host is not local "
            "(localhost, 127.0.0.1 or ::1). Reset scripts only run against a local database."
        )
    if not confirmed:
        raise ResetRefused(f"Refusing to reset: pass {CONFIRM_FLAG} to confirm.")


def guard_or_exit(argv, host):
    """Call at the top of a destructive script's __main__ block."""
    try:
        check_reset_allowed(host, CONFIRM_FLAG in argv)
    except ResetRefused as exc:
        print(exc)
        sys.exit(2)
