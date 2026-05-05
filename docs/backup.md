# Backup & Disaster Recovery

Dieses Dokument beschreibt das Backup-Konzept des Azubi-Portals: was gesichert
wird, wie oft, wohin – und wie ein Restore funktioniert.

## Übersicht

```
[App-Container] ──► /backups (Bind-Mount auf Host: /var/backups/azubi)
[Paperless]    ──►        │
                          ▼
                    [restic, verschlüsselt, dedupliziert]   ← Stufe 2 (geplant)
                          │
                          ▼
                    NAS via SFTP oder SMB
```

**Stufe 1 (aktiv):** Lokale Backups via Celery + django-dbbackup.
**Stufe 2 (geplant):** Off-Site-Spiegelung via restic auf NAS.
**Stufe 3 (geplant):** Quartalsweiser, automatischer Restore-Test.

## Was wird gesichert

| Komponente       | Inhalt                                | Tool              | Dateiname-Schema                    |
|------------------|---------------------------------------|-------------------|-------------------------------------|
| Azubi-DB         | Komplette PostgreSQL-DB (custom fmt)  | `pg_dump -Fc`     | `azubi-YYYYMMDD-HHMMSS.psql.bin`    |
| Azubi-Media      | `/app/media` (Uploads, Profilbilder)  | `tar`             | `azubi-media-YYYYMMDD-HHMMSS.tar`   |
| Paperless-DB     | Paperless-Postgres-DB (custom fmt)    | `pg_dump -Fc`     | `paperless-db-YYYYMMDD-HHMMSS.dump` |
| Paperless-Files  | `data/` + `media/` (PDFs, Index)      | `tar.gz`          | `paperless-files-YYYYMMDD-HHMMSS.tar.gz` |

**Nicht gesichert:** Redis (Cache + Result-Backend, regenerierbar), `staticfiles/`
(beim Build neu erzeugt), Logs (per separater Log-Pipeline).

## Zeitplan

Konfigurierbar unter **Einstellungen → Hintergrundaufgaben** (SiteConfiguration):

| Task                       | Default | Beschreibung                                  |
|----------------------------|---------|-----------------------------------------------|
| `backup-database`          | 02:00   | Azubi-DB-Dump                                 |
| `backup-media`             | 02:15   | Azubi-Media-Tarball                           |
| `backup-paperless`         | 02:30   | Paperless-DB + Files                          |
| `backup-cleanup`           | 02:45   | GFS-Rotation (siehe unten)                    |
| `backup-offsite` (Stufe 2) | 03:00   | restic-Sync auf NAS                           |

Die Versätze von 15 Minuten verhindern, dass pg_dump und große Tar-Operationen
gleichzeitig um IO/RAM konkurrieren.

## Aufbewahrungs-Strategie (GFS)

Pro Backup-Typ wird vorgehalten:

- die **letzten 7** täglichen Backups (`BACKUP_KEEP_DAILY`)
- das **älteste** Backup pro Kalenderwoche, für **4 Wochen** (`backup_keep_weekly`)
- das **älteste** Backup pro Kalendermonat, für **12 Monate** (`backup_keep_monthly`)

Beispiel: Bei 12 Monaten Betrieb liegen pro Typ ca. 7 + 4 + 12 = 23 Backups vor.

## Speicherbedarf abschätzen

| Komponente        | typische Größe | Hinweis                                          |
|-------------------|----------------|--------------------------------------------------|
| Azubi-DB-Dump     | 5–50 MB        | Hängt von Anzahl Auszubildender + Audit-Log ab   |
| Azubi-Media       | 100 MB – mehrere GB | Profilbilder + hochgeladene Dokumente       |
| Paperless-DB      | 1–20 MB        | Indexierungs-Metadaten                           |
| Paperless-Files   | wächst stark   | Kompletter PDF-Bestand + Suchindex               |

Faustformel: Plane mindestens **3× den Bestand der Paperless-Files** ein
(7 daily + 4 weekly + 12 monthly = 23 Snapshots, restic dedupliziert aber stark).

## Wo liegen die Backups

**Im Container:** `/backups` (read-write für `celery_worker`)
**Auf dem Host:** `${BACKUP_DIR}` aus `.env`, Default `/var/backups/azubi`

Empfehlung: Eigene Partition oder LVM-Volume, damit ein volles Backup-Verzeichnis
nicht die System-Disk füllt.

## Konfiguration

