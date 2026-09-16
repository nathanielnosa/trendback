from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin,BaseUserManager
from django.db import models
from django.utils import timezone

import uuid



# user management
class UserManager(BaseUserManager):
    def create_user(self,email,username,first_name,last_name,password=None,**extra_fields):
        if not email:
            raise ValueError("Email address is required")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self,email,username,first_name,last_name,password=None,**extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        return self.create_user(email=email,username=username,first_name=first_name,last_name=last_name,password=password,**extra_fields)

    
# user model
class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        EDITOR = "EDITOR", "Editor"
        AUTHOR = "AUTHOR", "Author"
        CONTRIBUTOR = "CONTRIBUTOR", "Contributor"
        SUBSCRIBER = "SUBSCRIBER", "Subscriber"

    email = models.EmailField(unique=True,db_index=True)
    username = models.CharField(max_length=100,unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    avatar = models.ImageField(upload_to="avatars/",blank=True,null=True)

    bio = models.TextField(blank=True)
    role = models.CharField(max_length=20,choices=Role.choices,default=Role.SUBSCRIBER)

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "username",
        "first_name",
        "last_name",
    ]

    def __str__(self):
        return self.email

class AuthToken(models.Model):

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = ("EMAIL_VERIFICATION","Email Verification")
        PASSWORD_RESET = ("PASSWORD_RESET","Password Reset")

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="auth_tokens")
    token_hash = models.CharField(max_length=128,unique=True,db_index=True)
    purpose = models.CharField(max_length=30,choices=Purpose.choices)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "purpose"]
            ),
            models.Index(
                fields=["expires_at"]
            ),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"