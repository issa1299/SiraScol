# -*- coding: utf-8 -*-
"""Import en masse d'élèves (CSV ou XLSX) avec création des comptes et inscriptions."""

import csv
import io
import re
import unicodedata
from datetime import date, datetime

from django.db import transaction

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
def _import_one(row, year, classroom, create_parents, create_invoices):
    """Importe une ligne dans une transaction ; lève ValueError si invalide.

    La classe est imposée par l'import (une classe à la fois) : la colonne
    « Classe » du fichier, si elle existe, est ignorée.
    """
    last_name = str(row.get('last_name') or '').strip()
    first_name = str(row.get('first_name') or '').strip()
    if not last_name or not first_name:
        raise ValueError('Nom et prénom obligatoires')

    gender = _parse_gender(row.get('gender') or 'M')
    dob = _parse_date(row.get('date_of_birth'))
    if not dob:
        raise ValueError('Date de naissance obligatoire')
    enrollment_date = _parse_date(row.get('enrollment_date')) or date.today()

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


def import_rows(rows, classroom, create_parents=True, create_invoices=True):
    """Importe les lignes D'UNE SEULE CLASSE et retourne un rapport détaillé."""
    if classroom is None:
        raise ValueError("Aucune classe sélectionnée.")
    year = classroom.academic_year

    report = {
        'year': year, 'classroom': classroom, 'total': len(rows),
        'created': 0, 'exists': 0, 'errors': [], 'credentials': [],
    }
    for row in rows:
        line = row.get('_line', '?')
        try:
            result = _import_one(
                row, year, classroom, create_parents, create_invoices
            )
            if result['created']:
                report['created'] += 1
            else:
                report['exists'] += 1
            report['credentials'].extend(result['credentials'])
        except Exception as exc:
            report['errors'].append({'line': line, 'message': str(exc)})
    return report


SAMPLE_HEADER = [
    'Nom', 'Prénom', 'Sexe', 'Date de naissance', "Date d'inscription",
    'Téléphone', 'Lieu de naissance', 'Adresse',
    'Nom du parent', 'Téléphone parent', 'Relation',
]


