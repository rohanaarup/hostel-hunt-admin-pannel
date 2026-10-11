from django.db import migrations

from apps.hostels.location_backfill import link_hostels, unlink_hostels


def forwards(apps, schema_editor):
    link_hostels(apps.get_model('hostels', 'Hostel'), apps.get_model('hostels', 'City'), apps.get_model('hostels', 'Locality'))


def backwards(apps, schema_editor):
    unlink_hostels(apps.get_model('hostels', 'Hostel'), apps.get_model('hostels', 'City'), apps.get_model('hostels', 'Locality'))


class Migration(migrations.Migration):
    """
    Builds City and Locality rows from the distinct text already on each hostel and links the hostels.

    - The legacy `city` / `locality` / `state` text columns are NOT changed.
    - Spellings are not corrected: each distinct text becomes one entry with the case tidied.
    - Reversible: the reverse clears the links and removes the entries this created.
    - Safe to run twice (entries are matched by normalised name before they are created).
    """

    dependencies = [
        ('hostels', '0005_city_and_locality_tables'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
