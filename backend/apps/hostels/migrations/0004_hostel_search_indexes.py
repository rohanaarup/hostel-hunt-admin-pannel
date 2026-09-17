from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds indexes for the fields HostelViewSet.get_queryset() actually
    filters on (gender_type=, city__iexact=, locality__icontains=).

    Hand-authored rather than autodetected: running `makemigrations`
    against this project's current model state triggers an unrelated,
    pre-existing autodetector prompt about a field rename on the
    `payments` app (`payment_id` -> `id`) that has nothing to do with
    this change. Rather than answer that prompt (and risk generating an
    unwanted migration for an unrelated app), this migration is written
    by hand and only touches the `hostels` app.

    NOTE: TrigramExtension requires the pg_trgm extension to be
    installable on the target Postgres instance. This has NOT been
    verified against the actual Supabase project (no confirmed
    successful `migrate` run against a live Postgres in this session —
    see the accompanying report). Most managed Postgres providers,
    including Supabase, allow pg_trgm by default, but confirm before
    applying this to production.
    """

    dependencies = [
        ('hostels', '0003_hostel_locality'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AlterField(
            model_name='hostel',
            name='city',
            field=models.CharField(max_length=100, db_index=True),
        ),
        migrations.AlterField(
            model_name='hostel',
            name='state',
            field=models.CharField(max_length=100, db_index=True),
        ),
        migrations.AlterField(
            model_name='hostel',
            name='gender_type',
            field=models.CharField(
                max_length=20,
                choices=[('boys', 'Boys'), ('girls', 'Girls'), ('co_living', 'Co-Living')],
                db_index=True,
            ),
        ),
        migrations.AddIndex(
            model_name='hostel',
            index=GinIndex(fields=['locality'], name='hostel_locality_trgm', opclasses=['gin_trgm_ops']),
        ),
    ]
