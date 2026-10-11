"""
A small, fixed catalogue used by the staging seed command and by the contract tests.

Everything is keyed on stable ids (uuid5 of a name) and reserved example.test addresses, so
running it twice changes nothing and it can never be mistaken for real data.
"""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.hostels.models import Hostel
from apps.media_uploads.models import MediaItem
from apps.rooms.models import Bed, Room

SEED_NAMESPACE = uuid.UUID('6f1c0f6e-6f55-4b53-9a3e-1b0a5c3d7e11')
SEED_EMAIL_DOMAIN = 'example.test'
SEED_EMAIL = f'seed.owner@{SEED_EMAIL_DOMAIN}'
# Staging only: the seed command refuses to run anywhere else. This is not a real credential.
SEED_PASSWORD = 'StagingSeed#2026'

CATALOG = [
    {
        'key': 'alpha', 'name': 'Seed Alpha Residency', 'city': 'Hyderabad', 'state': 'Telangana',
        'locality': 'Gachibowli', 'pincode': '500032', 'gender_type': 'boys',
        'amenities': ['wifi', 'ac'],
        'rooms': [('Single AC', 'single', 1, '9500.00', True), ('Double', 'double', 2, '6500.00', False)],
    },
    {
        'key': 'beta', 'name': 'Seed Beta Stay', 'city': 'Hyderabad', 'state': 'Telangana',
        'locality': 'Kondapur', 'pincode': '500084', 'gender_type': 'girls',
        'amenities': ['wifi'],
        'rooms': [('Triple', 'triple', 3, '5200.00', False)],
    },
    {
        'key': 'gamma', 'name': 'Seed Gamma PG', 'city': 'Pune', 'state': 'Maharashtra',
        'locality': 'Kothrud', 'pincode': '411038', 'gender_type': 'co_living',
        'amenities': ['wifi', 'ac', 'gym'],
        'rooms': [('Double AC', 'double', 2, '8000.00', True)],
    },
]


def seed_id(*parts):
    return uuid.uuid5(SEED_NAMESPACE, ':'.join(parts))


def ensure_sample_catalog():
    """Create or update the sample owner, hostels, rooms, beds and cover images. Returns the owner."""
    Owner = get_user_model()
    owner = Owner.objects.filter(email=SEED_EMAIL).first()
    if owner is None:
        owner = Owner.objects.create_user(email=SEED_EMAIL, display_name='Seed Owner', password=SEED_PASSWORD)

    for spec in CATALOG:
        hostel, _ = Hostel.objects.update_or_create(
            id=seed_id('hostel', spec['key']),
            defaults=dict(
                owner=owner, name=spec['name'], owner_name='Seed Owner', contact_number='9000000000',
                email=SEED_EMAIL, locality=spec['locality'], address=f"1 Sample Road, {spec['locality']}",
                city=spec['city'], state=spec['state'], pincode=spec['pincode'],
                gender_type=spec['gender_type'], amenities=spec['amenities'],
                occupancy_types=sorted({room[1] for room in spec['rooms']}), is_active=True,
            ),
        )
        for name, sharing, beds, price, is_ac in spec['rooms']:
            room, _ = Room.objects.update_or_create(
                id=seed_id('room', spec['key'], name),
                defaults=dict(
                    hostel=hostel, room_name=name, room_number=name[:3].upper(), sharing_type=sharing,
                    capacity=beds, bed_count=beds, available_beds=beds, price_per_month=Decimal(price),
                    is_ac=is_ac, is_active=True,
                ),
            )
            for number in range(1, beds + 1):
                Bed.objects.get_or_create(room=room, bed_number=number)
        MediaItem.objects.update_or_create(
            id=seed_id('media', spec['key']),
            defaults=dict(
                hostel=hostel, file_url=f"https://{SEED_EMAIL_DOMAIN}/seed/{spec['key']}.jpg",
                category='hostel', order_index=0,
            ),
        )
    return owner
