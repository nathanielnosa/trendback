from html import escape

from django.http import Http404, HttpResponse

from .seo import author_name, frontend_base, post_description, post_url, public_posts, site_name



def share_page(request, slug):
    """
    A tiny HTML page for link-preview robots (WhatsApp, X, Facebook, LinkedIn...).
    It carries the title, description and picture of the post. People who land on it
    are sent straight on to the real post page.
    """
    post = (
        public_posts()
        .select_related("author", "category")
        .filter(slug=slug)
        .first()
    )
    if post is None:
        raise Http404("Post not found.")

    title = (post.seo_title or "").strip() or post.title
    description = post_description(post)
    url = (post.canonical_url or "").strip() or post_url(post)
    image = (post.featured_image or "").strip()

    # Each entry is a (property, value) pair; empty values are left out.
    open_graph = [
        ("og:type", "article"),
        ("og:site_name", site_name()),
        ("og:title", title),
        ("og:description", description),
        ("og:url", url),
        ("og:image", image),
        ("article:published_time", post.published_at.isoformat()),
        ("article:author", author_name(post)),
    ]
    twitter = [
        ("twitter:card", "summary_large_image" if image else "summary"),
        ("twitter:title", title),
        ("twitter:description", description),
        ("twitter:image", image),
    ]

    tags = [f'<meta property="{escape(key)}" content="{escape(value)}">' for key, value in open_graph if value]
    tags += [f'<meta name="{escape(key)}" content="{escape(value)}">' for key, value in twitter if value]

    page = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)} | {escape(site_name())}</title>"
        f'<meta name="description" content="{escape(description)}">'
        f'<link rel="canonical" href="{escape(url)}">'
        + "".join(tags)
        + f'<meta http-equiv="refresh" content="0; url={escape(url)}">'
        "</head><body>"
        f'<h1>{escape(title)}</h1><p>{escape(description)}</p>'
        f'<p><a href="{escape(url)}">Read the story</a></p>'
        "</body></html>"
    )
    return HttpResponse(page, content_type="text/html; charset=utf-8")
