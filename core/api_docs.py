"""
API documentation details for /api/docs/.

Your views build their responses by hand, so drf-spectacular cannot see what
they accept or return. This file describes that, endpoint by endpoint, WITHOUT
touching the views themselves: each block below targets one view class by its
import path and attaches request, response and query-parameter details to it.

It is imported once from CoreConfig.ready() (core/apps.py).
To document another view, add one `document(...)` block at the bottom.
"""
from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

AUTH = ["Auth"]
POSTS = ["Posts"]
COMMENTS = ["Comments"]
NOTIFICATIONS = ["Notifications"]


# ============================================================
# BUILDING BLOCKS
# ============================================================
_CACHE = {}


def inline(name, make_fields):
    """Build an inline serializer once, so the schema never gets duplicate names."""
    if name not in _CACHE:
        _CACHE[name] = inline_serializer(name=name, fields=make_fields())
    return _CACHE[name]


def message():
    return inline("Message", lambda: {"message": serializers.CharField()})


def error():
    """The shape produced by core.exceptions.custom_exception_handler."""
    return inline(
        "ErrorResponse",
        lambda: {
            "success": serializers.BooleanField(),
            "message": serializers.CharField(),
            "errors": serializers.JSONField(allow_null=True),
        },
    )


def page_of(name, item_serializer):
    """The count / next / previous / results envelope used by paginated lists."""
    return inline(
        name,
        lambda: {
            "count": serializers.IntegerField(),
            "next": serializers.URLField(allow_null=True),
            "previous": serializers.URLField(allow_null=True),
            "results": item_serializer(many=True),
        },
    )


def user_summary(name):
    return inline(
        name,
        lambda: {
            "id": serializers.IntegerField(),
            "email": serializers.EmailField(),
            "username": serializers.CharField(),
            "first_name": serializers.CharField(),
            "last_name": serializers.CharField(),
        },
    )


FIELD_ERRORS = OpenApiResponse(
    description=(
        'Validation failed. `errors` holds the messages keyed by field name, '
        'for example {"email": ["This field is required."]}.'
    )
)


def msg(description):
    return OpenApiResponse(response=message(), description=description)


def unauthorized():
    return OpenApiResponse(response=error(), description="Missing or invalid access token.")


def forbidden():
    return OpenApiResponse(response=error(), description="Your role is not allowed to do this.")


PAGE = [
    OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Page number, starting at 1."),
    OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Items per page (maximum varies by endpoint)."),
]


def _use_standard_errors(responses):
    """
    Every error (status 400 and up) reaches the client as
    {"success": false, "message": "...", "errors": ...} because
    core.renderers.StandardJSONRenderer reshapes it, so document it that way.
    """
    for code, response in list((responses or {}).items()):
        if not (isinstance(code, int) and code >= 400):
            continue
        if isinstance(response, OpenApiResponse) and response.response in (None, message()):
            responses[code] = OpenApiResponse(response=error(), description=response.description)


def _noop():
    def handler(self, request, *args, **kwargs):
        pass  # never called: only used to carry the schema details

    return handler


def document(target, build):
    """
    Attach documentation to the view class at `target` ("app.module.ClassName").

    `build` is a function returning {"get": {...}, "post": {...}} where each
    value holds the keyword arguments for drf-spectacular's @extend_schema.
    It runs lazily, when the schema is generated, so models are already loaded.
    """

    class Docs(OpenApiViewExtension):
        target_class = target

        def view_replacement(self):
            methods = build()
            for details in methods.values():
                _use_standard_errors(details.get("responses"))
            namespace = {
                method: extend_schema(**details)(_noop())
                for method, details in methods.items()
            }
            base = self.target_class
            return type(base.__name__, (base,), namespace)

    return Docs


# ============================================================
# AUTH
# ============================================================
def _register():
    from accounts.serializers import RegisterSerializer

    return {
        "post": dict(
            tags=AUTH,
            summary="Create an account",
            description="Creates an unverified Subscriber account and emails a verification link.",
            request=RegisterSerializer,
            responses={
                201: inline(
                    "RegisterResponse",
                    lambda: {"message": serializers.CharField(), "user": user_summary("RegisteredUser")},
                ),
                400: FIELD_ERRORS,
            },
        )
    }


