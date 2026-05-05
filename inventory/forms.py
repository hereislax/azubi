# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Formulare für die Inventarverwaltung."""
from django import forms


class InventoryImportForm(forms.Form):
    _ALLOWED_IMPORT_EXTENSIONS = {"xlsx"}
    _MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10 MB

    file = forms.FileField(
        label="Excel-Datei (.xlsx)",
        help_text="Bitte zuerst die Vorlage herunterladen, ausfüllen und hier hochladen. "
                  "Pflichtspalten: Bezeichnung, Kategorie. Optional: Seriennummer, Status, "
                  "Lagerort, Notizen.",
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