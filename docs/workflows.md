# Fachliche Abläufe

Dieser Leitfaden beschreibt die wichtigsten Abläufe im Azubi-Portal aus fachlicher Sicht — was passiert wann, wer ist beteiligt und was die Nachwuchskraft beziehungsweise das Ausbildungsreferat sieht. Die zugrunde liegenden Genehmigungs-Stufen, Fristen und Eskalationen werden zentral über die [Genehmigungs-Workflows](workflow-engine.md) verwaltet; dort können Sie die Abläufe anpassen, ohne den Programm-Code zu ändern.

---

## Inhalt

1. [Praxiseinsatz](#1-praxiseinsatz)
2. [Stationsbeurteilung](#2-stationsbeurteilung)
3. [Ausbildungsnachweis](#3-ausbildungsnachweis)
4. [Änderungsantrag zu einem Praxiseinsatz](#4-änderungsantrag-zu-einem-praxiseinsatz)
5. [Praxistutor:in bestätigen](#5-praxistutorin-bestätigen)
6. [Lerntag-Antrag](#6-lerntag-antrag)
7. [Urlaubs- und Stornierungsantrag](#7-urlaubs--und-stornierungsantrag)
8. [Krankmeldung](#8-krankmeldung)
9. [Ankündigung veröffentlichen](#9-ankündigung-veröffentlichen)
10. [Zimmerbelegung im Wohnheim](#10-zimmerbelegung-im-wohnheim)
11. [Inventar-Ausgabe und Quittung](#11-inventar-ausgabe-und-quittung)
12. [Zuweisungsschreiben](#12-zuweisungsschreiben)
13. [Automatische Hintergrundaufgaben](#13-automatische-hintergrundaufgaben)

---

## 1. Praxiseinsatz

Ein Praxiseinsatz ordnet eine Nachwuchskraft für einen Zeitraum einer Organisationseinheit zu. Am Ende steht eine [Stationsbeurteilung](#2-stationsbeurteilung) als eigenständiger Folgevorgang.

**Beteiligte:** Ausbildungsreferat (planen), zuständige Ausbildungskoordination (annehmen / ablehnen), Praxistutor:in (informiert), Nachwuchskraft (informiert).

### Ablauf

1. **Planung** — Das Ausbildungsreferat erfasst den Einsatz (Einheit, Praxistutor:in, Zeitraum, Standort). Das Portal prüft die Kapazität der Einheit.
2. **Benachrichtigung** — Praxistutor:in und Koordination erhalten automatisch eine E-Mail.
3. **Annahme oder Ablehnung** — Die zuständige Koordination entscheidet. Wird nicht innerhalb von 5 Tagen entschieden, eskaliert das Portal an die Ausbildungsleitung.
4. **Termin-Erinnerungen** — 7 Tage vor Beginn und vor Ende erhält die Praxistutor:in eine Erinnerungs-E-Mail.
5. **Beurteilung** — Nach Einsatzende startet automatisch der Beurteilungs-Vorgang.

### Sonderfälle

- **Einsatz teilen / verschieben / Station ändern** — Änderungen während eines laufenden Einsatzes laufen über den [Änderungsantrag](#4-änderungsantrag-zu-einem-praxiseinsatz).
- **Ablehnung** — Endgültig; das Ausbildungsreferat legt bei Bedarf einen neuen Einsatz an.

> Stufen, Fristen und Eskalation des Genehmigungs-Workflows sind im Workflow `internship_assignment` konfigurierbar. Siehe [Workflow-Leitfaden](workflow-engine.md#9-mitgelieferte-workflows).

---

## 2. Stationsbeurteilung

Am Ende jedes Praxiseinsatzes erstellt das Ausbildungsreferat einen Beurteilungs-Vorgang. Die Praxistutor:in bewertet die Nachwuchskraft anhand der für das Berufsbild hinterlegten Vorlage, die zuständige Koordination zeichnet zur Kenntnis ab und das Ausbildungsreferat bestätigt am Ende verbindlich.

**Beteiligte:** Praxistutor:in (extern, ohne Login), Ausbildungskoordination (Kenntnisnahme), Ausbildungsreferat (Bestätigung).

### Ablauf

1. **Versand** — Das Ausbildungsreferat schickt der Praxistutor:in einen tokenbasierten Link per E-Mail (kein Login erforderlich).
2. **Bewertung** — Die Praxistutor:in füllt das Formular aus und reicht es ein. Der Token wird danach rotiert, damit der Link nicht erneut geöffnet werden kann. Frist: 21 Tage; bei Überschreitung eskaliert das Portal an die zuständige Koordination.
3. **Kenntnisnahme durch die Koordination** — Die Koordination öffnet die Beurteilung in ihrem Bereich und klickt auf „Zur Kenntnis nehmen". Frist: 7 Tage. Wird sie nicht abgezeichnet, springt der Workflow automatisch zur Bestätigung weiter.
4. **Verbindliche Bestätigung** — Das Ausbildungsreferat oder die Ausbildungsleitung bestätigt die Beurteilung. Bestätigt das Referat, bevor die Koordination abgezeichnet hat, wird die Kenntnisnahme implizit miterledigt (im Verlauf nachvollziehbar).
5. **Signiertes PDF** — Nach der Bestätigung steht ein PDF mit der Beurteilung und den Signaturen zur Verfügung.

> Selbstbeurteilung: Parallel zur Praxistutor-Beurteilung füllt die Nachwuchskraft im Self-Service-Portal eine Selbstbeurteilung aus. Beide werden in der Detailansicht nebeneinander dargestellt.

---

## 3. Ausbildungsnachweis

Wöchentliche Tätigkeitsnachweise der Nachwuchskraft. Bei Ablehnung sieht die Nachwuchskraft die Korrekturhinweise direkt im Nachweis und reicht den überarbeiteten Nachweis erneut ein.

**Beteiligte:** Nachwuchskraft (erfasst, reicht ein), Ausbildungsleitung (prüft).

### Ablauf

1. **Erfassung** — Die Nachwuchskraft legt für eine Kalenderwoche einen Nachweis an und trägt pro Tag Art (Praxis / Schule / Urlaub / Krank / Sonstiges) und Inhalt der Tätigkeit ein.
2. **Einreichen** — Nach Fertigstellung reicht die Nachwuchskraft den Nachweis ein.
3. **Prüfung** — Die Ausbildungsleitung sieht alle eingereichten Nachweise und entscheidet. Frist: 7 Tage; bei Überschreitung wird erinnert.
4. **Korrektur-Rücklauf** — Bei einer Ablehnung trägt die Leitung tagesbezogene Korrekturhinweise ein. Der Nachweis kehrt zur Nachwuchskraft zurück, die ihn überarbeitet und erneut einreicht. Der Workflow läuft anschließend komplett neu durch; alle Revisionen bleiben im Verlauf sichtbar.
5. **Export** — Genehmigte Nachweise können als Word-Dokument exportiert werden.

> Eine optionale Vorstufe „Bestätigung durch aktuelle Praxistutor:in" (per Token-Link) lässt sich in den [Workflow-Einstellungen](workflow-engine.md#3-eine-stufe-konfigurieren) jederzeit ergänzen.

---

## 4. Änderungsantrag zu einem Praxiseinsatz

Nach Annahme eines Einsatzes können Koordination und Ausbildungsreferat Änderungen anstoßen — Verschiebungen, Stationswechsel, Standortwechsel, Teilen, Stornieren oder einen einfachen Wechsel der Praxistutor:in.

**Beteiligte:** Koordination (stellt Antrag), Ausbildungsleitung (entscheidet, sofern genehmigungspflichtig).

### Ablauf

1. **Antrag** — Die Koordination wählt den Änderungstyp und füllt die typabhängigen Felder aus.
2. **Genehmigungs-Prüfung** — Das Portal prüft, ob der Änderungstyp genehmigungspflichtig ist.
   - **Praxistutor:in wechseln** wird direkt durchgewunken (kein Antrag, keine Wartezeit).
   - Alle anderen Typen gehen an die Ausbildungsleitung.
3. **Entscheidung** — Die Ausbildungsleitung genehmigt oder lehnt ab. Frist: 3 Tage; bei Überschreitung wird erinnert.
4. **Anwendung** — Bei Genehmigung wendet das Portal die Änderung automatisch auf den Einsatz an (z. B. neuer Zeitraum, neue Einheit) und sendet Beteiligte E-Mail-Updates.

> Die Liste der genehmigungspflichtigen Änderungstypen lässt sich über die Pre-Condition des Workflows `assignment_change_request` einschränken — z. B. nur dann genehmigen lassen, wenn der Einsatzbeginn weniger als 14 Tage entfernt ist (`target.requires_approval and target.is_short_notice`).

---

## 5. Praxistutor:in bestätigen

Neue Praxistutor:innen müssen einmalig durch die Ausbildungsleitung bestätigt werden, bevor sie Einsätzen zugewiesen werden können. Nach der Bestätigung versendet das Portal automatisch ein Bestellungsschreiben.

**Beteiligte:** Ausbildungsreferat (legt an), Ausbildungsleitung (bestätigt), Praxistutor:in (Bestellungsschreiben).

### Ablauf

1. **Anlegen** — Das Ausbildungsreferat erfasst Vorname, Nachname, E-Mail, Einheit, Standort und zuständige Berufsbilder.
2. **Benachrichtigung** — Die Ausbildungsleitung erhält eine interne Benachrichtigung. Frist für die Bestätigung: 5 Tage; bei Überschreitung wird erinnert.
3. **Bestätigung** — Die Leitung prüft den Datensatz und bestätigt. Das Bestellungsschreiben wird im Hintergrund versendet.
4. **Verfügbar für Einsätze** — Erst nach der Bestätigung wird die Praxistutor:in in den Einsatz-Formularen auswählbar.

Wird ein angelegter Praxistutor doch nicht bestätigt, sondern gelöscht, bleibt der Verlauf des Workflows als „abgebrochen" erhalten.

---

## 6. Lerntag-Antrag

Nachwuchskräfte können über das Self-Service-Portal Lerntage zur Prüfungsvorbereitung beantragen. Das Portal prüft das verbleibende Kontingent gemäß der für das Berufsbild hinterlegten Lerntage-Regel.

**Beteiligte:** Nachwuchskraft (stellt Antrag), Ausbildungsreferat (entscheidet, eskalierbar an Leitung).

### Ablauf

1. **Antrag** — Die Nachwuchskraft wählt im Self-Service-Portal ein Datum. Das Portal zeigt das verbleibende Kontingent (gesamt, pro Block, pro Woche oder pro Monat — je nach Regel).
2. **Prüfung** — Das Ausbildungsreferat sieht den Antrag in der Übersicht. Frist: 5 Tage; danach eskaliert der Antrag an die Ausbildungsleitung.
3. **Entscheidung** — Genehmigung oder Ablehnung. Die Nachwuchskraft wird per E-Mail benachrichtigt; ein Ablehnungsgrund kann mitgegeben werden.

> Die Lerntags-Regeln pro Berufsbild verwaltet die Ausbildungsleitung im Admin-Bereich (siehe [Admin-Leitfaden](admin-leitfaden.md#2-stammdaten-pflegen)).

---

## 7. Urlaubs- und Stornierungsantrag

Urlaubsanträge werden zweistufig bearbeitet: zuerst entscheidet das Ausbildungsreferat über die Genehmigung, anschließend trägt die Urlaubsstelle den verbleibenden Resturlaub ein.

**Beteiligte:** Nachwuchskraft (stellt Antrag im Portal) oder Ausbildungsreferat (manuelle Erfassung), Urlaubsstelle (übernimmt nach Genehmigung).

### Ablauf

1. **Einreichung** — Die Nachwuchskraft beantragt im Self-Service-Portal einen Zeitraum, oder das Ausbildungsreferat erfasst den Antrag manuell für die Nachwuchskraft.
2. **Entscheidung durch das Ausbildungsreferat** — Genehmigung oder Ablehnung. Frist: 5 Tage; danach eskaliert an die Ausbildungsleitung. Die Nachwuchskraft erhält die Entscheidung per E-Mail.
3. **Bündelung für die Urlaubsstelle** — Täglich um 08:00 Uhr stellt das Portal aus allen genehmigten, noch nicht weitergegebenen Anträgen ein Paket zusammen und sendet der Urlaubsstelle eine E-Mail mit einem einmaligen Bearbeitungslink (kein Login erforderlich).
4. **Resturlaub eintragen** — Die Urlaubsstelle öffnet den Link, trägt pro Antrag den Resturlaub (aktuelles Jahr / Vorjahr) und ggf. abweichende Arbeitstage ein. Frist: 10 Tage; bei Überschreitung wird erinnert.
5. **Abschluss** — Die Nachwuchskraft erhält eine Benachrichtigung mit den eingetragenen Werten. Optional steht eine Word-Urlaubsbestätigung zum Download bereit.

### Stornierung

Bereits genehmigte oder von der Urlaubsstelle bearbeitete Urlaube können von der Nachwuchskraft oder vom Ausbildungsreferat storniert werden. Der Stornierungsantrag durchläuft denselben Workflow wie der ursprüngliche Antrag und reist mit dem nächsten Tagespaket zur Urlaubsstelle.

> Die Urlaubsstelle hat aktuell **kein** eigenes Portal-Login — sie arbeitet ausschließlich über den Token-Link aus der Tages-E-Mail. Eine zukünftige Umstellung auf echte Logins (Rolle `holiday_office`) ist vorbereitet.

---

## 8. Krankmeldung

Krankmeldungen werden direkt vom Ausbildungsreferat erfasst und nicht genehmigt. Sie speisen die Abwesenheitsampel und werden täglich gesammelt an die Urlaubsstelle gemeldet.

**Beteiligte:** Ausbildungsreferat (erfasst und schließt), Ausbildungsleitung (Ampel-Wechsel-Benachrichtigung), Urlaubsstelle (Tagesbericht).

### Ablauf

1. **Erfassung** — Das Ausbildungsreferat legt eine Krankmeldung mit Typ (Selbstauskunft / K-Taste / Attest) und Startdatum an. Vorbelegung: heute.
2. **Tagesbericht** — Täglich um 08:05 Uhr versendet das Portal an die Urlaubsstelle einen Bericht über alle neuen Krank- und Gesundmeldungen seit dem letzten Bericht.
3. **Schließen** — Sobald die Nachwuchskraft gesund zurückkehrt, wird die Krankmeldung mit einem Enddatum geschlossen.
4. **Abwesenheitsampel** — Nach jeder Erfassung oder Schließung wird die Ampel der Nachwuchskraft automatisch neu berechnet. Wechselt der Status, erhalten alle Mitglieder der Ausbildungsleitung eine E-Mail.

> Krankmeldungen durchlaufen bewusst keinen Genehmigungs-Workflow — sie sind reine Erfassungen.

---

## 9. Ankündigung veröffentlichen

Über das Modul Ankündigungen erreichen Mitteilungen die Nachwuchskräfte gezielt nach Kurs, Berufsbild, Koordination, Laufbahn oder als Einzelansprache. Wer eine Ankündigung veröffentlichen darf, regelt eine Berechtigung; ob die Veröffentlichung **vorher freigegeben** werden muss, hängt vom Profil-Haken „Freigabe erforderlich" der verfassenden Person ab.

**Beteiligte:** Sachbearbeitung im Ausbildungsreferat oder Ausbildungsleitung (verfasst), Ausbildungsleitung (gibt frei, sofern erforderlich), Nachwuchskräfte (Empfänger:innen).

### Ablauf

1. **Entwurf** — Die verfassende Person legt Titel, Inhalt, Zielgruppe und optional Anhänge an. Optional: Lesebestätigung verpflichtend.
2. **Veröffentlichungs-Anstoß** — Mit Klick auf „Veröffentlichen" prüft das Portal den Profil-Haken „Freigabe erforderlich":
   - Trägt das Konto den Haken (Standard für neue Konten), startet ein Freigabe-Workflow. Die Ankündigung bleibt zunächst Entwurf.
   - Trägt das Konto den Haken **nicht** (z. B. dauerhaft vertrauenswürdige Sachbearbeitung oder die Ausbildungsleitung selbst), wird sofort veröffentlicht.
3. **Freigabe durch die Ausbildungsleitung** — Frist: 3 Tage; bei Überschreitung wird erinnert. Eine Ablehnung enthält eine Anmerkung; die Ankündigung kehrt zur Verfasser:in zurück, die sie überarbeiten und erneut einreichen kann.
4. **Versand** — Nach Veröffentlichung erstellt das Portal Empfänger-Datensätze und schickt optional E-Mails. Im Portal sehen Nachwuchskräfte die Ankündigung in ihrer Übersicht; lese- bzw. bestätigungspflichtige Ankündigungen werden besonders markiert.

> Den Profil-Haken „Freigabe erforderlich" verwaltet die Ausbildungsleitung in der [Kontoverwaltung](admin-leitfaden.md#1-benutzer-und-rollen-verwalten).

---

## 10. Zimmerbelegung im Wohnheim

```
Zuweisung erfassen → Verfügbarkeit prüfen → Reservierungsbestätigung
```

1. Hausverwaltung oder Ausbildungsreferat weist einer Nachwuchskraft ein Zimmer mit Ein- und Auszugsdatum zu.
2. Das Portal prüft auf Kapazitätsüberschreitung und Belegungsüberschneidungen.
3. Eine Reservierungsbestätigung wird als Word-Dokument generiert und in Paperless-ngx abgelegt.

> Zimmerbelegungen durchlaufen keinen Genehmigungs-Workflow; die fachliche Prüfung erfolgt durch die Hausverwaltung beim Anlegen.

---

## 11. Inventar-Ausgabe und Quittung

```
Ausgabe erfassen → Quittung erzeugen → Papier-Scan zuordnen → Rückgabe
```

1. **Ausgabe** — Ein Gegenstand wird einer Nachwuchskraft mit Zeitstempel und optionalen Notizen zugewiesen. Der Gegenstandsstatus wechselt auf „ausgegeben".
2. **Quittung generieren** — Das Portal erstellt automatisch eine PDF-Quittung aus der Word-Vorlage. Sie enthält einen QR-Code mit der eindeutigen Ausgabe-ID.
3. **Papier-Quittung** — Die unterschriebene Quittung wird gescannt und hochgeladen. Der QR-Code wird automatisch ausgelesen und die Datei der Ausgabe zugeordnet.
4. **Archivierung** — Generierte Dokumente werden in Paperless-ngx abgelegt.
5. **Rückgabe** — Bei der Rückgabe wird der Rückgabezeitpunkt erfasst; der Gegenstand wechselt zurück auf „verfügbar".

---

## 12. Zuweisungsschreiben

Automatisch generierte Dokumente begleiten Praxiseinsätze und Lehrgangsblöcke.

1. Das Portal generiert aus einer Word-Vorlage ein Zuweisungsschreiben (Briefkopf, Personaldaten, Einsatzdaten).
2. Nach interner Freigabe gilt das Schreiben als versendet.
3. Das fertige Dokument wird in Paperless-ngx abgelegt.

---

## 13. Automatische Hintergrundaufgaben

Diese Aufgaben laufen täglich ohne manuelle Auslösung:

| Aufgabe | Zeitpunkt | Beschreibung |
|---|---|---|
| Praxiseinsatz-Erinnerungen | 07:00 Uhr | Benachrichtigt Praxistutor:innen 7 Tage vor Beginn oder Ende eines Einsatzes |
| Ausbildungsnachweis-Erinnerungen | 07:00 Uhr | Erinnert Nachwuchskräfte an fehlende oder nicht eingereichte Nachweise |
| Urlaubsantragspaket | 08:00 Uhr | Bündelt genehmigte Urlaubsanträge und sendet sie an die Urlaubsstelle |
| Krankmeldungsbericht | 08:05 Uhr | Sendet täglichen Bericht über neue Krank- und Gesundmeldungen an die Urlaubsstelle |
| Workflow-Erinnerungen & Eskalationen | stündlich | Versendet Erinnerungen vor Fristablauf und setzt Eskalationen nach Fristablauf um (siehe [Genehmigungs-Workflows](workflow-engine.md#6-fristen-erinnerungen-eskalation)) |
| Anonymisierung | 12:00 Uhr | Anonymisiert Stammdaten inaktiver Nachwuchskräfte gemäß Datenschutzvorgaben |

Alle Aufgaben werden über **Celery Beat** via Redis gesteuert und laufen als eigener Docker-Container. Die Ausführungszeiten sind über die *Site-Konfiguration* im Admin-Bereich anpassbar.

Die Urlaubs- und Krankmeldungs-Aufgaben lassen sich für Tests auch manuell auslösen:

```bash
python manage.py send_vacation_batch [--dry-run]
python manage.py send_sick_leave_report [--dry-run]
```
