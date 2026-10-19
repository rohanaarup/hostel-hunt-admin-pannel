"""
Summarises the server's own request log (the `hh.request` JSON lines) from a Render log export.

  python summarize_log.py render-log.txt [--from 2026-01-01T10:00:00Z] [--to 2026-01-01T10:20:00Z]

The lines hold no addresses, names or tokens (see backend/docs/observability.md), so the output is safe to paste.
Prints a markdown table per route: requests, server time p50/p95/p99, database time p95, queries per request,
status counts, plus the highest `inflight` and the number of distinct worker pids. Only the standard library is used.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict


def percentile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def parse(lines, start=None, end=None):
    """Yields the request records found in `lines`. Anything that is not a request record is skipped."""
    for line in lines:
        brace = line.find('{')
        if brace < 0:
            continue
        try:
            record = json.loads(line[brace:])
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get('event') != 'request' or 'duration_ms' not in record:
            continue
        stamp = record.get('ts', '')
        if (start and stamp < start) or (end and stamp > end):
            continue
        yield record


def summarise(records):
    by_route = defaultdict(list)
    for record in records:
        by_route[f"{record.get('method', '?')} {record.get('route', '?')}"].append(record)
    rows = []
    for key, items in by_route.items():
        statuses = Counter(str(item.get('status'))[0] + 'xx' for item in items)
        rows.append({
            'route': key,
            'requests': len(items),
            'p50': percentile([i['duration_ms'] for i in items], 0.50),
            'p95': percentile([i['duration_ms'] for i in items], 0.95),
            'p99': percentile([i['duration_ms'] for i in items], 0.99),
            'db_p95': percentile([i.get('db_ms') or 0 for i in items], 0.95),
            'queries': sum(i.get('db_queries') or 0 for i in items) / len(items),
            'statuses': dict(sorted(statuses.items())),
            'inflight_max': max((i.get('inflight') or 0) for i in items),
            'pids': len({i.get('pid') for i in items}),
        })
    return sorted(rows, key=lambda r: -r['requests'])


def render(rows):
    out = ['| Route | Requests | p50 ms | p95 ms | p99 ms | DB p95 ms | Queries/req | Statuses | Max inflight |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        statuses = ', '.join(f'{k}: {v}' for k, v in r['statuses'].items())
        out.append(
            f"| {r['route']} | {r['requests']} | {r['p50']:.0f} | {r['p95']:.0f} | {r['p99']:.0f} | {r['db_p95']:.0f} | "
            f"{r['queries']:.1f} | {statuses} | {r['inflight_max']} |"
        )
    pids = {r['pids'] for r in rows}
    out.append(f"\nWorker processes seen: up to {max(pids) if pids else 0}. Highest in-flight requests: {max((r['inflight_max'] for r in rows), default=0)}.")
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('logfile')
    parser.add_argument('--from', dest='start')
    parser.add_argument('--to', dest='end')
    args = parser.parse_args(argv)
    with open(args.logfile, encoding='utf-8', errors='replace') as handle:
        rows = summarise(parse(handle, args.start, args.end))
    if not rows:
        print('No hh.request lines found in that file.', file=sys.stderr)
        return 1
    print(render(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
