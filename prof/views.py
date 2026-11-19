# -*- coding: utf-8 -*-
"""Espace Professeur — portail dédié, données limitées à ses affectations."""

from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import ClassRoom, Subject, SubjectAssignment
from attendance.models import Absence
from communication.models import Announcement, Message
from core.messaging import allowed_recipients
from core.models import Notification
from django.contrib.auth.models import User
from core.permissions import (
    get_linked_teacher, get_teacher_classrooms, role_required,
)
from core.year_context import get_selected_year
from eleve.forms import HomeworkForm
from eleve.models import Homework
from grades.bulletin_views import _build_bulletin_context
from grades.models import Grade
from students.models import Enrollment, Student
from timetable.models import TimetableEntry

from .forms import TeachingMaterialForm
from .models import Appointment, BulletinAppreciation, TeachingMaterial


DAYS = [(1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'), (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi')]


def _base(request):
    teacher = get_linked_teacher(request.user)
    year = get_selected_year(request) or AcademicYear_first()
    classrooms = get_teacher_classrooms(request.user).select_related(
        'level', 'level__cycle', 'academic_year'
    )
    if year:
        classrooms = classrooms.filter(academic_year=year)
    classrooms = list(classrooms)

    assigned_subjects = []
    if teacher:
        assigned_subjects = list(Subject.objects.filter(
            id__in=SubjectAssignment.objects.filter(teacher=teacher).values_list('subject_id', flat=True)
        ).order_by('name'))

    students = Student.objects.filter(
        enrollments__classroom__in=classrooms, enrollments__is_active=True
    ).distinct()
    return {
        'teacher': teacher, 'year': year, 'classrooms': classrooms,
        'subjects': assigned_subjects, 'students': students,
    }


def AcademicYear_first():
    from academics.models import AcademicYear
    return AcademicYear.objects.filter(is_current=True).first() or \
        AcademicYear.objects.order_by('-start_date', '-id').first()


