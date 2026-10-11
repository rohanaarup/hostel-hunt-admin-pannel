from unittest import mock

from django.db import OperationalError
from django.test import Client, SimpleTestCase, TestCase, override_settings


class HealthzTests(SimpleTestCase):
    """SimpleTestCase forbids database access, so a pass proves /healthz never touches it."""

    def test_healthz_is_ok_with_the_database_blocked(self):
        response = Client().get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @override_settings(ALLOWED_HOSTS=['api.example.com'])
    def test_healthz_ignores_allowed_hosts(self):
        response = Client(HTTP_HOST='10.0.0.5').get('/healthz')
        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_healthz_is_not_redirected_to_https(self):
        response = Client().get('/healthz')
        self.assertEqual(response.status_code, 200)


class ReadyzTests(TestCase):
    def test_readyz_is_ok_when_the_database_answers(self):
        response = Client().get('/readyz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readyz_is_503_without_leaking_the_error(self):
        boom = OperationalError('could not connect to server at secret-host')
        with mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.cursor', side_effect=boom):
            response = Client().get('/readyz')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'secret-host', response.content)
