"""
The capacity model from backend/docs/CAPACITY.md as code, so the arithmetic is checked rather than trusted.

  python tools/capacity_model.py                      # the 1,000 / 10,000 / 100,000 table with the assumed numbers
  python tools/capacity_model.py --rps-per-instance 42 --edge-hit 0.85 --workers 3 --threads 4

Two models:

  Connection budget (per pooler):
      connections = instances x workers x threads + cron jobs + deploy migrate + admin sessions
      it must stay at or under 80 percent of the pooler limit.

  Request load:
      peak concurrent users   = registered users x peak share (default 3 percent)
      requests per second     = peak concurrent users / seconds between a user's requests (default 5)
      origin requests/second  = total x (1 - public share x edge hit rate)       (public share default 80 percent)
      instances               = origin load / (0.6 x measured requests per second per instance), at least 2

The defaults are the founder's DESIGN TARGETS (assumptions). The measured requests per second per instance and the edge
hit rate are the two numbers a real load test has to supply: until then every output here is "if the assumptions hold".
"""
import argparse
import math

PEAK_SHARE = 0.03
SECONDS_BETWEEN_REQUESTS = 5.0
PUBLIC_SHARE = 0.80
HEADROOM = 0.6           # run instances at 60 percent of what they were measured to manage
POOLER_RATIO = 0.8       # stay at or under 80 percent of the pooler limit
MIN_INSTANCES = 2        # failover: one can restart while the other serves


def connections(instances, workers, threads, cron_jobs=1, deploy_migrate=1, admin_sessions=2):
    """Database connections the app can hold at once: every thread of every worker of every instance may keep one."""
    return instances * workers * threads + cron_jobs + deploy_migrate + admin_sessions


def fits_pooler(used, pooler_limit, ratio=POOLER_RATIO):
    return used <= ratio * pooler_limit


def max_instances(pooler_limit, workers, threads, cron_jobs=1, deploy_migrate=1, admin_sessions=2, ratio=POOLER_RATIO):
    """The largest instance count whose connections stay within the ratio of the pooler limit (0 if none fits)."""
    spare = ratio * pooler_limit - (cron_jobs + deploy_migrate + admin_sessions)
    return max(0, int(spare // (workers * threads)))


def request_load(registered, peak_share=PEAK_SHARE, seconds_between=SECONDS_BETWEEN_REQUESTS):
    concurrent = registered * peak_share
    return concurrent, concurrent / seconds_between


def origin_load(total_rps, public_share=PUBLIC_SHARE, edge_hit_rate=0.0):
    return total_rps * (1 - public_share * edge_hit_rate)


def instances_needed(origin_rps, rps_per_instance, headroom=HEADROOM, minimum=MIN_INSTANCES):
    if rps_per_instance <= 0:
        raise ValueError('rps_per_instance must be a measured number above zero')
    return max(minimum, math.ceil(origin_rps / (headroom * rps_per_instance)))


def plan(registered, rps_per_instance, edge_hit_rate, workers, threads, pooler_limit=None):
    concurrent, total = request_load(registered)
    origin = origin_load(total, edge_hit_rate=edge_hit_rate)
    count = instances_needed(origin, rps_per_instance)
    used = connections(count, workers, threads)
    row = {
        'registered': registered, 'concurrent': concurrent, 'total_rps': total, 'origin_rps': origin,
        'instances': count, 'connections': used,
    }
    if pooler_limit is not None:
        row['pooler_limit'] = pooler_limit
        row['fits'] = fits_pooler(used, pooler_limit)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--rps-per-instance', type=float, default=40.0,
                        help='MEASURED requests per second one instance sustains (default 40 is a placeholder)')
    parser.add_argument('--edge-hit', type=float, default=0.8, help='share of public reads the edge answers (0 to 1)')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--pooler-limit', type=int, default=60, help='connections the pooler allows (check Supabase)')
    args = parser.parse_args(argv)

    print(f'ASSUMPTIONS, not measurements: {args.rps_per_instance} req/s per instance, edge hit rate {args.edge_hit}, '
          f'{args.workers} workers x {args.threads} threads, pooler limit {args.pooler_limit}')
    print(f"{'registered':>10} {'peak users':>10} {'req/s':>7} {'origin req/s':>12} {'instances':>9} {'connections':>11} {'fits 80%':>8}")
    for registered in (1000, 10000, 100000):
        row = plan(registered, args.rps_per_instance, args.edge_hit, args.workers, args.threads, args.pooler_limit)
        print(f"{row['registered']:>10,} {row['concurrent']:>10,.0f} {row['total_rps']:>7.1f} {row['origin_rps']:>12.1f} "
              f"{row['instances']:>9} {row['connections']:>11} {'yes' if row['fits'] else 'NO':>8}")
    print(f"free session pooler (15): {max_instances(15, args.workers, args.threads)} instance(s) fit "
          f"at {args.workers} x {args.threads}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
