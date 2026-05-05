# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import template

register = template.Library()


@register.filter
def split(value, delimiter=" "):
    return value.split(delimiter)
