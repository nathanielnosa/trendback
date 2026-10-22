import uuid
from unittest.mock import patch

from django.urls import reverse, NoReverseMatch
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from analytics.models import AnalyticsEvent
from blog.models import Post

from .models import Reaction, Bookmark, Share, Follow
from .views import (
    PostReactionView,
    PostBookmarkView,
    PostShareView,
    UserFollowView,
)

REACTION = AnalyticsEvent.EventType.REACTION
BOOKMARK = AnalyticsEvent.EventType.BOOKMARK
SHARE = AnalyticsEvent.EventType.SHARE
FOLLOW = AnalyticsEvent.EventType.FOLLOW


# ============================================================
# HELPERS
# ============================================================
def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class EngagementTestBase(APITestCase):
    def make_user(self, role, username):
        return User.objects.create_user(
            email=f"{username}@example.com",
            username=username,
            first_name=username.title(),
            last_name="Tester",
            password="StrongPass123!",
            is_verified=True,
            role=role,
        )

    def make_post(self, title="A post", **kwargs):
        kwargs.setdefault("status", Post.Status.PUBLISHED)
        return Post.objects.create(
            author=self.author, title=title, content="Body", **kwargs
        )

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.contributor = self.make_user(User.Role.CONTRIBUTOR, "contrib1")
        self.reader = self.make_user(User.Role.SUBSCRIBER, "reader1")
        self.other_reader = self.make_user(User.Role.SUBSCRIBER, "reader2")

        self.post = self.make_post()
        self.reaction_url = url("post-reaction", post_id=self.post.id)
        self.bookmark_url = url("post-bookmark", post_id=self.post.id)
        self.share_url = url("post-share", post_id=self.post.id)
        self.follow_author_url = url("user-follow", user_id=self.author.id)

    def login(self, user=None):
        self.client.force_authenticate(user=user or self.reader)

    def events(self, event_type):
        return AnalyticsEvent.objects.filter(event_type=event_type)


# ============================================================
# AUTHENTICATION
# ============================================================
class AuthRequiredTests(EngagementTestBase):
    def test_anonymous_gets_401_everywhere(self):
        targets = [
            ("get", self.reaction_url),
            ("post", self.reaction_url),
            ("delete", self.reaction_url),
            ("get", self.bookmark_url),
            ("post", self.bookmark_url),
            ("delete", self.bookmark_url),
            ("get", url("bookmark-list")),
            ("get", self.share_url),
            ("post", self.share_url),
            ("get", self.follow_author_url),
            ("post", self.follow_author_url),
            ("delete", self.follow_author_url),
            ("get", url("following-list")),
            ("get", url("followers-list")),
        ]
        for method, target in targets:
            with self.subTest(method=method, target=target):
                response = getattr(self.client, method)(target)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# REACTIONS
