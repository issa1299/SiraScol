# -*- coding: utf-8 -*-
"""Espace Surveillant — pointage, présences, absences, retards, discipline, sorties."""
from datetime import date, timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom
from core.notifications import notify_role
from core.permissions import role_required
from core.year_context import get_selected_year
from students.models import Enrollment, Student

from .models import (
    AttendanceSession, DisciplineIncident, PresenceChange,
    PresenceRecord, StudentExit,
)

MENUS = [
    ('dashboard', 'Tableau de bord', 'fa-gauge-high', 'surveillant:dashboard'),
    ('pointage', 'Pointage des élèves', 'fa-user-check', 'surveillant:pointage'),
    ('presences', 'Présences', 'fa-calendar-day', 'surveillant:presences'),
    ('absences', 'Absences', 'fa-user-slash', 'surveillant:absences'),
    ('retards', 'Retards', 'fa-clock', 'surveillant:retards'),
    ('discipline', 'Discipline', 'fa-shield-halved', 'surveillant:discipline'),
    ('sorties', 'Sorties des élèves', 'fa-door-open', 'surveillant:sorties'),
    ('historique', 'Historique', 'fa-clock-rotate-left', 'surveillant:historique'),
    ('rapports', 'Rapports', 'fa-file-lines', 'surveillant:rapports'),
    ('notifications', 'Notifications', 'fa-bell', 'surveillant:notifications'),
    ('profil', 'Mon profil', 'fa-user', 'surveillant:profil'),
]


def _ctx(request, section, **extra):
    ctx = {'section': section, 'menus': MENUS, 'today': date.today()}
    ctx.update(extra)
    return ctx


def _classes(request):
    year = get_selected_year(request)
    qs = ClassRoom.objects.select_related('level', 'academic_year').order_by('name')
    if year:
        qs = qs.filter(academic_year=year)
    return qs, year


def _students_of(classroom):
    if not classroom:
        return []
    return list(
        Student.objects.filter(
            enrollments__classroom=classroom, enrollments__is_active=True
        ).select_related('user').order_by('last_name', 'first_name')
    )


def _selected_class(request):
    cid = request.GET.get('classroom') or request.POST.get('classroom') or ''
    return ClassRoom.objects.filter(pk=cid).first() if cid else None


def _filter_date(request):
    raw = (request.GET.get('date') or '').strip()
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


# ── 1. Tableau de bord ──────────────────────────────────────────────────────
@role_required('surveillant')
def dashboard(request):
    today = date.today()
    total = Student.objects.filter(status='actif').count()
    records = PresenceRecord.objects.filter(date=today)

    activities = []
    for change in PresenceChange.objects.select_related(
        'record__student', 'changed_by'
    )[:8]:
        activities.append({
            'when': change.changed_at, 'icon': 'fa-pen', 'color': 'blue',
            'text': f"{change.record.student} : {change.old_status} → {change.new_status}",
            'author': change.changed_by,
        })
    for exit in StudentExit.objects.select_related('student')[:8]:
        activities.append({
            'when': timezone.make_aware(timezone.datetime.combine(exit.date, exit.exit_time))
            if timezone.is_naive(timezone.datetime.combine(exit.date, exit.exit_time))
            else timezone.datetime.combine(exit.date, exit.exit_time),
            'icon': 'fa-door-open', 'color': 'amber',
            'text': f"Sortie de {exit.student} à {exit.exit_time.strftime('%H:%M')}",
            'author': None,
        })
    for inc in DisciplineIncident.objects.select_related('student')[:8]:
        activities.append({
            'when': timezone.datetime.combine(inc.date, timezone.datetime.min.time()),
            'icon': 'fa-shield-halved', 'color': 'rose',
            'text': f"{inc.get_type_display()} — {inc.student} : {inc.motif}",
            'author': inc.author,
        })
    def _naive(value):
        return timezone.make_naive(value) if timezone.is_aware(value) else value

    activities.sort(key=lambda x: _naive(x['when']), reverse=True)
    activities = activities[:10]

    return render(request, 'surveillant/dashboard.html', _ctx(
        request, 'dashboard',
        total_students=total,
        present=records.filter(status='present').count(),
        absent=records.filter(status='absent').count(),
        late=records.filter(status='retard').count(),
        excluded=records.filter(status='exclu').count()
        + DisciplineIncident.objects.filter(
            date=today, type='exclusion'
        ).count(),
        activities=activities,
    ))


