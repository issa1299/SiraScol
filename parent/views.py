# -*- coding: utf-8 -*-
"""Espace Parent — suivi de plusieurs enfants, données strictement limitées à eux."""

from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from communication.models import Announcement, Message
from core.access import get_student_for_user
from core.messaging import allowed_recipients
from core.models import Notification
from core.permissions import get_linked_parent, get_parent_students, role_required
from core.year_context import get_selected_year
from eleve.models import Homework
from finance.models import Invoice, Payment
from grades.bulletin_views import _build_bulletin_context
from grades.models import Grade, Period
from attendance.models import Absence
from prof.models import Appointment, BulletinAppreciation
from students.models import Enrollment, ParentStudent, Student
from timetable.models import TimetableEntry

DAYS = [(1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'), (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi')]


def _first_year():
    from academics.models import AcademicYear
    return AcademicYear.objects.filter(is_current=True).first() or \
        AcademicYear.objects.order_by('-start_date', '-id').first()


def _base(request):
    parent = get_linked_parent(request.user)
    children = list(get_parent_students(request.user).select_related('user').order_by('last_name', 'first_name'))
    child_id = request.GET.get('enfant') or ''
    child = None
    if child_id:
        child = next((s for s in children if str(s.pk) == str(child_id)), None)
    if child is None and children:
        child = children[0]
    year = get_selected_year(request) or _first_year()
    enrollment = None
    if child:
        enrollment = child.enrollments.filter(academic_year=year, is_active=True).select_related(
            'classroom', 'classroom__level'
        ).first()
        if not enrollment:
            enrollment = child.current_enrollment()
    return {
        'parent': parent, 'children': children, 'child': child,
        'year': year, 'enrollment': enrollment,
    }


def _announcements_for(children):
    qs = Announcement.objects.filter(is_published=True).filter(
        Q(target='all') | Q(target='parents')
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    classrooms = [c.enrollments.filter(is_active=True).first().classroom for c in children
                  if c.enrollments.filter(is_active=True).exists()]
    if classrooms:
        qs = qs | Announcement.objects.filter(
            is_published=True, target='class', classroom__in=classrooms
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    return qs.order_by('-published_at')[:6]


def _child_card(child, year):
    bctx = _build_bulletin_context(child, None, year)
    invoices = Invoice.objects.filter(student=child, academic_year=year)
    total = sum(i.amount for i in invoices)
    paid = sum(i.amount_paid for i in invoices)
    return {
        'student': child,
        'classroom': (child.current_enrollment().classroom if child.current_enrollment() else None),
        'average': bctx.get('general_avg'),
        'rank': bctx.get('rank'), 'rank_total': bctx.get('rank_total'),
        'balance': total - paid,
    }


@role_required('parent')
def dashboard(request):
    ctx = _base(request)
    cards = [_child_card(c, ctx['year']) for c in ctx['children']]
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    unread_messages = Message.objects.filter(recipient=request.user, is_read=False).count()
    return render(request, 'parent/dashboard.html', {
        'parent': ctx['parent'], 'children': ctx['children'],
        'cards': cards, 'year': ctx['year'],
        'unread': unread, 'unread_messages': unread_messages,
        'notifications': Notification.objects.filter(user=request.user, is_read=False)[:5],
        'announcements': _announcements_for(ctx['children']),
        'section': 'accueil',
    })


@role_required('parent')
def enfants(request):
    ctx = _base(request)
    cards = [_child_card(c, ctx['year']) for c in ctx['children']]
    return render(request, 'parent/enfants.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'cards': cards,
        'year': ctx['year'], 'section': 'enfants',
    })


@role_required('parent')
def notes(request):
    ctx = _base(request)
    child = ctx['child']
    periods = Period.objects.filter(academic_year=ctx['year']).order_by('order') if ctx['year'] else Period.objects.none()
    period_id = request.GET.get('periode', '')
    period = periods.filter(pk=period_id).first() if period_id else None
    bctx = _build_bulletin_context(child, period, ctx['year']) if child else None
    details = []
    if child:
        qs = Grade.objects.filter(student=child).select_related(
            'assessment__subject', 'assessment__assessment_type', 'assessment__period'
        ).order_by('-assessment__date')
        if period:
            qs = qs.filter(assessment__period=period)
        details = list(qs[:120])
    return render(request, 'parent/notes.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'enrollment': ctx['enrollment'],
        'periods': periods, 'period': period,
        'subject_results': bctx.get('subject_results', []) if bctx else [],
        'general_avg': bctx.get('general_avg') if bctx else None,
        'rank': bctx.get('rank') if bctx else None,
        'rank_total': bctx.get('rank_total') if bctx else None,
        'details': details, 'section': 'notes',
    })


@role_required('parent')
def bulletins(request):
    ctx = _base(request)
    child = ctx['child']
    rows = []
    if child and ctx['year']:
        for p in Period.objects.filter(academic_year=ctx['year']).order_by('order'):
            b = _build_bulletin_context(child, p, ctx['year'])
            rows.append({'period': p, 'average': b.get('general_avg'),
                         'rank': b.get('rank'), 'rank_total': b.get('rank_total')})
        b = _build_bulletin_context(child, None, ctx['year'])
        rows.append({'period': None, 'average': b.get('general_avg'),
                     'rank': b.get('rank'), 'rank_total': b.get('rank_total')})
    appreciations = []
    if child:
        appreciations = list(BulletinAppreciation.objects.filter(student=child).select_related(
            'teacher', 'period'
        ).order_by('-updated_at')[:20])
    return render(request, 'parent/bulletins.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'rows': rows, 'appreciations': appreciations,
        'section': 'bulletins',
    })


