import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from rest_framework_simplejwt.tokens import RefreshToken

from .models import AuthToken,User


# ::: create Auth Tokens For All
def create_auth_tokens(user):
    refresh = RefreshToken.for_user(user)

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

# ::: Hashing Token
def create_secure_token():
    """
    Generate a cryptographically secure random token.
    """

    raw_token = secrets.token_urlsafe(48)

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    return raw_token, token_hash

# ::: create Auth Token
def create_auth_token(user,purpose,expiration_minutes):

    raw_token, token_hash = create_secure_token()

    auth_token = AuthToken.objects.create(
        user=user,
        token_hash=token_hash,
        purpose=purpose,
        expires_at=(
            timezone.now()
            + timedelta(minutes=expiration_minutes)
        )
    )

    return raw_token, auth_token

# ::Get hash TOken
def get_token_hash(raw_token):

    return hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

# ::: Sending Verification Email
def send_verification_email(user,verification_url):

    send_mail(
        subject="Verify your Trending Archive account",

        message=(
            f"Hello {user.first_name},\n\n"
            "Welcome to BackBlog.\n\n"
            "Please verify your email address:\n\n"
            f"{verification_url}\n\n"
            "This link will expire in 60min."
        ),

        from_email=settings.DEFAULT_FROM_EMAIL,

        recipient_list=[
            user.email
        ],

        fail_silently=False,
    )

# ::::: PASSWORD RESET EMAIL
def send_password_reset_email(user,reset_url):

    send_mail(
        subject="Reset your BackBlog password",

        message=(
            f"Hello {user.first_name},\n\n"
            "We received a request to reset your password.\n\n"
            "Reset your password here:\n\n"
            f"{reset_url}\n\n"
            "If you did not request this, ignore this email."
        ),

        from_email=settings.DEFAULT_FROM_EMAIL,

        recipient_list=[
            user.email
        ],

        fail_silently=False,
    )

# ::: ROTATE REFRESH TOKEN
def rotate_refresh_token(refresh_token):
    """
    Validate the old refresh token, blacklist it,
    and issue a new access + refresh token pair.
    """

    old_refresh = RefreshToken(refresh_token)

    user_id = old_refresh["user_id"]

    user = User.objects.get(pk=user_id)

    if not user.is_active:
        raise ValueError("User account is inactive.")

    # Invalidate the old refresh token
    old_refresh.blacklist()

    # Create a new token pair
    new_refresh = RefreshToken.for_user(user)

    return {
        "access": str(new_refresh.access_token),
        "refresh": str(new_refresh),
    }