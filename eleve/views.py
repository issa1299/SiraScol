# -*- coding: utf-8 -*-
"""Espace Élève — portail dédié, en lecture seule sur les données scolaires."""

from datetime import date

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import AcademicYear
from attendance.models import Absence
from communication.models import Announcement, Message
from core.access import filter_classrooms_for_user
from core.permissions import (
    get_linked_student, get_linked_teacher, get_role,
    get_teacher_classrooms, role_required,
)
from core.year_context import get_selected_year
from grades.bulletin_views import _build_bulletin_context, _normalize, _q2
from grades.models import Grade, Period
from students.models import Enrollment, ParentStudent
from timetable.views import DAYS, _color_for, _is_break_slot, ensure_default_slots
from timetable.models import TimeSlot, TimetableEntry

from .forms import HomeworkForm
from .models import Homework, HomeworkCompletion


def _base_context(request):
    """Élève lié, année affichée et inscription courante."""
    student = get_linked_student(request.user)
    year = get_selected_year(request) or AcademicYear.objects.filter(is_current=True).first()
    enrollment = None
    if student:
        if year:
            enrollment = (
                student.enrollments
                .filter(academic_year=year, is_active=True)
                .select_related('classroom__level__cycle', 'academic_year')
                .first()
            )
        if not enrollment:
            enrollment = student.current_enrollment()
    return student, year, enrollment


def _periods_for(request, year, is_primary):
    if not year:
        return Period.objects.none()
    ptype = 'mois' if is_primary else 'trimestre'
    qs = Period.objects.filter(academic_year=year, period_type=ptype).order_by('order')
    if not qs.exists():
        qs = Period.objects.filter(academic_year=year).order_by('order')
    return qs


def _student_notifications(request, student, enrollment):
    """Annonces ciblées sur l'élève + messages non lus."""
    announcements = Announcement.objects.none()
    if student:
        target = Q(target='all') | Q(target='students')
        if enrollment:
            target |= Q(target='class', classroom=enrollment.classroom)
            target |= Q(target='level', level=enrollment.classroom.level)
        announcements = Announcement.objects.filter(
            target, is_published=True
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        ).select_related('classroom', 'level').order_by('-published_at')[:6]
    unread = 0
    if request.user.is_authenticated:
        try:
            unread = Message.objects.filter(recipient=request.user, is_read=False).count()
        except Exception:
            unread = 0
    return announcements, unread


@role_required('eleve')
def dashboard(request):
    student, year, enrollment = _base_context(request)
    bulletin = None
    if student:
        try:
            bulletin = _build_bulletin_context(student, None, year)
        except Exception:
            bulletin = None

    announcements, unread_messages = _student_notifications(request, student, enrollment)

    homeworks = Homework.objects.none()
    done_ids = set()
    if enrollment:
        homeworks = (
            Homework.objects
            .filter(is_published=True, classroom=enrollment.classroom, due_date__gte=date.today())
            .select_related('subject', 'teacher')
            .order_by('due_date')[:5]
        )
        done_ids = set(
            HomeworkCompletion.objects.filter(
                student=student, homework__in=homeworks
            ).values_list('homework_id', flat=True)
        )

    absences = Absence.objects.none()
    if student:
        absences = Absence.objects.filter(student=student)

    return render(request, 'eleve/dashboard.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': year,
        'school': bulletin.get('school') if bulletin else None,
        'general_avg': bulletin.get('general_avg') if bulletin else None,
        'rank': bulletin.get('rank') if bulletin else None,
        'rank_total': bulletin.get('rank_total') if bulletin else None,
        'is_primary': bulletin.get('is_primary') if bulletin else False,
        'subject_results': bulletin.get('subject_results') if bulletin else [],
        'announcements': announcements,
        'unread_messages': unread_messages,
        'homeworks': homeworks,
        'done_ids': done_ids,
        'nb_absences': absences.filter(type='absence').count(),
        'nb_retards': absences.filter(type='retard').count(),
        'nb_unjustified': absences.filter(status__in=['non_justifiee', 'en_attente']).count(),
        'section': 'accueil',
    })