def _verify_email():
    return {
        "post": dict(
            tags=AUTH,
            summary="Verify an email address",
            request=inline("VerifyEmailBody", lambda: {"token": serializers.CharField()}),
            responses={200: msg("Email verified."), 400: msg("Token missing, invalid, used or expired.")},
        )
    }


def _resend_verification():
    return {
        "post": dict(
            tags=AUTH,
            summary="Resend the verification email",
            description="Always answers the same way, so it cannot be used to discover which emails are registered.",
            request=inline("EmailBody", lambda: {"email": serializers.EmailField()}),
            responses={200: msg("Email sent if the account exists."), 400: msg("Email missing.")},
        )
    }


def _login():
    from accounts.serializers import LoginSerializer

    return {
        "post": dict(
            tags=AUTH,
            summary="Log in",
            description="Returns an access token (send it as `Authorization: Bearer <token>`) and a refresh token.",
            request=LoginSerializer,
            responses={
                200: inline(
                    "LoginResponse",
                    lambda: {
                        "message": serializers.CharField(),
                        "tokens": inline(
                            "TokenPair",
                            lambda: {"access": serializers.CharField(), "refresh": serializers.CharField()},
                        ),
                        "user": inline(
                            "LoginUser",
                            lambda: {
                                "id": serializers.IntegerField(),
                                "email": serializers.EmailField(),
                                "username": serializers.CharField(),
                                "first_name": serializers.CharField(),
                                "last_name": serializers.CharField(),
                                "role": serializers.CharField(),
                                "is_verified": serializers.BooleanField(),
                            },
                        ),
                    },
                ),
                400: FIELD_ERRORS,
                401: msg("Wrong email or password."),
                403: msg("Account deactivated, or email not verified yet."),
            },
        )
    }


def _forgot_password():
    return {
        "post": dict(
            tags=AUTH,
            summary="Request a password reset email",
            request=inline("EmailBody", lambda: {"email": serializers.EmailField()}),
            responses={200: msg("Email sent if the account exists."), 400: msg("Email missing.")},
        )
    }


def _reset_password():
    from accounts.serializers import ResetPasswordSerializer

    return {
        "post": dict(
            tags=AUTH,
            summary="Set a new password using an emailed token",
            request=ResetPasswordSerializer,
            responses={200: msg("Password reset."), 400: FIELD_ERRORS},
        )
    }


def _refresh():
    return {
        "post": dict(
            tags=AUTH,
            summary="Get a new access token",
            request=inline("RefreshBody", lambda: {"refresh": serializers.CharField()}),
            responses={
                200: inline(
                    "RefreshResponse",
                    lambda: {
                        "message": serializers.CharField(),
                        "tokens": inline(
                            "TokenPair",
                            lambda: {"access": serializers.CharField(), "refresh": serializers.CharField()},
                        ),
                    },
                ),
                400: msg("Refresh token missing."),
                401: msg("Invalid or expired refresh token."),
            },
        )
    }


def _logout():
    return {
        "post": dict(
            tags=AUTH,
            summary="Log out",
            description="Blacklists the refresh token so it can no longer be used.",
            request=inline("RefreshBody", lambda: {"refresh": serializers.CharField()}),
            responses={200: msg("Logged out."), 400: msg("Refresh token missing or invalid."), 401: unauthorized()},
        )
    }


