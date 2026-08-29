"""
test_security.py — Comprehensive Automated Security and Vulnerability Verification Suite for ChimneyCare.
"""

import io
import unittest
from app import app
from utils import (
    validate_email_strict,
    validate_phone_strict,
    validate_password_strict,
    validate_name_strict,
    validate_and_save_upload,
    validate_float_range,
    validate_integer_range,
)


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

    def test_health_check_endpoint(self):
        """Verify lightweight /health endpoint returns HTTP 200 with expected JSON payload."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("message"), "Server is healthy")
        self.assertIn("timestamp", data)
        res_head = self.client.head("/health")
        self.assertEqual(res_head.status_code, 200)

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

    def test_strict_email_validation(self):
        """Verify strict email validation accepts valid and rejects malformed emails."""
        valid, _ = validate_email_strict("user@example.com")
        self.assertTrue(valid)
        valid, _ = validate_email_strict("support.care@chimneycare.in")
        self.assertTrue(valid)

        invalid_emails = ["not-an-email", "@no-user.com", "user@", "user@.com", "user@com", "a" * 255 + "@test.com"]
        for email in invalid_emails:
            valid, _ = validate_email_strict(email)
            self.assertFalse(valid, f"Malformed email was accepted: {email}")

    def test_strict_phone_validation(self):
        """Verify Indian 10-digit mobile number format validation."""
        valid, _ = validate_phone_strict("9876543210")
        self.assertTrue(valid)
        valid, _ = validate_phone_strict("+91 87340 02200")
        self.assertTrue(valid)

        invalid_phones = ["12345", "0000000000", "5555555555", "1234567890123", "abcdefghij"]
        for phone in invalid_phones:
            valid, _ = validate_phone_strict(phone)
            self.assertFalse(valid, f"Invalid phone was accepted: {phone}")

    def test_strict_password_complexity(self):
        """Verify password complexity requirements."""
        valid, _ = validate_password_strict("ValidPass@2026")
        self.assertTrue(valid)

        weak_passwords = ["short", "nouppercase123", "NOLOWERCASE123", "NoNumbers!"]
        for pw in weak_passwords:
            valid, _ = validate_password_strict(pw)
            self.assertFalse(valid, f"Weak password was accepted: {pw}")

    def test_file_upload_magic_bytes_security(self):
        """Verify file upload rejects executable and spoofed file types."""
        # 1. Reject malicious extension
        fake_php = io.BytesIO(b"<?php echo 'hacked'; ?>")
        fake_php.filename = "payload.php"
        valid, msg = validate_and_save_upload(fake_php)
        self.assertFalse(valid)
        self.assertIn("Invalid file type", msg)

        # 2. Reject spoofed image with wrong magic bytes (e.g. PHP script renamed to .jpg)
        spoofed_jpg = io.BytesIO(b"<?php system($_GET['cmd']); ?>")
        spoofed_jpg.filename = "exploit.jpg"
        valid, msg = validate_and_save_upload(spoofed_jpg)
        self.assertFalse(valid)
        self.assertIn("not a valid JPEG", msg)

        # 3. Accept genuine JPEG file with valid magic bytes (\xFF\xD8\xFF)
        valid_jpg = io.BytesIO(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xFF\xDB\x00C\x00")
        valid_jpg.filename = "chimney_photo.jpg"
        valid, saved_name = validate_and_save_upload(valid_jpg, target_folder="static/uploads/test")
        self.assertTrue(valid)
        self.assertTrue(saved_name.endswith(".jpg"))

    def test_error_pages_do_not_leak_internal_paths(self):
        """Verify 404 and 500 error pages show clean, generic messages without paths or tracebacks."""
        res = self.client.get("/non-existent-endpoint-test-404")
        self.assertEqual(res.status_code, 404)
        body = res.data.decode("utf-8")
        self.assertNotIn("Traceback (most recent call last)", body)
        self.assertNotIn("c:\\Chineycare", body.lower())
        self.assertNotIn("c:/chineycare", body.lower())

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
