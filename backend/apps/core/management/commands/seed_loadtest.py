import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.bookings.models import Booking, Wishlist
from apps.core.sample_data import SEED_EMAIL_DOMAIN, ensure_sample_catalog, seed_id
from apps.hostels.locations import normalise_slug
from apps.hostels.models import City, Hostel, Locality
from apps.media_uploads.models import MediaItem
from apps.payments.models import Payment
from apps.rooms.models import Bed, Room

STUDENT_EMAIL = 'load{n:04d}@' + SEED_EMAIL_DOMAIN
PASSWORD_VARIABLE = 'LOADTEST_PASSWORD'
MIN_PASSWORD_LENGTH = 12

# (city, state, [localities]) the extra hostels are spread over.
PLACES = [
    ('Hyderabad', 'Telangana', ['Gachibowli', 'Kondapur', 'Madhapur', 'Ameerpet', 'Kukatpally']),
    ('Pune', 'Maharashtra', ['Kothrud', 'Hinjewadi', 'Viman Nagar']),
    ('Bengaluru', 'Karnataka', ['Koramangala', 'Indiranagar', 'Whitefield']),
]
GENDERS = ['boys', 'girls', 'co_living']
AMENITIES = [['wifi'], ['wifi', 'ac'], ['wifi', 'ac', 'gym'], ['wifi', 'laundry', 'meals'], ['wifi', 'ac', 'laundry', 'meals', 'gym']]
ROOM_SHAPES = [('Single', 'single', 1, '9500.00', True), ('Double', 'double', 2, '6500.00', False), ('Triple', 'triple', 3, '5200.00', False)]


class Command(BaseCommand):
    help = (
        "Load a LOAD-TEST data set into a STAGING database: many students (load0001@example.test ...), "
        "40 hostels with rooms and beds, and a few settled payments for status polling. Refuses to run unless "
        f"APP_ENV=staging and refuses if the database holds users that are not example.test accounts. "
        f"The password for the students comes from the {PASSWORD_VARIABLE} environment variable and is never printed. "
        "Safe to run again; --reset-activity removes what a test run created."
    )

    def add_arguments(self, parser):
        parser.add_argument('--students', type=int, default=300)
        parser.add_argument('--hostels', type=int, default=40)
        parser.add_argument('--payments', type=int, default=50, help='Settled payments students can poll the status of')
        parser.add_argument('--reset-activity', action='store_true', help='Delete bookings and saved hostels made by load students first')

    def handle(self, *args, **options):
        if settings.APP_ENV != 'staging':
            raise CommandError(
                "Refusing to seed: APP_ENV is not 'staging'. Load-test data must never reach production."
            )
        Owner = get_user_model()
        if Owner.objects.exclude(email__endswith=f'@{SEED_EMAIL_DOMAIN}').exists():
            raise CommandError(
                f"Refusing to seed: the database has users whose emails do not end in @{SEED_EMAIL_DOMAIN}. "
                "This looks like real data, not a staging database."
            )
        password = os.environ.get(PASSWORD_VARIABLE, '')
        if len(password) < MIN_PASSWORD_LENGTH:
            raise CommandError(f"Set {PASSWORD_VARIABLE} (at least {MIN_PASSWORD_LENGTH} characters) in the environment.")

        owner = ensure_sample_catalog()
        students = self._students(Owner, options['students'], password)
        if options['reset_activity']:
            removed, _ = Booking.objects.filter(student__in=students).delete()
            Wishlist.objects.filter(user__in=students).delete()
            self.stdout.write(f"Removed earlier load-test activity ({removed} rows including payments).")
        self._hostels(owner, options['hostels'])
        self._payments(students[: options['payments']])

        self.stdout.write(
            f"Load data ready: {len(students)} students, {Hostel.objects.count()} hostels, "
            f"{Room.objects.count()} rooms, {Bed.objects.count()} beds, {Payment.objects.count()} payments."
        )

    def _students(self, Owner, count, password):
        students = []
        for n in range(1, count + 1):
            email = STUDENT_EMAIL.format(n=n)
            student = Owner.objects.filter(email=email).first()
            if student is None:
                student = Owner.objects.create_user(email=email, display_name=f'Load Student {n}', password=password, is_verified=True)
            elif not student.check_password(password):
                student.set_password(password)
                student.save(update_fields=['password'])
            students.append(student)
        return students

    def _hostels(self, owner, count):
        slots = [(city, state, locality) for city, state, localities in PLACES for locality in localities]
        for i in range(count):
            city_name, state, locality_name = slots[i % len(slots)]
            city = City.objects.filter(slug=normalise_slug(city_name)).first() or City.objects.create(name=city_name, state=state)
            locality = Locality.objects.filter(city=city, slug=normalise_slug(locality_name)).first() or Locality.objects.create(city=city, name=locality_name)
            hostel, _ = Hostel.objects.update_or_create(
                id=seed_id('hostel', f'load{i}'),
                defaults=dict(
                    owner=owner, name=f'Load Test Hostel {i + 1}', owner_name='Seed Owner', contact_number='9000000000',
                    email=owner.email, locality=locality_name, address=f'{i + 1} Load Road, {locality_name}',
                    city=city_name, state=state, pincode='500000', city_ref=city, locality_ref=locality,
                    gender_type=GENDERS[i % len(GENDERS)], amenities=AMENITIES[i % len(AMENITIES)],
                    occupancy_types=sorted({shape[1] for shape in ROOM_SHAPES}), is_active=True,
                ),
            )
            for name, sharing, beds, price, is_ac in ROOM_SHAPES:
                for copy in range(1, 4):  # three rooms of each shape
                    room, _ = Room.objects.update_or_create(
                        id=seed_id('room', f'load{i}', f'{name}{copy}'),
                        defaults=dict(
                            hostel=hostel, room_name=f'{name} {copy}', room_number=f'{name[:1]}{copy:02d}', sharing_type=sharing,
                            capacity=beds, bed_count=beds, available_beds=beds,
                            price_per_month=Decimal(price) + Decimal(i * 50), is_ac=is_ac, is_active=True,
                        ),
                    )
                    for number in range(1, beds + 1):
                        Bed.objects.get_or_create(room=room, bed_number=number)
            for position in range(3):
                MediaItem.objects.update_or_create(
                    id=seed_id('media', f'load{i}', str(position)),
                    defaults=dict(hostel=hostel, file_url=f'https://{SEED_EMAIL_DOMAIN}/seed/load{i}-{position}.jpg', category='hostel', order_index=position),
                )

    def _payments(self, students):
        """One settled online booking plus payment per student, so the status poll has something real to read."""
        hostel = Hostel.objects.filter(id=seed_id('hostel', 'load0')).first()
        room = hostel.rooms.first() if hostel else None
        if room is None:
            return
        for n, student in enumerate(students, start=1):
            booking_id = seed_id('booking', f'load{student.email}')
            booking, _ = Booking.objects.get_or_create(
                id=booking_id,
                defaults=dict(
                    hostel=hostel, room=room, room_name=room.room_name, student=student, student_name=student.display_name,
                    payment_mode='online', status='paid', amount=room.price_per_month, check_in_date=timezone.localdate() + timedelta(days=7),
                ),
            )
            Payment.objects.get_or_create(
                id=seed_id('payment', f'load{student.email}'),
                defaults=dict(
                    booking=booking, razorpay_order_id=f'order_load_{uuid.uuid5(booking_id, "order").hex[:20]}',
                    amount=room.price_per_month, status=Payment.Status.SUCCESS, verified_at=timezone.now(),
                ),
            )
