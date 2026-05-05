# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from django import forms
from services.models import Adress
from .models import Competence, Location, OrganisationalUnit


class OrganisationalUnitForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs.setdefault("class", "kern-form-input__input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "kern-form-input__input")
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "kern-form-input__input")

        # Verhindern, dass eine Einheit ihre eigene übergeordnete Einheit wird
        if self.instance.pk:
            self.fields["parent"].queryset = OrganisationalUnit.objects.exclude(
                pk=self.instance.pk
            ).order_by("unit_type", "name")
        else:
            self.fields["parent"].queryset = OrganisationalUnit.objects.order_by(
                "unit_type", "name"
            )

    class Meta:
        model = OrganisationalUnit
        fields = ["name", "label", "unit_type", "parent", "max_capacity",
                  "locations", "competences", "notes", "is_active"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "locations": forms.SelectMultiple(attrs={"id": "id_locations"}),
            "competences": forms.SelectMultiple(attrs={"id": "id_competences"}),
        }


class AdressForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = (
                "kern-form-input__select"
                if isinstance(field.widget, forms.Select)
                else "kern-form-input__input"
            )
            field.widget.attrs.setdefault("class", css_class)

    class Meta:
        model = Adress
        fields = ["street", "house_number", "zip_code", "city", "holiday_state"]


class LocationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "kern-form-input__input")

    class Meta:
        model = Location
        fields = ["name"]


class CompetenceForm(forms.ModelForm):
    """Pflege-Form für Kompetenzen (Bezeichnung + Beschreibung)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "kern-form-input__input")

    class Meta:
        model = Competence
        fields = ["name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class OrganisationalUnitImportForm(forms.Form):
    _ALLOWED_IMPORT_EXTENSIONS = {"xlsx"}
    _MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10 MB

    file = forms.FileField(
        label="Excel-Datei (.xlsx)",
        help_text="Bitte zuerst die Vorlage herunterladen, ausfüllen und hier hochladen. "
                  "Pflichtspalten: Name, Bezeichnung, Art. Optional: Übergeordnete Einheit, "
                  "Standorte, Kompetenzen, Max. Kapazität, Notizen, Aktiv.",
        widget=forms.ClearableFileInput(attrs={"class": "kern-form-input__input", "accept": ".xlsx"}),
    )

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
            if ext not in self._ALLOWED_IMPORT_EXTENSIONS:
                raise forms.ValidationError(
                    f'Ungültiges Dateiformat „.{ext}". Erlaubt ist: XLSX.'
                )
            if f.size > self._MAX_IMPORT_SIZE:
                raise forms.ValidationError("Die Datei ist zu groß (maximal 10 MB).")
        return f
