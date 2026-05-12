# Barrierefreiheit (BITV 2.0 / WCAG 2.1 AA)

Diese Datei fasst die Konventionen zusammen, die in allen Templates eingehalten
werden müssen, damit das Portal die Anforderungen der
**Barrierefreie-Informationstechnik-Verordnung (BITV 2.0)** und damit der
**Web Content Accessibility Guidelines 2.1 Stufe AA** erfüllt.

> **Status:** Phase 1 (Audit + Sofortmaßnahmen) und Phase 2 (systematische
> Template-Sweeps) sind abgeschlossen. Insgesamt 218 Templates über 20 Module
> wurden BITV-konform überarbeitet. Diese Datei ist jetzt die **verbindliche
> Konvention für alle neuen oder geänderten Templates**.

---

## Verbindliche Konventionen

### 1. Eine `<h1>` pro Seite

Jede Template, die `{% extends 'base.html' %}` nutzt, muss genau **eine**
Überschrift der Ebene 1 enthalten. Wenn die Seite optisch keinen großen Titel
braucht, kann sie versteckt werden:

```html
<h1 class="kern-sr-only">{{ page_title }}</h1>
```

Folgeüberschriften strikt hierarchisch: `<h1>` → `<h2>` → `<h3>`. Keine Sprünge.

**Visuelle Größe ≠ semantische Ebene.** Wenn eine Card im Detail-Screen mit
einem visuell kleinen Titel beginnt, aber semantisch die Hauptüberschrift ist,
nutze `<h1 class="h5">` (Bootstrap-Utility behält das alte Aussehen):

```html
<div class="card-header bg-primary text-white">
    <h1 class="h5 mb-0"><i class="bi bi-…" aria-hidden="true"></i> Form-Titel</h1>
</div>
```

Für untergeordnete Card-Abschnitte analog: `<h2 class="h5">`, `<h2 class="h6">`.

### 2. Tabellen

```html
<table>
  <caption>Urlaubsanträge nach Status</caption>
  <thead>
    <tr>
      <th scope="col">Nachwuchskraft</th>
      <th scope="col">Von</th>
      <th scope="col">Bis</th>
      <th scope="col">Status</th>
    </tr>
  </thead>
  <tbody>…</tbody>
</table>
```

- `<caption>` ist Pflicht – darf via `kern-sr-only` versteckt werden.
- `<th scope="col">` für Spalten-Header, `<th scope="row">` für Zeilen-Header.
- Aktions-Spalten (Edit/Delete-Buttons) brauchen einen versteckten Header:
  `<th scope="col"><span class="kern-sr-only">Aktionen</span></th>`
