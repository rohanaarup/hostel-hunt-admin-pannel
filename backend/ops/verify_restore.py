"""
Compares two databases table by table (row counts) to prove a restore is complete.

  python verify_restore.py <source url> <restored url>

Exit code 0 when every table in the source exists in the restored copy with the same row count.
It prints table names and counts only, never row contents or the URLs.
"""
import sys

import psycopg


def counts(url):
    with psycopg.connect(url, connect_timeout=15) as conn, conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1")
        tables = [row[0] for row in cur.fetchall()]
        result = {}
        for table in tables:
            cur.execute(f'SELECT count(*) FROM "{table}"')
            result[table] = cur.fetchone()[0]
        return result


def compare(source, restored):
    """Returns the list of differences (empty when the copy is complete)."""
    problems = []
    for table, n in source.items():
        if table not in restored:
            problems.append(f'MISSING table {table}')
        elif restored[table] != n:
            problems.append(f'DIFFERENT {table}: source {n}, restored {restored[table]}')
    return problems


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    source, restored = counts(argv[1]), counts(argv[2])
    problems = compare(source, restored)
    rows = sum(source.values())
    print(f'{len(source)} tables, {rows} rows in the source; {len(restored)} tables in the restored copy.')
    for problem in problems:
        print(problem)
    print('RESULT: ' + ('FAIL' if problems else 'PASS'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
