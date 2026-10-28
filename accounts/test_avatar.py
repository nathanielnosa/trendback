import io
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


def make_image(name="avatar.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class AvatarUploadTests(APITestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)

        override = override_settings(MEDIA_ROOT=self.media_dir.name)
        override.enable()
        self.addCleanup(override.disable)

        self.me_url = "/api/v1/auth/me/"
        self.user = User.objects.create_user(
            email="verified@example.com",
            username="verifieduser",
            first_name="Verified",
            last_name="User",
            password="StrongPass123!",
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def upload(self, file):
        return self.client.patch(self.me_url, {"avatar": file}, format="multipart")

    def test_no_avatar_by_default(self):
        response = self.client.get(self.me_url)
        self.assertIsNone(response.data["avatar"])

    def test_can_upload_an_avatar(self):
        response = self.upload(make_image())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.startswith("avatars/"))
        self.assertTrue(os.path.exists(self.user.avatar.path))

    def test_upload_returns_an_absolute_url(self):
        response = self.upload(make_image())
        self.assertTrue(response.data["avatar"].startswith("http://testserver/media/avatars/"))

    def test_a_file_that_is_not_an_image_is_rejected(self):
        fake = SimpleUploadedFile("avatar.png", b"this is not an image", content_type="image/png")

        response = self.upload(fake)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_profile_text_fields_can_still_be_updated_without_a_file(self):
        response = self.client.patch(self.me_url, {"bio": "Hello"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_me_returns_the_same_absolute_url_after_upload(self):
        """Fails until MeView.get also uses build_absolute_uri."""
        self.upload(make_image())

        response = self.client.get(self.me_url)

        self.assertTrue(response.data["avatar"].startswith("http://testserver/media/avatars/"))