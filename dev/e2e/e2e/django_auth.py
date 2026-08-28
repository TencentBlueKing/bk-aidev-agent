from __future__ import annotations

import os

from django.contrib.auth import get_user_model


class E2EAuthMiddleware:
    """Inject the identity already resolved by the local login mock."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        username = os.getenv("E2E_USERNAME", "").strip()
        if username:
            user, _ = get_user_model().objects.get_or_create(username=username)
            request.user = user
            request._cached_user = user
        return self.get_response(request)