# ── 2. Pointage intelligent ────────────────────────────────────────────────
@role_required('surveillant')
def pointage(request):
    classes, year = _classes(request)
    classroom = _selected_class(request)
    day = _filter_date(request)
    period = request.GET.get('period', 'journee')

    existing = {}
    if classroom:
        for rec in PresenceRecord.objects.filter(date=day, period=period):
            existing[rec.student_id] = rec

    if request.method == 'POST':
        if not classroom:
            messages.error(request, 'Choisissez une classe.')
            return redirect('surveillant:pointage')
        day_raw = request.POST.get('date') or day.isoformat()
        try:
            day = date.fromisoformat(day_raw)
        except ValueError:
            messages.error(request, 'Date invalide.')
            return redirect('surveillant:pointage')
        period = request.POST.get('period', 'journee')
        validate = request.POST.get('validate') == '1'
        saved = 0
        with transaction.atomic():
            session, _ = AttendanceSession.objects.get_or_create(
                classroom=classroom, date=day, period=period,
                defaults={'validated_by': request.user},
            )
            for student in _students_of(classroom):
                status = request.POST.get(f'status_{student.pk}', 'present')
                if status not in dict(PresenceRecord.STATUS_CHOICES):
                    continue
                arrival = request.POST.get(f'arrival_{student.pk}') or None
                reason = request.POST.get(f'reason_{student.pk}', '').strip()
                if status == 'retard' and not arrival:
                    arrival = timezone.now().strftime('%H:%M')
                rec, created = PresenceRecord.objects.update_or_create(
                    student=student, date=day, period=period,
                    defaults={
                        'classroom': classroom, 'session': session,
                        'status': status, 'arrival_time': arrival, 'reason': reason,
                        'updated_by': request.user,
                        'recorded_by': request.user,
                    },
                )
                if not created:
                    PresenceChange.objects.create(
                        record=rec, old_status=rec.status, new_status=status,
                        new_reason=reason, changed_by=request.user,
                    )
                saved += 1
            if validate:
                session.validated_by = request.user
                session.save(update_fields=['validated_by'])
        messages.success(request, f'{saved} présence(s) enregistrée(s) pour {classroom.name}.')
        return redirect(
            f"{reverse('surveillant:pointage')}?classroom={classroom.pk}&date={day.isoformat()}&period={period}"
        )

    rows = []
    for student in _students_of(classroom):
        rows.append({'student': student, 'record': existing.get(student.pk)})
    return render(request, 'surveillant/pointage.html', _ctx(
        request, 'pointage', classes=classes, classroom=classroom, day=day,
        period=period, rows=rows, statuses=PresenceRecord.STATUS_CHOICES,
        validated=AttendanceSession.objects.filter(
            classroom=classroom, date=day, period=period, validated_by__isnull=False
        ).first() if classroom else None,
    ))


# ── 3. Présences ────────────────────────────────────────────────────────────
@role_required('surveillant')
def presences(request):
    classes, year = _classes(request)
    day = _filter_date(request)
    classroom = _selected_class(request)
    status_filter = request.GET.get('status', '')
    q = (request.GET.get('q') or '').strip()

    qs = PresenceRecord.objects.filter(date=day).select_related(
        'student', 'classroom', 'recorded_by'
    )
    if classroom:
        qs = qs.filter(classroom=classroom)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__matricule__icontains=q)
        )
    records = qs.order_by('classroom__name', 'student__last_name')[:300]
    return render(request, 'surveillant/presences.html', _ctx(
        request, 'presences', classes=classes, classroom=classroom, day=day,
        status_filter=status_filter, q=q, records=records,
        statuses=PresenceRecord.STATUS_CHOICES,
    ))


@role_required('surveillant')
@require_POST
def presence_edit(request, pk):
    rec = get_object_or_404(PresenceRecord, pk=pk)
    old_status, old_reason = rec.status, rec.reason
    status = request.POST.get('status', rec.status)
    if status in dict(PresenceRecord.STATUS_CHOICES):
        rec.status = status
    rec.arrival_time = request.POST.get('arrival_time') or None
    rec.reason = request.POST.get('reason', '')
    rec.updated_by = request.user
    rec.save()
    PresenceChange.objects.create(
        record=rec, old_status=old_status, new_status=rec.status,
        old_reason=old_reason, new_reason=rec.reason,
        changed_by=request.user, note=request.POST.get('note', ''),
    )
    if status == 'absent':
        notify_role(
            'directeur',
            'Absence signalée par le surveillant',
            f'{rec.student.full_name} — {rec.date} : {rec.reason or "absence non justifiée"}',
            'absence',
        )
    messages.success(request, 'Présence modifiée et tracée.')
    return redirect(request.POST.get('next') or reverse('surveillant:presences'))


