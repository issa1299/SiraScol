from functools import wraps

from core.year_context import get_selected_year

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Assessment, Grade
from .forms import AssessmentForm, level_is_primary, level_cycle_code
from core.permissions import (
    get_role, get_teacher_classrooms, get_parent_students, is_staff_role,
    can, permission_required,
)
from academics.models import ClassRoom, Subject, AcademicYear
from students.models import Enrollment, Student


def _teacher_can_classroom(user, classroom):
    """Seuls les utilisateurs autorisés à saisir des notes peuvent modifier une classe.

    Les enseignants sont en plus limités à leurs propres affectations. Les
    parents, élèves, comptables, secrétaires et surveillants sont refusés.
    """
    if not can(user, 'grades.entry'):
        return False
    if user.is_superuser or get_role(user) == 'directeur':
        return True
    if get_role(user) != 'enseignant':
        return False
    ids = set(get_teacher_classrooms(user).values_list('id', flat=True))
    return classroom.id in ids


def _deny_classroom(request):
    messages.error(request, "Cette classe ne fait pas partie de vos affectations.")
    return redirect('grades:classes')


def _students_use_portal(view_func):
    """Les élèves utilisent exclusivement leur espace dédié, pas l'interface de gestion."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_role(request.user) == 'eleve' and not request.user.is_superuser:
            return redirect('eleve:notes')
        return view_func(request, *args, **kwargs)
    return _wrapped


@login_required
@_students_use_portal
def grades_classes(request):
    """Saisie : 1er cycle | 2ème cycle | Lycée → classes → élèves + périodes."""
    from .forms import level_is_primary, level_cycle_code
    from .models import Period

    year = get_selected_year(request)
    cycle_filter = request.GET.get('cycle', '')  # primaire | secondaire
    classroom_id = request.GET.get('classroom', '')
    section = 'saisie'

    qs = ClassRoom.objects.select_related('level__cycle', 'academic_year', 'main_teacher')
    if year:
        qs = qs.filter(academic_year=year)
    qs = qs.annotate(
        nb_eleves=Count('enrollments', filter=Q(enrollments__is_active=True)),
        nb_evals=Count('assessments'),
    ).order_by('level__cycle__order', 'level__order', 'name')

    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        qs = qs.filter(id__in=get_teacher_classrooms(request.user).values_list('id', flat=True))
    elif role == 'parent':
        child_ids = get_parent_students(request.user).values_list('id', flat=True)
        class_ids = Enrollment.objects.filter(
            student_id__in=child_ids, is_active=True
        ).values_list('classroom_id', flat=True)
        qs = qs.filter(id__in=class_ids)

    primaire_classes = []
    secondaire_classes = []
    lycee_classes = []
    for c in qs:
        code = level_cycle_code(c.level)
        if code == 'primaire':
            primaire_classes.append(c)
        elif code == 'lycee':
            lycee_classes.append(c)
        else:
            secondaire_classes.append(c)

    classrooms = []
    is_primary_cycle = None
    if cycle_filter in ('primaire', 'pri'):
        classrooms = primaire_classes
        is_primary_cycle = True
    elif cycle_filter in ('secondaire', 'sec'):
        classrooms = secondaire_classes
        is_primary_cycle = False
    elif cycle_filter in ('lycee', 'lyc'):
        classrooms = lycee_classes
        is_primary_cycle = False

    periods = []
    if year and is_primary_cycle is not None:
        ptype = 'mois' if is_primary_cycle else 'trimestre'
        periods = list(Period.objects.filter(
            academic_year=year, period_type=ptype, is_active=True
        ).order_by('order'))
        if not periods:
            periods = list(Period.objects.filter(academic_year=year, is_active=True).order_by('order'))

    classroom = None
    students = []
    if classroom_id:
        classroom = get_object_or_404(
            ClassRoom.objects.select_related('level__cycle'), pk=classroom_id
        )
        if not _teacher_can_classroom(request.user, classroom):
            return _deny_classroom(request)
        from django.urls import reverse
        return redirect(reverse('grades:saisie_classe') + f'?classroom={classroom.id}')

    ctx = {
        'primaire_classes': primaire_classes,
        'secondaire_classes': secondaire_classes,
        'lycee_classes': lycee_classes,
        'classrooms': classrooms,
        'cycle_filter': cycle_filter,
        'is_primary_cycle': is_primary_cycle,
        'classroom': classroom,
        'classroom_id': str(classroom_id) if classroom_id else '',
        'students': students,
        'periods': periods,
        'current_year': year,
        'section': section,
        'nb_primaire': len(primaire_classes),
        'nb_secondaire': len(secondaire_classes),
        'nb_lycee': len(lycee_classes),
        'nb_eleves_pri': sum(getattr(c, 'nb_eleves', 0) for c in primaire_classes),
        'nb_eleves_sec': sum(getattr(c, 'nb_eleves', 0) for c in secondaire_classes),
        'nb_eleves_lyc': sum(getattr(c, 'nb_eleves', 0) for c in lycee_classes),
    }
    # Enseignant : interface notes dédiée (pas le centre des cotes admin)
    if role == 'enseignant' and not request.user.is_superuser:
        return render(request, 'grades/teacher_notes.html', ctx)
    return render(request, 'grades/cotes_hub.html', ctx)





@permission_required('grades.entry')
@login_required
@_students_use_portal
def saisie_classe(request):
    """
    Saisie collective : classe → période (mois/trimestre) + matière en haut,
    liste de tous les élèves avec champs de notes en bas.
    """
    from .forms import level_is_primary
    from .models import Period, Assessment, AssessmentType, Grade
    from academics.models import Subject, ClassSubject, SubjectAssignment
    from core.permissions import get_linked_teacher
    from decimal import Decimal, InvalidOperation

    classroom_id = request.GET.get('classroom') or request.POST.get('classroom')
    period_id = request.GET.get('period') or request.POST.get('period')
    subject_id = request.GET.get('subject') or request.POST.get('subject')

    if not classroom_id:
        messages.error(request, 'Choisissez une classe.')
        return redirect('grades:classes')

    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level__cycle', 'academic_year'),
        pk=classroom_id,
    )
    if not _teacher_can_classroom(request.user, classroom):
        return _deny_classroom(request)

    is_primary = level_is_primary(classroom.level)
    max_score = Decimal('10') if is_primary else Decimal('20')
    year = get_selected_year(request) or classroom.academic_year
    if year is None:
        year = AcademicYear.objects.filter(is_current=True).first()
        if year is None:
            year = AcademicYear.objects.order_by('-id').first()

    from datetime import date as _date

    def _ensure_periods(yr, primary):
        if not yr:
            return []
        ptype = 'mois' if primary else 'trimestre'
        d0 = getattr(yr, 'start_date', None) or _date(2026, 9, 1)
        d1 = getattr(yr, 'end_date', None) or _date(2027, 6, 30)

        def _list(ptype_filter=None):
            qs = Period.objects.filter(academic_year=yr)
            if ptype_filter:
                qs = qs.filter(period_type=ptype_filter)
            return list(qs.order_by('order', 'id'))

        periods_list = _list(ptype)
        if not periods_list:
            periods_list = _list(None)

        if not periods_list:
            specs = (
                [
                    ('Septembre', 1), ('Octobre', 2), ('Novembre', 3), ('Décembre', 4),
                    ('Janvier', 5), ('Février', 6), ('Mars', 7), ('Avril', 8),
                    ('Mai', 9), ('Juin', 10),
                ]
                if primary else
                [('1er trimestre', 1), ('2ème trimestre', 2), ('3ème trimestre', 3)]
            )
            for name, order in specs:
                try:
                    obj, created = Period.objects.get_or_create(
                        academic_year=yr,
                        name=name,
                        defaults={
                            'period_type': ptype,
                            'order': order,
                            'is_active': True,
                            'start_date': d0,
                            'end_date': d1,
                        },
                    )
                    if not created:
                        # Réactiver / corriger le type
                        changed = False
                        if obj.period_type != ptype:
                            obj.period_type = ptype
                            changed = True
                        if not obj.is_active:
                            obj.is_active = True
                            changed = True
                        if changed:
                            obj.save()
                except Exception:
                    continue
            periods_list = _list(ptype) or _list(None)

        # Afficher même si is_active=False
        return periods_list

    periods = _ensure_periods(year, is_primary)
    # Filet de sécurité : toutes les périodes de l'année, tous types
    if not periods and year:
        periods = list(Period.objects.filter(academic_year=year).order_by('order', 'id'))
    if not periods:
        periods = list(Period.objects.all().order_by('-academic_year_id', 'order')[:12])


    # Matières : programme classe, sinon catalogue, sinon créer un set minimal
    cs_qs = ClassSubject.objects.filter(classroom=classroom).select_related('subject')
    subjects = [cs.subject for cs in cs_qs if cs.subject_id]
    subjects_from_class = bool(subjects)
    if not subjects:
        subjects = list(Subject.objects.filter(is_active=True).order_by('name'))
    if not subjects:
        defaults = [
            ('Français', 'FR', 3),
            ('Mathématiques', 'MATH', 3),
            ('Anglais', 'ANG', 2),
            ('Sciences', 'SCI', 2),
            ('Histoire-Géo', 'HG', 2),
            ('Éducation civique', 'EC', 1),
        ]
        for name, code, coef in defaults:
            Subject.objects.get_or_create(
                code=code,
                defaults={'name': name, 'coefficient': coef, 'is_active': True},
            )
        subjects = list(Subject.objects.filter(is_active=True).order_by('name'))

    # Enseignant : seulement ses matières affectées
    role = get_role(request.user)
    teacher = get_linked_teacher(request.user)
    if role == 'enseignant' and teacher and not request.user.is_superuser:
        allowed_ids = set(
            SubjectAssignment.objects.filter(
                teacher=teacher, classroom=classroom
            ).values_list('subject_id', flat=True)
        )
        # 1er cycle + prof principal : toutes les matières de la classe
        if classroom.main_teacher_id == teacher.id:
            pass  # keep all class subjects
        elif allowed_ids:
            subjects = [s for s in subjects if s.id in allowed_ids]

    period = get_object_or_404(Period, pk=period_id) if period_id else None
    subject = get_object_or_404(Subject, pk=subject_id) if subject_id else None

    students = [
        e.student for e in Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student').order_by('student__last_name', 'student__first_name')
    ]

    type_compo, _ = AssessmentType.objects.get_or_create(
        code='composition',
        defaults={'name': 'Composition', 'weight': 2, 'description': 'Composition / examen'},
    )
    type_devoir, _ = AssessmentType.objects.get_or_create(
        code='devoir',
        defaults={'name': 'Devoir', 'weight': 1, 'description': 'Devoirs / interrogations'},
    )

    def _auto_apprec(score, mx):
        try:
            s = float(score)
            m = float(mx) or 20
            pct = (s / m) * 20 if m else 0
        except Exception:
            return ''
        if pct >= 16: return 'Très bien'
        if pct >= 14: return 'Bien'
        if pct >= 12: return 'Assez bien'
        if pct >= 10: return 'Passable'
        if pct >= 8: return 'Insuffisant'
        return 'Faible'

    def get_or_create_assessment(subj, atype, label):
        atype = atype or type_compo
        existing = Assessment.objects.filter(
            classroom=classroom, subject=subj, period=period, assessment_type=atype,
        ).first()
        if existing:
            return existing
        title = f'{atype.name} — {subj.name} — {period.name}'
        return Assessment.objects.create(
            classroom=classroom,
            subject=subj,
            period=period,
            assessment_type=atype,
            title=title[:150],
            date=period.end_date or period.start_date or timezone.now().date(),
            max_score=max_score,
            coefficient=getattr(subj, 'coefficient', 1) or 1,
        )

    # POST save
    if request.method == 'POST' and period and subject:
        n = 0
        if is_primary:
            assess = get_or_create_assessment(subject, type_compo, 'Composition')
            for st in students:
                raw = request.POST.get(f'score_{st.id}', '').strip()
                if raw == '':
                    continue
                try:
                    score = Decimal(raw.replace(',', '.'))
                except InvalidOperation:
                    continue
                sc = min(score, max_score)
                Grade.objects.update_or_create(
                    assessment=assess, student=st,
                    defaults={
                        'score': sc,
                        'is_absent': False,
                        'appreciation': _auto_apprec(sc, max_score),
                    },
                )
                n += 1
        else:
            # Devoirs D1 D2 D3 → note de classe (moyenne) + Composition
            assess_d = get_or_create_assessment(subject, type_devoir, 'Devoirs')
            assess_c = get_or_create_assessment(subject, type_compo, 'Composition')
            for st in students:
                d_scores = []
                for i in (1, 2, 3):
                    raw = request.POST.get(f'devoir{i}_{st.id}', '').strip()
                    if raw == '':
                        continue
                    try:
                        d_scores.append(Decimal(raw.replace(',', '.')))
                    except InvalidOperation:
                        continue
                if d_scores:
                    note_classe = sum(d_scores) / len(d_scores)
                    detail = ' | '.join(f'D{i+1}={s}' for i, s in enumerate(d_scores))
                    Grade.objects.update_or_create(
                        assessment=assess_d, student=st,
                        defaults={
                            'score': min(note_classe, max_score),
                            'is_absent': False,
                            'appreciation': f'Devoirs: {detail}',
                        },
                    )
                    n += 1
                raw_co = request.POST.get(f'compo_{st.id}', '').strip()
                if raw_co != '':
                    try:
                        score = Decimal(raw_co.replace(',', '.'))
                        sc = min(score, max_score)
                        Grade.objects.update_or_create(
                            assessment=assess_c, student=st,
                            defaults={
                                'score': sc,
                                'is_absent': False,
                                'appreciation': _auto_apprec(sc, max_score),
                            },
                        )
                        n += 1
                    except InvalidOperation:
                        pass
        messages.success(request, f'{n} note(s) enregistrée(s) — {subject.name} · {period.name}.')
        return redirect(
            f"{request.path}?classroom={classroom.id}&period={period.id}&subject={subject.id}"
        )

    # Existing grades for display
    rows = []
    if period and subject:
        if is_primary:
            assess = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period,
                assessment_type=type_compo,
            ).first()
            if not assess:
                assess = Assessment.objects.filter(
                    classroom=classroom, subject=subject, period=period,
                ).order_by('-id').first()
            gmap = {}
            if assess:
                gmap = {
                    g.student_id: g
                    for g in Grade.objects.filter(assessment=assess)
                }
            if not gmap:
                for g in Grade.objects.filter(
                    assessment__classroom=classroom,
                    assessment__subject=subject,
                    assessment__period=period,
                ):
                    gmap[g.student_id] = g
            for st in students:
                g = gmap.get(st.id)
                rows.append({
                    'student': st,
                    'score': g.score if g and g.score is not None else '',
                })
        else:
            import re as _re
            assess_d = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period,
                assessment_type=type_devoir,
            ).order_by('-id').first()
            assess_c = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period,
                assessment_type=type_compo,
            ).order_by('-id').first()
            if not assess_c:
                assess_c = Assessment.objects.filter(
                    classroom=classroom, subject=subject, period=period,
                ).exclude(assessment_type=type_devoir).order_by('-id').first()
            gmap_d = {
                g.student_id: g for g in Grade.objects.filter(assessment=assess_d)
            } if assess_d else {}
            gmap_c = {
                g.student_id: g for g in Grade.objects.filter(assessment=assess_c)
            } if assess_c else {}
            for st in students:
                gd, gc = gmap_d.get(st.id), gmap_c.get(st.id)
                devoirs = ['', '', '']
                if gd and gd.appreciation and 'Devoirs:' in (gd.appreciation or ''):
                    found = _re.findall(r'D(\d+)=([0-9.]+)', gd.appreciation)
                    for num, val in found:
                        idx = int(num) - 1
                        if 0 <= idx < 3:
                            devoirs[idx] = val
                elif gd and gd.score is not None:
                    devoirs[0] = str(gd.score)
                rows.append({
                    'student': st,
                    'devoir1': devoirs[0],
                    'devoir2': devoirs[1],
                    'devoir3': devoirs[2],
                    'note_classe': gd.score if gd else '',
                    'composition': gc.score if gc else '',
                })

    role = get_role(request.user)
    is_teacher_ui = role == 'enseignant' and not request.user.is_superuser
    # Rester dans le centre des cotes pour admin / direction
    tpl = 'grades/saisie_classe.html'
    section = 'saisie'
    return render(request, tpl, {
        'classroom': classroom,
        'periods': periods,
        'subjects': subjects,
        'period': period,
        'subject': subject,
        'period_id': str(period_id) if period_id else '',
        'subject_id': str(subject_id) if subject_id else '',
        'students': students,
        'rows': rows,
        'is_primary': is_primary,
        'max_score': max_score,
        'is_teacher_ui': is_teacher_ui,
        'subjects_from_class': subjects_from_class,
        'year': year,
        'section': section,
        'period_choices': [(p.id, p.name) for p in periods],
        'subject_choices': [(s.id, s.name) for s in subjects],
        'nb_periods': len(periods),
        'nb_subjects': len(subjects),
    })


@permission_required('grades.entry')
@login_required
@_students_use_portal
def saisie_eleve(request):
    """Saisie des notes d'un élève pour une période (interface type SiraScol)."""
    from .forms import level_is_primary
    from .models import Period, Assessment, AssessmentType, Grade
    from academics.models import Subject, ClassSubject
    from decimal import Decimal, InvalidOperation

    classroom_id = request.GET.get('classroom') or request.POST.get('classroom')
    student_id = request.GET.get('student') or request.POST.get('student')
    period_id = request.GET.get('period') or request.POST.get('period')
    if not (classroom_id and student_id and period_id):
        messages.error(request, 'Classe, élève et période sont obligatoires.')
        return redirect('grades:classes')

    classroom = get_object_or_404(ClassRoom.objects.select_related('level__cycle'), pk=classroom_id)
    if not _teacher_can_classroom(request.user, classroom):
        return _deny_classroom(request)
    student = get_object_or_404(
        Student,
        pk=student_id,
        enrollments__classroom=classroom,
        enrollments__is_active=True,
    )
    period = get_object_or_404(Period, pk=period_id)
    is_primary = level_is_primary(classroom.level)
    max_score = Decimal('10') if is_primary else Decimal('20')

    # Matières de la classe
    subjects = []
    cs = ClassSubject.objects.filter(classroom=classroom).select_related('subject').order_by('subject__name')
    if cs.exists():
        subjects = [x.subject for x in cs]
    else:
        subjects = list(Subject.objects.filter(is_active=True).order_by('name')[:20])

    # Types: devoir + composition pour sec, composition pour primaire
    type_devoir = AssessmentType.objects.filter(code='devoir').first()
    type_compo = AssessmentType.objects.filter(code__in=['composition', 'trimestre', 'examen']).first()
    if not type_compo:
        type_compo = AssessmentType.objects.first()
    if not type_devoir:
        type_devoir = type_compo

    def get_or_create_assessment(subject, atype, title_suffix):
        title = f'{atype.name if atype else "Éval"} — {subject.name} — {period.name}'
        obj, _ = Assessment.objects.get_or_create(
            classroom=classroom,
            subject=subject,
            period=period,
            assessment_type=atype or type_compo,
            defaults={
                'title': title[:150],
                'date': period.end_date or period.start_date,
                'max_score': max_score,
                'coefficient': subject.coefficient if hasattr(subject, 'coefficient') else 1,
            },
        )
        return obj

    if request.method == 'POST':
        for subject in subjects:
            if is_primary:
                raw = request.POST.get(f'score_{subject.id}', '').strip()
                if raw == '':
                    continue
                try:
                    score = Decimal(raw.replace(',', '.'))
                except InvalidOperation:
                    continue
                assess = get_or_create_assessment(subject, type_compo, 'Composition')
                Grade.objects.update_or_create(
                    assessment=assess, student=student,
                    defaults={'score': min(score, max_score), 'is_absent': False, 'appreciation': ''},
                )
            else:
                # Devoirs → Note de classe (moyenne) + Composition
                d_scores = []
                for n in (1, 2, 3):
                    raw = request.POST.get(f'score_{subject.id}_devoir{n}', '').strip()
                    if raw == '':
                        continue
                    try:
                        d_scores.append(Decimal(raw.replace(',', '.')))
                    except InvalidOperation:
                        continue
                if d_scores:
                    note_classe = sum(d_scores) / len(d_scores)
                    assess = get_or_create_assessment(subject, type_devoir, 'Devoirs')
                    # Stocker les devoirs individuels dans appreciation pour relecture
                    detail = ' | '.join(f'D{i+1}={s}' for i, s in enumerate(d_scores))
                    Grade.objects.update_or_create(
                        assessment=assess, student=student,
                        defaults={
                            'score': min(note_classe, max_score),
                            'is_absent': False,
                            'appreciation': f'Devoirs: {detail}',
                        },
                    )
                raw_c = request.POST.get(f'score_{subject.id}_compo', '').strip()
                if raw_c != '':
                    try:
                        score_c = Decimal(raw_c.replace(',', '.'))
                    except InvalidOperation:
                        score_c = None
                    if score_c is not None:
                        assess = get_or_create_assessment(subject, type_compo, 'Composition')
                        Grade.objects.update_or_create(
                            assessment=assess, student=student,
                            defaults={'score': min(score_c, max_score), 'is_absent': False, 'appreciation': ''},
                        )
        messages.success(request, f'Notes enregistrées pour {student}.')
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.GET.get('modal') == '1'
        )
        if is_ajax:
            from django.http import HttpResponse
            body = (
                '<p class="text-emerald-700 text-sm font-semibold p-4">'
                'OK Notes enregistrees pour ' + str(student) + '.</p>'
                '<script>setTimeout(function(){try{closeModal("modal-dynamic")}catch(e){}},800);</script>'
            )
            return HttpResponse(body)
        return redirect(
            f"{request.path}?classroom={classroom.id}&student={student.id}&period={period.id}"
        )

    # Load existing grades
    # Load existing grades
    rows = []
    for subject in subjects:
        if is_primary:
            assess = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period
            ).first()
            grade = Grade.objects.filter(assessment=assess, student=student).first() if assess else None
            rows.append({
                'subject': subject,
                'score': grade.score if grade else '',
                'coef': getattr(subject, 'coefficient', 1),
            })
        else:
            assess_c = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period,
                assessment_type=type_devoir,
            ).first()
            assess_x = Assessment.objects.filter(
                classroom=classroom, subject=subject, period=period,
                assessment_type=type_compo,
            ).first()
            if not assess_x:
                assess_x = Assessment.objects.filter(
                    classroom=classroom, subject=subject, period=period
                ).exclude(assessment_type=type_devoir).first()
            g_c = Grade.objects.filter(assessment=assess_c, student=student).first() if assess_c else None
            g_x = Grade.objects.filter(assessment=assess_x, student=student).first() if assess_x else None
            nc = float(g_c.score) if g_c else None
            nx = float(g_x.score) if g_x else None
            moy = None
            if nc is not None and nx is not None:
                moy = round((nc + 2 * nx) / 3, 2)
            elif nx is not None:
                moy = nx
            elif nc is not None:
                moy = nc
            # Reprise des devoirs individuels depuis appreciation "Devoirs: D1=12 | D2=14"
            devoirs = ['', '', '']
            if g_c and g_c.appreciation and 'Devoirs:' in g_c.appreciation:
                import re as _re
                found = _re.findall(r'D(\d+)=([0-9.]+)', g_c.appreciation)
                for num, val in found:
                    idx = int(num) - 1
                    if 0 <= idx < 3:
                        devoirs[idx] = val
            elif g_c and nc is not None:
                devoirs[0] = str(g_c.score)
            rows.append({
                'subject': subject,
                'devoir1': devoirs[0],
                'devoir2': devoirs[1],
                'devoir3': devoirs[2],
                'note_classe': g_c.score if g_c else '',
                'composition': g_x.score if g_x else '',
                'moyenne': moy,
                'coef': getattr(subject, 'coefficient', 1),
            })

    # All periods for tabs
    year = period.academic_year
    if is_primary:
        all_periods = Period.objects.filter(academic_year=year, period_type='mois', is_active=True).order_by('order')
    else:
        all_periods = Period.objects.filter(academic_year=year, period_type='trimestre', is_active=True).order_by('order')
    if not all_periods.exists():
        all_periods = Period.objects.filter(academic_year=year, is_active=True).order_by('order')

    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    role = get_role(request.user)
    ctx = {
        'classroom': classroom,
        'student': student,
        'period': period,
        'periods': all_periods,
        'rows': rows,
        'is_primary': is_primary,
        'max_score': max_score,
        'current_year': year,
        'is_modal': is_modal,
        'is_teacher_ui': role == 'enseignant',
        'section': 'saisie',
        'form_action': request.path + f'?classroom={classroom.id}&student={student.id}&period={period.id}' + ('&modal=1' if is_modal else ''),
    }
    if is_modal:
        return render(request, 'grades/saisie_eleve_modal.html', ctx)
    return render(request, 'grades/saisie_eleve.html', ctx)


