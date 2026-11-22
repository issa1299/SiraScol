# -*- coding: utf-8 -*-
"""Validateurs partagés pour les fichiers uploadés."""
from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 Mo

ALLOWED_EXTENSIONS = {
    '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv',
}


def validate_upload(file):
    """Refuse les fichiers trop gros ou aux extensions exécutables.

    À utiliser comme `validators=[validate_upload]` sur les FileField/ImageField.
    """
    name = (getattr(file, 'name', '') or '').lower()
    ext = ''
    if '.' in name:
        ext = '.' + name.rsplit('.', 1)[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f'Extension « {ext or "(aucune)"} » non autorisée. '
            f'Formats acceptés : {", ".join(sorted(ALLOWED_EXTENSIONS))}.'
        )
    if file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f'Fichier trop volumineux ({file.size // 1024 // 1024} Mo). '
            f'Limite : {MAX_UPLOAD_BYTES // 1024 // 1024} Mo.'
        )
    return file
