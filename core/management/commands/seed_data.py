"""
Fill the database with realistic demo data so the frontend has something to show.

    python manage.py seed_data              # create demo data (skips if it exists)
    python manage.py seed_data --reset      # delete earlier demo data, then recreate
    python manage.py seed_data --clear      # delete demo data and stop

Everything it creates belongs to users with an @seed.example.com email,
so real data is never touched. It refuses to run when DEBUG is False.
"""
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User
from analytics.models import AnalyticsEvent
from analytics.services import record_event
from blog.models import Category, Post, Tag
from comments.models import Comment
from engagements.models import Bookmark, Follow, Reaction, Share
from notifications.models import Notification
from notifications.services import (
    notify_bookmark,
    notify_comment_approved,
    notify_follow,
    notify_post_published,
    notify_reaction,
)

SEED_DOMAIN = "seed.example.com"
PASSWORD = "SeedPass123!"

CATEGORIES = [
    ("Technology", "Software, gadgets and the web."),
    ("Lifestyle", "Everyday life, habits and wellbeing."),
    ("Business", "Startups, money and careers."),
    ("Travel", "Places worth the trip."),
]

TAGS = ["python", "django", "react", "productivity", "remote-work", "startups", "design", "health"]

STAFF = [
    # username, first, last, role
    ("seed_admin", "Ada", "Admin", User.Role.ADMIN),
    ("seed_editor", "Emeka", "Editor", User.Role.EDITOR),
    ("seed_author1", "Amara", "Okafor", User.Role.AUTHOR),
    ("seed_author2", "Tunde", "Bakare", User.Role.AUTHOR),
    ("seed_contributor", "Chidi", "Contributor", User.Role.CONTRIBUTOR),
]

READERS = [
    ("seed_reader1", "Sade", "Reader"),
    ("seed_reader2", "Kemi", "Reader"),
    ("seed_reader3", "Ife", "Reader"),
    ("seed_reader4", "Bola", "Reader"),
]

PUBLISHED_TITLES = [
    "Getting started with Django REST Framework",
    "Ten habits of productive remote teams",
    "Why every small business needs a blog",
    "A weekend in Lagos: where to eat and what to see",
    "Testing your API before the frontend exists",
    "Designing a calm reading experience",
    "From side project to first customers",
    "Sleep, focus and the myth of the hustle",
    "Understanding JWT authentication",
    "Building a design system that lasts",
    "A beginner's guide to React hooks",
    "Budget travel across West Africa",
]

PARAGRAPHS = [
    "Good software starts with small, boring decisions made consistently. "
    "The teams that ship well are rarely the ones with the cleverest ideas.",
    "Write down what you expect to happen before you run the code. "
    "When reality disagrees, you have found something worth understanding.",
    "Readers decide in seconds whether a page is for them. "
    "A clear headline and an honest first paragraph do most of the work.",
    "Progress feels slow until you look back. Keep a short log of what you finished each week.",
    "Constraints are a gift. A fixed deadline, a small budget or a single screen size "
    "forces the choices that make a product feel focused.",
]

COMMENTS = [
    "Really useful, thanks for writing this.",
    "I disagree with the second point, but the rest is spot on.",
    "Bookmarked for later. Do you have a follow-up planned?",
    "This cleared up something I have been stuck on all week.",
    "Great read. The examples made it easy to follow.",
]


def seed_email(username):
    return f"{username}@{SEED_DOMAIN}"


