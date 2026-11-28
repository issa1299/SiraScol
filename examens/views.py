# -*- coding: utf-8 -*-
"""Examens nationaux — DEF (9ᵉ) et BAC (Terminale).

Espace distinct des inscriptions scolaires : candidats internes (élèves) ou
externes, dossiers et pièces, import depuis les classes de 9ᵉ / Terminale,
listes, statistiques, résultats et impressions.
"""
from datetime import date
from io import BytesIO

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom
from core.permissions import role_required
from core.year_context import get_selected_year
from students.models import Enrollment, Student

from .forms import CandidateForm, RequiredDocumentForm, SessionForm
from .models import Candidate, CandidateDocument, ExamSession, RequiredDocument


def _list_url(exam_type):
    return reverse('examens:candidats_bac' if exam_type == 'bac' else 'examens:candidats_def')


def _base(request, section, **extra):
    ctx = {
        'section': section,
        'today': date.today(),
        'year': get_selected_year(request),
        'menu': [
            {'key': 'dashboard', 'label': 'Tableau de bord',
             'icon': 'fa-gauge-high', 'url': reverse('examens:dashboard')},
            {'key': 'sessions', 'label': 'Sessions',
             'icon': 'fa-calendar', 'url': reverse('examens:sessions')},
            {'key': 'candidats_def', 'label': 'Candidats DEF (9ᵉ année)',
             'icon': 'fa-user-graduate', 'url': reverse('examens:candidats_def')},
            {'key': 'candidats_bac', 'label': 'Candidats BAC (12ᵉ année)',
             'icon': 'fa-user-tie', 'url': reverse('examens:candidats_bac')},
            {'key': 'inscriptions', 'label': 'Inscriptions',
             'icon': 'fa-file-signature', 'url': reverse('examens:inscriptions')},
            {'key': 'documents', 'label': 'Documents',
             'icon': 'fa-folder-open', 'url': reverse('examens:documents')},
            {'key': 'listes', 'label': 'Listes et statistiques',
             'icon': 'fa-chart-bar', 'url': reverse('examens:lists_stats')},
            {'key': 'transmission', 'label': 'Transmission des listes',
             'icon': 'fa-paper-plane', 'url': reverse('examens:transmission')},
            {'key': 'resultats', 'label': 'Résultats',
             'icon': 'fa-trophy', 'url': reverse('examens:results')},
        ],
    }
    ctx.update(extra)
    return ctx


def _exam_type(section):
    return 'bac' if section == 'candidats_bac' else 'def'


def _candidates_for(request, exam_type):
    year = get_selected_year(request)
    qs = Candidate.objects.filter(session__type=exam_type).select_related(
        'student', 'session', 'classroom'
    )
    if year:
        qs = qs.filter(session__academic_year=year)
    return qs, year


