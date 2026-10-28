import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from blog.models import Post
from core.renderers import normalize_error

SHAPE = {"success", "message", "errors"}


def fake_response(code):
    return SimpleNamespace(status_code=code, status_text={400: "Bad Request", 404: "Not Found"}.get(code, ""))


# ============================================================
# THE RESHAPING RULES ON THEIR OWN
# ============================================================
class NormalizeErrorTests(SimpleTestCase):
    def test_message_only(self):
        result = normalize_error({"message": "Post not found."}, fake_response(404))
        self.assertEqual(result, {"success": False, "message": "Post not found.", "errors": None})

    def test_error_key(self):
        result = normalize_error({"error": "Invalid event type."}, fake_response(400))
        self.assertEqual(result, {"success": False, "message": "Invalid event type.", "errors": None})

    def test_detail_key(self):
        result = normalize_error({"detail": "Not found."}, fake_response(404))
        self.assertEqual(result["message"], "Not found.")

    def test_extra_keys_move_into_errors(self):
        result = normalize_error({"message": "Nope.", "code": "x"}, fake_response(400))
        self.assertEqual(result["errors"], {"code": "x"})

    def test_field_errors(self):
        data = {"email": ["This field is required."]}
        result = normalize_error(data, fake_response(400))
        self.assertEqual(
            result,
            {"success": False, "message": "Validation failed.", "errors": data},
        )

    def test_field_error_that_is_a_plain_string(self):
        result = normalize_error({"scheduled_at": "Must be in the future."}, fake_response(400))
        self.assertEqual(result["errors"], {"scheduled_at": "Must be in the future."})

    def test_a_field_called_message_that_is_a_list_stays_a_field_error(self):
        result = normalize_error({"message": ["Too long."]}, fake_response(400))
        self.assertEqual(result["message"], "Validation failed.")
        self.assertEqual(result["errors"], {"message": ["Too long."]})

    def test_list_of_errors(self):
        result = normalize_error(["Something is wrong."], fake_response(400))
        self.assertEqual(result["errors"], ["Something is wrong."])
        self.assertFalse(result["success"])

    def test_empty_body_uses_the_status_text(self):
        result = normalize_error(None, fake_response(404))
        self.assertEqual(result, {"success": False, "message": "Not Found", "errors": None})

    def test_already_standard_is_returned_untouched(self):
        data = {"success": False, "message": "Not found.", "errors": None}
        self.assertIs(normalize_error(data, fake_response(404)), data)


# ============================================================
# THROUGH THE REAL API
# ============================================================
class ErrorShapeThroughTheApiTests(APITestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.subscriber = self.make_user(User.Role.SUBSCRIBER, "reader1")

    def make_user(self, role, username):
        return User.objects.create_user(
            email=f"{username}@example.com",
            username=username,
            first_name=username.title(),
            last_name="Tester",
            password=self.password,
            is_verified=True,
            role=role,
        )

    def body(self, response):
        return json.loads(response.content)

    def assert_standard(self, response, code, message=None):
        self.assertEqual(response.status_code, code)
        body = self.body(response)
        self.assertEqual(set(body), SHAPE)
        self.assertIs(body["success"], False)
        self.assertTrue(body["message"])
        if message is not None:
            self.assertEqual(body["message"], message)
        return body

    # ----- views that return {"message": ...} -----
    def test_wrong_password(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.author.email, "password": "wrong"},
            format="json",
        )
        body = self.assert_standard(response, 401, "Invalid email or password.")
        self.assertIsNone(body["errors"])

    def test_missing_email_on_forgot_password(self):
        response = self.client.post("/api/v1/auth/forgot-password/", {}, format="json")
        self.assert_standard(response, 400, "Email address is required.")

    def test_post_not_found(self):
        response = self.client.get(f"/api/v1/blog/posts/{uuid.uuid4()}/")
        self.assert_standard(response, 404, "Post not found.")

    def test_invalid_post_filter_on_comments(self):
        response = self.client.get("/api/v1/comments/", {"post": "not-a-uuid"})
        self.assert_standard(response, 400, "Invalid post id.")

    # ----- views that return {"error": ...} -----
    def test_invalid_analytics_event_type(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.get("/api/v1/analytics/events/", {"type": "bogus"})
        body = self.assert_standard(response, 400, "Invalid event type.")
        self.assertIsNone(body["errors"])

    def test_invalid_trending_days(self):
        response = self.client.get("/api/v1/analytics/trending/", {"days": "abc"})
        self.assert_standard(response, 400)

    # ----- serializer errors -----
    def test_registration_errors_are_listed_by_field(self):
        response = self.client.post("/api/v1/auth/register/", {}, format="json")
        body = self.assert_standard(response, 400, "Validation failed.")
        for field in ("email", "username", "password"):
            self.assertIn(field, body["errors"])

    def test_scheduling_in_the_past(self):
        post = Post.objects.create(
            author=self.author, title="Ready", content="Body", status=Post.Status.APPROVED
        )
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            f"/api/v1/blog/posts/{post.id}/publish/",
            {
                "action": "schedule",
                "scheduled_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        body = self.assert_standard(response, 400)
        self.assertIn("scheduled_at", body["errors"])

    # ----- errors raised as exceptions (already standard) -----
    def test_unauthenticated(self):
        self.assert_standard(self.client.get("/api/v1/auth/me/"), 401)

    def test_forbidden(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            "/api/v1/blog/posts/", {"title": "t", "content": "c"}, format="json"
        )
        self.assert_standard(response, 403)

    def test_wrong_method(self):
        self.client.force_authenticate(user=self.editor)
        self.assert_standard(self.client.delete("/api/v1/analytics/events/"), 405)

    def test_page_out_of_range(self):
        self.client.force_authenticate(user=self.author)
        self.assert_standard(self.client.get("/api/v1/notifications/", {"page": 99}), 404)

    # ----- successes must not change -----
    def test_login_success_is_untouched(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.author.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = self.body(response)
        self.assertIn("tokens", body)
        self.assertNotIn("success", body)

    def test_post_list_success_is_untouched(self):
        Post.objects.create(
            author=self.author, title="Live", content="Body", status=Post.Status.PUBLISHED
        )
        response = self.client.get("/api/v1/blog/posts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = self.body(response)
        self.assertEqual(set(body), {"count", "next", "previous", "results"})

    def test_delete_success_is_untouched(self):
        post = Post.objects.create(
            author=self.author, title="Gone", content="Body", status=Post.Status.DRAFT
        )
        self.client.force_authenticate(user=self.author)
        response = self.client.delete(f"/api/v1/blog/posts/{post.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")