import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.bookings.models import Booking


def last_ten_digits(value):
    """The last 10 digits of a phone number typed any way ("+91 90000-00001", "090000 00001"), or ''."""
    digits = re.sub(r'\D', '', value or '')
    return digits[-10:] if len(digits) >= 10 else ''


class Command(BaseCommand):
    help = (
        "Link old bookings that have no student account to the account they belong to, but only when the "
        "phone number typed on the booking matches EXACTLY ONE verified account. A DRY RUN unless --apply is "
        "given; --apply writes an undo file (booking ids only) and --restore <file> reverses it. Runs only "
        "when APP_ENV=staging. Prints counts only: never a name, email or phone number. Bookings that cannot "
        "be matched stay as they are, visible to the hostel owner and staff only."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show the counts and change nothing (the default).')
        parser.add_argument('--apply', action='store_true', help='Really link the bookings.')
        parser.add_argument('--undo-file', default='', help='Where to write the ids that --apply changes.')
        parser.add_argument('--restore', default='', help='Unlink the bookings listed in an undo file.')

    def handle(self, *args, **options):
        if settings.APP_ENV != 'staging':
            raise CommandError(
                "Refusing to run: APP_ENV is not 'staging'. This command is for the staging database; "
                "ask before using it anywhere else."
            )
        if options['apply'] and options['dry_run']:
            raise CommandError('Use either --dry-run or --apply, not both.')
        if options['restore']:
            return self._restore(Path(options['restore']))

        Owner = get_user_model()
        owners_by_phone = defaultdict(list)
        for pk, phone in Owner.objects.filter(is_verified=True).exclude(phone_number__isnull=True).exclude(phone_number='').values_list('pk', 'phone_number'):
            key = last_ten_digits(phone)
            if key:
                owners_by_phone[key].append(pk)

        counts = dict(total=0, no_phone=0, unusable=0, one=0, several=0, none=0)
        plan = defaultdict(list)  # owner id -> booking ids
        for booking_id, phone in Booking.objects.filter(student__isnull=True).values_list('pk', 'student_phone').iterator():
            counts['total'] += 1
            if not (phone or '').strip():
                counts['no_phone'] += 1
                continue
            key = last_ten_digits(phone)
            if not key:
                counts['unusable'] += 1
                continue
            matches = owners_by_phone.get(key, [])
            if len(matches) == 1:
                counts['one'] += 1
                plan[matches[0]].append(booking_id)
            elif len(matches) > 1:
                counts['several'] += 1
            else:
                counts['none'] += 1

        apply = options['apply']
        write = self.stdout.write
        write(f"{'Linking' if apply else 'DRY RUN: counts for'} legacy bookings (no student account):")
        write(f"  legacy bookings: {counts['total']}")
        write(f"  no phone typed (left alone): {counts['no_phone']}")
        write(f"  phone is not a usable number (left alone): {counts['unusable']}")
        write(f"  phone matches exactly one verified account ({'linked' if apply else 'would be linked'}): {counts['one']}")
        write(f"  phone matches several verified accounts (left alone): {counts['several']}")
        write(f"  phone matches no verified account (left alone): {counts['none']}")

        if not apply:
            write('DRY RUN: nothing changed. Re-run with --apply to link them (reversible with --restore).')
            return
        if not counts['one']:
            write('Nothing to link.')
            return

        booking_ids = [str(b) for ids in plan.values() for b in ids]
        undo = Path(options['undo_file'] or f"linked_bookings_{datetime.now():%Y%m%d_%H%M%S}.json")
        undo.write_text(json.dumps({'created': datetime.now().isoformat(), 'booking_ids': booking_ids}, indent=2))
        linked = 0
        for owner_id, ids in plan.items():
            # student__isnull again, so a booking someone linked in the meantime is never overwritten
            linked += Booking.objects.filter(pk__in=ids, student__isnull=True).update(student_id=owner_id)
        self.stdout.write(self.style.SUCCESS(
            f'Linked {linked}. Undo file: {undo} (python manage.py link_legacy_bookings --restore {undo})'
        ))

    def _restore(self, path):
        if not path.exists():
            raise CommandError(f'Undo file not found: {path}')
        ids = json.loads(path.read_text())['booking_ids']
        changed = Booking.objects.filter(pk__in=ids).update(student=None)
        self.stdout.write(self.style.SUCCESS(f'Unlinked {changed} booking(s) from {path}.'))