# ── 4. Absences ─────────────────────────────────────────────────────────────
@role_required('surveillant')
def absences(request):
    classes, year = _classes(request)
    day = _filter_date(request)
    classroom = _selected_class(request)
    qs = PresenceRecord.objects.filter(status='absent', date=day).select_related(
        'student', 'classroom'
    )
    if classroom:
        qs = qs.filter(classroom=classroom)
    rows = list(qs.order_by('classroom__name', 'student__last_name'))
    return render(request, 'surveillant/absences.html', _ctx(
        request, 'absences', classes=classes, classroom=classroom, day=day, rows=rows,
    ))


@role_required('surveillant')
@require_POST
def absence_justify(request, pk):
    rec = get_object_or_404(PresenceRecord, pk=pk, status='absent')
    rec.reason = request.POST.get('reason', '').strip() or 'Justificatif fourni'
    rec.updated_by = request.user
    rec.save(update_fields=['reason', 'updated_by', 'updated_at'])
    PresenceChange.objects.create(
        record=rec, old_status='absent', new_status='absent',
        new_reason=rec.reason, changed_by=request.user, note='Absence justifiée',
    )
    messages.success(request, 'Justificatif enregistré.')
    return redirect('surveillant:absences')


@role_required('surveillant')
@require_POST
def absence_create(request):
    student_id = request.POST.get('student')
    day_raw = request.POST.get('date') or date.today().isoformat()
    kind = request.POST.get('kind', 'absent')
    if not student_id:
        messages.error(request, 'Choisissez un élève.')
        return redirect('surveillant:absences')
    try:
        day = date.fromisoformat(day_raw)
    except ValueError:
        messages.error(request, 'Date invalide.')
        return redirect('surveillant:absences')
    student = get_object_or_404(Student, pk=student_id)
    rec, created = PresenceRecord.objects.update_or_create(
        student=student, date=day, period='journee',
        defaults={
            'classroom': student.current_enrollment().classroom
            if student.current_enrollment() else None,
            'status': 'retard' if kind == 'retard' else 'absent',
            'arrival_time': request.POST.get('arrival_time') or None,
            'reason': request.POST.get('reason', '').strip(),
            'recorded_by': request.user,
        },
    )
    messages.success(request, 'Enregistrement effectué.')
    return redirect('surveillant:absences' if kind != 'retard' else 'surveillant:retards')


# ── 5. Retards ──────────────────────────────────────────────────────────────
@role_required('surveillant')
def retards(request):
    classes, year = _classes(request)
    day = _filter_date(request)
    rows = PresenceRecord.objects.filter(status='retard', date=day).select_related(
        'student', 'classroom'
    ).order_by('arrival_time', 'student__last_name')
    return render(request, 'surveillant/retards.html', _ctx(
        request, 'retards', classes=classes, day=day, rows=rows,
    ))


# ── 6. Discipline ───────────────────────────────────────────────────────────
@role_required('surveillant')
def discipline(request):
    classes, year = _classes(request)
    q = (request.GET.get('q') or '').strip()
    qs = DisciplineIncident.objects.select_related('student', 'classroom', 'author')
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q)
            | Q(motif__icontains=q)
        )
    rows = qs[:200]
    return render(request, 'surveillant/discipline.html', _ctx(
        request, 'discipline', classes=classes, rows=rows, q=q,
        types=DisciplineIncident.TYPE_CHOICES,
        students=Student.objects.filter(status='actif').order_by('last_name', 'first_name'),
    ))


@role_required('surveillant')
@require_POST
def discipline_create(request):
    student = get_object_or_404(Student, pk=request.POST.get('student'))
    kind = request.POST.get('type', 'observation')
    motif = (request.POST.get('motif') or '').strip()
    if not motif:
        messages.error(request, 'Le motif est obligatoire.')
        return redirect('surveillant:discipline')
    day_raw = request.POST.get('date') or date.today().isoformat()
    try:
        day = date.fromisoformat(day_raw)
    except ValueError:
        day = date.today()
    classroom = student.current_enrollment().classroom if student.current_enrollment() else None
    inc = DisciplineIncident.objects.create(
        student=student, classroom=classroom, type=kind, motif=motif,
        description=request.POST.get('description', ''), date=day, author=request.user,
    )
    if kind in ('sanction', 'exclusion', 'avertissement'):
        PresenceRecord.objects.update_or_create(
            student=student, date=day, period='journee',
            defaults={
                'classroom': classroom, 'status': 'exclu' if kind == 'exclusion' else 'present',
                'reason': f'{inc.get_type_display()} : {motif}', 'recorded_by': request.user,
            },
        )
        notify_role(
            'directeur', f'{inc.get_type_display()} — {student.full_name}',
            f'{motif}. Voir la fiche du élève.', 'info',
        )
    messages.success(request, 'Incident disciplinaire enregistré.')
    return redirect('surveillant:discipline')


