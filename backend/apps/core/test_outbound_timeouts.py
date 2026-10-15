"""
Every call that leaves the server must carry a timeout well below the gunicorn timeout, otherwise one hung
provider ties up a worker thread (G03). This scans the source, so a NEW outbound call without a timeout
fails the build (F4 Part 1 writes the scan; it fails today on the calls listed in its message).

Rules:
  * requests.get/post/put/patch/delete/request(...)  needs timeout=<number or name>; a literal must be <= MAX_TIMEOUT.
  * razorpay.Client(...)                             must be given session=... (a session that sets a default timeout).
  * settings.EMAIL_TIMEOUT                           must be <= MAX_TIMEOUT (it is the SMTP socket timeout).
"""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

MAX_TIMEOUT = 10  # seconds; gunicorn's own timeout is 60
HTTP_VERBS = {'get', 'post', 'put', 'patch', 'delete', 'request', 'head', 'options'}
REQUESTS_NAMES = {'requests', '_requests'}


def source_files():
    root = Path(settings.BASE_DIR)
    for folder in ('apps', 'utils', 'config'):
        for path in (root / folder).rglob('*.py'):
            name = path.name
            if any('migrations' in part for part in path.parts) or name.startswith('test') or name.endswith('_test.py'):
                continue
            yield path


def offenders():
    found = []
    for path in source_files():
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            where = f'{path.relative_to(settings.BASE_DIR).as_posix()}:{node.lineno}'
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id in REQUESTS_NAMES and node.func.attr in HTTP_VERBS:
                timeout = next((k.value for k in node.keywords if k.arg == 'timeout'), None)
                if timeout is None:
                    found.append(f'{where} requests.{node.func.attr}() has no timeout')
                elif isinstance(timeout, ast.Constant) and isinstance(timeout.value, (int, float)) and timeout.value > MAX_TIMEOUT:
                    found.append(f'{where} requests.{node.func.attr}() timeout={timeout.value} is above {MAX_TIMEOUT}')
            if isinstance(owner, ast.Name) and owner.id == 'razorpay' and node.func.attr == 'Client':
                if not any(k.arg == 'session' for k in node.keywords):
                    found.append(f'{where} razorpay.Client() is built without a session that sets a timeout')
    return found


class OutboundTimeoutTests(SimpleTestCase):
    def test_every_outbound_http_call_has_a_short_timeout(self):
        self.assertEqual(offenders(), [])

    def test_smtp_timeout_is_short(self):
        self.assertLessEqual(settings.EMAIL_TIMEOUT, MAX_TIMEOUT)
