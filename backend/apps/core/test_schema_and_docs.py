import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCHEMA_FILE = BACKEND_DIR / 'schema.yml'


class SchemaFileTests(SimpleTestCase):
    def test_committed_schema_matches_the_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'schema.yml'
            call_command('spectacular', file=str(target), stdout=StringIO(), stderr=StringIO())
            generated = target.read_text(encoding='utf-8').replace('\r\n', '\n')
        committed = SCHEMA_FILE.read_text(encoding='utf-8').replace('\r\n', '\n')
        self.assertEqual(
            generated, committed,
            'backend/schema.yml is out of date. A serializer, view or URL changed. If the change is '
            'intended, regenerate it:  python manage.py spectacular --file schema.yml',
        )

    def test_schema_describes_the_public_hostel_list(self):
        text = SCHEMA_FILE.read_text(encoding='utf-8')
        self.assertIn('/api/v1/hostels/:', text)
        self.assertIn('openapi: 3', text)


class ApiDocsAccessTests(SimpleTestCase):
    """Swagger UI and the raw schema are served only in DEBUG or on staging."""

    @override_settings(DEBUG=False, APP_ENV='production')
    def test_not_served_in_production(self):
        client = Client()
        self.assertEqual(client.get('/api/docs/').status_code, 404)
        self.assertEqual(client.get('/api/schema/').status_code, 404)

    @override_settings(DEBUG=False, APP_ENV='staging')
    def test_served_on_staging(self):
        client = Client()
        self.assertEqual(client.get('/api/docs/').status_code, 200)
        self.assertEqual(client.get('/api/schema/').status_code, 200)

    @override_settings(DEBUG=True, APP_ENV='development')
    def test_served_in_debug(self):
        self.assertEqual(Client().get('/api/docs/').status_code, 200)
