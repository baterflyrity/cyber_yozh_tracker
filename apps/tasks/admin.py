"""Django admin registration for tasks (convenience for developers)."""

from django.contrib import admin

from .models import Comment, Task


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "assigned_to", "is_completed", "updated_at")
    list_filter = ("is_completed",)
    search_fields = ("title", "description")
    autocomplete_fields = ("created_by", "assigned_to")
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "author", "created_at")
    search_fields = ("body",)
