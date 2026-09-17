from django.urls import path

from .views import *


urlpatterns = [

    path("register/",RegisterView.as_view(),name="register"),
    path("login/",LoginView.as_view(),name="login"),

    path("refresh/",RefreshTokenView.as_view(),name="refresh"),

    path("logout/",LogoutView.as_view(),name="logout"),

    path("me/",MeView.as_view(),name="me"),

    path("change-password/",ChangePasswordView.as_view(),name="change-password"),

    path("verify-email/",VerifyEmailView.as_view(),name="verify-email"),

    path("resend-verification/",ResendVerificationView.as_view(),name="resend-verification"),

    path("forgot-password/",ForgotPasswordView.as_view(),name="forgot-password"),

    path("reset-password/",ResetPasswordView.as_view(),name="reset-password"),

    path("server-error/",ServerErrorTestView.as_view(),name="server-error"),


    # ============================================================
# ROLE & PERMISSION TEST ROUTES
# ============================================================

path(
    "test/admin/",
    AdminPermissionTestView.as_view(),
    name="test-admin-permission",
),

path(
    "test/editor/",
    EditorPermissionTestView.as_view(),
    name="test-editor-permission",
),

path(
    "test/author/",
    AuthorPermissionTestView.as_view(),
    name="test-author-permission",
),

path(
    "test/contributor/",
    ContributorPermissionTestView.as_view(),
    name="test-contributor-permission",
),

path(
    "test/subscriber/",
    SubscriberPermissionTestView.as_view(),
    name="test-subscriber-permission",
),

path(
    "test/create-post/",
    CreatePostPermissionTestView.as_view(),
    name="test-create-post-permission",
),

path(
    "test/publish-post/",
    PublishPostPermissionTestView.as_view(),
    name="test-publish-post-permission",
),

path(
    "test/review-post/",
    ReviewPostPermissionTestView.as_view(),
    name="test-review-post-permission",
),

path(
    "test/manage-users/",
    ManageUsersPermissionTestView.as_view(),
    name="test-manage-users-permission",
),

path(
    "test/analytics/",AnalyticsPermissionTestView.as_view(),
    name="test-analytics-permission",
),
]