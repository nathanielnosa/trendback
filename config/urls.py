from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(api_version="v1"), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    
    # APP URL
    path("api/", include("core.urls")),
    path("api/<str:version>/auth/", include("accounts.urls")),
    path("api/<str:version>/blog/", include("blog.urls")),
    path("api/<str:version>/comments/", include("comments.urls")),
    path("api/<str:version>/engagements/", include("engagements.urls")),
    path("api/<str:version>/notifications/", include("notifications.urls")),
    path("api/<str:version>/analytics/", include("analytics.urls")),
       path("api/<str:version>/media/", include("media_library.urls")),
]

# Unknown /api/ paths get a JSON 404 instead of an HTML page
handler404 = "core.views.not_found"

# Serve uploaded files (avatars) while developing
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)