# ============================================================
class ReactionTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.reader)

    def react(self, value="like"):
        return self.client.post(
            self.reaction_url, {"reaction_type": value}, format="json"
        )

    def test_counts_start_at_zero_for_every_type(self):
        response = self.client.get(self.reaction_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = {value for value, _ in Reaction.ReactionType.choices}
        self.assertEqual(set(response.data["counts"]), expected)
        self.assertTrue(all(v == 0 for v in response.data["counts"].values()))
        self.assertIsNone(response.data["user_reaction"])

    def test_can_react(self):
        response = self.react("like")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reaction = Reaction.objects.get()
        self.assertEqual(reaction.user, self.reader)
        self.assertEqual(reaction.post, self.post)
        self.assertEqual(reaction.reaction_type, "like")

    def test_reaction_type_is_required(self):
        response = self.client.post(self.reaction_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_reaction_type_is_rejected(self):
        response = self.react("angry")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Reaction.objects.count(), 0)

    def test_same_reaction_twice_keeps_one_row(self):
        self.react("like")
        response = self.react("like")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Reaction.objects.count(), 1)

    def test_changing_reaction_updates_the_same_row(self):
        self.react("like")
        response = self.react("love")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Reaction.objects.count(), 1)
        self.assertEqual(Reaction.objects.get().reaction_type, "love")

    def test_counts_and_own_reaction(self):
        self.react("like")
        self.login(self.other_reader)
        self.react("love")

        self.login(self.reader)
        data = self.client.get(self.reaction_url).data

        self.assertEqual(data["counts"]["like"], 1)
        self.assertEqual(data["counts"]["love"], 1)
        self.assertEqual(data["user_reaction"], "like")

    def test_can_remove_reaction(self):
        self.react("like")
        response = self.client.delete(self.reaction_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Reaction.objects.count(), 0)

    def test_removing_missing_reaction_is_404(self):
        response = self.client.delete(self.reaction_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_remove_someone_elses_reaction(self):
        Reaction.objects.create(user=self.other_reader, post=self.post, reaction_type="like")
        response = self.client.delete(self.reaction_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Reaction.objects.count(), 1)

    def test_user_field_in_payload_is_ignored(self):
        self.client.post(
            self.reaction_url,
            {"reaction_type": "like", "user": self.admin.id},
            format="json",
        )
        self.assertEqual(Reaction.objects.get().user, self.reader)

    def test_draft_private_and_unknown_posts_are_404(self):
        draft = self.make_post("Draft", status=Post.Status.DRAFT)
        private = self.make_post("Private", visibility=Post.Visibility.PRIVATE)
        for post_id in (draft.id, private.id, uuid.uuid4()):
            target = url("post-reaction", post_id=post_id)
            for method in ("get", "post", "delete"):
                with self.subTest(post=post_id, method=method):
                    response = getattr(self.client, method)(
                        target, {"reaction_type": "like"}, format="json"
                    )
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_reaction_records_one_analytics_event(self):
        self.react("like")
        event = self.events(REACTION).get()
        self.assertEqual(event.actor, self.reader)
        self.assertEqual(event.post, self.post)
        self.assertEqual(event.metadata, {"reaction_type": "like"})

    def test_changing_reaction_does_not_add_an_event(self):
        self.react("like")
        self.react("love")
        self.assertEqual(self.events(REACTION).count(), 1)


# ============================================================
# BOOKMARKS
# ============================================================
class BookmarkTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.reader)

    def test_not_bookmarked_by_default(self):
        data = self.client.get(self.bookmark_url).data
        self.assertFalse(data["bookmarked"])
        self.assertIsNone(data["bookmark"])

    def test_can_bookmark(self):
        response = self.client.post(self.bookmark_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        bookmark = Bookmark.objects.get()
        self.assertEqual(bookmark.user, self.reader)
        self.assertEqual(bookmark.post, self.post)

    def test_bookmark_shows_as_bookmarked(self):
        self.client.post(self.bookmark_url)
        data = self.client.get(self.bookmark_url).data
        self.assertTrue(data["bookmarked"])
        self.assertIsNotNone(data["bookmark"])

    def test_bookmarking_twice_keeps_one_row(self):
        self.client.post(self.bookmark_url)
        response = self.client.post(self.bookmark_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_can_remove_bookmark(self):
        self.client.post(self.bookmark_url)
        response = self.client.delete(self.bookmark_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_removing_missing_bookmark_is_404(self):
        response = self.client.delete(self.bookmark_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_bookmarks_are_per_user(self):
        Bookmark.objects.create(user=self.other_reader, post=self.post)
        data = self.client.get(self.bookmark_url).data
        self.assertFalse(data["bookmarked"])

    def test_list_shows_only_my_bookmarks(self):
        second = self.make_post("Second")
        Bookmark.objects.create(user=self.reader, post=self.post)
        Bookmark.objects.create(user=self.reader, post=second)
        Bookmark.objects.create(user=self.other_reader, post=self.post)

        data = self.client.get(url("bookmark-list")).data

        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["bookmarks"]), 2)

    def test_list_is_newest_first(self):
        second = self.make_post("Second")
        Bookmark.objects.create(user=self.reader, post=self.post)
        Bookmark.objects.create(user=self.reader, post=second)
        titles = [b["post_title"] for b in self.client.get(url("bookmark-list")).data["bookmarks"]]
        self.assertEqual(titles, ["Second", "A post"])

    def test_draft_private_and_unknown_posts_are_404(self):
        draft = self.make_post("Draft", status=Post.Status.DRAFT)
        private = self.make_post("Private", visibility=Post.Visibility.PRIVATE)
        for post_id in (draft.id, private.id, uuid.uuid4()):
            target = url("post-bookmark", post_id=post_id)
            for method in ("get", "post", "delete"):
                with self.subTest(post=post_id, method=method):
                    response = getattr(self.client, method)(target)
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_bookmark_records_one_event(self):
        self.client.post(self.bookmark_url)
        self.client.post(self.bookmark_url)  # duplicate click
        self.assertEqual(self.events(BOOKMARK).count(), 1)


# ============================================================
# SHARES
# ============================================================
class ShareTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.reader)

    def share(self, platform="whatsapp"):
        return self.client.post(
            self.share_url, {"platform": platform}, format="json"
        )

    def test_can_share(self):
        response = self.share("whatsapp")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        share = Share.objects.get()
        self.assertEqual(share.user, self.reader)
        self.assertEqual(share.post, self.post)
        self.assertEqual(share.platform, "whatsapp")

    def test_platform_is_required(self):
        response = self.client.post(self.share_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_platform_is_rejected(self):
        response = self.share("myspace")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Share.objects.count(), 0)

    def test_counts_by_platform(self):
        self.share("whatsapp")
        self.share("whatsapp")
        self.share("twitter")

        data = self.client.get(self.share_url).data

        self.assertEqual(data["total_shares"], 3)
        self.assertEqual(data["shares_by_platform"]["whatsapp"], 2)
        self.assertEqual(data["shares_by_platform"]["twitter"], 1)
        self.assertEqual(data["shares_by_platform"]["facebook"], 0)
        expected = {value for value, _ in Share.Platform.choices}
        self.assertEqual(set(data["shares_by_platform"]), expected)

    def test_draft_private_and_unknown_posts_are_404(self):
        draft = self.make_post("Draft", status=Post.Status.DRAFT)
        private = self.make_post("Private", visibility=Post.Visibility.PRIVATE)
        for post_id in (draft.id, private.id, uuid.uuid4()):
            target = url("post-share", post_id=post_id)
            for method in ("get", "post"):
                with self.subTest(post=post_id, method=method):
                    response = getattr(self.client, method)(
                        target, {"platform": "whatsapp"}, format="json"
                    )
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_records_event_with_platform(self):
        self.share("telegram")
        event = self.events(SHARE).get()
        self.assertEqual(event.actor, self.reader)
        self.assertEqual(event.post, self.post)
        self.assertEqual(event.metadata, {"platform": "telegram"})


# ============================================================
# FOLLOWS
# ============================================================
class FollowTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.reader)

    def test_status_before_following(self):
        data = self.client.get(self.follow_author_url).data
        self.assertFalse(data["is_following"])
        self.assertEqual(data["followers_count"], 0)
        self.assertEqual(data["following_count"], 0)

    def test_can_follow_an_author(self):
        response = self.client.post(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        follow = Follow.objects.get()
        self.assertEqual(follow.follower, self.reader)
        self.assertEqual(follow.following, self.author)

    def test_can_follow_editors_and_admins(self):
        for target_user in (self.editor, self.admin):
            with self.subTest(role=target_user.role):
                response = self.client.post(url("user-follow", user_id=target_user.id))
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_status_after_following(self):
        self.client.post(self.follow_author_url)
        data = self.client.get(self.follow_author_url).data
        self.assertTrue(data["is_following"])
        self.assertEqual(data["followers_count"], 1)

    def test_cannot_follow_yourself(self):
        self.login(self.author)
        response = self.client.post(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Follow.objects.count(), 0)

    def test_cannot_follow_a_regular_subscriber(self):
        response = self.client.post(url("user-follow", user_id=self.other_reader.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Follow.objects.count(), 0)

    def test_following_twice_keeps_one_row(self):
        self.client.post(self.follow_author_url)
        response = self.client.post(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Follow.objects.count(), 1)

    def test_unknown_user_is_404(self):
        response = self.client.post(url("user-follow", user_id=999999999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_inactive_user_is_404(self):
        self.author.is_active = False
        self.author.save()
        response = self.client.post(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_can_unfollow(self):
        self.client.post(self.follow_author_url)
        response = self.client.delete(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Follow.objects.count(), 0)

    def test_unfollowing_when_not_following_is_404(self):
        response = self.client.delete(self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_following_list_shows_only_my_follows(self):
        Follow.objects.create(follower=self.reader, following=self.author)
        Follow.objects.create(follower=self.other_reader, following=self.editor)

        data = self.client.get(url("following-list")).data

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["following"][0]["following"], self.author.id)

    def test_followers_list_shows_my_followers(self):
        Follow.objects.create(follower=self.reader, following=self.author)
        Follow.objects.create(follower=self.other_reader, following=self.editor)

        self.login(self.author)
        data = self.client.get(url("followers-list")).data

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["followers"][0]["follower"], self.reader.id)

    def test_follow_records_event(self):
        self.client.post(self.follow_author_url)
        self.client.post(self.follow_author_url)  # duplicate click
        event = self.events(FOLLOW).get()
        self.assertEqual(event.actor, self.reader)
        self.assertEqual(event.metadata["followed_user_id"], str(self.author.id))


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(EngagementTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.reader)

    # ----- crashes -----
    def test_non_numeric_user_id_does_not_crash(self):
        self.client.raise_request_exception = False
        response = self.client.get(url("user-follow", user_id="abc"))
        self.assertLess(response.status_code, 500)

    def test_unhashable_reaction_type_does_not_crash(self):
        self.client.raise_request_exception = False
        response = self.client.post(
            self.reaction_url, {"reaction_type": ["like"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ----- toggling must not inflate analytics (and trending) -----
    def test_toggling_a_reaction_records_one_event(self):
        for _ in range(2):
            self.client.post(self.reaction_url, {"reaction_type": "like"}, format="json")
            self.client.delete(self.reaction_url)
        self.client.post(self.reaction_url, {"reaction_type": "like"}, format="json")
        self.assertEqual(self.events(REACTION).count(), 1)

    def test_toggling_a_bookmark_records_one_event(self):
        for _ in range(2):
            self.client.post(self.bookmark_url)
            self.client.delete(self.bookmark_url)
        self.client.post(self.bookmark_url)
        self.assertEqual(self.events(BOOKMARK).count(), 1)

    def test_toggling_a_follow_records_one_event(self):
        for _ in range(2):
            self.client.post(self.follow_author_url)
            self.client.delete(self.follow_author_url)
        self.client.post(self.follow_author_url)
        self.assertEqual(self.events(FOLLOW).count(), 1)

    def test_repeated_shares_by_one_user_record_one_event(self):
        for platform in ("whatsapp", "facebook", "twitter"):
            self.client.post(self.share_url, {"platform": platform}, format="json")
        self.assertEqual(self.events(SHARE).count(), 1)

    # ----- an analytics failure must not break the action -----
    def _with_broken_analytics(self, view_class, target, data=None):
        self.client.raise_request_exception = False
        with patch(f"{view_class.__module__}.record_event", side_effect=Exception("down")):
            return self.client.post(target, data or {}, format="json")

    def test_reaction_survives_analytics_failure(self):
        response = self._with_broken_analytics(
            PostReactionView, self.reaction_url, {"reaction_type": "like"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bookmark_survives_analytics_failure(self):
        response = self._with_broken_analytics(PostBookmarkView, self.bookmark_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_share_survives_analytics_failure(self):
        response = self._with_broken_analytics(
            PostShareView, self.share_url, {"platform": "whatsapp"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_follow_survives_analytics_failure(self):
        response = self._with_broken_analytics(UserFollowView, self.follow_author_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ----- privacy -----
    def test_bookmark_list_hides_posts_that_are_no_longer_public(self):
        Bookmark.objects.create(user=self.reader, post=self.post)
        self.post.visibility = Post.Visibility.PRIVATE
        self.post.save()
        data = self.client.get(url("bookmark-list")).data
        self.assertEqual(data["count"], 0)