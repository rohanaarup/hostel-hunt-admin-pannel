import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.hostels.models import Hostel


class Command(BaseCommand):
    help = (
        "Hide test-looking hostels from the public list by setting is_active=False. Nothing is deleted. "
        "A DRY RUN unless --apply is given; --apply writes an undo file and --restore <file> reverses it. "
        "Runs only when APP_ENV=staging. Test-looking means: the hostel's city is inactive, or its city or "
        "state text contains 'test'. Use --ids to name hostels explicitly instead."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Really deactivate (default is a dry run).')
        parser.add_argument('--ids', default='', help='Comma-separated hostel ids to deactivate instead of the rules.')
        parser.add_argument('--undo-file', default='', help='Where to write the ids that --apply changes.')
        parser.add_argument('--restore', default='', help='Reactivate the hostels listed in an undo file.')

    def handle(self, *args, **options):
        if settings.APP_ENV != 'staging':
            raise CommandError(
                "Refusing to run: APP_ENV is not 'staging'. This command is for the staging database; "
                "ask before using it anywhere else."
            )

        if options['restore']:
            return self._restore(Path(options['restore']))

        qs = Hostel.objects.filter(is_active=True)
        ids = [part.strip() for part in options['ids'].split(',') if part.strip()]
        if ids:
            qs = qs.filter(pk__in=ids)
        else:
            qs = qs.filter(
                Q(city_ref__is_active=False) | Q(city__icontains='test') | Q(state__icontains='test')
            )
        hostels = list(qs.order_by('created_at', 'pk'))

        self.stdout.write(f"{'DRY RUN: would deactivate' if not options['apply'] else 'Deactivating'} {len(hostels)} hostel(s):")
        for hostel in hostels:
            self.stdout.write(f"  {hostel.pk}  {hostel.name!r}  city={hostel.city!r}  state={hostel.state!r}")
        if not hostels:
            return
        if not options['apply']:
            self.stdout.write('DRY RUN: nothing changed. Re-run with --apply to deactivate (reversible with --restore).')
            return

        undo = Path(options['undo_file'] or f"deactivated_hostels_{datetime.now():%Y%m%d_%H%M%S}.json")
        undo.write_text(json.dumps({'created': datetime.now().isoformat(), 'hostel_ids': [str(h.pk) for h in hostels]}, indent=2))
        Hostel.objects.filter(pk__in=[h.pk for h in hostels]).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Deactivated {len(hostels)}. Undo file: {undo} (python manage.py deactivate_test_hostels --restore {undo})'))

    def _restore(self, path):
        if not path.exists():
            raise CommandError(f'Undo file not found: {path}')
        ids = json.loads(path.read_text())['hostel_ids']
        changed = Hostel.objects.filter(pk__in=ids, is_active=False).update(is_active=True)
        self.stdout.write(self.style.SUCCESS(f'Restored {changed} hostel(s) from {path}.'))
