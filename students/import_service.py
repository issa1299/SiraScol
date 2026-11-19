# -*- coding: utf-8 -*-
"""Import en masse d'élèves (CSV ou XLSX) avec création des comptes et inscriptions."""

import csv
import io
import re
import unicodedata
from datetime import date, datetime

from django.db import transaction

from academics.models import AcademicYear, ClassRoom
from core.account_sync import ensure_user_for_parent, ensure_user_for_student

from .models import Enrollment, Parent, ParentStudent, Student


# ── Noms de colonnes acceptés ────────────────────────────────────────────────
ALIASES = {
    'nom': 'last_name', 'name': 'last_name', 'lastname': 'last_name',
    'last_name': 'last_name', 'nom_eleve': 'last_name', 'noms': 'last_name',
    'prenom': 'first_name', 'firstname': 'first_name', 'first_name': 'first_name',
    'prenoms': 'first_name',
    'sexe': 'gender', 'gender': 'gender', 'genre': 'gender',
    'date_de_naissance': 'date_of_birth', 'date_naissance': 'date_of_birth',
    'naissance': 'date_of_birth', 'date_of_birth': 'date_of_birth', 'dob': 'date_of_birth',
    'date_inscription': 'enrollment_date', 'date_d_inscription': 'enrollment_date',
    'inscription': 'enrollment_date', 'enrollment_date': 'enrollment_date',
    'classe': 'classroom', 'class': 'classroom', 'classroom': 'classroom',
    'annee': 'academic_year', 'annee_scolaire': 'academic_year',
    'academic_year': 'academic_year', 'year': 'academic_year',
    'telephone': 'phone', 'tel': 'phone', 'phone': 'phone',
    'lieu_de_naissance': 'place_of_birth', 'lieu_naissance': 'place_of_birth',
    'place_of_birth': 'place_of_birth',
    'adresse': 'address', 'address': 'address',
    'email': 'email', 'mail': 'email',
    'matricule': 'matricule',
    'nom_du_parent': 'parent_name', 'nom_parent': 'parent_name',
    'parent': 'parent_name', 'tuteur': 'parent_name', 'guardian': 'parent_name',
    'telephone_parent': 'parent_phone', 'tel_parent': 'parent_phone',
    'parent_phone': 'parent_phone', 'contact': 'parent_phone',
    'relation': 'relation', 'lien': 'relation', 'qualite': 'relation',
}


def _norm(header):
    s = unicodedata.normalize('NFKD', str(header or '')).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s.strip().lower()).strip('_')
    return s


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date invalide : « {s} » (utilisez AAAA-MM-JJ ou JJ/MM/AAAA)")


def _parse_gender(value):
    s = _norm(value)
    if s in ('m', 'masculin', 'male', 'garcon', '1'):
        return 'M'
    if s in ('f', 'feminin', 'female', 'fille', '2'):
        return 'F'
    raise ValueError(f"Sexe invalide : « {value} » (M ou F)")


def _parse_relation(value):
    s = _norm(value)
    mapping = {
        'pere': 'pere', 'father': 'pere', 'pap': 'pere',
        'mere': 'mere', 'mother': 'mere', 'maman': 'mere',
        'tuteur': 'tuteur', 'gardien': 'tuteur', 'guardian': 'tuteur',
        'autre': 'autre', 'other': 'autre',
    }
    return mapping.get(s, 'autre')


def parse_file(file_obj, filename=''):
    """Retourne une liste de lignes dict {champs canoniques, _line}."""
    name = str(filename or getattr(file_obj, 'name', '') or '').lower()
    raw = file_obj.read() if hasattr(file_obj, 'read') else file_obj
    if isinstance(raw, str):
        raw = raw.encode('utf-8')

    rows = []
    if name.endswith(('.xlsx', '.xlsm')):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ValueError("Le module openpyxl est requis pour les fichiers Excel.")
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active
        data = list(ws.iter_rows(values_only=True))
        wb.close()
        if not data:
            return rows
        headers = [_norm(h) for h in data[0]]
        values = data[1:]
    else:
        text = raw.decode('utf-8-sig', errors='replace')
        if '\ufffd' in text:
            text = raw.decode('cp1252', errors='replace')
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=';,\t|')
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ';' if ';' in sample else ','
        reader = csv.reader(io.StringIO(text), dialect)
        data = list(reader)
        if not data:
            return rows
        headers = [_norm(h) for h in data[0]]
        values = data[1:]

    for i, values_row in enumerate(values, start=2):
        if not any(str(v or '').strip() for v in values_row):
            continue
        row = {'_line': i}
        for idx, h in enumerate(headers):
            key = ALIASES.get(h, h)
            row[key] = values_row[idx] if idx < len(values_row) else ''
        rows.append(row)
    return rows


