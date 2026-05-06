# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare für das Nachwuchskräfte-Portal (Einsatzwünsche, persönliche Daten)."""
from django import forms


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
