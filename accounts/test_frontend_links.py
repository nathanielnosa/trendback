from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import User
from .services import frontend_link


class FrontendLinkTests(APITestCase):
    """Email links are built from the FRONTEND_URL setting, never hard-coded."""

    @override_settings(FRONTEND_URL="https://trendarchive.example/")
    def test_link_uses_the_setting_and_ignores_a_trailing_slash(self):
        self.assertEqual(
            frontend_link("/verify-email", "abc"),
            "https://trendarchive.example/verify-email?token=abc",
        )

    @override_settings(
        FRONTEND_URL="https://trendarchive.example",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_password_reset_email_points_at_the_configured_site(self):
        User.objects.create_user(
            email="reader@example.com",
            username="reader",
            first_name="Rea",
            last_name="Der",
            password="StrongPass123!",
            is_verified=True,
        )
        response = self.client.post(
            "/api/v1/auth/forgot-password/", {"email": "reader@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://trendarchive.example/reset-password?token=", mail.outbox[0].body)
        self.assertNotIn("localhost", mail.outbox[0].body)