@role_required('eleve')
def notes(request):
    student, year, enrollment = _base_context(request)
    is_primary = False
    if student:
        from grades.bulletin_views import _is_primary
        is_primary = _is_primary(student, year)
    periods = _periods_for(request, year, is_primary)

    period_id = request.GET.get('period', '')
    period = None
    if period_id:
        period = get_object_or_404(Period, pk=period_id)
        if year and period.academic_year_id != year.pk:
            period = None
            period_id = ''

    bulletin = None
    if student:
        bulletin = _build_bulletin_context(student, period, year)

    details = []
    if student:
        gqs = Grade.objects.filter(student=student).select_related(
            'assessment__subject', 'assessment__assessment_type',
            'assessment__period', 'assessment__classroom',
        ).order_by('-assessment__date', '-id')
        if period:
            gqs = gqs.filter(assessment__period=period)
        elif year:
            gqs = gqs.filter(assessment__period__academic_year=year)
        out_of = 10 if is_primary else 20
        for g in gqs:
            a = g.assessment
            code = (a.assessment_type.code if a.assessment_type else '') or ''
            details.append({
                'grade': g,
                'date': a.date,
                'subject': a.subject,
                'title': a.title,
                'period': a.period,
                'type': code or (a.assessment_type.name if a.assessment_type else 'Évaluation'),
                'type_label': a.assessment_type.name if a.assessment_type else 'Évaluation',
                'score': g.score,
                'max_score': a.max_score,
                'value': _q2(_normalize(g.score, a.max_score, out_of)) if not g.is_absent else None,
                'appreciation': g.appreciation,
            })

    period_averages = []
    for p in periods:
        try:
            ctx = _build_bulletin_context(student, p, year)
            period_averages.append({'period': p, 'average': ctx.get('general_avg'), 'rank': ctx.get('rank')})
        except Exception:
            period_averages.append({'period': p, 'average': None, 'rank': None})

    return render(request, 'eleve/notes.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': year,
        'is_primary': is_primary,
        'periods': periods,
        'period': period,
        'period_id': str(period.pk) if period else '',
        'subject_results': bulletin.get('subject_results', []) if bulletin else [],
        'general_avg': bulletin.get('general_avg') if bulletin else None,
        'rank': bulletin.get('rank') if bulletin else None,
        'rank_total': bulletin.get('rank_total') if bulletin else None,
        'details': details,
        'period_averages': period_averages,
        'section': 'notes',
    })


@role_required('eleve')
def bulletins(request):
    student, default_year, enrollment = _base_context(request)
    years = []
    selected_year = default_year
    if student:
        years = [
            e.academic_year for e in student.enrollments
            .select_related('academic_year').order_by('-academic_year__start_date')
        ]
        year_id = request.GET.get('year', '')
        if year_id:
            selected_year = next((y for y in years if str(y.pk) == str(year_id)), default_year)

    is_primary = False
    if student:
        from grades.bulletin_views import _is_primary
        is_primary = _is_primary(student, selected_year)
    periods = _periods_for(request, selected_year, is_primary)

    rows = []
    if student:
        for p in periods:
            ctx = _build_bulletin_context(student, p, selected_year)
            rows.append({
                'period': p,
                'average': ctx.get('general_avg'),
                'rank': ctx.get('rank'),
                'rank_total': ctx.get('rank_total'),
                'appreciation': ctx.get('appreciation'),
            })
        annual = _build_bulletin_context(student, None, selected_year)
        rows.append({
            'period': None,
            'average': annual.get('general_avg'),
            'rank': annual.get('rank'),
            'rank_total': annual.get('rank_total'),
            'appreciation': annual.get('appreciation'),
        })

    return render(request, 'eleve/bulletins.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': selected_year,
        'years': years,
        'is_primary': is_primary,
        'rows': rows,
        'section': 'bulletins',
    })


