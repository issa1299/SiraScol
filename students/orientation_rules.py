# -*- coding: utf-8 -*-
"""Règles d'orientation du lycée malien — décision pédagogique, jamais automatique.

Les classes de 10ᵉ Commune, 11ᵉ L, 11ᵉ SES et 11ᵉ S sont les seules sources
gérées par ce parcours. Les suffixes de division (A, B, C…) sont ignorés lors
de la reconnaissance, mais conservés pour la répartition des élèves.
"""
import re
import unicodedata

from academics.models import ClassRoom

# Noms de base des classes de destination (par série d'origine).
ORIENTATION_MAP = {
    '10eme commune': ('11eme L', '11eme SES', '11eme S'),
    '11eme l': ('TLL', 'TAL'),
    '11eme ses': ('TSS', 'TSEco'),
    '11eme s': ('TSExp', 'TSE'),
}


def normalize(name):
    """Nom de classe normalisé (sans accents ni ponctuation) pour comparaison."""
    value = unicodedata.normalize('NFKD', (name or '')).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()


def orientation_key(classroom):
    """Clé de la règle applicable à une classe, ou ``None`` si elle n'est pas concernée."""
    norm = normalize(getattr(classroom, 'name', ''))
    if not norm:
        return None
    if norm in ORIENTATION_MAP:
        return norm
    for base in ORIENTATION_MAP:
        rest = norm[len(base):].strip() if norm.startswith(base + ' ') else ''
        if len(rest) == 1 and rest.isalpha():  # ex. « 11ème L A »
            return base
    return None


def is_orientation_classroom(classroom):
    return orientation_key(classroom) is not None


def destination_bases(source_classroom):
    """Noms de base autorisés pour la classe source (tuple vide si non concernée)."""
    key = orientation_key(source_classroom)
    return ORIENTATION_MAP.get(key, ())


def _matching_rooms(source_name, target_year):
    """Classes de l'année cible dont le nom correspond à un nom de base (+ division)."""
    needle = normalize(source_name)
    if not needle:
        return []
    matched = []
    for room in ClassRoom.objects.filter(academic_year=target_year).select_related('level'):
        norm = normalize(room.name)
        if norm == needle or (norm.startswith(needle + ' ') and
                              len(norm[len(needle):].strip()) == 1 and
                              norm[len(needle):].strip().isalpha()):
            matched.append(room)
    return sorted(matched, key=lambda room: room.name)


def destination_classrooms(source_classroom, target_year):
    """Classes de destination autorisées, présentes dans l'année cible."""
    rooms = []
    for base in destination_bases(source_classroom):
        rooms.extend(_matching_rooms(base, target_year))
    # Une classe ne doit pas apparaître deux fois (ex. TSE et TSEco).
    seen = set()
    unique = []
    for room in rooms:
        if room.pk not in seen:
            seen.add(room.pk)
            unique.append(room)
    return sorted(unique, key=lambda room: room.name)


def repetition_classrooms(source_classroom, target_year):
    """Classes de l'année cible portant le même nom que la classe source (redoublement)."""
    return _matching_rooms(source_classroom.name, target_year)


def allowed_destination_ids(source_classroom, target_year, decision):
    """Identifiants acceptés en POST pour une décision donnée (sécurité serveur)."""
    if decision == 'promoted':
        rooms = destination_classrooms(source_classroom, target_year)
    elif decision == 'repeated':
        rooms = repetition_classrooms(source_classroom, target_year)
    else:
        rooms = []
    return {room.pk for room in rooms}
