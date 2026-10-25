"""Idempotent demo data seeding for local development.

The command is intentionally blocked outside development (``DEBUG`` must be
true) and never touches passwords of existing users: it only creates what is
missing, so restarting the containers cannot duplicate data.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tasks.models import Comment, Task

User = get_user_model()

DEMO_USERS = [
    {"username": "demo_owner", "password": "DemoOwner123!", "email": "demo_owner@example.local"},
    {"username": "demo_worker", "password": "DemoWorker123!", "email": "demo_worker@example.local"},
    {
        "username": "demo_outsider",
        "password": "DemoOutsider123!",
        "email": "demo_outsider@example.local",
    },
]

DEMO_TASKS = [
    {
        "title": "Подготовить демонстрационный API-сценарий",
        "description": (
            "Основная задача E2E-сценария: создана demo_owner и назначена demo_worker. "
            "Исполнитель может менять только статус выполнения."
        ),
        "created_by": "demo_owner",
        "assigned_to": "demo_worker",
        "is_completed": False,
    },
    {
        "title": "Задача только для владельца",
        "description": (
            "Не назначена исполнителю: demo_worker и demo_outsider не должны видеть её "
            "ни в списке, ни по detail endpoint."
        ),
        "created_by": "demo_owner",
        "assigned_to": None,
        "is_completed": False,
    },
    {
        "title": "Моя задача исполнителя",
        "description": "Собственная задача demo_worker: назначать и редактировать её может только автор.",
        "created_by": "demo_worker",
        "assigned_to": None,
        "is_completed": False,
    },
]

DEMO_COMMENTS = [
    {
        "task_title": "Подготовить демонстрационный API-сценарий",
        "author": "demo_owner",
        "body": "Комментарий владельца: проверьте назначение исполнителя и статус задачи.",
    },
    {
        "task_title": "Подготовить демонстрационный API-сценарий",
        "author": "demo_worker",
        "body": "Комментарий исполнителя: беру задачу в работу.",
    },
]


class Command(BaseCommand):
    help = (
        "Idempotently create demo users, tasks and comments for the local "
        "E2E scenario. Development only: refuses to run when DEBUG is false."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to seed demo data: DJANGO_DEBUG is false. "
                "Demo data is for local development only."
            )

        users = self._seed_users()
        tasks = self._seed_tasks(users)
        self._seed_comments(users, tasks)

        self.stdout.write(self.style.SUCCESS("Demo data is up to date."))

    def _seed_users(self) -> dict:
        users = {}
        for spec in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={"email": spec["email"]},
            )
            if created:
                # Passwords are hashed by Django; an existing user's password is
                # never changed so re-running seed cannot break manual changes.
                user.set_password(spec["password"])
                user.save(update_fields=["password"])
                self.stdout.write(f"  + user {user.username}")
            else:
                self.stdout.write(f"  = user {user.username} already exists")
            users[spec["username"]] = user
        return users

    def _seed_tasks(self, users: dict) -> dict:
        tasks = {}
        for spec in DEMO_TASKS:
            task, created = Task.objects.get_or_create(
                title=spec["title"],
                created_by=users[spec["created_by"]],
                defaults={
                    "description": spec["description"],
                    "assigned_to": users[spec["assigned_to"]] if spec["assigned_to"] else None,
                    "is_completed": spec["is_completed"],
                },
            )
            if created:
                self.stdout.write(f"  + task {task.title}")
            else:
                self.stdout.write(f"  = task {task.title} already exists")
            tasks[spec["title"]] = task
        return tasks

    def _seed_comments(self, users: dict, tasks: dict) -> None:
        for spec in DEMO_COMMENTS:
            comment, created = Comment.objects.get_or_create(
                task=tasks[spec["task_title"]],
                author=users[spec["author"]],
                body=spec["body"],
            )
            if created:
                self.stdout.write(f"  + comment by {spec['author']}")
            else:
                self.stdout.write(f"  = comment by {spec['author']} already exists")
