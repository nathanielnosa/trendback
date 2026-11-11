import re
import secrets

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .models import User


def verify_google_credential(credential):
    """
    Check a Google sign-in token and return the person's details.
    Raises ValueError if the token is fake, expired, made for another app,
    or belongs to an email address Google has not verified.
    """
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not set.")

    # Checks the signature, the expiry time and that the token was made for OUR client id.
    info = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)

    if not info.get("email") or not info.get("email_verified"):
        raise ValueError("The Google email address is not verified.")

    return info


def unique_username(base):
    """Turn the start of an email address into a username nobody else has."""
    cleaned = re.sub(r"[^a-z0-9_]", "", base.lower())[:30] or "reader"
    username = cleaned
    while User.objects.filter(username=username).exists():
        username = f"{cleaned}{secrets.randbelow(9000) + 1000}"
    return username


def get_or_create_google_user(info):
    """
    Find the account for a Google email, or make one.
    Returns (user, created). Google has proven the email is theirs,
    so the account counts as verified.
    """
    email = info["email"].lower()
    user = User.objects.filter(email=email).first()

    if user:
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified", "updated_at"])
        return user, False

    local_part = email.split("@")[0]
    user = User.objects.create_user(
        email=email,
        username=unique_username(local_part),
        first_name=info.get("given_name") or local_part,
        last_name=info.get("family_name") or "",
        is_verified=True,
    )
    return user, True