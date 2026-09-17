from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from .models import Room


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


def _make_room(hostel, name="R1"):
    return Room.objects.create(
        hostel=hostel, room_name=name, sharing_type="single",
        capacity=1, price_per_month=1000, available_beds=1,
    )


class RoomTenantIsolationTests(APITestCase):
    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")
        self.room_a = _make_room(self.hostel_a)
        self.room_b = _make_room(self.hostel_b)

    def _detail_url(self, hostel, room):
        return reverse("rooms-detail", kwargs={"hostel_id": str(hostel.id), "pk": str(room.id)})

    def test_cannot_reparent_own_room_into_another_owners_hostel(self):
        """
        A PATCH that changes `hostel` to a hostel the requester doesn't
        own must be rejected — otherwise an owner could move/plant a room
        into a competitor's hostel via the room's own update endpoint,
        even though get_queryset() correctly scoped which room they were
        allowed to fetch in the first place.
        """
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            self._detail_url(self.hostel_a, self.room_a),
            {"hostel": str(self.hostel_b.id)},
            format="json",
        )
        self.room_a.refresh_from_db()
        self.assertNotEqual(self.room_a.hostel_id, self.hostel_b.id)
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))

    def test_cannot_patch_another_owners_room_at_all(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            self._detail_url(self.hostel_b, self.room_b),
            {"room_name": "hacked"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.room_b.refresh_from_db()
        self.assertEqual(self.room_b.room_name, "R1")

    def test_can_update_own_room(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            self._detail_url(self.hostel_a, self.room_a),
            {"room_name": "Renamed"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
