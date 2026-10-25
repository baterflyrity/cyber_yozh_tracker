#!/usr/bin/env python3
"""Django management entry point."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - environment problem only
        raise ImportError(
            "Django is not installed. Install dependencies first: `uv sync` "
            "or `pip install -r requirements.txt`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
