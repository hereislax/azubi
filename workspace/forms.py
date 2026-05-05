# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare für die Raumbuchung (Admin/Koordinations- und Portal-Variante)."""
from datetime import date as date_type, timedelta

from django import forms

from .models import Workspace, WorkspaceBooking, WorkspaceClosure


class WorkspaceBookingForm(forms.ModelForm):
    """Formular für Admin/Koordinationen: bucht im Auftrag einer Nachwuchskraft."""

    class Meta:
        model = WorkspaceBooking
        fields = ['workspace', 'student', 'date', 'purpose', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
            'workspace': forms.Select(attrs={'class': 'kern-form-input__select'}),
            'student': forms.Select(attrs={'class': 'kern-form-input__select'}),
            'purpose': forms.TextInput(attrs={'class': 'kern-form-input__input', 'maxlength': 200}),
            'notes': forms.Textarea(attrs={'class': 'kern-form-input__input', 'rows': 3}),
        }

    def __init__(self, *args, initial_workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['workspace'].queryset = Workspace.objects.filter(is_active=True).select_related('location', 'workspace_type')
        if initial_workspace and not self.initial.get('workspace'):
            self.initial['workspace'] = initial_workspace.pk


class WorkspaceBookingPortalForm(forms.ModelForm):
    """Portal-Formular für Nachwuchskräfte: student wird vom View gesetzt."""

    class Meta:
        model = WorkspaceBooking
        fields = ['workspace', 'date', 'purpose']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
            'workspace': forms.Select(attrs={'class': 'kern-form-input__select'}),
            'purpose': forms.TextInput(
                attrs={
                    'class': 'kern-form-input__input',
                    'maxlength': 200,
                    'placeholder': 'optional, z.B. „Lerntag-Vorbereitung"',
                },
            ),
        }

    def __init__(self, *args, initial_workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['workspace'].queryset = (
            Workspace.objects
            .filter(is_active=True)
            .select_related('location', 'workspace_type')
            .order_by('location__name', 'name')
        )
        today = date_type.today()
        self.fields['date'].widget.attrs['min'] = today.isoformat()
        self.fields['date'].widget.attrs['max'] = (today + timedelta(days=365)).isoformat()
        if initial_workspace:
            self.initial['workspace'] = initial_workspace.pk


class WorkspaceClosureForm(forms.ModelForm):
    """Sperrzeitraum für einen Arbeitsplatz."""

    class Meta:
        model = WorkspaceClosure
        fields = ['workspace', 'start_date', 'end_date', 'reason']
        widgets = {
            'workspace':  forms.Select(attrs={'class': 'kern-form-input__select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
            'end_date':   forms.DateInput(attrs={'type': 'date', 'class': 'kern-form-input__input'}),
            'reason':     forms.TextInput(attrs={'class': 'kern-form-input__input', 'maxlength': 200}),
        }