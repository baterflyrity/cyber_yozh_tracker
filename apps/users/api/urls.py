"""URLs for authentication and the user directory (mounted at ``/api/``)."""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = "users_api"

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("users/", views.UserListView.as_view(), name="user-list"),
]
