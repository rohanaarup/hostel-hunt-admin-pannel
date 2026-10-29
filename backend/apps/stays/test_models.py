"""
Phase 4, Part 3 and 4: the stays app's models, their constraints, the tenancy classification, the wiring and the
reversible migration. No endpoint exists, and none is tested for here except that none exists.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import get_resolver

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.core.tenancy import checks as tenancy_checks
from apps.core.tenancy.models import GlobalModel, TenantScopedModel, UserScopedModel
from apps.payments.models import Payment
from apps.payments.test_locking import make_online_booking
from apps.residents.models import Resident
from apps.rooms.models import Room
from apps.stays import billing
from apps.stays.models import Due, HostelBillingConfig, OutboxEvent, Stay

STAYS_DIR = Path(settings.BASE_DIR) / 'apps' / 'stays'
_UNSET = object()  # lets a test pass student=None on purpose


class Base(TestCase):
    def setUp(self):
        ensure_sample_catalog()
        self.room = Room.objects.order_by('room_name').first()
        self.hostel = self.room.hostel
        self.student, self.booking = make_online_booking(self.room, 1, 'stay.student@example.test')

    def make_stay(self, booking=None, student=_UNSET, **extra):
        values = dict(
            student=self.student if student is _UNSET else student, hostel=self.hostel, room=self.room, bed_number='1',
            booking=booking or self.booking, join_date=date(2026, 9, 18), rent_amount=Decimal('6500.00'),
        )
        values.update(extra)
        return Stay.objects.create(**values)

    def make_due(self, stay, **extra):
        values = dict(stay=stay, period_start=date(2026, 9, 18), period_end=date(2026, 10, 17),
                      due_date=date(2026, 9, 18), amount=Decimal('6500.00'))
        values.update(extra)
        return Due.objects.create(**values)


class HostelBillingConfigTests(Base):
    def test_a_hostel_without_a_config_uses_the_defaults_and_nothing_is_saved(self):
        config = HostelBillingConfig.effective_for(self.hostel)
        self.assertEqual(config.billing_mode, 'ANNIVERSARY')
        self.assertEqual((config.payable_window_days, config.grace_days), (7, 0))
        self.assertTrue(config._state.adding)  # not saved (a UUID key is generated on creation, so pk is never None)
        self.assertFalse(HostelBillingConfig.objects.exists())

    def test_the_effective_config_is_the_saved_one_when_there_is_one(self):
        saved = HostelBillingConfig.objects.create(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_day=5,
                                                   first_period_policy='PRORATE', grace_days=2)
        self.assertEqual(HostelBillingConfig.effective_for(self.hostel).pk, saved.pk)

    def test_defaults_when_created(self):
        config = HostelBillingConfig.objects.create(hostel=self.hostel)
        self.assertEqual(config.billing_mode, 'ANNIVERSARY')
        self.assertIsNone(config.fixed_due_day)
        self.assertFalse(config.fixed_due_last_day)
        self.assertEqual(config.payable_window_days, 7)
        self.assertEqual(config.grace_days, 0)
        self.assertEqual(config.first_period_policy, 'FULL_MONTH')

    def test_one_config_per_hostel(self):
        HostelBillingConfig.objects.create(hostel=self.hostel)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HostelBillingConfig.objects.create(hostel=self.hostel)

    def test_the_billing_modes_and_policies_are_the_engines(self):
        self.assertEqual([c[0] for c in HostelBillingConfig.BillingMode.choices], list(billing.BILLING_MODES))
        self.assertEqual([c[0] for c in HostelBillingConfig.FirstPeriodPolicy.choices], list(billing.FIRST_PERIOD_POLICIES))

    def test_the_engine_gets_the_fixed_day_or_the_last_day_marker(self):
        self.assertEqual(HostelBillingConfig(billing_mode='FIXED_DAY', fixed_due_day=5).fixed_day_spec(), 5)
        self.assertEqual(HostelBillingConfig(billing_mode='FIXED_DAY', fixed_due_last_day=True).fixed_day_spec(),
                         billing.LAST_DAY)
        self.assertIsNone(HostelBillingConfig(billing_mode='ANNIVERSARY').fixed_day_spec())

    def test_the_snapshot_holds_every_setting_a_stay_needs_later(self):
        config = HostelBillingConfig(billing_mode='FIXED_DAY', fixed_due_day=5, first_period_policy='PRORATE',
                                     payable_window_days=10, grace_days=3)
        self.assertEqual(config.snapshot(), {
            'billing_mode': 'FIXED_DAY', 'fixed_due_day': 5, 'fixed_due_last_day': False,
            'first_period_policy': 'PRORATE', 'payable_window_days': 10, 'grace_days': 3,
        })

    def test_the_snapshot_is_plain_json_data(self):
        import json
        json.dumps(HostelBillingConfig.effective_for(self.hostel).snapshot())

    def test_validation_accepts_the_two_shapes_of_fixed_day(self):
        HostelBillingConfig(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_day=28).full_clean()
        HostelBillingConfig(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_last_day=True).full_clean()

    def test_validation_refuses_a_fixed_day_outside_1_to_28(self):
        for day in (0, 29, 31):
            with self.assertRaises(ValidationError, msg=day):
                HostelBillingConfig(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_day=day).full_clean()

    def test_validation_refuses_fixed_day_mode_without_a_day(self):
        with self.assertRaises(ValidationError):
            HostelBillingConfig(hostel=self.hostel, billing_mode='FIXED_DAY').full_clean()

    def test_validation_refuses_a_day_and_the_last_day_flag_together(self):
        with self.assertRaises(ValidationError):
            HostelBillingConfig(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_day=5,
                                fixed_due_last_day=True).full_clean()

    def test_validation_refuses_a_day_in_anniversary_mode(self):
        with self.assertRaises(ValidationError):
            HostelBillingConfig(hostel=self.hostel, billing_mode='ANNIVERSARY', fixed_due_day=5).full_clean()

    def test_the_database_refuses_what_validation_refuses(self):
        bad = [
            dict(billing_mode='FIXED_DAY', fixed_due_day=29),
            dict(billing_mode='FIXED_DAY', fixed_due_day=0),
            dict(billing_mode='FIXED_DAY'),
            dict(billing_mode='FIXED_DAY', fixed_due_day=5, fixed_due_last_day=True),
            dict(billing_mode='ANNIVERSARY', fixed_due_day=5),
        ]
        for values in bad:
            with self.assertRaises(IntegrityError, msg=values), transaction.atomic():
                HostelBillingConfig.objects.bulk_create([HostelBillingConfig(hostel=self.hostel, **values)])

    def test_window_and_grace_have_sensible_limits(self):
        for field, value in (('payable_window_days', -1), ('payable_window_days', 61), ('grace_days', -1), ('grace_days', 31)):
            with self.assertRaises(ValidationError, msg=(field, value)):
                HostelBillingConfig(hostel=self.hostel, **{field: value}).full_clean()


class StayTests(Base):
    def test_defaults(self):
        stay = self.make_stay()
        self.assertEqual(stay.status, 'UPCOMING')
        self.assertFalse(stay.needs_review)
        self.assertIsNone(stay.vacate_requested_at)
        self.assertIsNone(stay.ended_at)
        self.assertIsNone(stay.resident)
        self.assertEqual(stay.billing_snapshot, {})

    def test_the_statuses(self):
        self.assertEqual([c[0] for c in Stay.Status.choices], ['UPCOMING', 'ACTIVE', 'NOTICE', 'ENDED', 'CANCELLED'])

    def test_the_current_statuses_are_upcoming_active_and_notice(self):
        self.assertEqual(Stay.CURRENT_STATUSES, ('UPCOMING', 'ACTIVE', 'NOTICE'))
        self.assertTrue(self.make_stay(status='NOTICE').is_current)
        self.assertFalse(self.make_stay(booking=self.new_booking('b@example.test'), student=self.student, status='ENDED').is_current)

    def new_booking(self, email):
        _, booking = make_online_booking(self.room, 2, email)
        return booking

    def test_one_stay_per_booking(self):
        self.make_stay()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_stay()

    def test_a_student_can_have_several_stays_over_time_and_the_database_does_not_limit_them(self):
        """E4: a second paid booking must never be blocked (the money is already taken); the one-current-stay rule
        (D2) lives in the booking serializer in a later phase, so there is deliberately no unique constraint here."""
        self.make_stay()
        second = self.make_stay(booking=self.new_booking('second@example.test'))
        self.assertEqual(Stay.objects.filter(student=self.student, status='UPCOMING').count(), 2)
        second.needs_review = True
        second.save()

    def test_a_stay_keeps_the_rent_and_the_billing_settings_it_was_created_with(self):
        config = HostelBillingConfig.objects.create(hostel=self.hostel, billing_mode='FIXED_DAY', fixed_due_day=5,
                                                    first_period_policy='PRORATE')
        stay = self.make_stay(billing_snapshot=config.snapshot())
        config.fixed_due_day = 10
        config.save()
        self.room.price_per_month = Decimal('9999.00')
        self.room.save()
        stay.refresh_from_db()
        self.assertEqual(stay.billing_snapshot['fixed_due_day'], 5)
        self.assertEqual(stay.rent_amount, Decimal('6500.00'))

    def test_the_optional_resident_link(self):
        resident = Resident.objects.create(hostel=self.hostel, room=self.room, name='Resident', phone='9000000001',
                                           id_proof_type='aadhaar', id_proof_number='X', move_in_date=date(2026, 9, 18))
        stay = self.make_stay(resident=resident)
        self.assertEqual(list(resident.stays.all()), [stay])
        resident.delete()
        stay.refresh_from_db()
        self.assertIsNone(stay.resident)  # a stay outlives the resident row

    def test_a_stay_may_have_no_student_account(self):
        """A booking marked paid offline can have no account (the student field of a booking is optional)."""
        guest = Booking.objects.create(hostel=self.hostel, room=self.room, bed_number='3', payment_mode='offline',
                                       status='paid', student_name='Guest')
        stay = self.make_stay(booking=guest, student=None)
        self.assertIsNone(Stay.objects.get(pk=stay.pk).student)

    def test_deleting_the_student_account_keeps_the_stay(self):
        stay = self.make_stay()
        self.student.delete()
        self.assertTrue(Stay.objects.filter(pk=stay.pk).exists())

    def test_the_student_and_status_index_exists(self):
        indexed = [tuple(index.fields) for index in Stay._meta.indexes]
        self.assertIn(('student', 'status'), indexed)

    def test_the_rent_is_a_decimal_with_two_places(self):
        stay = self.make_stay(rent_amount=Decimal('6500'))
        stay.refresh_from_db()
        self.assertEqual(stay.rent_amount, Decimal('6500.00'))


class DueTests(Base):
    def setUp(self):
        super().setUp()
        self.stay = self.make_stay()

    def test_defaults(self):
        due = self.make_due(self.stay)
        self.assertEqual(due.status, 'SCHEDULED')
        self.assertEqual(due.kind, 'RENT')
        self.assertIsNone(due.paid_at)
        self.assertIsNone(due.payment)

    def test_the_statuses_have_no_stored_overdue(self):
        self.assertEqual([c[0] for c in Due.Status.choices], ['SCHEDULED', 'PAYABLE', 'PAID', 'WAIVED', 'CANCELLED'])
        self.assertNotIn('OVERDUE', [c[0] for c in Due.Status.choices])
        self.assertEqual([c[0] for c in Due.Status.choices], [s for s in billing.STORED_STATUSES])

    def test_the_kinds(self):
        self.assertEqual([c[0] for c in Due.Kind.choices], ['BOOKING_PERIOD', 'RENT'])

    def test_one_due_per_stay_and_period_start(self):
        self.make_due(self.stay)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_due(self.stay, period_end=date(2026, 10, 20))

    def test_the_same_period_start_is_fine_on_another_stay(self):
        other = self.make_stay(booking=self.new_booking('other@example.test'))
        self.make_due(self.stay)
        self.make_due(other)

    def new_booking(self, email):
        _, booking = make_online_booking(self.room, 2, email)
        return booking

    def test_a_different_period_start_on_the_same_stay_is_fine(self):
        self.make_due(self.stay)
        self.make_due(self.stay, period_start=date(2026, 10, 18), period_end=date(2026, 11, 17), due_date=date(2026, 10, 18))

    def test_the_unique_constraint_is_declared_on_stay_and_period_start(self):
        fields = [tuple(c.fields) for c in Due._meta.constraints if c.__class__.__name__ == 'UniqueConstraint']
        self.assertIn(('stay', 'period_start'), fields)

    def test_the_indexes_exist(self):
        indexed = [tuple(index.fields) for index in Due._meta.indexes]
        self.assertIn(('status', 'due_date'), indexed)
        self.assertIn(('stay', 'due_date'), indexed)

    def test_the_payment_link_is_optional_and_set_null_when_the_payment_goes(self):
        from apps.payments.models import Payment
        payment = Payment.objects.create(booking=self.booking, razorpay_order_id='order_test_1', amount=Decimal('6500.00'))
        due = self.make_due(self.stay, payment=payment, status='PAID', paid_at=datetime(2026, 9, 18, tzinfo=timezone.utc))
        self.assertEqual(list(payment.dues.all()), [due])
        payment.delete()
        due.refresh_from_db()
        self.assertIsNone(due.payment)
        self.assertEqual(due.status, 'PAID')  # the record of what was paid survives

    def test_the_payment_field_is_a_string_reference_to_the_payments_app(self):
        self.assertIs(Due._meta.get_field('payment').related_model, Payment)
        migration = (STAYS_DIR / 'migrations' / '0001_initial.py').read_text(encoding='utf-8')
        self.assertIn("'payments.payment'", migration.lower().replace('"', "'"))

    def test_a_period_cannot_end_before_it_starts(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_due(self.stay, period_start=date(2026, 11, 1), period_end=date(2026, 10, 31), due_date=date(2026, 11, 1))

    def test_an_amount_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_due(self.stay, period_start=date(2026, 12, 1), period_end=date(2026, 12, 31), amount=Decimal('-1.00'))

    def test_deleting_a_stay_deletes_its_dues(self):
        due = self.make_due(self.stay)
        self.stay.delete()
        self.assertFalse(Due.objects.filter(pk=due.pk).exists())

    def test_the_billing_engine_periods_fit_the_model_exactly(self):
        """Phase 5 will build Due 1 and Due 2 from billing.build_periods: prove the shapes line up."""
        first, second = billing.build_periods(date(2026, 9, 18), 'ANNIVERSARY', None, Decimal('6500.00'), None, 2)
        for kind, period in ((Due.Kind.BOOKING_PERIOD, first), (Due.Kind.RENT, second)):
            self.make_due(self.stay, kind=kind, period_start=period.start, period_end=period.end, due_date=period.due_date,
                          amount=period.amount)
        self.assertEqual(Due.objects.filter(stay=self.stay).count(), 2)


class OutboxEventTests(TestCase):
    def test_defaults(self):
        event = OutboxEvent.objects.create(topic='rent.reminder', dedupe_key='due:1:7d:inbox')
        self.assertEqual(event.status, 'PENDING')
        self.assertEqual(event.attempts, 0)
        self.assertEqual(event.payload, {})
        self.assertIsNone(event.processed_at)
        self.assertLessEqual(event.next_attempt_at, datetime.now(timezone.utc) + timedelta(seconds=5))

    def test_the_statuses(self):
        self.assertEqual([c[0] for c in OutboxEvent.Status.choices], ['PENDING', 'DONE', 'FAILED'])

    def test_the_dedupe_key_is_unique(self):
        OutboxEvent.objects.create(topic='a', dedupe_key='same')
        with self.assertRaises(IntegrityError), transaction.atomic():
            OutboxEvent.objects.create(topic='b', dedupe_key='same')

    def test_the_payload_round_trips_json(self):
        event = OutboxEvent.objects.create(topic='a', dedupe_key='k', payload={'due_id': 'x', 'n': [1, 2], 'ok': True})
        event.refresh_from_db()
        self.assertEqual(event.payload, {'due_id': 'x', 'n': [1, 2], 'ok': True})

    def test_the_consumer_query_has_an_index(self):
        indexed = [tuple(index.fields) for index in OutboxEvent._meta.indexes]
        self.assertIn(('status', 'next_attempt_at'), indexed)


class TenancyClassificationTests(Base):
    def test_every_stays_model_is_classified_and_the_startup_check_passes(self):
        self.assertEqual(tenancy_checks.check_business_models_are_classified(None), [])
        self.assertEqual(tenancy_checks.check_scoped_models_declare_lookup(None), [])

    def test_stays_is_in_the_explicit_app_list(self):
        self.assertIn('stays', tenancy_checks.BUSINESS_APP_LABELS)

    def test_the_scope_of_each_model(self):
        self.assertTrue(issubclass(HostelBillingConfig, TenantScopedModel))
        self.assertFalse(issubclass(HostelBillingConfig, UserScopedModel))
        for model in (Stay, Due):
            self.assertTrue(issubclass(model, TenantScopedModel), model)
            self.assertTrue(issubclass(model, UserScopedModel), model)
        self.assertTrue(issubclass(OutboxEvent, GlobalModel))

    def test_the_lookups_walk_real_paths_back_to_the_owner_and_the_student(self):
        self.assertEqual(HostelBillingConfig.OWNER_LOOKUP, 'hostel__owner')
        self.assertEqual((Stay.OWNER_LOOKUP, Stay.USER_LOOKUP), ('hostel__owner', 'student'))
        self.assertEqual((Due.OWNER_LOOKUP, Due.USER_LOOKUP), ('stay__hostel__owner', 'stay__student'))
        stay = self.make_stay()
        self.make_due(stay)
        owner = self.hostel.owner
        self.assertEqual(list(Stay.objects.filter(**{Stay.OWNER_LOOKUP: owner})), [stay])
        self.assertEqual(list(Stay.objects.filter(**{Stay.USER_LOOKUP: self.student})), [stay])
        self.assertEqual(Due.objects.filter(**{Due.OWNER_LOOKUP: owner}).count(), 1)
        self.assertEqual(Due.objects.filter(**{Due.USER_LOOKUP: self.student}).count(), 1)
        self.assertEqual(Due.objects.filter(**{Due.USER_LOOKUP: owner}).count(), 0)  # another person sees nothing

    def test_the_outbox_holds_no_personal_data_by_contract(self):
        self.assertIn('personal data', (OutboxEvent.__doc__ or '').lower())


class WiringTests(SimpleTestCase):
    def test_the_app_is_installed(self):
        self.assertIn('apps.stays', settings.INSTALLED_APPS)
        self.assertEqual(django_apps.get_app_config('stays').name, 'apps.stays')

    def test_the_models_are_registered_in_the_admin(self):
        for model in (HostelBillingConfig, Stay, Due, OutboxEvent):
            self.assertIn(model, admin.site._registry, model)

    def test_the_admin_does_not_let_money_and_status_be_typed_over(self):
        due_admin = admin.site._registry[Due]
        for field in ('amount', 'status', 'paid_at', 'payment', 'kind'):
            self.assertIn(field, due_admin.readonly_fields)
        self.assertIn('rent_amount', admin.site._registry[Stay].readonly_fields)
        self.assertIn('billing_snapshot', admin.site._registry[Stay].readonly_fields)

    def test_the_outbox_cannot_be_added_to_by_hand_in_the_admin(self):
        self.assertFalse(admin.site._registry[OutboxEvent].has_add_permission(None))

    def test_there_is_no_endpoint_no_view_no_serializer(self):
        for name in ('views.py', 'urls.py', 'serializers.py', 'viewsets.py'):
            self.assertFalse((STAYS_DIR / name).exists(), name)
        patterns = [str(p.pattern) for p in get_resolver().url_patterns]
        self.assertFalse(any('stays' in p for p in patterns), patterns)

    def test_no_environment_variable_was_added(self):
        source = ''.join(path.read_text(encoding='utf-8') for path in STAYS_DIR.glob('*.py') if not path.name.startswith('test'))
        self.assertNotIn('config(', source)
        self.assertNotIn('os.environ', source)


class MigrationTests(TransactionTestCase):
    """0001 is additive (new tables only) and reverses cleanly."""

    def tables(self):
        return {name for name in connection.introspection.table_names() if name.startswith(('stays_', 'stay', 'dues', 'outbox', 'hostel_billing'))}

    def test_it_creates_only_new_tables_and_reverses_cleanly(self):
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(connection)
        migration = loader.get_migration('stays', '0001_initial')
        self.assertTrue(migration.initial)
        operations = {type(op).__name__ for op in migration.operations}
        # Only creation: nothing is altered, renamed or removed in an existing table.
        self.assertLessEqual(operations, {'CreateModel', 'AddIndex', 'AddConstraint'})
        self.assertIn('CreateModel', operations)
        created = {op.name.lower() for op in migration.operations if type(op).__name__ == 'CreateModel'}
        self.assertEqual(created, {'outboxevent', 'stay', 'due', 'hostelbillingconfig'})
        for op in migration.operations:
            if type(op).__name__ in ('AddIndex', 'AddConstraint'):
                self.assertIn(op.model_name.lower(), created, 'an index or constraint on a table this migration did not create')
        before = self.tables()
        self.assertTrue({'stays', 'dues', 'outbox_events', 'hostel_billing_configs'} & before, before)
        try:
            call_command('migrate', 'stays', 'zero', verbosity=0)
            self.assertFalse(self.tables() & {'stays', 'dues', 'outbox_events', 'hostel_billing_configs'})
            for existing in ('bookings', 'payments', 'hostels', 'rooms', 'residents'):
                self.assertIn(existing, connection.introspection.table_names())  # nobody else was touched
        finally:
            call_command('migrate', verbosity=0)
        self.assertEqual(self.tables(), before)

    def test_makemigrations_finds_nothing_left_to_do(self):
        from io import StringIO
        out = StringIO()
        call_command('makemigrations', '--check', '--dry-run', stdout=out)
