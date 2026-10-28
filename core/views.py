from django.http import JsonResponse
from django.views.defaults import page_not_found

from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response({
        "status": "success",
        "message": "Blog API is running",
    })


def not_found(request, exception=None):
    """404 page: JSON for API paths, Django's normal page for everything else."""
    if request.path.startswith("/api/"):
        return JsonResponse(
            {"success": False, "message": "Not found.", "errors": None},
            status=404,
        )

    return page_not_found(request, exception)