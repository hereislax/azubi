# Azubi-Portal – Übersicht

Das Azubi-Portal ist eine webbasierte Verwaltungsanwendung für die Ausbildung von Nachwuchskräften in Behörden und öffentlichen Organisationen. Es begleitet Auszubildende vom Eintritt bis zum Abschluss und koordiniert alle beteiligten Personen und Prozesse.

---

## Wofür wird es genutzt?

| Bereich | Beschreibung |
|---|---|
| Nachwuchskräfte | Stammdaten, Status, Kontakthistorie, Onboarding, benutzerdefinierte Felder |
| Kurse & Einsatzplanung | Lehrgangsblöcke, Praxiseinsätze, Zuweisungsschreiben, Kapazitätsprüfung |
| Praxistutoren & Koordination | Verwaltung von Betreuungspersonen, Koordinationsgruppen und Funktionspostfächern |
| Ausbildungsnachweise | Wöchentliche Tätigkeitsnachweise mit Prüf- und Genehmigungsworkflow |
| Abwesenheitsmanagement | Urlaubsanträge, Krankmeldungen, Abwesenheitsampel, token-basiertes Urlaubsstellen-Portal |
| Lerntagsanträge | Self-Service-Beantragung von Lerntagen mit konfigurierbarem Regelwerk und Kontingent |
| Wohnheimverwaltung | Zimmerbelegung, Kapazitätsprüfung, Reservierungsbestätigungen |
| Inventar | Gegenstandsverwaltung, Ausgaben an Nachwuchskräfte, automatische Quittungserstellung |
| Beurteilungen | Konfigurierbare Bewertungsbögen mit token-basiertem Zugang für externe Bewerter |
| Interventionen | Erfassung und Verfolgung von Maßnahmen mit konfigurierbaren Kategorien und Eskalationsstufen |
| Bekanntmachungen | Gezielte Mitteilungen an Nachwuchskräfte mit optionaler Bestätigungspflicht und E-Mail-Versand |
| Organisationsstruktur | Hierarchische Behördenstruktur mit Kapazitätsverwaltung |
| Dokumente | Automatische Briefgenerierung auf Basis von Word-Vorlagen, Integration mit Paperless-ngx |
| Compliance | Lückenloser Audit-Log aller Datenänderungen (DSGVO), automatische Anonymisierung |

---

## Technische Grundlage

- **Backend:** Django 6 (Python)
- **Datenbank:** PostgreSQL 17
- **Hintergrundaufgaben:** Celery 5 + Redis 7
- **Statische Dateien:** WhiteNoise
- **Dokumentenspeicher:** Paperless-ngx (externe Instanz, API-Integration)
- **Deployment:** Docker Compose (5 Container: app, db, redis, celery_worker, celery_beat)

---

## Weitere Dokumentation

- [Installation (umfangreich)](installation.md)
- [Admin-Leitfaden](admin-leitfaden.md)
- [Module & Funktionen](module.md)
- [Benutzerrollen](rollen.md)
- [Workflows](workflows.md)
- [Backup & Disaster Recovery](backup.md)
