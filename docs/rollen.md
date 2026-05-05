# Benutzerrollen

Das Azubi-Portal kennt sieben Rollen. Der Zugriff wird über Django-Gruppen und ein URL-Whitelist-Middleware gesteuert.

---

## Übersicht

| Rolle (Gruppenname) | Beschreibung |
|---|---|
| `ausbildungsleitung` | Vollzugriff auf alle Funktionen |
| `ausbildungsreferat` | Breiter operativer Zugriff, kann alles einsehen und bearbeiten |
| `ausbildungskoordination` | Koordinationsrolle: Einsätze annehmen/ablehnen, Praxistutoren verwalten |
| `ausbildungsverantwortliche` | Lesezugriff auf zugewiesene Nachwuchskräfte + Ausbildungsnachweise prüfen |
| `hausverwaltung` | Nur Wohnheim-Kalender und Nachwuchskraft-Stammdaten |
| `reisekostenstelle` | Lesezugriff auf Nachwuchskräfteliste, Kurse und Wohnheim-Kalender |
| *(Nachwuchskraft)* | Eigenes Self-Service-Portal und Ausbildungsnachweise |

> Besitzt ein Benutzer sowohl `ausbildungskoordination` als auch `ausbildungsverantwortliche`, gelten die Zugriffsrechte beider Rollen kombiniert.

---

## Ausbildungsleitung

Django-Staff-Benutzer oder Mitglieder der Gruppe `ausbildungsleitung`. Kein URL-Filter — vollständiger Zugriff auf alle Bereiche der Anwendung einschließlich Django-Admin.

---

## Ausbildungsreferat

Breiter operativer Zugriff. Kein URL-Filter — kann alle Bereiche einsehen und bearbeiten. Administrative Bestätigungsfunktionen (z. B. Praxistutor-Bestätigung, Anonymisierung) sind der Ausbildungsleitung vorbehalten.

---

## Ausbildungskoordination

Zugriff über URL-Whitelist. Typischerweise Hauptkoordinatoren (`ChiefInstructor`) einer Koordinationsgruppe.

**Erlaubte Bereiche:**
- Nachwuchskräfteliste und -detailansicht (lesend)
- Organisationseinheiten einsehen und bearbeiten
- Praxistutoren: Liste, Anlegen, Detailansicht
- Eigene Koordinationsgruppe: Detailansicht, Kalender
- Praxiseinsätze der eigenen Gruppe: bearbeiten, annehmen, ablehnen, Aufteilung beantragen
- Praktikumsbewertungen einsehen und bestätigen
- Kapazitätsübersicht und Kurskalender
- Suche und Benachrichtigungen

---

## Ausbildungsverantwortliche

Zugriff über URL-Whitelist. Eingeschränkt auf zugewiesene Nachwuchskräfte.

**Erlaubte Bereiche:**
- Nachwuchskräfteliste und -detailansicht (lesend)
- Dokumentenvorschau und -download
- Aktensuche für einzelne Nachwuchskräfte
- Ausbildungsnachweise: prüfen und genehmigen
- Abwesenheiten: Urlaubsantragsliste und -detail, Krankmeldungsliste (nur lesend, kein Erfassen oder Entscheiden)
- Suche und Benachrichtigungen

---

## Hausverwaltung

Zugriff über URL-Whitelist. Sehr eingeschränkte Rolle für Wohnheimbetreiber.

**Erlaubte Bereiche:**
- Wohnheim-Belegungskalender
- Nachwuchskraft-Detailansicht (lesend)

---

## Reisekostenstelle

Zugriff über URL-Whitelist. Reine Leserolle für abrechnungsrelevante Stellen.

**Erlaubte Bereiche:**
- Nachwuchskräfteliste und -detailansicht (lesend)
- Kursliste und -detailansicht (lesend)
- Wohnheim-Belegungskalender (lesend)

---

## Nachwuchskraft

Kein Gruppenname — wird über das Vorhandensein eines verknüpften `student_profile` erkannt.

**Erlaubte Bereiche:**
- Self-Service-Portal (`/portal/`): Dashboard, eigene Stammdaten, Stationsplan, Noten
- Urlaub (`/portal/urlaub/`): eigene Urlaubsanträge einsehen, neuen Antrag stellen, Stornierungsantrag stellen
- Lerntagsanträge (`/portal/`): Lerntagsantrag stellen, eigene Anträge und Restkontingent einsehen
- Ausbildungsnachweise (`/ausbildungsnachweise/`): erstellen, bearbeiten, einreichen
- Impressum und Datenschutz