def sample_csv():
    """Modèle CSV d'une classe (séparateur ';', BOM UTF-8 pour Excel).

    La classe et l'année sont choisies dans le formulaire, pas dans le fichier.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=';')
    writer.writerow(SAMPLE_HEADER)
    writer.writerow([
        'Bah', 'Ibrahim', 'M', '2010-05-12', '2026-09-01',
        '0700000000', 'Abidjan', '',
        'Moussa Bah', '0700000001', 'Père',
    ])
    return '\ufeff' + buf.getvalue()


# ── Validation / aperçu (sans aucune écriture en base) ────────────────────────
def validate_rows(rows, classroom, create_parents=True):
    """Analyse les lignes et retourne un aperçu, SANS rien créer en base.

    Chaque entrée : {line, data, status, message, display_name}.
    status ∈ {'ok', 'existing', 'duplicate', 'error'}.
      - ok        : nouvel élève, importable ;
      - existing  : élève déjà en base (matricule conservé), sera réinscrit ;
      - duplicate : doublon avec une ligne précédente du fichier, ignoré ;
      - error     : données invalides, ignoré.
    Les dates sont sérialisées en ISO pour pouvoir être stockées en session.
    """
    seen = {}
    out = []
    for row in rows:
        line = row.get('_line', '?')
        data = {
            '_line': line,
            'last_name': str(row.get('last_name') or '').strip(),
            'first_name': str(row.get('first_name') or '').strip(),
            'gender': '',
            'date_of_birth': '',
            'enrollment_date': '',
            'place_of_birth': str(row.get('place_of_birth') or '').strip(),
            'address': str(row.get('address') or '').strip(),
            'phone': str(row.get('phone') or '').strip(),
            'email': str(row.get('email') or '').strip(),
            'parent_name': str(row.get('parent_name') or '').strip(),
            'parent_phone': str(row.get('parent_phone') or '').strip(),
            'relation': str(row.get('relation') or '').strip(),
        }
        problems = []
        dob = None

        if not data['last_name'] or not data['first_name']:
            problems.append('Nom et prénom obligatoires')

        try:
            data['gender'] = _parse_gender(row.get('gender') or 'M')
        except ValueError as exc:
            problems.append(str(exc))

        try:
            dob = _parse_date(row.get('date_of_birth'))
            if not dob:
                raise ValueError('Date de naissance obligatoire')
            data['date_of_birth'] = dob.isoformat()
        except ValueError as exc:
            problems.append(str(exc))
            dob = None

        try:
            enr = _parse_date(row.get('enrollment_date')) or date.today()
            data['enrollment_date'] = enr.isoformat()
        except ValueError as exc:
            problems.append(str(exc))

        status = 'error' if problems else 'ok'
        message = '; '.join(problems) if problems else 'Prêt à importer'

        if status == 'ok':
            key = (
                data['last_name'].lower(), data['first_name'].lower(),
                data['date_of_birth'],
            )
            if key in seen:
                status = 'duplicate'
                message = f'Doublon dans le fichier (même élève qu’en ligne {seen[key]})'
            else:
                seen[key] = line
                existing = Student.objects.filter(
                    last_name__iexact=data['last_name'],
                    first_name__iexact=data['first_name'],
                    date_of_birth=dob,
                ).first()
                if existing:
                    status = 'existing'
                    message = f'Déjà enregistré — matricule {existing.matricule}'

        out.append({
            'line': line,
            'data': data,
            'status': status,
            'message': message,
            'display_name': (data['last_name'] + ' ' + data['first_name']).strip() or '—',
        })

    return {
        'rows': out,
        'classroom': classroom,
        'total': len(out),
        'nb_ok': sum(1 for r in out if r['status'] == 'ok'),
        'nb_existing': sum(1 for r in out if r['status'] == 'existing'),
        'nb_duplicate': sum(1 for r in out if r['status'] == 'duplicate'),
        'nb_error': sum(1 for r in out if r['status'] == 'error'),
        'importable': sum(1 for r in out if r['status'] in ('ok', 'existing')),
    }


def import_from_preview(preview_rows, classroom, create_parents=True, create_invoices=True):
    """Importe les lignes validées, dans UNE transaction globale.

    Les erreurs de validation (doublons, données invalides) sont ajoutées au
    rapport pour alimenter le rapport d'erreurs téléchargeable.
    """
    report = {
        'year': classroom.academic_year,
        'classroom': classroom,
        'total': len(preview_rows),
        'created': 0, 'exists': 0, 'errors': [], 'credentials': [],
    }
    for entry in preview_rows:
        if entry.get('status') in ('error', 'duplicate'):
            report['errors'].append({
                'line': entry.get('line'), 'message': entry.get('message', ''),
            })

    with transaction.atomic():
        for entry in preview_rows:
            if entry.get('status') not in ('ok', 'existing'):
                continue
            try:
                result = _import_one(
                    entry['data'], classroom.academic_year, classroom,
                    create_parents, create_invoices,
                )
                if result['created']:
                    report['created'] += 1
                else:
                    report['exists'] += 1
                report['credentials'].extend(result['credentials'])
            except Exception as exc:
                report['errors'].append({
                    'line': entry.get('line'), 'message': str(exc),
                })
    return report


# ── Modèle Excel et rapport d'erreurs ────────────────────────────────────────
SAMPLE_EXAMPLE = [
    'Bah', 'Ibrahim', 'M', '2010-05-12', '2026-09-01',
    '0700000000', 'Abidjan', '', 'Moussa Bah', '0700000001', 'Père',
]

_TEMPLATE_NOTES = [
    ['MODELE D\'IMPORT DES ELEVES — SiraScol'],
    [],
    ['1. Choisissez d\'abord l\'année et la classe dans l\'application.'],
    ['2. Remplissez une ligne par élève de CETTE classe (1 import = 1 classe).'],
    ['3. Le matricule est généré automatiquement (ex. 2026-0001).'],
    ['4. Sexe : M ou F. Dates : AAAA-MM-JJ ou JJ/MM/AAAA.'],
    ['5. Nom du parent : « Prénom Nom ». Relation : Père / Mère / Tuteur.'],
    ['6. La classe et l\'année NE SONT PAS dans le fichier : elles viennent du formulaire.'],
    ['7. Après le dépôt, un aperçu est affiché avant confirmation définitive.'],
]


def sample_xlsx():
    """Retourne les octets d'un classeur Excel modèle (file 'Élèves' + 'Consignes')."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Élèves'
    ws.append(SAMPLE_HEADER)
    ws.append(SAMPLE_EXAMPLE)
    header_fill = PatternFill('solid', fgColor='2563EB')
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 30
    widths = [14, 14, 8, 18, 18, 15, 18, 24, 20, 16, 12]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = 'A2'

    notes = wb.create_sheet('Consignes')
    for row in _TEMPLATE_NOTES:
        notes.append(row)
    notes['A1'].font = Font(bold=True, size=13, color='2563EB')
    notes.column_dimensions['A'].width = 95

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def error_report_xlsx(report_data):
    """Retourne les octets d'un classeur listant les lignes en erreur."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = 'Erreurs'
    ws.append(['Classe', 'Année', 'Créés', 'Existants', 'Erreurs'])
    ws.append([
        report_data.get('classroom', ''), report_data.get('year', ''),
        report_data.get('created', 0), report_data.get('exists', 0),
        len(report_data.get('errors', [])),
    ])
    ws.append([])
    ws.append(['Ligne', 'Message'])
    for cell in ws[4]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='DC2626')
    for err in report_data.get('errors', []):
        ws.append([err.get('line', ''), err.get('message', '')])
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 85
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
