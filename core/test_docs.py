import json

from rest_framework import status
from rest_framework.test import APITestCase


class ApiDocsTests(APITestCase):
    def load_schema(self):
        response = self.client.get("/api/schema/", {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return json.loads(response.content)

    def test_schema_is_available_without_login(self):
        schema = self.load_schema()
        self.assertIn("openapi", schema)

    def test_schema_has_the_project_title(self):
        from django.conf import settings

        schema = self.load_schema()
        self.assertEqual(
            schema["info"]["title"],
            settings.SPECTACULAR_SETTINGS["TITLE"],
        )

    def test_every_app_appears_in_the_schema(self):
        paths = self.load_schema()["paths"]
        expected = [
            "/api/v1/auth/login/",
            "/api/v1/auth/me/",
            "/api/v1/blog/posts/",
            "/api/v1/blog/my-posts/",
            "/api/v1/blog/review-queue/",
            "/api/v1/comments/",
            "/api/v1/comments/pending/",
            "/api/v1/engagements/bookmarks/",
            "/api/v1/notifications/",
            "/api/v1/analytics/summary/",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertIn(path, paths)

    def test_version_placeholder_is_filled_in(self):
        paths = self.load_schema()["paths"]
        leftovers = [p for p in paths if "{version}" in p]
        self.assertEqual(leftovers, [])

    def test_schema_describes_bearer_authentication(self):
        schemes = self.load_schema()["components"]["securitySchemes"]
        self.assertIn("jwtAuth", schemes)
        self.assertEqual(schemes["jwtAuth"]["scheme"], "bearer")

    def test_swagger_page_loads(self):
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("swagger", response.content.decode().lower())