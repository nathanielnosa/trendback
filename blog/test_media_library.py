import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import User

from .models import MediaAsset, Post

# Uploaded files go to a throw-away folder, never into the real media folder.
TEMP_MEDIA = tempfile.mkdtemp()


def make_user(email, username, role):
    """Create a verified user with the given role."""
    return User.objects.create_user(
        email=email,
        username=username,
        first_name=username.title(),
        last_name="Test",
        password="StrongPass123!",
        is_verified=True,
        role=role,
    )


def png_file(name="pic.png"):
    """A tiny real PNG, ready to upload."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MediaLibraryTests(APITestCase):
    url = "/api/v1/blog/media/"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.author = make_user("a@example.com", "author1", User.Role.AUTHOR)
        self.other = make_user("o@example.com", "author2", User.Role.AUTHOR)
        self.admin = make_user("m@example.com", "admin1", User.Role.ADMIN)

    def upload(self, user):
        """Upload one picture as the given user and return the response."""
        self.client.force_authenticate(user)
        return self.client.post(self.url, {"file": png_file()}, format="multipart")

    def test_upload_is_recorded_and_listed(self):
        response = self.upload(self.author)
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)

        listing = self.client.get(self.url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        self.assertEqual(listing.data["results"][0]["url"], response.data["url"])

    def test_you_only_see_your_own_pictures(self):
        self.upload(self.author)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    def test_delete_removes_the_picture(self):
        asset_id = self.upload(self.author).data["id"]
        response = self.client.delete(f"{self.url}{asset_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MediaAsset.objects.filter(id=asset_id).exists())

    def test_someone_else_cannot_delete_it(self):
        asset_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(f"{self.url}{asset_id}/").status_code, 404)
        self.assertTrue(MediaAsset.objects.filter(id=asset_id).exists())

    def test_admin_can_delete_any(self):
        asset_id = self.upload(self.author).data["id"]
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"{self.url}{asset_id}/").status_code, 204)

    def test_picture_in_use_cannot_be_deleted(self):
        response = self.upload(self.author)
        Post.objects.create(
            author=self.author, title="Uses it", content="<p>x</p>", featured_image=response.data["url"]
        )
        result = self.client.delete(f"{self.url}{response.data['id']}/")
        self.assertEqual(result.status_code, 400)
        self.assertTrue(MediaAsset.objects.filter(id=response.data["id"]).exists())