"""
Rate limits for the endpoints people abuse: login and anything that sends email.

Limits live in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], so they can be
changed without touching this file. Counts are kept in the cache (Redis).
A request over the limit gets status 429 and a Retry-After header.
"""
import hashlib
import logging

from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger("backblog.throttles")


class FailOpenMixin:
    """
    If the cache (Redis) cannot be reached, let the request through and log a
    warning. A broken cache must not stop people from logging in.
    """

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning("Rate limit skipped for %s: cache unavailable.", self.scope, exc_info=True)
            return True


class LoginIPThrottle(FailOpenMixin, SimpleRateThrottle):
    """Limits login attempts from one IP address, whatever email is tried."""

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginEmailThrottle(FailOpenMixin, SimpleRateThrottle):
    """Limits login attempts against one email, whatever IP they come from."""

    scope = "login_email"

    def get_cache_key(self, request, view):
        data = request.data
        email = data.get("email") if hasattr(data, "get") else None
        email = str(email or "").strip().lower()
        if not email:
            return None  # nothing to count; the IP limit still applies
        ident = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthEmailThrottle(FailOpenMixin, SimpleRateThrottle):
    """
    Shared limit, per IP address, for the endpoints that send an email:
    register, resend verification and forgot password.
    """

    scope = "auth_email"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}