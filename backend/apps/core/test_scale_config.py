"""
Phase 3, Parts 5 and 6: the scale blueprint and the capacity model.

render.yaml and render.scale.yaml are validated against Render's own published schema (stored in
backend/contract/render.schema.json, read from https://render.com/schema/render.yaml.json on 2026-10-29), so a key name
is never a guess.
"""
import importlib.util
import json
from io import StringIO
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase
from jsonschema import validators

BACKEND = Path(settings.BASE_DIR)
REPO = BACKEND.parent


def load(name):
    return yaml.safe_load((REPO / name).read_text(encoding='utf-8'))


def schema_errors(document):
    schema = json.loads((BACKEND / 'contract' / 'render.schema.json').read_text(encoding='utf-8'))
    validator = validators.validator_for(schema)(schema)
    return [f"{list(e.path)}: {e.message[:140]}" for e in validator.iter_errors(document)]


def service(document, name):
    return next(s for s in document['services'] if s['name'] == name)


def env(svc):
    return {e['key']: e for e in svc.get('envVars', [])}


class RenderSchemaTests(SimpleTestCase):
    def test_the_current_blueprint_is_valid(self):
        self.assertEqual(schema_errors(load('render.yaml')), [])

    def test_the_scale_blueprint_is_valid(self):
        self.assertEqual(schema_errors(load('render.scale.yaml')), [])

    def test_the_schema_check_can_fail(self):
        broken = load('render.scale.yaml')
        service(broken, 'hostel-hunt-backend')['numInstanses'] = 2  # a misspelt key must be caught
        self.assertTrue(schema_errors(broken))

    def test_the_off_value_is_the_string_not_the_boolean(self):
        self.assertEqual(service(load('render.yaml'), 'hostel-hunt-backend')['autoDeployTrigger'], 'off')

    def test_an_autoscaling_block_with_the_schema_key_names_is_valid(self):
        document = load('render.scale.yaml')
        svc = service(document, 'hostel-hunt-backend')
        svc.pop('numInstances')
        svc['scaling'] = {'minInstances': 2, 'maxInstances': 4, 'targetCPUPercent': 60}
        self.assertEqual(schema_errors(document), [])


class ScaleBlueprintTests(SimpleTestCase):
    def setUp(self):
        self.doc = load('render.scale.yaml')
        self.prod = service(self.doc, 'hostel-hunt-backend')

    def test_production_runs_two_instances_for_failover(self):
        self.assertEqual(self.prod['numInstances'], 2)

    def test_migrate_runs_once_per_deploy_not_in_the_build(self):
        self.assertIn('migrate', self.prod['preDeployCommand'])
        self.assertNotIn('migrate', self.prod['buildCommand'])
        for name in ('hostel-hunt-backend', 'hostel-hunt-backend-staging'):
            self.assertIn('migrate', service(self.doc, name)['preDeployCommand'])

    def test_the_cache_is_internal_only_and_wired_to_the_web_service(self):
        cache = service(self.doc, 'hostel-hunt-cache')
        self.assertEqual(cache['type'], 'keyvalue')
        self.assertEqual(cache['ipAllowList'], [])  # nothing outside Render can connect
        self.assertEqual(cache['maxmemoryPolicy'], 'allkeys-lru')
        ref = env(self.prod)['REDIS_URL']['fromService']
        self.assertEqual((ref['type'], ref['name'], ref['property']), ('keyvalue', 'hostel-hunt-cache', 'connectionString'))

    def test_staging_has_its_own_cache(self):
        ref = env(service(self.doc, 'hostel-hunt-backend-staging'))['REDIS_URL']['fromService']
        self.assertEqual(ref['name'], 'hostel-hunt-cache-staging')

    def test_production_stays_in_session_mode_and_one_proxy_until_the_founder_changes_them(self):
        values = env(self.prod)
        self.assertEqual(values['DB_POOL_MODE']['value'], 'session')
        self.assertEqual(values['TRUSTED_PROXY_COUNT']['value'], '1')

    def test_the_edge_secret_is_never_a_value_in_the_file(self):
        entry = env(self.prod)['EDGE_SHARED_SECRET']
        self.assertIs(entry['sync'], False)
        self.assertNotIn('value', entry)

    def test_no_secret_value_is_written_in_either_blueprint(self):
        secrets = ('SECRET_KEY', 'DATABASE_URL', 'EMAIL_API_KEY', 'RAZORPAY_KEY_SECRET', 'RAZORPAY_WEBHOOK_SECRET',
                   'SENTRY_DSN', 'HEARTBEAT_URL', 'EDGE_SHARED_SECRET', 'REDIS_URL')
        for name in ('render.yaml', 'render.scale.yaml'):
            for svc in load(name)['services']:
                for key, entry in env(svc).items():
                    if key in secrets:
                        self.assertNotIn('value', entry, f'{name} {svc["name"]} {key}')

    def test_the_start_command_keeps_the_statement_timeout_and_the_release_tag(self):
        for name in ('hostel-hunt-backend', 'hostel-hunt-backend-staging'):
            start = service(self.doc, name)['startCommand']
            self.assertIn('DB_STATEMENT_TIMEOUT_MS=25000', start)
            self.assertIn('GIT_COMMIT=$RENDER_GIT_COMMIT', start)

    def test_the_connection_budget_of_the_chosen_workers_and_threads_is_stated_and_fits_a_larger_pooler(self):
        model = load_model()
        values = env(self.prod)
        workers, threads = int(values['WEB_CONCURRENCY']['value']), int(values['GUNICORN_THREADS']['value'])
        used = model.connections(self.prod['numInstances'], workers, threads)
        self.assertEqual(used, 2 * 3 * 4 + 4)
        self.assertFalse(model.fits_pooler(used, 15), 'the free 15-slot pooler must NOT fit two instances')
        self.assertTrue(model.fits_pooler(used, 60))

    def test_the_current_blueprint_has_no_multi_instance_or_pre_deploy_change(self):
        for svc in load('render.yaml')['services']:
            self.assertNotIn('numInstances', svc)
            self.assertNotIn('preDeployCommand', svc)
            self.assertNotIn('REDIS_URL', env(svc))


