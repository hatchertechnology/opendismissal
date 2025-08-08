from django.test import TestCase, Client
from django.contrib.auth.models import User


class CSPHeaderTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="password123",
            is_staff=True,
        )

    def test_csp_on_dismissal_pages_is_local_only_with_nonce(self):
        # Login as staff to access dismissal pages
        self.client.login(username="staffuser", password="password123")

        resp = self.client.get("/dissmissal/")
        self.assertEqual(resp.status_code, 200)

        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertTrue(csp, "CSP header should be present")

        # No external CDNs allowed
        self.assertNotIn("cdn.jsdelivr.net", csp)

        # style-src should include self and nonce
        self.assertIn("style-src 'self'", csp)
        self.assertIn("nonce-", csp)

        # font-src should be self data:
        self.assertIn("font-src 'self' data:", csp)

        # script-src currently allows unsafe-inline plus nonce for legacy inline handlers
        self.assertIn("script-src 'self'", csp)
        self.assertIn("'unsafe-inline'", csp)
        self.assertIn("nonce-", csp)

    def test_csp_on_admin_login_allows_admin_inline(self):
        resp = self.client.get("/admin/login/")
        self.assertEqual(resp.status_code, 200)

        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertTrue(csp, "CSP header should be present on admin login")

        self.assertIn("script-src 'self' 'unsafe-inline'", csp)
        self.assertIn("style-src 'self' 'unsafe-inline'", csp)
        # No external CDNs allowed
        self.assertNotIn("cdn.jsdelivr.net", csp)