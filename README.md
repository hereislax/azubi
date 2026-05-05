![logo_text.svg](static/img/logo_text.svg)

# Azubi-Portal

Webbasierte Verwaltungsanwendung für Nachwuchskräfte in Behörden und öffentlichen Organisationen. Das Portal begleitet Auszubildende vom Eintritt bis zum Abschluss und koordiniert alle beteiligten Personen und Prozesse.

Lizenziert unter the [EUPL v1.2](LICENSE).

**Kernfunktionen:** Nachwuchskräfteverwaltung · Kurs- und Einsatzplanung · Ausbildungsnachweise · Abwesenheitsmanagement · Lerntagsanträge · Wohnheimverwaltung · Inventar · Beurteilungen · Interventionen · Bekanntmachungen · Audit-Log

---

## Voraussetzungen

- [Docker](https://docs.docker.com/get-docker/) (inkl. Docker Compose Plugin)
- Zugang zu einer laufenden [Paperless-ngx](https://docs.paperless-ngx.com/)-Instanz

---

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/hereislax/azubi.git
cd Azubi
```

### 2. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Anschließend `.env` mit einem Texteditor öffnen und alle Werte befüllen (siehe [Konfigurationsreferenz](#konfigurationsreferenz) weiter unten).

### 3. App starten

```bash
docker compose up --build -d
```

Beim ersten Start werden automatisch alle Datenbankmigrationen ausgeführt.

Die App ist anschließend unter `http://localhost` erreichbar.

### 4. Superuser anlegen

```bash
docker compose exec app python manage.py createsuperuser
```

### 5. Grundkonfiguration im Admin-Bereich

Nach dem ersten Login unter `/admin/` folgende Einstellungen vornehmen:

- **SiteConfiguration** — Basis-URL der Instanz, Anonymisierungszeitplan, Erinnerungszeiten
- **AbsenceSettings** — E-Mail-Adresse der Urlaubsstelle, Bundesland für Feiertagsberechnung
- **NotificationTemplate** — E-Mail-Vorlagen für alle Ereignistypen prüfen und anpassen

---

## Konfigurationsreferenz

Alle Einstellungen werden über die `.env`-Datei gesetzt.

### Django

| Variable | Beschreibung | Beispiel |
|---|---|---|
| `SECRET_KEY` | Kryptografischer Schlüssel – muss geheim und einzigartig sein | Zufälligen Wert generieren (s.u.) |
| `DEBUG` | Debug-Modus – in Produktion immer `False` | `False` |
| `ALLOWED_HOSTS` | Kommagetrennte Liste erlaubter Hostnamen | `meine-domain.de,www.meine-domain.de` |
| `CSRF_TRUSTED_ORIGINS` | Vertrauenswürdige Ursprünge für HTTPS-Proxies | `https://meine-domain.de` |
| `SITE_BASE_URL` | Basis-URL der Instanz (für Links in E-Mails) | `https://meine-domain.de` |

**SECRET_KEY generieren:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Datenbank

| Variable | Beschreibung | Standard |
|---|---|---|
| `DB_NAME` | Name der PostgreSQL-Datenbank | `azubi` |
| `DB_USER` | Datenbankbenutzer | `azubi` |
| `DB_PASSWORD` | Datenbankpasswort | – |
| `DB_HOST` | Hostname des Datenbankservers | `db` (Docker-intern) |
| `DB_PORT` | Port | `5432` |

> `DB_HOST` muss auf `db` gesetzt bleiben, wenn die Datenbank über Docker Compose betrieben wird.

### E-Mail (SMTP)

| Variable | Beschreibung | Beispiel |
|---|---|---|
| `EMAIL_HOST` | SMTP-Serveradresse | `smtp.example.de` |
| `EMAIL_PORT` | SMTP-Port | `587` |
| `EMAIL_HOST_USER` | SMTP-Benutzername | `portal@example.de` |
| `EMAIL_HOST_PASSWORD` | SMTP-Passwort | – |
| `EMAIL_USE_TLS` | TLS aktivieren | `True` |
| `EMAIL_USE_SSL` | SSL aktivieren (alternativ zu TLS) | `False` |
| `DEFAULT_FROM_EMAIL` | Absenderadresse | `Azubi-Portal <portal@example.de>` |
| `DEFAULT_REPLY_TO_EMAIL` | Antwortadresse | `verwaltung@example.de` |

### Celery / Redis

| Variable | Beschreibung | Standard |
|---|---|---|
| `CELERY_BROKER_URL` | Redis-URL für den Task-Broker | `redis://redis:6379/0` (Docker-intern) |
| `CELERY_RESULT_BACKEND` | Redis-URL für Task-Ergebnisse | `redis://redis:6379/0` (Docker-intern) |

> Beide Werte werden automatisch gesetzt, wenn Redis über Docker Compose betrieben wird.

### Paperless-ngx

| Variable | Beschreibung | Beispiel |
|---|---|---|
| `PAPERLESS_URL` | URL der Paperless-ngx-Instanz | `http://paperless.intern:8000` |
| `PAPERLESS_API_KEY` | API-Token aus den Paperless-Einstellungen | `abc123...` |

Den API-Token findet man in Paperless-ngx unter: **Einstellungen → API-Token**.

---

## Verzeichnisstruktur (Docker-relevant)

```
Azubi/
├── Dockerfile              # Image-Definition
├── docker-compose.yml      # Service-Orchestrierung
├── .env                    # Umgebungsvariablen (nicht ins Git!)
└── .env.example            # Vorlage für .env
```

---

## Automatische Hintergrundaufgaben

Fünf Aufgaben laufen täglich automatisch über **Celery Beat** (via Redis):

| Aufgabe | Zeitplan | Beschreibung |
|---|---|---|
| Praxiseinsatz-Erinnerungen | täglich 07:00 Uhr | Benachrichtigt Praxistutoren 7 Tage vor Beginn oder Ende eines Einsatzes |
| Ausbildungsnachweis-Erinnerungen | täglich 07:00 Uhr | Erinnert Nachwuchskräfte an fehlende oder nicht eingereichte Nachweise |
| Urlaubsantragspaket | täglich 08:00 Uhr | Bündelt genehmigte Urlaubsanträge und sendet sie an die Urlaubsstelle |
| Krankmeldungsbericht | täglich 08:05 Uhr | Täglicher Bericht über neue Krank- und Gesundmeldungen an die Urlaubsstelle |
| Anonymisierung | täglich 12:00 Uhr | Anonymisiert Stammdaten inaktiver Nachwuchskräfte (Datenschutz) |

Die Ausführungszeiten sind über **SiteConfiguration** im Django-Admin-Bereich konfigurierbar. Nach einer Änderung muss der `celery_beat`-Container neu gestartet werden:

```bash
docker compose restart celery_beat
```

---

## Health-Checks

Zwei öffentliche Endpunkte für externes Monitoring (kein Login erforderlich):

| Endpunkt | Zweck | Antwort |
|---|---|---|
| `/healthz` | Liveness — bestätigt nur, dass der Django-Prozess läuft | `200 ok` (text/plain) |
| `/readyz` | Readiness — prüft zusätzlich Datenbank und Cache (Redis) | `200` mit JSON `{"status":"ok","checks":{...}}`, sonst `503` |

```bash
curl -fsS https://meine-domain.de/healthz
curl -fsS https://meine-domain.de/readyz | jq .
```

Beide Endpunkte sind mit `Cache-Control: no-store` markiert, sodass Reverse-Proxies und CDNs keine veralteten Antworten ausliefern.

---

## Nützliche Befehle

```bash
# Alle Services starten
docker compose up -d

# Logs anzeigen
docker compose logs -f app
docker compose logs -f celery_worker
docker compose logs -f celery_beat

# Datenbankmigrationen manuell ausführen
docker compose exec app python manage.py migrate

# Statische Dateien neu einsammeln
docker compose exec app python manage.py collectstatic --noinput

# Hintergrundaufgaben manuell auslösen
docker compose exec app python manage.py send_internship_reminders
docker compose exec app python manage.py send_proof_of_training_reminders
docker compose exec app python manage.py send_vacation_batch [--dry-run]
docker compose exec app python manage.py send_sick_leave_report [--dry-run]
docker compose exec app python manage.py anonymize_inactive_students

# Alle Services stoppen
docker compose down

# Alle Services stoppen und Volumes löschen (Achtung: löscht Datenbankdaten!)
docker compose down -v
```

---

## HTTPS einrichten

Die App lauscht auf Port 80 (HTTP). Für Produktion wird HTTPS empfohlen. Eine einfache Möglichkeit ist [Caddy](https://caddyserver.com/) als Reverse Proxy — er übernimmt automatisch Let's Encrypt-Zertifikate und leitet HTTPS-Anfragen an Port 80 der App weiter.

Außerdem `CSRF_TRUSTED_ORIGINS` in der `.env` auf die HTTPS-URL setzen:

```
CSRF_TRUSTED_ORIGINS=https://meine-domain.de
```

---

## Weitere Dokumentation

Vollständiges Handbuch im Ordner `docs/` — auch als Word-Dokument unter [`Azubi_Portal_Handbuch.docx`](docs/Azubi_Portal_Handbuch.docx) verfügbar.

- [Übersicht & Technische Grundlage](docs/uebersicht.md)
- [**Installation (umfangreich)**](docs/installation.md)
- [Admin-Leitfaden für den täglichen Betrieb](docs/admin-leitfaden.md)
- [Module & Funktionen](docs/module.md)
- [Benutzerrollen](docs/rollen.md)
- [Workflows](docs/workflows.md)
- [Backup & Disaster Recovery](docs/backup.md)
