import logging

from django.conf import settings

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


# Create a logger for unexpected application errors.
logger = logging.getLogger("Trending Archive")


def custom_exception_handler(exc, context):
    """
    Custom exception handler for the TRENDING ARCHIVE API.

    Handles known Django REST Framework exceptions and converts
    them into a consistent response format.

    Known errors:

        400 Bad Request
        401 Unauthorized
        403 Forbidden
        404 Not Found
        405 Method Not Allowed

    Unexpected errors are logged and return a generic 500 response
    when DEBUG=False.
    """

    # ============================================================
    # LET DRF HANDLE THE EXCEPTION FIRST
    # ============================================================

    response = exception_handler(exc, context)

    # ============================================================
    # PERMISSION
    # ============================================================
    if response is not None and response.status_code == 403:
        request = context.get("request")

        logger.warning(
            "Permission denied: method=%s path=%s user=%s",
            getattr(request, "method", None),
            getattr(request, "path", None),
            getattr(
                getattr(request, "user", None),
                "email",
                "anonymous",
            ),
        )
    

    # ============================================================
    # AUTHENTICATION EXCEPTION
    # ============================================================
    if response is not None and response.status_code == 401:
        request = context.get("request")

        logger.warning(
            "Authentication failed: method=%s path=%s",
            getattr(request, "method", None),
            getattr(request, "path", None),
        )
    # ============================================================
    # UNEXPECTED EXCEPTION
    # ============================================================
    if response is None:

        # Log the complete exception including traceback.
        logger.exception(
            "Unhandled exception in TRENDING ARCHIVE API",
            exc_info=exc,
            extra={
                "view": str(context.get("view")),
                "request_method": getattr(
                    context.get("request"),
                    "method",
                    None
                ),
                "request_path": getattr(
                    context.get("request"),
                    "path",
                    None
                ),
            },
        )

        # --------------------------------------------------------
        # DEVELOPMENT
        # --------------------------------------------------------
        #
        # When DEBUG=True, allow Django to show the normal
        # detailed error page.
        #
        if settings.DEBUG:
            return None

        # --------------------------------------------------------
        # PRODUCTION
        # --------------------------------------------------------
        #
        # Never expose internal exception details to users.
        #
        return Response(
            {
                "success": False,
                "message": "An unexpected server error occurred.",
                "errors": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ============================================================
    # DEFAULT VALUES
    # ============================================================

    message = "An error occurred."
    errors = None

    # ============================================================
    # DICTIONARY RESPONSE
    # ============================================================

    if isinstance(response.data, dict):

        # DRF uses "detail" for many standard errors:
        #
        # 401
        # 403
        # 404
        # 405
        #
        if "detail" in response.data:

            message = str(response.data["detail"])

        else:

            # Serializer validation errors
            message = "Validation failed."
            errors = response.data

    # ============================================================
    # LIST RESPONSE
    # ============================================================

    elif isinstance(response.data, list):

        message = "An error occurred."
        errors = response.data

    # ============================================================
    # OTHER RESPONSE TYPES
    # ============================================================

    else:

        message = str(response.data)

    # ============================================================
    # STANDARD TRENDING ARCHIVE ERROR RESPONSE
    # ============================================================

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }

    return response