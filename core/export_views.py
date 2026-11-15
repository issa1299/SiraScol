"""Exports Excel (CSV compatible Excel) et sauvegarde base."""
import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages

from .permissions import role_required, is_staff_role


def _csv_response(filename, headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    resp = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@role_required('admin', 'directeur', 'secretaire')
def export_students(request):
    from students.models import Student, Enrollment
    from academics.models import AcademicYear
    year = AcademicYear.objects.filter(is_current=True).first()
    rows = []
    for s in Student.objects.filter(status='actif').order_by('last_name'):
        enr = Enrollment.objects.filter(student=s, is_active=True, academic_year=year).select_related('classroom').first() if year else None
        rows.append([
            s.matricule, s.last_name, s.first_name, s.gender,
            s.date_of_birth.isoformat() if s.date_of_birth else '',
            enr.classroom.name if enr else '',
            s.phone if hasattr(s, 'phone') else '',
            s.status,
        ])
    return _csv_response(
        f'eleves_{datetime.now():%Y%m%d}.csv',
        ['Matricule', 'Nom', 'Prénom', 'Sexe', 'Naissance', 'Classe', 'Téléphone', 'Statut'],
        rows,
    )


@role_required('admin', 'directeur', 'secretaire', 'enseignant')
def export_grades(request):
    from grades.models import Grade
    from academics.models import AcademicYear
    year = AcademicYear.objects.filter(is_current=True).first()
    qs = Grade.objects.select_related(
        'student', 'assessment', 'assessment__subject', 'assessment__classroom', 'assessment__period'
    )
    if year:
        qs = qs.filter(assessment__period__academic_year=year)
    rows = []
    for g in qs.order_by('student__last_name')[:5000]:
        rows.append([
            g.student.matricule, g.student.last_name, g.student.first_name,
            g.assessment.classroom.name if g.assessment.classroom_id else '',
            g.assessment.subject.name if g.assessment.subject_id else '',
            g.assessment.title,
            g.assessment.period.name if g.assessment.period_id else '',
            '' if g.is_absent else str(g.score).replace('.', ','),
            'Oui' if g.is_absent else '',
            g.appreciation,
        ])
    return _csv_response(
        f'notes_{datetime.now():%Y%m%d}.csv',
        ['Matricule', 'Nom', 'Prénom', 'Classe', 'Matière', 'Évaluation', 'Période', 'Note', 'Absent', 'Appréciation'],
        rows,
    )


@role_required('admin', 'directeur', 'secretaire')
def export_payments(request):
    from finance.models import Payment
    rows = []
    for p in Payment.objects.select_related('invoice', 'invoice__student', 'invoice__fee_type').order_by('-payment_date')[:5000]:
        inv = p.invoice
        rows.append([
            inv.student.matricule if inv else '',
            inv.student.last_name if inv else '',
            inv.student.first_name if inv else '',
            inv.fee_type.name if inv and inv.fee_type_id else '',
            str(p.amount).replace('.', ','),
            p.payment_date.isoformat() if p.payment_date else '',
            getattr(p, 'method', '') or getattr(p, 'payment_method', ''),
            getattr(p, 'reference', '') or '',
        ])
    return _csv_response(
        f'paiements_{datetime.now():%Y%m%d}.csv',
        ['Matricule', 'Nom', 'Prénom', 'Type frais', 'Montant', 'Date', 'Mode', 'Référence'],
        rows,
    )


@role_required('admin', 'directeur')
def backup_download(request):
    """Télécharge db.sqlite3 + dossier media en ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        db_path = Path(settings.DATABASES['default']['NAME'])
        if db_path.exists():
            zf.write(db_path, arcname='db.sqlite3')
        media = Path(settings.MEDIA_ROOT)
        if media.exists():
            for f in media.rglob('*'):
                if f.is_file():
                    zf.write(f, arcname=str(Path('media') / f.relative_to(media)))
    buf.seek(0)
    filename = f'sauvegarde_gestion_scolaire_{datetime.now():%Y%m%d_%H%M}.zip'
    resp = HttpResponse(buf.read(), content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
