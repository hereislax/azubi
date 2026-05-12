# Barrierefreiheit (BITV 2.0 / WCAG 2.1 AA)

Diese Datei fasst die Konventionen zusammen, die in allen Templates eingehalten
werden müssen, damit das Portal die Anforderungen der
**Barrierefreie-Informationstechnik-Verordnung (BITV 2.0)** und damit der
**Web Content Accessibility Guidelines 2.1 Stufe AA** erfüllt.

Phase 1 (Audit + Sofortmaßnahmen) ist umgesetzt. Diese Datei ist die Vorlage
für Phase 2 (systematische Sweeps in einzelnen Modulen).

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

### 3. Icon-only Buttons und Links

`title=""` allein genügt **nicht** für Screen Reader. Pflicht:

```html
<button type="button" class="btn btn-sm btn-outline-danger"
        aria-label="Eintrag {{ obj.name }} löschen">
  <i class="bi bi-trash" aria-hidden="true"></i>
</button>
```

Faustregel: Wenn ein Button ausschließlich ein `<i class="bi …"></i>` enthält,
braucht er `aria-label="…"`. Das Icon selbst bekommt `aria-hidden="true"`.

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

### 5. Formulare

- **Jedes Eingabefeld** braucht ein `<label for="…">`. `placeholder=""` ist
  **kein** Ersatz.
- Pflichtfelder: `required` **und** `aria-required="true"`. Das `*` neben dem
  Label bekommt `aria-label="erforderlich"` oder steckt im Label-Text.
- Fehlerausgabe via `aria-invalid="true"` und `aria-describedby="…-error"`:

```html
<input id="id_username" name="username" required aria-required="true"
       aria-invalid="{% if form.username.errors %}true{% else %}false{% endif %}"
       aria-describedby="id_username-error">
{% if form.username.errors %}
  <div id="id_username-error" class="text-danger small">
    {{ form.username.errors|join:" " }}
  </div>
{% endif %}
```

### 6. Farbe ist nie alleiniger Bedeutungsträger

Status-Badges immer mit Text **oder** Icon **und** Beschriftung. Beispiel:

```html
<span class="badge bg-success">
  <i class="bi bi-check-circle" aria-hidden="true"></i>
  Genehmigt
</span>
```

### 7. Sprachwechsel

Englische Begriffe im deutschen Text mit `lang="en"` markieren, z.B.
`<span lang="en">Service Worker</span>`.

### 8. Fokus-Indikator

Niemals `outline: none` ohne sichtbaren Ersatz. Wenn der globale `:focus-visible`-
Ring stört, mit `:focus-visible` (Pseudoklasse) targeten – nicht mit `:focus`.

### 9. Onclick auf div / span / a verboten

Interaktive Elemente sind `<button>` oder `<a href>`. Wenn `onclick` auf einem
nicht-fokussierbaren Element nötig erscheint, ist meist ein Button die richtige
Wahl.

---

## Was Phase 1 bereits liefert

- Skip-Link in `base.html` (sichtbar bei Tastatur-Fokus)
- `<main id="main-content">` als Sprung-Ziel
- Sidebar-Backdrop als `<button>` (Tastatur-bedienbar, ESC schließt)
- `aria-expanded`/`aria-controls` auf Sidebar-Toggle und Navbar-Suche
- `aria-label` auf den Icon-only Buttons in der Top-Navigation
- DataTables-Filterfelder: sichtbarer Tastatur-Fokus wiederhergestellt
- Native `<dialog>`-Fallback in `kernDialogOpen`
- Erklärung zur Barrierefreiheit unter `/barrierefreiheit/`
- Footer-Link zur Erklärung

## Was in Phase 2 noch zu tun ist

- `<h1>` auf allen Modulseiten (Student-Liste, Detailseiten, Reports, …)
- `<th scope="col">` & `<caption>` in allen Listen-Tabellen
- `aria-label` auf allen modulinternen Icon-only Buttons
- `aria-labelledby` auf allen Bootstrap-Modals und kern-dialogs
- `aria-invalid` / `aria-describedby` via Form-Widget oder Template-Tag
- Sprach-Markierung in `acknowledgments.html`

PDF-Barrierefreiheit (PDF/UA) bleibt außerhalb dieses Projekts: die Dokumenten-
ablage erfolgt über Paperless-ngx, das selbst nicht PDF/UA produziert. Für die
Erklärung zur Barrierefreiheit unter „Nicht barrierefreie Inhalte" weiterhin
auflisten – das ist eine zulässige unverhältnismäßige Belastung nach §12c BGG.
