# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TTL_DOCUMENTS = 3600          # 1h für Studi-/Kurs-Dokumentenlisten
CACHE_TTL_UNASSIGNED = 600          # 10min für Eingangskorb (Beat refresht alle 2min)
CACHE_TTL_DOCUMENT_TYPES = 86400    # 24h für quasi-statische Dokumenttypen
CACHE_TTL_DOC_CORRESPONDENT = 3600  # 1h für Dok→Korrespondent-Mapping (Berechtigungs-Lookup)
CACHE_KEY_UNASSIGNED = 'paperless:unassigned'
CACHE_KEY_DOCUMENT_TYPES = 'paperless:document_types'


def _cache_key_student(student_id) -> str:
    return f'paperless:student:{student_id}'


def _cache_key_course(course_title: str) -> str:
    return f'paperless:course:{course_title}'


def _cache_key_doc_correspondent(doc_id) -> str:
    return f'paperless:doc:{doc_id}:correspondent'


class PaperlessService:
    """Kapselt alle Aufrufe an die Paperless-ngx REST API."""

    TIMEOUT = 10

    # ─────────────────────────────────────────
    #  Cache-Invalidierung
    # ─────────────────────────────────────────

    @staticmethod
    def invalidate_unassigned():
        cache.delete(CACHE_KEY_UNASSIGNED)

    @staticmethod
    def invalidate_student(student_id):
        cache.delete(_cache_key_student(student_id))

    @staticmethod
    def invalidate_course(course_title: str):
        cache.delete(_cache_key_course(course_title))

    @staticmethod
    def invalidate_doc_correspondent(doc_id):
        cache.delete(_cache_key_doc_correspondent(doc_id))

    @classmethod
    def invalidate_for_correspondent(cls, correspondent_id: int | None):
        """Findet den Korrespondenten zur ID und invalidiert dessen Cache (Studi oder Kurs)."""
        if correspondent_id is None:
            return
        try:
            resp = requests.get(
                f"{cls._base()}/api/correspondents/{correspondent_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            resp.raise_for_status()
            name = resp.json().get('name')
            if not name:
                return
            cache.delete(_cache_key_student(name))
            cache.delete(_cache_key_course(name))
        except requests.RequestException as e:
            logger.warning("Korrespondenten-Lookup für Cache-Invalidierung fehlgeschlagen: %s", e)

    @classmethod
    def _base(cls):
        from services.models import SiteConfiguration
        config = SiteConfiguration.get()
        url = config.paperless_url or settings.PAPERLESS_URL
        return url.rstrip('/')

    @classmethod
    def _headers(cls):
        from services.models import SiteConfiguration
        config = SiteConfiguration.get()
        api_key = config.paperless_api_key or settings.PAPERLESS_API_KEY
        return {"Authorization": f"Token {api_key}"}

    # ─────────────────────────────────────────
    #  Eingangskorb
    # ─────────────────────────────────────────

    @classmethod
    def get_unassigned_documents(cls, force_refresh: bool = False) -> list[dict]:
        """Gibt alle Dokumente zurück, denen noch kein Korrespondent zugewiesen ist."""
        if not force_refresh:
            cached = cache.get(CACHE_KEY_UNASSIGNED)
            if cached is not None:
                return cached
        results = cls._fetch_unassigned_documents()
        cache.set(CACHE_KEY_UNASSIGNED, results, timeout=CACHE_TTL_UNASSIGNED)
        return results

    @classmethod
    def _fetch_unassigned_documents(cls) -> list[dict]:
        try:
            results = []
            page = 1
            while True:
                response = requests.get(
                    f"{cls._base()}/api/documents/",
                    headers=cls._headers(),
                    timeout=cls.TIMEOUT,
                    params={
                        "correspondent__isnull": "true",
                        "ordering": "-created",
                        "page_size": 100,
                        "page": page,
                    },
                )
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("results", []))
                if not data.get("next"):
                    break
                page += 1
            return results

        except requests.HTTPError as e:
            logger.error(
                "Paperless-ngx HTTP-Fehler beim Laden des Eingangskorbs: %s – %s",
                e.response.status_code, e.response.text,
            )
            return []
        except requests.RequestException as e:
            logger.error("Paperless-ngx Verbindungsfehler: %s", e)
            return []

    # ─────────────────────────────────────────
    #  Zuweisung
    # ─────────────────────────────────────────

    @classmethod
    def assign_student(cls, paperless_doc_id: int, student_id: str) -> bool:
        """
        Weist ein Paperless-Dokument einem Studierenden zu,
        indem der Korrespondent auf die student_id gesetzt wird.
        Der Korrespondent wird bei Bedarf automatisch angelegt.
        """
        try:
            correspondent_id = cls._get_or_create_correspondent(student_id)
            if correspondent_id is None:
                return False

            response = requests.patch(
                f"{cls._base()}/api/documents/{paperless_doc_id}/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json={"correspondent": correspondent_id},
            )
            response.raise_for_status()
            cls.invalidate_unassigned()
            cls.invalidate_student(student_id)
            cls.invalidate_doc_correspondent(paperless_doc_id)
            return True

        except requests.HTTPError as e:
            logger.error(
                "Paperless-ngx PATCH fehlgeschlagen für Dok. %s: %s – %s",
                paperless_doc_id, e.response.status_code, e.response.text,
            )
            return False
        except requests.RequestException as e:
            logger.error("Paperless-ngx Verbindungsfehler bei Zuweisung: %s", e)
            return False

    @classmethod
    def assign_document_type(cls, paperless_doc_id: int, type_name: str) -> bool:
        """Setzt den Dokumenttyp eines Paperless-Dokuments und legt ihn bei Bedarf an."""
        try:
            type_id = cls._get_or_create_document_type(type_name)
            if type_id is None:
                return False

            response = requests.patch(
                f"{cls._base()}/api/documents/{paperless_doc_id}/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json={"document_type": type_id},
            )
            response.raise_for_status()
            cls.invalidate_doc_correspondent(paperless_doc_id)
            return True
        except requests.HTTPError as e:
            logger.error(
                "Paperless-ngx PATCH document_type fehlgeschlagen für Dok. %s: %s – %s",
                paperless_doc_id, e.response.status_code, e.response.text,
            )
            return False
        except requests.RequestException as e:
            logger.error("Paperless-ngx Verbindungsfehler bei Typ-Zuweisung: %s", e)
            return False

    @classmethod
    def _get_or_create_document_type(cls, name: str) -> int | None:
        """Sucht einen Dokumenttyp nach Name oder legt ihn neu an."""
        try:
            for dt in cls.get_document_types():
                if dt.get("name", "").lower() == name.lower():
                    return dt["id"]
            response = requests.post(
                f"{cls._base()}/api/document_types/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json={"name": name},
            )
            response.raise_for_status()
            cls.get_document_types(force_refresh=True)
            return response.json()["id"]
        except requests.RequestException as e:
            logger.error("Dokumenttyp '%s' konnte nicht angelegt werden: %s", name, e)
            return None

    @classmethod
    def assign_course(cls, paperless_doc_id: int, course_title: str) -> bool:
        """
        Weist ein Paperless-Dokument einem Kurs zu,
        indem der Korrespondent auf den Kurs-Titel gesetzt wird.
        Der Korrespondent wird bei Bedarf automatisch angelegt.
        """
        try:
            correspondent_id = cls._get_or_create_correspondent(course_title)
            if correspondent_id is None:
                return False

            response = requests.patch(
                f"{cls._base()}/api/documents/{paperless_doc_id}/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json={"correspondent": correspondent_id},
            )
            response.raise_for_status()
            cls.invalidate_unassigned()
            cls.invalidate_course(course_title)
            cls.invalidate_doc_correspondent(paperless_doc_id)
            return True

        except requests.HTTPError as e:
            logger.error(
                "Paperless-ngx PATCH fehlgeschlagen für Dok. %s: %s – %s",
                paperless_doc_id, e.response.status_code, e.response.text,
            )
            return False
        except requests.RequestException as e:
            logger.error("Paperless-ngx Verbindungsfehler bei Kurs-Zuweisung: %s", e)
            return False

    # ─────────────────────────────────────────
    #  Metadaten bearbeiten
    # ─────────────────────────────────────────

    @classmethod
    def update_document(cls, doc_id: int, title: str = None, created: str = None) -> bool:
        """Aktualisiert Titel und/oder Datum eines Paperless-Dokuments."""
        data = {}
        if title is not None:
            data['title'] = title
        if created is not None:
            data['created'] = created  # ISO-Format: YYYY-MM-DD
        if not data:
            return True
        try:
            resp = requests.patch(
                f"{cls._base()}/api/documents/{doc_id}/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json=data,
            )
            resp.raise_for_status()
            cls.invalidate_unassigned()
            try:
                doc_resp = requests.get(
                    f"{cls._base()}/api/documents/{doc_id}/",
                    headers=cls._headers(),
                    timeout=cls.TIMEOUT,
                )
                doc_resp.raise_for_status()
                cls.invalidate_for_correspondent(doc_resp.json().get('correspondent'))
            except requests.RequestException:
                pass
            return True
        except requests.HTTPError as e:
            logger.error(
                "Paperless-ngx PATCH Metadaten fehlgeschlagen für Dok. %s: %s – %s",
                doc_id, e.response.status_code, e.response.text,
            )
            return False
        except requests.RequestException as e:
            logger.error("Paperless-ngx Verbindungsfehler beim Metadaten-Update: %s", e)
            return False

    # ─────────────────────────────────────────
    #  Upload
    # ─────────────────────────────────────────

    @classmethod
    def upload_document(cls, file, title: str) -> requests.Response:
        """Lädt ein Dokument in Paperless-ngx hoch."""
        resp = requests.post(
            f"{cls._base()}/api/documents/post_document/",
            headers=cls._headers(),
            timeout=30,
            data={"title": title},
            files={"document": file},
        )
        cls.invalidate_unassigned()
        return resp

    @classmethod
    def upload_and_wait(
        cls,
        file_bytes: bytes,
        title: str,
        student_id: str,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf",
        timeout: int = 30,
    ) -> int | None:
        """
        Lädt eine Datei hoch, wartet auf die Verarbeitung durch Paperless-ngx
        und weist danach den Studierenden als Korrespondenten zu.
        Gibt die Paperless-Dokument-ID zurück oder None bei Fehler/Timeout.
        """
        import time

        try:
            resp = requests.post(
                f"{cls._base()}/api/documents/post_document/",
                headers=cls._headers(),
                timeout=30,
                data={"title": title},
                files={"document": (filename, file_bytes, mime_type)},
            )
            resp.raise_for_status()
            task_id = resp.json()  # Paperless returns the UUID task ID as plain string
        except requests.RequestException as e:
            logger.error("Paperless-ngx Upload fehlgeschlagen: %s", e)
            return None

        # Task-Endpoint pollen, bis SUCCESS oder Timeout erreicht ist
        deadline = time.time() + timeout
        doc_id = None
        while time.time() < deadline:
            time.sleep(1)
            try:
                task_resp = requests.get(
                    f"{cls._base()}/api/tasks/",
                    headers=cls._headers(),
                    params={"task_id": task_id},
                    timeout=cls.TIMEOUT,
                )
                task_resp.raise_for_status()
                tasks = task_resp.json()
                if tasks and tasks[0].get("status") == "SUCCESS":
                    doc_id = tasks[0].get("related_document")
                    break
                if tasks and tasks[0].get("status") == "FAILURE":
                    logger.error("Paperless-ngx Task fehlgeschlagen: %s", tasks[0])
                    return None
            except requests.RequestException as e:
                logger.warning("Paperless-ngx Task-Polling Fehler: %s", e)

        if doc_id is None:
            logger.error("Paperless-ngx: Timeout beim Warten auf Dokument (task %s)", task_id)
            return None

        cls.assign_student(doc_id, student_id)
        return doc_id

    @classmethod
    def upload_and_wait_simple(
        cls,
        file_bytes: bytes,
        title: str,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf",
        document_type: str | None = None,
        timeout: int = 30,
    ) -> int | None:
        """
        Lädt eine Datei hoch und wartet auf die Verarbeitung – ohne Korrespondenten-Zuweisung.
        Optional wird ein Dokumenttyp gesetzt (Name; wird bei Bedarf in Paperless angelegt).
        """
        import time

        try:
            resp = requests.post(
                f"{cls._base()}/api/documents/post_document/",
                headers=cls._headers(),
                timeout=30,
                data={"title": title},
                files={"document": (filename, file_bytes, mime_type)},
            )
            resp.raise_for_status()
            task_id = resp.json()
        except requests.RequestException as e:
            logger.error("Paperless-ngx Upload fehlgeschlagen: %s", e)
            return None

        deadline = time.time() + timeout
        doc_id = None
        while time.time() < deadline:
            time.sleep(1)
            try:
                task_resp = requests.get(
                    f"{cls._base()}/api/tasks/",
                    headers=cls._headers(),
                    params={"task_id": task_id},
                    timeout=cls.TIMEOUT,
                )
                task_resp.raise_for_status()
                tasks = task_resp.json()
                if tasks and tasks[0].get("status") == "SUCCESS":
                    doc_id = tasks[0].get("related_document")
                    break
                if tasks and tasks[0].get("status") == "FAILURE":
                    logger.error("Paperless-ngx Task fehlgeschlagen: %s", tasks[0])
                    return None
            except requests.RequestException as e:
                logger.warning("Paperless-ngx Task-Polling Fehler: %s", e)

        if doc_id is None:
            logger.error("Paperless-ngx: Timeout beim Warten auf Dokument (task %s)", task_id)
            return None

        if document_type:
            cls.assign_document_type(doc_id, document_type)
        return doc_id

    # ─────────────────────────────────────────
    #  Löschen
    # ─────────────────────────────────────────

    @classmethod
    def download_document(cls, doc_id: int) -> tuple[bytes, str] | None:
        """
        Lädt den Inhalt eines Paperless-Dokuments herunter.
        Gibt (bytes, original_filename) zurück oder None bei Fehler.
        """
        try:
            resp = requests.get(
                f"{cls._base()}/api/documents/{doc_id}/download/",
                headers=cls._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            # Content-Disposition: attachment; filename="..."
            disposition = resp.headers.get('Content-Disposition', '')
            filename = 'bewertung.pdf'
            if 'filename=' in disposition:
                filename = disposition.split('filename=')[-1].strip().strip('"')
            return resp.content, filename
        except requests.RequestException as e:
            logger.error("Paperless: Dokument %s konnte nicht heruntergeladen werden: %s", doc_id, e)
            return None

    @classmethod
    def download_pdf(cls, doc_id: int) -> bytes | None:
        """Lädt die von Paperless gerenderte PDF-Version eines Dokuments."""
        try:
            resp = requests.get(
                f"{cls._base()}/api/documents/{doc_id}/download/",
                headers=cls._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            logger.error("Paperless: PDF für Dokument %s konnte nicht geladen werden: %s", doc_id, e)
            return None

    @classmethod
    def get_document_title(cls, doc_id: int) -> str | None:
        """Gibt den Titel eines Paperless-Dokuments zurück oder None bei Fehler."""
        try:
            resp = requests.get(
                f"{cls._base()}/api/documents/{doc_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("title")
        except requests.RequestException as e:
            logger.error("Paperless: Titel für Dokument %s konnte nicht abgerufen werden: %s", doc_id, e)
            return None

    @classmethod
    def get_correspondent_name_for_document(cls, doc_id, force_refresh: bool = False) -> str | None:
        """Liefert den Korrespondent-Namen eines Dokuments (= ``student.pk`` oder Kurstitel).

        Cached, weil dieser Lookup bei jedem Dokument-Download für die
        Berechtigungsprüfung anfällt. Wird invalidiert sobald sich der
        Korrespondent eines Dokuments ändert (``assign_student`` /
        ``assign_course`` / ``delete_document``).
        """
        key = _cache_key_doc_correspondent(doc_id)
        if not force_refresh:
            cached = cache.get(key)
            if cached is not None:
                # Sentinel '' bedeutet "kein Korrespondent" — vermeidet erneuten Lookup
                return cached or None
        name = cls._fetch_correspondent_name_for_document(doc_id)
        cache.set(key, name or '', timeout=CACHE_TTL_DOC_CORRESPONDENT)
        return name

    @classmethod
    def _fetch_correspondent_name_for_document(cls, doc_id) -> str | None:
        try:
            resp = requests.get(
                f"{cls._base()}/api/documents/{doc_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            resp.raise_for_status()
            correspondent_id = resp.json().get('correspondent')
            if not correspondent_id:
                return None
            c_resp = requests.get(
                f"{cls._base()}/api/correspondents/{correspondent_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            c_resp.raise_for_status()
            return c_resp.json().get('name')
        except requests.RequestException as e:
            logger.error(
                "Paperless: Korrespondent für Dokument %s konnte nicht ermittelt werden: %s",
                doc_id, e,
            )
            return None

    @classmethod
    def delete_document(cls, doc_id: int) -> bool:
        """Löscht ein Dokument in Paperless-ngx."""
        correspondent_id = None
        try:
            doc_resp = requests.get(
                f"{cls._base()}/api/documents/{doc_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            doc_resp.raise_for_status()
            correspondent_id = doc_resp.json().get('correspondent')
        except requests.RequestException:
            pass

        try:
            resp = requests.delete(
                f"{cls._base()}/api/documents/{doc_id}/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
            )
            resp.raise_for_status()
            cls.invalidate_unassigned()
            cls.invalidate_for_correspondent(correspondent_id)
            cls.invalidate_doc_correspondent(doc_id)
            return True
        except requests.RequestException as e:
            logger.error("Paperless: Dokument %s konnte nicht gelöscht werden: %s", doc_id, e)
            return False

    # ─────────────────────────────────────────
    #  Dokumente eines Studierenden abrufen
    # ─────────────────────────────────────────

    @classmethod
    def get_documents_for_student(cls, student_id, force_refresh: bool = False) -> list[dict]:
        """Gibt alle Dokumente zurück, die einem Studierenden zugeordnet sind."""
        key = _cache_key_student(student_id)
        if not force_refresh:
            cached = cache.get(key)
            if cached is not None:
                return cached
        results = cls._fetch_documents_for_student(student_id)
        cache.set(key, results, timeout=CACHE_TTL_DOCUMENTS)
        return results

    @classmethod
    def _fetch_documents_for_student(cls, student_id) -> list[dict]:
        try:
            correspondent_id = cls._find_correspondent(student_id)
            if correspondent_id is None:
                return []

            response = requests.get(
                f"{cls._base()}/api/documents/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
                params={
                    "correspondent__id": correspondent_id,
                    "ordering": "-created",
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])

        except requests.RequestException as e:
            logger.error(
                "Paperless-ngx: Dokumente für %s konnten nicht geladen werden: %s",
                student_id, e,
            )
            return []

    # ─────────────────────────────────────────
    #  Volltext-Suche
    # ─────────────────────────────────────────

    @classmethod
    def search_documents_for_student(cls, student_id: str, query: str) -> list[dict]:
        """Volltextsuche in den Dokumenten eines Studierenden via Paperless-ngx."""
        try:
            correspondent_id = cls._find_correspondent(student_id)
            if correspondent_id is None:
                return []

            response = requests.get(
                f"{cls._base()}/api/documents/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
                params={
                    "correspondent__id": correspondent_id,
                    "query": query,
                    "ordering": "-created",
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])

        except requests.RequestException as e:
            logger.error("Paperless-ngx Volltextsuche fehlgeschlagen: %s", e)
            return []

    # ─────────────────────────────────────────
    #  Dokumente eines Kurses abrufen
    # ─────────────────────────────────────────

    @classmethod
    def get_documents_for_course(cls, course_title: str, force_refresh: bool = False) -> list[dict]:
        """Gibt alle Dokumente zurück, die einem Kurs zugeordnet sind."""
        key = _cache_key_course(course_title)
        if not force_refresh:
            cached = cache.get(key)
            if cached is not None:
                return cached
        results = cls._fetch_documents_for_course(course_title)
        cache.set(key, results, timeout=CACHE_TTL_DOCUMENTS)
        return results

    @classmethod
    def _fetch_documents_for_course(cls, course_title: str) -> list[dict]:
        try:
            correspondent_id = cls._find_correspondent(course_title)
            if correspondent_id is None:
                return []

            response = requests.get(
                f"{cls._base()}/api/documents/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
                params={
                    "correspondent__id": correspondent_id,
                    "ordering": "-created",
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])

        except requests.RequestException as e:
            logger.error(
                "Paperless-ngx: Dokumente für Kurs '%s' konnten nicht geladen werden: %s",
                course_title, e,
            )
            return []

    @classmethod
    def search_documents_for_course(cls, course_title: str, query: str) -> list[dict]:
        """Volltextsuche in den Dokumenten eines Kurses via Paperless-ngx."""
        try:
            correspondent_id = cls._find_correspondent(course_title)
            if correspondent_id is None:
                return []

            response = requests.get(
                f"{cls._base()}/api/documents/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
                params={
                    "correspondent__id": correspondent_id,
                    "query": query,
                    "ordering": "-created",
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])

        except requests.RequestException as e:
            logger.error("Paperless-ngx Volltextsuche für Kurs fehlgeschlagen: %s", e)
            return []

    @classmethod
    def upload_and_wait_for_course(
        cls,
        file_bytes: bytes,
        title: str,
        course_title: str,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf",
        timeout: int = 30,
    ) -> int | None:
        """
        Lädt eine Datei hoch, wartet auf die Verarbeitung durch Paperless-ngx
        und weist danach den Kurs als Korrespondenten zu.
        Gibt die Paperless-Dokument-ID zurück oder None bei Fehler/Timeout.
        """
        import time

        try:
            resp = requests.post(
                f"{cls._base()}/api/documents/post_document/",
                headers=cls._headers(),
                timeout=30,
                data={"title": title},
                files={"document": (filename, file_bytes, mime_type)},
            )
            resp.raise_for_status()
            task_id = resp.json()
        except requests.RequestException as e:
            logger.error("Paperless-ngx Upload fehlgeschlagen: %s", e)
            return None

        deadline = time.time() + timeout
        doc_id = None
        while time.time() < deadline:
            time.sleep(1)
            try:
                task_resp = requests.get(
                    f"{cls._base()}/api/tasks/",
                    headers=cls._headers(),
                    params={"task_id": task_id},
                    timeout=cls.TIMEOUT,
                )
                task_resp.raise_for_status()
                tasks = task_resp.json()
                if tasks and tasks[0].get("status") == "SUCCESS":
                    doc_id = tasks[0].get("related_document")
                    break
                if tasks and tasks[0].get("status") == "FAILURE":
                    logger.error("Paperless-ngx Task fehlgeschlagen: %s", tasks[0])
                    return None
            except requests.RequestException as e:
                logger.warning("Paperless-ngx Task-Polling Fehler: %s", e)

        if doc_id is None:
            logger.error("Paperless-ngx: Timeout beim Warten auf Dokument (task %s)", task_id)
            return None

        correspondent_id = cls._get_or_create_correspondent(course_title)
        if correspondent_id:
            try:
                requests.patch(
                    f"{cls._base()}/api/documents/{doc_id}/",
                    headers={**cls._headers(), "Content-Type": "application/json"},
                    timeout=cls.TIMEOUT,
                    json={"correspondent": correspondent_id},
                )
                cls.invalidate_unassigned()
                cls.invalidate_course(course_title)
            except requests.RequestException as e:
                logger.error(
                    "Paperless-ngx: Kurs-Zuweisung fehlgeschlagen für Dok. %s: %s", doc_id, e,
                )
        return doc_id

    # ─────────────────────────────────────────
    #  Hilfsmethoden
    # ─────────────────────────────────────────

    @classmethod
    def _get_or_create_correspondent(cls, name: str) -> int | None:
        """Sucht einen Korrespondenten nach Name oder legt ihn neu an."""
        try:
            existing_id = cls._find_correspondent(name)
            if existing_id is not None:
                return existing_id

            response = requests.post(
                f"{cls._base()}/api/correspondents/",
                headers={**cls._headers(), "Content-Type": "application/json"},
                timeout=cls.TIMEOUT,
                json={"name": name},
            )
            response.raise_for_status()
            return response.json()["id"]

        except requests.RequestException as e:
            logger.error("Korrespondent '%s' konnte nicht angelegt werden: %s", name, e)
            return None

    @classmethod
    def get_document_types(cls, force_refresh: bool = False) -> list[dict]:
        """Gibt alle Dokumenttypen aus Paperless zurück."""
        if not force_refresh:
            cached = cache.get(CACHE_KEY_DOCUMENT_TYPES)
            if cached is not None:
                return cached
        results = cls._fetch_document_types()
        cache.set(CACHE_KEY_DOCUMENT_TYPES, results, timeout=CACHE_TTL_DOCUMENT_TYPES)
        return results

    @classmethod
    def _fetch_document_types(cls) -> list[dict]:
        try:
            results = []
            page = 1
            while True:
                response = requests.get(
                    f"{cls._base()}/api/document_types/",
                    headers=cls._headers(),
                    timeout=cls.TIMEOUT,
                    params={"page_size": 100, "page": page},
                )
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("results", []))
                if not data.get("next"):
                    break
                page += 1
            return results
        except requests.RequestException as e:
            logger.error("Dokumenttypen konnten nicht geladen werden: %s", e)
            return []

    @classmethod
    def _find_correspondent(cls, name: str) -> int | None:
        """Gibt die ID eines Korrespondenten zurück oder None wenn nicht gefunden."""
        try:
            response = requests.get(
                f"{cls._base()}/api/correspondents/",
                headers=cls._headers(),
                timeout=cls.TIMEOUT,
                params={"name__iexact": name},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            return results[0]["id"] if results else None

        except requests.RequestException as e:
            logger.error("Korrespondenten-Suche fehlgeschlagen: %s", e)
            return None
