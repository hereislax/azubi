# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Helper für sichere Weiterleitungen (Open-Redirect-Schutz)."""
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(request, fallback: str) -> str:
    """
    Liefert die `next`-URL aus dem Request, wenn sie sicher ist
    (selbe Origin wie aktuelle Anfrage), ansonsten `fallback`.

    Schützt vor Open-Redirect-Phishing über manipulierte `?next=…`-Parameter.
    """
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback