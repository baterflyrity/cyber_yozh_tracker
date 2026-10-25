"""URLs of the browser UI shell."""

from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("tasks/<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
]