`.env`:
```
BACKUP_DIR=/var/backups/azubi          # Bind-Mount-Pfad auf dem Host
BACKUP_KEEP_DAILY=7                     # tägliche Backups vorhalten
BACKUP_ALERT_EMAILS=ops@deine-domain.de # Empfänger für Fehler-Mails
```

Vor dem ersten Start:
```
sudo mkdir -p /var/backups/azubi
sudo chown 1000:1000 /var/backups/azubi   # appuser im Container
```

## Manuelles Backup

```
docker compose exec app python manage.py backup_now
```

Optionen:
- `--skip-paperless` – wenn Paperless gerade nicht läuft
- `--skip-cleanup` – Rotation nicht ausführen

Übersicht aller vorhandenen Backups:
```
docker compose exec app python manage.py list_backups
```

## Restore-Runbook

### Voraussetzung

Stelle sicher, dass die Compose-Stack läuft, aber die App **nicht** auf der DB
arbeitet, während du sie wiederherstellst:
```
docker compose stop app celery_worker celery_beat
```

### A) Azubi-Datenbank wiederherstellen

```bash
# 1. Vorhandene DB leeren (VORSICHT: löscht alle Daten!)
docker compose exec db psql -U $DB_USER -d $DB_NAME -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 2. Dump einspielen
docker compose exec -T db pg_restore -U $DB_USER -d $DB_NAME --no-owner --no-acl < /var/backups/azubi/azubi-20260503-020000.psql.bin

# 3. App-Container hochfahren
docker compose start app celery_worker celery_beat
```

### B) Azubi-Media wiederherstellen

```bash
# Ins media-Volume entpacken
docker run --rm -v azubi_media_data:/dest -v /var/backups/azubi:/src:ro alpine \
    sh -c "rm -rf /dest/* && tar xf /src/azubi-media-20260503-021500.tar -C /dest --strip-components=2"
```
Hinweis: `--strip-components` hängt vom Tar-Layout ab (django-dbbackup nutzt absolute
Pfade ab `/app/media`); im Zweifel vorher `tar tf <file> | head` prüfen.

### C) Paperless wiederherstellen

```bash
# 1. Paperless stoppen
docker compose stop paperless

# 2. Datenbank neu anlegen
docker compose exec db psql -U $DB_USER -c "DROP DATABASE IF EXISTS paperless; CREATE DATABASE paperless;"

# 3. DB-Dump einspielen
docker compose exec -T db pg_restore -U $DB_USER -d paperless --no-owner --no-acl < /var/backups/azubi/paperless-db-20260503-023000.dump

# 4. Dateien (data + media) zurückspielen
docker run --rm -v azubi_paperless_data:/dest_data -v azubi_paperless_media:/dest_media \
       -v /var/backups/azubi:/src:ro alpine \
       sh -c "rm -rf /dest_data/* /dest_media/* && tar xzf /src/paperless-files-20260503-023000.tar.gz -C /tmp && \
              cp -a /tmp/data/. /dest_data/ && cp -a /tmp/media/. /dest_media/"

# 5. Paperless wieder starten – Suchindex wird beim Start automatisch validiert
docker compose start paperless
```

## RPO / RTO

- **RPO (Recovery Point Objective):** 24 h
  Maximaler Datenverlust = Zeitspanne seit letztem Backup, also bis zu 24 Stunden.
- **RTO (Recovery Time Objective):** 1 h
  Vollständige Wiederherstellung in unter einer Stunde, sofern Backups verfügbar.

Bei strengeren Anforderungen (RPO < 1 h) → PostgreSQL WAL-Archiving evaluieren.

## Monitoring

Erfolg und Fehler jedes Backups landen im **Audit-Log**
(`/auditlog/`, Filter: Aktion = "Backup erstellt" oder "Backup fehlgeschlagen").

Bei Fehlern wird zusätzlich eine Mail an `BACKUP_ALERT_EMAILS` gesendet.

---

## Stufe 2: Off-Site-Sync via restic

Das lokale Backup-Verzeichnis wird täglich um 03:00 (konfigurierbar) verschlüsselt
auf das NAS gespiegelt. restic dedupliziert über Snapshots hinweg, sodass die
Größe auf dem NAS nicht linear mit der Anzahl Snapshots wächst.

### Vorbereitung

