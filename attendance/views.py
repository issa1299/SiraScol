from functools import wraps

from core.year_context import get_selected_year
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator

from .models import Absence
from students.models import Student, Enrollment
from academics.models import ClassRoom
from core.permissions import (
    get_role, get_teacher_classrooms, get_parent_students, get_linked_student,
    permission_required,
)


def _students_use_portal(view_func):
    """Les élèves consultent leurs présences dans leur espace dédié."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_role(request.user) == 'eleve' and not request.user.is_superuser:
            return redirect('eleve:absences')
        return view_func(request, *args, **kwargs)
    return _wrapped


@permission_required('attendance.view')
@login_required
@_students_use_portal
def absence_list(request):
    """Historique des présences (pointages QR + absences) — style SiraScol."""
    from datetime import datetime, timedelta
    from collections import defaultdict
    from django.utils import timezone
    from .models import AttendancePunch
    from teachers.models import Teacher

    today = date.today()
    q = request.GET.get('q', '').strip()
    period = request.GET.get('period', 'month')  # today | week | month | year
    year_s = request.GET.get('year', str(today.year))
    month_s = request.GET.get('month', str(today.month))
    status_f = request.GET.get('status', '')  # present | absent | all
    kind_f = request.GET.get('kind', '')  # eleve | personnel

    try:
        year_i = int(year_s)
        month_i = int(month_s)
    except ValueError:
        year_i, month_i = today.year, today.month

    if period == 'today':
        d_from = d_to = today
    elif period == 'week':
        d_from = today - timedelta(days=today.weekday())
        d_to = today
    elif period == 'year':
        d_from = date(year_i, 1, 1)
        d_to = date(year_i, 12, 31)
    else:
        # month
        d_from = date(year_i, month_i, 1)
        if month_i == 12:
            d_to = date(year_i, 12, 31)
        else:
            d_to = date(year_i, month_i + 1, 1) - timedelta(days=1)

    punches = AttendancePunch.objects.filter(date__gte=d_from, date__lte=d_to).select_related(
        'student', 'teacher'
    ).order_by('-punched_at')

    if kind_f in ('eleve', 'personnel'):
        punches = punches.filter(kind=kind_f)
    if q:
        punches = punches.filter(
            Q(student__last_name__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__matricule__icontains=q) |
            Q(teacher__last_name__icontains=q) |
            Q(teacher__first_name__icontains=q) |
            Q(teacher__matricule__icontains=q)
        )

    # Agrégation par personne + date → arrivée / départ
    groups = {}
    for p in punches:
        key = (p.date, p.kind, p.student_id or 0, p.teacher_id or 0)
        if key not in groups:
            groups[key] = {
                'date': p.date,
                'kind': p.kind,
                'student': p.student,
                'teacher': p.teacher,
                'arrivee': None,
                'depart': None,
            }
        local_t = timezone.localtime(p.punched_at) if p.punched_at else None
        if p.action == 'arrivee':
            if groups[key]['arrivee'] is None or (local_t and local_t < groups[key]['arrivee']):
                groups[key]['arrivee'] = local_t
        else:
            if groups[key]['depart'] is None or (local_t and local_t > groups[key]['depart']):
                groups[key]['depart'] = local_t

    rows = []
    for g in groups.values():
        name = ''
        code = ''
        poste = 'Élève' if g['kind'] == 'eleve' else 'Personnel'
        initial = '?'
        if g['student']:
            name = f"{g['student'].last_name} {g['student'].first_name}"
            code = g['student'].matricule
            initial = (g['student'].last_name or '?')[:1].upper()
        elif g['teacher']:
            name = f"{g['teacher'].last_name} {g['teacher'].first_name}"
            code = g['teacher'].matricule
            poste = g['teacher'].speciality or 'Personnel'
            initial = (g['teacher'].last_name or '?')[:1].upper()
        present = g['arrivee'] is not None
        if status_f == 'present' and not present:
            continue
        if status_f == 'absent' and present:
            continue
        rows.append({
            'date': g['date'],
            'name': name,
            'code': code,
            'poste': poste,
            'initial': initial,
            'present': present,
            'arrivee': g['arrivee'],
            'depart': g['depart'],
        })
    rows.sort(key=lambda r: (r['date'], r['arrivee'] or datetime.min.replace(tzinfo=None)), reverse=True)

    n_records = len(rows)
    n_present = sum(1 for r in rows if r['present'])
    n_absent_badge = n_records - n_present

    # Ont pointé / n'ont pas pointé (aujourd'hui, personnel+élèves actifs simplifié)
    punched_today_keys = set()
    for p in AttendancePunch.objects.filter(date=today):
        if p.student_id:
            punched_today_keys.add(('s', p.student_id))
        elif p.teacher_id:
            punched_today_keys.add(('t', p.teacher_id))
    n_pointed = len(punched_today_keys)

    # Stats absences (saisies manuelles) sur période
    abs_qs = Absence.objects.filter(date__gte=d_from, date__lte=d_to)
    n_absences = abs_qs.count()

    # Présences par jour de semaine (lundi=0)
    by_weekday = [0] * 7
    for r in rows:
        if r['present']:
            by_weekday[r['date'].weekday()] += 1
    weekday_labels = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    weekday_stats = []
    total_present = max(n_present, 1)
    for i, lab in enumerate(weekday_labels[:6]):
        c = by_weekday[i]
        weekday_stats.append({
            'label': lab,
            'count': c,
            'pct': int(round(100 * c / total_present)) if n_present else 0,
        })

    # Arrivées par heure 6h-18h
    hour_counts = [0] * 13  # 6..18
    for r in rows:
        if r['arrivee']:
            h = r['arrivee'].hour
            if 6 <= h <= 18:
                hour_counts[h - 6] += 1
    hour_stats = [{'hour': h, 'count': hour_counts[h - 6]} for h in range(6, 19)]
    max_hour = max(hour_counts) if hour_counts else 1

    recent = rows[:8]

    context = {
        'rows': rows[:100],
        'recent': recent,
        'q': q,
        'period': period,
        'year_s': str(year_i),
        'month_s': str(month_i),
        'status_f': status_f,
        'kind_f': kind_f,
        'd_from': d_from,
        'd_to': d_to,
        'today': today,
        'stats': {
            'enregistrements': n_records,
            'presences': n_present,
            'absences': n_absences,
            'ont_pointe': n_pointed,
            'pas_pointe': max(0, n_records - n_pointed),
        },
        'weekday_stats': weekday_stats,
        'hour_stats': hour_stats,
        'max_hour': max(max_hour, 1),
        'months': [
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
            (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        ],
        'years': list(range(today.year - 2, today.year + 2)),
    }
    return render(request, 'attendance/absence_list.html', context)


@permission_required('attendance.take')
@login_required
@_students_use_portal
def absence_create(request):
    """Formulaire simple pour saisir une absence"""
    if request.method == 'POST':
        student_id = request.POST.get('student')
        absence_date = request.POST.get('date')
        absence_type = request.POST.get('type', 'absence')
        status = request.POST.get('status', 'non_justifiee')
        reason = request.POST.get('reason', '')
        classroom_id = request.POST.get('classroom') or None

        try:
            student = Student.objects.get(pk=student_id)
            absence = Absence(
                student=student,
                date=absence_date,
                type=absence_type,
                status=status,
                reason=reason,
            )
            if classroom_id:
                absence.classroom_id = classroom_id
            else:
                enr = student.current_enrollment()
                if enr:
                    absence.classroom = enr.classroom
            absence.save()
            messages.success(request, f"Absence enregistrée pour {student}.")
            return redirect('attendance:list')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    students = Student.objects.filter(status='actif').order_by('last_name', 'first_name')
    classrooms = ClassRoom.objects.select_related('level').all()
    context = {
        'students': students,
        'classrooms': classrooms,
        'type_choices': Absence.TYPE_CHOICES,
        'status_choices': Absence.STATUS_CHOICES,
        'today': date.today().isoformat(),
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'attendance/absence_form_modal.html', context)
    return render(request, 'attendance/absence_form.html', context)


@login_required
@_students_use_portal
def attendance_classes(request):
    from academics.models import AcademicYear
    from students.models import Enrollment
    from django.db.models import Count, Q

    year = get_selected_year(request)
    qs = ClassRoom.objects.select_related('level', 'academic_year')
    if year:
        qs = qs.filter(academic_year=year)
    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        qs = qs.filter(id__in=get_teacher_classrooms(request.user).values_list('id', flat=True))
    elif role == 'parent':
        kids = get_parent_students(request.user)
        qs = qs.filter(id__in=Enrollment.objects.filter(student__in=kids, is_active=True).values_list('classroom_id', flat=True))
    elif role == 'eleve':
        st = get_linked_student(request.user)
        if st:
            qs = qs.filter(id__in=Enrollment.objects.filter(student=st, is_active=True).values_list('classroom_id', flat=True))
        else:
            qs = qs.none()
    qs = qs.annotate(
        nb_eleves=Count('enrollments', filter=Q(enrollments__is_active=True))
    ).order_by('level__order', 'name')

    return render(request, 'attendance/classes.html', {
        'classrooms': qs,
        'current_year': year,
    })


@permission_required('attendance.take')
@login_required
@_students_use_portal
def class_attendance(request, classroom_id):
    """Saisie des absences pour une classe (date + checklist)."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level'), pk=classroom_id
    )
    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        if classroom.id not in get_teacher_classrooms(request.user).values_list('id', flat=True):
            messages.error(request, "Classe hors de vos affectations.")
            return redirect('attendance:classes')
    if role in ('parent', 'eleve') and request.method == 'POST':
        messages.error(request, "Vous ne pouvez pas modifier les absences.")
        return redirect('attendance:classes')
    students = [
        e.student for e in Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student').order_by('student__last_name', 'student__first_name')
    ]
    selected_date = request.GET.get('date') or request.POST.get('date') or date.today().isoformat()
    try:
        selected_date = date.fromisoformat(str(selected_date))
    except (ValueError, TypeError):
        selected_date = date.today()

    if request.method == 'POST':
        absence_type = request.POST.get('type', 'absence')
        status = request.POST.get('status', 'non_justifiee')
        count = 0
        for student in students:
            if request.POST.get(f'absent_{student.id}') == 'on':
                reason = request.POST.get(f'reason_{student.id}', '')
                Absence.objects.update_or_create(
                    student=student,
                    date=selected_date,
                    type=absence_type,
                    defaults={
                        'status': status,
                        'reason': reason,
                        'classroom': classroom,
                    },
                )
                count += 1
        messages.success(request, f"{count} absence(s) enregistrée(s) pour le {selected_date}.")
        return redirect(f"{request.path}?date={selected_date}")

    # Absences déjà notées ce jour
    existing = {
        a.student_id: a
        for a in Absence.objects.filter(classroom=classroom, date=selected_date)
    }
    rows = []
    for s in students:
        a = existing.get(s.id)
        rows.append({'student': s, 'absence': a, 'is_absent': a is not None})

    return render(request, 'attendance/class_attendance.html', {
        'classroom': classroom,
        'rows': rows,
        'selected_date': selected_date,
        'type_choices': Absence.TYPE_CHOICES,
        'status_choices': Absence.STATUS_CHOICES,
    })


