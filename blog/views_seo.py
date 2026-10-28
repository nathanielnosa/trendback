import xml.etree.ElementTree as ET
from email.utils import format_datetime

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .seo import build_seo, frontend_base, post_description, post_url, public_posts, site_name

SITEMAP_LIMIT = 50000  # the maximum the sitemap format allows in one file
RSS_LIMIT = 20

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
DC_NS = "http://purl.org/dc/elements/1.1/"
ET.register_namespace("dc", DC_NS)


def xml_response(root, content_type):
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return HttpResponse(body, content_type=f"{content_type}; charset=utf-8")


class PostSEOView(APIView):
    """GET /api/v1/seo/posts/<slug>/: everything the frontend needs for <head>."""

    permission_classes = [AllowAny]

    def get(self, request, slug, *args, **kwargs):
        post = (
            public_posts()
            .select_related("author", "category")
            .prefetch_related("tags")
            .filter(slug=slug)
            .first()
        )
        if post is None:
            return Response({"message": "Post not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(build_seo(post))


def sitemap_xml(request):
    """Every public post, plus the home page."""
    root = ET.Element("urlset", xmlns=SITEMAP_NS)

    home = ET.SubElement(root, "url")
    ET.SubElement(home, "loc").text = f"{frontend_base()}/"

    for post in public_posts().order_by("-published_at")[: SITEMAP_LIMIT - 1]:
        entry = ET.SubElement(root, "url")
        ET.SubElement(entry, "loc").text = (post.canonical_url or "").strip() or post_url(post)
        ET.SubElement(entry, "lastmod").text = post.updated_at.isoformat()

    return xml_response(root, "application/xml")


def rss_feed(request):
    """RSS 2.0 feed of the newest public posts."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = site_name()
    ET.SubElement(channel, "link").text = f"{frontend_base()}/"
    ET.SubElement(channel, "description").text = f"Latest posts from {site_name()}"

    posts = (
        public_posts()
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-published_at")[:RSS_LIMIT]
    )
    for post in posts:
        link = (post.canonical_url or "").strip() or post_url(post)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = (post.seo_title or "").strip() or post.title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link
        ET.SubElement(item, "description").text = post_description(post)
        ET.SubElement(item, "pubDate").text = format_datetime(post.published_at)
        ET.SubElement(item, f"{{{DC_NS}}}creator").text = (
            f"{post.author.first_name} {post.author.last_name}".strip() or post.author.username
        )
        if post.category:
            ET.SubElement(item, "category").text = post.category.name
        for tag in post.tags.all():
            ET.SubElement(item, "category").text = tag.name

    return xml_response(rss, "application/rss+xml")