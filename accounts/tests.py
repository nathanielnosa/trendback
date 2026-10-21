from .models import AuthToken
from .services import create_auth_token

from django.test import override_settings
from django.core import mail
from datetime import timedelta
from django.utils import timezone

from rest_framework import status   
from rest_framework.test import APITestCase
from .models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class AuthenticationTests(APITestCase):
    """Tests for registration, login, and the current-user endpoint."""

    def setUp(self):
        self.register_url = "/api/v1/auth/register/"
        self.login_url = "/api/v1/auth/login/"
        self.me_url = "/api/v1/auth/me/"

        self.password = "StrongPass123!"

        self.user = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password=self.password,
            is_verified=True,
        )

    # test registration
    def registration_data(self, **overrides):
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "password": self.password,
            "password_confirmation": self.password,
        }
        data.update(overrides)
        return data
    
    def test_registration_creates_unverified_subscriber(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        user = User.objects.get(email="newuser@example.com")

        self.assertFalse(user.is_verified)
        self.assertEqual(user.role, User.Role.SUBSCRIBER)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(len(mail.outbox), 1)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(
                password_confirmation="DifferentPass123!"
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(
            User.objects.filter(email="newuser@example.com").exists()
        )

    def test_registration_rejects_duplicate_email(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(email=self.user.email),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(username=self.user.username),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_login_succeeds_for_verified_user(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["message"], "Login successful.")
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], self.user.email)

    def test_login_rejects_incorrect_password(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_login_rejects_unverified_user(self):
        unverified_user = User.objects.create_user(
            email="unverified@example.com",
            username="unverifieduser",
            first_name="Unverified",
            last_name="User",
            password=self.password,
            is_verified=False,
        )

        response = self.client.post(
            self.login_url,
            {
                "email": unverified_user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            response.data["message"],
            "Please verify your email before logging in.",
        )

    def test_me_requires_authentication(self):
        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_me_returns_authenticated_user(self):
        response = self.client.post(
            self.login_url,
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        access_token = response.data["tokens"]["access"]
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get(self.me_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["role"], self.user.role)
        self.assertTrue(response.data["is_verified"])

    
    def test_email_verification_succeeds_with_valid_token(self):
        raw_token, token_record = create_auth_token(
            user=self.user,
            purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
            expiration_minutes=60,
        )

        # Make this user unverified before testing verification.
        self.user.is_verified = False
        self.user.save(update_fields=["is_verified"])

        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        token_record.refresh_from_db()

        self.assertTrue(self.user.is_verified)
        self.assertIsNotNone(token_record.used_at)

    
    def test_email_verification_rejects_missing_token(self):
        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["message"],
            "Verification token is required.",
        )

    
    def test_email_verification_rejects_invalid_token(self):
        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"token": "this-token-does-not-exist"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["message"],
            "Invalid verification token.",
        )

        
    def test_email_verification_rejects_used_token(self):
        raw_token, token_record = create_auth_token(
            user=self.user,
            purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
            expiration_minutes=60,
        )

        token_record.used_at = timezone.now()
        token_record.save(update_fields=["used_at"])

        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["message"],
            "This verification token has already been used.",
        )
    
    def test_email_verification_rejects_expired_token(self):
        raw_token, token_record = create_auth_token(
            user=self.user,
            purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
            expiration_minutes=60,
        )

        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save(update_fields=["expires_at"])

        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["message"],
            "This verification token has expired.",
        )

    def test_registration_ignores_role_and_privilege_fields(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(
                role="ADMIN",
                is_staff=True,
                is_superuser=True,
                is_verified=True,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.role, User.Role.SUBSCRIBER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_verified)

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(
                password="123",
                password_confirmation="123",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            User.objects.filter(email="newuser@example.com").exists()
        )

    def test_login_rejects_nonexistent_email(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "ghost@example.com",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_email_verification_rejects_password_reset_token(self):
        raw_token, _ = create_auth_token(
            user=self.user,
            purpose=AuthToken.Purpose.PASSWORD_RESET,
            expiration_minutes=60,
        )

        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"token": raw_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_duplicate_email_different_case(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(email=self.user.email.upper()),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_registration_rejects_common_password(self):
        response = self.client.post(
            self.register_url,
            self.registration_data(
                password="12345678",
                password_confirmation="12345678",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class PasswordResetTests(APITestCase):
    """Tests for forgot-password and reset-password."""

    def setUp(self):
        self.forgot_url = "/api/v1/auth/forgot-password/"
        self.reset_url = "/api/v1/auth/reset-password/"
        self.login_url = "/api/v1/auth/login/"

        self.password = "StrongPass123!"
        self.new_password = "EvenStronger456!"

        self.user = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password=self.password,
            is_verified=True,
        )

    def test_forgot_password_sends_email_and_creates_token(self):
        response = self.client.post(
            self.forgot_url,
            {"email": self.user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            AuthToken.objects.filter(
                user=self.user,
                purpose=AuthToken.Purpose.PASSWORD_RESET,
            ).exists()
        )

    def test_forgot_password_gives_same_response_for_unknown_email(self):
        known = self.client.post(
            self.forgot_url,
            {"email": self.user.email},
            format="json",
        )
        unknown = self.client.post(
            self.forgot_url,
            {"email": "ghost@example.com"},
            format="json",
        )

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)  # only the real user got an email

    def test_forgot_password_requires_email(self):
        response = self.client.post(self.forgot_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def make_reset_token(self, **overrides):
        raw_token, record = create_auth_token(
            user=self.user,
            purpose=AuthToken.Purpose.PASSWORD_RESET,
            expiration_minutes=30,
        )
        if overrides:
            for field, value in overrides.items():
                setattr(record, field, value)
            record.save()
        return raw_token, record

    def reset_data(self, raw_token, password=None):
        password = password or self.new_password
        return {
            "token": raw_token,
            "new_password": password,
            "new_password_confirmation": password,
        }

    def test_reset_password_succeeds(self):
        raw_token, record = self.make_reset_token()

        response = self.client.post(
            self.reset_url,
            self.reset_data(raw_token),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        record.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertIsNotNone(record.used_at)

    def test_reset_password_token_cannot_be_reused(self):
        raw_token, _ = self.make_reset_token()

        self.client.post(
            self.reset_url, self.reset_data(raw_token), format="json"
        )
        response = self.client.post(
            self.reset_url,
            self.reset_data(raw_token, password="AnotherPass789!"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    def test_reset_password_rejects_expired_token(self):
        raw_token, _ = self.make_reset_token(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        response = self.client.post(
            self.reset_url, self.reset_data(raw_token), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_rejects_weak_password(self):
        raw_token, _ = self.make_reset_token()

        response = self.client.post(
            self.reset_url,
            self.reset_data(raw_token, password="123"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_mixed_case_email_can_request_password_reset(self):
        User.objects.create_user(
            email="MixedCase@Example.com",
            username="mixedcase",
            first_name="Mixed",
            last_name="Case",
            password=self.password,
            is_verified=True,
        )

        self.client.post(
            self.forgot_url,
            {"email": "MixedCase@Example.com"},
            format="json",
        )

        self.assertEqual(len(mail.outbox), 1)

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class SessionTests(APITestCase):
    """Tests for change-password, refresh-token, and logout."""

    def setUp(self):
        self.login_url = "/api/v1/auth/login/"
        self.change_password_url = "/api/v1/auth/change-password/"
        self.refresh_url = "/api/v1/auth/refresh/"
        self.logout_url = "/api/v1/auth/logout/"

        self.password = "StrongPass123!"
        self.new_password = "EvenStronger456!"

        self.user = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password=self.password,
            is_verified=True,
        )

    def login(self, password=None):
        return self.client.post(
            self.login_url,
            {"email": self.user.email, "password": password or self.password},
            format="json",
        )

    def authenticate(self):
        tokens = self.login().data["tokens"]
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}"
        )
        return tokens

    def password_data(self, current=None, new=None):
        new = new or self.new_password
        return {
            "current_password": current or self.password,
            "new_password": new,
            "new_password_confirmation": new,
        }

    # ---------- change password ----------
    def test_change_password_requires_authentication(self):
        response = self.client.post(
            self.change_password_url, self.password_data(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_rejects_wrong_current_password(self):
        self.authenticate()
        response = self.client.post(
            self.change_password_url,
            self.password_data(current="WrongPass999!"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_rejects_same_password(self):
        self.authenticate()
        response = self.client.post(
            self.change_password_url,
            self.password_data(new=self.password),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_succeeds(self):
        self.authenticate()
        response = self.client.post(
            self.change_password_url, self.password_data(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    # ---------- refresh token ----------
    def test_refresh_requires_token(self):
        response = self.client.post(self.refresh_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_rejects_invalid_token(self):
        response = self.client.post(
            self.refresh_url, {"refresh": "garbage"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_tokens(self):
        tokens = self.login().data["tokens"]
        response = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])

    # ---------- logout ----------
    def test_logout_requires_authentication(self):
        response = self.client.post(
            self.logout_url, {"refresh": "x"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_refresh_token(self):
        self.authenticate()
        response = self.client.post(self.logout_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_blacklists_refresh_token(self):
        tokens = self.authenticate()
        response = self.client.post(
            self.logout_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # the same refresh token must no longer work
        self.client.credentials()
        response = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class ResendVerificationTests(APITestCase):
    """Tests for resend-verification."""

    def setUp(self):
        self.resend_url = "/api/v1/auth/resend-verification/"

        self.unverified_user = User.objects.create_user(
            email="unverified@example.com",
            username="unverifieduser",
            first_name="Unverified",
            last_name="User",
            password="StrongPass123!",
            is_verified=False,
        )

    def test_resend_requires_email(self):
        response = self.client.post(self.resend_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_sends_email_to_unverified_user(self):
        response = self.client.post(
            self.resend_url,
            {"email": self.unverified_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.unverified_user.email])
        self.assertTrue(
            AuthToken.objects.filter(
                user=self.unverified_user,
                purpose=AuthToken.Purpose.EMAIL_VERIFICATION,
            ).exists()
        )

    def test_resend_gives_generic_response_for_unknown_email(self):
        response = self.client.post(
            self.resend_url,
            {"email": "ghost@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_does_not_reveal_verified_accounts(self):
        verified = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password="StrongPass123!",
            is_verified=True,
        )

        known = self.client.post(
            self.resend_url, {"email": verified.email}, format="json"
        )
        unknown = self.client.post(
            self.resend_url, {"email": "ghost@example.com"}, format="json"
        )

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 0)  # no email for a verified user

class ProfileTests(APITestCase):
    """Tests for updating the current user's profile via PATCH /me/."""

    def setUp(self):
        self.login_url = "/api/v1/auth/login/"
        self.me_url = "/api/v1/auth/me/"
        self.password = "StrongPass123!"

        self.user = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password=self.password,
            is_verified=True,
        )
        User.objects.create_user(
            email="other@example.com",
            username="otheruser",
            first_name="Other",
            last_name="User",
            password=self.password,
            is_verified=True,
        )

    def authenticate(self):
        response = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}"
        )

    def test_patch_requires_authentication(self):
        response = self.client.patch(
            self.me_url, {"bio": "hello"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_updates_profile_fields(self):
        self.authenticate()
        response = self.client.patch(
            self.me_url,
            {"first_name": "Changed", "bio": "New bio"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Changed")
        self.assertEqual(self.user.bio, "New bio")

    def test_patch_cannot_change_protected_fields(self):
        self.authenticate()
        response = self.client.patch(
            self.me_url,
            {
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
                "is_verified": False,
                "email": "hacker@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.SUBSCRIBER)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_verified)
        self.assertEqual(self.user.email, "verified@example.com")

    def test_patch_rejects_taken_username(self):
        self.authenticate()
        response = self.client.patch(
            self.me_url, {"username": "otheruser"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_allows_keeping_own_username(self):
        self.authenticate()
        response = self.client.patch(
            self.me_url, {"username": "verifieduser"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)