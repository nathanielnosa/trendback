
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("core.urls")),
    path("api/<str:version>/auth/", include("accounts.urls")),
]
