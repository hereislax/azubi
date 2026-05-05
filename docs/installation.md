# Installation

Diese Anleitung beschreibt die vollständige Inbetriebnahme des Azubi-Portals von einem leeren Server bis zum produktiven Betrieb. Sie richtet sich an System­administratoren mit Linux-Grundkenntnissen.

> **Für Eilige:** [Schnellstart](#5-schnellstart-für-eilige) am Ende dieses Dokuments.

---

## Inhaltsverzeichnis

1. [Systemanforderungen](#1-systemanforderungen)
2. [Vorbereitung](#2-vorbereitung)
3. [Installation Schritt für Schritt](#3-installation-schritt-für-schritt)
4. [Erste Konfiguration nach dem Start](#4-erste-konfiguration-nach-dem-start)
5. [Schnellstart für Eilige](#5-schnellstart-für-eilige)
6. [HTTPS / Reverse Proxy](#6-https--reverse-proxy)
7. [Paperless-ngx einbinden](#7-paperless-ngx-einbinden)
8. [Backups einrichten](#8-backups-einrichten)
9. [Updates](#9-updates)
10. [Troubleshooting](#10-troubleshooting)
11. [Härtungsempfehlungen für Produktion](#11-härtungsempfehlungen-für-produktion)

---

## 1. Systemanforderungen

### Hardware

| Ressource | Minimum | Empfohlen | Hinweis |
|---|---|---|---|
| CPU | 2 vCPU | 4 vCPU | Gunicorn nutzt 3 Worker, Celery nochmal 2 |
| RAM | 2 GB | 4–8 GB | Postgres + Redis + 5 Container |
| Festplatte | 10 GB | ≥ 50 GB | Plus Backup-Volumen, siehe Backup-Doku |
| Netzwerk | 1 öffentliche IPv4 | – | für SMTP, Paperless-API, Updates |

### Software

| Komponente | Mindestversion | Hinweise |
|---|---|---|
| Linux x86_64 | beliebige aktuelle Distribution | Getestet auf Debian 12, Ubuntu 22.04/24.04 |
| Docker Engine | ≥ 24.0 | `docker --version` |
| Docker Compose Plugin | ≥ 2.20 | `docker compose version` (mit Leerzeichen, nicht das alte `docker-compose`) |
| Git | beliebig | nur für `git clone`/`git pull` |

> Für eine Installation auf macOS oder Windows ist Docker Desktop ausreichend, jedoch nicht für den produktiven Betrieb empfohlen.

### Externe Dienste

- **SMTP-Server** für ausgehende E-Mails (Benachrichtigungen, Urlaubsbatch, Bestätigungen)
- **Paperless-ngx** Instanz (kann lokal mitlaufen — siehe `docker-compose.yml`)
- **DNS-Eintrag** auf den Server (z. B. `azubi.deine-domain.de`)
- **TLS-Zertifikat** (z. B. via Let's Encrypt + Caddy/Traefik/nginx)

---

## 2. Vorbereitung

### 2.1 Server vorbereiten

```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Zeitzone und NTP setzen (wichtig für Celery-Beat-Zeitpläne!)
sudo timedatectl set-timezone Europe/Berlin
sudo apt install -y systemd-timesyncd
sudo systemctl enable --now systemd-timesyncd

# Docker installieren (offizielle Anleitung: https://docs.docker.com/engine/install/)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"      # Logout/Login danach nötig

# Prüfen
docker --version
docker compose version
```

### 2.2 DNS und Firewall

- DNS-A/AAAA-Record auf den Server zeigen lassen (z. B. `azubi.deine-domain.de`).
- Firewall-Ports öffnen:
  - **80/tcp** (HTTP, später Redirect → HTTPS)
  - **443/tcp** (HTTPS via Reverse Proxy)
- SSH (Port 22) auf bekannte IPs einschränken oder VPN-only.

### 2.3 Backup-Verzeichnis anlegen

```bash
sudo mkdir -p /var/backups/azubi
sudo chown 1000:1000 /var/backups/azubi   # 1000:1000 = appuser im Container
```

> Idealerweise eigene Partition oder LVM-Volume — ein voll geschriebenes Backup-Verzeichnis darf nie die System-Disk verstopfen. Details siehe [Backup & Disaster Recovery](backup.md).

---

## 3. Installation Schritt für Schritt

### 3.1 Repository klonen

```bash
sudo mkdir -p /opt/azubi
sudo chown "$USER":"$USER" /opt/azubi
git clone https://github.com/hereislax/azubi.git /opt/azubi
cd /opt/azubi
```

### 3.2 Umgebungsdatei erzeugen

```bash
cp .env.example .env
```

Wichtige Pflichtwerte (alle anderen siehe [Konfigurationsreferenz](#konfigurationsreferenz-env)):

```env
SECRET_KEY=<langer Zufallsstring, siehe unten>
DEBUG=False
ALLOWED_HOSTS=azubi.deine-domain.de
CSRF_TRUSTED_ORIGINS=https://azubi.deine-domain.de
SITE_BASE_URL=https://azubi.deine-domain.de

DB_PASSWORD=<sicheres Passwort>

EMAIL_HOST=smtp.deine-domain.de
EMAIL_HOST_USER=portal@deine-domain.de
EMAIL_HOST_PASSWORD=<smtp-passwort>
DEFAULT_FROM_EMAIL=Azubi-Portal <portal@deine-domain.de>

PAPERLESS_URL=http://paperless:8000
PAPERLESS_API_KEY=<api-token-aus-paperless>

BACKUP_DIR=/var/backups/azubi
BACKUP_ALERT_EMAILS=ops@deine-domain.de
```

**SECRET\_KEY generieren:**

```bash
docker run --rm python:3.13-slim python -c \
  "from secrets import token_urlsafe; print(token_urlsafe(50))"
```

### 3.3 Container starten

```bash
docker compose up -d --build
```

Der erste Start kann mehrere Minuten dauern — Docker zieht Images, baut die App, wartet auf die Datenbank, führt Migrationen aus und sammelt statische Dateien ein.

**Status prüfen:**

```bash
docker compose ps
docker compose logs -f app
```

Erwartete Ausgabe in den App-Logs:

```
Operations to perform:
  Apply all migrations: …
Applying … OK
[INFO] Listening at: http://0.0.0.0:8000 (1)
```

### 3.4 Funktionsprüfung

Zwei Endpunkte stehen zur Verfügung:

```bash
# Liveness — bestätigt nur, dass die App läuft (kein DB-/Cache-Zugriff)
curl -fsS http://localhost/healthz && echo OK

# Readiness — prüft zusätzlich Datenbank und Cache (Redis)
curl -fsS http://localhost/readyz | jq .
```

`/healthz` antwortet immer mit `200 ok`, solange der Django-Prozess Anfragen verarbeitet. `/readyz` liefert JSON wie `{"status": "ok", "checks": {"database": "ok", "cache": "ok"}}` und wechselt auf `503`, sobald eine Abhängigkeit nicht erreichbar ist — geeignet für Loadbalancer-, Kubernetes- und Blackbox-Exporter-Probes.

> Wenn Sie HTTPS-Endpoints einsetzen, prüfen Sie `https://azubi.deine-domain.de/healthz` (oder `/readyz`) durch den Reverse Proxy.

### 3.5 Superuser anlegen

```bash
docker compose exec app python manage.py createsuperuser
```

Mit diesem Konto ist der Erstzugang zu `/admin/` möglich. Das Konto erhält keine Sondergruppen — danach idealerweise ein zweites Konto für die Tagesarbeit anlegen und der Gruppe `ausbildungsleitung` zuweisen.

---

## 4. Erste Konfiguration nach dem Start

Nach dem ersten Login unter `/admin/` (oder über die normalen Verwaltungsmasken) folgendes einrichten:

### 4.1 Standardgruppen prüfen

Die sieben Rollen werden beim ersten Start automatisch angelegt (Migration). Im Admin unter **Authentifizierung → Gruppen** sollten zu sehen sein:

`ausbildungsleitung`, `ausbildungsreferat`, `ausbildungskoordination`, `ausbildungsverantwortliche`, `hausverwaltung`, `reisekostenstelle` und ggf. weitere.

Eigenes Tagesarbeitskonto anlegen und der Gruppe `ausbildungsleitung` hinzufügen.

### 4.2 SiteConfiguration

Im Admin unter **Portal → SiteConfiguration**:

- Basis-URL der Instanz (für E-Mail-Links)
- Anonymisierungszeitplan
- Erinnerungszeiten für Celery-Beat-Tasks

### 4.3 AbsenceSettings

Unter **Absence → AbsenceSettings**:

- E-Mail-Adresse der Urlaubsstelle (Empfänger der Tagesbatches)
- Bundesland (für Feiertagsberechnung der Krankheits-Ampel)
- Word-Vorlage für Urlaubsbestätigungen hochladen

### 4.4 NotificationTemplates

Unter **Notifications → NotificationTemplates**: Alle E-Mail-Vorlagen einmal durchsehen, Absender und Inhalt an Ihre Organisation anpassen. Platzhalter (z. B. `{{ student.full_name }}`) bleiben stehen.

### 4.5 Stammdaten anlegen

In dieser Reihenfolge erfassen:

1. **Berufsbilder** (`/career/`) — z. B. „Verwaltungsfachangestellter", „Inspektoranwärter"
2. **Organisationsstruktur** (`/organisation/`) — Behörde → Abteilung → Referat
3. **Standorte**
4. **Praxistutoren** (`/instructor/`)
5. **Koordinationsgruppen** (`/instructor/coordination/`)
6. **Beurteilungsvorlagen** (`/assessment/`)
7. **Wohnheime** (`/dormitory/`)
8. **Inventarkategorien und -gegenstände** (`/inventory/`)

### 4.6 Nachwuchskräfte importieren

Unter **Studenten → Import** entweder als CSV (Semikolon-getrennt, UTF-8) oder XLSX hochladen. Vorlage und Pflichtspalten siehe Hilfetext im Import-Dialog.

---

## 5. Schnellstart für Eilige

```bash
# 1. Repo klonen
git clone https://github.com/devNicoLax/Azubi.git /opt/azubi && cd /opt/azubi

# 2. .env ausfüllen
cp .env.example .env
${EDITOR:-nano} .env

# 3. Backup-Verzeichnis
sudo mkdir -p /var/backups/azubi && sudo chown 1000:1000 /var/backups/azubi

# 4. Stack hochfahren
docker compose up -d --build

# 5. Superuser
docker compose exec app python manage.py createsuperuser

# 6. Browser öffnen
xdg-open http://localhost/admin/
```

---

## 6. HTTPS / Reverse Proxy

Die App selbst lauscht nur auf HTTP, Port 80. Für Produktion **immer** einen Reverse Proxy mit TLS davorschalten.

### 6.1 Caddy (empfohlen — automatisches Let's Encrypt)

`/etc/caddy/Caddyfile`:

```caddy
azubi.deine-domain.de {
    encode zstd gzip
    reverse_proxy localhost:80
}
```

```bash
sudo apt install -y caddy
sudo systemctl reload caddy
```

Caddy holt das Zertifikat automatisch und erneuert es selbst. Nach Aktivierung:

```env
# .env anpassen
CSRF_TRUSTED_ORIGINS=https://azubi.deine-domain.de
SITE_BASE_URL=https://azubi.deine-domain.de
```

```bash
docker compose restart app
```

### 6.2 nginx (Alternative)

```nginx
server {
    listen 443 ssl http2;
    server_name azubi.deine-domain.de;

    ssl_certificate     /etc/letsencrypt/live/azubi.deine-domain.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/azubi.deine-domain.de/privkey.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass         http://127.0.0.1:80;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name azubi.deine-domain.de;
    return 301 https://$host$request_uri;
}
```

---

## 7. Paperless-ngx einbinden

Das Portal benötigt eine erreichbare Paperless-ngx-Instanz für die Dokumentenablage (Zuweisungsschreiben, Quittungen, Bestätigungen).

### 7.1 Paperless mitstarten (im selben Compose)

`docker-compose.yml` enthält optional einen Paperless-Service. Variablen aus `.env`:

```env
PAPERLESS_PUBLIC_URL=https://paperless.deine-domain.de
PAPERLESS_SECRET_KEY=<langer-zufalls-string>
PAPERLESS_ADMIN_USER=admin
PAPERLESS_ADMIN_PASSWORD=<sicher>
PAPERLESS_URL=http://paperless:8000
PAPERLESS_API_KEY=<wird unten erzeugt>
```

Nach dem Start:

```bash
docker compose up -d paperless
docker compose logs -f paperless
```

### 7.2 API-Token erzeugen

1. Browser öffnen: `https://paperless.deine-domain.de/`
2. Mit `PAPERLESS_ADMIN_USER` einloggen
3. **Einstellungen → API-Token** → Token generieren
4. Token in `.env` als `PAPERLESS_API_KEY` eintragen
5. App-Container neu starten:

```bash
docker compose restart app celery_worker
```

### 7.3 Verbindung testen

```bash
docker compose exec app python manage.py shell -c "
from django.conf import settings
import requests
r = requests.get(f'{settings.PAPERLESS_URL}/api/documents/?page=1',
    headers={'Authorization': f'Token {settings.PAPERLESS_API_KEY}'}, timeout=5)
print('Status:', r.status_code)
"
```

Erwartete Ausgabe: `Status: 200`.

---

## 8. Backups einrichten

Das vollständige Backup-Konzept (Stufen, Restic, Disaster-Recovery, Restore-Tests) ist in [docs/backup.md](backup.md) dokumentiert. Mindestens diese Schritte vor dem Produktivstart:

1. `BACKUP_DIR` auf eigener Partition / Volume verlegen.
2. `BACKUP_ALERT_EMAILS` setzen — die Adresse muss regelmäßig gelesen werden.
3. Einen ersten manuellen Backuplauf durchführen:
   ```bash
   docker compose exec app python manage.py backup_now
   docker compose exec app python manage.py list_backups
   ```
4. Empfohlen: Off-Site-Spiegelung mit restic auf NAS oder S3-Storage einrichten.

---

## 9. Updates

```bash
cd /opt/azubi

# 1. Backup vor jedem Update
docker compose exec app python manage.py backup_now

# 2. Neuen Stand holen
git pull

# 3. Image neu bauen, Container neu starten
docker compose up -d --build

# 4. Logs prüfen
docker compose logs -f app | head -50
```

Migrationen werden beim Start automatisch ausgeführt. Statische Dateien werden im Build neu eingesammelt.

> Größere Versionssprünge: Vor dem Update den Eintrag im Changelog (`VERSION` und ggf. `CHANGELOG.md` im Repo) lesen.

---

## 10. Troubleshooting

### App-Container startet nicht / kann sich nicht zur DB verbinden

```bash
docker compose logs db | tail -50
docker compose logs app | tail -50
```

Häufige Ursachen:
- `DB_PASSWORD` in `.env` geändert, aber Datenbankvolumen ist alt → entweder altes Passwort wieder setzen oder Volume löschen (Achtung: alle Daten weg).
- `DB_HOST` ist nicht `db` (Standard im Compose-Netz).

### Migrationsfehler

```bash
docker compose exec app python manage.py migrate --plan
docker compose exec app python manage.py migrate
```

Wenn eine Migration fehlschlägt, bitte den Fehler aus den Logs ans Entwicklerteam weitergeben — niemals manuell `--fake` setzen.

### E-Mails kommen nicht an

```bash
docker compose exec app python manage.py shell -c "
from django.core.mail import send_mail
send_mail('Test', 'Hallo', None, ['empfaenger@example.de'])
"
```

Prüfen:
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` korrekt
- `EMAIL_USE_TLS=True` UND `EMAIL_USE_SSL=False` (oder umgekehrt — niemals beides)
- Firewall: ausgehender Port 587/465 erreichbar
- DNS: `nslookup smtp.deine-domain.de`

### Celery führt geplante Aufgaben nicht aus

```bash
docker compose logs celery_beat | tail -50
docker compose logs celery_worker | tail -50
```

Häufig: Server-Zeitzone falsch. Korrektur per `timedatectl set-timezone Europe/Berlin`, danach `docker compose restart celery_beat`.

### Paperless-Upload schlägt fehl

```bash
docker compose logs celery_worker | grep -i paperless
```

Häufig: API-Token falsch oder `PAPERLESS_URL` nicht erreichbar (DNS, interne IP). Mit dem Test aus Abschnitt 7.3 verifizieren.

### Static Files (CSS/JS) fehlen

```bash
docker compose exec app python manage.py collectstatic --noinput
docker compose restart app
```

---

## 11. Härtungsempfehlungen für Produktion

- [ ] `DEBUG=False` in `.env` (zwingend!)
- [ ] HTTPS-only — Reverse Proxy mit aktuellem TLS-Zertifikat
- [ ] `ALLOWED_HOSTS` exakt auf Ihre Domain eingeschränkt (kein `*`)
- [ ] `SECRET_KEY` mind. 50 Zeichen, einzigartig, nirgendwo geloggt
- [ ] Datenbank-Passwort mind. 24 Zeichen, kein Wiederverwendungs-Passwort
- [ ] SMTP-Zugangsdaten an dedizierten Account binden (nicht persönliches Postfach)
- [ ] Server-Firewall: nur 80/443 öffentlich, 22 auf Admin-IP eingeschränkt
- [ ] Backups laufen, Alert-Mail wird gelesen
- [ ] Quartalsweiser Restore-Test in Audit-Log sichtbar
- [ ] Off-Site-Spiegelung (restic) konfiguriert, `restic.key` an zwei sicheren Orten
- [ ] Server-Updates automatisiert (`unattended-upgrades` oder vergleichbar)
- [ ] Monitoring auf `/healthz` (Liveness) und `/readyz` (Readiness inkl. DB/Cache) — z. B. Uptime Robot, Prometheus Blackbox Exporter
- [ ] Logging zentralisiert (z. B. Loki/Promtail oder Filebeat)

---

## Konfigurationsreferenz (.env)

Vollständige Liste aller Variablen siehe `.env.example` im Repository. Die wichtigsten Gruppen im Überblick:

| Gruppe | Variablen | Hinweise |
|---|---|---|
| **Django** | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_BASE_URL` | Pflicht |
| **Datenbank** | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `DB_HOST=db` im Compose-Netz |
| **E-Mail** | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, `DEFAULT_REPLY_TO_EMAIL` | TLS und SSL nicht gleichzeitig |
| **Celery / Redis** | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | im Compose-Netz `redis://redis:6379/0` |
| **Paperless** | `PAPERLESS_URL`, `PAPERLESS_API_KEY` (+ optional `PAPERLESS_PUBLIC_URL`, `PAPERLESS_SECRET_KEY`, `PAPERLESS_ADMIN_USER`, `PAPERLESS_ADMIN_PASSWORD`) | API-Token nicht im Klartext loggen |
| **Backup** | `BACKUP_DIR`, `BACKUP_KEEP_DAILY`, `BACKUP_ALERT_EMAILS`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD_FILE`, `RESTIC_SECRETS_DIR` | Details siehe [backup.md](backup.md) |

---

## Weitere Dokumentation

- [Übersicht & Technische Grundlage](uebersicht.md)
- [Module & Funktionen](module.md)
- [Benutzerrollen](rollen.md)
- [Workflows](workflows.md)
- [Backup & Disaster Recovery](backup.md)
- [Admin-Leitfaden für den täglichen Betrieb](admin-leitfaden.md)