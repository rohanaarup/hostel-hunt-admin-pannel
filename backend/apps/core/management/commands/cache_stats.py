"""
Management command: cache_stats

Prints the shared cache's own counters, so a load test can report a cache hit rate (CAPACITY.md, Part 6). Read-only; it
never prints REDIS_URL or any key or value.

  python manage.py cache_stats

Redis counts EVERY command, including DRF's rate-limit reads and the single-flight locks, so the absolute hit rate is
not the hit rate of the public lists. Take two snapshots, one before and one after a run, and compare the differences
(or run it against an otherwise idle instance). With no REDIS_URL the cache is per-process memory and there is nothing
to report.
"""
from django.core.cache import caches
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show the Redis cache's hit and miss counters, memory use and key count."

    def handle(self, *args, **options):
        from apps.core.cache_backend import ResilientRedisCache

        backend = caches['default']  # the real backend (django.core.cache.cache is only a proxy to it)
        if not isinstance(backend, ResilientRedisCache):
            self.stdout.write('The cache is not Redis (REDIS_URL is unset): nothing to report.')
            return
        try:
            client = backend.client.get_client(write=True)
            stats, memory, keys = client.info('stats'), client.info('memory'), client.dbsize()
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(f'The shared cache could not be reached ({type(exc).__name__}).')
            raise SystemExit(1)
        hits, misses = int(stats.get('keyspace_hits', 0)), int(stats.get('keyspace_misses', 0))
        total = hits + misses
        self.stdout.write(f'keyspace_hits={hits}')
        self.stdout.write(f'keyspace_misses={misses}')
        self.stdout.write(f"hit_rate={hits / total:.3f}" if total else 'hit_rate=n/a')
        self.stdout.write(f"used_memory={memory.get('used_memory_human', '?')}")
        self.stdout.write(f'keys={keys}')
        self.stdout.write(f"evicted_keys={int(stats.get('evicted_keys', 0))}")
