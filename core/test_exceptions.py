from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import (
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.test import APITestCase

from accounts.models import User
from analytics.views import AnalyticsSummaryView
from core import exceptions as exceptions_module
from core.exceptions import custom_exception_handler


def make_user(role, username):
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        first_name=username.title(),
        last_name="Tester",
        password="StrongPass123!",
        is_verified=True,
        role=role,
    )


# ============================================================
# THE HANDLER ON ITS OWN
# ============================================================
class HandlerUnitTests(TestCase):
    def handle(self, exc):
        return custom_exception_handler(exc, {"request": None, "view": None})

    def test_validation_error_with_fields(self):
        response = self.handle(ValidationError({"title": ["This field is required."]}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {
                "success": False,
                "message": "Validation failed.",
                "errors": {"title": ["This field is required."]},
            },
        )

    def test_validation_error_with_a_list(self):
        response = self.handle(ValidationError(["Something is wrong."]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["errors"], ["Something is wrong."])
        self.assertFalse(response.data["success"])

    def test_not_found(self):
        response = self.handle(NotFound())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data,
            {"success": False, "message": "Not found.", "errors": None},
        )

    def test_permission_denied(self):
        response = self.handle(PermissionDenied())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["message"], "You do not have permission to perform this action."
        )
        self.assertIsNone(response.data["errors"])

    def test_not_authenticated(self):
        response = self.handle(NotAuthenticated())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_method_not_allowed(self):
        response = self.handle(MethodNotAllowed("DELETE"))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertIn("DELETE", response.data["message"])

    def test_unexpected_error_returns_a_generic_500(self):
        with patch.object(exceptions_module, "logger") as mock_logger:
            response = self.handle(RuntimeError("secret internal detail"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.data,
            {
                "success": False,
                "message": "An unexpected server error occurred.",
                "errors": None,
            },
        )
        self.assertNotIn("secret internal detail", str(response.data))
        mock_logger.exception.assert_called_once()

    def test_unexpected_error_is_left_to_django_when_debugging(self):
        with self.settings(DEBUG=True), patch.object(exceptions_module, "logger"):
            response = self.handle(RuntimeError("boom"))
        self.assertIsNone(response)


# ============================================================
# THE HANDLER INSIDE THE REAL API
# ============================================================
class HandlerThroughTheApiTests(APITestCase):
    def setUp(self):
        self.editor = make_user(User.Role.EDITOR, "editor1")
        self.author = make_user(User.Role.AUTHOR, "author1")

    def assert_standard_error(self, response, code):
        self.assertEqual(response.status_code, code)
        self.assertEqual(set(response.data), {"success", "message", "errors"})
        self.assertIs(response.data["success"], False)
        self.assertTrue(response.data["message"])

    def test_unauthenticated_request_gets_the_standard_401(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assert_standard_error(response, status.HTTP_401_UNAUTHORIZED)
        self.assertIsNone(response.data["errors"])

    def test_rendered_json_matches_the_standard_shape(self):
        import json

        response = self.client.get("/api/v1/auth/me/")
        body = json.loads(response.content)
        self.assertEqual(set(body), {"success", "message", "errors"})
        self.assertFalse(body["success"])

    def test_invalid_token_gets_the_standard_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get("/api/v1/auth/me/")
        self.assert_standard_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_forbidden_request_gets_the_standard_403(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get("/api/v1/analytics/summary/")
        self.assert_standard_error(response, status.HTTP_403_FORBIDDEN)

    def test_missing_object_gets_the_standard_404(self):
        import uuid

        self.client.force_authenticate(user=self.author)
        response = self.client.get(f"/api/v1/notifications/{uuid.uuid4()}/")
        self.assert_standard_error(response, status.HTTP_404_NOT_FOUND)

    def test_page_out_of_range_gets_the_standard_404(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get("/api/v1/notifications/", {"page": 99})
        self.assert_standard_error(response, status.HTTP_404_NOT_FOUND)

    def test_wrong_method_gets_the_standard_405(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.delete("/api/v1/analytics/events/")
        self.assert_standard_error(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unsupported_api_version_gets_the_standard_404(self):
        response = self.client.get("/api/v2/blog/posts/")
        self.assert_standard_error(response, status.HTTP_404_NOT_FOUND)

    def test_crash_inside_a_view_returns_a_generic_500(self):
        self.client.force_authenticate(user=self.editor)
        self.client.raise_request_exception = False

        with patch.object(
            AnalyticsSummaryView, "get", side_effect=RuntimeError("secret internal detail")
        ), patch.object(exceptions_module, "logger"):
            response = self.client.get("/api/v1/analytics/summary/")

        self.assert_standard_error(response, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertNotIn("secret internal detail", str(response.data))


# ============================================================
# HEALTH CHECK
# ============================================================
class HealthCheckTests(APITestCase):
    def test_health_check_is_public(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")

    def test_health_check_is_read_only(self):
        response = self.client.post("/api/health/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(APITestCase):
    def test_error_logs_reach_the_backblog_log_files(self):
        name = exceptions_module.logger.name
        self.assertTrue(
            name == "backblog" or name.startswith("backblog."),
            f"logger is '{name}', so errors skip the files configured for 'backblog'",
        )

    def test_unknown_api_route_returns_json(self):
        response = self.client.get("/api/v1/this-route-does-not-exist/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(response["Content-Type"].startswith("application/json"))