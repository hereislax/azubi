# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Tokenlose Public-Views für die Vortragsbestätigung durch externe Vortragende."""
from django import forms
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    SeminarLecture,
    LECTURE_STATUS_CONFIRMED,
    LECTURE_STATUS_DECLINED,
    LECTURE_STATUS_PENDING,
)


class LectureDeclineForm(forms.Form):
    decline_reason = forms.CharField(
        label='Begründung (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'kern-form-input__input'}),
    )


def _get_lecture_by_token(token):
    return get_object_or_404(SeminarLecture, confirmation_token=token)


@require_http_methods(['GET', 'POST'])
def lecture_confirm(request, token):
    lecture = _get_lecture_by_token(token)
    already_responded = lecture.status != LECTURE_STATUS_PENDING

    if request.method == 'POST' and not already_responded:
        lecture.status = LECTURE_STATUS_CONFIRMED
        lecture.responded_at = timezone.now()
        lecture.save(update_fields=['status', 'responded_at'])
        from services.notifications import notify_lecture_decision
        notify_lecture_decision(lecture)
        return render(request, 'course/public/lecture_response.html', {
            'lecture': lecture,
            'action': 'confirmed',
            'already_responded': False,
        })

    return render(request, 'course/public/lecture_confirm.html', {
        'lecture': lecture,
        'already_responded': already_responded,
    })


@require_http_methods(['GET', 'POST'])
def lecture_decline(request, token):
    lecture = _get_lecture_by_token(token)
    already_responded = lecture.status != LECTURE_STATUS_PENDING

    form = LectureDeclineForm(request.POST or None)
    if request.method == 'POST' and not already_responded and form.is_valid():
        lecture.status = LECTURE_STATUS_DECLINED
        lecture.decline_reason = form.cleaned_data['decline_reason']
        lecture.responded_at = timezone.now()
        lecture.save(update_fields=['status', 'decline_reason', 'responded_at'])
        from services.notifications import notify_lecture_decision
        notify_lecture_decision(lecture)
        return render(request, 'course/public/lecture_response.html', {
            'lecture': lecture,
            'action': 'declined',
            'already_responded': False,
        })

    return render(request, 'course/public/lecture_decline.html', {
        'lecture': lecture,
        'form': form,
        'already_responded': already_responded,
    })