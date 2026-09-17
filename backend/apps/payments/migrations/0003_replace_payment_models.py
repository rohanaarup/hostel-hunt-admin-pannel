# Generated manually — replaces the old offline Payment model with the
# new Razorpay-specific Payment and PaymentAttempt models.
#
# Migration strategy:
#   0001_initial.py       → created old Payment table (user_name, room_name, etc.)
#   0002_remove_...py     → altered the old Payment table
#   0003_replace_...py    → THIS FILE: drops old table, creates new Payment +
#                           PaymentAttempt tables for the Razorpay flow.
#
# NOTE: No production data was present in the old payments table.
# The old `related_name='payments'` on Booking is preserved on the new FK.

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_remove_payment_amount_remove_payment_method_and_more'),
        ('bookings', '0001_initial'),
    ]

    operations = [
        # ── Drop the old Payment table ────────────────────────────────────────
        migrations.DeleteModel(
            name='Payment',
        ),

        # ── Create new Payment table ──────────────────────────────────────────
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('payment_id', models.UUIDField(
                    db_column='payment_id',
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False,
                )),
                ('razorpay_order_id', models.CharField(
                    db_index=True,
                    help_text='Razorpay order ID returned by the Orders API (e.g. order_XXXX).',
                    max_length=100,
                    unique=True,
                )),
                ('amount', models.DecimalField(
                    decimal_places=2,
                    help_text='Amount in INR (rupees, not paise). Computed server-side from Room.price_per_month.',
                    max_digits=10,
                )),
                ('currency', models.CharField(default='INR', max_length=10)),
                ('status', models.CharField(
                    choices=[
                        ('CREATED', 'Created'),
                        ('PENDING', 'Pending'),
                        ('SUCCESS', 'Success'),
                        ('FAILED', 'Failed'),
                        ('REFUNDED', 'Refunded'),
                    ],
                    db_index=True,
                    default='CREATED',
                    max_length=20,
                )),
                ('verified_at', models.DateTimeField(
                    blank=True,
                    help_text='Timestamp when signature verification succeeded.',
                    null=True,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments',
                    to='bookings.booking',
                )),
            ],
            options={
                'db_table': 'payments',
                'ordering': ['-created_at'],
            },
        ),

        # ── Create PaymentAttempt table ───────────────────────────────────────
        migrations.CreateModel(
            name='PaymentAttempt',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4,
                    editable=False,
                    primary_key=True,
                    serialize=False,
                )),
                ('method', models.CharField(
                    choices=[
                        ('UPI_GPAY', 'Google Pay'),
                        ('UPI_PHONEPE', 'PhonePe'),
                        ('UPI_PAYTM', 'Paytm'),
                        ('CARD', 'Credit / Debit Card'),
                    ],
                    max_length=20,
                )),
                ('razorpay_payment_id', models.CharField(
                    blank=True,
                    help_text='Razorpay payment ID (pay_XXXX). Set once Razorpay processes the attempt.',
                    max_length=100,
                    null=True,
                    unique=True,
                )),
                ('razorpay_signature', models.CharField(
                    blank=True,
                    help_text='HMAC-SHA256 signature from Razorpay. Set only on SUCCESS.',
                    max_length=256,
                    null=True,
                )),
                ('status', models.CharField(
                    choices=[
                        ('INITIATED', 'Initiated'),
                        ('SUCCESS', 'Success'),
                        ('FAILED', 'Failed'),
                    ],
                    db_index=True,
                    default='INITIATED',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('payment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attempts',
                    to='payments.payment',
                )),
            ],
            options={
                'db_table': 'payment_attempts',
                'ordering': ['-created_at'],
            },
        ),
    ]
