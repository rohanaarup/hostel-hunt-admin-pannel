from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from .models import Resident


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


class ResidentTenantIsolationTests(APITestCase):
    """
    Resident was already correctly wired (TenantScopedQuerysetMixin +
    TenantOwnershipValidationMixin + get_tenant_scoped_object_or_404) but
    had zero regression tests despite being a real tenant-scoped model
    with real endpoints — closing that gap here.
    """

    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")
        self.resident_a = Resident.objects.create(
            hostel=self.hostel_a, name="Res A", phone="9000000001",
            id_proof_type="aadhaar", id_proof_number="1111", move_in_date="2026-01-01",
        )
        self.resident_b = Resident.objects.create(
            hostel=self.hostel_b, name="Res B", phone="9000000002",
            id_proof_type="aadhaar", id_proof_number="2222", move_in_date="2026-01-01",
        )

    def test_list_excludes_other_tenants_resident(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("resident-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.resident_a.id), ids)
        self.assertNotIn(str(self.resident_b.id), ids)

    def test_create_rejects_hostel_owned_by_another_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(
            reverse("resident-create"),
            {
                "hostel": str(self.hostel_b.id), "name": "X", "phone": "9000000003",
                "id_proof_type": "aadhaar", "id_proof_number": "3333", "move_in_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_vacated_rejects_other_tenants_resident(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(reverse("resident-mark-vacated", args=[self.resident_b.id]))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.resident_b.refresh_from_db()
        self.assertEqual(self.resident_b.status, "active")

    def test_mark_vacated_allows_own_resident(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(reverse("resident-mark-vacated", args=[self.resident_a.id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.resident_a.refresh_from_db()
        self.assertEqual(self.resident_a.status, "vacated")
