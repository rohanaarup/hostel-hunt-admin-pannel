"""
Database connection options that come from the environment.

  DB_CONNECT_TIMEOUT       seconds to wait for a new connection (default 5). Passed to libpq, which every
                           Supabase pooler mode accepts. An unreachable database fails fast instead of holding
                           a worker thread.
  DB_STATEMENT_TIMEOUT_MS  longest a single statement may run, in milliseconds (default 0 = no limit). Set it
                           ONLY on the web process (see the start command in render.yaml), never where
                           migrations or the clean-up job run, because a long migration statement must not be
                           cut off. It is applied with a SET when a connection opens, not as a startup
                           option, because poolers reject unknown startup options.
"""
from django.conf import settings


def postgres_options(existing, connect_timeout):
    """OPTIONS for a PostgreSQL database: whatever the database URL already set, plus a connect timeout
    (a timeout written in the URL wins)."""
    options = dict(existing or {})
    options.setdefault('connect_timeout', int(connect_timeout))
    return options


def statement_timeout_sql(milliseconds):
    """`SET statement_timeout = N`, or None when no limit is wanted. The value is forced through int() first,
    so nothing but a number can ever reach the SQL text."""
    number = int(milliseconds)
    if number <= 0:
        return None
    return f'SET statement_timeout = {number}'


def apply_statement_timeout(sender, connection, **kwargs):
    """connection_created receiver (registered in CoreConfig.ready)."""
    if connection.vendor != 'postgresql':
        return
    sql = statement_timeout_sql(getattr(settings, 'DB_STATEMENT_TIMEOUT_MS', 0))
    if sql:
        with connection.cursor() as cursor:
            cursor.execute(sql)
