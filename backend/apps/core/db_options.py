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
  DB_POOL_MODE             session (default) or transaction: what kind of pooler sits in front of the database.
                           See apply_pool_mode and docs/CAPACITY.md.

Session mode: a client keeps ONE server connection for as long as it stays connected, so session-level state (a SET,
a server-side cursor, a prepared statement) is safe. Transaction mode: the pooler lends a server connection for one
transaction only, so none of that state may be relied on. In transaction mode this module therefore (a) turns off
server-side cursors and psycopg's automatic prepared statements, and (b) applies the statement timeout with
SET LOCAL at the start of each transaction instead of one SET per connection.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

POOL_MODES = ('session', 'transaction')


def postgres_options(existing, connect_timeout):
    """OPTIONS for a PostgreSQL database: whatever the database URL already set, plus a connect timeout
    (a timeout written in the URL wins)."""
    options = dict(existing or {})
    options.setdefault('connect_timeout', int(connect_timeout))
    return options


def pool_mode_from(value):
    """The DB_POOL_MODE value, lower-cased; empty means session."""
    return (value or 'session').strip().lower() or 'session'


def apply_pool_mode(database, mode):
    """Adjust one DATABASES entry in place for the pooler mode. Session mode changes nothing."""
    if mode not in POOL_MODES:
        raise ImproperlyConfigured(f"DB_POOL_MODE must be 'session' or 'transaction' (got {mode!r}).")
    if mode == 'transaction':
        database['DISABLE_SERVER_SIDE_CURSORS'] = True  # a cursor lives on one server connection
        options = dict(database.get('OPTIONS') or {})
        options['prepare_threshold'] = None  # psycopg 3 would otherwise prepare statements after 5 uses
        database['OPTIONS'] = options
    return database


def statement_timeout_sql(milliseconds):
    """`SET statement_timeout = N`, or None when no limit is wanted. The value is forced through int() first,
    so nothing but a number can ever reach the SQL text."""
    number = int(milliseconds)
    if number <= 0:
        return None
    return f'SET statement_timeout = {number}'


def local_timeout_wrapper(milliseconds):
    """An execute wrapper for transaction mode: the first statement of every transaction block is preceded by
    SET LOCAL statement_timeout, which lasts exactly until that transaction ends (so it can never leak to another
    client that is lent the same server connection). Statements outside a transaction block are left alone (see the
    module text). The raw psycopg cursor is used so the extra statement does not pass through this wrapper again."""
    from psycopg.pq import TransactionStatus

    sql = f'SET LOCAL statement_timeout = {int(milliseconds)}'

    def wrapper(execute, statement, params, many, context):
        conn = context['connection']
        if conn.in_atomic_block and conn.connection.info.transaction_status == TransactionStatus.IDLE:
            with conn.connection.cursor() as raw:
                raw.execute(sql)
        return execute(statement, params, many, context)

    return wrapper


def apply_statement_timeout(sender, connection, **kwargs):
    """connection_created receiver (registered in CoreConfig.ready)."""
    if connection.vendor != 'postgresql':
        return
    milliseconds = getattr(settings, 'DB_STATEMENT_TIMEOUT_MS', 0)
    sql = statement_timeout_sql(milliseconds)
    if not sql:
        return
    if getattr(settings, 'DB_POOL_MODE', 'session') == 'transaction':
        connection.execute_wrappers.append(local_timeout_wrapper(milliseconds))
        return
    with connection.cursor() as cursor:
        cursor.execute(sql)