@permission_required('attendance.take')
@login_required
@_students_use_portal
def scan_qr(request):
    """Page pointeuse QR — style SiraScol."""
    from datetime import date
    from django.db.models import Count, Q
    from .models import AttendancePunch

    today = date.today()
    tab = request.GET.get('tab', 'personnel')  # personnel | eleves
    punches = AttendancePunch.objects.filter(date=today)
    if tab == 'eleves':
        punches = punches.filter(kind='eleve')
    else:
        punches = punches.filter(kind='personnel')

    n_arrivee = punches.filter(action='arrivee').count()
    n_depart = punches.filter(action='depart').count()
    # présents = personnes avec au moins une arrivée sans départ après (approx: arrivee count - depart)
    person_keys = set()
    for p in punches.filter(action='arrivee'):
        key = ('s', p.student_id) if p.student_id else ('t', p.teacher_id)
        person_keys.add(key)
    for p in punches.filter(action='depart'):
        key = ('s', p.student_id) if p.student_id else ('t', p.teacher_id)
        person_keys.discard(key)
    n_present = len(person_keys)
    n_total = punches.values('student_id', 'teacher_id').distinct().count()

    recent_qs = punches.select_related(
        'student', 'student__user', 'teacher', 'teacher__user', 'recorded_by'
    ).order_by('-id')[:12]
    recent = []
    for punch in recent_qs:
        if punch.student_id and punch.student:
            name = f"{punch.student.first_name} {punch.student.last_name}".strip()
            code = punch.student.matricule
        elif punch.teacher_id and punch.teacher:
            name = f"{punch.teacher.first_name} {punch.teacher.last_name}".strip() or punch.teacher.matricule
            code = punch.teacher.matricule
        else:
            name, code = '—', '—'
        recent.append({'punch': punch, 'name': name, 'code': code})

    return render(request, 'attendance/scan_qr.html', {
        'tab': tab,
        'today': today,
        'stats': {
            'total': n_total,
            'presents': n_present,
            'arrivees': n_arrivee,
            'departs': n_depart,
        },
        'recent': recent,
    })


