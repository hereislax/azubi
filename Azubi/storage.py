# SPDX-License-Identifier: EUPL-1.2
# SPDX-FileCopyrightText: 2026 devNicoLax
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Wie CompressedManifestStaticFilesStorage, bricht aber nicht ab wenn
    referenzierte Dateien fehlen (z. B. Source-Map-Kommentare in Bootstrap).
    """

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name
