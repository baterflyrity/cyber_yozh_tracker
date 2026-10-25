"""API endpoints for registration, JWT tokens, current user and user directory."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .. import services as users_services
from ..selectors import active_users
from .serializers import RegisterSerializer, UserBriefSerializer, UserDirectorySerializer

User = get_user_model()


@extend_schema(tags=["auth"])
class RegisterView(generics.CreateAPIView):
    """``POST /api/auth/register/`` — create a new account (public)."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={201: UserBriefSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = users_services.register_user(**serializer.validated_data)
        return Response(UserBriefSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["auth"])
class LoginView(TokenObtainPairView):
    """``POST /api/auth/token/`` — issue JWT access/refresh pair (public)."""


@extend_schema(tags=["auth"])
class TokenRefreshView(TokenRefreshView):
    """``POST /api/auth/token/refresh/`` — exchange refresh for access token."""


@extend_schema(tags=["auth"])
class MeView(APIView):
    """``GET /api/auth/me/`` — info about the current user."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=UserBriefSerializer)
    def get(self, request):
        return Response(UserBriefSerializer(request.user).data)


@extend_schema(tags=["users"])
class UserListView(generics.ListAPIView):
    """``GET /api/users/?search=`` — active users for task assignment."""

    serializer_class = UserDirectorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return active_users(self.request.query_params.get("search"))