@role_required('eleve')
def emploi_du_temps(request):
    student, year, enrollment = _base_context(request)
    classroom = enrollment.classroom if enrollment else None
    classroom_id = request.GET.get('classroom', '')
    if classroom_id:
        allowed = filter_classrooms_for_user(request.user)
        classroom = allowed.filter(pk=classroom_id).first() or classroom

    ensure_default_slots()
    slots = list(TimeSlot.objects.order_by('order'))
    entries = {}
    if classroom:
        entries = {
            (e.day, e.time_slot_id): e
            for e in TimetableEntry.objects.filter(classroom=classroom).select_related(
                'subject', 'teacher', 'room', 'time_slot'
            )
        }

    days = []
    for day_num, label in DAYS:
        items = []
        for slot in slots:
            if _is_break_slot(slot) or (
                slot.start_time.hour == 0 and slot.end_time.hour == 0
                and slot.start_time.minute == 0 and slot.end_time.minute == 0
            ):
                continue
            entry = entries.get((day_num, slot.pk))
            if not entry:
                continue
            items.append({
                'entry': entry,
                'slot': slot,
                'color': _color_for(entry.subject.name) if entry.subject_id else _color_for(''),
            })
        days.append({'num': day_num, 'label': label, 'items': items})

    today = date.today().isoweekday()
    return render(request, 'eleve/emploi_du_temps.html', {
        'student': student,
        'enrollment': enrollment,
        'classroom': classroom,
        'current_year': year,
        'days': days,
        'slots': slots,
        'today': today,
        'section': 'emploi',
    })


@role_required('eleve')
def absences(request):
    student, year, enrollment = _base_context(request)
    qs = Absence.objects.none()
    if student:
        qs = Absence.objects.filter(student=student).select_related(
            'classroom', 'recorded_by'
        ).order_by('-date', '-id')

    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    if type_filter in ('absence', 'retard'):
        qs = qs.filter(type=type_filter)
    if status_filter in ('justifiee', 'non_justifiee', 'en_attente'):
        qs = qs.filter(status=status_filter)

    all_qs = Absence.objects.filter(student=student) if student else Absence.objects.none()
    stats = {
        'absences': all_qs.filter(type='absence').count(),
        'retards': all_qs.filter(type='retard').count(),
        'justifiees': all_qs.filter(status='justifiee').count(),
        'non_justifiees': all_qs.filter(status__in=['non_justifiee', 'en_attente']).count(),
    }
    page = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'eleve/absences.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': year,
        'page': page,
        'stats': stats,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'section': 'absences',
    })


@role_required('eleve')
@require_POST
def homework_toggle(request, pk):
    student, _year, _enrollment = _base_context(request)
    if not student:
        messages.error(request, "Aucun élève n'est lié à votre compte.")
        return redirect('eleve:homework')
    homework = get_object_or_404(
        Homework,
        pk=pk,
        is_published=True,
        classroom__enrollments__student=student,
        classroom__enrollments__is_active=True,
    )
    if request.POST.get('done') == '1':
        HomeworkCompletion.objects.get_or_create(homework=homework, student=student)
        messages.success(request, 'Devoir marqué comme fait.')
    else:
        HomeworkCompletion.objects.filter(homework=homework, student=student).delete()
        messages.info(request, 'Devoir remis à faire.')
    return redirect(request.POST.get('next') or 'eleve:homework')


@role_required('eleve')
def homework_list(request):
    student, year, enrollment = _base_context(request)
    qs = Homework.objects.none()
    if student:
        qs = (
            Homework.objects
            .filter(
                is_published=True,
                classroom__enrollments__student=student,
                classroom__enrollments__is_active=True,
            )
            .select_related('subject', 'teacher', 'classroom')
            .distinct()
        )
    tab = request.GET.get('tab', '')
    done_ids = set()
    if student:
        done_ids = set(
            HomeworkCompletion.objects.filter(student=student).values_list('homework_id', flat=True)
        )
    today = date.today()
    if tab == 'a_faire':
        qs = qs.filter(due_date__gte=today).exclude(pk__in=done_ids)
    elif tab == 'faits':
        qs = qs.filter(pk__in=done_ids)
    elif tab == 'passes':
        qs = qs.filter(due_date__lt=today)

    homeworks = []
    for hw in qs:
        homeworks.append({
            'homework': hw,
            'done': hw.pk in done_ids,
            'late': hw.due_date < today and hw.pk not in done_ids,
            'days_left': (hw.due_date - today).days,
        })

    return render(request, 'eleve/devoirs.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': year,
        'homeworks': homeworks,
        'done_ids': done_ids,
        'tab': tab,
        'today': today,
        'section': 'devoirs',
    })