def _me():
    from accounts.serializers import ProfileUpdateSerializer

    me = inline(
        "MeResponse",
        lambda: {
            "id": serializers.IntegerField(),
            "email": serializers.EmailField(),
            "username": serializers.CharField(),
            "first_name": serializers.CharField(),
            "last_name": serializers.CharField(),
            "role": serializers.CharField(),
            "is_verified": serializers.BooleanField(),
            "avatar": serializers.URLField(allow_null=True),
            "bio": serializers.CharField(allow_blank=True),
            "date_joined": serializers.DateTimeField(),
        },
    )
    return {
        "get": dict(
            tags=AUTH,
            summary="Get the logged-in user's profile",
            responses={200: me, 401: unauthorized()},
        ),
        "patch": dict(
            tags=AUTH,
            summary="Update the logged-in user's profile",
            description=(
                "Only username, first_name, last_name, bio and avatar can change. "
                "Send multipart/form-data when uploading an avatar."
            ),
            request={
                "application/json": ProfileUpdateSerializer,
                "multipart/form-data": ProfileUpdateSerializer,
            },
            responses={200: me, 400: FIELD_ERRORS, 401: unauthorized()},
        ),
    }


def _change_password():
    from accounts.serializers import ChangePasswordSerializer

    return {
        "post": dict(
            tags=AUTH,
            summary="Change the logged-in user's password",
            request=ChangePasswordSerializer,
            responses={200: msg("Password changed."), 400: FIELD_ERRORS, 401: unauthorized()},
        )
    }


document("accounts.views.RegisterView", _register)
document("accounts.views.VerifyEmailView", _verify_email)
document("accounts.views.ResendVerificationView", _resend_verification)
document("accounts.views.LoginView", _login)
document("accounts.views.ForgotPasswordView", _forgot_password)
document("accounts.views.ResetPasswordView", _reset_password)
document("accounts.views.RefreshTokenView", _refresh)
document("accounts.views.LogoutView", _logout)
document("accounts.views.MeView", _me)
document("accounts.views.ChangePasswordView", _change_password)


