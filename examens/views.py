# -*- coding: utf-8 -*-
"""Espace Examens — candidats DEF et BAC."""
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom
from core.permissions import role_required
from core.year_context import get_selected_year
from students.models import Student

from .models import Candidate, ExamSession


def _base(request, section, **extra):
    ctx = {'section': section, 'today': date.today(), 'year': get_selected_year(request)}
    ctx.update(extra)
    return ctx


@role_required('directeur', 'secretaire', 'admin')
def exam_dashboard(request):
    year = get_selected_year(request)
    sessions = ExamSession.objects.filter(academic_year=year) if year else ExamSession.objects.all()
    sessions = sessions.select_related('academic_year').order_by('-date')
    candidates = Candidate.objects.filter(session__academic_year=year) if year else Candidate.objects.all()
    stats = {
        'total': candidates.count(),
        'def': candidates.filter(session__type='def').count(),
        'bac': candidates.filter(session__type='bac').count(),
        'validated': candidates.filter(status='valide').count(),
        'admitted': candidates.filter(status='admis').count(),
    }
    classrooms = ClassRoom.objects.filter(academic_year=year) if year else ClassRoom.objects.all()
    return render(request, 'examens/dashboard.html', _base(
        request, 'dashboard', sessions=sessions, stats=stats, classrooms=classrooms,
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_list(request):
    year = get_selected_year(request)
    qs = Candidate.objects.select_related(
        'student', 'session', 'classroom'
    ).order_by('registration_number')
    exam_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    q = (request.GET.get('q') or '').strip()
    session_id = request.GET.get('session', '')
    if year:
        qs = qs.filter(session__academic_year=year)
    if exam_type:
        qs = qs.filter(session__type=exam_type)
    if status:
        qs = qs.filter(status=status)
    if session_id:
        qs = qs.filter(session_id=session_id)
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q)
            | Q(student__matricule__icontains=q) | Q(registration_number__icontains=q)
        )
    sessions = ExamSession.objects.filter(academic_year=year) if year else ExamSession.objects.all()
    return render(request, 'examens/candidate_list.html', _base(
        request, 'candidates', rows=qs[:300], exam_type=exam_type, status=status,
        q=q, session_id=session_id, sessions=sessions,
        statuses=Candidate.STATUS_CHOICES,
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_create(request):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        student_id = request.POST.get('student')
        session_id = request.POST.get('session')
        if not student_id or not session_id:
            messages.error(request, 'Élève et session sont obligatoires.')
            return redirect('examens:candidate_list')
        classroom_id = request.POST.get('classroom') or None
        try:
            fee = Decimal((request.POST.get('exam_fee') or '0').replace(',', '.'))
        except InvalidOperation:
            fee = Decimal('0')
        candidate, created = Candidate.objects.get_or_create(
            student_id=student_id, session_id=session_id,
            defaults={
                'classroom_id': classroom_id,
                'series': request.POST.get('series', ''),
                'exam_fee': fee,
                'notes': request.POST.get('notes', ''),
                'recorded_by': request.user,
            },
        )
        if created:
            messages.success(request, f'Candidat {candidate.registration_number} enregistré.')
        else:
            messages.info(request, 'Cet élève est déjà candidat pour cette session.')
        if is_modal:
            return render(request, 'examens/candidate_done.html', {'candidate': candidate})
        return redirect('examens:candidate_list')
    year = get_selected_year(request)
    sessions = ExamSession.objects.filter(is_open=True)
    if year:
        sessions = sessions.filter(academic_year=year)
    students = Student.objects.filter(status='actif').order_by('last_name', 'first_name')
    classrooms = ClassRoom.objects.filter(academic_year=year) if year else ClassRoom.objects.all()
    template = 'examens/candidate_form_modal.html' if is_modal else 'examens/candidate_form.html'
    return render(request, template, _base(
        request, 'candidates', sessions=sessions, students=students,
        classrooms=classrooms, series=Candidate.SERIES_CHOICES,
        form_action=reverse('examens:candidate_create'),
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == 'POST':
        candidate.status = request.POST.get('status', candidate.status)
        candidate.series = request.POST.get('series', '')
        candidate.fee_paid = request.POST.get('fee_paid') == 'on'
        candidate.notes = request.POST.get('notes', '')
        try:
            candidate.exam_fee = Decimal((request.POST.get('exam_fee') or '0').replace(',', '.'))
        except InvalidOperation:
            pass
        candidate.save()
        messages.success(request, 'Candidat mis à jour.')
        return redirect('examens:candidate_list')
    return render(request, 'examens/candidate_edit.html', _base(
        request, 'candidates', candidate=candidate,
        statuses=Candidate.STATUS_CHOICES, series=Candidate.SERIES_CHOICES,
    ))


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def candidate_delete(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    candidate.delete()
    messages.success(request, 'Candidat retiré.')
    return redirect('examens:candidate_list')


@role_required('directeur', 'secretaire', 'admin')
def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    return render(request, 'examens/candidate_detail.html', _base(
        request, 'candidates', candidate=candidate,
    ))


@role_required('directeur', 'secretaire', 'admin')
def session_create(request):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        ExamSession.objects.update_or_create(
            type=request.POST.get('type'),
            academic_year_id=request.POST.get('academic_year'),
            session=request.POST.get('session', 'normal'),
            defaults={
                'date': request.POST.get('date') or date.today(),
                'center': request.POST.get('center', ''),
            },
        )
        messages.success(request, 'Session d’examen enregistrée.')
        return redirect('examens:dashboard')
    years = AcademicYear.objects.order_by('-is_current', '-start_date')
    types = ExamSession.TYPE_CHOICES
    sessions_choices = ExamSession.SESSION_CHOICES
    template = 'examens/session_form_modal.html' if is_modal else 'examens/session_form.html'
    return render(request, template, _base(
        request, 'sessions', years=years, types=types, sessions=sessions_choices,
        form_action=reverse('examens:session_create'),
    ))


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def bulk_enroll(request):
    classroom_id = request.POST.get('classroom')
    session_id = request.POST.get('session')
    if not classroom_id or not session_id:
        messages.error(request, 'Classe et session obligatoires.')
        return redirect('examens:dashboard')
    students = Student.objects.filter(
        enrollments__classroom_id=classroom_id, enrollments__is_active=True
    )
    created = 0
    with transaction.atomic():
        for student in students:
            _, was_created = Candidate.objects.get_or_create(
                student=student, session_id=session_id,
                defaults={
                    'classroom_id': classroom_id,
                    'recorded_by': request.user,
                },
            )
            created += int(was_created)
    messages.success(request, f'{created} candidat(s) inscrit(s) depuis la classe.')
    return redirect('examens:candidate_list')


@role_required('directeur', 'secretaire', 'admin')
def export_report(request):
    kind = request.GET.get('format', 'excel')
    qs = Candidate.objects.select_related('student', 'session', 'classroom').order_by('registration_number')
    year = get_selected_year(request)
    if year:
        qs = qs.filter(session__academic_year=year)
    if request.GET.get('type'):
        qs = qs.filter(session__type=request.GET['type'])
    headers = ['N° candidat', 'Nom et prénom', 'Matricule', 'Examen', 'Classe', 'Statut', 'Frais payés']
    rows = [[
        c.registration_number, c.student.full_name, c.student.matricule,
        c.session.get_type_display(), c.classroom.name if c.classroom else '—',
        c.get_status_display(), 'Oui' if c.fee_paid else 'Non',
    ] for c in qs]
    if kind == 'pdf':
        from core.list_pdf import build_list_pdf
        return build_list_pdf('Liste des candidats DEF / BAC', '', headers, rows,
                              'candidats_examens.pdf', landscape_mode=True)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Candidats'
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1E40AF')
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="candidats_examens.xlsx"'
    return resp
