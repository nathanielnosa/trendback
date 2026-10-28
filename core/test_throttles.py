import json
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

from accounts.models import User

LOGIN = "/api/v1/auth/login/"
FORGOT = "/api/v1/auth/forgot-password/"
RESEND = "/api/v1/auth/resend-verification/"
REGISTER = "/api/v1/auth/register/"

# Roomy limits for the scopes a test is not about.
ROOMY = {"login": "1000/min", "login_email": "1000/min", "auth_email": "1000/hour"}


class ThrottleTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            email="reader@example.com",
            username="reader",
            first_name="Reader",
            last_name="Tester",
            password="StrongPass123!",
            is_verified=True,
            role=User.Role.SUBSCRIBER,
        )

    def limits(self, **overrides):
        return patch.dict(SimpleRateThrottle.THROTTLE_RATES, {**ROOMY, **overrides})

    def login(self, email="reader@example.com", password="wrong-password", **extra):
        return self.client.post(LOGIN, {"email": email, "password": password}, format="json", **extra)


class SettingsTests(SimpleTestCase):
    def test_every_scope_has_a_rate(self):
        for scope in ("login", "login_email", "auth_email"):
            self.assertIn(scope, SimpleRateThrottle.THROTTLE_RATES)


class LoginThrottleTests(ThrottleTestBase):
    def test_normal_use_is_not_blocked_while_testing(self):
        # The test run raises every limit so other test files can log in freely.
        for _ in range(30):
            self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_one_email_is_blocked_after_too_many_attempts(self):
        with self.limits(login_email="2/min"):
            self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)
            response = self.login()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_blocked_response_has_the_standard_shape_and_retry_after(self):
        with self.limits(login_email="1/min"):
            self.login()
            response = self.login()
        body = json.loads(response.content)
        self.assertEqual(set(body), {"success", "message", "errors"})
        self.assertIs(body["success"], False)
        self.assertIn("throttled", body["message"].lower())
        self.assertTrue(int(response["Retry-After"]) > 0)

    def test_the_right_password_is_also_blocked_once_over_the_limit(self):
        with self.limits(login_email="2/min"):
            self.login()
            self.login()
            response = self.login(password="StrongPass123!")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_a_successful_login_within_the_limit_still_works(self):
        with self.limits(login_email="2/min"):
            response = self.login(password="StrongPass123!")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_email_limit_ignores_case_and_spaces(self):
        with self.limits(login_email="2/min"):
            self.login("reader@example.com")
            self.login("  READER@Example.com ")
            response = self.login("Reader@EXAMPLE.com")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_blocking_one_email_does_not_block_another(self):
        with self.limits(login_email="1/min"):
            self.login("one@example.com")
            self.assertEqual(self.login("one@example.com").status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertEqual(self.login("two@example.com").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_email_limit_follows_the_email_across_addresses(self):
        with self.limits(login_email="1/min"):
            self.login(REMOTE_ADDR="10.0.0.1")
            response = self.login(REMOTE_ADDR="10.0.0.2")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_ip_limit_counts_every_email_from_one_address(self):
        with self.limits(login="3/min"):
            for number in range(3):
                self.assertEqual(self.login(f"user{number}@example.com").status_code, status.HTTP_401_UNAUTHORIZED)
            response = self.login("user9@example.com")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_ip_limit_does_not_affect_other_addresses(self):
        with self.limits(login="1/min"):
            self.login(REMOTE_ADDR="10.0.0.1")
            self.assertEqual(self.login(REMOTE_ADDR="10.0.0.1").status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertEqual(self.login(REMOTE_ADDR="10.0.0.2").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_missing_email_is_still_limited_by_ip(self):
        with self.limits(login="2/min"):
            self.client.post(LOGIN, {}, format="json")
            self.client.post(LOGIN, {}, format="json")
            response = self.client.post(LOGIN, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class EmailEndpointThrottleTests(ThrottleTestBase):
    def forgot(self, **extra):
        return self.client.post(FORGOT, {"email": "nobody@example.com"}, format="json", **extra)

    def test_forgot_password_is_limited_per_ip(self):
        with self.limits(auth_email="2/hour"):
            self.assertEqual(self.forgot().status_code, status.HTTP_200_OK)
            self.assertEqual(self.forgot().status_code, status.HTTP_200_OK)
            response = self.forgot()
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_resend_verification_is_limited(self):
        with self.limits(auth_email="1/hour"):
            self.client.post(RESEND, {"email": "nobody@example.com"}, format="json")
            response = self.client.post(RESEND, {"email": "nobody@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_register_is_limited(self):
        with self.limits(auth_email="1/hour"):
            self.client.post(REGISTER, {}, format="json")
            response = self.client.post(REGISTER, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_the_three_endpoints_share_one_allowance(self):
        with self.limits(auth_email="2/hour"):
            self.forgot()
            self.client.post(RESEND, {"email": "nobody@example.com"}, format="json")
            response = self.client.post(REGISTER, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_other_addresses_are_not_affected(self):
        with self.limits(auth_email="1/hour"):
            self.forgot(REMOTE_ADDR="10.0.0.1")
            self.assertEqual(self.forgot(REMOTE_ADDR="10.0.0.1").status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertEqual(self.forgot(REMOTE_ADDR="10.0.0.2").status_code, status.HTTP_200_OK)

    def test_login_limits_do_not_touch_these_endpoints(self):
        with self.limits(login="1/min", login_email="1/min"):
            self.login()
            self.assertEqual(self.forgot().status_code, status.HTTP_200_OK)

    def test_other_account_endpoints_are_not_limited(self):
        with self.limits(login="1/min", login_email="1/min", auth_email="1/hour"):
            self.client.force_authenticate(user=self.user)
            for _ in range(3):
                self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, status.HTTP_200_OK)


class CacheDownTests(ThrottleTestBase):
    """When Redis is unreachable the limiter steps aside instead of crashing."""

    def broken_cache(self):
        broken = Mock()
        broken.get.side_effect = ConnectionError("redis is down")
        broken.set.side_effect = ConnectionError("redis is down")
        return patch.object(SimpleRateThrottle, "cache", broken)

    def test_login_still_works(self):
        with self.broken_cache(), self.assertLogs("backblog.throttles", "WARNING"):
            response = self.login(password="StrongPass123!")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_wrong_password_is_still_a_401_not_a_500(self):
        with self.broken_cache(), self.assertLogs("backblog.throttles", "WARNING"):
            response = self.login()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forgot_password_still_works(self):
        with self.broken_cache(), self.assertLogs("backblog.throttles", "WARNING"):
            response = self.client.post(FORGOT, {"email": "nobody@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)