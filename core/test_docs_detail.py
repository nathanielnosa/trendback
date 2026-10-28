import json

from rest_framework import status
from rest_framework.test import APITestCase


class DocumentedSchemaTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._schema = None

    def schema(self):
        response = self.client.get("/api/schema/", {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return json.loads(response.content)

    def operation(self, path, method):
        paths = self.schema()["paths"]
        self.assertIn(path, paths)
        self.assertIn(method, paths[path])
        return paths[path][method]

    def response_ref(self, operation, code="200"):
        content = operation["responses"][code]["content"]["application/json"]["schema"]
        return content.get("$ref", "")

    def parameter_names(self, operation):
        return {p["name"] for p in operation.get("parameters", [])}

    # ---------- auth ----------
    def test_every_auth_post_endpoint_describes_its_request_body(self):
        for path in (
            "register", "verify-email", "resend-verification", "login",
            "forgot-password", "reset-password", "refresh", "logout", "change-password",
        ):
            with self.subTest(path=path):
                operation = self.operation(f"/api/v1/auth/{path}/", "post")
                self.assertIn("requestBody", operation)

    def test_login_describes_tokens_and_failures(self):
        operation = self.operation("/api/v1/auth/login/", "post")
        self.assertTrue(self.response_ref(operation).endswith("LoginResponse"))
        for code in ("400", "401", "403"):
            self.assertIn(code, operation["responses"])

    def test_me_documents_get_and_patch_with_avatar_upload(self):
        paths = self.schema()["paths"]["/api/v1/auth/me/"]
        self.assertIn("get", paths)
        self.assertIn("patch", paths)
        content_types = set(paths["patch"]["requestBody"]["content"])
        self.assertIn("multipart/form-data", content_types)
        self.assertIn("application/json", content_types)

    def test_errors_are_documented_in_the_standard_shape(self):
        for path, method, code in (
            ("/api/v1/auth/login/", "post", "401"),
            ("/api/v1/auth/login/", "post", "400"),
            ("/api/v1/blog/posts/{post_id}/", "get", "404"),
            ("/api/v1/comments/{comment_id}/moderate/", "post", "403"),
        ):
            with self.subTest(path=path, code=code):
                operation = self.operation(path, method)
                self.assertTrue(self.response_ref(operation, code).endswith("ErrorResponse"))

    # ---------- posts ----------
    def test_post_list_documents_filters_and_pagination(self):
        operation = self.operation("/api/v1/blog/posts/", "get")
        for name in ("category", "tag", "author", "featured", "trending", "search", "page", "page_size"):
            self.assertIn(name, self.parameter_names(operation))
        self.assertTrue(self.response_ref(operation).endswith("PostPage"))

    def test_post_create_describes_body_and_errors(self):
        operation = self.operation("/api/v1/blog/posts/", "post")
        self.assertIn("requestBody", operation)
        for code in ("201", "400", "401", "403"):
            self.assertIn(code, operation["responses"])

    def test_post_detail_documents_every_method(self):
        paths = self.schema()["paths"]["/api/v1/blog/posts/{post_id}/"]
        for method in ("get", "put", "patch", "delete"):
            self.assertIn(method, paths)
        self.assertIn("204", paths["delete"]["responses"])

    def test_dashboard_endpoints_are_documented(self):
        mine = self.operation("/api/v1/blog/my-posts/", "get")
        self.assertIn("status", self.parameter_names(mine))
        queue = self.operation("/api/v1/blog/review-queue/", "get")
        self.assertIn("status", self.parameter_names(queue))

    def test_review_publish_and_submit_describe_their_request(self):
        for suffix in ("review", "publish", "submit-review"):
            with self.subTest(action=suffix):
                operation = self.operation(f"/api/v1/blog/posts/{{post_id}}/{suffix}/", "post")
                self.assertIn("requestBody", operation)
                self.assertIn("200", operation["responses"])

    # ---------- comments ----------
    def test_comment_endpoints_are_documented(self):
        listing = self.operation("/api/v1/comments/", "get")
        self.assertIn("post", self.parameter_names(listing))

        create = self.operation("/api/v1/comments/", "post")
        self.assertIn("requestBody", create)

        self.operation("/api/v1/comments/{comment_id}/", "patch")
        self.operation("/api/v1/comments/{comment_id}/", "delete")

        moderate = self.operation("/api/v1/comments/{comment_id}/moderate/", "post")
        self.assertIn("requestBody", moderate)

    def test_pending_comments_are_paginated(self):
        operation = self.operation("/api/v1/comments/pending/", "get")
        self.assertTrue(self.response_ref(operation).endswith("PendingCommentPage"))

    # ---------- notifications ----------
    def test_notification_list_documents_filters_and_unread_count(self):
        operation = self.operation("/api/v1/notifications/", "get")
        for name in ("is_read", "type", "page", "page_size"):
            self.assertIn(name, self.parameter_names(operation))
        self.assertTrue(self.response_ref(operation).endswith("NotificationListResponse"))

    def test_other_notification_endpoints_are_documented(self):
        self.operation("/api/v1/notifications/{notification_id}/", "get")
        self.operation("/api/v1/notifications/{notification_id}/read/", "patch")
        self.operation("/api/v1/notifications/read-all/", "patch")
        self.operation("/api/v1/notifications/unread/", "get")

    # ---------- the page itself ----------
    def test_operations_are_grouped_under_tags(self):
        tags = {
            tag
            for methods in self.schema()["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict)
            for tag in operation.get("tags", [])
        }
        for expected in ("Auth", "Posts", "Comments", "Notifications"):
            self.assertIn(expected, tags)