# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
"""
Hilfsfunktionen zur Erzeugung von PDFs mit elektronischem Signaturblock.

Verwendet PyMuPDF (fitz)
Erzeugt einfache elektronische Signaturen gem. eIDAS Art. 3 Nr. 10.
"""
import logging
from datetime import datetime
from io import BytesIO

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Farben (RGB, Werte 0–1)
_BLACK      = (0.0,  0.0,  0.0)
_DARK_GRAY  = (0.2,  0.2,  0.2)
_MID_GRAY   = (0.45, 0.45, 0.45)
_LIGHT_GRAY = (0.75, 0.75, 0.75)
_SIG_BG     = (0.96, 0.96, 0.98)   # ganz leichter Blau-Grau-Ton für Signaturblock

# Seitenmaße A4 (Punkte)
_PAGE_W = 595
_PAGE_H = 842
_LEFT   = 60
_RIGHT  = 535


def create_signed_pdf(
    title: str,
    fields: list[tuple[str, str]],
    signer_name: str,
    signer_role: str,
    signed_at: datetime,
) -> bytes:
    """
    Erzeugt ein einfaches A4-PDF mit Dokumentdaten und Signaturblock.

    Args:
        title:       Dokumenttitel (z. B. „Urlaubsgenehmigung")
        fields:      Liste von (Bezeichnung, Wert) Tupeln für den Dokumentkörper
        signer_name: Vollständiger Name des Unterzeichners
        signer_role: Funktion/Rolle des Unterzeichners
        signed_at:   Zeitpunkt der elektronischen Unterzeichnung

    Returns:
        PDF als bytes
    """
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W, height=_PAGE_H)

    y = 72  # Startposition (Baseline des ersten Textelements)

    # ── Titel ────────────────────────────────────────────────────────────────
    page.insert_text((_LEFT, y), title, fontsize=18, fontname="hebo", color=_BLACK)
    y += 10

    # Trennlinie unter Titel
    page.draw_line((_LEFT, y + 6), (_RIGHT, y + 6), color=_LIGHT_GRAY, width=0.7)
    y += 26

    # ── Dokumentfelder ───────────────────────────────────────────────────────
    for label, value in fields:
        # Bezeichnung (klein, grau)
        page.insert_text((_LEFT, y), label, fontsize=8, fontname="helv", color=_MID_GRAY)
        y += 14
        # Wert (normal, schwarz)
        page.insert_text((_LEFT + 8, y), str(value) if value else "–", fontsize=10, fontname="helv", color=_BLACK)
        y += 22

    y += 12  # etwas Abstand vor Signaturblock

    # ── Signaturblock ────────────────────────────────────────────────────────
    sig_top = y

    # Hintergrund-Rechteck
    page.draw_rect(
        fitz.Rect(_LEFT - 4, sig_top - 4, _RIGHT + 4, sig_top + 76),
        color=_LIGHT_GRAY,
        fill=_SIG_BG,
        width=0.5,
    )

    # Obere Trennlinie
    page.draw_line((_LEFT, sig_top), (_RIGHT, sig_top), color=_DARK_GRAY, width=0.8)
    y = sig_top + 14

    # Überschrift
    page.insert_text((_LEFT, y), "Elektronisch unterzeichnet", fontsize=9, fontname="hebo", color=_DARK_GRAY)
    y += 16

    # Felder
    page.insert_text((_LEFT, y), f"Name:             {signer_name}", fontsize=9, fontname="helv", color=_DARK_GRAY)
    y += 13
    page.insert_text((_LEFT, y), f"Funktion:         {signer_role}", fontsize=9, fontname="helv", color=_DARK_GRAY)
    y += 13
    page.insert_text(
        (_LEFT, y),
        f"Datum / Uhrzeit:  {signed_at.strftime('%d.%m.%Y, %H:%M:%S')} Uhr",
        fontsize=9,
        fontname="helv",
        color=_DARK_GRAY,
    )
    y += 16

    # eIDAS-Hinweis
    page.insert_text(
        (_LEFT, y),
        "Einfache elektronische Signatur gem. eIDAS Art. 3 Nr. 10",
        fontsize=7.5,
        fontname="heit",   # Helvetica kursiv
        color=_MID_GRAY,
    )
    y += 10

    # Untere Trennlinie
    page.draw_line((_LEFT, y), (_RIGHT, y), color=_DARK_GRAY, width=0.8)

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
