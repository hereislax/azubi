# Module & Funktionen

Das Azubi-Portal ist in folgende Module gegliedert:

---

## Nachwuchskräfte

Zentrale Verwaltung aller Auszubildenden.

**Stammdaten**
- Name, Geburtsdatum, Kontaktdaten, E-Mail, Telefon
- Eindeutige Azubi-ID (Format: `azubi-` + 8 Hex-Zeichen, z. B. `azubi-a1b2c3d4`)
- Zugeordneter Kurs und Berufsbild
- Status (farblich kodiert: grün / gelb / rot / grau / blau)
- Benutzerdefinierte Zusatzfelder je Nachwuchskraft

**Kontakthistorie**
- Erfassung von Kontakteinträgen (Telefon, E-Mail, persönlich)
- Protokollierung von Anliegen und Rückmeldungen

**Onboarding**
- Checklisten-Vorlagen für den Eintritt
- Fortschrittsanzeige je Nachwuchskraft

**Datenschutz**
- Automatische Anonymisierung inaktiver Nachwuchskräfte (täglich, 12:00 Uhr)
- Manuelle Anonymisierung durch Ausbildungsleitung
- Vollständige Änderungshistorie pro Nachwuchskraft für DSGVO-Auskunftsersuchen

**Import / Export**
- CSV-Import (Semikolon-getrennt, UTF-8) und Excel-Import (.xlsx)
- CSV-Export der Nachwuchskräftedaten

---

## Kurse & Einsatzplanung

Verwaltung von Ausbildungskursen und deren Zeitplanung.

**Kurse**
- Erstellung mit Start- und Enddatum sowie Berufsbild
- Zuordnung von Nachwuchskräften

**Lehrgangsblöcke**
- Zeitliche Blöcke innerhalb eines Kurses (z. B. Theorie, Praxis, Standort)
- Automatische Generierung von Zuweisungsschreiben auf Basis von Word-Vorlagen

**Praxiseinsätze**
- Individuelle Zuweisung einer Nachwuchskraft zu einer Organisationseinheit und einem Praxistutor
- Genehmigungsworkflow: ausstehend → genehmigt / abgelehnt
- Kapazitätsprüfung je Organisationseinheit
- Aufteilungsanfragen (Einsatz auf mehrere Einheiten aufteilen)

**Benotung von Praxiseinsätzen**
- Praxisbericht, Note und Bestätigungsworkflow
- Erinnerungsmails an Praxistutoren (7 Tage vor Beginn und Ende, täglich 07:00 Uhr)

**Dokumente**
- Zuweisungsschreiben, Stationsschreiben, Einsatzplanschreiben
- Genehmigungsprozess vor dem Versand, Ablage in Paperless-ngx

---

## Praxistutoren & Koordination

Verwaltung der betreuenden Personen.

**Praxistutoren**
- Anlegen mit Berufsbild, Standort und Organisationseinheit
- Bestätigungsworkflow: ausstehend → bestätigt
- Benachrichtigung per E-Mail bei Zuweisung

**Koordination**
- Koordinationsgruppen mit gemeinsamen Funktionspostfächern
- Zuständigkeit für bestimmte Organisationseinheiten (inkl. nachgeordneter Bereiche)
- Mitgliederverwaltung (Hauptkoordinatoren mit eigenem Benutzerkonto)
- Kalenderansicht je Koordinationsgruppe

---

## Ausbildungsnachweise

Wöchentliche Tätigkeitsnachweise der Nachwuchskräfte.

- Erfassung pro Kalenderwoche mit einzelnen Tagen (Praxis / Schule / Urlaub / Krank / Sonstiges)
- Statusworkflow: Entwurf → Eingereicht → Genehmigt / Abgelehnt
- Korrekturhinweise durch Prüfer bei Ablehnung; Nachweis geht in Entwurfsstatus zurück
- Erinnerungsmail an Nachwuchskräfte bei fehlenden Einreichungen (täglich 07:00 Uhr)
- Massenexport als Word-Dokument
- Nur für Berufsbilder mit aktivierter Nachweispflicht

---

## Abwesenheitsmanagement

Verwaltung von Urlaub und Krankmeldungen.

**Urlaubsanträge**
- Erfassung durch das Ausbildungsreferat oder durch die Nachwuchskraft im Self-Service-Portal
- Genehmigungsworkflow: ausstehend → genehmigt / abgelehnt
- Tägliche Bündelung genehmigter Anträge (Celery Beat, 08:00 Uhr) als Paket per E-Mail an die Urlaubsstelle
- Token-basiertes Portal für die Urlaubsstelle: Eintrag des Resturlaubs (aktuelles Jahr / Vorjahr) ohne Login
- Automatische Benachrichtigung der Nachwuchskraft nach Entscheidung und nach Bearbeitung durch die Urlaubsstelle
- Stornierungsanträge für bereits genehmigte oder bearbeitete Anträge
- Generierung einer Word-Bestätigung nach Urlaubsstellenbearbeitung (Vorlage konfigurierbar)

**Krankmeldungen**
- Erfassung mit Typ (Selbstauskunft / K-Taste / Attest) und Startdatum (Vorauswahl: heute)
- Schließen mit Enddatum (Gesundmeldung)
- Täglicher Bericht per E-Mail an die Urlaubsstelle (Celery Beat, 08:05 Uhr): neue Krank- und Gesundmeldungen