- Abkürzungen in Headern: `<abbr title="Arbeitstage">AT</abbr>`.
- **Key-Value-Tabellen** (z.B. „Block: 12.05.2026"): `<tr><th scope="row">Block</th><td>12.05.2026</td></tr>`.

### 3. Icon-only Buttons und Links

`title=""` allein genügt **nicht** für Screen Reader. Pflicht:

```html
<button type="button" class="btn btn-sm btn-outline-danger"
        aria-label="Eintrag „{{ obj.name }}" löschen">
  <i class="bi bi-trash" aria-hidden="true"></i>
</button>
```

Faustregel: Wenn ein Button ausschließlich ein `<i class="bi …"></i>` enthält,
braucht er `aria-label="…"`. Das Icon selbst bekommt `aria-hidden="true"`.

**Mit sichtbarem Text:** Wenn der Button-Text die Bedeutung schon trägt
(„Bearbeiten", „Hochladen"), reicht `aria-hidden="true"` am Icon.

**Toggle-Buttons** (Aktivieren/Deaktivieren): Zusätzlich `aria-pressed="true|false"`
und das `aria-label` beschreibt die Aktion, nicht den Zustand:

```html
<button type="submit" aria-pressed="{% if doc.is_active %}true{% else %}false{% endif %}"
        aria-label="Dokument „{{ doc.title }}" {% if doc.is_active %}deaktivieren{% else %}aktivieren{% endif %}">
  <i class="bi {% if doc.is_active %}bi-check-circle-fill{% else %}bi-pause-circle{% endif %}" aria-hidden="true"></i>
</button>
```

### 4. Bootstrap-Modals

```html
<div class="modal fade" id="myModal" tabindex="-1"
     aria-labelledby="myModal-title" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="modal-title h5" id="myModal-title">Titel</h2>
        <button type="button" class="btn-close" data-bs-dismiss="modal"
                aria-label="Schließen"></button>
      </div>
      …
    </div>
  </div>
</div>
```

Native `<dialog>` (`kern-dialog`-Variante) braucht analog `aria-labelledby="…"`
mit Verweis auf eine `id` innerhalb des Dialogs.

**Dialog-Trigger** sollten dem Nutzer ankündigen, dass ein Dialog geöffnet wird:

```html
<button type="button" onclick="kernDialogOpen('myModal')"
        aria-haspopup="dialog" aria-label="Details ansehen">…</button>
```

### 5. Formulare

- **Jedes Eingabefeld** braucht ein `<label for="…">`. `placeholder=""` ist
  **kein** Ersatz.
- Pflichtfelder: `required` **und** `aria-required="true"`. Das `*` neben dem
  Label bekommt `aria-label="erforderlich"`:

```html
<label for="id_title">Titel <span class="text-danger" aria-label="erforderlich">*</span></label>
<input id="id_title" required aria-required="true" ...>
```

- **Fehlerausgabe** via `aria-invalid="true"` und `aria-describedby="…-error"`:

```html
<input id="id_username" name="username" required aria-required="true"
       aria-invalid="{% if form.username.errors %}true{% else %}false{% endif %}"
       aria-describedby="id_username-error">
{% if form.username.errors %}
  <div id="id_username-error" class="text-danger small" role="alert">
    {{ form.username.errors|join:" " }}
  </div>
{% endif %}
```

- **Help-Text** ebenfalls über `aria-describedby` verbinden:

```html
<input id="id_email" type="email" aria-describedby="id_email-help">
<div id="id_email-help" class="form-text">Dienstliche oder private Adresse.</div>
```

- **Autocomplete-Hints** für Browser-Passwort-Manager: `username`,
  `current-password`, `new-password`, `email`, `name`, `one-time-code`.

### 6. Radio-Button-Gruppen

Zusammengehörende Radio-Buttons (z.B. Bewertungsskala) immer mit
`<fieldset>`/`<legend>` strukturieren – sonst weiß der Screenreader nicht,
welcher Frage die Optionen zugeordnet sind:

```html
<fieldset {% if field.errors %}aria-describedby="{{ field.name }}-error"{% endif %}>
  <legend class="fw-semibold mb-1 fs-6">{{ field.label }}</legend>
  <div role="radiogroup">
    {% for radio in field %}
    <div class="form-check form-check-inline">
      {{ radio.tag }}
      <label class="form-check-label" for="{{ radio.id_for_label }}">{{ radio.choice_label }}</label>
    </div>
    {% endfor %}
  </div>
  {% if field.errors %}
  <span class="kern-error" id="{{ field.name }}-error" role="alert">
    <i class="bi bi-exclamation-circle me-1" aria-hidden="true"></i>{{ field.errors|join:", " }}
  </span>
  {% endif %}
</fieldset>
```

### 7. Autocomplete-Suche (Combobox)

Eigene Autocomplete-Felder (NK-Suche in `vacation_create`, `sick_leave_create`)
müssen dem WAI-ARIA-Combobox-Pattern folgen:

```html
<input type="text" id="student_search" class="kern-form-input__input"
       required aria-required="true"
       role="combobox" aria-autocomplete="list"
       aria-controls="student_dropdown" aria-expanded="false"
       aria-describedby="student_error">
<div id="student_dropdown" role="listbox"></div>
```

JS muss `aria-expanded` synchron mit dem Open/Close des Dropdowns setzen:

```js
function closeDropdown() {
    dropdown.style.display = 'none';
    search.setAttribute('aria-expanded', 'false');
}
function openDropdown() {
    dropdown.style.display = 'block';
    search.setAttribute('aria-expanded', 'true');
}
```

Items im Dropdown bekommen `role="option"`. Der zugrundeliegende
`<select>` wird mit `aria-hidden="true" tabindex="-1"` aus dem
Tab-Order entfernt (er ist nur Wert-Halter).

### 8. Farbe ist nie alleiniger Bedeutungsträger

Status-Badges immer mit Text **oder** Icon **und** Beschriftung. Beispiel:

```html
<span class="badge bg-success">
  <i class="bi bi-check-circle" aria-hidden="true"></i>
  Genehmigt
</span>
```

Wenn die Information nur durch ein Status-Icon vermittelt wird (z.B. in
Matrix-Ansichten), braucht das Icon ein beschreibendes `aria-label`:

```html
<span class="badge bg-{{ cell.badge }}"
      aria-label="{{ cell.label }}{% if cell.date %}, gültig bis {{ cell.date|date:'d.m.Y' }}{% endif %}">
  <i class="bi bi-check" aria-hidden="true"></i>
</span>
```

### 9. Sprachwechsel

Englische Begriffe im deutschen Text mit `lang="en"` markieren, z.B.
`<span lang="en">Service Worker</span>`, `<span lang="en">Paperless-ngx</span>`,
`<span lang="en">DataTables</span>`.

### 10. Fokus-Indikator

Niemals `outline: none` ohne sichtbaren Ersatz. Wenn der globale
`:focus-visible`-Ring stört, mit `:focus-visible` (Pseudoklasse) targeten –
nicht mit `:focus`:

```css
/* Falsch — entfernt Tastatur-Fokus */
.btn:focus { outline: none; }

/* Richtig — Maus-Fokus aus, Tastatur-Fokus an */
.btn:focus:not(:focus-visible) { outline: none; }
```

### 11. Keine `onclick` auf div / span / a ohne href

Interaktive Elemente sind `<button>` oder `<a href>`. Wenn `onclick` auf einem
nicht-fokussierbaren Element nötig erscheint, ist meist ein Button die richtige
Wahl. Andernfalls explizit `tabindex="0"` und Keyboard-Event-Handler
(`Enter`/`Space`) ergänzen.

### 12. `onsubmit="return confirm(...)"`-Falle

Die HTML-Attribut-Grenze ist der ASCII-`"` (U+0022). Wenn deutsche Anführungs-
zeichen im Confirm-Text gewünscht sind, NICHT den ASCII-`"` mit dem öffnenden
`„` paaren – das schließt das Attribut vorzeitig:

```html
<!-- Defekt: das " hinter cl.name schließt das onsubmit-Attribut -->
<form onsubmit="return confirm('Checkliste „{{ cl.name }}" wirklich löschen?')">

<!-- Richtig: deutsche Schlusszitate U+201C und escapejs-Filter -->
<form onsubmit="return confirm('Checkliste „{{ cl.name|escapejs }}" wirklich löschen?')">
```

Das gleiche Pattern für `aria-label="…„{{ obj.name }}" …"` – immer
`„…"` (typographisch) statt `„…"` (ASCII) verwenden.

### 13. Cards als semantische Sections

Wenn eine Card eine logische Inhaltssektion bildet (z.B. „Reservierungen",
„Sperrungen", „Aktueller Status"), nutze `<section aria-labelledby="…">`
statt `<div>`:

```html
<section class="card shadow-sm" aria-labelledby="reservations-heading">
  <div class="card-header">
    <h2 id="reservations-heading" class="h5 mb-0">Reservierungen</h2>
  </div>
  <div class="card-body">…</div>
</section>
```

Screen-Reader-User können dann per Region-Navigation direkt zu der Section
springen.

### 14. `title`-Attribut ist kein Ersatz für `aria-label`

Viele Screenreader ignorieren das `title`-Attribut komplett. Wenn die
Information für die Barrierefreiheit wichtig ist (z.B. Tooltip auf einem
Status-Icon), nutze `aria-label`. `title` darf für **zusätzlichen**
visuellen Hover-Hint stehen bleiben.

### 15. Disabled-Buttons

`disabled` allein reicht meist, aber für maximale Kompatibilität auch
`aria-disabled="true"` setzen:

```html
<button type="submit" disabled aria-disabled="true"
        title="Kann nicht gelöscht werden, da bereits verwendet">
  Löschen
</button>
```

---

## Modul-Status (Phase 2 abgeschlossen)

Alle Templates der folgenden Module sind BITV-konform:

| Modul | Templates | Besonderheiten |
|---|---:|---|
| `student/` | 13 | h1, Tabellen, Form-Labels |
| `course/` | 35 | inkl. Timeline-Block, Letter-Workflows mit Dialogen |
| `registration/` | 9 | Login, 2FA, Passwort-Reset mit `aria-invalid`/`aria-describedby` |
| `portal/` | 18 | Self-Service inkl. Stations-Feedback mit `<fieldset>` |
| `absence/` | 11 | Combobox-Pattern für NK-Suche, öffentliches Urlaubsstellen-Portal |
| `proofoftraining/` | 5 | Form-Widget mit dynamischem `aria-label` (Wochentag-Kontext) |
| `assessment/` | 5 | Token-Formular mit Radio-Fieldsets, Form-Widget für `aria-describedby` |
| `instructor/` | 20 | inkl. Koordinations-Detail (5 Tabellen), Änderungs-Workflow |
| `dormitory/` | 10 | Belegungs-Dialog, Generierungs-Statusseite mit `aria-live` |
| `inventory/` | 13 | QR-Etiketten, Bulk-Selection mit korrekten Checkbox-Labels |
| `mandatorytraining/` | 9 | Status-Matrix mit `aria-label`-Badges |
| `workspace/` | 13 | Kalender-Navigation mit `aria-live` für Monatswechsel |
| `studyday/` | 6 | Schlanke Form-Workflows |
| `announcements/` | 5 | Dialog mit `aria-labelledby` (vorher fehlte) |
| `intervention/` | 5 | Eskalations-Frist mit `aria-label`-Icon, disabled mit `aria-disabled` |
| `knowledge/` | 3 | Toggle-Buttons mit `aria-pressed`, Datei-Typ-Icons mit `aria-label` |
| `auditlog/` | 3 | `<th scope="row">` für Feldnamen im Diff-Dialog |
| `organisation/` | 13 | Org-Detail mit 4 Tabellen + 3 Sub-Sections |
| `document/` | 2 | Preview-Dialog (war bereits gut) |
| `services/` | 20 | Settings-Übersicht mit Drei-Ebenen-Hierarchie (h1/h2/h3) |

**Phase-1-Infrastruktur** (`base.html`, `custom.css`):

- Skip-Link in `base.html` (sichtbar bei Tastatur-Fokus)
- `<main id="main-content">` als Sprung-Ziel
- Sidebar-Backdrop als `<button>` (Tastatur-bedienbar, ESC schließt)
- `aria-expanded`/`aria-controls` auf Sidebar-Toggle und Navbar-Suche
- `aria-label` auf den Icon-only Buttons in der Top-Navigation
- DataTables-Filterfelder: sichtbarer Tastatur-Fokus wiederhergestellt
- Native `<dialog>`-Fallback in `kernDialogOpen`
- Erklärung zur Barrierefreiheit unter `/barrierefreiheit/` mit
  konfigurierbarem Text via `SiteConfiguration.barrierefreiheit_text`
- Footer-Link zur Erklärung

---

## Bekannte Limitierungen

Diese Punkte werden in der **Erklärung zur Barrierefreiheit**
(`templates/accessibility.html`, Section „Nicht barrierefreie Inhalte")
ausgewiesen:

1. **PDF/UA für generierte Dokumente** – die Dokumentenablage erfolgt über
   `Paperless-ngx`, das PDF/UA aktuell nicht unterstützt. Nachrüstung wäre
   nach §12c BGG mit unverhältnismäßiger Belastung verbunden. Alternative
   Formate auf Anfrage.
2. **DataTables-Filter** – einzelne Sub-Komponenten (Spaltenfilter,
   Sortier-Pfeile) haben eingeschränkte Screen-Reader-Unterstützung.
3. **Drag-and-Drop in Belegungsplänen** – primär maus-/touch-optimiert.
   Alternative Bedien-Wege (Formularfelder, Detail-Buttons) sind für
   alle Aktionen verfügbar.
4. **Farbkontraste** – noch nicht systematisch gegen AA-Schwellwert
   (4,5:1) geprüft. Kritische Bedienelemente erfüllen den Kontrast.

---

## Pflichten vor Produktivgang

Bevor eine Instanz produktiv geht, muss die Admin-Person unter
**Einstellungen › Impressum & Datenschutz** die folgenden Platzhalter im
„Erklärung zur Barrierefreiheit"-Text ersetzen:

- `[Name der Behörde / Stelle]`
- `[Anschrift]`
- `[barrierefreiheit@example.de]` (Feedback-Kontakt)
- `[+49 …]` (Telefon)
- `[Datum eintragen]` (Datum der Selbstbewertung)

Die Schlichtungsstelle nach §16 BGG ist die Bundesstelle in Berlin – diese
Adresse bleibt unverändert.
