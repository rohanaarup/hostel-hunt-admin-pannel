"""
API contract tests.

contract/endpoints.txt lists every endpoint the Flutter app and the admin site call.
These tests fail when a route is renamed or removed, when a method is not allowed, and
when a documented gap ("expected-fail") has been fixed but its marker is still there.
"""
import json
import os
import re
import uuid
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import Resolver404, resolve
from rest_framework.test import APIClient

from apps.core.sample_data import ensure_sample_catalog

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONTRACT_FILE = BACKEND_DIR / 'contract' / 'endpoints.txt'
HOSTELS_FIXTURE = BACKEND_DIR / 'contract' / 'fixtures' / 'hostels_list.json'
API_PREFIX = '/api/v1'
SAMPLE_ID = '00000000-0000-0000-0000-000000000001'
MARKER = '| expected-fail:'


def read_entries():
    """Yield (client, method, path, expected_fail_reason_or_None) for each contract line."""
    entries = []
    for number, raw in enumerate(CONTRACT_FILE.read_text(encoding='utf-8').splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        body, _, reason = line.partition(MARKER)
        parts = body.split()
        assert len(parts) == 3, f'{CONTRACT_FILE.name}:{number}: expected "<client> <METHOD> <path>", got {raw!r}'
        client, method, path = parts
        assert client in ('app', 'admin'), f'{CONTRACT_FILE.name}:{number}: unknown client {client!r}'
        entries.append((client, method.upper(), path, reason.strip() or None, number))
    return entries


def allowed_methods(view_func):
    actions = getattr(view_func, 'actions', None)  # ViewSet routed by a router
    if actions:
        return {m.upper() for m in actions}
    cls = getattr(view_func, 'cls', None) or getattr(view_func, 'view_class', None)
    if cls is None:
        return set()
    return {m.upper() for m in cls.http_method_names if m != 'options' and hasattr(cls, m)}


def endpoint_problem(method, path):
    """None when the route exists and allows the method, otherwise a short reason."""
    url = API_PREFIX + path.replace('{id}', SAMPLE_ID).replace('{slug}', 'hyderabad')
    try:
        match = resolve(url)
    except Resolver404:
        return 'route does not exist (404)'
    # A router detail route such as bookings/<pk>/ also "resolves" for words like my-bookings. Ids in
    # this API are UUIDs, so a non-UUID segment means the server would look up an object and answer 404.
    for name, value in match.kwargs.items():
        if name == 'pk' or name.endswith('_id'):
            try:
                uuid.UUID(str(value))
            except ValueError:
                return f"'{value}' is read as an object id by {match.view_name}, so the server answers 404"
    methods = allowed_methods(match.func)
    if method not in methods:
        return f'method not allowed (405); the view allows {", ".join(sorted(methods)) or "nothing"}'
    return None


class EndpointContractTests(SimpleTestCase):
    def test_contract_file_has_entries_for_both_clients(self):
        clients = {client for client, *_ in read_entries()}
        self.assertEqual(clients, {'app', 'admin'})

    def test_every_endpoint_matches_its_documented_state(self):
        broken, fixed = [], []
        for client, method, path, reason, number in read_entries():
            if '?' in path:
                continue
            problem = endpoint_problem(method, path)
            where = f'{CONTRACT_FILE.name}:{number} {client} {method} {path}'
            if problem and reason is None:
                broken.append(f'{where}: {problem}')
            if not problem and reason is not None:
                fixed.append(f'{where}: now works, remove the expected-fail marker')
        message = ''
        if broken:
            message += 'Endpoints the clients call that are broken (rename or remove?):\n  ' + '\n  '.join(broken)
        if fixed:
            message += '\nExpected failures that now pass:\n  ' + '\n  '.join(fixed)
        self.assertFalse(broken or fixed, message)


class HostelQueryParameterContractTests(TestCase):
    """The client sends these filters to GET /hostels/; check each is honoured."""

    @classmethod
    def setUpTestData(cls):
        ensure_sample_catalog()

    def names(self, **params):
        response = APIClient().get(API_PREFIX + '/hostels/', params)
        self.assertEqual(response.status_code, 200)
        return {item['name'] for item in response.json()['results']}

    # (parameters sent, expected). A set means "exactly these hostel names"; an int means "this many".
    CHECKS = {
        'city': ({'city': 'Hyderabad'}, {'Seed Alpha Residency', 'Seed Beta Stay'}),
        'locality': ({'city': 'Hyderabad', 'locality': 'Gachibowli'}, {'Seed Alpha Residency'}),
        'page_size': ({'page_size': 1}, 1),
        'page': ({'page': 2, 'page_size': 1}, 1),
        'gender_type': ({'gender_type': 'girls'}, {'Seed Beta Stay'}),
        'search': ({'search': 'Gamma'}, {'Seed Gamma PG'}),
        'amenity': ({'amenity': 'gym'}, {'Seed Gamma PG'}),
    }

    def test_every_parameter_matches_its_documented_state(self):
        broken, fixed = [], []
        for client, method, path, reason, number in read_entries():
            if '?' not in path:
                continue
            base, _, param = path.partition('?')
            self.assertEqual(base, '/hostels/', f'no check written for {path}')
            params, expected = self.CHECKS[param]
            got = self.names(**params)
            honoured = (len(got) == expected) if isinstance(expected, int) else (got == expected)
            where = f'{CONTRACT_FILE.name}:{number} {client} GET {path}'
            if not honoured and reason is None:
                broken.append(f'{where}: the backend ignores or mishandles this parameter')
            if honoured and reason is not None:
                fixed.append(f'{where}: now honoured, remove the expected-fail marker')
        message = '\n'.join(broken + fixed)
        self.assertFalse(broken or fixed, message)


UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
DATETIME_RE = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d')


def normalise(value):
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, str) and UUID_RE.match(value):
        return '<uuid>'
    if isinstance(value, str) and DATETIME_RE.match(value):
        return '<datetime>'
    return value


class HostelListFixtureTests(TestCase):
    """The committed sample of the real /hostels/ list response must match the serializer.

    The Flutter app parses a copy of this file in its own tests. When the response changes this
    fails until the fixture is regenerated and copied to the app repo:
        UPDATE_CONTRACT_FIXTURES=1 python manage.py test apps.core.test_contract.HostelListFixtureTests
    """

    @classmethod
    def setUpTestData(cls):
        ensure_sample_catalog()

    def test_fixture_matches_the_real_response(self):
        response = APIClient().get(API_PREFIX + '/hostels/', {'city': 'Hyderabad'})
        self.assertEqual(response.status_code, 200)
        actual = normalise(response.json())
        actual['results'] = sorted(actual['results'], key=lambda item: item['name'])

        if os.environ.get('UPDATE_CONTRACT_FIXTURES') == '1':
            HOSTELS_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            HOSTELS_FIXTURE.write_text(json.dumps(actual, indent=2, sort_keys=True) + '\n', encoding='utf-8')

        expected = json.loads(HOSTELS_FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(
            actual, expected,
            'GET /hostels/ no longer matches contract/fixtures/hostels_list.json. If the change is '
            'intended, regenerate it (see this class docstring) and copy it to the app repo.',
        )

    def test_fixture_carries_what_the_app_reads(self):
        item = json.loads(HOSTELS_FIXTURE.read_text(encoding='utf-8'))['results'][0]
        for key in ('hostel_id', 'name', 'city', 'gender_type', 'cover_image', 'price_from', 'price_to'):
            self.assertIn(key, item)
        self.assertTrue(item['cover_image'])
        self.assertTrue(item['price_from'])
