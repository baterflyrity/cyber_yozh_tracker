"""Domain services: state-changing operations and business rules.

Every write path in the API goes through this module. Services receive plain
arguments (user objects, model instances, validated data) and raise Django
core exceptions (``PermissionDenied`` / ``ValidationError``) that the API layer
converts to 403/400 responses.

Access rules implemented here (spec/SPEC.md, section 4):

* a task is visible to its creator and its current assignee;
* the creator may edit every editable field and delete the task;
* the assignee may only toggle ``is_completed``;
* comments may be read/added by task participants, and edited/deleted only by
  their author while they still have access to the task.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Comment, Task

User = get_user_model()

MAX_TITLE_LENGTH = 200
MAX_COMMENT_LENGTH = 5000

# Fields the creator is allowed to change.
CREATOR_EDITABLE_FIELDS = {"title", "description", "assigned_to", "is_completed"}
# Fields the assignee is allowed to change.
ASSIGNEE_EDITABLE_FIELDS = {"is_completed"}


def is_participant(task: Task, user) -> bool:
    """True when the user may see the task and take part in its discussion."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return task.created_by_id == user.pk or task.assigned_to_id == user.pk


def is_creator(task: Task, user) -> bool:
    """True when the user owns the task."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return task.created_by_id == user.pk


def _validate_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        raise ValidationError("Title is required.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"Title must be {MAX_TITLE_LENGTH} characters or fewer.")
    return title


def _validate_body(body: str) -> str:
    body = (body or "").strip()
    if not body:
        raise ValidationError("Comment body is required.")
    if len(body) > MAX_COMMENT_LENGTH:
        raise ValidationError(f"Comment body must be {MAX_COMMENT_LENGTH} characters or fewer.")
    return body


def resolve_assignee(value):
    """Validate an assignee reference (user instance, pk or ``None``).

    Only existing, active users may be assigned; anything else is a validation
    error (never a server error).
    """
    if value is None or value == "":
        return None
    if isinstance(value, User):
        user = value
    else:
        try:
            user = User.objects.get(pk=value)
        except (User.DoesNotExist, TypeError, ValueError) as exc:
            raise ValidationError("Assignee must be an existing user.") from exc
    if not user.is_active:
        raise ValidationError("Assignee must be an active user.")
    return user


# --- Tasks ------------------------------------------------------------------


def create_task(*, actor, title: str, description: str = "", assigned_to=None) -> Task:
    """Create a task owned by ``actor`` regardless of the payload."""
    title = _validate_title(title)
    assignee = resolve_assignee(assigned_to)
    return Task.objects.create(
        title=title,
        description=description or "",
        created_by=actor,
        assigned_to=assignee,
    )


def update_task(*, actor, task: Task, fields: dict) -> Task:
    """Apply an allowed set of changes to ``task`` for ``actor``.

    * creator: ``title``, ``description``, ``assigned_to``, ``is_completed``;
    * assignee: ``is_completed`` only;
    * anyone else: no access at all.
    """
    if not is_participant(task, actor):
        raise PermissionDenied("You do not have access to this task.")

    if is_creator(task, actor):
        allowed = CREATOR_EDITABLE_FIELDS
    else:
        allowed = ASSIGNEE_EDITABLE_FIELDS

    disallowed = sorted(set(fields) - allowed)
    if disallowed:
        if not is_creator(task, actor):
            raise PermissionDenied(
                "Assignee may only change the completion status of the task."
            )
        raise PermissionDenied(f"You are not allowed to change: {', '.join(disallowed)}.")

    if not fields:
        return task

    if "title" in fields:
        fields["title"] = _validate_title(fields["title"])
    if "assigned_to" in fields:
        fields["assigned_to"] = resolve_assignee(fields["assigned_to"])

    with transaction.atomic():
        for name, value in fields.items():
            setattr(task, name, value)
        task.full_clean(exclude=["created_by"])
        task.save(update_fields=[*fields, "updated_at"])
    return task


def delete_task(*, actor, task: Task) -> None:
    """Delete a task; only the creator may do it. Comments cascade in the DB."""
    if not is_creator(task, actor):
        if is_participant(task, actor):
            raise PermissionDenied("Only the task creator can delete this task.")
        raise PermissionDenied("You do not have access to this task.")
    task.delete()


# --- Comments ---------------------------------------------------------------


def add_comment(*, actor, task: Task, body: str) -> Comment:
    """Add a comment to a task visible to ``actor``."""
    if not is_participant(task, actor):
        raise PermissionDenied("You do not have access to this task.")
    return Comment.objects.create(task=task, author=actor, body=_validate_body(body))


def update_comment(*, actor, comment: Comment, body: str) -> Comment:
    """Edit a comment: author-only and only while still a task participant."""
    if comment.author_id != getattr(actor, "pk", None):
        raise PermissionDenied("Only the comment author can edit this comment.")
    if not is_participant(comment.task, actor):
        raise PermissionDenied("You no longer have access to the related task.")
    comment.body = _validate_body(body)
    comment.save(update_fields=["body", "updated_at"])
    return comment


def delete_comment(*, actor, comment: Comment) -> None:
    """Delete a comment: author-only and only while still a task participant."""
    if comment.author_id != getattr(actor, "pk", None):
        raise PermissionDenied("Only the comment author can delete this comment.")
    if not is_participant(comment.task, actor):
        raise PermissionDenied("You no longer have access to the related task.")
    comment.delete()
