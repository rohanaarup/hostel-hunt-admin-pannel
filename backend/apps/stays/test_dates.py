"""today_ist(): calendar dates are IST (Asia/Kolkata). Render's cron runs in UTC, so midnight IST is 18:30 UTC the day before."""
from datetime import date, datetime, timedelta, timezone

from django.test import SimpleTestCase

from apps.stays import dates


class TodayIstTests(SimpleTestCase):
    def test_a_utc_evening_is_already_the_next_day_in_india(self):
        # 18:30 UTC on 29 Oct is exactly midnight on 30 Oct in IST.
        self.assertEqual(dates.today_ist(datetime(2026, 10, 29, 18, 30, tzinfo=timezone.utc)), date(2026, 10, 30))

    def test_one_minute_before_ist_midnight_is_still_the_same_day(self):
        self.assertEqual(dates.today_ist(datetime(2026, 10, 29, 18, 29, tzinfo=timezone.utc)), date(2026, 10, 29))

    def test_a_utc_morning_is_the_same_day(self):
        self.assertEqual(dates.today_ist(datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)), date(2026, 10, 29))

    def test_the_offset_is_five_and_a_half_hours_with_no_daylight_saving(self):
        for month in (1, 7):
            moment = datetime(2026, month, 15, 12, 0, tzinfo=timezone.utc)
            self.assertEqual(dates.to_ist(moment).utcoffset(), timedelta(hours=5, minutes=30))

    def test_a_time_in_another_zone_is_converted(self):
        new_york = timezone(timedelta(hours=-5))
        self.assertEqual(dates.today_ist(datetime(2026, 10, 29, 14, 0, tzinfo=new_york)), date(2026, 10, 30))  # 19:00 UTC

    def test_a_naive_time_is_refused(self):
        with self.assertRaises(ValueError):
            dates.today_ist(datetime(2026, 10, 29, 12, 0))

    def test_without_an_argument_it_returns_a_date(self):
        self.assertIsInstance(dates.today_ist(), date)
        self.assertNotIsInstance(dates.today_ist(), datetime)

    def test_the_cron_time_for_ist_midnight(self):
        """The documented rule: midnight IST is 18:30 UTC the day before."""
        self.assertEqual(dates.ist_midnight_utc(date(2026, 10, 30)), datetime(2026, 10, 29, 18, 30, tzinfo=timezone.utc))
