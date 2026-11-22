# -*- coding: utf-8 -*-
"""Validation partagée de la date de naissance des élèves."""
from datetime import date


def check_birth_date(value):
    """Retourne un message d'erreur si la date est future ou donne < 3 ans."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return 'Date de naissance invalide.'
    today = date.today()
    if value > today:
        return 'La date de naissance ne peut pas être dans le futur.'
    try:
        third_birthday = value.replace(year=value.year + 3)
    except ValueError:  # 29 février
        third_birthday = value.replace(year=value.year + 3, day=28)
    if today < third_birthday:
        return 'L’élève doit avoir au moins 3 ans.'
    return None
