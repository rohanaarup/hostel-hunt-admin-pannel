"""
The push and email wording must be the wording of the approved boards, word for word (docs/ui/text/PushPreview.txt and
EmailPreview.txt). These tests spell the expected strings out, so a change of wording is a deliberate change of a test.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from . import templates

DUE = date(2026, 10, 18)
AMOUNT = Decimal('6000.00')
HOSTEL = 'Sample PG'


class PushWording(SimpleTestCase):
    def push(self, offset):
        return templates.push_text(offset, AMOUNT, HOSTEL, DUE)

    def test_7_days_before(self):
        self.assertEqual(self.push(7), ('Rent due in 7 days', '₹6,000 for Sample PG is due on 18 Oct. You can pay now.'))

    def test_3_days_before(self):
        self.assertEqual(self.push(3), ('Rent due in 3 days', 'Pay ₹6,000 by 18 Oct. Tap to pay in the app.'))

    def test_1_day_before(self):
        self.assertEqual(self.push(1), ('Rent due tomorrow', '₹6,000 is due tomorrow, 18 Oct.'))

    def test_due_day(self):
        self.assertEqual(self.push(0), ('Rent is due today', 'Pay ₹6,000 now to stay on track.'))

    def test_3_days_overdue(self):
        self.assertEqual(self.push(-3), ('Rent is 3 days overdue', '₹6,000 was due on 18 Oct. Please pay as soon as you can.'))

    def test_the_other_ladder_steps_use_the_same_voice(self):
        self.assertEqual(self.push(-1), ('Rent is 1 day overdue', '₹6,000 was due on 18 Oct. Please pay as soon as you can.'))
        self.assertEqual(self.push(-7)[0], 'Rent is 7 days overdue')
        self.assertEqual(self.push(5)[0], 'Rent due in 5 days')

    def test_amounts_with_paise(self):
        title, body = templates.push_text(7, Decimal('6500.50'), HOSTEL, DUE)
        self.assertIn('₹6,500.50', body)

    def test_the_wording_is_in_the_board_text_file(self):
        text = (Path(settings.BASE_DIR).parent / 'docs' / 'ui' / 'text' / 'PushPreview.txt').read_text(encoding='utf-8')
        for offset in (7, 3, 1, 0, -3):
            title, body = self.push(offset)
            self.assertIn(title, text)
            self.assertIn(body, text)


class EmailWording(SimpleTestCase):
    def email(self, offset=0, **extra):
        values = dict(amount=AMOUNT, hostel='Sample PG', locality='Dilsukhnagar', name='Student A', due_date=DUE,
                      period_start=date(2026, 10, 18), period_end=date(2026, 11, 17), room_label='Room 204',
                      bed_label='Bed B')
        values.update(extra)
        return templates.email_content(offset, **values)

    def test_due_day_email_matches_the_board(self):
        subject, text, html = self.email(0)
        self.assertEqual(subject, 'Your rent of ₹6,000 is due today')
        for line in ('Your rent is due today',
                     'Hi Student A, your rent for Sample PG · Dilsukhnagar is due today. Paying on time keeps your stay record clear.',
                     'Amount', '₹6,000', 'Due date', '18 Oct 2026', 'Rent period', '18 Oct – 17 Nov 2026',
                     'Room and bed', 'Room 204, Bed B', 'Pay rent in the app',
                     'You are receiving this because you have an active stay on Hostel Hunt. '
                     'Reminder emails are sent on the due date and when rent is overdue.'):
            self.assertIn(line, text, line)
            self.assertIn(line.replace('&', '&amp;'), html, line)

    def test_the_overdue_email(self):
        subject, text, html = self.email(-3)
        self.assertEqual(subject, 'Your rent of ₹6,000 is overdue')
        self.assertIn('Your rent is overdue', text)
        self.assertIn('was due on 18 Oct', text)
        self.assertIn('Please pay as soon as you can.', text)

    def test_only_the_due_day_and_overdue_get_an_email(self):
        self.assertEqual([o for o in (7, 3, 1, 0, -1, -3, -7) if templates.email_is_sent(o)], [0, -1, -3, -7])

    def test_the_html_escapes_names(self):
        _, _, html = self.email(0, name='<b>Eve</b> & Co')
        self.assertNotIn('<b>Eve</b>', html)
        self.assertIn('&lt;b&gt;Eve&lt;/b&gt; &amp; Co', html)

    def test_the_board_lines_are_in_the_board_text_file(self):
        text = (Path(settings.BASE_DIR).parent / 'docs' / 'ui' / 'text' / 'EmailPreview.txt').read_text(encoding='utf-8')
        subject, plain, _ = self.email(0)
        self.assertIn(subject, text)
        for line in ('Your rent is due today', 'Pay rent in the app', 'Room and bed'):
            self.assertIn(line, text)


class Kinds(SimpleTestCase):
    def test_ladder(self):
        self.assertEqual(templates.LADDER, (7, 3, 1, 0, -1, -3, -7))
        self.assertEqual([templates.kind_for(o) for o in templates.LADDER],
                         ['before_7', 'before_3', 'before_1', 'due_day', 'overdue_1', 'overdue_3', 'overdue_7'])
        self.assertIsNone(templates.kind_for(5))

    def test_severity_orders_overdue_before_upcoming(self):
        order = sorted(templates.LADDER, key=templates.priority_for, reverse=True)
        self.assertEqual(order, [-7, -3, -1, 0, 1, 3, 7])

    def test_money_format(self):
        self.assertEqual(templates.money(Decimal('6000')), '₹6,000')
        self.assertEqual(templates.money(Decimal('1234567.00')), '₹1,234,567')
