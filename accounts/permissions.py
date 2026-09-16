from rest_framework.permissions import BasePermission


# ============================================================
# ROLE-BASED PERMISSIONS
# ============================================================


class IsAdmin(BasePermission):
    """
    Allows access only to administrators.
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "ADMIN"
        )


class IsEditor(BasePermission):
    """
    Allows access to editors and administrators.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
            ]
        )


class IsAuthor(BasePermission):
    """
    Allows access to authors, editors and administrators.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
                "AUTHOR",
            ]
        )


class IsContributor(BasePermission):
    """
    Allows access to contributors.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "CONTRIBUTOR"

        )


class IsSubscriber(BasePermission):
    """
    Allows access to subscribers.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "SUBSCRIBER"
        )


# ============================================================
# POST PERMISSIONS
# ============================================================


class CanCreatePost(BasePermission):
    """
    Allows users who are permitted to create blog posts.

    Allowed:
        - ADMIN
        - EDITOR
        - AUTHOR
        - CONTRIBUTOR

    Not allowed:
        - SUBSCRIBER
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
                "AUTHOR",
                "CONTRIBUTOR",
            ]
        )


class CanEditPost(BasePermission):
    """
    Allows users to edit posts.

    ADMIN:
        Can edit any post.

    EDITOR:
        Can edit any post.

    AUTHOR:
        Can edit their own post.

    CONTRIBUTOR:
        Can edit their own post.

    SUBSCRIBER:
        Cannot edit posts.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
                "AUTHOR",
                "CONTRIBUTOR",
            ]
        )

    def has_object_permission(self, request, view, obj):
        # Admin can edit every post
        if request.user.role == "ADMIN":
            return True

        # Editor can edit every post
        if request.user.role == "EDITOR":
            return True

        # Authors and contributors can only edit
        # posts that belong to them
        return obj.author == request.user


class CanDeletePost(BasePermission):
    """
    Allows users to delete posts.

    ADMIN:
        Can delete any post.

    EDITOR:
        Can delete any post.

    AUTHOR:
        Can delete their own post.

    CONTRIBUTOR:
        Can delete their own post.

    SUBSCRIBER:
        Cannot delete posts.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
                "AUTHOR",
                "CONTRIBUTOR",
            ]
        )

    def has_object_permission(self, request, view, obj):
        # Admin can delete every post
        if request.user.role == "ADMIN":
            return True

        # Editor can delete every post
        if request.user.role == "EDITOR":
            return True

        # Authors and contributors can delete
        # only their own posts
        return obj.author == request.user


class CanPublishPost(BasePermission):
    """
    Allows users to publish posts.

    Only:
        - ADMIN
        - EDITOR

    can publish posts.

    Authors and contributors must submit their
    posts for review.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
            ]
        )


class CanReviewPost(BasePermission):
    """
    Allows users to review posts before publication.

    Only:
        - ADMIN
        - EDITOR

    can review posts.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
            ]
        )


# ============================================================
# USER MANAGEMENT PERMISSIONS
# ============================================================


class CanManageUsers(BasePermission):
    """
    Allows access to user-management features.

    Only ADMIN can:
        - View users
        - Update users
        - Change roles
        - Activate/deactivate users
        - Delete users
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "ADMIN"
        )


# ============================================================
# COMMENT PERMISSIONS
# ============================================================


class CanManageComments(BasePermission):
    """
    Allows users to manage comments.

    ADMIN:
        Full comment management.

    EDITOR:
        Can manage comments.

    AUTHOR:
        Can manage comments related to their own posts.

    CONTRIBUTORS:
        Do not have global comment-management access.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
                "AUTHOR",
            ]
        )

    def has_object_permission(self, request, view, obj):
        # Admin can manage every comment
        if request.user.role == "ADMIN":
            return True

        # Editor can manage every comment
        if request.user.role == "EDITOR":
            return True

        # Author can manage comments
        # belonging to their own post
        if request.user.role == "AUTHOR":
            return obj.post.author == request.user

        return False


# ============================================================
# ANALYTICS PERMISSIONS
# ============================================================


class CanViewAnalytics(BasePermission):
    """
    Allows access to BackBlog analytics.

    Only:
        - ADMIN
        - EDITOR

    can view analytics.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                "ADMIN",
                "EDITOR",
            ]
        )


# ============================================================
# GENERAL AUTHENTICATED USER PERMISSION
# ============================================================


class IsVerifiedUser(BasePermission):
    """
    Allows access only to authenticated users
    whose email has been verified.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_verified
        )
