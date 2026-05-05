# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""Datenmodelle für die Organisationsstruktur (Standorte, Kompetenzen, Organisationseinheiten)."""

import uuid
from django.db import models

# Re-Export für Backwards-Compat (HOLIDAY_STATE_CHOICES wohnt jetzt auf services.Adress).
from services.models import HOLIDAY_STATE_CHOICES  # noqa: F401


class Location(models.Model):
    """Physischer Standort mit optionaler Adresse."""

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=200, verbose_name="Bezeichnung")
    address = models.OneToOneField(
        'services.Adress',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Adresse",
    )

    def __str__(self) -> str:
        if self.address:
            return f"{self.name} – {self.address}"
        return self.name

    class Meta:
        verbose_name = "Standort"
        verbose_name_plural = "Standorte"
        ordering = ["name"]


class Competence(models.Model):
    """Kompetenz, die einer Organisationseinheit zugeordnet werden kann."""
    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(max_length=200, unique=True, verbose_name="Bezeichnung")
    description = models.TextField(blank=True, verbose_name="Beschreibung")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kompetenz"
        verbose_name_plural = "Kompetenzen"
        ordering = ["name"]


class OrganisationalUnit(models.Model):
    """Hierarchische Organisationseinheit (Behörde, Abteilung, Referat, Sachgebiet)."""

    UNIT_TYPES = [
        ("authority",       "Behörde"),
        ("department",      "Abteilung"),
        ("division_group",  "Referatsgruppe"),
        ("division",        "Referat"),
        ("section",         "Sachgebiet"),
    ]

    # Öffentliche, nicht erratbare ID – ersetzt int-PK in URLs gegen Enumeration.
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Öffentliche ID',
    )

    name = models.CharField(
        max_length=30, verbose_name="Name"
    )
    label = models.CharField(
        max_length=200, default="", verbose_name="Bezeichnung"
    )
    unit_type = models.CharField(
        max_length=30,
        choices=UNIT_TYPES,
        verbose_name="Art der Organisationseinheit",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        verbose_name="Übergeordnete Organisationseinheit",
    )
    locations = models.ManyToManyField(
        Location,
        blank=True,
        related_name="units",
        verbose_name="Standorte",
    )
    max_capacity = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Max. Kapazität"
    )
    competences = models.ManyToManyField(
        Competence,
        blank=True,
        related_name="units",
        verbose_name="Kompetenzen",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    # ── Hilfsmethoden ────────────────────────────────────────────────────
    def get_all_locations(self) -> models.QuerySet:
        """
        Gibt alle Standorte der Organisationseinheit aus, inklusive aller nachgeordneten Organisationseinheiten, ohne Duplikate.
        """
        all_units = list(OrganisationalUnit.objects.only("pk", "parent_id"))
        children_map: dict[int, list[int]] = {u.pk: [] for u in all_units}
        for unit in all_units:
            if unit.parent_id:
                children_map.setdefault(unit.parent_id, []).append(unit.pk)

        # Sammelt rekursiv alle PrimaryKeys der Kindknoten
        def collect_pks(root_pk: int) -> list[int]:
            result = [root_pk]
            for child_pk in children_map.get(root_pk, []):
                result.extend(collect_pks(child_pk))
            return result

        descendant_pks = collect_pks(self.pk)
        return Location.objects.filter(units__pk__in=descendant_pks).distinct()

    def get_ancestors(self) -> list["OrganisationalUnit"]:
        """
        Gibt alle übergeordneten Organisationseinheiten, beginnend beim Root, zurück.
        """
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_depth(self) -> int:
        """
        0 = root, 1 = Ebene unter Root, …
        """
        return len(self.get_ancestors())

    def get_full_path(self) -> str:
        """
        Bspw.: 'Behörde A › Abteilung 1 › Referat X'
        """
        parts = [u.name for u in self.get_ancestors()] + [self.name]
        return " › ".join(parts)

    def __str__(self) -> str:
        if self.label:
            return f"{self.name} ({self.label})"
        return self.name

    class Meta:
        verbose_name = "Organisationseinheit"
        verbose_name_plural = "Organisationseinheiten"
        ordering = ["unit_type", "name"]
