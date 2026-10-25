"""Shared DRF pagination settings for the API."""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Numbered pages with 20 items per page (see ``spec/SPEC.md``)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
