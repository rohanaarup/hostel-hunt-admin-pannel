from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from .models import Hostel


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


class HostelTenantIsolationTests(APITestCase):
    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")

    def test_authenticated_list_excludes_other_owners_hostel(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("hostels-list"))
        ids = {row["hostel_id"] for row in resp.data["results"]} if "results" in resp.data else {row["hostel_id"] for row in resp.data}
        self.assertIn(str(self.hostel_a.id), ids)
        self.assertNotIn(str(self.hostel_b.id), ids)

    def test_cannot_patch_another_owners_hostel(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("hostels-detail", args=[self.hostel_b.id]), {"name": "hacked"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.hostel_b.refresh_from_db()
        self.assertEqual(self.hostel_b.name, "Hostel B")

    def test_can_patch_own_hostel(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("hostels-detail", args=[self.hostel_a.id]), {"name": "Renamed"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_owner_field_is_not_client_writable(self):
        # 'owner' is read_only on HostelSerializer — confirm a PATCH can't
        # transfer a hostel to a different owner.
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("hostels-detail", args=[self.hostel_a.id]),
            {"owner": str(self.owner_b.id)}, format="json",
        )
        self.hostel_a.refresh_from_db()
        self.assertEqual(self.hostel_a.owner_id, self.owner_a.id)

    def test_public_list_is_unauthenticated_and_unscoped_by_owner(self):
        # Public browsing intentionally shows all active hostels from
        # every owner — not a leak, this is the documented public surface.
        resp = self.client.get(reverse("hostels-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
