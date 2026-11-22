# -*- coding: utf-8 -*-
"""Badges scolaires unifiés : élèves ET personnel, même modèle, même QR.

Toutes les vues (HTML, PNG, PDF, aperçu) consomment le même contexte construit
ici. Les couleurs sont celles proposées dans les paramètres de l'école.
"""
from datetime import date
from urllib.parse import quote

from django.urls import reverse

from .qr import badge_payload

# Format CR80 (carte bancaire)
CARD_W_MM = 85.6
CARD_H_MM = 54.0

LABEL_COLOR = '#4f5f54'

# Les clés correspondent exactement à SchoolSettings.CARD_TEMPLATE_CHOICES
# `label` = nom affiché du modèle ; `label_color` = couleur des étiquettes.
BADGE_DESIGNS = {
    'official': {
        'label': 'Officiel — vert & or',
        'primary': '#0c4a37', 'secondary': '#0c4a37', 'accent': '#e8b94a',
        'band': '#0c4a37', 'bg': '#fcfbf7', 'ink': '#111827', 'muted': '#6b7280',
        'photo_bg': '#e7eee9', 'footer': '#0c4a37', 'caption': '#4f5f54',
        'label_color': '#4f5f54',
    },
    'modern': {
        'label': 'Moderne — bleu nuit & or',
        'primary': '#0f172a', 'secondary': '#1e293b', 'accent': '#fbbf24',
        'band': '#fbbf24', 'bg': '#f8fafc', 'ink': '#0f172a', 'muted': '#475569',
        'photo_bg': '#e8edf2', 'caption': LABEL_COLOR, 'label_color': LABEL_COLOR,
    },
    'classic': {
        'label': 'Classique — bleu roi',
        'primary': '#1d4ed8', 'secondary': '#2563eb', 'accent': '#60a5fa',
        'band': '#1e3a8a', 'bg': '#ffffff', 'ink': '#0f172a', 'muted': '#475569',
        'photo_bg': '#e6ecf7', 'caption': LABEL_COLOR, 'label_color': LABEL_COLOR,
    },
    'gold': {
        'label': 'Prestige — or & noir',
        'primary': '#111827', 'secondary': '#1f2937', 'accent': '#d4af37',
        'band': '#d4af37', 'bg': '#fffdf7', 'ink': '#111827', 'muted': '#4b5563',
        'photo_bg': '#f0ece0', 'caption': LABEL_COLOR, 'label_color': LABEL_COLOR,
    },
    'green': {
        'label': 'Émeraude',
        'primary': '#065f46', 'secondary': '#047857', 'accent': '#34d399',
        'band': '#059669', 'bg': '#f6fefb', 'ink': '#064e3b', 'muted': '#3f6b5b',
        'photo_bg': '#e3efe8', 'caption': LABEL_COLOR, 'label_color': LABEL_COLOR,
    },
    'burgundy': {
        'label': 'Bordeaux',
        'primary': '#7f1d1d', 'secondary': '#991b1b', 'accent': '#fca5a5',
        'band': '#7f1d1d', 'bg': '#fffafa', 'ink': '#450a0a', 'muted': '#7f4b4b',
        'photo_bg': '#f1e4e4', 'caption': LABEL_COLOR, 'label_color': LABEL_COLOR,
    },
}


def get_badge_design(key):
    return BADGE_DESIGNS.get(key) or BADGE_DESIGNS['official']


def parents_pair(student):
    """Retourne (père/tuteur, mère) pour un élève."""
    father = mother = None
    try:
        links = list(student.parents.select_related('parent').all())
    except Exception:
        links = []
    for link in links:
        rel = (getattr(link, 'relation', '') or '').lower()
        p = link.parent
        name = f'{p.last_name} {p.first_name}'.strip()
        if rel in ('pere', 'père', 'father') and not father:
            father = name
        elif rel in ('mere', 'mère', 'mother') and not mother:
            mother = name
        elif rel in ('tuteur', 'tutrice', 'tutor') and not father:
            father = name
        elif not father:
            father = name
        elif not mother:
            mother = name
    return father or '—', mother or '—'


def school_context(school):
    """En-tête de l'établissement, réutilisé par tous les rendus."""
    name = (getattr(school, 'name', None) if school else None) or ''
    motto = ''
    if school and getattr(school, 'motto', None):
        motto = school.motto
    else:
        motto = 'TRAVAIL - DISCIPLINE - REUSSITE'

    left_raw = (getattr(school, 'header_left', None) if school else None) or ''
    if not left_raw and school:
        parts = ['M.E.N']
        if getattr(school, 'inspection', None):
            parts.append(school.inspection)
        place = getattr(school, 'commune', None) or getattr(school, 'city', None)
        if place:
            parts.append(f'A.E DE {place}'.upper())
        left_raw = '\n'.join(parts)
    left_lines = [ln.strip() for ln in left_raw.replace('|', '\n').split('\n') if ln.strip()][:3]
    if not left_lines:
        left_lines = ['M.E.N']

    right_raw = (getattr(school, 'header_right', None) if school else None) or ''
    if not right_raw:
        country = (getattr(school, 'country', None) if school else None) or 'MALI'
        right_raw = f'REPUBLIQUE DU {str(country).upper()}\nUN PEUPLE - UN BUT - UNE FOI'
    right_lines = [ln.strip() for ln in right_raw.replace('|', '\n').split('\n') if ln.strip()][:2]

    logo_path = stamp_path = None
    if school:
        for attr, target in (('logo', 'logo_path'), ('stamp', 'stamp_path')):
            try:
                f = getattr(school, attr, None)
                if f:
                    path = f.path
                    if target == 'logo_path':
                        logo_path = path
                    else:
                        stamp_path = path
            except Exception:
                pass

    director = (getattr(school, 'director_name', None) if school else None) or '—'
    city = (getattr(school, 'city', None) if school else None) or ''
    place = city  # Ville seule, sans crochets ni pays ajouté.

    logo_url = stamp_url = None
    if school:
        try:
            if school.logo:
                logo_url = school.logo.url
        except Exception:
            pass
        try:
            if school.stamp:
                stamp_url = school.stamp.url
        except Exception:
            pass

    year_label = (getattr(school, 'academic_year_label', None) if school else None) or ''
    if not year_label:
        today = date.today()
        year_label = f'{today.year}-{today.year + 1}'

    return {
        'name': name,
        'motto': motto.upper(),
        'left_lines': left_lines,
        'right_lines': right_lines,
        'director': director,
        'logo_path': logo_path,
        'stamp_path': stamp_path,
        'logo_url': logo_url,
        'stamp_url': stamp_url,
        'city': city,
        'place': place,
        'year_label': year_label,
    }


