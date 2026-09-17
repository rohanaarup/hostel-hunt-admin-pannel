import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from apps.bookings.models import Booking
from .models import Payment


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


def _make_booking(hostel, student):
    return Booking.objects.create(hostel=hostel, student=student, student_name=student.display_name)


def _make_payment(booking, **extra):
    return Payment.objects.create(
        booking=booking, razorpay_order_id=f"order_{uuid.uuid4().hex[:12]}",
        amount=1000, **extra,
    )


class PaymentIsolationTests(APITestCase):
    """
    Payment is dual-scope: OWNER_LOOKUP="booking__hostel__owner" for the
    hostel owner, USER_LOOKUP="booking__student" for the paying student.
    """

    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.student_a = _make_owner("student_a@test.com")
        self.student_b = _make_owner("student_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")
        self.booking_a = _make_booking(self.hostel_a, self.student_a)
        self.booking_b = _make_booking(self.hostel_b, self.student_b)
        self.payment_a = _make_payment(self.booking_a)
        self.payment_b = _make_payment(self.booking_b)

    # --- owner side ---------------------------------------------------

    def test_admin_list_excludes_other_tenants_payments(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("payment-admin-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.payment_a.id), ids)
        self.assertNotIn(str(self.payment_b.id), ids)

    def test_refund_rejects_other_tenants_payment(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(reverse("payment-refund", args=[self.payment_b.id]), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --- student side --------------------------------------------------

    def test_payment_list_excludes_other_students_payments(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("payment-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.payment_a.id), ids)
        self.assertNotIn(str(self.payment_b.id), ids)

    def test_status_poll_rejects_other_students_payment(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("payment-status-poll", args=[self.payment_b.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_poll_allows_own_payment(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("payment-status-poll", args=[self.payment_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_hostel_owner_cannot_use_student_status_poll_for_their_own_hostels_payment(self):
        # Owner A owns hostel_a but is not the *student* on payment_a —
        # USER_LOOKUP scoping is by booking.student, not hostel ownership.
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("payment-status-poll", args=[self.payment_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
