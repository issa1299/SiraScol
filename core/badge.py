# -*- coding: utf-8 -*-
"""Badges scolaires unifiés : élèves ET personnel, même modèle, même QR.

Toutes les vues (HTML, PNG, PDF, aperçu) consomment le même contexte construit
ici. Les couleurs sont celles proposées dans les paramètres de l'école.
"""
from datetime import date
from urllib.parse import quote

from django.urls import reverse

from .qr import badge_payload, staff_display_code

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


PARTICLES = {'de', 'du', 'des', 'la', 'le', 'et'}


def format_person_name(text):
    """Capitalise chaque mot sauf les particules (de, du, des, la, le, et). Accents préservés."""
    if not text:
        return ''
    words = str(text).strip().split()
    result = []
    for i, word in enumerate(words):
        w_lower = word.lower()
        if i > 0 and w_lower in PARTICLES:
            result.append(w_lower)
        elif "'" in word and len(word) > 2:
            prefix, rest = word.split("'", 1)
            p_low = prefix.lower()
            if i > 0 and p_low in PARTICLES:
                p_res = p_low
            else:
                p_res = prefix[:1].upper() + (prefix[1:].lower() if prefix.isupper() else prefix[1:])
            r_res = rest[:1].upper() + (rest[1:].lower() if rest.isupper() else rest[1:])
            result.append(f"{p_res}'{r_res}")
        else:
            if word.isupper() and len(word) > 1:
                result.append(word[:1].upper() + word[1:].lower())
            else:
                result.append(word[:1].upper() + word[1:])
    return ' '.join(result)


def title_words(text):
    """Alias rétro-compatible utilisant le formatage respectueux des particules."""
    return format_person_name(text)


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
    raw_name = (getattr(school, 'name', None) if school else None) or ''
    import unicodedata
    normalized = ''.join(
        c for c in unicodedata.normalize('NFKD', raw_name.strip().lower())
        if not unicodedata.combining(c)
    )
    # Anciennes valeurs par défaut (éventuellement avec une faute de frappe
    # comme « Mon Écolek ») : on les traite comme absentes.
    name = '' if normalized.startswith('mon ecole') else raw_name
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
    address = (getattr(school, 'address', None) if school else None) or ''
    phone = (getattr(school, 'phone', None) if school else None) or ''
    phone2 = (getattr(school, 'phone2', None) if school else None) or ''
    email = (getattr(school, 'email', None) if school else None) or ''
    website = (getattr(school, 'website', None) if school else None) or ''

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
        'address': address,
        'phone': phone,
        'phone2': phone2,
        'email': email,
        'website': website,
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
        dob_str = _fmt_date(person.date_of_birth) if person.date_of_birth else ''
        pob = (getattr(person, 'place_of_birth', '') or '').strip()
        dob_display = f"{dob_str} à {pob}" if (dob_str and pob) else dob_str

        lines = [
            ('NOM', (person.last_name or '').upper()),
            ('PRÉNOM', person.first_name or ''),
            ('MATRICULE', person.matricule or '—'),
            ('CLASSE', classe),
            (born_word.upper(), dob_display or '—'),
            (child_word.upper(), father),
            ('ET DE', mother),
            ('TÉL.', parent_phone or (person.phone or '—')),
        ]
        main_fields = [
            ('CLASSE', classe),
            ('MATRICULE', person.matricule or '—'),
        ]
        if dob_display:
            main_fields.append((born_word.upper(), dob_display))
        else:
            main_fields.append(('STATUT', 'Élève régulier(e)'))

        emergency_name = father if father != '—' else (mother if mother != '—' else '')
        if parent_phone and emergency_name:
            emergency_contact = f"{emergency_name} · Tél : {parent_phone}"
        elif parent_phone:
            emergency_contact = f"Tél. urgence : {parent_phone}"
        elif emergency_name:
            emergency_contact = emergency_name
        else:
            emergency_contact = ''
        title = "CARTE SCOLAIRE"
        role_label = 'ÉLÈVE'
        service = ''
        function = 'Élève'
    else:
        category = dict(getattr(person, 'CATEGORY_CHOICES', []) or []).get(
            getattr(person, 'category', ''), getattr(person, 'category', '') or '—'
        )
        function = getattr(person, 'function', None) or getattr(person, 'speciality', None) or category
        department = (getattr(person, 'department', None) or '').strip()
        service = department or getattr(person, 'speciality', None)
        if not service:
            if str(category).lower() in ('admin', 'administratif', 'direction'):
                service = 'Administration'
            elif str(category).lower() in ('service', 'technique'):
                service = 'Services Généraux'
            else:
                service = 'Pédagogique'
        lines = [
            ('NOM', (person.last_name or '').upper()),
            ('PRÉNOM', person.first_name or ''),
            ('MATRICULE', person.matricule or '—'),
            ('FONCTION', function or '—'),
            ('SERVICE', service or '—'),
            ('CATÉGORIE', category or '—'),
            ('TÉL.', getattr(person, 'phone', None) or '—'),
        ]
        main_fields = [
            ('FONCTION', function or 'Enseignant'),
            ('SERVICE', service),
            ('MATRICULE', staff_display_code(person)),
        ]
        classe = ''
        emergency_contact = ''
        father = mother = parent_phone = ''
        dob_display = ''
        born_word = 'Né le'
        gender = (getattr(person, 'gender', '') or '').upper()
        year_label = school_ctx['year_label']
        title = 'CARTE DU PERSONNEL'
        role_label = 'PERSONNEL'

    code = (staff_display_code(person) if kind == 'personnel'
            else (getattr(person, 'matricule', None) or person.pk))
    payload = badge_payload(kind, code)
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
        'last_name': title_words(person.last_name),
        'first_name': title_words(person.first_name),
        'full_name': title_words(f'{person.first_name} {person.last_name}'),
        'matricule': (staff_display_code(person) if kind == 'personnel'
                      else (getattr(person, 'matricule', None) or '—')),
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
        'function': function,
        'service': service,
        'classe': classe,
        'dob_display': dob_display,
        'born_word': born_word,
        'gender': gender,
        'emergency_contact': emergency_contact,
        'father': father,
        'mother': mother,
        'parent_phone': parent_phone,
        'phone': getattr(person, 'phone', None) or '—',
        'address': getattr(person, 'address', '') or '',
        'matricule_raw': getattr(person, 'matricule', '') or str(person.pk),
    }
