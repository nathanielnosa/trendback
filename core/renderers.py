"""
One error shape for the whole API.

Every response with a status of 400 or more is sent to the client as

    {"success": false, "message": "<short text>", "errors": <details or null>}

Views keep returning errors however they like ({"message": ...}, {"error": ...},
serializer.errors ...). This renderer reshapes them on the way out, so the
views, and the tests that read response.data, do not change.
"""
from rest_framework.renderers import JSONRenderer

STANDARD_KEYS = {"success", "message", "errors"}


def normalize_error(data, response):
    """Return `data` in the standard error shape."""
    # Already standard (produced by core.exceptions.custom_exception_handler).
    if isinstance(data, dict) and set(data) == STANDARD_KEYS:
        return data

    fallback = (
        "Validation failed."
        if response.status_code == 400
        else (getattr(response, "status_text", "") or "Request failed.")
    )

    if isinstance(data, dict):
        # {"message": "..."}, {"error": "..."} or DRF's {"detail": "..."}
        for key in ("message", "error", "detail"):
            if isinstance(data.get(key), str):
                extra = {name: value for name, value in data.items() if name != key}
                return {"success": False, "message": data[key], "errors": extra or None}

        # Field errors such as {"email": ["This field is required."]}
        return {"success": False, "message": fallback, "errors": data or None}

    if data is None or data == "":
        return {"success": False, "message": fallback, "errors": None}

    # A bare list or string of errors
    return {"success": False, "message": fallback, "errors": data}


class StandardJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")

        if response is not None and response.status_code >= 400:
            data = normalize_error(data, response)

        return super().render(data, accepted_media_type, renderer_context)