# ============================================================
# POSTS
# ============================================================
def _post_list_create():
    from blog.serializers import PostSerializer

    return {
        "get": dict(
            tags=POSTS,
            summary="List published public posts",
            description="Anyone can call this. Drafts, posts under review and private posts never appear.",
            parameters=[
                OpenApiParameter("category", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Category slug."),
                OpenApiParameter("tag", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Tag slug."),
                OpenApiParameter("author", OpenApiTypes.INT, OpenApiParameter.QUERY, description="Author's user id."),
                OpenApiParameter("featured", OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="Only featured posts."),
                OpenApiParameter("trending", OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="Only trending posts."),
                OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Matches title, excerpt and content."),
                *PAGE,
            ],
            responses={200: page_of("PostPage", PostSerializer)},
        ),
        "post": dict(
            tags=POSTS,
            summary="Create a post",
            description=(
                "Authors, contributors, editors and admins can create posts. "
                "A new post starts as a draft. Only editors and admins may choose another status."
            ),
            request=PostSerializer,
            responses={201: PostSerializer, 400: FIELD_ERRORS, 401: unauthorized(), 403: forbidden()},
        ),
    }


def _post_detail():
    from blog.serializers import PostSerializer

    not_found = msg("Post not found, or not public.")
    return {
        "get": dict(
            tags=POSTS,
            summary="Read one published post",
            description="Also records a page-view analytics event.",
            responses={200: PostSerializer, 404: not_found},
        ),
        "put": dict(
            tags=POSTS,
            summary="Replace a post",
            request=PostSerializer,
            responses={200: PostSerializer, 400: FIELD_ERRORS, 401: unauthorized(), 403: forbidden(), 404: not_found},
        ),
        "patch": dict(
            tags=POSTS,
            summary="Edit part of a post",
            request=PostSerializer,
            responses={200: PostSerializer, 400: FIELD_ERRORS, 401: unauthorized(), 403: forbidden(), 404: not_found},
        ),
        "delete": dict(
            tags=POSTS,
            summary="Delete a post",
            responses={204: None, 401: unauthorized(), 403: forbidden(), 404: not_found},
        ),
    }


def _my_posts():
    from blog.serializers import PostSerializer

    return {
        "get": dict(
            tags=POSTS,
            summary="My posts (author dashboard)",
            description="Every post the logged-in user wrote, in any status, including review notes.",
            parameters=[
                OpenApiParameter(
                    "status", OpenApiTypes.STR, OpenApiParameter.QUERY,
                    enum=["draft", "under_review", "approved", "published", "archived"],
                ),
                OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Matches the title."),
                *PAGE,
            ],
            responses={200: page_of("PostPage", PostSerializer), 400: FIELD_ERRORS, 401: unauthorized(), 403: forbidden()},
        )
    }


def _review_queue():
    from blog.serializers import PostSerializer

    return {
        "get": dict(
            tags=POSTS,
            summary="Review queue (editors and admins)",
            description="Posts waiting for an editor, oldest first.",
            parameters=[
                OpenApiParameter(
                    "status", OpenApiTypes.STR, OpenApiParameter.QUERY,
                    enum=["under_review", "approved"],
                    description="under_review (default) or approved posts waiting to be published.",
                ),
                *PAGE,
            ],
            responses={200: page_of("PostPage", PostSerializer), 400: FIELD_ERRORS, 401: unauthorized(), 403: forbidden()},
        )
    }


def _post_action(summary, request_serializer_name, success_text):
    def build():
        import blog.serializers as blog_serializers

        post_result = inline(
            "PostActionResponse",
            lambda: {"message": serializers.CharField(), "post": blog_serializers.PostSerializer()},
        )
        return {
            "post": dict(
                tags=POSTS,
                summary=summary,
                request=getattr(blog_serializers, request_serializer_name),
                responses={
                    200: OpenApiResponse(response=post_result, description=success_text),
                    400: FIELD_ERRORS,
                    401: unauthorized(),
                    403: forbidden(),
                    404: msg("Post not found."),
                },
            )
        }

    return build


document("blog.views.PostListCreateView", _post_list_create)
document("blog.views.PostDetailView", _post_detail)
document("blog.views_dashboard.MyPostsView", _my_posts)
document("blog.views_dashboard.ReviewQueueView", _review_queue)
document(
    "blog.views.PostSubmitReviewView",
    _post_action("Submit a draft for review", "PostSubmitReviewSerializer", "Post is now under review."),
)
document(
    "blog.views.PostReviewView",
    _post_action("Approve or reject a post (editors and admins)", "PostReviewSerializer", "Post approved, or returned to draft."),
)
document(
    "blog.views.PostPublishView",
    _post_action("Publish or schedule an approved post (editors and admins)", "PostPublishSerializer", "Post published or scheduled."),
)


# ============================================================
# COMMENTS
# ============================================================
def _comment_list_create():
    from comments.serializers import CommentSerializer

    return {
        "get": dict(
            tags=COMMENTS,
            summary="List approved comments",
            description="Only approved comments on published public posts appear. Not paginated.",
            parameters=[
                OpenApiParameter("post", OpenApiTypes.UUID, OpenApiParameter.QUERY, description="Only comments on this post."),
            ],
            responses={200: CommentSerializer(many=True), 400: msg("Invalid post id.")},
        ),
        "post": dict(
            tags=COMMENTS,
            summary="Add a comment or reply",
            description="New comments start as pending and appear publicly once a moderator approves them.",
            request=CommentSerializer,
            responses={201: CommentSerializer, 400: FIELD_ERRORS, 401: unauthorized()},
        ),
    }


def _comment_detail():
    from comments.serializers import CommentSerializer

    return {
        "patch": dict(
            tags=COMMENTS,
            summary="Edit your own comment",
            request=inline("CommentEdit", lambda: {"content": serializers.CharField()}),
            responses={
                200: CommentSerializer, 400: FIELD_ERRORS, 401: unauthorized(),
                403: msg("Not your comment."), 404: msg("Comment not found."),
            },
        ),
        "delete": dict(
            tags=COMMENTS,
            summary="Delete a comment",
            description="Soft delete. Allowed for the comment's author, editors and admins.",
            responses={
                200: msg("Comment deleted."), 401: unauthorized(),
                403: msg("Not allowed."), 404: msg("Comment not found."),
            },
        ),
    }


def _comment_moderate():
    from comments.serializers import CommentModerationSerializer, CommentSerializer

    result = inline(
        "CommentModerationResponse",
        lambda: {"message": serializers.CharField(), "comment": CommentSerializer()},
    )
    return {
        "post": dict(
            tags=COMMENTS,
            summary="Approve or reject a pending comment",
            description="Allowed for admins, editors, and the owner of the post being commented on.",
            request=CommentModerationSerializer,
            responses={
                200: result, 400: FIELD_ERRORS, 401: unauthorized(),
                403: forbidden(), 404: msg("Comment not found."),
            },
        )
    }


def _comment_pending():
    from comments.views_queue import PendingCommentSerializer

    return {
        "get": dict(
            tags=COMMENTS,
            summary="Pending comments (moderation queue)",
            description="Admins and editors see all of them. Authors see only comments on their own posts.",
            parameters=PAGE,
            responses={200: page_of("PendingCommentPage", PendingCommentSerializer), 401: unauthorized(), 403: forbidden()},
        )
    }


document("comments.views.CommentListCreateView", _comment_list_create)
document("comments.views.CommentDetailView", _comment_detail)
document("comments.views.CommentModerationView", _comment_moderate)
document("comments.views_queue.PendingCommentsView", _comment_pending)


# ============================================================
# NOTIFICATIONS
# ============================================================
def _notification_list():
    from notifications.models import Notification
    from notifications.serializers import NotificationSerializer

    return {
        "get": dict(
            tags=NOTIFICATIONS,
            summary="My notifications",
            description="Newest first, 10 per page. `unread_count` always counts every unread notification, whatever the filters.",
            parameters=[
                OpenApiParameter("is_read", OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="true or false."),
                OpenApiParameter(
                    "type", OpenApiTypes.STR, OpenApiParameter.QUERY,
                    enum=list(Notification.NotificationType.values),
                ),
                *PAGE,
            ],
            responses={
                200: inline(
                    "NotificationListResponse",
                    lambda: {
                        "count": serializers.IntegerField(),
                        "next": serializers.URLField(allow_null=True),
                        "previous": serializers.URLField(allow_null=True),
                        "unread_count": serializers.IntegerField(),
                        "notifications": NotificationSerializer(many=True),
                    },
                ),
                401: unauthorized(),
            },
        )
    }


def _notification_detail():
    from notifications.serializers import NotificationSerializer

    return {
        "get": dict(
            tags=NOTIFICATIONS,
            summary="Read one notification",
            description="Does not mark it as read.",
            responses={200: NotificationSerializer, 401: unauthorized(), 404: error()},
        )
    }


def _notification_mark_read():
    from notifications.serializers import NotificationSerializer

    return {
        "patch": dict(
            tags=NOTIFICATIONS,
            summary="Mark one notification as read",
            request=None,
            responses={
                200: inline(
                    "NotificationReadResponse",
                    lambda: {"message": serializers.CharField(), "notification": NotificationSerializer()},
                ),
                401: unauthorized(),
                404: error(),
            },
        )
    }


def _notification_mark_all():
    return {
        "patch": dict(
            tags=NOTIFICATIONS,
            summary="Mark all my notifications as read",
            request=None,
            responses={
                200: inline(
                    "NotificationReadAllResponse",
                    lambda: {"message": serializers.CharField(), "updated_count": serializers.IntegerField()},
                ),
                401: unauthorized(),
            },
        )
    }


def _notification_unread():
    from notifications.serializers import NotificationSerializer

    return {
        "get": dict(
            tags=NOTIFICATIONS,
            summary="My unread notifications",
            description="Not paginated.",
            responses={
                200: inline(
                    "UnreadNotificationsResponse",
                    lambda: {"count": serializers.IntegerField(), "notifications": NotificationSerializer(many=True)},
                ),
                401: unauthorized(),
            },
        )
    }


document("notifications.views.NotificationListView", _notification_list)
document("notifications.views.NotificationDetailView", _notification_detail)
document("notifications.views.NotificationMarkReadView", _notification_mark_read)
document("notifications.views.NotificationMarkAllReadView", _notification_mark_all)
document("notifications.views.UnreadNotificationListView", _notification_unread)