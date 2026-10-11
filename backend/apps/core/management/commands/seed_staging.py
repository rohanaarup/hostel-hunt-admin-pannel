from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.sample_data import SEED_EMAIL, SEED_EMAIL_DOMAIN, SEED_PASSWORD, ensure_sample_catalog
from apps.hostels.models import Hostel
from apps.rooms.models import Bed, Room


class Command(BaseCommand):
    help = (
        "Load a small fixed sample catalogue (3 hostels with rooms, beds and cover images) into a "
        "STAGING database. Safe to run repeatedly. Refuses to run unless APP_ENV=staging, and refuses "
        "if the database holds owners that are not seed data."
    )

    def handle(self, *args, **options):
        if settings.APP_ENV != 'staging':
            raise CommandError(
                "Refusing to seed: APP_ENV is not 'staging'. Set APP_ENV=staging in the staging "
                "service's environment. Never run this against production."
            )
        Owner = get_user_model()
        if Owner.objects.exclude(email__endswith=f'@{SEED_EMAIL_DOMAIN}').exists():
            raise CommandError(
                f"Refusing to seed: the database has owners that are not seed data (emails not ending "
                f"in @{SEED_EMAIL_DOMAIN}). This looks like real data, not a staging database."
            )
        ensure_sample_catalog()
        self.stdout.write(
            f"Seeded staging: {Hostel.objects.count()} hostels, {Room.objects.count()} rooms, "
            f"{Bed.objects.count()} beds. Sample owner login: {SEED_EMAIL} / {SEED_PASSWORD}"
        )
