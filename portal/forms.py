# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare für das Nachwuchskräfte-Portal (Anfragen, Einsatzwünsche, persönliche Daten)."""
import os

from django import forms

from student.models import StudentInquiry

_ALLOWED_ATTACHMENT_EXTENSIONS = {'pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'xlsx', 'csv'}
_MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024  # 20 MB


def _clean_attachment(f):
    """Validierung für Dateianhänge bei Anfragen."""
    ext = os.path.splitext(f.name)[1].lstrip('.').lower()
    if ext not in _ALLOWED_ATTACHMENT_EXTENSIONS:
        raise forms.ValidationError(
            f'Dateityp „.{ext}" nicht erlaubt. '
            f'Erlaubt: {", ".join(sorted(_ALLOWED_ATTACHMENT_EXTENSIONS))}.'
        )
    if f.size > _MAX_ATTACHMENT_SIZE:
        raise forms.ValidationError('Die Datei darf maximal 20 MB groß sein.')
    return f


class StudentInquiryForm(forms.ModelForm):
    """Formular zum Erstellen einer neuen Anfrage durch die Nachwuchskraft."""
    class Meta:
        model = StudentInquiry
        fields = ['subject', 'message', 'attachment']
        widgets = {
            'subject': forms.TextInput(attrs={'placeholder': 'Betreff Ihrer Anfrage'}),
            'message': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Beschreiben Sie Ihr Anliegen...',
            }),
        }

    def clean_attachment(self):
        f = self.cleaned_data.get('attachment')
        if f:
            return _clean_attachment(f)
        return f


class InquiryReplyForm(forms.Form):
    """Formular für die Antwort auf eine bestehende Anfrage."""
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ihre Antwort...'}),
        label='Antwort',
    )
    attachment = forms.FileField(required=False, label='Anhang')

    def clean_attachment(self):
        f = self.cleaned_data.get('attachment')
        if f:
            return _clean_attachment(f)
        return f


class InternshipPreferenceForm(forms.ModelForm):
    """Formular für die Einsatzwünsche der Nachwuchskraft (bevorzugte OEs und Standorte)."""
    class Meta:
        from student.models import InternshipPreference
        model = InternshipPreference
        fields = ['preferred_units', 'preferred_locations', 'notes']
        widgets = {
            'preferred_units': forms.CheckboxSelectMultiple(),
            'preferred_locations': forms.CheckboxSelectMultiple(),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'z. B. Interesse an IT-Themen, bevorzugt Vormittagszeiten...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from organisation.models import OrganisationalUnit, Location
        self.fields['preferred_units'].queryset = (
            OrganisationalUnit.objects
            .filter(unit_type__in=['authority', 'department'], is_active=True)
            .order_by('unit_type', 'name')
        )
        self.fields['preferred_locations'].queryset = Location.objects.order_by('name')


class StudentPersonalDataForm(forms.Form):
    """Formular für die Bearbeitung persönlicher Daten durch den Azubi."""
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        label='Telefonnummer',
    )
    street = forms.CharField(max_length=200, required=False, label='Straße')
    house_number = forms.CharField(max_length=20, required=False, label='Hausnummer')
    zip_code = forms.CharField(max_length=10, required=False, label='PLZ')
    city = forms.CharField(max_length=100, required=False, label='Ort')
