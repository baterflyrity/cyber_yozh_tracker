"""Query/selector layer: every read path that needs access filtering.

Selectors return plain querysets; they never build HTTP responses. All
visibility rules are expressed once here so list and detail endpoints share
the same scope.
"""

from django.db.models import Q, QuerySet

from .models import Comment, Task


def tasks_visible_to(user) -> QuerySet[Task]:
    """Tasks the user may see: created by them or assigned to them."""
    if not user or not user.is_authenticated:
        return Task.objects.none()
    return Task.objects.filter(Q(created_by=user) | Q(assigned_to=user))


def _search_q(search: str) -> Q:
    """Build a title/description search condition.

    ``icontains`` only case-folds ASCII in SQLite, so the common casing
    variants are added explicitly to keep Cyrillic search usable.
    """
    condition = Q(title__icontains=search) | Q(description__icontains=search)
    for variant in {search.lower(), search.upper(), search.capitalize(), search.title()}:
        condition |= Q(title__contains=variant) | Q(description__contains=variant)
    return condition


def filter_tasks(
    queryset: QuerySet[Task],
    *,
    search: str | None = None,
    is_completed: bool | None = None,
    ordering: str | None = None,
) -> QuerySet[Task]:
    """Apply the supported list query parameters (spec section 5)."""
    if search:
        queryset = queryset.filter(_search_q(search))
    if is_completed is not None:
        queryset = queryset.filter(is_completed=is_completed)
    if ordering:
        queryset = queryset.order_by(ordering)
    return queryset


def comments_for_task(task: Task) -> QuerySet[Comment]:
    """Comments of a task the caller has already proven access to."""
    return Comment.objects.filter(task=task).select_related("author", "task")
