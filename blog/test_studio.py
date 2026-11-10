import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Post

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


def png_file(name="pic.png", size=(20, 20)):
    """A tiny real PNG, ready to upload."""
    buffer = io.BytesIO()
    Image.new("RGB", size, "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MediaUploadTests(APITestCase):
    url = "/api/v1/blog/media/"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.author = make_user("a@example.com", "author1", User.Role.AUTHOR)
        self.reader = make_user("r@example.com", "reader1", User.Role.SUBSCRIBER)

    def test_author_can_upload_a_picture(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(self.url, {"file": png_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["url"].startswith("http"))
        self.assertIn("/posts/", response.data["url"])
        self.assertTrue(response.data["url"].endswith(".png"))

    def test_reader_cannot_upload(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(self.url, {"file": png_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_upload(self):
        response = self.client.post(self.url, {"file": png_file()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_file_is_rejected(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)

    def test_fake_picture_is_rejected(self):
        self.client.force_authenticate(self.author)
        fake = SimpleUploadedFile("evil.png", b"not really a picture", content_type="image/png")
        response = self.client.post(self.url, {"file": fake}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_picture_is_rejected(self):
        self.client.force_authenticate(self.author)
        big = SimpleUploadedFile("big.png", b"0" * (5 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.post(self.url, {"file": big}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MyPostDetailTests(APITestCase):
    def setUp(self):
        self.author = make_user("a@example.com", "author1", User.Role.AUTHOR)
        self.other = make_user("o@example.com", "author2", User.Role.AUTHOR)
        self.editor = make_user("e@example.com", "editor1", User.Role.EDITOR)
        self.draft = Post.objects.create(
            author=self.author, title="My Draft", content="Draft body.", status=Post.Status.DRAFT
        )

    def url(self):
        return f"/api/v1/blog/my-posts/{self.draft.id}/"

    def test_author_reads_own_draft(self):
        self.client.force_authenticate(self.author)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "My Draft")

    def test_other_author_cannot_read_it(self):
        self.client.force_authenticate(self.other)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_read_it(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)