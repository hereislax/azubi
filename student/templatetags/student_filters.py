# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import template

register = template.Library()


@register.filter
def phone_format(value):
    if not value:
        return '–'
    digits = str(value).replace(' ', '')
    return ' '.join(digits[i:i+4] for i in range(0, len(digits), 4))