1. **Repository-Schlüssel erzeugen** (mind. 32 zufällige Zeichen):
   ```
   openssl rand -base64 32 > docker/restic-secrets/restic.key
   chmod 400 docker/restic-secrets/restic.key
   ```
   ⚠️ **Diesen Schlüssel sicher off-site speichern** (Passwort-Manager, Tresor).
   Ohne ihn sind die Backups unbrauchbar – es gibt keine Wiederherstellungs-Möglichkeit.

2. **Eine der drei Varianten konfigurieren:**

#### Variante A: SFTP (empfohlen für Synology/QNAP/TrueNAS)

```
# .env
RESTIC_REPOSITORY=sftp:backup-user@nas.local:/volume1/backups/azubi
RESTIC_PASSWORD_FILE=/secrets/restic.key
```

SSH-Key auf dem Host erzeugen und in `docker/restic-secrets/` ablegen:
```
ssh-keygen -t ed25519 -N '' -f docker/restic-secrets/ssh_id
ssh-copy-id -i docker/restic-secrets/ssh_id.pub backup-user@nas.local
ssh-keyscan -H nas.local > docker/restic-secrets/ssh_known_hosts
chmod 600 docker/restic-secrets/ssh_id
```

restic ruft intern `ssh` auf. Damit der richtige Key verwendet wird, im
Container eine `~/.ssh/config` ablegen oder direkt in `.env`:
```
GIT_SSH_COMMAND='ssh -i /secrets/ssh_id -o UserKnownHostsFile=/secrets/ssh_known_hosts -o StrictHostKeyChecking=yes'
```

#### Variante B: SMB/NFS (NAS auf Host gemountet)

NAS auf dem Host mounten, z. B. SMB:
```
sudo mkdir -p /mnt/nas/azubi-backup
sudo mount -t cifs //nas.local/backups/azubi /mnt/nas/azubi-backup \
    -o credentials=/etc/samba/azubi.cred,uid=1000,gid=1000
```
(In `/etc/fstab` für persistente Mounts eintragen.)

In `docker-compose.override.yml` (lokale Datei, nicht im Repo) ergänzen:
```yaml
services:
  celery_worker:
    volumes:
      - /mnt/nas/azubi-backup:/restic-target
```

In `.env`:
```
RESTIC_REPOSITORY=/restic-target
RESTIC_PASSWORD_FILE=/secrets/restic.key
```

#### Variante C: S3-kompatibel (MinIO, Backblaze B2, AWS)

```
RESTIC_REPOSITORY=s3:https://minio.local:9000/azubi
RESTIC_PASSWORD_FILE=/secrets/restic.key
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### Erstinitialisierung

Beim ersten Lauf der Off-Site-Task wird das Repository automatisch initialisiert.
Manuell prüfen:
```
docker compose exec celery_worker restic snapshots
```

### Off-Site-Snapshots manuell ansehen

```
# Liste aller Snapshots
docker compose exec celery_worker restic snapshots --tag azubi

# Inhalt eines Snapshots
docker compose exec celery_worker restic ls latest

# Restore einzelner Datei oder ganzer Snapshot
docker compose exec celery_worker restic restore latest --target /tmp/restore --include /backups/azubi-20260503-020000.psql.bin
```

### Off-Site-Aufbewahrung

Identisch zur lokalen GFS-Strategie, aber über `restic forget --prune`:
- 7 daily, 4 weekly, 12 monthly (aus SiteConfiguration)
- `--prune` gibt freigegebenen Speicher tatsächlich frei

---

## Stufe 3: Quartalsweiser Restore-Test

> Ein Backup, das nie zurückgespielt wurde, ist kein Backup.

Am 1. Januar/April/Juli/Oktober wird automatisch der jüngste DB-Dump in eine
temporäre Datenbank `azubi_restore_test_<timestamp>` zurückgespielt und auf
Vollständigkeit geprüft (Pflichttabellen: `auth_user`, `student_student`,
`course_course`, `auditlog_auditlogentry`).

Ergebnis landet im Audit-Log; bei Fehler zusätzliche Mail an `BACKUP_ALERT_EMAILS`.
Die Test-DB wird am Ende immer gelöscht – auch bei Fehler.

### Manueller Restore-Test

```
# Liste verfügbare Dumps
docker compose exec app python manage.py list_backups

# Test-Restore (ohne --confirm = Dry-Run)
docker compose exec app python manage.py restore_backup /backups/azubi-20260503-020000.psql.bin

# Tatsächlich in Test-DB einspielen
docker compose exec app python manage.py restore_backup /backups/azubi-20260503-020000.psql.bin --confirm