class Command(BaseCommand):
    help = "Create demo users, posts, comments, engagements and notifications."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete earlier demo data first.")
        parser.add_argument("--clear", action="store_true", help="Delete demo data and stop.")
        parser.add_argument("--force", action="store_true", help="Allow running when DEBUG is False.")

    # ------------------------------------------------------------
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Refusing to seed data while DEBUG is False. Use --force to override.")

        random.seed(42)  # the same data every run

        if options["reset"] or options["clear"]:
            self.clear()
            if options["clear"]:
                return

        if User.objects.filter(email__endswith=f"@{SEED_DOMAIN}").exists():
            self.stdout.write(self.style.WARNING("Demo data already exists. Use --reset to recreate it."))
            return

        with transaction.atomic():
            users = self.make_users()
            categories, tags = self.make_taxonomy()
            published = self.make_posts(users, categories, tags)
            self.make_follows(users)
            self.make_comments(users, published)
            self.make_engagements(users, published)
            self.make_views(users, published)

        self.summary()

    # ------------------------------------------------------------
    def clear(self):
        seed_users = User.objects.filter(email__endswith=f"@{SEED_DOMAIN}")
        Post.objects.filter(author__in=seed_users).delete()  # cascades comments and engagements
        Notification.objects.filter(recipient__in=seed_users).delete()
        AnalyticsEvent.objects.filter(actor__in=seed_users).delete()
        AnalyticsEvent.objects.filter(post__isnull=True, actor__isnull=True, source="seed").delete()
        count = seed_users.count()
        seed_users.delete()
        Category.objects.filter(posts__isnull=True, description__startswith="[seed]").delete()
        self.stdout.write(f"Removed demo data ({count} users).")

    # ------------------------------------------------------------
    def make_users(self):
        users = {}
        for username, first, last, role in STAFF:
            users[username] = User.objects.create_user(
                email=seed_email(username), username=username,
                first_name=first, last_name=last,
                password=PASSWORD, role=role, is_verified=True,
            )
        for username, first, last in READERS:
            users[username] = User.objects.create_user(
                email=seed_email(username), username=username,
                first_name=first, last_name=last,
                password=PASSWORD, role=User.Role.SUBSCRIBER, is_verified=True,
            )
        # one account that has not verified its email, for testing that flow
        users["seed_unverified"] = User.objects.create_user(
            email=seed_email("seed_unverified"), username="seed_unverified",
            first_name="Una", last_name="Unverified",
            password=PASSWORD, role=User.Role.SUBSCRIBER, is_verified=False,
        )
        return users

    def get_or_make(self, model, name, **extra):
        """Reuse an existing row with the same slug or name (any capitalisation)."""
        slug = slugify(name)
        existing = (
            model.objects.filter(slug=slug).first()
            or model.objects.filter(name__iexact=name).first()
        )
        if existing:
            return existing
        return model.objects.create(name=name, slug=slug, **extra)

    def make_taxonomy(self):
        categories = [
            self.get_or_make(Category, name, description=f"[seed] {desc}")
            for name, desc in CATEGORIES
        ]
        tags = [self.get_or_make(Tag, name) for name in TAGS]
        return categories, tags

    # ------------------------------------------------------------
    def body(self):
        return "\n\n".join(random.sample(PARAGRAPHS, 4))

    def make_post(self, author, title, state, categories, tags, **extra):
        content = self.body()
        post = Post.objects.create(
            author=author,
            title=title,
            excerpt=content[:140].rsplit(" ", 1)[0] + "...",
            content=content,
            category=random.choice(categories),
            status=state,
            reading_time=max(1, len(content.split()) // 200),
            **extra,
        )
        post.tags.set(random.sample(tags, 2))
        return post

    def make_posts(self, users, categories, tags):
        authors = [users["seed_author1"], users["seed_author2"], users["seed_editor"]]
        now = timezone.now()
        published = []

        for index, title in enumerate(PUBLISHED_TITLES):
            author = authors[index % len(authors)]
            when = now - timedelta(days=index * 2 + 1)
            post = self.make_post(
                author, title, Post.Status.PUBLISHED, categories, tags,
                published_at=when, is_featured=index < 2,
                reviewed_by=users["seed_editor"], reviewed_at=when,
            )
            Post.objects.filter(pk=post.pk).update(created_at=when - timedelta(days=1))
            published.append(post)

        # posts in every other state, so every dashboard screen has content
        author = users["seed_author1"]
        self.make_post(author, "Draft: notes on caching", Post.Status.DRAFT, categories, tags)
        self.make_post(author, "Draft: my 2027 reading list", Post.Status.DRAFT, categories, tags)
        self.make_post(users["seed_author2"], "Waiting for review: API versioning",
                       Post.Status.UNDER_REVIEW, categories, tags)
        self.make_post(users["seed_contributor"], "Waiting for review: first guest post",
                       Post.Status.UNDER_REVIEW, categories, tags)
        self.make_post(author, "Approved: launch checklist", Post.Status.APPROVED, categories, tags,
                       reviewed_by=users["seed_editor"], reviewed_at=now,
                       review_notes="Ready to publish.")
        rejected = self.make_post(
            users["seed_author2"], "Rejected: untitled thoughts", Post.Status.DRAFT, categories, tags,
            reviewed_by=users["seed_editor"], reviewed_at=now,
            review_notes="Please add sources and a clearer introduction.",
        )
        self.make_post(author, "Private: team handbook", Post.Status.PUBLISHED, categories, tags,
                       visibility=Post.Visibility.PRIVATE, published_at=now)
        self.make_post(author, "Archived: old announcement", Post.Status.ARCHIVED, categories, tags)
        self.make_post(author, "Scheduled: next month's recap", Post.Status.APPROVED, categories, tags,
                       scheduled_at=now + timedelta(days=30))
        return published

    # ------------------------------------------------------------
    def make_follows(self, users):
        followed = [users["seed_author1"], users["seed_author2"], users["seed_editor"]]
        readers = [users[name] for name, _, _ in READERS]
        for reader in readers:
            for target in random.sample(followed, 2):
                notify_follow(Follow.objects.create(follower=reader, following=target))

    def make_comments(self, users, published):
        readers = [users[name] for name, _, _ in READERS]
        for post in published[:8]:
            for reader in random.sample(readers, 2):
                comment = Comment.objects.create(
                    post=post, author=reader, content=random.choice(COMMENTS),
                    status=Comment.Status.APPROVED,
                )
                notify_comment_approved(comment)
                record_event(event_type=AnalyticsEvent.EventType.COMMENT, actor=reader, post=post, source="seed")

            # one threaded reply
            parent = post.comments.first()
            reply = Comment.objects.create(
                post=post, author=users["seed_author1"], parent=parent,
                content="Thanks for reading, glad it helped!", status=Comment.Status.APPROVED,
            )
            notify_comment_approved(reply)

        # pending comments, so the moderation queue has items
        for post in published[:3]:
            Comment.objects.create(
                post=post, author=random.choice(readers),
                content="Is this still accurate for the latest version?", status=Comment.Status.PENDING,
            )

    def make_engagements(self, users, published):
        readers = [users[name] for name, _, _ in READERS]
        reaction_types = Reaction.ReactionType.values
        platforms = Share.Platform.values

        for post in published:
            for reader in random.sample(readers, random.randint(1, len(readers))):
                reaction = Reaction.objects.create(
                    user=reader, post=post, reaction_type=random.choice(reaction_types)
                )
                notify_reaction(reaction)
                record_event(event_type=AnalyticsEvent.EventType.REACTION, actor=reader, post=post, source="seed")

            for reader in random.sample(readers, random.randint(0, 2)):
                notify_bookmark(Bookmark.objects.create(user=reader, post=post))
                record_event(event_type=AnalyticsEvent.EventType.BOOKMARK, actor=reader, post=post, source="seed")

            for reader in random.sample(readers, random.randint(0, 2)):
                Share.objects.create(user=reader, post=post, platform=random.choice(platforms))
                record_event(event_type=AnalyticsEvent.EventType.SHARE, actor=reader, post=post, source="seed")

            notify_post_published(post, actor=users["seed_editor"])
            record_event(event_type=AnalyticsEvent.EventType.POST_PUBLISHED, actor=users["seed_editor"],
                         post=post, source="seed")

    def make_views(self, users, published):
        """Spread page views over the last two weeks so the traffic chart has a shape."""
        now = timezone.now()
        for post in published:
            popularity = random.randint(3, 40)
            for _ in range(popularity):
                event = record_event(
                    event_type=AnalyticsEvent.EventType.POST_VIEW,
                    post=post, visitor_id=f"visitor-{random.randint(1, 60)}", source="seed",
                )
                AnalyticsEvent.objects.filter(pk=event.pk).update(
                    occurred_at=now - timedelta(days=random.randint(0, 13), hours=random.randint(0, 23))
                )
            Post.objects.filter(pk=post.pk).update(views=popularity)

    # ------------------------------------------------------------
    def summary(self):
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(f"  Users:         {User.objects.filter(email__endswith='@' + SEED_DOMAIN).count()}")
        self.stdout.write(f"  Posts:         {Post.objects.filter(author__email__endswith='@' + SEED_DOMAIN).count()}")
        self.stdout.write(f"  Comments:      {Comment.objects.filter(post__author__email__endswith='@' + SEED_DOMAIN).count()}")
        self.stdout.write(f"  Notifications: {Notification.objects.filter(recipient__email__endswith='@' + SEED_DOMAIN).count()}")
        self.stdout.write("")
        self.stdout.write(f"Every demo account uses the password: {PASSWORD}")
        self.stdout.write("  Admin:        " + seed_email("seed_admin"))
        self.stdout.write("  Editor:       " + seed_email("seed_editor"))
        self.stdout.write("  Author:       " + seed_email("seed_author1"))
        self.stdout.write("  Contributor:  " + seed_email("seed_contributor"))
        self.stdout.write("  Reader:       " + seed_email("seed_reader1"))
        self.stdout.write("  Unverified:   " + seed_email("seed_unverified"))