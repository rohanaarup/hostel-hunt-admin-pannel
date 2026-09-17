from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.owners.models import Owner
from apps.hostels.models import Hostel
from .models import Notice


def _make_owner(email):
    return Owner.objects.create_user(email=email, display_name=email, password="pass1234")


def _make_hostel(owner, name):
    return Hostel.objects.create(
        owner=owner, name=name, owner_name=owner.display_name,
        contact_number="9999999999", email=owner.email,
        locality="Loc", address="Addr", city="City", state="State",
        pincode="500000", gender_type="co_living",
    )


class NoticeTenantIsolationTests(APITestCase):
    """
    Notice.OWNER_LOOKUP was mislabeled as "posted_by" (a proxy that only
    happened to work under the current one-login-per-hostel cardinality);
    fixed to "hostel__owner", with a documented fallback for legacy/global
    notices where hostel is NULL (scoped to their poster instead).
    """

    def setUp(self):
        self.owner_a = _make_owner("owner_a@test.com")
        self.owner_b = _make_owner("owner_b@test.com")
        self.hostel_a = _make_hostel(self.owner_a, "Hostel A")
        self.hostel_b = _make_hostel(self.owner_b, "Hostel B")

        self.notice_a = Notice.objects.create(
            hostel=self.hostel_a, title="A's notice", body="body",
            posted_by=self.owner_a,
        )
        self.notice_b = Notice.objects.create(
            hostel=self.hostel_b, title="B's notice", body="body",
            posted_by=self.owner_b,
        )
        self.global_notice = Notice.objects.create(
            hostel=None, title="Global", body="body", posted_by=self.owner_a,
        )

    def test_list_excludes_other_tenants_notice(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.get(reverse("notice-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.notice_a.id), ids)
        self.assertIn(str(self.global_notice.id), ids)
        self.assertNotIn(str(self.notice_b.id), ids)

    def test_owner_b_does_not_see_owner_a_global_notice(self):
        # Global notice belongs to whoever posted it, not every owner.
        self.client.force_authenticate(user=self.owner_b)
        resp = self.client.get(reverse("notice-list"))
        ids = {row["id"] for row in resp.data["results"]} if "results" in resp.data else {row["id"] for row in resp.data}
        self.assertIn(str(self.notice_b.id), ids)
        self.assertNotIn(str(self.notice_a.id), ids)
        self.assertNotIn(str(self.global_notice.id), ids)

    def test_update_rejects_other_tenants_notice(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("notice-update", args=[self.notice_b.id]), {"title": "hacked"}, format="json",
        )
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.notice_b.refresh_from_db()
        self.assertEqual(self.notice_b.title, "B's notice")

    def test_update_allows_own_global_notice(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.patch(
            reverse("notice-update", args=[self.global_notice.id]), {"title": "updated"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_delete_rejects_other_tenants_notice(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.delete(reverse("notice-delete", args=[self.notice_b.id]))
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertTrue(Notice.objects.filter(id=self.notice_b.id).exists())

    def test_create_rejects_hostel_owned_by_another_tenant(self):
        self.client.force_authenticate(user=self.owner_a)
        resp = self.client.post(
            reverse("notice-create"),
            {"hostel": str(self.hostel_b.id), "title": "x", "body": "y"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
