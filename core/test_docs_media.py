import json

from rest_framework import status
from rest_framework.test import APITestCase


class MediaAndSEODocsTests(APITestCase):
    def schema(self):
        response = self.client.get("/api/schema/", {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return json.loads(response.content)

    def operation(self, path, method):
        paths = self.schema()["paths"]
        self.assertIn(path, paths)
        self.assertIn(method, paths[path])
        return paths[path][method]

    def ref(self, operation, code):
        content = operation["responses"][code]["content"]["application/json"]["schema"]
        return content.get("$ref", "")

    def parameter_names(self, operation):
        return {p["name"] for p in operation.get("parameters", [])}

    # ---------- media ----------
    def test_media_endpoints_exist(self):
        paths = self.schema()["paths"]
        self.assertTrue({"get", "post"} <= set(paths["/api/v1/media/"]))
        self.assertTrue({"get", "patch", "delete"} <= set(paths["/api/v1/media/{media_id}/"]))

    def test_upload_is_documented_as_multipart(self):
        operation = self.operation("/api/v1/media/", "post")
        self.assertIn("multipart/form-data", operation["requestBody"]["content"])
        self.assertTrue(self.ref(operation, "201").endswith("Media"))
        for code in ("400", "401", "403"):
            self.assertIn(code, operation["responses"])

    def test_list_documents_filters_and_pagination(self):
        operation = self.operation("/api/v1/media/", "get")
        for name in ("search", "mine", "page", "page_size"):
            self.assertIn(name, self.parameter_names(operation))
        self.assertTrue(self.ref(operation, "200").endswith("MediaPage"))

    def test_detail_methods(self):
        operation = self.operation("/api/v1/media/{media_id}/", "patch")
        self.assertIn("requestBody", operation)
        delete = self.operation("/api/v1/media/{media_id}/", "delete")
        self.assertIn("204", delete["responses"])
        self.assertTrue(self.ref(self.operation("/api/v1/media/{media_id}/", "get"), "404").endswith("ErrorResponse"))

    # ---------- seo ----------
    def test_post_seo_is_documented(self):
        operation = self.operation("/api/v1/seo/posts/{slug}/", "get")
        self.assertTrue(self.ref(operation, "200").endswith("PostSEO"))
        self.assertTrue(self.ref(operation, "404").endswith("ErrorResponse"))

    def test_open_graph_and_twitter_fields_are_described(self):
        schemas = self.schema()["components"]["schemas"]
        self.assertIn("image", schemas["OpenGraphTags"]["properties"])
        self.assertIn("card", schemas["TwitterCardTags"]["properties"])

    # ---------- grouping ----------
    def test_new_groups_exist(self):
        tags = {
            tag
            for methods in self.schema()["paths"].values()
            for operation in methods.values()
            if isinstance(operation, dict)
            for tag in operation.get("tags", [])
        }
        self.assertIn("Media", tags)
        self.assertIn("SEO", tags)