@permission_required('attendance.take')
@login_required
def scan_manual(request):
    """Formulaire de saisie manuelle du matricule, affiché en modale."""
    return render(request, 'attendance/scan_manual_modal.html')


@permission_required('attendance.take')
@login_required
def scan_camera_help(request):
    """Aide à la caméra, affichée en modale."""
    return render(request, 'attendance/scan_camera_help_modal.html')


@permission_required('attendance.view')
@login_required
def scan_punch_detail(request, pk):
    """Détail d'un pointage, affiché en modale."""
    from .models import AttendancePunch
    punch = get_object_or_404(AttendancePunch, pk=pk)
    person = punch.student or punch.teacher
    person_name = (
        f"{person.first_name} {person.last_name}" if person else ''
    ).strip()
    return render(request, 'attendance/scan_punch_detail_modal.html', {
        'punch': punch,
        'person': person,
        'person_name': person_name,
        'person_url_name': 'students:detail' if punch.student_id else 'teachers:detail',
    })


@permission_required('attendance.take')
@login_required
@_students_use_portal
def scan_qr_api(request):
    """POST JSON: code, action (arrivee|depart), kind (eleve|personnel)."""
    from datetime import date
    from django.http import JsonResponse
    from django.utils import timezone
    from django.db import IntegrityError
    from .models import AttendancePunch
    from students.models import Student
    from teachers.models import Teacher
    import json

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    try:
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body.decode('utf-8') or '{}')
        else:
            data = request.POST
        code = (data.get('code') or '').strip()
        action = (data.get('action') or 'arrivee').strip()
        kind = (data.get('kind') or 'eleve').strip()
        if action not in ('arrivee', 'depart'):
            action = 'arrivee'
        if not code:
            return JsonResponse({'ok': False, 'error': 'Code QR vide'}, status=400)

        # Formats acceptés: matricule, STU:matricule, TCH:matricule, id numérique
        student = None
        teacher = None
        raw = code
        if code.upper().startswith(('STU:', 'ELEVE:', 'STUDENT:')):
            code = code.split(':', 1)[1].strip()
            kind = 'eleve'
        elif code.upper().startswith(('TCH:', 'ENS:', 'PER:', 'ADM:', 'STAFF:', 'TEACHER:')):
            code = code.split(':', 1)[1].strip()
            kind = 'personnel'

        if kind == 'personnel':
            teacher = Teacher.objects.filter(matricule__iexact=code).first()
            if not teacher and '-' in code:
                # Codes de badge ADM-/PER-/ENS- : on retrouve le matricule
                # stocké par son suffixe, sans dépendre du préfixe affiché.
                suffix = code.split('-', 1)[1]
                teacher = Teacher.objects.filter(matricule__iendswith=f'-{suffix}').first()
            if not teacher and code.isdigit():
                teacher = Teacher.objects.filter(pk=int(code)).first()
            if not teacher:
                return JsonResponse({'ok': False, 'error': f'Personnel introuvable : {raw}'}, status=404)
            today = date.today()
            # Anti-doublon : même action le même jour
            already = AttendancePunch.objects.filter(
                kind='personnel', teacher=teacher, date=today, action=action
            ).exists()
            if already:
                label = 'Arrivée' if action == 'arrivee' else 'Départ'
                return JsonResponse({
                    'ok': False,
                    'error': f'{label} déjà enregistrée aujourd\'hui pour {teacher.last_name} {teacher.first_name}.',
                    'duplicate': True,
                }, status=409)
            # Arrivée obligatoire avant départ
            if action == 'depart' and not AttendancePunch.objects.filter(
                kind='personnel', teacher=teacher, date=today, action='arrivee'
            ).exists():
                return JsonResponse({
                    'ok': False,
                    'error': f'Pas d\'arrivée enregistrée aujourd\'hui pour {teacher.last_name} {teacher.first_name}.',
                }, status=400)
            try:
                punch = AttendancePunch.objects.create(
                    kind='personnel', action=action, teacher=teacher,
                    date=today, recorded_by=request.user,
                )
            except IntegrityError:
                return JsonResponse({
                    'ok': False, 'duplicate': True,
                    'error': f"Déjà pointé aujourd'hui ({'arrivée' if action=='arrivee' else 'départ'}).",
                }, status=409)
            photo = teacher.photo.url if teacher.photo else None
            return JsonResponse({
                'ok': True,
                'action': action,
                'action_label': 'Arrivée' if action == 'arrivee' else 'Départ',
                'time': timezone.localtime(punch.punched_at).strftime('%H:%M:%S'),
                'name': f'{teacher.first_name} {teacher.last_name}',
                'role': teacher.function or teacher.speciality or teacher.get_category_display(),
                'detail': teacher.department or teacher.get_category_display(),
                'code': teacher.matricule,
                'phone': teacher.phone or '—',
                'type': 'Personnel',
                'photo': photo,
                'person_id': teacher.pk,
                'profile_url': f"/enseignants/{teacher.pk}/",
                'message': f"{'Arrivée' if action == 'arrivee' else 'Départ'} enregistré",
            })
        else:
            student = Student.objects.filter(matricule__iexact=code).first()
            if not student and code.isdigit():
                student = Student.objects.filter(pk=int(code)).first()
            if not student:
                return JsonResponse({'ok': False, 'error': f'Élève introuvable : {raw}'}, status=404)
            today = date.today()
            already = AttendancePunch.objects.filter(
                kind='eleve', student=student, date=today, action=action
            ).exists()
            if already:
                label = 'Arrivée' if action == 'arrivee' else 'Départ'
                return JsonResponse({
                    'ok': False,
                    'error': f'{label} déjà enregistrée aujourd\'hui pour {student.last_name} {student.first_name}.',
                    'duplicate': True,
                }, status=409)
            if action == 'depart' and not AttendancePunch.objects.filter(
                kind='eleve', student=student, date=today, action='arrivee'
            ).exists():
                return JsonResponse({
                    'ok': False,
                    'error': f'Pas d\'arrivée enregistrée aujourd\'hui pour {student.last_name} {student.first_name}.',
                }, status=400)
            try:
                punch = AttendancePunch.objects.create(
                    kind='eleve', action=action, student=student,
                    date=today, recorded_by=request.user,
                )
            except IntegrityError:
                return JsonResponse({
                    'ok': False, 'duplicate': True,
                    'error': f"Déjà pointé aujourd'hui ({'arrivée' if action=='arrivee' else 'départ'}).",
                }, status=409)
            photo = student.photo.url if getattr(student, 'photo', None) else None
            return JsonResponse({
                'ok': True,
                'action': action,
                'action_label': 'Arrivée' if action == 'arrivee' else 'Départ',
                'time': timezone.localtime(punch.punched_at).strftime('%H:%M:%S'),
                'name': f'{student.first_name} {student.last_name}',
                'role': 'Élève',
                'detail': (
                    student.current_enrollment().classroom.name
                    if student.current_enrollment() else '—'
                ),
                'code': student.matricule,
                'phone': student.phone or '—',
                'type': 'Élève',
                'photo': photo,
                'person_id': student.pk,
                'profile_url': f"/eleves/{student.pk}/",
                'message': f"{'Arrivée' if action == 'arrivee' else 'Départ'} enregistré",
            })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@permission_required('attendance.view')
