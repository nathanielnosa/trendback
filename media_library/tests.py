import shutil
import tempfile
import uuid
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Media

MEDIA_DIR = tempfile.mkdtemp(prefix="backblog-test-media-")

LIST_URL = "/api/v1/media/"


def detail_url(media_id):
    return f"/api/v1/media/{media_id}/"


def image_file(name="photo.png", fmt="PNG", size=(800, 600), color=(200, 30, 30)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/octet-stream")


@override_settings(MEDIA_ROOT=MEDIA_DIR)
class MediaLibraryTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, MEDIA_DIR, ignore_errors=True)

    def setUp(self):
        self.password = "StrongPass123!"
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.other_author = self.make_user(User.Role.AUTHOR, "author2")
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

    def upload(self, user, upload=None, **extra):
        self.client.force_authenticate(user=user)
        data = {"file": upload or image_file(), **extra}
        return self.client.post(LIST_URL, data, format="multipart")

    # ---------- uploading ----------
    def test_author_can_upload(self):
        response = self.upload(self.author, alt_text="A red square")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(data["alt_text"], "A red square")
        self.assertEqual(data["width"], 800)
        self.assertEqual(data["height"], 600)
        self.assertEqual(data["content_type"], "image/png")
        self.assertEqual(data["uploaded_by"], "author1")
        self.assertTrue(data["url"].startswith("http"))
        self.assertTrue(data["thumbnail_url"].endswith(".webp"))

    def test_editor_and_admin_can_upload(self):
        for user in (self.editor, self.admin):
            with self.subTest(role=user.role):
                self.assertEqual(self.upload(user).status_code, status.HTTP_201_CREATED)

    def test_files_are_stored(self):
        response = self.upload(self.author)
        media = Media.objects.get(id=response.data["id"])
        self.assertTrue(media.file.storage.exists(media.file.name))
        self.assertTrue(media.file.storage.exists(media.thumbnail.name))
        self.assertEqual(media.size, media.file.size)

    def test_thumbnail_is_scaled_down(self):
        response = self.upload(self.author, image_file(size=(1600, 800)))
        media = Media.objects.get(id=response.data["id"])
        with Image.open(media.thumbnail.path) as thumb:
            self.assertEqual(thumb.size, (400, 200))

    def test_small_images_are_not_enlarged(self):
        response = self.upload(self.author, image_file(size=(100, 100)))
        media = Media.objects.get(id=response.data["id"])
        with Image.open(media.thumbnail.path) as thumb:
            self.assertEqual(thumb.size, (100, 100))

    def test_stored_name_ignores_the_clients_filename_and_extension(self):
        response = self.upload(self.author, image_file(name="../../evil.php"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        media = Media.objects.get(id=response.data["id"])
        self.assertTrue(media.file.name.endswith(".png"))
        self.assertNotIn("evil", media.file.name)
        self.assertIn("evil.php", media.original_name)

    def test_extension_follows_the_real_format(self):
        response = self.upload(self.author, image_file(name="photo.png", fmt="JPEG"))
        self.assertEqual(response.data["content_type"], "image/jpeg")
        self.assertTrue(response.data["url"].endswith(".jpg"))

    def test_every_allowed_format(self):
        for fmt, content_type in (
            ("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp"), ("GIF", "image/gif"),
        ):
            with self.subTest(fmt=fmt):
                response = self.upload(self.author, image_file(fmt=fmt))
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["content_type"], content_type)

    def test_two_uploads_never_share_a_filename(self):
        first = self.upload(self.author, image_file(name="same.png")).data
        second = self.upload(self.author, image_file(name="same.png")).data
        self.assertNotEqual(first["url"], second["url"])

    def test_subscriber_cannot_upload(self):
        self.assertEqual(self.upload(self.subscriber).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Media.objects.count(), 0)

    def test_anonymous_cannot_upload(self):
        response = self.client.post(LIST_URL, {"file": image_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_is_required(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(LIST_URL, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data["errors"])

    def test_text_renamed_to_png_is_refused(self):
        fake = SimpleUploadedFile("photo.png", b"just some text", content_type="image/png")
        response = self.upload(self.author, fake)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.count(), 0)

    def test_svg_is_refused(self):
        svg = SimpleUploadedFile(
            "logo.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            content_type="image/svg+xml",
        )
        self.assertEqual(self.upload(self.author, svg).status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_image_format_is_refused(self):
        response = self.upload(self.author, image_file(name="photo.bmp", fmt="BMP"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_file_is_refused(self):
        with patch("media_library.services.MAX_BYTES", 100):
            response = self.upload(self.author)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.count(), 0)

    def test_oversized_dimensions_are_refused(self):
        with patch("media_library.services.MAX_DIMENSION", 500):
            response = self.upload(self.author)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_alt_text_is_optional(self):
        response = self.upload(self.author)
        self.assertEqual(response.data["alt_text"], "")

    def test_alt_text_length_is_limited(self):
        response = self.upload(self.author, alt_text="x" * 300)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- listing ----------
    def test_author_sees_only_their_own_files(self):
        self.upload(self.author)
        self.upload(self.other_author)
        self.client.force_authenticate(user=self.author)
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["uploaded_by"], "author1")

    def test_editor_sees_everyones_files(self):
        self.upload(self.author)
        self.upload(self.other_author)
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.client.get(LIST_URL).data["count"], 2)

    def test_editor_can_narrow_to_their_own(self):
        self.upload(self.author)
        self.upload(self.editor)
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(LIST_URL, {"mine": "true"})
        self.assertEqual(response.data["count"], 1)

    def test_list_is_paginated(self):
        for _ in range(3):
            self.upload(self.author)
        self.client.force_authenticate(user=self.author)
        response = self.client.get(LIST_URL, {"page_size": 2})
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])

    def test_page_out_of_range_is_404(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.client.get(LIST_URL, {"page": 9}).status_code, status.HTTP_404_NOT_FOUND)

    def test_newest_first(self):
        first = self.upload(self.author).data["id"]
        second = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.author)
        ids = [item["id"] for item in self.client.get(LIST_URL).data["results"]]
        self.assertEqual(ids, [second, first])

    def test_search_by_name_and_alt_text(self):
        self.upload(self.author, image_file(name="sunset.png"), alt_text="Evening sky")
        self.upload(self.author, image_file(name="logo.png"), alt_text="Company mark")
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.client.get(LIST_URL, {"search": "sunset"}).data["count"], 1)
        self.assertEqual(self.client.get(LIST_URL, {"search": "company"}).data["count"], 1)
        self.assertEqual(self.client.get(LIST_URL, {"search": "nothing"}).data["count"], 0)

    def test_subscriber_cannot_list(self):
        self.client.force_authenticate(user=self.subscriber)
        self.assertEqual(self.client.get(LIST_URL).status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_list(self):
        self.assertEqual(self.client.get(LIST_URL).status_code, status.HTTP_401_UNAUTHORIZED)

    # ---------- detail ----------
    def test_owner_can_read_a_file(self):
        media_id = self.upload(self.author).data["id"]
        response = self.client.get(detail_url(media_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], media_id)

    def test_other_author_gets_404(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.other_author)
        self.assertEqual(self.client.get(detail_url(media_id)).status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_read_anyones_file(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.client.get(detail_url(media_id)).status_code, status.HTTP_200_OK)

    def test_unknown_id_is_404(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.client.get(detail_url(uuid.uuid4())).status_code, status.HTTP_404_NOT_FOUND)

    def test_malformed_id_is_404(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.client.get(f"{LIST_URL}not-a-uuid/").status_code, status.HTTP_404_NOT_FOUND)

    def test_subscriber_cannot_read_detail(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.subscriber)
        self.assertEqual(self.client.get(detail_url(media_id)).status_code, status.HTTP_403_FORBIDDEN)

    # ---------- editing ----------
    def test_owner_can_edit_alt_text(self):
        media_id = self.upload(self.author).data["id"]
        response = self.client.patch(detail_url(media_id), {"alt_text": "New text"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["alt_text"], "New text")
        self.assertEqual(Media.objects.get(id=media_id).alt_text, "New text")

    def test_alt_text_can_be_cleared(self):
        media_id = self.upload(self.author, alt_text="Old").data["id"]
        response = self.client.patch(detail_url(media_id), {"alt_text": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["alt_text"], "")

    def test_other_author_cannot_edit(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.other_author)
        response = self.client.patch(detail_url(media_id), {"alt_text": "Hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.get(id=media_id).alt_text, "")

    def test_editor_can_edit_anyones_file(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.editor)
        response = self.client.patch(detail_url(media_id), {"alt_text": "Fixed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_editing_requires_alt_text(self):
        media_id = self.upload(self.author).data["id"]
        response = self.client.patch(detail_url(media_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_editing_cannot_replace_the_file(self):
        media_id = self.upload(self.author).data["id"]
        before = Media.objects.get(id=media_id).file.name
        self.client.patch(detail_url(media_id), {"alt_text": "x", "file": "other.png", "width": 1}, format="json")
        media = Media.objects.get(id=media_id)
        self.assertEqual(media.file.name, before)
        self.assertEqual(media.width, 800)

    # ---------- deleting ----------
    def test_owner_can_delete_and_files_are_removed(self):
        media_id = self.upload(self.author).data["id"]
        media = Media.objects.get(id=media_id)
        file_name, thumb_name, storage = media.file.name, media.thumbnail.name, media.file.storage

        response = self.client.delete(detail_url(media_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=media_id).exists())
        self.assertFalse(storage.exists(file_name))
        self.assertFalse(storage.exists(thumb_name))

    def test_other_author_cannot_delete(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.other_author)
        self.assertEqual(self.client.delete(detail_url(media_id)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=media_id).exists())

    def test_editor_can_delete_anyones_file(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.client.delete(detail_url(media_id)).status_code, status.HTTP_204_NO_CONTENT)

    def test_deleting_a_user_keeps_their_files(self):
        media_id = self.upload(self.author).data["id"]
        self.author.delete()
        media = Media.objects.get(id=media_id)
        self.assertIsNone(media.uploaded_by)

    def test_subscriber_cannot_delete(self):
        media_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(user=self.subscriber)
        self.assertEqual(self.client.delete(detail_url(media_id)).status_code, status.HTTP_403_FORBIDDEN)

    # ---------- error shape ----------
    def test_errors_use_the_standard_shape(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get(detail_url(uuid.uuid4()))
        import json
        body = json.loads(response.content)
        self.assertEqual(set(body), {"success", "message", "errors"})
        self.assertEqual(body["message"], "Media not found.")