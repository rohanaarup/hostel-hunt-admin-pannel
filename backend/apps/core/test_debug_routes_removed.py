from rest_framework.test import APITestCase


class DebugRoutesRemovedTests(APITestCase):
    def test_debug_logs_is_not_served(self):
        self.assertEqual(self.client.get('/api/v1/debug-logs/').status_code, 404)

    def test_debug_version_is_not_served(self):
        self.assertEqual(self.client.get('/api/v1/debug-version/').status_code, 404)
