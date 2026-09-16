from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    ordering = ("email",)

    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "is_verified",
        "is_active",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_verified",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "email",
        "username",
        "first_name",
        "last_name",
    )

    readonly_fields = (
        "date_joined",
        "updated_at",
        "last_login",
    )

    fieldsets = (
        (None, {
            "fields": (
                "email",
                "password",
            )
        }),

        ("Personal Information", {
            "fields": (
                "username",
                "first_name",
                "last_name",
                "avatar",
                "bio",
            )
        }),

        ("Permissions", {
            "fields": (
                "role",
                "is_verified",
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),

        ("Important Dates", {
            "fields": (
                "last_login",
                "date_joined",
                "updated_at",
            )
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "username",
                "first_name",
                "last_name",
                "password1",
                "password2",
                "role",
            ),
        }),
    )