from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from apps.bookings.models import Wishlist, Booking
from apps.payments.models import Payment


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


class WishlistUserIsolationTests(APITestCase):
    def setUp(self):
        self.student_a = _make_owner("student_a@test.com")
        self.student_b = _make_owner("student_b@test.com")
        self.owner = _make_owner("owner_c@test.com")
        self.hostel = _make_hostel(self.owner, "Hostel C")
        self.item_a = Wishlist.objects.create(user=self.student_a, hostel=self.hostel)
        self.item_b = Wishlist.objects.create(user=self.student_b, hostel=self.hostel)

    def test_list_excludes_other_users_wishlist(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("wishlist-list"))
        ids = {row["id"] for row in resp.data["wishlist"]}
        self.assertIn(str(self.item_a.id), ids)
        self.assertNotIn(str(self.item_b.id), ids)

    def test_cannot_delete_another_users_wishlist_item(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.delete(reverse("wishlist-detail", args=[self.item_b.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Wishlist.objects.filter(id=self.item_b.id).exists())

    def test_can_delete_own_wishlist_item(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.delete(reverse("wishlist-detail", args=[self.item_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Wishlist.objects.filter(id=self.item_a.id).exists())


class DashboardStatsIsolationTests(APITestCase):
    """
    DashboardStatsView/DashboardActivityView referenced Payment fields
    (hostel, amount_due, amount_paid, resident_name) that no longer exist
    on the current schema — they would 500 if ever called. Fixed against
    the current Payment/Booking schema; these tests both prove the fix
    (no crash) and that revenue/activity stay tenant-isolated.
    """

    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")

        booking_a_offline = Booking.objects.create(
            hostel=self.hostel_a, student_name="A1", payment_mode="offline",
            status="paid", amount=500,
        )
        Booking.objects.create(
            hostel=self.hostel_a, student_name="A2", payment_mode="online",
            status="pending", amount=700,
        )
        booking_a_online = Booking.objects.create(
            hostel=self.hostel_a, student_name="A3", payment_mode="online",
            status="paid", amount=900,
        )
        Payment.objects.create(
            booking=booking_a_online, razorpay_order_id="order_a1",
            amount=900, status=Payment.Status.SUCCESS,
        )

        booking_b_offline = Booking.objects.create(
            hostel=self.hostel_b, student_name="B1", payment_mode="offline",
            status="paid", amount=10000,
        )

    def test_stats_do_not_crash_and_isolate_revenue_by_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("dashboard-stats"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data["data"]
        # 500 (offline) + 900 (online SUCCESS) = 1400, never B's 10000
        self.assertEqual(data["revenue_collected"], 1400.0)
        self.assertEqual(data["revenue_pending"], 700.0)
        self.assertEqual(data["pending_bookings"], 1)

    def test_activity_does_not_crash_and_isolates_by_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("dashboard-activity"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        descriptions = " ".join(a["description"] for a in resp.data["data"])
        self.assertNotIn("B1", descriptions)


class StudentDashboardStatsIsolationTests(APITestCase):
    def setUp(self):
        self.student_a = _make_owner("student_a@test.com")
        self.student_b = _make_owner("student_b@test.com")
        self.owner = _make_owner("owner_c@test.com")
        self.hostel = _make_hostel(self.owner, "Hostel C")
        Booking.objects.create(hostel=self.hostel, student=self.student_a, student_name="A", status="confirmed", amount=500)
        Booking.objects.create(hostel=self.hostel, student=self.student_b, student_name="B", status="confirmed", amount=800)

    def test_stats_isolate_by_student(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("student-dashboard-stats"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["booking_stats"]["total"], 1)
        self.assertEqual(resp.data["active_booking"]["amount"], "500.00")