@role_required('surveillant')
@require_POST
def discipline_comment(request, pk):
    inc = get_object_or_404(DisciplineIncident, pk=pk)
    comment = (request.POST.get('comment') or '').strip()
    if comment:
        inc.comment = (inc.comment + '\n' + comment).strip()
        inc.save(update_fields=['comment', 'updated_at'])
        messages.success(request, 'Commentaire ajouté.')
    return redirect('surveillant:discipline')


# ── 7. Sorties ──────────────────────────────────────────────────────────────
@role_required('surveillant')
def sorties(request):
    day = _filter_date(request)
    rows = StudentExit.objects.filter(date=day).select_related(
        'student', 'classroom', 'recorded_by'
    )
    return render(request, 'surveillant/sorties.html', _ctx(
        request, 'sorties', day=day, rows=rows,
        students=Student.objects.filter(status='actif').order_by('last_name', 'first_name'),
    ))


@role_required('surveillant')
@require_POST
def sortie_create(request):
    student = get_object_or_404(Student, pk=request.POST.get('student'))
    day_raw = request.POST.get('date') or date.today().isoformat()
    time_raw = request.POST.get('exit_time') or timezone.now().strftime('%H:%M')
    try:
        day = date.fromisoformat(day_raw)
    except ValueError:
        day = date.today()
    classroom = student.current_enrollment().classroom if student.current_enrollment() else None
    StudentExit.objects.create(
        student=student, classroom=classroom, date=day, exit_time=time_raw,
        reason=request.POST.get('reason', '').strip(),
        picked_up_by=request.POST.get('picked_up_by', '').strip(),
        return_time=request.POST.get('return_time') or None,
        recorded_by=request.user,
    )
    PresenceRecord.objects.update_or_create(
        student=student, date=day, period='journee',
        defaults={
            'classroom': classroom, 'status': 'sortie', 'recorded_by': request.user,
            'reason': request.POST.get('reason', ''),
        },
    )
    messages.success(request, 'Sortie enregistrée.')
    return redirect('surveillant:sorties')


@role_required('surveillant')
@require_POST
def sortie_return(request, pk):
    exit = get_object_or_404(StudentExit, pk=pk)
    exit.return_time = request.POST.get('return_time') or timezone.now().strftime('%H:%M')
    exit.save(update_fields=['return_time'])
    messages.success(request, 'Heure de retour enregistrée.')
    return redirect('surveillant:sorties')


# ── 8. Historique ───────────────────────────────────────────────────────────
@role_required('surveillant')
def historique(request):
    q = (request.GET.get('q') or '').strip()
    kind = request.GET.get('kind', '')
    rows = []
    if kind in ('', 'presence'):
        for c in PresenceChange.objects.select_related('record__student', 'changed_by')[:200]:
            rows.append({
                'date': c.changed_at.date(), 'kind': 'Présence',
                'student': c.record.student,
                'detail': f'{c.old_status} → {c.new_status} {c.note}', 'author': c.changed_by,
            })
    if kind in ('', 'sortie'):
        for s in StudentExit.objects.select_related('student')[:200]:
            rows.append({
                'date': s.date, 'kind': 'Sortie', 'student': s.student,
                'detail': f"{s.exit_time.strftime('%H:%M')} · {s.reason} · {s.picked_up_by}",
                'author': s.recorded_by,
            })
    if kind in ('', 'discipline'):
        for i in DisciplineIncident.objects.select_related('student')[:200]:
            rows.append({
                'date': i.date, 'kind': i.get_type_display(), 'student': i.student,
                'detail': i.motif, 'author': i.author,
            })
    if q:
        rows = [r for r in rows if q.lower() in r['student'].full_name.lower()]
    rows.sort(key=lambda x: x['date'], reverse=True)
    return render(request, 'surveillant/historique.html', _ctx(
        request, 'historique', rows=rows[:200], q=q, kind=kind,
    ))