@role_required('eleve')
def messagerie(request):
    qs = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).order_by('-sent_at')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'repondre':
            msg = get_object_or_404(Message, pk=request.POST.get('id'), recipient=request.user)
            if msg.sender_id:
                Message.objects.create(
                    sender=request.user, recipient=msg.sender,
                    subject=f'Re : {msg.subject}',
                    body=request.POST.get('body', '').strip(),
                )
                messages.success(request, 'Réponse envoyée.')
        elif action == 'nouveau':
            recipient = User.objects.filter(
                pk=request.POST.get('recipient'), is_active=True
            ).first()
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            if recipient and subject and body:
                Message.objects.create(
                    sender=request.user, recipient=recipient,
                    subject=subject, body=body,
                )
                messages.success(request, 'Message envoyé.')
            else:
                messages.error(request, 'Destinataire, objet et message sont obligatoires.')
        return redirect('eleve:messagerie')

    return render(request, 'eleve/messagerie.html', {
        'conversations': qs[:60],
        'unread': qs.filter(recipient=request.user, is_read=False).count(),
        'contacts': User.objects.filter(is_active=True).exclude(pk=request.user.pk)
        .order_by('last_name', 'first_name')[:100],
        'section': 'messages',
    })


@role_required('eleve')
def informations(request):
    student, year, enrollment = _base_context(request)
    parents = []
    if student:
        parents = list(
            ParentStudent.objects.filter(student=student)
            .select_related('parent')
            .order_by('-is_primary', 'parent__last_name')
        )
    return render(request, 'eleve/informations.html', {
        'student': student,
        'enrollment': enrollment,
        'current_year': year,
        'parents': parents,
        'section': 'profil',
    })


# ── Saisie des devoirs (enseignants / direction) ────────────────────────────

def _manageable_classrooms(user):
    if get_role(user) == 'enseignant' and not user.is_superuser:
        return get_teacher_classrooms(user)
    from academics.models import ClassRoom
    return ClassRoom.objects.all()


@role_required('enseignant')
def teacher_homework(request):
    classrooms = _manageable_classrooms(request.user)
    qs = (
        Homework.objects
        .filter(classroom__in=classrooms)
        .select_related('classroom', 'subject', 'teacher')
        .order_by('-due_date', '-created_at')
    )
    return render(request, 'eleve/teacher_homework.html', {
        'homeworks': qs,
        'classrooms': classrooms,
        'section': 'devoirs',
    })


@role_required('enseignant')
def teacher_homework_form(request, pk=None):
    instance = None
    if pk:
        instance = get_object_or_404(Homework, pk=pk)
        if not _manageable_classrooms(request.user).filter(pk=instance.classroom_id).exists():
            messages.error(request, "Ce devoir n'est pas dans vos classes.")
            return redirect('eleve:teacher_homework')

    manageable = _manageable_classrooms(request.user)

    if request.method == 'POST':
        form = HomeworkForm(request.POST, request.FILES, instance=instance)
        form.fields['classroom'].queryset = manageable
        if form.is_valid():
            hw = form.save(commit=False)
            if not hw.teacher_id:
                hw.teacher = get_linked_teacher(request.user)
            hw.save()
            messages.success(request, 'Devoir enregistré.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal') == '1':
                return HttpResponse(
                    '<div class="p-4 text-sm text-emerald-700">Devoir enregistré. '
                    'Fermez cette fenêtre pour actualiser la liste.</div>'
                )
            return redirect('eleve:teacher_homework')
    else:
        form = HomeworkForm(instance=instance)

    form.fields['classroom'].queryset = manageable
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    template = 'eleve/homework_form_modal.html' if is_modal else 'eleve/homework_form.html'
    return render(request, template, {
        'form': form,
        'instance': instance,
        'is_modal': is_modal,
        'section': 'devoirs',
    })


@role_required('enseignant')
@require_POST
def teacher_homework_delete(request, pk):
    instance = get_object_or_404(Homework, pk=pk)
    if not _manageable_classrooms(request.user).filter(pk=instance.classroom_id).exists():
        messages.error(request, "Ce devoir n'est pas dans vos classes.")
        return redirect('eleve:teacher_homework')
    instance.delete()
    messages.success(request, 'Devoir supprimé.')
    return redirect('eleve:teacher_homework')