def _teacher_announcements(classrooms):
    qs = Announcement.objects.filter(is_published=True).filter(
        Q(target='all') | Q(target='teachers')
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    if classrooms:
        qs = qs | Announcement.objects.filter(
            is_published=True, target='class',
            classroom__in=classrooms,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    return qs.select_related('classroom').order_by('-published_at')[:6]


@role_required('enseignant')
def dashboard(request):
    ctx = _base(request)
    teacher = ctx['teacher']
    entries = TimetableEntry.objects.none()
    if teacher:
        entries = TimetableEntry.objects.filter(teacher=teacher).select_related(
            'subject', 'classroom', 'room', 'time_slot'
        )
    today = date.today().isoweekday()
    upcoming = [e for e in entries if e.day >= today][:6]
    if len(upcoming) < 5:
        upcoming += [e for e in entries if e.day < today][:5 - len(upcoming)]

    absences_qs = Absence.objects.none()
    if teacher:
        absences_qs = Absence.objects.filter(recorded_by=teacher)
    grades_qs = Grade.objects.none()
    if teacher:
        grades_qs = Grade.objects.filter(assessment__teacher=teacher)

    notifications = Notification.objects.filter(user=request.user, is_read=False)[:5]
    return render(request, 'prof/dashboard.html', {
        'teacher': teacher, 'year': ctx['year'],
        'classrooms': ctx['classrooms'], 'subjects': ctx['subjects'],
        'nb_students': ctx['students'].count(),
        'upcoming': upcoming, 'days': DAYS,
        'announcements': _teacher_announcements(ctx['classrooms']),
        'notifications': notifications,
        'nb_absences': absences_qs.count(),
        'nb_grades': grades_qs.count(),
        'nb_unvalidated': grades_qs.filter(is_validated=False).count(),
        'nb_homeworks': Homework.objects.filter(teacher=teacher).count() if teacher else 0,
        'section': 'accueil',
    })


@role_required('enseignant')
def classes(request):
    ctx = _base(request)
    rows = []
    for c in ctx['classrooms']:
        rows.append({
            'classroom': c,
            'nb_students': Enrollment.objects.filter(classroom=c, is_active=True).count(),
            'subjects': Subject.objects.filter(
                id__in=SubjectAssignment.objects.filter(
                    classroom=c, teacher=ctx['teacher']
                ).values_list('subject_id', flat=True)
            ) if ctx['teacher'] else Subject.objects.none(),
        })
    return render(request, 'prof/classes.html', {
        'rows': rows, 'teacher': ctx['teacher'], 'year': ctx['year'],
        'section': 'classes',
    })


@role_required('enseignant')
def class_detail(request, classroom_id):
    ctx = _base(request)
    classroom = get_object_or_404(ClassRoom, pk=classroom_id)
    if classroom not in ctx['classrooms']:
        messages.error(request, "Cette classe ne fait pas partie de vos affectations.")
        return redirect('prof:classes')
    students = Student.objects.filter(
        enrollments__classroom=classroom, enrollments__is_active=True
    ).select_related('user').order_by('last_name', 'first_name')
    subjects = Subject.objects.filter(
        id__in=SubjectAssignment.objects.filter(
            classroom=classroom, teacher=ctx['teacher']
        ).values_list('subject_id', flat=True)
    )
    return render(request, 'prof/class_detail.html', {
        'classroom': classroom, 'students': students, 'subjects': subjects,
        'teacher': ctx['teacher'], 'year': ctx['year'], 'section': 'classes',
    })


@role_required('enseignant')
def notes(request):
    ctx = _base(request)
    classroom_id = request.GET.get('classroom', '')
    classroom = None
    if classroom_id:
        classroom = next((c for c in ctx['classrooms'] if str(c.pk) == classroom_id), None)
    qs = Grade.objects.none()
    if ctx['teacher']:
        qs = Grade.objects.filter(assessment__teacher=ctx['teacher']).select_related(
            'student', 'assessment__subject', 'assessment__assessment_type',
            'assessment__period', 'assessment__classroom'
        ).order_by('-updated_at')
    if classroom:
        qs = qs.filter(assessment__classroom=classroom)
    grades = list(qs[:150])
    return render(request, 'prof/notes.html', {
        'teacher': ctx['teacher'], 'year': ctx['year'],
        'classrooms': ctx['classrooms'], 'classroom': classroom,
        'grades': grades, 'section': 'notes',
    })


@role_required('enseignant')
def presence(request):
    ctx = _base(request)
    absences = Absence.objects.none()
    if ctx['teacher']:
        absences = Absence.objects.filter(recorded_by=ctx['teacher']).select_related(
            'student', 'classroom'
        ).order_by('-date')[:120]
    frequent = []
    if ctx['classrooms']:
        frequent = list(
            Student.objects.filter(
                enrollments__classroom__in=ctx['classrooms'], enrollments__is_active=True
            ).annotate(
                n_abs=Count('absences', filter=Q(absences__type='absence'))
            ).filter(n_abs__gte=3).order_by('-n_abs')[:10]
        )
    return render(request, 'prof/presence.html', {
        'teacher': ctx['teacher'], 'year': ctx['year'],
        'classrooms': ctx['classrooms'], 'absences': absences,
        'frequent': frequent, 'section': 'presence',
    })


@role_required('enseignant')
def emploi_du_temps(request):
    ctx = _base(request)
    entries = TimetableEntry.objects.none()
    if ctx['teacher']:
        entries = TimetableEntry.objects.filter(teacher=ctx['teacher']).select_related(
            'subject', 'classroom', 'room', 'time_slot'
        ).order_by('day', 'time_slot__order')
    by_day = defaultdict(list)
    for e in entries:
        by_day[e.day].append(e)
    days = []
    for num, label in DAYS:
        items = by_day.get(num, [])
        if not items:
            continue
        days.append({'num': num, 'label': label, 'items': items})
    return render(request, 'prof/emploi_du_temps.html', {
        'teacher': ctx['teacher'], 'year': ctx['year'],
        'days': days, 'today': date.today().isoweekday(),
        'section': 'emploi',
    })


@role_required('enseignant')
def devoirs(request):
    ctx = _base(request)
    teacher = ctx['teacher']
    qs = Homework.objects.none()
    if teacher:
        qs = Homework.objects.filter(teacher=teacher).select_related(
            'classroom', 'subject'
        ).order_by('-due_date')

    if request.method == 'POST':
        form = HomeworkForm(request.POST, request.FILES)
        form.fields['classroom'].queryset = ClassRoom.objects.filter(
            id__in=[c.pk for c in ctx['classrooms']]
        )
        if form.is_valid():
            hw = form.save(commit=False)
            hw.teacher = teacher
            hw.save()
            messages.success(request, 'Devoir publié.')
            return redirect('prof:devoirs')
    else:
        form = HomeworkForm()
        form.fields['classroom'].queryset = ClassRoom.objects.filter(
            id__in=[c.pk for c in ctx['classrooms']]
        )

    return render(request, 'prof/devoirs.html', {
        'teacher': teacher, 'year': ctx['year'], 'homeworks': qs,
        'form': form, 'section': 'devoirs',
    })


@role_required('enseignant')
def supports(request):
    ctx = _base(request)
    teacher = ctx['teacher']
    qs = TeachingMaterial.objects.none()
    if teacher:
        qs = TeachingMaterial.objects.filter(teacher=teacher).select_related(
            'classroom', 'subject'
        ).order_by('-created_at')

    if request.method == 'POST':
        form = TeachingMaterialForm(request.POST, request.FILES)
        form.fields['classroom'].queryset = ClassRoom.objects.filter(
            id__in=[c.pk for c in ctx['classrooms']]
        )
        if form.is_valid():
            obj = form.save(commit=False)
            obj.teacher = teacher
            obj.save()
            messages.success(request, 'Support de cours publié.')
            return redirect('prof:supports')
    else:
        form = TeachingMaterialForm()
        form.fields['classroom'].queryset = ClassRoom.objects.filter(
            id__in=[c.pk for c in ctx['classrooms']]
        )

    return render(request, 'prof/supports.html', {
        'teacher': teacher, 'year': ctx['year'], 'materials': qs,
        'form': form, 'section': 'supports',
    })


@require_POST
@role_required('enseignant')
def support_delete(request, pk):
    obj = get_object_or_404(TeachingMaterial, pk=pk, teacher=get_linked_teacher(request.user))
    obj.delete()
    messages.success(request, 'Support supprimé.')
    return redirect('prof:supports')


@role_required('enseignant')
def bulletins(request):
    ctx = _base(request)
    classroom_id = request.GET.get('classroom', '')
    classroom = None
    if classroom_id:
        classroom = next((c for c in ctx['classrooms'] if str(c.pk) == classroom_id), None)
    rows = []
    if classroom:
        for student in Student.objects.filter(
            enrollments__classroom=classroom, enrollments__is_active=True
        ).order_by('last_name', 'first_name'):
            bctx = _build_bulletin_context(student, None, ctx['year'])
            appreciation = BulletinAppreciation.objects.filter(
                teacher=ctx['teacher'], student=student, is_general=True
            ).first()
            rows.append({
                'student': student, 'average': bctx.get('general_avg'),
                'rank': bctx.get('rank'), 'rank_total': bctx.get('rank_total'),
                'appreciation': appreciation.appreciation if appreciation else '',
                'appreciation_id': appreciation.pk if appreciation else None,
            })
    elif ctx['classrooms']:
        classroom = ctx['classrooms'][0]
        return redirect(f"{reverse('prof:bulletins')}?classroom={classroom.pk}")

    if request.method == 'POST' and ctx['teacher']:
        student_id = request.POST.get('student')
        obj, _created = BulletinAppreciation.objects.update_or_create(
            teacher=ctx['teacher'],
            student_id=student_id,
            period=None,
            is_general=True,
            defaults={'appreciation': request.POST.get('appreciation', '')},
        )
        messages.success(request, 'Appréciation enregistrée.')
        return redirect(f"{reverse('prof:bulletins')}?classroom={classroom.pk}" if classroom else reverse('prof:bulletins'))

    return render(request, 'prof/bulletins.html', {
        'teacher': ctx['teacher'], 'year': ctx['year'],
        'classrooms': ctx['classrooms'], 'classroom': classroom,
        'rows': rows, 'section': 'bulletins',
    })


@role_required('enseignant')
def notifications(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:60]
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        messages.success(request, 'Notifications marquées comme lues.')
        return redirect('prof:notifications')
    return render(request, 'prof/notifications.html', {
        'notifications': qs, 'section': 'notifications',
    })


@role_required('enseignant')
def profil(request):
    ctx = _base(request)
    teacher = ctx['teacher']
    return render(request, 'prof/profil.html', {
        'teacher': teacher, 'year': ctx['year'],
        'classrooms': ctx['classrooms'], 'subjects': ctx['subjects'],
        'section': 'profil',
    })


@role_required('enseignant')
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
                    attachment=request.FILES.get('attachment'),
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
                    attachment=request.FILES.get('attachment'),
                )
                messages.success(request, 'Message envoyé.')
            else:
                messages.error(request, 'Destinataire, objet et message sont obligatoires.')
        elif action == 'lu':
            Message.objects.filter(
                recipient=request.user, id__in=request.POST.getlist('ids')
            ).update(is_read=True)
        return redirect('prof:messages')

    unread = qs.filter(recipient=request.user, is_read=False).count()
    return render(request, 'prof/messagerie.html', {
        'conversations': qs[:60], 'unread': unread,
        'contacts': allowed_recipients(request.user),
        'section': 'messages',
    })


@role_required('enseignant')
def rendezvous(request):
    teacher = get_linked_teacher(request.user)
    qs = Appointment.objects.all() if teacher is None else Appointment.objects.filter(teacher=teacher)
    qs = qs.select_related('parent', 'student', 'teacher').order_by('-created_at')

    if request.method == 'POST':
        pk = request.POST.get('id')
        statut = request.POST.get('status', 'traite')
        reponse = request.POST.get('response', '').strip()
        obj = get_object_or_404(Appointment, pk=pk)
        if teacher is None or obj.teacher_id == teacher.pk:
            obj.status = statut
            obj.response = reponse
            obj.save(update_fields=['status', 'response', 'updated_at'])
            messages.success(request, 'Réponse enregistrée.')
        else:
            messages.error(request, 'Cette demande ne vous est pas adressée.')
        return redirect('prof:rendezvous')

    return render(request, 'prof/rendezvous.html', {
        'appointments': qs[:80], 'teacher': teacher,
        'section': 'rendezvous',
    })


@role_required('directeur')
def validation(request):
    grades = Grade.objects.filter(is_validated=False).select_related(
        'student', 'assessment__subject', 'assessment__classroom', 'assessment__teacher'
    ).order_by('assessment__classroom__name', 'student__last_name')[:200]
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        qs = Grade.objects.filter(id__in=ids)
        qs.update(
            is_validated=True, validated_by=request.user, validated_at=timezone.now()
        )
        messages.success(request, f'{qs.count()} note(s) validée(s).')
        return redirect('prof:validation')
    return render(request, 'prof/validation.html', {
        'grades': grades, 'section': 'validation',
    })