# In andere Test-DB einspielen
docker compose exec app python manage.py restore_backup /backups/...psql.bin --target-db=azubi_smoke --confirm
```

### Restore in Produktiv-DB (Disaster-Recovery)

⚠️ **Destruktive Operation – nur im Notfall!**

```
# 1. Anwendung herunterfahren
docker compose stop app celery_worker celery_beat

# 2. Restore mit explizitem --target=production --confirm
docker compose exec app python manage.py restore_backup \
    /backups/azubi-20260503-020000.psql.bin \
    --target=production --confirm

# 3. App wieder hochfahren
docker compose start app celery_worker celery_beat
```

---

## Komplettes Disaster-Recovery-Runbook

Szenario: Server ist abgeraucht, neuer Server steht bereit, NAS ist erreichbar.

```bash
# 1. Repo klonen, .env aus Tresor wiederherstellen
git clone <repo> /opt/azubi
cd /opt/azubi
cp /tresor/azubi.env .env
cp /tresor/restic.key docker/restic-secrets/

# 2. Backup-Verzeichnis anlegen
sudo mkdir -p /var/backups/azubi
sudo chown 1000:1000 /var/backups/azubi

# 3. Stack starten (ohne app/celery, nur DB+Redis+Paperless)
docker compose up -d db redis

# 4. Jüngsten Snapshot vom NAS holen
docker compose run --rm celery_worker \
    restic restore latest --target / --include /backups

# 5. DB-Restore
docker compose exec -T db psql -U $DB_USER -c "DROP DATABASE IF EXISTS $DB_NAME; CREATE DATABASE $DB_NAME;"
docker compose exec -T db pg_restore -U $DB_USER -d $DB_NAME --no-owner --no-acl \
    < $(ls -t /var/backups/azubi/azubi-*.psql.bin | head -1)

# 6. Paperless-DB-Restore (analog)
docker compose exec -T db psql -U $DB_USER -c "DROP DATABASE IF EXISTS paperless; CREATE DATABASE paperless;"
docker compose exec -T db pg_restore -U $DB_USER -d paperless --no-owner --no-acl \
    < $(ls -t /var/backups/azubi/paperless-db-*.dump | head -1)

# 7. Media + Paperless-Files entpacken (siehe oben "Restore-Runbook")

# 8. Stack komplett hochfahren
docker compose up -d

# 9. Funktionsprüfung (Liveness + Readiness inkl. DB/Cache)
curl -fsS https://azubi.deine-domain.de/healthz || echo 'Liveness-Check fehlgeschlagen'
curl -fsS https://azubi.deine-domain.de/readyz  || echo 'Readiness-Check fehlgeschlagen'
docker compose exec app python manage.py list_backups
```

**Erwartete Wiederherstellungszeit (RTO):** ~30–60 Minuten bei < 50 GB Gesamt-Backup.

---

## Was NICHT gesichert ist – und warum

| Komponente             | Grund                                                       |
|------------------------|-------------------------------------------------------------|
| Redis (Cache)          | Cache regeneriert sich aus DB                               |
| Redis (Celery-Result)  | Task-Status nur kurzlebig relevant                          |
| Redis (Celery-Broker)  | Pending Tasks sind reproduzierbar (Beat-Schedule in DB)     |
| `staticfiles/`         | Wird beim `collectstatic` aus Code regeneriert              |
| Logs                   | Sollte über zentrale Log-Pipeline (z. B. Loki) laufen       |
| Container-Images       | Werden aus Dockerfile/registry rebuilt                      |
| Paperless-Suchindex    | Wird beim Start aus DB+Files automatisch neu aufgebaut      |

## Sicherheits-Checkliste

- [ ] `restic.key` an mindestens 2 sicheren Orten off-site gelagert (z. B. Passwort-Manager + verschlossener Umschlag)
- [ ] `BACKUP_DIR` auf eigener Partition oder LVM-Volume (nicht System-Disk)
- [ ] NAS-Account hat **nur** Schreibrechte auf `/backups/azubi`, kein root
- [ ] Quartalsweiser Restore-Test läuft – Audit-Log auf "Restore-Test erfolgreich" prüfen
- [ ] `BACKUP_ALERT_EMAILS` zeigt auf eine Adresse, die regelmäßig gelesen wird
- [ ] Backup-Volume vom NAS regelmäßig auf Speicher-Auslastung monitoren
