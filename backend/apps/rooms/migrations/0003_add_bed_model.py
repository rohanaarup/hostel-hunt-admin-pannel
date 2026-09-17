# Generated manually — adds the Bed model to the rooms app.
#
# Bed rows represent individual bed slots within a Room.
# The held_until field is critical for the payment pipeline:
# CreateOrderView uses select_for_update() on Bed rows to prevent
# concurrent double-booking during the payment window.

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0002_room_bed_count_room_floor_number_room_room_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='Bed',
            fields=[
                ('bed_id', models.UUIDField(
                    db_column='bed_id',
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False,
                )),
                ('bed_number', models.PositiveIntegerField(
                    help_text='1-indexed bed number within the room (e.g. 1, 2, 3).',
                )),
                ('is_available', models.BooleanField(
                    db_index=True,
                    default=True,
                    help_text='False once a payment is confirmed for this bed.',
                )),
                ('held_until', models.DateTimeField(
                    blank=True,
                    db_index=True,
                    help_text='Set while payment is in-flight; cleared on capture or expiry.',
                    null=True,
                )),
                ('room', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='beds',
                    to='rooms.room',
                )),
            ],
            options={
                'db_table': 'beds',
                'ordering': ['room', 'bed_number'],
                'unique_together': {('room', 'bed_number')},
            },
        ),
    ]
