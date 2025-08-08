import os
from django.test import TestCase, Client
from django.contrib.auth.models import User


class CSPHeaderTests(TestCase):
    """Test CSP headers are correctly configured for different page types."""
    
    def setUp(self):
        """Set up test user with secure password handling."""
        self.client = Client()
        # Use environment variable or secure test password
        self.test_password = os.environ.get("TEST_STAFF_PASSWORD", "test-secure-pass-2024")
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password=self.test_password,
            is_staff=True,
        )

    def test_csp_on_dismissal_pages_is_local_only_with_nonce(self):
        """Test CSP headers on dismissal pages allow only local resources with nonce."""
        # Login as staff to access dismissal pages
        self.client.login(username="staffuser", password=self.test_password)

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