@login_required
@_students_use_portal
def absence_list_pdf(request):
    from core.list_pdf import build_list_pdf
    from core.models import SchoolSettings
    from attendance.models import Absence
    from core.year_context import get_selected_year

    school = SchoolSettings.get_solo()
    year = get_selected_year(request)
    qs = Absence.objects.select_related('student').order_by('-date')
    # optional filters from GET
    period = request.GET.get('period') or ''
    status = request.GET.get('status') or ''
    kind = request.GET.get('kind') or request.GET.get('type') or ''
    q = (request.GET.get('q') or '').strip()
    today = date.today()
    if period == 'today':
        qs = qs.filter(date=today)
    elif period == 'week':
        qs = qs.filter(date__gte=today - timedelta(days=7))
    elif period == 'month':
        qs = qs.filter(date__gte=today.replace(day=1))
    if status:
        qs = qs.filter(status=status)
    if kind:
        qs = qs.filter(type=kind)
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q) | Q(student__first_name__icontains=q) | Q(student__matricule__icontains=q)
        )
    rows = []
    for a in qs[:500]:
        rows.append([
            a.date.strftime('%d/%m/%Y') if a.date else '—',
            f"{a.student.last_name} {a.student.first_name}" if a.student_id else '—',
            getattr(a.student, 'matricule', '') or '—',
            a.get_type_display() if hasattr(a, 'get_type_display') else (a.type or '—'),
            a.get_status_display() if hasattr(a, 'get_status_display') else (a.status or '—'),
        ])
    school_name = getattr(school, 'name', None) or 'Établissement'
    year_name = year.name if year else ''
    return build_list_pdf(
        title=school_name,
        subtitle=f"Liste des absences{' — ' + year_name if year_name else ''} · {len(rows)} ligne(s)",
        headers=['Date', 'Élève', 'Matricule', 'Type', 'Statut'],
        rows=rows,
        filename='liste_absences.pdf',
    )
