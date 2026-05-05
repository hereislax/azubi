# restic-Secrets

Hier liegen Schlüssel und Konfigurationsdateien für das Off-Site-Backup via
restic. Der Inhalt wird von `docker-compose.yml` als read-only Bind-Mount
nach `/secrets` im celery_worker-Container gehängt.

**Niemals echte Schlüssel hier einchecken!** Die Datei `.gitkeep` hält nur das
Verzeichnis im Git, alles andere ist über `.gitignore` ausgeschlossen.

## Erforderliche Dateien

### `restic.key`
Das Repository-Passwort (eine Zeile, kein abschließender Newline).
Mindestens 32 zufällige Zeichen empfohlen, z. B. via:
```
openssl rand -base64 32 > restic.key
chmod 400 restic.key
```

### `ssh_id` (nur für SFTP-Backend)
SSH-Privatschlüssel für die Verbindung zum NAS. Berechtigungen:
```
chmod 600 ssh_id
```
Den zugehörigen `ssh_id.pub` auf dem NAS in `~/.ssh/authorized_keys` hinterlegen.

### `ssh_known_hosts` (empfohlen für SFTP)
Damit restic den NAS-Hostkey nicht interaktiv akzeptieren muss:
```
ssh-keyscan -H nas.local > ssh_known_hosts
```

## Verwendung in `.env`

```
RESTIC_REPOSITORY=sftp:backup-user@nas.local:/volume1/backups/azubi
RESTIC_PASSWORD_FILE=/secrets/restic.key
```

Für SFTP zusätzlich in `.env`:
```
# restic ruft ssh intern auf – der Key muss erreichbar sein
GIT_SSH_COMMAND='ssh -i /secrets/ssh_id -o UserKnownHostsFile=/secrets/ssh_known_hosts'
```

(Genauere Beispiele in `docs/backup.md`.)
