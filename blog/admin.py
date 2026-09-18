from django.contrib import admin

from .models import Category,Tag,Post

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

# ::: ADMIN POST
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title","author","category","status","visibility","is_featured","is_trending","views","created_at")
    list_filter = ("status","visibility","is_featured","is_trending","allow_comments","category")
    search_fields = ("title","slug","content","excerpt","author__email")
    filter_horizontal = ("tags",)
    readonly_fields = ("views","likes","created_at","updated_at")
    prepopulated_fields = {"slug": ("title",)}