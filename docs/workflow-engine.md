# Genehmigungs-Workflows

Dieser Leitfaden richtet sich an die Ausbildungsleitung und erklärt, wie Sie die Genehmigungs-Abläufe im Portal anpassen. Er ergänzt den [Admin-Leitfaden](admin-leitfaden.md) und die Beschreibung der fachlichen [Workflows](workflows.md).

Mit den Genehmigungs-Workflows steuern Sie, wer welche Anträge im Portal freigeben muss — z. B. Lerntags-Anträge, Urlaubsanträge, Praktikumseinsätze oder Stationsbeurteilungen. Die Abläufe sind nicht im Programm-Code festverdrahtet: Sie können Stufen ergänzen, Fristen ändern oder ganze Genehmigungspflichten ein- und ausschalten.

---

## Inhalt

1. [Begriffe](#1-begriffe)
2. [Workflows verwalten](#2-workflows-verwalten)
3. [Eine Stufe konfigurieren](#3-eine-stufe-konfigurieren)
4. [Wer darf entscheiden? – Approver-Typen](#4-wer-darf-entscheiden--approver-typen)
5. [Bedingungen (Pre- und Skip-Conditions)](#5-bedingungen-pre--und-skip-conditions)
6. [Fristen, Erinnerungen, Eskalation](#6-fristen-erinnerungen-eskalation)
7. [Reject-Verhalten – was passiert bei einer Ablehnung?](#7-reject-verhalten--was-passiert-bei-einer-ablehnung)
8. [Workflow-Verlauf einsehen](#8-workflow-verlauf-einsehen)
9. [Mitgelieferte Workflows](#9-mitgelieferte-workflows)
10. [Häufige Aufgaben](#10-häufige-aufgaben)
11. [Hinweise für Entwickler:innen](#11-hinweise-für-entwicklerinnen)

---

## 1. Begriffe

- **Workflow** — eine wiederverwendbare Vorlage für einen Genehmigungs-Ablauf, z. B. „Lerntag-Antrag" oder „Urlaubsantrag". Jeder Workflow besteht aus einer geordneten Folge von Stufen.
- **Stufe** — ein einzelner Genehmigungsschritt: wer entscheidet, wie lange die Frist ist, was bei Fristüberschreitung passiert.
- **Workflow-Instanz** — ein konkret laufender Antrag (z. B. „Lerntag-Antrag von Max Müller vom 15.04."). Jede Instanz durchläuft die Stufen ihrer Vorlage.
- **Transition (Verlaufseintrag)** — ein protokollierter Schritt einer Instanz: Einreichung, Genehmigung, Ablehnung, Erinnerung usw. Bildet zusammen den nachvollziehbaren Verlauf.

---

## 2. Workflows verwalten

Unter **Einstellungen › Genehmigungs-Workflows** sehen Sie alle Workflow-Vorlagen.

Pro Vorlage stehen Ihnen folgende Felder zur Verfügung:

| Feld | Bedeutung |
|---|---|
| **Name** | Anzeigename für Mitarbeitende, z. B. „Lerntag-Antrag". |
| **Code** | Technischer Schlüssel, mit dem das Portal die Vorlage findet. Wird beim Anlegen einmal vergeben und sollte danach nicht mehr geändert werden. |
| **Beschreibung** | Frei wählbarer Text, der die Anwendung des Workflows kurz erläutert. |
| **Aktiv** | Wird der Haken entfernt, startet das Portal keine neuen Instanzen mehr für diesen Workflow. Bereits laufende Instanzen bleiben erhalten. |
| **Reject-Verhalten** | Siehe [Abschnitt 7](#7-reject-verhalten--was-passiert-bei-einer-ablehnung). |
| **Pre-Condition** | Optionale Bedingung, die beim Start geprüft wird (siehe [Abschnitt 5](#5-bedingungen-pre--und-skip-conditions)). |
| **Stufen** | Liste der Genehmigungs-Stufen, in der Reihenfolge der Bearbeitung. |

> **Hinweis:** Den Code einer Vorlage nicht nachträglich umbenennen — er ist mit dem Programm-Code verbunden. Wollen Sie eine Vorlage außer Betrieb nehmen, deaktivieren Sie sie über den „Aktiv"-Schalter.

---

## 3. Eine Stufe konfigurieren

Stufen werden direkt in der Vorlage über die Pfeiltasten in die gewünschte Reihenfolge gebracht. Pro Stufe legen Sie fest:

- **Name** — was bei den Bearbeitenden in der Liste steht, z. B. „Prüfung durch Ausbildungsreferat".
- **Approver-Typ** und **Wert** — wer entscheiden darf (siehe [Abschnitt 4](#4-wer-darf-entscheiden--approver-typen)).
- **Frist (Tage)** — wie lange die Stufe maximal offen bleiben soll. Bleibt das Feld leer, gibt es keine Frist.
- **Verhalten bei Fristablauf** — Erinnerung, Eskalation, oder automatische Genehmigung/Ablehnung (siehe [Abschnitt 6](#6-fristen-erinnerungen-eskalation)).
- **Skip-Condition** — optionale Bedingung, mit der die Stufe für bestimmte Anträge automatisch übersprungen wird.

---

## 4. Wer darf entscheiden? – Approver-Typen

Beim Anlegen einer Stufe wählen Sie, **wie** der Empfänger der Genehmigung bestimmt wird:

| Typ | Wann sinnvoll | Beispiel-Wert |
|---|---|---|
| **Rolle** | Alle Mitarbeitenden einer Rolle dürfen entscheiden. | `training_director`, `training_office`, `training_coordinator`, `holiday_office` |
| **Einzelner Benutzer** | Genau eine Person ist zuständig. | Benutzer-ID |
| **Dynamisch** | Die zuständige Person ergibt sich aus dem Antrag selbst (z. B. „aktuelle:r Praxistutor:in"). | Codename des Resolvers |
| **Extern via Token** | Empfänger:in hat kein Login. Bekommt einen Magic-Link per E-Mail (z. B. Praxistutor:in für eine Beurteilung). | Beliebiges Label |
| **Info / zur Kenntnis** | Stufe blockiert den Ablauf, bis jemand mit der angegebenen Rolle den Antrag zur Kenntnis nimmt — gibt aber keine eigene Entscheidung ab. | Rolle wie bei „Rolle" |

> **Tipp:** Der Typ „Info" eignet sich, wenn z. B. die Koordination einen Vorgang vor der Bestätigung des Ausbildungsreferats sehen soll. Wird die Stufe nicht innerhalb der Frist abgezeichnet, hängt das gewünschte Folge-Verhalten ab vom Feld „Verhalten bei Fristablauf".

---

## 5. Bedingungen (Pre- und Skip-Conditions)

Mit Bedingungen schalten Sie Genehmigungspflichten **antrags-abhängig** ein oder aus, ohne den Code anzufassen.

- **Pre-Condition** auf der Workflow-Vorlage: Greift beim Start. Wird die Bedingung **nicht** erfüllt, überspringt der Workflow alle Stufen und wird sofort als „automatisch genehmigt" abgeschlossen (sichtbar im Verlauf).
- **Skip-Condition** auf einer Stufe: Greift beim Übergang auf diese Stufe. Wird die Bedingung erfüllt, springt der Workflow direkt zur nächsten Stufe und vermerkt das Überspringen im Verlauf.

### Verfügbare Ausdrücke

Verwenden Sie einfache logische Ausdrücke. Verfügbar sind die Platzhalter `initiator` (Antragstellende Person) und `target` (das Antragsobjekt).

Erlaubt:

- Attribut-Zugriffe: `target.duration`, `initiator.profile.flag`
- Vergleiche: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`
- Logik: `and`, `or`, `not`
- Werte: Zahlen, Texte in Anführungszeichen, `True`, `False`, `None`, einfache Listen

Nicht erlaubt sind Funktionsaufrufe, Importe oder beliebige Programmierung. Ungültige Ausdrücke führen nicht zu einem Absturz — der Workflow läuft dann einfach so, als gäbe es keine Bedingung.

### Beispiele

| Ausdruck | Bedeutung |
|---|---|
| `initiator.profile.announcement_requires_approval` | Ankündigungen müssen nur freigegeben werden, wenn das Profil der verfassenden Person den Haken „Freigabe erforderlich" trägt. |
| `target.requires_approval` | Workflow läuft nur, wenn der Änderungstyp grundsätzlich genehmigungspflichtig ist. |
| `target.requires_approval and target.is_short_notice` | Zusätzlich nur, wenn der Einsatzbeginn weniger als 14 Tage entfernt ist. |
| `target.duration > 30` | Stufe wird nur ausgeführt bei Anträgen über 30 (Tage, Einheiten, …). |

---

## 6. Fristen, Erinnerungen, Eskalation

Jede Stufe kann eine Frist in Tagen tragen. Das Portal verschickt **einen Tag vor Fristablauf** automatisch eine Erinnerungs-E-Mail an die zuständigen Bearbeitenden (idempotent: pro Stufe und Revision genau einmal).

Beim Erreichen der Frist greift das gewählte Verhalten:

| Verhalten | Wirkung |
|---|---|
| **Erinnern** | Nur die Erinnerung wurde verschickt, sonst passiert nichts. |
| **An nächste Stufe eskalieren** | Die aktuelle Stufe wird automatisch als erledigt markiert; die nächste Stufe übernimmt. |
| **An ergänzenden Approver eskalieren** | Die Stufe bleibt offen, aber eine zweite Rolle (z. B. die Ausbildungsleitung) darf zusätzlich entscheiden. |
| **Automatisch genehmigen** | Die Stufe wird im Sinne des Antrags abgeschlossen. |
| **Automatisch ablehnen** | Der Workflow endet mit „abgelehnt". |

> **Hinweis:** Damit Erinnerungen und Eskalationen ausgelöst werden, muss der Hintergrunddienst `celery beat` laufen (siehe [Installation](installation.md)). Solange er nicht läuft, sind die Workflows funktional, Fristen werden aber erst beim nächsten Start nachgeholt.

---

## 7. Reject-Verhalten – was passiert bei einer Ablehnung?

Pro Vorlage legen Sie fest, wie sich der Workflow nach einer Ablehnung verhält:

| Wert | Bedeutung |
|---|---|
| **final** | Endgültige Ablehnung. Der Vorgang ist abgeschlossen; eine neue Einreichung ist nur durch das Anlegen eines neuen Antrags möglich. |
| **zurück auf Stufe 1** | Der Antrag landet wieder beim ersten Genehmiger. Eine interne Revision wird hochgezählt; der bisherige Verlauf bleibt sichtbar. |
| **zurück an Antragsteller:in** | Der Antrag pausiert bei der antragstellenden Person, bis sie ihn überarbeitet und erneut einreicht. Anschließend läuft die Genehmigungs-Kette komplett neu durch (Revision +1). |

Beispiele aus dem Portal:

- *Lerntag-Antrag*: `final` – wer abgelehnt wird, muss einen neuen Antrag stellen.
- *Ankündigung*: `zurück an Antragsteller:in` – die verfassende Person bekommt die Anmerkung und kann den Text überarbeiten.
- *Ausbildungsnachweis*: `zurück an Antragsteller:in` – die Nachwuchskraft sieht die Korrekturhinweise pro Tag und reicht den Nachweis erneut ein.

---

## 8. Workflow-Verlauf einsehen

Der vollständige Audit-Trail jedes Vorgangs wird **direkt auf der Antragsseite** angezeigt — sowohl in den Entscheidungs-Ansichten der Bearbeitenden als auch in den Detail-Ansichten. Sichtbar sind:

- Wer den Antrag eingereicht hat
- Welche Stufe wann durchlaufen wurde
- Wer entschieden hat (oder bei externen Token-Stufen: der eingetragene Name)
- Eventuelle Kommentare bzw. Ablehnungsgründe
- Automatische Aktionen wie Erinnerungen, Eskalationen, Auto-Genehmigungen
- Revisionen bei Rück-Schleifen

Der Verlauf wird nicht gelöscht — auch nicht, wenn der zugehörige Datensatz später entfernt wird. Damit bleibt nachvollziehbar, wer wann was entschieden hat.

---

## 9. Mitgelieferte Workflows

Das Portal liefert die folgenden Vorlagen aus. Alle können über *Einstellungen › Genehmigungs-Workflows* angepasst werden.

| Code | Anwendung | Stufen (Reihenfolge) | Bemerkung |
|---|---|---|---|
| `study_day_request` | Lerntag-Antrag | Ausbildungsreferat (5 Tage, eskaliert an Leitung) | Ablehnung endgültig. |
| `announcement_publish` | Ankündigung veröffentlichen | Ausbildungsleitung (3 Tage, Erinnerung) | Pre-Condition prüft Profil-Haken „Freigabe nötig". Ablehnung → zurück an Verfasser:in. |
| `vacation_request` | Urlaubs- und Stornierungsantrag | Ausbildungsreferat (5 Tage, eskaliert an Leitung) → Urlaubsstelle (10 Tage, Erinnerung) | Zweite Stufe wird vorerst aus dem Token-Portal der Urlaubsstelle ausgelöst. |
| `training_record` | Wöchentlicher Ausbildungsnachweis | Ausbildungsleitung (7 Tage, Erinnerung) | Ablehnung → zurück an Nachwuchskraft. Optionale Praxistutor-Vorstufe per UI ergänzbar. |
| `assessment_confirm` | Stationsbeurteilung | Praxistutor:in via Token-Link (21 Tage, eskaliert an Koordination) → Koordination zur Kenntnis (7 Tage, Auto-Sprung) → Ausbildungsreferat (7 Tage, Erinnerung) | Stufe 1 ohne Login; Info-Stufe wird bei expliziter Bestätigung des Referats implizit abgezeichnet. |
| `internship_assignment` | Praktikumseinsatz | Zuständige Koordination (5 Tage, eskaliert an Leitung) | Auch beim „Splitten" eines Einsatzes startet für die zweite Hälfte ein neuer Workflow. |
| `assignment_change_request` | Änderungsantrag (Praxiseinsatz) | Ausbildungsleitung (3 Tage, Erinnerung) | Pre-Condition: nur genehmigungspflichtige Änderungstypen; Praxistutor-Wechsel wird automatisch durchgewunken. Erweiterbar um Zeitabstand-Kriterium. |
| `instructor_confirmation` | Praxistutor:in bestätigen | Ausbildungsleitung (5 Tage, Erinnerung) | Beim Löschen eines Praxistutor:innen-Datensatzes wird der Workflow als „Abgebrochen" archiviert, damit der Verlauf erhalten bleibt. |

---

## 10. Häufige Aufgaben

### Frist einer Stufe ändern

1. *Einstellungen › Genehmigungs-Workflows* öffnen
2. Auf die Vorlage klicken (z. B. „Lerntag-Antrag")
3. In der Stufen-Tabelle auf „Bearbeiten" klicken
4. **Frist (Tage)** ändern, **Verhalten bei Fristablauf** ggf. anpassen
5. Speichern

> Die Änderung gilt für alle neu eingehenden Anträge. Bereits laufende Instanzen behalten ihre ursprüngliche Frist.

### Genehmigungspflicht abschalten

Zwei Wege:

- **Vollständig:** „Aktiv"-Haken bei der Vorlage entfernen. Das Portal startet dann keine neuen Workflow-Instanzen mehr für diesen Typ; die Module greifen auf ihren Direktpfad zurück.
- **Bedingt:** Eine Pre-Condition ergänzen, die nur in den gewünschten Fällen `True` ergibt. So lassen Sie z. B. nur „kurzfristige" Änderungen durch die Leitung laufen.

### Eine zusätzliche Stufe einfügen

1. Vorlage öffnen
2. „Stufe hinzufügen" anklicken
3. Approver-Typ wählen (Rolle, Benutzer, Info, …)
4. Reihenfolge mit den Pfeiltasten an die gewünschte Position bringen
5. Speichern

> Achten Sie darauf, dass die neue Reihenfolge fachlich sinnvoll ist — die nachgelagerten Stufen erwarten in der Regel, dass die vorherigen erfolgreich entschieden wurden.

### Workflow für eine neue Mandantin / einen neuen Mandanten anpassen

Im Portal arbeitet pro Installation **eine** Mandantin / ein Mandant. Wollen Sie z. B. statt der Standard-Workflows abweichende Abläufe nutzen, passen Sie die mitgelieferten Vorlagen direkt an. Eine Versionierung oder Vererbung zwischen Mandanten gibt es bewusst nicht — die Konfiguration bleibt überschaubar.

### Audit-Log eines konkreten Antrags exportieren

Der Verlauf ist Teil der Datenbank. Wer eine Kopie braucht (z. B. für eine Personalakte), exportiert die Antragsdetail-Seite als PDF über den Browser (`Datei › Drucken › Als PDF speichern`).

---

## 11. Hinweise für Entwickler:innen

Dieser Abschnitt ist nur relevant, wenn Sie ein neues Modul an die Workflow-Engine anbinden möchten.

### Neuen Workflow im Code starten

```python
from workflow.engine import start_workflow, perform_action

# Beim Erfassen eines Antrags
instance = start_workflow('mein_workflow', target=antragsobjekt,
                          initiator=request.user)

# Bei einer Entscheidung
perform_action(instance, actor=request.user, action='approve', comment='OK')
```

### Auf den Abschluss eines Workflows reagieren

```python
# in apps.py: ready()
from workflow.engine import register_completion_hook
from workflow.models import INSTANCE_STATUS_APPROVED

def on_approved(instance, status):
    if status != INSTANCE_STATUS_APPROVED:
        return
    instance.target.publish()  # eigene Folge-Aktion

register_completion_hook('mein_workflow', on_approved)
```

### Vorlage über eine Daten-Migration ausliefern

Workflow-Vorlagen werden über Datenmigrationen in `workflow/migrations/` eingespielt. Vorlage zum Kopieren: `0002_seed_default_workflows.py`.

### Den Verlauf in einem Template anzeigen

```django
{% load workflow_tags %}
{% workflow_history target=mein_antrag %}
```

## Weitere Dokumentation

- [Installation (umfangreich)](installation.md)
- [Admin-Leitfaden](admin-leitfaden.md)
- [Module & Funktionen](module.md)
- [Benutzerrollen](rollen.md)
- [Workflows](workflows.md)
- [Backup & Disaster Recovery](backup.md)