def _search(qs, q):
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q)
            | Q(student__matricule__icontains=q)
            | Q(external_last_name__icontains=q) | Q(external_first_name__icontains=q)
            | Q(external_matricule__icontains=q)
            | Q(registration_number__icontains=q)
            | Q(official_number__icontains=q)
        )
    return qs


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
        'validated': candidates.filter(registration_status='valide').count(),
        'admitted': candidates.filter(status='admis').count(),
    }
    classrooms = ClassRoom.objects.filter(academic_year=year) if year else ClassRoom.objects.all()
    return render(request, 'examens/dashboard.html', _base(
        request, 'dashboard', sessions=sessions, stats=stats, classrooms=classrooms,
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_list(request, exam_type=None):
    """Liste des candidats DEF ou BAC (URL dédiée ou paramètre ``?type=``)."""
    url_name = request.resolver_match.url_name if request.resolver_match else ''
    if url_name == 'candidats_bac':
        section, exam_type = 'candidats_bac', 'bac'
    elif url_name == 'candidats_def':
        section, exam_type = 'candidats_def', 'def'
    else:
        section = request.GET.get('section', 'candidats_def')
        exam_type = request.GET.get('type') or _exam_type(section)
    qs, year = _candidates_for(request, exam_type)
    status = request.GET.get('status', '')
    reg_status = request.GET.get('registration_status', '')
    q = (request.GET.get('q') or '').strip()
    if status:
        qs = qs.filter(status=status)
    if reg_status:
        qs = qs.filter(registration_status=reg_status)
    qs = _search(qs, q)
    return render(request, 'examens/candidate_list.html', _base(
        request, section, rows=qs[:300], exam_type=exam_type, status=status,
        reg_status=reg_status, q=q,
        statuses=Candidate.STATUS_CHOICES,
        reg_statuses=Candidate.REGISTRATION_STATUS_CHOICES,
    ))


@role_required('directeur', 'secretaire', 'admin')
def import_from_class(request):
    """Étape 1 : élèves de 9ᵉ (DEF) ou de Terminale (BAC) de l'année choisie."""
    section = request.GET.get('section', 'candidats_def')
    exam_type = _exam_type(section)
    year = get_selected_year(request)
    sessions = ExamSession.objects.filter(type=exam_type)
    if year:
        sessions = sessions.filter(academic_year=year)
    levels = (Q(level__name__icontains='9') if exam_type == 'def'
              else Q(level__name__icontains='12') | Q(level__name__icontains='Terminale'))
    classrooms = ClassRoom.objects.filter(levels, academic_year=year) if year else ClassRoom.objects.none()
    students = []
    if year:
        ids = Enrollment.objects.filter(
            classroom__in=classrooms, is_active=True
        ).values_list('student_id', flat=True)
        students = list(Student.objects.filter(pk__in=ids).order_by('last_name', 'first_name'))
    else:
        students = []
    existing = {
        c.student_id: c for c in Candidate.objects.filter(
            session__type=exam_type, session__academic_year=year
        ) if c.student_id
    } if year else {}
    for student in students:
        student.exam_candidate = existing.get(student.pk)
    return render(request, 'examens/import_from_class.html', _base(
        request, section, students=students, sessions=sessions,
        existing=existing, exam_type=exam_type, classrooms=classrooms,
    ))


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def import_confirm(request):
    """Étape 2 : inscrire les élèves cochés (transaction atomique)."""
    session = get_object_or_404(ExamSession, pk=request.POST.get('session'))
    student_ids = request.POST.getlist('students')
    created = 0
    with transaction.atomic():
        for student in Student.objects.filter(pk__in=student_ids):
            enrollment = student.current_enrollment()
            _, was_created = Candidate.objects.get_or_create(
                student=student, session=session,
                defaults={
                    'classroom': enrollment.classroom if enrollment else None,
                    'birth_place': student.place_of_birth or '',
                    'school_name': '',
                    'registration_status': 'a_verifier',
                    'exam_center': session.center,
                    'academy': session.academy,
                    'candidate_kind': 'regulier',
                    'series': (enrollment.classroom.serie if enrollment
                               and enrollment.classroom else ''),
                    'recorded_by': request.user,
                },
            )
            created += int(was_created)
    messages.success(request, f'{created} candidat(s) inscrit(s). Statut : À vérifier.')
    return redirect(_list_url(session.type))


@role_required('directeur', 'secretaire', 'admin')
def inscriptions_home(request):
    """Page d'entrée des inscriptions : individuelle, groupée ou Excel."""
    year = get_selected_year(request)
    sessions = ExamSession.objects.filter(is_open=True)
    if year:
        sessions = sessions.filter(academic_year=year)
    return render(request, 'examens/inscriptions.html', _base(
        request, 'inscriptions', sessions=sessions,
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_create(request):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.recorded_by = request.user
            if candidate.student_id and Candidate.objects.filter(
                student_id=candidate.student_id, session=candidate.session
            ).exists():
                messages.info(request, 'Cet élève est déjà candidat pour cette session.')
            else:
                candidate.save()
                messages.success(request, f'Candidat {candidate.registration_number} enregistré.')
                if is_modal:
                    return render(request, 'examens/candidate_done.html', {'candidate': candidate})
                return redirect(_list_url(candidate.session.type))
        else:
            messages.error(request, 'Vérifiez les champs du formulaire.')
        if is_modal:
            return render(request, 'examens/candidate_form_modal.html', _base(
                request, 'inscriptions', form=form,
                form_action=reverse('examens:candidate_create'),
            ))
    else:
        year = get_selected_year(request)
        initial = {'registration_status': 'brouillon'}
        sessions = ExamSession.objects.filter(is_open=True)
        if year:
            sessions = sessions.filter(academic_year=year)
        if sessions.exists():
            initial['session'] = sessions.first().pk
        form = CandidateForm(initial=initial, user=request.user)
        if year:
            form.fields['session'].queryset = sessions
    template = 'examens/candidate_form_modal.html' if is_modal else 'examens/candidate_form.html'
    return render(request, template, _base(
        request, 'inscriptions', form=form,
        form_action=reverse('examens:candidate_create'),
    ))


@role_required('directeur', 'secretaire', 'admin')
def candidate_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, instance=candidate,
                             user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dossier du candidat mis à jour.')
            return redirect(_list_url(candidate.session.type))
        messages.error(request, 'Vérifiez les champs du formulaire.')
    else:
        form = CandidateForm(instance=candidate, user=request.user)
    return render(request, 'examens/candidate_edit.html', _base(
        request, 'inscriptions', candidate=candidate, form=form,
    ))


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def candidate_delete(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    exam_type = candidate.session.type
    candidate.delete()
    messages.success(request, 'Candidat retiré.')
    return redirect(_list_url(exam_type))


@role_required('directeur', 'secretaire', 'admin')
def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    requirements = RequiredDocument.objects.filter(
        session=candidate.session
    ).order_by('order', 'name')
    existing = {d.required_document_id: d for d in candidate.documents.all()}
    documents = [(requirement, existing.get(requirement.pk)) for requirement in requirements]
    return render(request, 'examens/candidate_detail.html', _base(
        request, 'documents', candidate=candidate, documents=documents,
        status_choices=CandidateDocument.STATUS_CHOICES,
    ))


@role_required('directeur', 'secretaire', 'admin')
def documents(request):
    """Suivi des pièces exigées, avec configuration par session."""
    year = get_selected_year(request)
    sessions = ExamSession.objects.filter(academic_year=year) if year else ExamSession.objects.all()
    required = list(RequiredDocument.objects.filter(
        session__in=sessions
    ).select_related('session').order_by('session__date', 'order', 'name'))

    q = (request.GET.get('q') or '').strip()
    qs = _search(Candidate.objects.select_related('student', 'session'), q)
    if year:
        qs = qs.filter(session__academic_year=year)
    qs = qs.order_by('registration_number')

    rows = []
    for candidate in qs[:300]:
        by_requirement = {d.required_document_id: d for d in candidate.documents.all()}
        docs = []
        missing = 0
        for requirement in required:
            if requirement.session_id != candidate.session_id:
                continue
            piece = by_requirement.get(requirement.pk)
            if piece is None or piece.status == 'manquant':
                if requirement.is_required:
                    missing += 1
            docs.append((requirement, piece))
        rows.append({'candidate': candidate, 'docs': docs, 'missing': missing})
    return render(request, 'examens/documents.html', _base(
        request, 'documents', rows=rows, q=q, required=required,
    ))


@role_required('admin', 'directeur')
def required_documents(request):
    """Configuration des pièces exigées pour une session."""
    sessions = ExamSession.objects.select_related('academic_year').order_by('-date')
    session_id = request.GET.get('session') or (sessions.first().pk if sessions else None)
    session = sessions.filter(pk=session_id).first() if session_id else None
    if request.method == 'POST':
        form = RequiredDocumentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pièce exigée ajoutée.')
            return redirect(reverse('examens:required_documents')
                            + f'?session={form.cleaned_data["session"].pk}')
        messages.error(request, 'Vérifiez les champs.')
    else:
        form = RequiredDocumentForm(initial={'session': session} if session else {})
    documents = (RequiredDocument.objects.filter(session=session).order_by('order', 'name')
                 if session else RequiredDocument.objects.none())
    return render(request, 'examens/required_documents.html', _base(
        request, 'documents', sessions=sessions, session=session, form=form,
        documents=documents,
    ))


@role_required('admin', 'directeur')
@require_POST
def required_document_delete(request, pk):
    get_object_or_404(RequiredDocument, pk=pk).delete()
    messages.success(request, 'Pièce exigée retirée.')
    return redirect('examens:required_documents')


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def candidate_document_upload(request, pk, document_id):
    candidate = get_object_or_404(Candidate, pk=pk)
    requirement = get_object_or_404(RequiredDocument, pk=document_id)
    if requirement.session_id != candidate.session_id or not request.FILES.get('file'):
        messages.error(request, 'Dépôt invalide.')
        return redirect('examens:candidate_detail', pk=pk)
    now = timezone.now()
    piece, _ = CandidateDocument.objects.update_or_create(
        candidate=candidate, required_document=requirement,
        defaults={
            'file': request.FILES['file'], 'status': 'recu',
            'deposited_at': now, 'verified_by': None, 'verified_at': None,
        },
    )
    messages.success(request, f'Pièce « {requirement.name} » déposée.')
    return redirect('examens:candidate_detail', pk=pk)


@role_required('admin', 'directeur')
@require_POST
def candidate_document_status(request, pk, doc_pk):
    piece = get_object_or_404(CandidateDocument, pk=doc_pk, candidate_id=pk)
    status = request.POST.get('status')
    if status in dict(CandidateDocument.STATUS_CHOICES):
        piece.status = status
        if status in ('valide', 'rejete', 'a_verifier'):
            piece.verified_by = request.user
            piece.verified_at = timezone.now()
        piece.save()
        messages.success(request, 'Statut de la pièce mis à jour.')
    return redirect('examens:candidate_detail', pk=pk)


@role_required('directeur', 'secretaire', 'admin')
def lists_stats(request):
    year = get_selected_year(request)
    qs = Candidate.objects.filter(session__academic_year=year) if year else Candidate.objects.all()
    by_type = {'DEF': qs.filter(session__type='def').count(), 'BAC': qs.filter(session__type='bac').count()}
    total = qs.count()
    by_status = []
    for value, label in Candidate.REGISTRATION_STATUS_CHOICES:
        n = qs.filter(registration_status=value).count()
        by_status.append((label, n, round(n * 100 / total) if total else 0))
    by_class = []
    classrooms = ClassRoom.objects.filter(academic_year=year) if year else ClassRoom.objects.none()
    for classroom in classrooms:
        n = qs.filter(classroom=classroom).count()
        if n:
            by_class.append((classroom.name, n))
    return render(request, 'examens/lists_stats.html', _base(
        request, 'listes', by_type=by_type, by_status=by_status, by_class=by_class,
        total=total,
    ))


@role_required('directeur', 'secretaire', 'admin')
def results(request):
    year = get_selected_year(request)
    qs = Candidate.objects.filter(session__academic_year=year) if year else Candidate.objects.all()
    qs = qs.select_related('student', 'session')
    if request.method == 'POST':
        candidate = get_object_or_404(Candidate, pk=request.POST.get('candidate'))
        candidate.status = request.POST.get('status', candidate.status)
        candidate.notes = request.POST.get('notes', candidate.notes)
        candidate.save()
        messages.success(request, 'Résultat enregistré.')
        return redirect('examens:results')
    return render(request, 'examens/results.html', _base(
        request, 'resultats', rows=qs[:300], statuses=Candidate.STATUS_CHOICES,
    ))


@role_required('directeur', 'secretaire', 'admin')
def sessions_home(request):
    """Liste des sessions, filtrée par année de travail."""
    year = get_selected_year(request)
    qs = ExamSession.objects.select_related('academic_year')
    if year:
        qs = qs.filter(academic_year=year)
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    if type_filter:
        qs = qs.filter(type=type_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'examens/sessions.html', _base(
        request, 'sessions', sessions=qs, types=ExamSession.TYPE_CHOICES,
        statuses=ExamSession.STATUS_CHOICES, type_filter=type_filter,
        status_filter=status_filter,
    ))


@role_required('directeur', 'secretaire', 'admin')
def session_create(request):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            legacy = ('rattrapage' if 'rattrapage' in data['kind'].lower() else 'normal')
            ExamSession.objects.update_or_create(
                type=data['type'], academic_year=data['academic_year'], kind=data['kind'],
                defaults={
                    'date': data['start_date'] or date.today(),
                    'start_date': data['start_date'], 'end_date': data['end_date'],
                    'academy': data['academy'], 'center': data['center'],
                    'status': data['status'], 'session': legacy,
                },
            )
            messages.success(request, 'Session d’examen enregistrée.')
            return redirect('examens:sessions')
        messages.error(request, 'Vérifiez les champs de la session.')
    else:
        year = get_selected_year(request)
        form = SessionForm(initial={
            'type': 'def', 'kind': 'normale', 'status': 'preparation',
            'start_date': date.today(), 'end_date': date.today(),
            'academic_year': year,
        })
    template = 'examens/session_form_modal.html' if is_modal else 'examens/session_form.html'
    return render(request, template, _base(
        request, 'sessions', form=form,
        form_action=reverse('examens:session_create'),
    ))


@role_required('directeur', 'secretaire', 'admin')
def session_edit(request, pk):
    session = get_object_or_404(ExamSession, pk=pk)
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            data = form.cleaned_data
            form.save(commit=False)
            session.date = data['start_date'] or session.date
            session.session = ('rattrapage' if 'rattrapage' in data['kind'].lower()
                               else 'normal')
            session.save()
            messages.success(request, 'Session mise à jour.')
            return redirect('examens:sessions')
        messages.error(request, 'Vérifiez les champs de la session.')
    else:
        form = SessionForm(instance=session)
    return render(request, 'examens/session_form.html', _base(
        request, 'sessions', form=form, is_edit=True, form_action=request.path,
    ))


@role_required('admin', 'directeur')
@require_POST
def session_status(request, pk):
    """Ouvre ou clôture définitivement une session (directeur uniquement)."""
    session = get_object_or_404(ExamSession, pk=pk)
    status = request.POST.get('status')
    if status in dict(ExamSession.STATUS_CHOICES):
        session.status = status
        session.save()
        messages.success(request, f'Session passée en « {session.get_status_display()} ».')
    return redirect('examens:sessions')


@role_required('directeur', 'secretaire', 'admin')
def transmission_home(request):
    """Onglet Transmission des listes (implémenté en phase 5)."""
    return render(request, 'examens/transmission.html', _base(request, 'transmission'))


@role_required('directeur', 'secretaire', 'admin')
@require_POST
def bulk_enroll(request):
    classroom_id = request.POST.get('classroom')
    session = get_object_or_404(ExamSession, pk=request.POST.get('session'))
    if not classroom_id:
        messages.error(request, 'Classe obligatoire.')
        return redirect('examens:dashboard')
    students = Student.objects.filter(
        enrollments__classroom_id=classroom_id, enrollments__is_active=True
    )
    source_serie = (ClassRoom.objects.filter(pk=classroom_id)
                    .values_list('serie', flat=True).first() or '')
    created = 0
    with transaction.atomic():
        for student in students:
            _, was_created = Candidate.objects.get_or_create(
                student=student, session=session,
                defaults={
                    'classroom_id': int(classroom_id), 'recorded_by': request.user,
                    'registration_status': 'a_verifier', 'exam_center': session.center,
                    'academy': session.academy, 'candidate_kind': 'regulier',
                    'series': source_serie,
                },
            )
            created += int(was_created)
    messages.success(request, f'{created} candidat(s) inscrit(s) depuis la classe.')
    return redirect(_list_url(session.type))


@role_required('directeur', 'secretaire', 'admin')
def excel_import(request):
    """Import groupé depuis un fichier Excel (matricule, nom, prénom, …)."""
    if request.method == 'POST':
        uploaded = request.FILES.get('file')
        session = get_object_or_404(ExamSession, pk=request.POST.get('session'))
        if not uploaded:
            messages.error(request, 'Fichier obligatoire.')
            return redirect('examens:excel_import')
        from openpyxl import load_workbook
        try:
            wb = load_workbook(uploaded, read_only=True, data_only=True)
            rows = list(wb.active.iter_rows(values_only=True))
        except Exception as exc:
            messages.error(request, f'Lecture impossible : {exc}')
            return redirect('examens:excel_import')
        created = errors = 0
        with transaction.atomic():
            for row in rows[1:]:
                if not row or not any(v for v in row):
                    continue
                values = ['' if v is None else str(v).strip() for v in row]
                values += [''] * (8 - len(values))
                matricule, last, first = values[0], values[1], values[2]
                student = Student.objects.filter(matricule=matricule).first() if matricule else None
                defaults = {
                    'registration_status': 'a_verifier',
                    'recorded_by': request.user,
                    'exam_center': session.center,
                    'external_matricule': '' if student else matricule,
                    'external_last_name': '' if student else last,
                    'external_first_name': '' if student else first,
                    'is_external': not student,
                    'candidate_kind': 'libre' if not student else 'regulier',
                    'academy': session.academy,
                    'parent_name': values[6], 'parent_phone': values[7],
                    'birth_place': values[4], 'school_name': values[5],
                }
                if not student and not (last and first):
                    errors += 1
                    continue
                if student:
                    lookup = {'student': student, 'session': session}
                elif matricule:
                    lookup = {'student': None, 'session': session, 'external_matricule': matricule}
                else:
                    lookup = {'student': None, 'session': session,
                              'external_last_name': last, 'external_first_name': first}
                _, was_created = Candidate.objects.get_or_create(defaults=defaults, **lookup)
                created += int(was_created)
        messages.success(request, f'{created} candidat(s) importé(s), {errors} ligne(s) ignorée(s).')
        return redirect(_list_url(session.type))
    sessions = ExamSession.objects.filter(is_open=True)
    return render(request, 'examens/excel_import.html', _base(
        request, 'inscriptions', sessions=sessions,
    ))


@role_required('directeur', 'secretaire', 'admin')
def export_report(request):
    kind = request.GET.get('format', 'excel')
    exam_type = request.GET.get('type', '')
    year = get_selected_year(request)
    qs = Candidate.objects.select_related('student', 'session', 'classroom').order_by('registration_number')
    if year:
        qs = qs.filter(session__academic_year=year)
    if exam_type:
        qs = qs.filter(session__type=exam_type)
    headers = ['N° candidat', 'Nom et prénom', 'Sexe', 'Naissance', 'Matricule', 'Classe',
               'Examen', 'Statut inscription', 'Frais payés']
    rows = []
    for c in qs:
        birth = c.candidate_birth_date
        rows.append([
            c.registration_number, c.candidate_name, c.candidate_gender_display,
            birth.strftime('%d/%m/%Y') if birth else '—',
            c.candidate_matricule or '—', c.classroom.name if c.classroom else '—',
            c.session.get_type_display(), c.get_registration_status_display(),
            'Oui' if c.fee_paid else 'Non',
        ])
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


@role_required('directeur', 'secretaire', 'admin')
def candidate_fiche_pdf(request, pk):
    """Fiche individuelle de candidature (PDF A4, reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    candidate = get_object_or_404(Candidate, pk=pk)
    birth = candidate.candidate_birth_date
    lines = [
        f'Numero de candidat : {candidate.registration_number}',
        f'Nom et prenom : {candidate.candidate_name}',
        f'Sexe : {candidate.candidate_gender_display}',
        f'Ne(e) le : {birth.strftime("%d/%m/%Y") if birth else "—"}',
        f'Lieu de naissance : {candidate.birth_place or "—"}',
        f'Matricule : {candidate.candidate_matricule or "—"}',
        f'Classe : {candidate.classroom.name if candidate.classroom else "—"}',
        f'Etablissement : {candidate.school_name or "—"}',
        f'Parent / tuteur : {candidate.parent_name or "—"}',
        f'Telephone parent : {candidate.parent_phone or "—"}',
        f'Centre d examen : {candidate.exam_center or candidate.session.center or "—"}',
        f'Serie / specialite : {(candidate.get_series_display() + " " + candidate.speciality).strip()}',
        f'Classe de Terminale : {candidate.terminale_class or "—"}',
        f'Langue vivante : {candidate.get_living_language_display() or "—"}',
        f'Matieres et options : {candidate.subjects_options or "—"}',
        f'Statut d inscription : {candidate.get_registration_status_display()}',
    ]
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawCentredString(width / 2, height - 60, 'FICHE DE CANDIDATURE')
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawCentredString(
        width / 2, height - 82,
        f'{candidate.session.get_type_display()} — {candidate.session.academic_year.name}',
    )
    y = height - 120
    pdf.setFont('Helvetica', 11)
    for line in lines:
        pdf.drawString(70, y, line[:95])
        y -= 22
    pdf.showPage()
    pdf.save()
    resp = HttpResponse(buf.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="fiche_{candidate.registration_number}.pdf"'
    return resp
