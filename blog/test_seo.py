import xml.etree.ElementTree as ET
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Category, Post, Tag

SEO_URL = "/api/v1/seo/posts/{slug}/"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "dc": "http://purl.org/dc/elements/1.1/"}


@override_settings(FRONTEND_URL="https://example.test", SITE_NAME="Test Archive")
class SEOTestBase(APITestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="writer@example.com",
            username="writer",
            first_name="Ada",
            last_name="Obi",
            password="StrongPass123!",
            is_verified=True,
            role=User.Role.AUTHOR,
        )

    def post(self, title="Hello World", **fields):
        defaults = {
            "author": self.author,
            "title": title,
            "content": "Body text of the post.",
            "status": Post.Status.PUBLISHED,
            "published_at": timezone.now() - timedelta(hours=1),
        }
        defaults.update(fields)
        return Post.objects.create(**defaults)

    def seo(self, post):
        return self.client.get(SEO_URL.format(slug=post.slug))


# ============================================================
# /api/v1/seo/posts/<slug>/
# ============================================================
@override_settings(FRONTEND_URL="https://example.test", SITE_NAME="Test Archive")
class PostSEOTests(SEOTestBase):
    def test_shape(self):
        response = self.seo(self.post())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {"title", "description", "canonical_url", "image", "robots", "open_graph", "twitter", "json_ld"},
        )

    def test_is_public(self):
        self.assertEqual(self.seo(self.post()).status_code, status.HTTP_200_OK)

    def test_title_falls_back_to_the_post_title(self):
        self.assertEqual(self.seo(self.post("My Post")).data["title"], "My Post")

    def test_written_seo_title_wins(self):
        self.assertEqual(self.seo(self.post(seo_title="Better title")).data["title"], "Better title")

    def test_written_description_wins_and_is_not_cut(self):
        text = "d" * 200
        self.assertEqual(self.seo(self.post(seo_description=text)).data["description"], text)

    def test_description_falls_back_to_the_excerpt(self):
        response = self.seo(self.post(excerpt="A short summary."))
        self.assertEqual(response.data["description"], "A short summary.")

    def test_description_falls_back_to_the_content_without_html(self):
        response = self.seo(self.post(content="<p>Hello <b>there</b></p>\n<p>friend</p>"))
        self.assertEqual(response.data["description"], "Hello there friend")

    def test_long_content_is_cut_to_160_characters(self):
        response = self.seo(self.post(content="word " * 200))
        self.assertLessEqual(len(response.data["description"]), 160)

    def test_canonical_defaults_to_the_frontend_address(self):
        post = self.post()
        self.assertEqual(self.seo(post).data["canonical_url"], f"https://example.test/posts/{post.slug}")

    @override_settings(FRONTEND_POST_PATH="/blog/{slug}")
    def test_post_path_can_be_changed(self):
        post = self.post()
        self.assertEqual(self.seo(post).data["canonical_url"], f"https://example.test/blog/{post.slug}")

    def test_written_canonical_wins(self):
        response = self.seo(self.post(canonical_url="https://original.test/story"))
        self.assertEqual(response.data["canonical_url"], "https://original.test/story")
        self.assertEqual(response.data["open_graph"]["url"], "https://original.test/story")

    def test_image_and_card_type(self):
        response = self.seo(self.post(featured_image="https://cdn.test/a.jpg"))
        self.assertEqual(response.data["image"], "https://cdn.test/a.jpg")
        self.assertEqual(response.data["open_graph"]["image"], "https://cdn.test/a.jpg")
        self.assertEqual(response.data["twitter"]["image"], "https://cdn.test/a.jpg")
        self.assertEqual(response.data["twitter"]["card"], "summary_large_image")

    def test_no_image_uses_a_small_card(self):
        response = self.seo(self.post())
        self.assertIsNone(response.data["image"])
        self.assertEqual(response.data["twitter"]["card"], "summary")

    def test_open_graph_details(self):
        category = Category.objects.create(name="Tech", slug="tech")
        post = self.post()
        post.category = category
        post.save()
        post.tags.add(Tag.objects.create(name="python", slug="python"), Tag.objects.create(name="django", slug="django"))
        og = self.seo(post).data["open_graph"]
        self.assertEqual(og["type"], "article")
        self.assertEqual(og["site_name"], "Test Archive")
        self.assertEqual(og["author"], "Ada Obi")
        self.assertEqual(og["section"], "Tech")
        self.assertEqual(sorted(og["tags"]), ["django", "python"])
        self.assertIsNotNone(og["published_time"])

    def test_json_ld_article(self):
        data = self.seo(self.post("Structured")).data["json_ld"]
        self.assertEqual(data["@type"], "Article")
        self.assertEqual(data["headline"], "Structured")
        self.assertEqual(data["author"], {"@type": "Person", "name": "Ada Obi"})
        self.assertEqual(data["publisher"]["name"], "Test Archive")

    def test_robots_allows_indexing(self):
        self.assertEqual(self.seo(self.post()).data["robots"], "index, follow")

    # ----- what must stay hidden -----
    def test_draft_is_404(self):
        self.assertEqual(self.seo(self.post(status=Post.Status.DRAFT)).status_code, status.HTTP_404_NOT_FOUND)

    def test_under_review_is_404(self):
        post = self.post(status=Post.Status.UNDER_REVIEW)
        self.assertEqual(self.seo(post).status_code, status.HTTP_404_NOT_FOUND)

    def test_archived_is_404(self):
        self.assertEqual(self.seo(self.post(status=Post.Status.ARCHIVED)).status_code, status.HTTP_404_NOT_FOUND)

    def test_private_is_404(self):
        post = self.post(visibility=Post.Visibility.PRIVATE)
        self.assertEqual(self.seo(post).status_code, status.HTTP_404_NOT_FOUND)

    def test_scheduled_for_later_is_404(self):
        post = self.post(published_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.seo(post).status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_slug_is_404(self):
        response = self.client.get(SEO_URL.format(slug="nope"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "Post not found.")


# ============================================================
# /sitemap.xml
# ============================================================
@override_settings(FRONTEND_URL="https://example.test", SITE_NAME="Test Archive")
class SitemapTests(SEOTestBase):
    def urls(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        root = ET.fromstring(response.content)
        return [
            element.find("sm:loc", NS).text for element in root.findall("sm:url", NS)
        ]

    def test_content_type_and_valid_xml(self):
        response = self.client.get("/sitemap.xml")
        self.assertIn("application/xml", response["Content-Type"])
        self.assertEqual(ET.fromstring(response.content).tag, "{%s}urlset" % NS["sm"])

    def test_always_lists_the_home_page(self):
        self.assertEqual(self.urls(), ["https://example.test/"])

    def test_lists_published_posts(self):
        post = self.post()
        self.assertIn(f"https://example.test/posts/{post.slug}", self.urls())

    def test_each_post_has_a_last_modified_date(self):
        self.post()
        root = ET.fromstring(self.client.get("/sitemap.xml").content)
        entries = root.findall("sm:url", NS)
        self.assertIsNotNone(entries[1].find("sm:lastmod", NS))

    def test_excludes_everything_not_public(self):
        self.post("Draft", status=Post.Status.DRAFT)
        self.post("Review", status=Post.Status.UNDER_REVIEW)
        self.post("Archived", status=Post.Status.ARCHIVED)
        self.post("Private", visibility=Post.Visibility.PRIVATE)
        self.post("Later", published_at=timezone.now() + timedelta(days=2))
        self.assertEqual(self.urls(), ["https://example.test/"])

    def test_uses_the_canonical_address_when_set(self):
        self.post(canonical_url="https://original.test/story")
        self.assertIn("https://original.test/story", self.urls())

    @override_settings(FRONTEND_POST_PATH="/blog/{slug}")
    def test_follows_the_post_path_setting(self):
        post = self.post()
        self.assertIn(f"https://example.test/blog/{post.slug}", self.urls())

    def test_needs_no_login(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/sitemap.xml").status_code, status.HTTP_200_OK)


# ============================================================
# /rss.xml
# ============================================================
@override_settings(FRONTEND_URL="https://example.test", SITE_NAME="Test Archive")
class RSSTests(SEOTestBase):
    def feed(self):
        response = self.client.get("/rss.xml")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return ET.fromstring(response.content)

    def items(self):
        return self.feed().findall("channel/item")

    def test_content_type_and_structure(self):
        response = self.client.get("/rss.xml")
        self.assertIn("application/rss+xml", response["Content-Type"])
        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, "rss")
        self.assertEqual(root.get("version"), "2.0")
        self.assertEqual(root.find("channel/title").text, "Test Archive")
        self.assertEqual(root.find("channel/link").text, "https://example.test/")

    def test_empty_feed_is_valid(self):
        self.assertEqual(self.items(), [])

    def test_item_fields(self):
        category = Category.objects.create(name="Tech", slug="tech")
        post = self.post("First Post", excerpt="Summary here.")
        post.category = category
        post.save()
        item = self.items()[0]
        link = f"https://example.test/posts/{post.slug}"
        self.assertEqual(item.find("title").text, "First Post")
        self.assertEqual(item.find("link").text, link)
        self.assertEqual(item.find("guid").text, link)
        self.assertEqual(item.find("guid").get("isPermaLink"), "true")
        self.assertEqual(item.find("description").text, "Summary here.")
        self.assertEqual(item.find("dc:creator", NS).text, "Ada Obi")
        self.assertEqual(item.find("category").text, "Tech")
        self.assertTrue(item.find("pubDate").text.endswith("+0000"))

    def test_newest_first(self):
        self.post("Old", published_at=timezone.now() - timedelta(days=5))
        self.post("New", published_at=timezone.now() - timedelta(hours=1))
        titles = [item.find("title").text for item in self.items()]
        self.assertEqual(titles, ["New", "Old"])

    def test_limited_to_twenty_items(self):
        for number in range(25):
            self.post(f"Post {number}")
        self.assertEqual(len(self.items()), 20)

    def test_excludes_everything_not_public(self):
        self.post("Draft", status=Post.Status.DRAFT)
        self.post("Private", visibility=Post.Visibility.PRIVATE)
        self.post("Later", published_at=timezone.now() + timedelta(days=2))
        self.assertEqual(self.items(), [])

    def test_special_characters_are_escaped(self):
        self.post("Q&A: <b>Tips</b> & \"tricks\"")
        self.assertEqual(self.items()[0].find("title").text, "Q&A: <b>Tips</b> & \"tricks\"")

    def test_tags_become_categories(self):
        post = self.post()
        post.tags.add(Tag.objects.create(name="python", slug="python"))
        names = [c.text for c in self.items()[0].findall("category")]
        self.assertIn("python", names)

    def test_seo_title_is_used_when_written(self):
        self.post("Plain", seo_title="Search friendly")
        self.assertEqual(self.items()[0].find("title").text, "Search friendly")