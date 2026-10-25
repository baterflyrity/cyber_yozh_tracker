"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Authentication + user directory (public: register/token, auth: me/users)
    path("api/", include(("apps.users.api.urls", "users_api"), namespace="users_api")),
    # Tasks and nested comments
    path("api/", include(("apps.tasks.api.urls", "tasks_api"), namespace="tasks_api")),
    # OpenAPI schema and interactive docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Browser UI (template shell only; all data comes from the REST API)
    path("", include("web.urls")),
]
