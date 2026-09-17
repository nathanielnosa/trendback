from django.contrib import admin

from .models import Category,Tag

# ::: ADMIN CATEGORY
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name","slug","created_at","updated_at")
    search_fields = ("name","slug")
    prepopulated_fields = {"slug": ("name",)}

# ::: ADMIN TAG
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name","slug","created_at","updated_at")
    search_fields = ("name","slug")
    prepopulated_fields = {"slug": ("name",)}