"""Django settings for the CyberYozh task manager.

All deployment-sensitive values are read from environment variables; see
``.env.example`` for the full list. The defaults are safe only for local
development with ``DJANGO_DEBUG=true``.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core -------------------------------------------------------------------

INSECURE_DEV_KEY = "insecure-dev-only-key-do-not-use-in-production"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", INSECURE_DEV_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if not DEBUG and SECRET_KEY == INSECURE_DEV_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real value when DJANGO_DEBUG is false."
    )

if not DEBUG and os.environ.get("SEED_DEMO_DATA", "").strip().lower() in {"1", "true", "yes"}:
    raise ImproperlyConfigured(
        "Demo data seeding is a development-only feature and is disabled when DJANGO_DEBUG is false."
    )

# --- Database ---------------------------------------------------------------

# SQLite file location is configurable so that Docker Compose can point it at a
# named volume (/app/data/db.sqlite3) while local runs default to ./data/db.sqlite3.
DB_PATH = Path(os.environ.get("DJANGO_DB_PATH", BASE_DIR / "data" / "db.sqlite3"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
    }
}

# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "drf_spectacular",
    # Local Swagger UI / Redoc bundles - API docs need no CDN
    "drf_spectacular_sidecar",
    # Local apps
    "apps.users",
    "apps.tasks",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Authentication ---------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- REST framework / JWT / OpenAPI ----------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CyberYozh Task Manager API",
    "DESCRIPTION": (
        "JWT-protected REST API for the task manager.\n\n"
        "**Authentication:** obtain an access/refresh token pair via "
        "`POST /api/auth/token/` and send `Authorization: Bearer <access token>`.\n\n"
        "**Access rules:** a task is visible only to its creator and its current assignee. "
        "The creator may edit/delete the task, the assignee may only toggle `is_completed`. "
        "Comments are visible to task participants; only their author may edit or delete them. "
        "Objects outside the caller's visible scope answer with `404`, forbidden operations "
        "inside the scope answer with `403`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"bearerAuth": []}],
    # Serve Swagger UI and Redoc from the version-pinned local bundle shipped by
    # drf-spectacular-sidecar instead of a remote CDN:
    #  * no external network dependency for the documentation pages;
    #  * no "Cannot use 'import.meta' outside a module" error, because
    #    `redoc@latest` on the CDN is Redoc 3.x whose standalone bundle is an
    #    ES module, while the bundled one is a classic UMD build.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Redoc must not fetch Google Fonts at runtime: keep the page fully local.
    "REDOC_UI_SETTINGS": {"disableGoogleFont": True},
}

# --- Internationalization / static / messages -------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Misc -------------------------------------------------------------------

# Used by the seed_demo_data command as an explicit production guard.
DEMO_DATA_ALLOWED = DEBUG
