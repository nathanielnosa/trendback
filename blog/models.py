from django.db import models
from django.conf import settings
from django.utils.text import slugify
import uuid


# ::: CATEGORY
class Category(models.Model):

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name = models.CharField(max_length=100,unique=True)
    slug = models.SlugField(max_length=120,unique=True,db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name
    
# ::: TAGS
class Tag(models.Model):

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name = models.CharField(max_length=100,unique=True)
    slug = models.SlugField(max_length=120,unique=True,db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name

# ::: POSTS
class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255,unique=True,blank=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    featured_image = models.URLField(blank=True,null=True)

    author = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="posts")
    category = models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True,related_name="posts")
    tags = models.ManyToManyField(Tag,blank=True,related_name="posts")

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    visibility = models.CharField(max_length=20,choices=Visibility.choices,default=Visibility.PUBLIC)
    published_at = models.DateTimeField(null=True,blank=True)
    scheduled_at = models.DateTimeField(null=True,blank=True)

    reviewed_at = models.DateTimeField(null=True,blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="reviewed_posts")
    review_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    reading_time = models.PositiveIntegerField(default=0,help_text="Estimated reading time in minutes.")

    seo_title = models.CharField(max_length=255,blank=True)
    seo_description = models.TextField(blank=True)
    canonical_url = models.URLField(blank=True,null=True)

    is_featured = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    
    class Meta:
        ordering = ["-created_at"]

        indexes = [
        models.Index(fields=["status"]),
        models.Index(fields=["visibility"]),
        models.Index(fields=["status", "visibility"]),
        models.Index(fields=["published_at"]),
        ]

    def __str__(self):
        return self.title
    # slug auto
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def is_published(self):
        return self.status == self.Status.PUBLISHED

    def is_draft(self):
        return self.status == self.Status.DRAFT

    def is_archived(self):
        return self.status == self.Status.ARCHIVED

    def is_public(self):
        return (
            self.status == self.Status.PUBLISHED
            and self.visibility == self.Visibility.PUBLIC
        )