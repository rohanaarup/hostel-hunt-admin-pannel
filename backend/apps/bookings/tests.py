from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from .models import Booking


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


def _make_booking(hostel, **extra):
    return Booking.objects.create(hostel=hostel, **extra)


class BookingTenantIsolationTests(APITestCase):
    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")
        self.booking_a = _make_booking(self.hostel_a, student_name="Alice", status="pending")
        self.booking_b = _make_booking(self.hostel_b, student_name="Bob", status="pending")

    def test_list_excludes_other_tenants_bookings(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("booking-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.booking_a.id), ids)
        self.assertNotIn(str(self.booking_b.id), ids)

    def test_cannot_patch_another_owners_booking(self):
        # Generic PATCH is disabled outright (see update()/partial_update()
        # override) — 405 regardless of whose booking it targets, which is
        # a stronger guarantee than a tenant-scoped 404 would be.
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("booking-detail", args=[self.booking_b.id]), {"status": "paid"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.booking_b.refresh_from_db()
        self.assertEqual(self.booking_b.status, "pending")

    def test_direct_patch_cannot_bypass_approve_to_set_status_paid(self):
        """
        Status changes are meant to go through the explicit approve/
        reject/verify/mark_paid actions (see BookingViewSet's docstring),
        not a generic PATCH — otherwise an owner could skip payment
        verification entirely by PATCHing status='paid' directly.
        """
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("booking-detail", args=[self.booking_a.id]), {"status": "paid"}, format="json",
        )
        self.booking_a.refresh_from_db()
        self.assertNotEqual(self.booking_a.status, "paid")

    def test_direct_patch_cannot_reparent_booking_to_another_owners_hostel(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("booking-detail", args=[self.booking_a.id]),
            {"hostel": str(self.hostel_b.id)}, format="json",
        )
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.hostel_id, self.hostel_a.id)

    def test_approve_action_still_works_for_own_booking(self):
        # Confirms disabling the generic update()/partial_update() route
        # didn't also break the legitimate custom-action mutation path.
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(reverse("booking-approve", args=[self.booking_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, "confirmed")

    def test_approve_action_rejects_another_owners_booking(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(reverse("booking-approve", args=[self.booking_b.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.booking_b.refresh_from_db()
        self.assertEqual(self.booking_b.status, "pending")


class MyBookingsUserIsolationTests(APITestCase):
    """
    The student-facing counterpart to BookingViewSet (which is owner-
    scoped only) — previously missing entirely. Two students, each with
    their own booking; neither should see the other's via /bookings/my/.
    """

    def setUp(self):
        self.student_a = _make_owner("student_a@test.com")
        self.student_b = _make_owner("student_b@test.com")
        self.owner = _make_owner("owner_c@test.com")
        self.hostel = _make_hostel(self.owner, "Hostel C")
        self.booking_a = _make_booking(self.hostel, student=self.student_a, student_name="A")
        self.booking_b = _make_booking(self.hostel, student=self.student_b, student_name="B")

    def test_my_bookings_list_excludes_other_students(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("my-booking-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.booking_a.id), ids)
        self.assertNotIn(str(self.booking_b.id), ids)

    def test_my_booking_detail_rejects_other_students_booking(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("my-booking-detail", args=[self.booking_b.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_my_booking_detail_allows_own_booking(self):
        self.client.force_authenticate(user=self.student_a)
        resp = self.client.get(reverse("my-booking-detail", args=[self.booking_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_hostel_owner_cannot_see_bookings_via_my_bookings_route(self):
        # /bookings/my/ is student-scoped (USER_LOOKUP="student"); the
        # hostel owner isn't the `student` on either booking, so they get
        # nothing back here even though they own the hostel these
        # bookings are on — that's BookingViewSet's job, a separate route.
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(reverse("my-booking-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertEqual(ids, set())
