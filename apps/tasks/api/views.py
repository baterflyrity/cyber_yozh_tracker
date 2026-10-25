"""Task endpoints: translate HTTP to selectors/services and back."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import selectors, services
from .permissions import IsCommentParticipant, IsTaskParticipant
from .serializers import CommentSerializer, TaskSerializer

TRUTHY = {"1", "true", "yes", "on"}
FALSY = {"0", "false", "no", "off"}


def parse_bool_param(raw: str, name: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in TRUTHY:
        return True
    if lowered in FALSY:
        return False
    raise ValidationError({name: ["Must be 'true' or 'false'."]})


@extend_schema(
    tags=["tasks"],
    parameters=[
        OpenApiParameter(
            "is_completed", str, description="Filter by completion status (true/false)."
        ),
        OpenApiParameter("search", str, description="Search in title and description."),
        OpenApiParameter(
            "ordering",
            str,
            description="Sort order, e.g. `created_at`, `-updated_at`, `title`.",
        ),
    ],
)
class TaskViewSet(viewsets.ModelViewSet):
    """CRUD over the tasks visible to the current user.

    Visibility comes from the selector (creator or assignee), field-level
    permissions come from ``apps.tasks.services``.
    """

    serializer_class = TaskSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "title", "is_completed"]
    ordering = "-updated_at"
    permission_classes = [IsAuthenticated, IsTaskParticipant]
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        queryset = selectors.tasks_visible_to(self.request.user)
        search = self.request.query_params.get("search")
        raw_completed = self.request.query_params.get("is_completed")
        is_completed = None
        if raw_completed is not None and raw_completed != "":
            is_completed = parse_bool_param(raw_completed, "is_completed")
        return selectors.filter_tasks(queryset, search=search, is_completed=is_completed)

    def get_object(self):
        # Detail endpoints ignore list filters; only the visibility scope applies,
        # so foreign objects consistently answer with 404.
        queryset = selectors.tasks_visible_to(self.request.user)
        obj = get_object_or_404(queryset, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(responses={201: TaskSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = services.create_task(
            actor=request.user,
            title=data.get("title", ""),
            description=data.get("description", ""),
            assigned_to=data.get("assigned_to"),
        )
        out = self.get_serializer(task)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: TaskSerializer})
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        task = self.get_object()
        serializer = self.get_serializer(task, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        services.update_task(actor=request.user, task=task, fields=serializer.validated_data)
        out = self.get_serializer(task)
        return Response(out.data)

    def perform_destroy(self, instance):
        services.delete_task(actor=self.request.user, task=instance)

    @extend_schema(responses={204: None})
    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        services.delete_task(actor=request.user, task=task)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["comments"])
class CommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Nested comments of a task visible to the current user.

    The nested ``task_id`` is validated on every request: a comment can only be
    reached through the URL of the task it belongs to, and only while that task
    is visible to the caller. ``PUT`` is intentionally not offered (``PATCH`` is
    enough for partial edits, spec section 5).
    """

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsCommentParticipant]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    # Typed ids keep the generated OpenAPI path parameters as integers.
    lookup_value_regex = r"\d+"

    def _get_task(self):
        return get_object_or_404(
            selectors.tasks_visible_to(self.request.user), pk=self.kwargs["task_pk"]
        )

    def get_queryset(self):
        return selectors.comments_for_task(self._get_task())

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    @extend_schema(responses={201: CommentSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = services.add_comment(
            actor=request.user,
            task=self._get_task(),
            body=serializer.validated_data.get("body", ""),
        )
        out = self.get_serializer(comment)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: CommentSerializer})
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        comment = self.get_object()
        serializer = self.get_serializer(comment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        services.update_comment(
            actor=request.user,
            comment=comment,
            body=serializer.validated_data.get("body", comment.body),
        )
        out = self.get_serializer(comment)
        return Response(out.data)

    @extend_schema(responses={204: None})
    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        services.delete_comment(actor=request.user, comment=comment)
        return Response(status=status.HTTP_204_NO_CONTENT)
