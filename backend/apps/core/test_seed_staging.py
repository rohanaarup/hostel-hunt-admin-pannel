from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.hostels.models import Hostel
from apps.rooms.models import Bed, Room

Owner = get_user_model()


def run_seed():
    out = StringIO()
    call_command('seed_staging', stdout=out)
    return out.getvalue()


class SeedStagingGuardTests(TestCase):
    @override_settings(APP_ENV='production')
    def test_refuses_in_production(self):
        with self.assertRaises(CommandError) as ctx:
            run_seed()
        self.assertIn('APP_ENV', str(ctx.exception))
        self.assertEqual(Hostel.objects.count(), 0)

    @override_settings(APP_ENV='development')
    def test_refuses_in_development(self):
        with self.assertRaises(CommandError):
            run_seed()
        self.assertEqual(Hostel.objects.count(), 0)

    @override_settings(APP_ENV='staging')
    def test_refuses_when_real_looking_owners_exist(self):
        Owner.objects.create_user(email='real.person@gmail.example', display_name='Real', password='pass12345')
        with self.assertRaises(CommandError) as ctx:
            run_seed()
        self.assertIn('not seed data', str(ctx.exception))
        self.assertEqual(Hostel.objects.count(), 0)


@override_settings(APP_ENV='staging')
class SeedStagingTests(TestCase):
    def test_seeds_a_usable_catalog(self):
        run_seed()
        self.assertEqual(Hostel.objects.count(), 3)
        self.assertTrue(Room.objects.exists())
        self.assertTrue(Bed.objects.exists())
        self.assertFalse(Owner.objects.exclude(email__endswith='@example.test').exists())

    def test_is_idempotent(self):
        run_seed()
        counts = (Owner.objects.count(), Hostel.objects.count(), Room.objects.count(), Bed.objects.count())
        run_seed()
        self.assertEqual(
            counts,
            (Owner.objects.count(), Hostel.objects.count(), Room.objects.count(), Bed.objects.count()),
        )
