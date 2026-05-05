# Workflows

Beschreibung der wichtigsten Abläufe im Azubi-Portal.

---

## 1. Praxiseinsatz-Workflow

Ein Praxiseinsatz wird durch zwei Datensätze abgebildet: den Einsatz selbst (`InternshipAssignment`) und — am Ende — eine separate Beurteilung (`Assessment`). Beide haben eigene Status-Maschinen.

```
InternshipAssignment:   Ausstehend → Angenommen
                                  ↘ Abgelehnt

Assessment (nach Einsatzende):   Ausstehend → Eingereicht → Bestätigt
```

**Schritte:**

1. **Planung** — Das Ausbildungsreferat erstellt einen Praxiseinsatz für eine Nachwuchskraft (Organisationseinheit, Praxistutor, Zeitraum). Das System prüft die Kapazität der Einheit. Der Einsatz wird mit Status **Ausstehend** angelegt.
2. **Benachrichtigung** — Der zuständige Praxistutor und ggf. der Hauptkoordinator erhalten automatisch eine E-Mail.
3. **Annahme / Ablehnung** — Das Ausbildungsreferat oder der Koordinator setzt den Einsatzstatus auf **Angenommen** oder **Abgelehnt**. Bei Ablehnung erhält die Nachwuchskraft eine Benachrichtigung.
4. **Erinnerung** — 7 Tage vor Beginn und Ende des Einsatzes wird der Praxistutor automatisch per E-Mail erinnert.
5. **Beurteilung (separater Vorgang)** — Nach dem Einsatz wird ein Beurteilungsformular freigeschaltet (siehe [Beurteilungs-Workflow](#10-beurteilungs-workflow)). Der Praxistutor trägt Bericht und Note ein und reicht ein → Status **Eingereicht**.
6. **Bestätigung** — Das Ausbildungsreferat prüft und bestätigt die eingereichte Beurteilung → Status **Bestätigt**. Der Einsatz gilt damit als abgeschlossen.

**Aufteilungsanfrage:**  
Ein Praxistutor kann eine Aufteilung des Einsatzes auf mehrere Einheiten beantragen. Das Ausbildungsreferat prüft und genehmigt oder lehnt die Anfrage ab.

---

## 2. Ausbildungsnachweis-Workflow

Wöchentliche Tätigkeitsnachweise der Nachwuchskräfte.

```
Entwurf → Eingereicht → Genehmigt
                      ↘ Abgelehnt → Entwurf (zur Korrektur)
```

**Schritte:**

1. **Erfassung** — Die Nachwuchskraft legt für eine Kalenderwoche einen Nachweis an und trägt täglich Art und Inhalt der Tätigkeit ein (Praxis / Schule / Urlaub / Krank / Sonstiges).
2. **Einreichen** — Nach Fertigstellung reicht die Nachwuchskraft den Nachweis ein.
3. **Prüfung** — Ausbildungsverantwortliche, Ausbildungsreferat oder Ausbildungsleitung prüfen den Nachweis.
4. **Genehmigung / Ablehnung** — Bei Ablehnung werden Korrekturhinweise hinterlegt; der Nachweis geht zurück in den Entwurfsstatus.
5. **Export** — Genehmigte Nachweise können als Word-Dokument exportiert werden.

---

## 3. Praxistutor-Bestätigungsworkflow

Neue Praxistutoren müssen bestätigt werden, bevor sie Einsätze erhalten.

```
Angelegt (ausstehend) → Bestätigt
```

1. Das Ausbildungsreferat legt einen neuen Praxistutor an.
2. Der Praxistutor wird per E-Mail informiert.
3. Das Ausbildungsreferat bestätigt den Praxistutor nach Prüfung.
4. Erst danach kann der Praxistutor Praxiseinsätzen zugewiesen werden.

---

## 4. Zuweisungsschreiben-Workflow

Automatisch generierte Dokumente für Praxiseinsätze und Lehrgangsblöcke.

```
Entwurf → Genehmigung ausstehend → Versendet
```

1. Das System generiert aus einer Word-Vorlage ein Zuweisungsschreiben (Briefkopf, Personaldaten, Einsatzdaten).
2. Das Schreiben wird zur Genehmigung vorgelegt.
3. Nach Genehmigung gilt es als versendet und wird in Paperless-ngx abgelegt.

---

## 5. Zimmerbelegung (Wohnheim)

```
Anfrage → Zimmerzuweisung → Reservierungsbestätigung
```

1. Die Hausverwaltung oder das Ausbildungsreferat weist einer Nachwuchskraft ein Zimmer zu (mit Ein- und Auszugsdatum).
2. Das System prüft auf Kapazitätsüberschreitung und Belegungsüberschneidungen.
3. Eine Reservierungsbestätigung wird als Word-Dokument generiert und in Paperless-ngx abgelegt.

---

## 6. Urlaubsantrag-Workflow

```
Portal / Referat → Ausstehend → Genehmigt → (Batch) → Urlaubsstelle bearbeitet
                             ↘ Abgelehnt
```

**Schritte:**

1. **Einreichung** — Die Nachwuchskraft stellt einen Antrag im Self-Service-Portal oder das Ausbildungsreferat erfasst ihn manuell.
2. **Entscheidung** — Das Ausbildungsreferat genehmigt oder lehnt den Antrag ab. Die Nachwuchskraft erhält eine E-Mail-Benachrichtigung.
3. **Batchversand** — Täglich um 08:00 Uhr bündelt Celery Beat alle genehmigten, noch nicht versendeten Anträge und sendet der Urlaubsstelle eine E-Mail mit einmaligem Bearbeitungslink.
4. **Urlaubsstelle** — Die Urlaubsstelle öffnet den Link (kein Login erforderlich), trägt den Resturlaub (aktuelles Jahr / Vorjahr) für jeden Antrag ein und schließt die Bearbeitung ab.
5. **Bestätigung** — Die Nachwuchskraft erhält eine automatische Benachrichtigung mit den eingetragenen Resturlaubstagen. Optional kann eine Word-Bestätigung heruntergeladen werden.

**Stornierung:**
- Nachwuchskraft oder Ausbildungsreferat kann einen Stornierungsantrag für genehmigte oder bearbeitete Anträge stellen.
- Stornierungsanträge durchlaufen denselben Genehmigungsworkflow und werden im nächsten Batch mit übermittelt.

---

## 7. Krankmeldungs-Workflow

```
Erfassung (offen) → Gesundmeldung (geschlossen)
```

**Schritte:**

1. **Erfassung** — Das Ausbildungsreferat erfasst eine Krankmeldung mit Typ (Selbstauskunft / K-Taste / Attest) und Startdatum (Vorauswahl: heute).
2. **Tagesbericht** — Täglich um 08:05 Uhr sendet Celery Beat einen Bericht an die Urlaubsstelle mit allen neuen Krank- und Gesundmeldungen seit dem letzten Bericht.
3. **Schließen** — Sobald die Nachwuchskraft gesund zurückkehrt, wird die Krankmeldung mit einem Enddatum geschlossen.
4. **Abwesenheitsampel** — Nach jeder Erfassung oder Schließung wird die Ampel automatisch neu berechnet. Bei einem Wechsel des Ampelstatus erhalten alle Mitglieder der Ausbildungsleitung eine E-Mail.

---

## 8. Lerntagsantrag-Workflow

```
Self-Service-Antrag → Ausstehend → Genehmigt
                               ↘ Abgelehnt
```

**Schritte:**

1. **Antrag** — Die Nachwuchskraft stellt über das Self-Service-Portal einen Antrag für ein bestimmtes Datum. Das System prüft das verbleibende Kontingent gemäß der konfigurierten StudyDayPolicy für das Berufsbild.
2. **Kontingentanzeige** — Die verbleibenden Lerntage (gesamt, pro Block, pro Woche oder pro Monat) werden angezeigt.
3. **Entscheidung** — Das Ausbildungsreferat genehmigt oder lehnt den Antrag ab. Die Nachwuchskraft wird per E-Mail benachrichtigt.

---

## 9. Inventar- und Quittungs-Workflow

```
Ausgabe → Quittung generiert → Papierquittung hochladen → Dokument zugeordnet
       ↘ Rückgabe
```

**Schritte:**

1. **Ausgabe** — Ein Gegenstand wird einer Nachwuchskraft zugewiesen (mit Zeitstempel und optionalen Notizen). Der Status des Gegenstands wechselt auf „ausgegeben".
2. **Quittungsgenerierung** — Das System generiert automatisch eine Ausgabequittung als PDF aus einer Word-Vorlage. Die Quittung enthält einen QR-Code mit der eindeutigen Ausgabe-ID.
3. **Papierquittung** — Die ausgedruckte, unterschriebene Quittung kann als Scan hochgeladen werden. Der QR-Code wird automatisch ausgelesen und die Datei der Ausgabe zugeordnet.
4. **Paperless** — Generierte Dokumente werden in Paperless-ngx abgelegt.
5. **Rückgabe** — Bei Rückgabe wird ein Rückgabezeitpunkt gesetzt; der Gegenstandsstatus wechselt zurück auf „verfügbar".

---

## 10. Beurteilungs-Workflow

```
Beurteilungsformular erstellt → Link versendet → Externe Bewertung abgegeben → Bestätigt
```

**Schritte:**

1. **Formular** — Das Ausbildungsreferat erstellt einen Bewertungsauftrag für einen Praxiseinsatz. Das System generiert einen einmaligen Token-Link.
2. **Versand** — Der Link wird an den externen Bewerter (z. B. Praxistutor) per E-Mail übermittelt.
3. **Bewertung** — Der Bewerter öffnet das Formular ohne Login und füllt die Kriterien gemäß der konfigurierten Bewertungsvorlage aus.
4. **Bestätigung** — Das Ausbildungsreferat prüft und bestätigt die eingegangene Beurteilung.

---

## 11. Automatische Hintergrundaufgaben

Fünf Aufgaben laufen täglich ohne manuelle Auslösung:

| Aufgabe | Zeitpunkt | Beschreibung |
|---|---|---|
| Praxiseinsatz-Erinnerungen | 07:00 Uhr | Benachrichtigt Praxistutoren 7 Tage vor Beginn oder Ende eines Einsatzes |
| Ausbildungsnachweis-Erinnerungen | 07:00 Uhr | Erinnert Nachwuchskräfte an fehlende oder nicht eingereichte Ausbildungsnachweise |
| Urlaubsantragspaket | 08:00 Uhr | Bündelt genehmigte Urlaubsanträge und sendet sie per E-Mail an die Urlaubsstelle |
| Krankmeldungsbericht | 08:05 Uhr | Sendet täglichen Bericht über neue Krank- und Gesundmeldungen an die Urlaubsstelle |
| Anonymisierung | 12:00 Uhr | Anonymisiert Stammdaten inaktiver Nachwuchskräfte gemäß Datenschutzvorgaben |

Alle Aufgaben werden über **Celery Beat** via Redis gesteuert und laufen als eigener Docker-Container. Die Ausführungszeiten sind über **SiteConfiguration** im Django-Admin-Bereich konfigurierbar.

Die Urlaubsaufgaben können manuell über Management Commands ausgelöst werden:

```bash
python manage.py send_vacation_batch [--dry-run]
python manage.py send_sick_leave_report [--dry-run]
```
