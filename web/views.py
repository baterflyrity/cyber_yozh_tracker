"""HTML page views.

These views only render templates. All data access, filtering and mutations go
through the REST API from browser JavaScript, so no access rules live here and
no protected object is ever embedded into the HTML.
"""

from django.views.generic import TemplateView


class DashboardView(TemplateView):
    """``/`` — task workspace shell."""

    template_name = "dashboard.html"


class LoginView(TemplateView):
    """``/login/`` — sign-in shell."""

    template_name = "login.html"


class RegisterView(TemplateView):
    """``/register/`` — registration shell."""

    template_name = "register.html"


class TaskDetailView(TemplateView):
    """``/tasks/<id>/`` — task detail shell; data is loaded by JavaScript."""

    template_name = "task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_id"] = kwargs.get("pk")
        return context
