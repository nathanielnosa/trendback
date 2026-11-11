from unittest.mock import patch

from rest_framework.test import APITestCase

from .models import User

URL = "/api/v1/auth/google/"
VERIFY = "accounts.views.verify_google_credential"


def google_info(email="reader@example.com", given="Ada", family="Obi"):
    """What Google's token check would return for a signed-in person."""
    return {"email": email, "email_verified": True, "given_name": given, "family_name": family}


class GoogleLoginTests(APITestCase):
    """Google sign-in: the token check is replaced by a fake, everything else is real."""

    def test_new_person_gets_an_account_and_tokens(self):
        with patch(VERIFY, return_value=google_info()):
            response = self.client.post(URL, {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data["tokens"])
        user = User.objects.get(email="reader@example.com")
        self.assertTrue(user.is_verified)
        self.assertEqual(user.role, User.Role.SUBSCRIBER)
        self.assertEqual(user.first_name, "Ada")
        self.assertFalse(user.has_usable_password())

    def test_existing_account_is_reused_and_verified(self):
        existing = User.objects.create_user(
            email="reader@example.com", username="reader", first_name="Rea", last_name="Der", password="StrongPass123!"
        )
        self.assertFalse(existing.is_verified)
        with patch(VERIFY, return_value=google_info()):
            response = self.client.post(URL, {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email="reader@example.com").count(), 1)
        existing.refresh_from_db()
        self.assertTrue(existing.is_verified)
        self.assertEqual(response.data["user"]["id"], existing.id)

    def test_username_clash_gets_a_different_username(self):
        User.objects.create_user(
            email="other@example.com", username="reader", first_name="O", last_name="T", password="StrongPass123!"
        )
        with patch(VERIFY, return_value=google_info()):
            response = self.client.post(URL, {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["user"]["username"], "reader")

    def test_bad_token_is_refused(self):
        with patch(VERIFY, side_effect=ValueError("bad")):
            response = self.client.post(URL, {"credential": "nope"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(User.objects.count(), 0)

    def test_missing_token_is_a_bad_request(self):
        self.assertEqual(self.client.post(URL, {}, format="json").status_code, 400)

    def test_deactivated_account_cannot_sign_in(self):
        user = User.objects.create_user(
            email="reader@example.com", username="reader", first_name="Rea", last_name="Der", password="StrongPass123!"
        )
        user.is_active = False
        user.save()
        with patch(VERIFY, return_value=google_info()):
            response = self.client.post(URL, {"credential": "fake-token"}, format="json")
        self.assertEqual(response.status_code, 403)