@role_required('parent')
def absences(request):
    ctx = _base(request)
    child = ctx['child']
    qs = Absence.objects.none()
    if child:
        qs = Absence.objects.filter(student=child).select_related('classroom').order_by('-date')
    return render(request, 'parent/absences.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'absences': qs,
        'nb_absences': qs.filter(type='absence').count(),
        'nb_retards': qs.filter(type='retard').count(),
        'section': 'absences',
    })


@role_required('parent')
def paiements(request):
    ctx = _base(request)
    child = ctx['child']
    invoices = Invoice.objects.none()
    if child:
        invoices = Invoice.objects.filter(student=child).select_related(
            'fee_type', 'academic_year'
        ).order_by('-due_date')
    invoices = list(invoices)
    payments = Payment.objects.filter(invoice__student=child).select_related(
        'invoice'
    ).order_by('-payment_date') if child else Payment.objects.none()
    total = sum(i.amount for i in invoices)
    paid = sum(i.amount_paid for i in invoices)
    return render(request, 'parent/paiements.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'invoices': invoices, 'payments': payments,
        'total': total, 'paid': paid, 'balance': total - paid,
        'today': date.today(), 'section': 'paiements',
    })


@role_required('parent')
def emploi_du_temps(request):
    ctx = _base(request)
    classroom = ctx['enrollment'].classroom if ctx['enrollment'] else None
    by_day = defaultdict(list)
    if classroom:
        for e in TimetableEntry.objects.filter(classroom=classroom).select_related(
            'subject', 'teacher', 'room', 'time_slot'
        ).order_by('day', 'time_slot__order'):
            by_day[e.day].append(e)
    days = []
    for num, label in DAYS:
        if by_day.get(num):
            days.append({'num': num, 'label': label, 'items': by_day[num]})
    return render(request, 'parent/emploi_du_temps.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': ctx['child'],
        'year': ctx['year'], 'classroom': classroom, 'days': days,
        'today': date.today().isoweekday(), 'section': 'emploi',
    })


@role_required('parent')
def devoirs(request):
    ctx = _base(request)
    child = ctx['child']
    homework = []
    if child:
        for h in Homework.objects.filter(
            is_published=True,
            classroom__enrollments__student=child,
            classroom__enrollments__is_active=True,
        ).select_related('subject', 'teacher', 'classroom').distinct().order_by('due_date'):
            done = h.completions.filter(student=child).exists()
            homework.append({
                'homework': h, 'done': done,
                'late': h.due_date < date.today() and not done,
            })
    return render(request, 'parent/devoirs.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'homeworks': homework, 'section': 'devoirs',
    })


@role_required('parent')
def communication(request):
    ctx = _base(request)
    child = ctx['child']
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'message':
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
                messages.success(request, 'Votre message a été envoyé.')
            else:
                messages.error(request, 'Destinataire, objet et message sont obligatoires.')
        elif action == 'rendezvous':
            teacher_id = request.POST.get('teacher') or None
            motif = request.POST.get('motif', '').strip()
            if motif and child:
                Appointment.objects.create(
                    parent=ctx['parent'], student=child,
                    teacher_id=teacher_id,
                    motif=motif,
                    message=request.POST.get('message', ''),
                    proposed_date=request.POST.get('proposed_date') or None,
                )
                messages.success(request, 'Votre demande de rendez-vous a été envoyée.')
            else:
                messages.error(request, 'Indiquez un motif et sélectionnez un enfant.')
        return redirect('parent:communication')

    conversations = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).order_by('-sent_at')[:20]
    teachers = User.objects.filter(profile__role='enseignant', is_active=True).order_by('last_name')
    appointments = Appointment.objects.filter(parent=ctx['parent']).order_by('-created_at')[:10]
    return render(request, 'parent/communication.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'child': child,
        'year': ctx['year'], 'announcements': _announcements_for(ctx['children']),
        'conversations': conversations, 'teachers': teachers,
        'contacts': allowed_recipients(request.user),
        'appointments': appointments, 'section': 'communication',
    })


@role_required('parent')
def notifications(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:60]
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, id__in=request.POST.getlist('ids')).update(is_read=True)
        messages.success(request, 'Notifications marquées comme lues.')
        return redirect('parent:notifications')
    return render(request, 'parent/notifications.html', {
        'notifications': qs, 'section': 'notifications',
    })


@role_required('parent')
def profil(request):
    ctx = _base(request)
    links = ParentStudent.objects.filter(parent=ctx['parent']).select_related(
        'student'
    ).order_by('-is_primary')
    return render(request, 'parent/profil.html', {
        'parent': ctx['parent'], 'children': ctx['children'], 'year': ctx['year'],
        'links': links, 'section': 'profil',
    })