@login_required
@_students_use_portal
def class_assessments(request, classroom_id):
    """Évaluations d'une classe + création adaptée."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level__cycle', 'academic_year'),
        pk=classroom_id,
    )
    if not _teacher_can_classroom(request.user, classroom):
        return _deny_classroom(request)
    is_primary = level_is_primary(classroom.level)
    assessments = (
        Assessment.objects.filter(classroom=classroom)
        .select_related('subject', 'assessment_type', 'period', 'teacher')
        .order_by('-date')
    )
    form = AssessmentForm(
        classroom=classroom,
        is_primary=is_primary,
        initial={
            'date': timezone.now().date(),
            'classroom': classroom.pk,
            'max_score': 10 if is_primary else 20,
            'coefficient': 1,
        },
    )
    return render(request, 'grades/class_assessments.html', {
        'classroom': classroom,
        'assessments': assessments,
        'is_primary': is_primary,
        'form': form,
        'mode_label': '1er cycle — notes /10' if is_primary else ('Lycée — notes /20' if level_cycle_code(getattr(classroom, 'level', None)) == 'lycee' else '2ème cycle — notes /20'),
        'current_year': get_selected_year(request),
        'section': 'saisie',
    })


@login_required
@_students_use_portal
def assessment_list(request):
    """Redirige vers la vue par classes."""
    return redirect('grades:classes')


@permission_required('grades.entry')
@login_required
@_students_use_portal
def assessment_create(request):
    classroom_id = request.GET.get('classroom') or request.POST.get('classroom')
    classroom = None
    is_primary = None
    if classroom_id:
        classroom = get_object_or_404(
            ClassRoom.objects.select_related('level'), pk=classroom_id
        )
        is_primary = level_is_primary(classroom.level)

    if request.method == 'POST':
        form = AssessmentForm(request.POST, classroom=classroom, is_primary=is_primary)
        if form.is_valid():
            assessment = form.save()
            messages.success(request, f"Évaluation « {assessment.title} » créée. Saisissez les notes.")
            return redirect('grades:entry', pk=assessment.pk)
    else:
        form = AssessmentForm(
            classroom=classroom,
            is_primary=is_primary,
            initial={
                'date': timezone.now().date(),
                'max_score': 10 if is_primary else 20,
                'coefficient': 1,
                'classroom': classroom.pk if classroom else None,
            },
        )

    ctx = {
        'form': form,
        'title': 'Nouvelle évaluation',
        'classroom': classroom,
        'is_primary': is_primary if is_primary is not None else getattr(form, 'is_primary', False),
        'form_action': request.path + (f'?classroom={classroom.pk}' if classroom else ''),
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'grades/assessment_form_modal.html', ctx)
    return render(request, 'grades/assessment_form.html', ctx)


@permission_required('grades.entry')
@login_required
@_students_use_portal
def grade_entry(request, pk):
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            'classroom', 'classroom__level', 'subject', 'assessment_type', 'period'
        ),
        pk=pk,
    )
    if not _teacher_can_classroom(request.user, assessment.classroom):
        return _deny_classroom(request)
    if (
        get_role(request.user) == 'enseignant'
        and not request.user.is_superuser
        and Grade.objects.filter(assessment=assessment, is_validated=True).exists()
    ):
        messages.error(request, "Cette évaluation est déjà validée : modification refusée.")
        return redirect('grades:list')
    enrollments = (
        Enrollment.objects.filter(classroom=assessment.classroom, is_active=True)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )
    students = [e.student for e in enrollments]
    existing = {
        g.student_id: g
        for g in Grade.objects.filter(assessment=assessment)
    }
    is_primary = level_is_primary(assessment.classroom.level)
    max_score = assessment.max_score or (10 if is_primary else 20)

    def auto_appreciation(score, absent=False):
        if absent:
            return 'Absent'
        if score is None:
            return ''
        try:
            s = float(score)
        except (TypeError, ValueError):
            return ''
        # Échelles adaptées /10 (primaire) ou /20 (secondaire)
        if float(max_score) <= 10:
            if s >= 9:
                return 'Excellent'
            if s >= 8:
                return 'Très bien'
            if s >= 7:
                return 'Bien'
            if s >= 6:
                return 'Assez bien'
            if s >= 5:
                return 'Passable'
            if s >= 4:
                return 'Insuffisant'
            return 'Très insuffisant'
        else:
            if s >= 16:
                return 'Excellent'
            if s >= 14:
                return 'Bien'
            if s >= 12:
                return 'Assez bien'
            if s >= 10:
                return 'Passable'
            if s >= 8:
                return 'Insuffisant'
            return 'Très insuffisant'

    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        saved = 0
        with transaction.atomic():
            for student in students:
                # Prendre la dernière valeur si plusieurs champs (sécurité)
                score_vals = request.POST.getlist(f'score_{student.id}')
                score_raw = ''
                for v in score_vals:
                    if v is not None and str(v).strip() != '':
                        score_raw = str(v).strip()
                absent = request.POST.get(f'absent_{student.id}') == 'on'

                if absent:
                    app = auto_appreciation(0, absent=True)
                    Grade.objects.update_or_create(
                        assessment=assessment,
                        student=student,
                        defaults={
                            'score': Decimal('0'),
                            'is_absent': True,
                            'appreciation': app,
                        },
                    )
                    saved += 1
                elif score_raw != '':
                    try:
                        score = Decimal(score_raw.replace(',', '.'))
                    except (InvalidOperation, ValueError):
                        continue
                    app = auto_appreciation(float(score))
                    Grade.objects.update_or_create(
                        assessment=assessment,
                        student=student,
                        defaults={
                            'score': score,
                            'is_absent': False,
                            'appreciation': app,
                        },
                    )
                    saved += 1
        messages.success(
            request,
            f"{saved} note(s) enregistrée(s) pour « {assessment.title} »."
        )
        return redirect('grades:entry', pk=assessment.pk)

    # Recharger après POST
    existing = {
        g.student_id: g
        for g in Grade.objects.filter(assessment=assessment)
    }
    rows = []
    for s in students:
        g = existing.get(s.id)
        score_display = ''
        if g and not g.is_absent:
            # Afficher sans trop de décimales inutiles
            score_display = f'{g.score:.2f}'.rstrip('0').rstrip('.')
        rows.append({
            'student': s,
            'score': score_display,
            'is_absent': bool(g and g.is_absent),
            'appreciation': (g.appreciation if g else '') or '',
            'has_grade': g is not None,
        })

    return render(request, 'grades/grade_entry.html', {
        'assessment': assessment,
        'rows': rows,
        'is_primary': is_primary,
        'max_score': max_score,
        'section': 'saisie',
    })



def _cotes_classrooms(request, year=None):
    """Classes filtrées selon le rôle."""
    year = year or get_selected_year(request)
    qs = ClassRoom.objects.select_related('level__cycle', 'academic_year').annotate(
        nb_eleves=Count('enrollments', filter=Q(enrollments__is_active=True)),
    ).order_by('level__cycle__order', 'level__order', 'name')
    if year:
        qs = qs.filter(academic_year=year)
    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        qs = qs.filter(id__in=get_teacher_classrooms(request.user).values_list('id', flat=True))
    elif role == 'parent':
        child_ids = get_parent_students(request.user).values_list('id', flat=True)
        class_ids = Enrollment.objects.filter(
            student_id__in=child_ids, is_active=True
        ).values_list('classroom_id', flat=True)
        qs = qs.filter(id__in=class_ids)
    return qs, year


@login_required
@_students_use_portal
def cotes_liste_eleves(request):
    """Onglet Liste des élèves — tous les élèves avec classe et lien notes."""
    from students.models import Student
    qs, year = _cotes_classrooms(request)
    classroom_id = request.GET.get('classroom', '')
    q = request.GET.get('q', '').strip()
    enrollments = Enrollment.objects.filter(is_active=True).select_related(
        'student', 'classroom', 'classroom__level'
    )
    if year:
        enrollments = enrollments.filter(classroom__academic_year=year)
    if classroom_id:
        enrollments = enrollments.filter(classroom_id=classroom_id)
    else:
        enrollments = enrollments.filter(classroom_id__in=qs.values_list('id', flat=True))
    if q:
        enrollments = enrollments.filter(
            Q(student__last_name__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__matricule__icontains=q)
        )
    enrollments = enrollments.order_by('student__last_name', 'student__first_name')
    page = Paginator(enrollments, 40).get_page(request.GET.get('page'))
    return render(request, 'grades/cotes_liste.html', {
        'page': page,
        'classrooms': qs,
        'classroom_id': classroom_id,
        'q': q,
        'current_year': year,
        'section': 'liste',
    })


@permission_required('grades.entry')
@login_required
@_students_use_portal
def cotes_modifier(request):
    """Onglet Modifier les cotes — liste des évaluations récentes à modifier."""
    qs, year = _cotes_classrooms(request)
    assessments = (
        Assessment.objects.filter(classroom_id__in=qs.values_list('id', flat=True))
        .select_related('classroom', 'subject', 'period', 'assessment_type')
        .annotate(nb_notes=Count('grades'))
        .order_by('-date', '-id')
    )
    classroom_id = request.GET.get('classroom', '')
    if classroom_id:
        assessments = assessments.filter(classroom_id=classroom_id)
    page = Paginator(assessments, 30).get_page(request.GET.get('page'))
    return render(request, 'grades/cotes_modifier.html', {
        'page': page,
        'classrooms': qs,
        'classroom_id': classroom_id,
        'current_year': year,
        'section': 'modifier',
    })


@permission_required('grades.validate')
@login_required
@_students_use_portal
def cotes_valider(request):
    """Onglet Valider les cotes — évaluations avec notes saisies (aperçu validation)."""
    qs, year = _cotes_classrooms(request)
    assessments = (
        Assessment.objects.filter(classroom_id__in=qs.values_list('id', flat=True))
        .select_related('classroom', 'subject', 'period')
        .annotate(
            nb_notes=Count('grades', distinct=True),
            nb_eleves=Count(
                'classroom__enrollments',
                filter=Q(classroom__enrollments__is_active=True),
                distinct=True,
            ),
        )
        .filter(nb_notes__gt=0)
        .order_by('-date')
    )
    classroom_id = request.GET.get('classroom', '')
    if classroom_id:
        assessments = assessments.filter(classroom_id=classroom_id)
    page = Paginator(assessments, 30).get_page(request.GET.get('page'))
    return render(request, 'grades/cotes_valider.html', {
        'page': page,
        'classrooms': qs,
        'classroom_id': classroom_id,
        'current_year': year,
        'section': 'valider',
    })


@login_required
@_students_use_portal
def cotes_niveaux(request):
    """Onglet Niveau des élèves — effectifs et moyennes par classe."""
    from django.db.models import Avg
    qs, year = _cotes_classrooms(request)
    rows = []
    for c in qs:
        avg = Grade.objects.filter(
            assessment__classroom=c, is_absent=False
        ).aggregate(a=Avg('score'))['a']
        rows.append({
            'classroom': c,
            'nb_eleves': c.nb_eleves,
            'moyenne': round(float(avg), 2) if avg is not None else None,
            'nb_notes': Grade.objects.filter(assessment__classroom=c).count(),
        })
    return render(request, 'grades/cotes_niveaux.html', {
        'rows': rows,
        'current_year': year,
        'section': 'niveaux',
    })


@login_required
@_students_use_portal
def cotes_palmares(request):
    """Onglet Palmarès — classement des élèves par moyenne."""
    from django.db.models import Avg
    qs, year = _cotes_classrooms(request)
    classroom_id = request.GET.get('classroom', '')
    period_id = request.GET.get('period', '')
    from .models import Period
    periods = Period.objects.filter(academic_year=year).order_by('order') if year else Period.objects.none()

    ranking = []
    is_primary = False
    if classroom_id:
        from .forms import level_is_primary
        classroom = get_object_or_404(ClassRoom, pk=classroom_id)
        is_primary = level_is_primary(classroom.level)
        enrollments = Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student')
        for enr in enrollments:
            gqs = Grade.objects.filter(student=enr.student, is_absent=False, assessment__classroom=classroom)
            if period_id:
                gqs = gqs.filter(assessment__period_id=period_id)
            avg = gqs.aggregate(a=Avg('score'))['a']
            if avg is not None:
                ranking.append({
                    'student': enr.student,
                    'moyenne': round(float(avg), 2),
                    'nb': gqs.count(),
                })
        ranking.sort(key=lambda x: -x['moyenne'])
        for i, r in enumerate(ranking, 1):
            r['rang'] = i
    else:
        classroom = None

    return render(request, 'grades/cotes_palmares.html', {
        'classrooms': qs,
        'classroom_id': classroom_id,
        'classroom': classroom,
        'periods': periods,
        'period_id': period_id,
        'ranking': ranking,
        'current_year': year,
        'is_primary': is_primary,
        'section': 'palmares',
    })


@login_required
@_students_use_portal
def cotes_historique(request):
    """Onglet Historique — dernières notes saisies."""
    qs, year = _cotes_classrooms(request)
    grades = (
        Grade.objects.filter(assessment__classroom_id__in=qs.values_list('id', flat=True))
        .select_related('student', 'assessment', 'assessment__subject', 'assessment__classroom', 'assessment__period')
        .order_by('-updated_at')[:100]
    )
    return render(request, 'grades/cotes_historique.html', {
        'grades': grades,
        'current_year': year,
        'section': 'historique',
    })
