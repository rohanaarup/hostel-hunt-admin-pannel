import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BACKEND_DIR = Path(__file__).resolve().parents[1]
FLAG = '--i-understand-this-drops-all-tables'


class ResetGuardTests(SimpleTestCase):
    def test_remote_host_is_refused_even_with_the_flag(self):
        from utils.db_safety import ResetRefused, check_reset_allowed
        with self.assertRaises(ResetRefused):
            check_reset_allowed('db.example.com', confirmed=True)

    def test_local_host_without_the_flag_is_refused(self):
        from utils.db_safety import ResetRefused, check_reset_allowed
        with self.assertRaises(ResetRefused):
            check_reset_allowed('localhost', confirmed=False)

    def test_missing_host_is_refused(self):
        from utils.db_safety import ResetRefused, check_reset_allowed
        for host in ('', None):
            with self.assertRaises(ResetRefused):
                check_reset_allowed(host, confirmed=True)

    def test_local_host_with_the_flag_is_allowed(self):
        from utils.db_safety import check_reset_allowed
        for host in ('localhost', '127.0.0.1', '::1'):
            check_reset_allowed(host, confirmed=True)

    def _run_script(self, name, *args):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings', DEBUG='True',
                   USE_DB='supabase', DATABASE_URL='postgres://u:p@db.invalid:5432/hh')
        return subprocess.run([sys.executable, name, *args], cwd=BACKEND_DIR, env=env,
                              capture_output=True, text=True, timeout=60, input='y\n')

    def test_reset_db_auto_refuses_a_remote_database(self):
        for args in ((), (FLAG,)):
            proc = self._run_script('reset_db_auto.py', *args)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('refus', (proc.stdout + proc.stderr).lower())

    def test_reset_db_refuses_a_remote_database(self):
        for args in ((), (FLAG,)):
            proc = self._run_script('reset_db.py', *args)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('refus', (proc.stdout + proc.stderr).lower())