def _split_parent(name):
    parts = str(name or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


@transaction.atomic
def _import_one(row, year, default_classroom, create_parents, create_invoices):
    """Importe une ligne dans une transaction ; lève ValueError si invalide."""
    last_name = str(row.get('last_name') or '').strip()
    first_name = str(row.get('first_name') or '').strip()
    if not last_name or not first_name:
        raise ValueError('Nom et prénom obligatoires')

    gender = _parse_gender(row.get('gender') or 'M')
    dob = _parse_date(row.get('date_of_birth'))
    if not dob:
        raise ValueError('Date de naissance obligatoire')
    enrollment_date = _parse_date(row.get('enrollment_date')) or date.today()

    class_name = str(row.get('classroom') or '').strip() or default_classroom
    if not class_name:
        raise ValueError('Classe obligatoire (colonne « Classe » ou option --class)')
    classroom = ClassRoom.objects.filter(
        academic_year=year, name__iexact=class_name
    ).select_related('level').first()
    if not classroom:
        raise ValueError(f"Classe « {class_name} » introuvable pour {year.name}")

    # Évite les doublons : même nom + prénom + date de naissance
    student = Student.objects.filter(
        last_name__iexact=last_name,
        first_name__iexact=first_name,
        date_of_birth=dob,
    ).first()
    created_student = False
    if not student:
        student = Student(
            last_name=last_name,
            first_name=first_name,
            gender=gender,
            date_of_birth=dob,
            enrollment_date=enrollment_date,
            place_of_birth=str(row.get('place_of_birth') or '').strip(),
            address=str(row.get('address') or '').strip(),
            phone=str(row.get('phone') or '').strip(),
            email=str(row.get('email') or '').strip(),
        )
        student.save()  # génère le matricule et déclenche la création du compte
        created_student = True

    # Sécurité : le signal de création avale les erreurs, on rappelle explicitement.
    user, account_created, raw_password = ensure_user_for_student(student)
    credentials = []
    if account_created and raw_password:
        credentials.append({
            'type': 'Élève', 'name': student.full_name,
            'username': user.username, 'password': raw_password,
        })
    elif student.matricule and user:
        # mot de passe initial = matricule (voir core.account_sync)
        if created_student:
            credentials.append({
                'type': 'Élève', 'name': student.full_name,
                'username': user.username, 'password': student.matricule,
            })

    enrollment, enr_created = Enrollment.objects.get_or_create(
        student=student,
        academic_year=year,
        defaults={'classroom': classroom, 'enrollment_date': enrollment_date},
    )
    if not enr_created and enrollment.classroom_id != classroom.pk:
        enrollment.classroom = classroom
        enrollment.save(update_fields=['classroom'])

    if create_invoices and enr_created:
        try:
            from students.views import _create_invoices_for_enrollment
            _create_invoices_for_enrollment(student, classroom, year, enrollment_date)
        except Exception:
            pass

    if create_parents and row.get('parent_name') and row.get('parent_phone'):
        p_first, p_last = _split_parent(row.get('parent_name'))
        p_phone = str(row.get('parent_phone') or '').strip()
        parent = Parent.objects.filter(
            phone=p_phone, first_name__iexact=p_first, last_name__iexact=p_last
        ).first()
        if not parent:
            parent = Parent(
                first_name=p_first or 'Parent',
                last_name=p_last or student.last_name,
                phone=p_phone,
                email=str(row.get('email') or '').strip(),
            )
            parent.save()
        pu, p_created, p_pwd = ensure_user_for_parent(parent)
        if p_created and pu:
            credentials.append({
                'type': 'Parent', 'name': parent.first_name + ' ' + parent.last_name,
                'username': pu.username, 'password': p_pwd or p_phone,
            })
        ParentStudent.objects.get_or_create(
            parent=parent,
            student=student,
            defaults={
                'relation': _parse_relation(row.get('relation')),
                'is_primary': True,
            },
        )

    return {
        'student': student,
        'created': created_student,
        'classroom': classroom,
        'credentials': credentials,
        'enrollment_created': enr_created,
    }


def import_rows(rows, year=None, default_classroom='', create_parents=True,
                create_invoices=True):
    """Importe les lignes et retourne un rapport détaillé."""
    if year is None:
        year = AcademicYear.objects.filter(is_current=True).first() or \
            AcademicYear.objects.order_by('-start_date', '-id').first()
    if year is None:
        raise ValueError("Aucune année scolaire configurée.")

    report = {
        'year': year, 'total': len(rows), 'created': 0, 'exists': 0,
        'errors': [], 'credentials': [], 'classrooms': set(),
    }
    for row in rows:
        line = row.get('_line', '?')
        try:
            result = _import_one(
                row, year, default_classroom, create_parents, create_invoices
            )
            if result['created']:
                report['created'] += 1
            else:
                report['exists'] += 1
            report['credentials'].extend(result['credentials'])
            report['classrooms'].add(result['classroom'].name)
        except Exception as exc:
            report['errors'].append({'line': line, 'message': str(exc)})
    return report


SAMPLE_HEADER = [
    'Nom', 'Prénom', 'Sexe', 'Date de naissance', "Date d'inscription",
    'Classe', 'Année scolaire', 'Téléphone', 'Lieu de naissance',
    'Adresse', 'Nom du parent', 'Téléphone parent', 'Relation',
]


def sample_csv():
    """Modèle CSV prêt à remplir (séparateur ';', BOM UTF-8 pour Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=';')
    writer.writerow(SAMPLE_HEADER)
    writer.writerow([
        'Bah', 'Ibrahim', 'M', '2010-05-12', '2026-09-01',
        '1ère A', '2026-2027', '0700000000', 'Abidjan',
        '', 'Moussa Bah', '0700000001', 'Père',
    ])
    return '\ufeff' + buf.getvalue()
