"""URLs for tasks and nested comments (mounted at ``/api/``)."""

from rest_framework.routers import SimpleRouter

from .views import CommentViewSet, TaskViewSet

app_name = "tasks_api"

router = SimpleRouter()
router.register("tasks", TaskViewSet, basename="task")
# Nested comments: /api/tasks/{task_id}/comments/[{id}/]
router.register(
    r"tasks/(?P<task_pk>\d+)/comments",
    CommentViewSet,
    basename="comment",
)

urlpatterns = router.urls