**Abwesenheitsampel**
- Automatische Berechnung des Krankheitsanteils (Arbeitstage) am Kurszeitraum
- Grün < 5 %, Gelb ≥ 5 %, Rot ≥ 10 %
- Anzeige im Nachwuchskraft-Detailtab „Abwesenheiten"
- Benachrichtigung der Ausbildungsleitung per E-Mail bei jedem Ampelwechsel
- Feiertagsbereinigung nach Bundesland (konfigurierbar)

**Einstellungen**
- Konfigurierbare E-Mail-Adresse der Urlaubsstelle
- Bundesland für die Berechnung gesetzlicher Feiertage
- Upload und Verwaltung von Word-Vorlagen für die Urlaubsbestätigung

---

## Lerntagsanträge

Self-Service-Beantragung von Lerntagen durch Nachwuchskräfte.

**Regelwerk (StudyDayPolicy)**
- Konfigurierbar je Berufsbild: Gesamtkontingent, pro Block, pro Woche oder pro Monat
- Verknüpfung mit Ausbildungslehrgang und Kursblock möglich
- Unterstützung für mehrjährige Ausbildungen mit jahresabhängiger Kontingentanpassung

**Antrag und Workflow**
- Nachwuchskraft stellt Antrag für ein bestimmtes Datum im Self-Service-Portal
- Statusworkflow: ausstehend → genehmigt / abgelehnt
- Kontingentprüfung: verbleibende Lerntage werden angezeigt und geprüft

---

## Beurteilungen

Konfigurierbare Bewertungsbögen für Praxiseinsätze.

- Beurteilungskriterien je Berufsbild mit eigenen Kategorien
- Bewertungsvorlagen mit konfigurierbarer Notenskala (1,0–6,0 oder Punkte 0–15)
- Token-basierte Bewertungsformulare für externe Bewerter (kein Login erforderlich)
- Zuordnung von Beurteilungen zu Praxiseinsätzen

---

## Interventionen

Erfassung und Nachverfolgung von Maßnahmen bei Nachwuchskräften.

- Konfigurierbare Interventionskategorien mit Eskalationsstufen
- Statusworkflow: offen → in Bearbeitung → geschlossen / eskaliert
- Auslösertypen konfigurierbar (z. B. Fehlverhalten, Fördermaßnahmen)
- Zuordnung zu einzelnen Nachwuchskräften

---

## Bekanntmachungen

Gezielte Mitteilungen an Nachwuchskräfte.

- Zielgruppenauswahl: alle Nachwuchskräfte, nach Kurs, Berufsbild, Koordinationsgruppe, Laufbahn oder einzeln
- Entwurfs- und Veröffentlichungsstatus
- Optionale Bestätigungspflicht (Nachwuchskraft muss Kenntnisnahme bestätigen)
- Optionaler E-Mail-Versand bei Veröffentlichung

---

## Inventar

Verwaltung von Gegenständen, die an Nachwuchskräfte ausgegeben werden.

**Kategorien und Gegenstände**
- Kategorien mit eigenem Icon und optionaler Quittungsvorlage (Word)
- Einzelne Gegenstände mit Seriennummer, Beschreibung und Status (verfügbar / ausgegeben / defekt / ausgemustert)

**Ausgaben**
- Ausgabe eines Gegenstands an eine Nachwuchskraft mit Zeitstempel und Notizen
- Rückgabe mit Zeitstempel
- Automatische Generierung einer Ausgabequittung als PDF auf Basis einer Word-Vorlage
- QR-Code auf der Quittung kodiert die eindeutige Ausgabe-ID
- Upload der gescannten Papierquittung: QR-Code wird automatisch ausgelesen und der Quittung zugeordnet
- Ablage generierter Dokumente in Paperless-ngx

---

## Wohnheimverwaltung

Zimmerverwaltung für Nachwuchskräfte.

- Wohnheime mit Zimmern und Kapazitätsgrenzen
- Zimmerbelegung mit Ein- und Auszugsdaten
- Überschneidungsvalidierung bei Belegungen
- Zeitliche Zimmersperrungen (Wartung, Renovierung)
- Kalenderansicht der Belegung
- Automatische Generierung von Reservierungsbestätigungen (Word-Vorlagen)

---

## Organisationsstruktur

Abbildung der Behördenhierarchie.

- Mehrstufige Hierarchie: Behörde → Abteilung → Referatsgruppe → Referat → Sachgebiet
- Kapazitätsgrenzen je Einheit für die Einsatzplanung
- Standortverwaltung mit Adressen
- Darstellung als Baumstruktur

---

## Self-Service-Portal (Nachwuchskraft)

Eingeschränkte Ansicht für Auszubildende.

- Dashboard mit aktuellem und nächstem Praxiseinsatz
- Übersicht über Ausbildungsnachweise und Noten
- Lesezugriff auf eigene Stammdaten und Stationsplan
- Urlaubsanträge stellen und eigene Anträge einsehen
- Stornierungsantrag für genehmigte Urlaubsanträge stellen
- Lerntagsanträge stellen und einsehen
- Keine sonstige Bearbeitungsmöglichkeit

---

## Dokumente

Integration mit Paperless-ngx.

- Vorschau von PDF-Dokumenten direkt im Portal
- Download von Originaldateien

---

## Audit-Log

Lückenlose Nachvollziehbarkeit aller Datenänderungen.

- Protokollierung von Erstellen, Ändern und Löschen aller relevanten Objekte
- Filterbar nach Modell, Aktion, Benutzer und Zeitraum
- Vollständige Änderungshistorie pro Nachwuchskraft (für DSGVO-Auskunftsersuchen)
- Farbliche Kennzeichnung der Aktionstypen
- Speicherung von Vorher/Nachher-Werten als JSON
