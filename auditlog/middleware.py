# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
import threading

_thread_locals = threading.local()


def get_current_user():
    """Return the user from the current request, or None."""
    return getattr(_thread_locals, 'user', None)


class AuditLogMiddleware:
    """Stores the current request user in thread-local storage so signals can access it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            _thread_locals.user = request.user
        else:
            _thread_locals.user = None
        response = self.get_response(request)
        return response