def load_model():
    spec = importlib.util.spec_from_file_location('capacity_model', REPO / 'tools' / 'capacity_model.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapacityModelTests(SimpleTestCase):
    def setUp(self):
        self.m = load_model()

    def test_the_connection_formula(self):
        self.assertEqual(self.m.connections(1, 2, 4), 8 + 1 + 1 + 2)
        self.assertEqual(self.m.connections(2, 3, 4, cron_jobs=1, deploy_migrate=1, admin_sessions=2), 28)

    def test_one_free_pooler_fits_one_small_instance_and_no_more(self):
        self.assertEqual(self.m.max_instances(15, 2, 4), 1)   # 8 threads + 4 others = 12 = 80 percent of 15
        self.assertTrue(self.m.fits_pooler(self.m.connections(1, 2, 4), 15))
        self.assertFalse(self.m.fits_pooler(self.m.connections(2, 2, 4), 15))
        self.assertEqual(self.m.max_instances(15, 3, 4), 0)   # one 3 x 4 instance already needs 16 of 12 allowed

    def test_a_larger_pooler_allows_more_instances(self):
        self.assertEqual(self.m.max_instances(200, 3, 4), 13)

    def test_the_eighty_percent_rule(self):
        self.assertTrue(self.m.fits_pooler(48, 60))
        self.assertFalse(self.m.fits_pooler(49, 60))

    def test_peak_users_and_requests_per_second(self):
        concurrent, rps = self.m.request_load(10000)
        self.assertEqual(concurrent, 300)
        self.assertEqual(rps, 60)

    def test_the_edge_removes_the_public_share_it_answers(self):
        self.assertAlmostEqual(self.m.origin_load(100, edge_hit_rate=0.0), 100)
        self.assertAlmostEqual(self.m.origin_load(100, edge_hit_rate=1.0), 20)   # only the 20 percent that is not public
        self.assertAlmostEqual(self.m.origin_load(100, edge_hit_rate=0.5), 60)

    def test_instances_follow_the_sixty_percent_rule_with_a_minimum_of_two(self):
        self.assertEqual(self.m.instances_needed(0.5, 50), 2)
        self.assertEqual(self.m.instances_needed(168, 50), 6)       # 168 / (0.6 x 50) = 5.6
        self.assertEqual(self.m.instances_needed(60, 50), 2)        # exactly two instances at 60 percent each

    def test_it_refuses_to_guess_the_measured_number(self):
        with self.assertRaises(ValueError):
            self.m.instances_needed(10, 0)

    def test_the_hundred_thousand_user_row(self):
        row = self.m.plan(100000, rps_per_instance=50, edge_hit_rate=0.9, workers=3, threads=4, pooler_limit=200)
        self.assertEqual(row['concurrent'], 3000)
        self.assertAlmostEqual(row['total_rps'], 600)
        self.assertAlmostEqual(row['origin_rps'], 600 * (1 - 0.8 * 0.9))
        self.assertEqual(row['instances'], 6)         # ceil(168 / (0.6 x 50)) = ceil(5.6)
        self.assertEqual(row['connections'], 6 * 3 * 4 + 4)
        self.assertTrue(row['fits'])                  # 76 is within 80 percent of 200

    def test_the_command_line_prints_the_three_rows(self):
        out = StringIO()
        import contextlib
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.m.main(['--rps-per-instance', '50']), 0)
        text = out.getvalue()
        self.assertIn('ASSUMPTIONS', text)
        for row in ('1,000', '10,000', '100,000'):
            self.assertIn(row, text)


class CacheStatsCommandTests(SimpleTestCase):
    def test_without_redis_it_says_so_and_succeeds(self):
        import os
        if os.environ.get('REDIS_URL'):
            self.skipTest('this run uses Redis')
        out = StringIO()
        call_command('cache_stats', stdout=out)
        self.assertIn('not Redis', out.getvalue())