def _photo_path(person):
    try:
        if person.photo:
            return person.photo.path
    except Exception:
        pass
    return None


def _photo_url(person):
    try:
        if person.photo:
            return person.photo.url
    except Exception:
        pass
    return ''


def _fmt_date(value):
    if not value:
        return '—'
    try:
        return value.strftime('%d/%m/%Y')
    except Exception:
        return str(value)


def build_badge_context(person, kind, school, enrollment=None, design_key='official'):
    """Construit le contexte unique utilisé par HTML / PDF / PNG."""
    kind = 'personnel' if kind in ('teacher', 'staff', 'personnel') else 'eleve'
    school_ctx = school_context(school)
    design = get_badge_design(design_key)

    if kind == 'eleve':
        father, mother = parents_pair(person)
        gender = (getattr(person, 'gender', '') or '').upper()
        child_word = 'Fille de' if gender == 'F' else 'Fils de'
        born_word = 'Née le' if gender == 'F' else 'Né le'
        parent_phone = ''
        try:
            link = person.parents.select_related('parent').first()
            if link and link.parent:
                parent_phone = link.parent.phone or ''
        except Exception:
            pass
        classe = (
            getattr(enrollment.classroom, 'name', str(enrollment.classroom))
            if enrollment else '—'
        )
        if enrollment and getattr(enrollment, 'academic_year_id', None):
            year_label = str(enrollment.academic_year.name)
        else:
            year_label = school_ctx['year_label']
        lines = [
            ('NOM', (person.last_name or '').upper()),
            ('PRÉNOM', person.first_name or ''),
            ('MATRICULE', person.matricule or '—'),
            ('CLASSE', classe),
            (born_word.upper(), _fmt_date(person.date_of_birth)),
            (child_word.upper(), father),
            ('ET DE', mother),
            ('TÉL.', parent_phone or (person.phone or '—')),
        ]
        main_fields = [('CLASSE', classe), ('MATRICULE', person.matricule or '—'),
                       (born_word.upper(), _fmt_date(person.date_of_birth))]
        title = "CARTE SCOLAIRE"
        role_label = 'ÉLÈVE'
    else:
        category = dict(getattr(person, 'CATEGORY_CHOICES', []) or []).get(
            getattr(person, 'category', ''), getattr(person, 'category', '') or '—'
        )
        function = getattr(person, 'function', None) or getattr(person, 'speciality', None) or category
        lines = [
            ('NOM', (person.last_name or '').upper()),
            ('PRÉNOM', person.first_name or ''),
            ('MATRICULE', person.matricule or '—'),
            ('FONCTION', function or '—'),
            ('CATÉGORIE', category or '—'),
            ('SERVICE', getattr(person, 'department', None) or '—'),
            ('TÉL.', getattr(person, 'phone', None) or '—'),
        ]
        main_fields = [
            ('FONCTION', function or '—'),
            ('MATRICULE', person.matricule or '—'),
            ('CATÉGORIE', category or '—'),
        ]
        year_label = school_ctx['year_label']
        title = 'CARTE SCOLAIRE'
        role_label = 'PERSONNEL'

    payload = badge_payload(kind, getattr(person, 'matricule', None) or person.pk)
    try:
        qr_url = reverse('core:qr_image') + '?data=' + quote(payload)
    except Exception:
        qr_url = ''

    today = date.today()
    try:
        valid_until = date(today.year + 1, 8, 31)
    except ValueError:
        valid_until = today

    return {
        'kind': kind,
        'role_label': role_label,
        'title': title,
        'person': person,
        'last_name': person.last_name or '',
        'first_name': person.first_name or '',
        'full_name': f'{person.last_name} {person.first_name}'.strip(),
        'matricule': getattr(person, 'matricule', None) or '—',
        'enrollment': enrollment,
        'lines': lines,
        'main_fields': main_fields,
        'year_label': year_label,
        'place': school_ctx['place'],
        'photo_path': _photo_path(person),
        'photo_url': _photo_url(person),
        'initials': ((person.last_name or '?')[:1] + (person.first_name or '?')[:1]).upper(),
        'qr_payload': payload,
        'qr_url': qr_url,
        'school': school_ctx,
        'director': school_ctx['director'],
        'valid_until': valid_until,
        'valid_until_str': _fmt_date(valid_until),
        'design': design,
        'design_key': design_key,
        'issued_str': _fmt_date(today),
    }
