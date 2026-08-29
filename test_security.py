"""
test_security.py — Automated Security and Route Verification Test Suite for ChimneyCare.
"""

import unittest
from app import app


class ChimneyCareSecurityTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = True
        self.client = app.test_client()

    def test_security_headers_present(self):
        """Verify OWASP-compliant security headers on responses."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_unauthenticated_admin_access_blocked(self):
        """Ensure all protected admin endpoints deny unauthenticated access."""
        protected_routes = [
            "/admin",
            "/admin/bookings",
            "/admin/repairs",
            "/admin/technicians",
            "/admin/amc-plans",
            "/admin/parts",
            "/admin/products",
            "/admin/promo-codes",
            "/admin/orders",
        ]
        for route in protected_routes:
            res = self.client.get(route)
            # Must redirect to login or deny access
            self.assertIn(res.status_code, [302, 401, 403], f"Unprotected route: {route}")

    def test_csrf_protection_on_post_requests(self):
        """Ensure POST endpoints reject requests without a valid CSRF token."""
        res = self.client.post("/contact", data={"name": "Attacker", "email": "hacker@test.com", "message": "XSS attack"})
        self.assertEqual(res.status_code, 400, "CSRF protection bypassed!")

    def test_customer_role_cannot_access_admin(self):
        """Ensure logged-in customer role cannot access admin portal."""
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "id": "mock-customer-id",
                "email": "customer@example.com",
                "name": "Customer User",
                "role": "customer",
            }
        res = self.client.get("/admin/bookings")
        self.assertIn(res.status_code, [302, 403], "Customer bypassed admin authorization!")

    def test_all_public_pages_load_cleanly(self):
        """Ensure all public storefront routes return 200 OK without errors."""
        public_routes = [
            "/",
            "/about",
            "/contact",
            "/service-areas",
            "/faq",
            "/terms",
            "/privacy",
            "/marketplace",
            "/repair",
            "/services",
            "/services/amc",
            "/login",
            "/register",
            "/forgot-password",
            "/admin/login",
        ]
        for route in public_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Failed on route: {route}")


if __name__ == "__main__":
    unittest.main()
