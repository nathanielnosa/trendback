import logging

from .models import Notification

logger = logging.getLogger("backblog")

Types = Notification.NotificationType


def _name(user):
    if user is None:
        return "Someone"
    return user.get_full_name() or user.username


def create_notification(
    *,
    recipient,
    notification_type,
    title,
    message,
    actor=None,
    related_object_id=None,
    related_url="",
    dedupe=False,
):
    """
    Create one notification.

    - Never raises: a notification problem must not break the user's action.
    - Never notifies someone about their own action.
    - With dedupe=True, the same actor cannot create the same notification
      (same type and related object) twice, so toggling a like or follow
      cannot spam the recipient.

    Returns the notification, or None if nothing was created.
    """
    try:
        if recipient is None:
            return None

        if actor is not None and actor.pk == recipient.pk:
            return None

        if notification_type not in Notification.NotificationType.values:
            logger.error("Unknown notification type: %s", notification_type)
            return None

        if related_object_id is not None:
            related_object_id = str(related_object_id)

        if dedupe:
            already_sent = Notification.objects.filter(
                recipient=recipient,
                actor=actor,
                notification_type=notification_type,
                related_object_id=related_object_id,
            ).exists()

            if already_sent:
                return None

        return Notification.objects.create(
            recipient=recipient,
            actor=actor,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_url=related_url,
        )
    except Exception:
        logger.exception("Failed to create notification: %s", notification_type)
        return None


# ==========================
# COMMENTS
# ==========================
def notify_comment_approved(comment):
    """Tell the post author (or the parent comment's author) about a new comment."""
    try:
        post = comment.post
        commenter = comment.author
        url = f"/posts/{post.slug}#comment-{comment.id}"

        if comment.parent_id:
            return create_notification(
                recipient=comment.parent.author,
                actor=commenter,
                notification_type=Types.REPLY,
                title="New reply to your comment",
                message=f'{_name(commenter)} replied to your comment on "{post.title}".',
                related_object_id=comment.id,
                related_url=url,
            )

        return create_notification(
            recipient=post.author,
            actor=commenter,
            notification_type=Types.COMMENT,
            title="New comment on your post",
            message=f'{_name(commenter)} commented on "{post.title}".',
            related_object_id=comment.id,
            related_url=url,
        )
    except Exception:
        logger.exception("Failed to build comment notification.")
        return None


# ==========================
# ENGAGEMENTS
# ==========================
def notify_reaction(reaction):
    try:
        post = reaction.post
        return create_notification(
            recipient=post.author,
            actor=reaction.user,
            notification_type=Types.REACTION,
            title="New reaction on your post",
            message=f'{_name(reaction.user)} reacted to "{post.title}".',
            related_object_id=post.id,
            related_url=f"/posts/{post.slug}",
            dedupe=True,
        )
    except Exception:
        logger.exception("Failed to build reaction notification.")
        return None


def notify_bookmark(bookmark):
    try:
        post = bookmark.post
        return create_notification(
            recipient=post.author,
            actor=bookmark.user,
            notification_type=Types.BOOKMARK,
            title="Your post was bookmarked",
            message=f'{_name(bookmark.user)} bookmarked "{post.title}".',
            related_object_id=post.id,
            related_url=f"/posts/{post.slug}",
            dedupe=True,
        )
    except Exception:
        logger.exception("Failed to build bookmark notification.")
        return None


def notify_follow(follow):
    try:
        follower = follow.follower
        return create_notification(
            recipient=follow.following,
            actor=follower,
            notification_type=Types.FOLLOW,
            title="You have a new follower",
            message=f"{_name(follower)} started following you.",
            related_object_id=follower.id,
            related_url=f"/users/{follower.id}",
            dedupe=True,
        )
    except Exception:
        logger.exception("Failed to build follow notification.")
        return None


# ==========================
# PUBLISHING
# ==========================
def notify_post_published(post, actor=None):
    """
    Tell the author (if someone else published their post) and all the
    author's followers. Returns how many notifications were created.
    """
    created = 0

    try:
        author = post.author
        url = f"/posts/{post.slug}"

        if create_notification(
            recipient=author,
            actor=actor,
            notification_type=Types.PUBLISH,
            title="Your post was published",
            message=f'"{post.title}" is now live.',
            related_object_id=post.id,
            related_url=url,
            dedupe=True,
        ):
            created += 1

        # Imported here to avoid a circular import between the apps.
        from engagements.models import Follow

        already_notified = Notification.objects.filter(
            notification_type=Types.PUBLISH,
            related_object_id=str(post.id),
        ).values("recipient_id")

        follower_ids = (
            Follow.objects
            .filter(following=author)
            .exclude(follower_id__in=already_notified)
            .values_list("follower_id", flat=True)
        )

        notifications = [
            Notification(
                recipient_id=follower_id,
                actor=author,
                notification_type=Types.PUBLISH,
                title=f"New post from {_name(author)}",
                message=f'{_name(author)} published "{post.title}".',
                related_object_id=str(post.id),
                related_url=url,
            )
            for follower_id in follower_ids
        ]

        Notification.objects.bulk_create(notifications, batch_size=500)
        created += len(notifications)
    except Exception:
        logger.exception("Failed to notify followers about a published post.")

    return created