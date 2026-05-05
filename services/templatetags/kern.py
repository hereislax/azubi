# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""KERN-Form-Tags: rendern Django-Form-Felder als natives KERN-UX-Markup.

Verwendung im Template:
    {% load kern %}
    {% kern_field form.email %}
    {% kern_field form.role label="Rolle" %}
    {% kern_field form.notes rows=5 %}
"""
from django import forms, template
from django.utils.html import format_html, conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


def _classify(field):
    widget = field.field.widget
    if isinstance(widget, forms.CheckboxInput):
        return "checkbox"
    if isinstance(widget, forms.RadioSelect):
        return "radio"
    if isinstance(widget, forms.CheckboxSelectMultiple):
        return "checkbox_multi"
    if isinstance(widget, (forms.Select, forms.SelectMultiple)):
        return "select"
    if isinstance(widget, forms.Textarea):
        return "textarea"
    if isinstance(widget, forms.FileInput):
        return "file"
    return "input"


def _apply_kern_class(field, kind):
    """Setzt die richtige KERN-CSS-Klasse, entfernt Bootstrap-Klassen."""
    widget = field.field.widget
    existing = widget.attrs.get("class", "")
    if kind == "select":
        target = "kern-form-input__select"
    elif kind == "checkbox":
        target = "kern-form-check__checkbox"
    elif kind == "radio":
        target = "kern-form-check__radio"
    else:
        target = "kern-form-input__input"
    drop = {"form-control", "form-select", "form-control-sm", "form-select-sm"}
    classes = [c for c in existing.split() if c and c not in drop]
    if target not in classes:
        classes.append(target)
    widget.attrs["class"] = " ".join(classes)


def _hint_html(text):
    if not text:
        return ""
    return format_html('<span class="kern-hint">{}</span>', text)


def _error_html(field):
    if not field.errors:
        return ""
    return format_html(
        '<span class="kern-error"><i class="bi bi-exclamation-circle me-1"></i>{}</span>',
        "; ".join(field.errors),
    )


@register.simple_tag
def kern_field(field, label=None, hint=None, rows=None):
    """Rendert ein Form-Feld als KERN-UX-Markup."""
    if field is None:
        return ""

    kind = _classify(field)
    _apply_kern_class(field, kind)

    if rows and kind == "textarea":
        field.field.widget.attrs["rows"] = rows

    label_text = label if label is not None else field.label
    help_text = hint if hint is not None else field.help_text
    err_class = "kern-form-input--error" if field.errors else ""

    if kind == "checkbox":
        return format_html(
            '<div class="kern-form-check {}">{}'
            '<label for="{}" class="kern-label">{}</label>{}{}</div>',
            "kern-form-check--error" if field.errors else "",
            field,
            field.id_for_label,
            label_text or "",
            _hint_html(help_text),
            _error_html(field),
        )

    if kind == "select":
        return format_html(
            '<div class="kern-form-input {}">'
            '<label for="{}" class="kern-label">{}</label>'
            '<div class="kern-form-input__select-wrapper">{}</div>{}{}</div>',
            err_class,
            field.id_for_label,
            label_text or "",
            field,
            _hint_html(help_text),
            _error_html(field),
        )

    return format_html(
        '<div class="kern-form-input {}">'
        '<label for="{}" class="kern-label">{}</label>{}{}{}</div>',
        err_class,
        field.id_for_label,
        label_text or "",
        field,
        _hint_html(help_text),
        _error_html(field),
    )


@register.simple_tag
def kern_field_errors(field):
    if not field:
        return ""
    return _error_html(field)
