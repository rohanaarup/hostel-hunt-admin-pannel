import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from apps.rooms.models import Room
from .models import MediaItem


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


def _make_room(hostel):
    return Room.objects.create(
        hostel=hostel, room_name="R1", sharing_type="single",
        capacity=1, price_per_month=1000, available_beds=1,
    )


class MediaItemTenantIsolationTests(APITestCase):
    """
    MediaItem is TenantScopedModel with a tuple OWNER_LOOKUP
    ("hostel__owner" or "room__hostel__owner"). Two owners, each with
    their own hostel/room/media — assert every access point (upload,
    detail-delete, reorder) rejects cross-tenant access.
    """

    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")
        self.room_a = _make_room(self.hostel_a)
        self.room_b = _make_room(self.hostel_b)
        self.media_a = MediaItem.objects.create(
            hostel=self.hostel_a, file_url="https://example.com/a.jpg", category="hostel",
        )
        self.media_b_room = MediaItem.objects.create(
            room=self.room_b, file_url="https://example.com/b.jpg", category="room",
        )

    def test_upload_rejects_hostel_owned_by_another_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(
            reverse("media-upload"),
            {"hostel": str(self.hostel_b.id), "file_url": "https://example.com/x.jpg", "category": "hostel"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_rejects_room_owned_by_another_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(
            reverse("media-upload"),
            {"room": str(self.room_b.id), "file_url": "https://example.com/x.jpg", "category": "room"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_allows_own_hostel(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(
            reverse("media-upload"),
            {"hostel": str(self.hostel_a.id), "file_url": "https://example.com/x.jpg", "category": "hostel"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_delete_rejects_other_tenants_media(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.delete(reverse("media-detail", args=[self.media_b_room.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MediaItem.objects.filter(id=self.media_b_room.id).exists())

    def test_delete_allows_own_media(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.delete(reverse("media-detail", args=[self.media_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MediaItem.objects.filter(id=self.media_a.id).exists())

    def test_reorder_skips_other_tenants_media(self):
        self.client.force_authenticate(user=self.owner_a)
        original_order = self.media_b_room.order_index
        resp = self.client.patch(
            reverse("media-reorder"),
            {"items": [{"id": str(self.media_b_room.id), "order_index": 99}]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated"], 0)
        self.media_b_room.refresh_from_db()
        self.assertEqual(self.media_b_room.order_index, original_order)
