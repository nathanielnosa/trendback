"""Builds SEO, OpenGraph, Twitter and JSON-LD data for a post.

Everything here is computed from fields the post already has, so the
frontend only has to render the result into <head>.
"""
import re

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from .models import Post

DESCRIPTION_LENGTH = 160


def site_name():
    return getattr(settings, "SITE_NAME", "Trending Archive")


def frontend_base():
    return settings.FRONTEND_URL.rstrip("/")


def post_url(post):
    """Public address of the post on the frontend. Set FRONTEND_POST_PATH to match its route."""
    path = getattr(settings, "FRONTEND_POST_PATH", "/posts/{slug}").format(slug=post.slug)
    return f"{frontend_base()}{path}"


def plain_text(text):
    return re.sub(r"\s+", " ", strip_tags(text or "")).strip()


def public_posts():
    """Posts anyone may see: published, public, and not scheduled for later."""
    return Post.objects.filter(
        status=Post.Status.PUBLISHED,
        visibility=Post.Visibility.PUBLIC,
        published_at__isnull=False,
        published_at__lte=timezone.now(),
    )


def author_name(post):
    author = post.author
    full = f"{getattr(author, 'first_name', '')} {getattr(author, 'last_name', '')}".strip()
    return full or author.username


def post_description(post):
    written = (post.seo_description or "").strip()
    if written:
        return written
    fallback = plain_text(post.excerpt) or plain_text(post.content)
    return Truncator(fallback).chars(DESCRIPTION_LENGTH)


def build_seo(post):
    title = (post.seo_title or "").strip() or post.title
    description = post_description(post)
    url = (post.canonical_url or "").strip() or post_url(post)
    image = (post.featured_image or "").strip() or None
    published = post.published_at.isoformat() if post.published_at else None
    modified = post.updated_at.isoformat()
    author = author_name(post)
    category = post.category.name if post.category else None
    tags = [tag.name for tag in post.tags.all()]

    return {
        "title": title,
        "description": description,
        "canonical_url": url,
        "image": image,
        "robots": "index, follow" if post.is_public() else "noindex, nofollow",
        "open_graph": {
            "type": "article",
            "site_name": site_name(),
            "title": title,
            "description": description,
            "url": url,
            "image": image,
            "published_time": published,
            "modified_time": modified,
            "author": author,
            "section": category,
            "tags": tags,
        },
        "twitter": {
            "card": "summary_large_image" if image else "summary",
            "title": title,
            "description": description,
            "image": image,
        },
        "json_ld": {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "image": [image] if image else [],
            "datePublished": published,
            "dateModified": modified,
            "author": {"@type": "Person", "name": author},
            "publisher": {"@type": "Organization", "name": site_name()},
            "mainEntityOfPage": url,
        },
    }