from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class RegisterEmailFailureTests(APITestCase):
    """Sign-up must not crash when the verification email cannot be sent."""

    def payload(self):
        return {
            "email": "mailfail@example.com",
            "username": "mailfail",
            "first_name": "Mail",
            "last_name": "Fail",
            "password": "StrongPass123!",
            "password_confirmation": "StrongPass123!",
        }

    def test_account_is_created_even_if_email_fails(self):
        with patch("accounts.views.send_verification_email", side_effect=Exception("SMTP down")):
            response = self.client.post("/api/v1/auth/register/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["email_sent"])
        self.assertTrue(User.objects.filter(email="mailfail@example.com").exists())

    def test_email_sent_flag_is_true_normally(self):
        response = self.client.post("/api/v1/auth/register/", self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["email_sent"])