# Admin-Leitfaden

Dieser Leitfaden richtet sich an die Ausbildungsleitung und Admins, die das Portal im Tagesbetrieb verwalten. Er ergänzt die [Installation](installation.md) und das [Backup-Konzept](backup.md).

---

## Inhalt

1. [Benutzer und Rollen verwalten](#1-benutzer-und-rollen-verwalten)
2. [Stammdaten pflegen](#2-stammdaten-pflegen)
3. [E-Mail-Vorlagen anpassen](#3-e-mail-vorlagen-anpassen)
4. [Word-Vorlagen pflegen](#4-word-vorlagen-pflegen)
5. [Hintergrundaufgaben überwachen](#5-hintergrundaufgaben-überwachen)
6. [Audit-Log nutzen](#6-audit-log-nutzen)
7. [Häufige Wartungsaufgaben](#7-häufige-wartungsaufgaben)
8. [Datenschutz & Anonymisierung](#8-datenschutz--anonymisierung)

---

## 1. Benutzer und Rollen verwalten

### Neuen Benutzer anlegen

1. `/admin/auth/user/add/` öffnen
2. Benutzername, Passwort vergeben
3. Im zweiten Schritt: Vorname, Nachname, E-Mail-Adresse erfassen
4. **Gruppen** zuweisen — eine oder mehrere der sieben Rollen
5. Bei Hauptkoordinatoren zusätzlich: über `/instructor/coordination/` einer Koordinationsgruppe zuweisen

> Mitglieder der Gruppe `ausbildungsleitung` haben automatisch Vollzugriff. Ein zusätzlicher Django-Staff-Status ist nur erforderlich, wenn der Nutzer auch direkt im Django-Admin (`/admin/`) arbeiten soll.

### Rollen kombinieren

Ein Benutzer kann mehreren Gruppen angehören. Die Berechtigungen addieren sich. Beispiel: `ausbildungskoordination` + `ausbildungsverantwortliche` ergibt einen Hauptkoordinator, der auch Ausbildungsnachweise prüfen kann.

### Account deaktivieren

Im Admin den Haken bei **„Aktiv"** entfernen. Das Konto bleibt erhalten, kann sich aber nicht mehr einloggen. Für endgültige Entfernung: Account löschen — dann gehen verknüpfte Aktionen im Audit-Log auf „Gelöschter Benutzer".

---

## 2. Stammdaten pflegen

| Bereich | Pfad | Verantwortlich |
|---|---|---|
| Berufsbilder | `/career/` | Ausbildungsleitung |
| Organisationsstruktur | `/organisation/` | Ausbildungsleitung |
| Standorte | `/organisation/locations/` | Ausbildungsleitung |
| Praxistutoren | `/instructor/` | Ausbildungsreferat |
| Koordinationsgruppen | `/instructor/coordination/` | Ausbildungsleitung |
| Wohnheime & Zimmer | `/dormitory/` | Hausverwaltung / Ausbildungsleitung |
| Inventarkategorien | `/inventory/categories/` | Ausbildungsreferat |
| Bewertungsvorlagen | `/assessment/` | Ausbildungsleitung |
| Interventionskategorien | `/intervention/categories/` | Ausbildungsleitung |
| Lerntags-Regeln | `/admin/studyday/studydaypolicy/` | Ausbildungsleitung |
| Onboarding-Vorlagen | `/admin/student/onboardingtemplate/` | Ausbildungsleitung |

### Reihenfolge beim Erstinstall

Halten Sie die Reihenfolge ein, da spätere Datensätze auf die früheren verweisen:

```
Berufsbilder → Organisationsstruktur → Standorte → Praxistutoren →
Koordinationsgruppen → Bewertungsvorlagen → Wohnheime → Inventar
```

---

## 3. E-Mail-Vorlagen anpassen

Pfad: `/admin/notifications/notificationtemplate/`

Jede Benachrichtigung hat einen technischen Schlüssel (z. B. `vacation_approved`) und einen Betreff/Body. Platzhalter sind Django-Template-Tags.

**Häufig verwendete Platzhalter:**

| Platzhalter | Beschreibung |
|---|---|
| `{{ student.full_name }}` | Voller Name der Nachwuchskraft |
| `{{ student.azubi_id }}` | Eindeutige ID (`azubi-XXXX`) |
| `{{ site_url }}` | Basis-URL (aus `SITE_BASE_URL`) |
| `{{ link }}` | Direktlink zum betroffenen Objekt |
| `{{ user.first_name }}` | Empfänger-Vorname (z. B. Praxistutor) |

> Nach Änderung sofort eine Test-Mail über den Knopf „Test versenden" auslösen.

---

## 4. Word-Vorlagen pflegen

Word-Vorlagen werden für automatische Schreiben verwendet:

| Vorlagentyp | Verwendet für | Pfad im Admin |
|---|---|---|
| Zuweisungsschreiben | Lehrgangsblöcke | `/admin/course/letter…` |
| Stationsschreiben | Praxiseinsätze | `/admin/course/letter…` |
| Urlaubsbestätigung | Nach Bearbeitung durch Urlaubsstelle | `/admin/absence/absencesettings/` |
| Reservierungsbestätigung Wohnheim | Zimmerbelegung | `/admin/dormitory/letter…` |
| Inventarquittung | Ausgabe von Gegenständen | `/admin/inventory/category/` |

**Platzhaltersyntax** in Word: Jinja-Stil mit `{{ … }}`. Verfügbare Variablen werden im jeweiligen Admin-Hinweistext gelistet.

**Vorgehen:**
1. Bestehende Vorlage als Muster herunterladen.
2. In Word anpassen (Logo, Briefkopf, Formulierungen).
3. **Genaue Schreibweise der Platzhalter beibehalten**, sonst bleibt das Feld leer.
4. Hochladen und einmal testen — z. B. einen Testeinsatz in einer Test-DB anlegen.

---

## 5. Hintergrundaufgaben überwachen

Fünf tägliche Aufgaben laufen automatisch:

| Task | Default-Zeit | Wirkung |
|---|---|---|
| Praxiseinsatz-Erinnerungen | 07:00 | Mail an Praxistutoren 7 Tage vor Beginn/Ende |
| Ausbildungsnachweis-Erinnerungen | 07:00 | Mail an Nachwuchskräfte mit fehlenden Nachweisen |
| Urlaubsantragspaket | 08:00 | Tagesbatch an die Urlaubsstelle |
| Krankmeldungsbericht | 08:05 | Tagesbericht über neue Krank-/Gesundmeldungen |
| Anonymisierung | 12:00 | Inaktive Nachwuchskräfte werden anonymisiert |
| Backup-Tasks | 02:00–02:45 | DB- und Mediendump, Rotation |

### Manuell auslösen (zum Testen)

```bash
docker compose exec app python manage.py send_internship_reminders
docker compose exec app python manage.py send_vacation_batch --dry-run
docker compose exec app python manage.py send_sick_leave_report --dry-run
docker compose exec app python manage.py anonymize_inactive_students
```

`--dry-run` zeigt nur, was gesendet würde.

### Zeitplan ändern

`/admin/portal/siteconfiguration/` → entsprechende Felder anpassen. Anschließend:

```bash
docker compose restart celery_beat
```

Erst dann übernimmt der Beat-Container den neuen Plan.

### Fehler in Tasks

```bash
docker compose logs celery_worker | tail -100
docker compose logs celery_beat | tail -50
```

Erfolgreiche und fehlgeschlagene Backups landen zusätzlich im Audit-Log.

---

## 6. Audit-Log nutzen

Pfad: `/auditlog/`

Filterbar nach:
- **Modell** (Student, Vacation, Internship …)
- **Aktion** (Erstellt, Geändert, Gelöscht, Backup, Anonymisierung)
- **Benutzer**
- **Zeitraum**

### DSGVO-Auskunftsersuchen

Auf der Detailseite einer Nachwuchskraft gibt es einen Tab „Änderungshistorie", der nur die Einträge zu dieser Person zeigt. Diese Liste lässt sich exportieren.

### Eigene Aktivität nachvollziehen

Im Audit-Log nach dem eigenen Benutzer filtern, um nachzuvollziehen, welche Änderungen man wann selbst vorgenommen hat.

---

## 7. Häufige Wartungsaufgaben

### Logs ansehen

```bash
docker compose logs -f --tail=200 app
docker compose logs -f --tail=200 celery_worker
docker compose logs -f --tail=200 celery_beat
```

### Container-Status

```bash
docker compose ps
docker stats --no-stream
```

### Datenbank-Shell (vorsichtig)

```bash
docker compose exec db psql -U "$DB_USER" -d "$DB_NAME"
```

### Django-Shell

```bash
docker compose exec app python manage.py shell
```

### Statische Dateien neu sammeln

```bash
docker compose exec app python manage.py collectstatic --noinput
docker compose restart app
```

### Container neu starten

```bash
docker compose restart app
docker compose restart celery_worker
docker compose restart celery_beat
```

### Vollständiger Stop und Neustart

```bash
docker compose down
docker compose up -d
```

> `docker compose down -v` löscht **auch alle Volumes**, also die Datenbank! Niemals ohne aktuelles Backup.

---

## 8. Datenschutz & Anonymisierung

### Automatische Anonymisierung

Inaktive Nachwuchskräfte (Status „inaktiv" oder „Ausbildung beendet") werden täglich um 12:00 Uhr automatisch anonymisiert: Stammdaten werden überschrieben, sobald die in der `SiteConfiguration` definierte Frist abgelaufen ist.

### Manuell anonymisieren

Ausbildungsleitung: Auf der Detailseite einer Nachwuchskraft gibt es den Knopf „Anonymisieren" (rot). Wirkung:

- Klarname → `anonymisiert-XXXX`
- Geburtsdatum, Adresse, E-Mail, Telefon → leer
- Bilder, Notizen, Kontakthistorie → entfernt
- Audit-Log bleibt vollständig (Pseudonym wird verwendet)

Diese Aktion ist **nicht rückgängig zu machen**.

### Was erhalten bleibt

- Aggregierte/historische Daten (für Statistik)
- Ausbildungsnachweise (anonymisiert)
- Audit-Log-Einträge (mit Pseudonym)

### Einwilligungen und Sperrvermerke

Nachwuchskräfte mit Sperrvermerk (z. B. nach §51 BMG) können im Detail mit dem Feld „Sperrvermerk" markiert werden. Die Auswirkung muss in der Organisation dokumentiert werden — das Portal selbst ändert das Verhalten nicht automatisch.