# ── 9. Rapports ─────────────────────────────────────────────────────────────
@role_required('surveillant')
def rapports(request):
    start_raw = request.GET.get('start', '')
    end_raw = request.GET.get('end', '')
    today = date.today()
    try:
        start = date.fromisoformat(start_raw) if start_raw else today - timedelta(days=30)
    except ValueError:
        start = today - timedelta(days=30)
    try:
        end = date.fromisoformat(end_raw) if end_raw else today
    except ValueError:
        end = today
    kind = request.GET.get('kind', 'presence')

    if kind == 'discipline':
        qs = DisciplineIncident.objects.filter(date__range=[start, end]).select_related('student', 'classroom')
        headers = ['Date', 'Élève', 'Classe', 'Type', 'Motif', 'Auteur']
        rows = [[
            i.date.strftime('%d/%m/%Y'), i.student.full_name,
            i.classroom.name if i.classroom else '—', i.get_type_display(), i.motif,
            (i.author.get_full_name() if i.author else '—'),
        ] for i in qs]
    elif kind == 'sorties':
        qs = StudentExit.objects.filter(date__range=[start, end]).select_related('student')
        headers = ['Date', 'Élève', 'Heure', 'Motif', 'Récupéré par', 'Retour']
        rows = [[
            s.date.strftime('%d/%m/%Y'), s.student.full_name, s.exit_time.strftime('%H:%M'),
            s.reason, s.picked_up_by, s.return_time.strftime('%H:%M') if s.return_time else '—',
        ] for s in qs]
    else:
        qs = PresenceRecord.objects.filter(date__range=[start, end]).select_related('student', 'classroom')
        if kind in ('absences', 'retards'):
            qs = qs.filter(status='absent' if kind == 'absences' else 'retard')
        headers = ['Date', 'Élève', 'Classe', 'Statut', 'Arrivée', 'Motif']
        rows = [[
            r.date.strftime('%d/%m/%Y'), r.student.full_name,
            r.classroom.name if r.classroom else '—', r.get_status_display(),
            r.arrival_time.strftime('%H:%M') if r.arrival_time else '—', r.reason,
        ] for r in qs]

    fmt = request.GET.get('format', '')
    if fmt == 'excel':
        return _excel_report(kind, headers, rows)
    if fmt == 'pdf':
        from core.list_pdf import build_list_pdf
        labels = {
            'presence': 'Rapport de présence', 'absences': 'Rapport des absences',
            'retards': 'Rapport des retards', 'discipline': 'Rapport disciplinaire',
            'sorties': 'Rapport des sorties',
        }
        return build_list_pdf(
            labels.get(kind, 'Rapport'), f'Du {start.strftime("%d/%m/%Y")} au {end.strftime("%d/%m/%Y")}',
            headers, rows, f'rapport_{kind}_{start.isoformat()}.pdf', landscape_mode=True,
        )

    return render(request, 'surveillant/rapports.html', _ctx(
        request, 'rapports', kind=kind, start=start, end=end,
        headers=headers, rows=rows[:300], count=len(rows),
    ))


def _excel_report(kind, headers, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapport'
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1E40AF')
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        width = max((len(str(c.value or '')) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 12), 45)
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="rapport_{kind}.xlsx"'
    return resp


# ── 10. Notifications ───────────────────────────────────────────────────────
@role_required('surveillant')
def notifications(request):
    since = date.today() - timedelta(days=30)
    repeated_absences = (
        PresenceRecord.objects.filter(date__gte=since, status='absent')
        .values('student__pk', 'student__first_name', 'student__last_name')
        .annotate(total=Count('pk'))
        .filter(total__gte=3).order_by('-total')
    )
    frequent_lates = (
        PresenceRecord.objects.filter(date__gte=since, status='retard')
        .values('student__pk', 'student__first_name', 'student__last_name')
        .annotate(total=Count('pk'))
        .filter(total__gte=3).order_by('-total')
    )
    return render(request, 'surveillant/notifications.html', _ctx(
        request, 'notifications',
        repeated_absences=repeated_absences, frequent_lates=frequent_lates,
    ))


@role_required('surveillant')
@require_POST
def notify_direction(request):
    subject = (request.POST.get('subject') or '').strip()
    body = (request.POST.get('body') or '').strip()
    if not subject or not body:
        messages.error(request, 'Le sujet et le message sont obligatoires.')
        return redirect('surveillant:notifications')
    notify_role('directeur', subject, body, 'info', reverse('surveillant:historique'))
    messages.success(request, 'Information transmise à la direction.')
    return redirect('surveillant:notifications')


# ── 11. Profil ──────────────────────────────────────────────────────────────
@role_required('surveillant')
def profil(request):
    return render(request, 'surveillant/profil.html', _ctx(request, 'profil'))
