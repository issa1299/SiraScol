from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.db.models import Avg

from core.access import (
    filter_classrooms_for_user, get_classroom_for_user, get_student_for_user,
)
from core.permissions import get_role
from core.year_context import get_selected_year
from students.models import Student, Enrollment
from grades.models import Grade, Period
from academics.models import AcademicYear
from core.models import SchoolSettings


def _students_use_portal(view_func):
    """Les élèves consultent leurs bulletins depuis leur espace dédié."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_role(request.user) == 'eleve' and not request.user.is_superuser:
            return redirect('eleve:bulletins')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _q2(value):
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _normalize(score, max_score, out_of=20):
    if not max_score or max_score == 0:
        return Decimal('0')
    return (Decimal(str(score)) / Decimal(str(max_score))) * Decimal(str(out_of))


def _is_primary(student, academic_year=None):
    """
    PRIMAIRE (notes /10) : 1ère → 5ème année
    SECONDAIRE + LYCÉE (notes /20, devoir+comp) : 6ème → 12ème
    """
    from grades.forms import level_is_primary, level_cycle_code
    enr = None
    if academic_year:
        enr = student.enrollments.filter(
            academic_year=academic_year, is_active=True
        ).select_related('classroom__level__cycle').first()
    if not enr:
        enr = student.current_enrollment()
    if not enr:
        return True
    return level_is_primary(enr.classroom.level)


def _compute_grades_primary(student, period=None, academic_year=None):
    grades = Grade.objects.filter(student=student).select_related(
        'assessment__subject', 'assessment__assessment_type', 'assessment__period'
    )
    if period:
        grades = grades.filter(assessment__period=period)
    elif academic_year:
        grades = grades.filter(assessment__period__academic_year=academic_year)

    by_subject = defaultdict(list)
    for g in grades:
        if g.is_absent:
            continue
        by_subject[g.assessment.subject].append({
            'score': g.score,
            'max_score': g.assessment.max_score,
            'appreciation': g.appreciation,
        })

    results = []
    for subject, items in sorted(by_subject.items(), key=lambda x: x[0].name):
        total = Decimal('0')
        n = 0
        for it in items:
            total += _normalize(it['score'], it['max_score'], 10)
            n += 1
        avg = _q2(total / n) if n else None
        coef = subject.coefficient
        results.append({
            'subject': subject,
            'note_classe': None,
            'note_composition': None,
            'note_composition_40': None,
            'average': avg,
            'coefficient': coef,
            'moy_coef': _q2(Decimal(str(avg)) * coef) if avg is not None else None,
        })
    return results


def _compute_grades_secondary(student, period=None, academic_year=None, formula='comp40_plus_classe_div3'):
    """
    Modèle type école malienne (bulletin réel) :

      Note de classe  → sur 20  (moyenne des devoirs)
      Note composition → sur 40 (composition / examen de trimestre)
      Moyenne         → (NoteComp_40 + NoteClasse_20) / 3
                        = équivalent à (Comp_sur_20 × 2 + Classe) / 3

      Moy × Coef = Moyenne × Coefficient
    """
    grades = Grade.objects.filter(student=student).select_related(
        'assessment__subject', 'assessment__assessment_type', 'assessment__period'
    )
    if period:
        grades = grades.filter(assessment__period=period)
    elif academic_year:
        grades = grades.filter(assessment__period__academic_year=academic_year)

    by_subject = defaultdict(list)
    for g in grades:
        if g.is_absent:
            continue
        by_subject[g.assessment.subject].append({
            'score': g.score,
            'max_score': g.assessment.max_score,
            'type': g.assessment.assessment_type.name,
            'code': getattr(g.assessment.assessment_type, 'code', '') or '',
        })

    results = []
    for subject, items in sorted(by_subject.items(), key=lambda x: x[0].name):
        classe_20 = []
        comp_40 = []

        for it in items:
            code = (it.get('code') or '').lower()
            name = (it.get('type') or '').lower()
            score = Decimal(str(it['score']))
            max_s = Decimal(str(it['max_score'] or 20))

            is_classe = code in ('devoir', 'interrogation', 'classe') or any(
                k in name for k in ('devoir', 'interrogation', 'classe')
            )
            is_comp = code in ('composition', 'trimestre', 'examen') or any(
                k in name for k in ('composition', 'trimestre', 'examen')
            )

            if is_classe:
                classe_20.append(_normalize(score, max_s, 20))
            elif is_comp:
                # Composition affichée sur 40 (comme le bulletin papier)
                comp_40.append(_normalize(score, max_s, 40))
            else:
                classe_20.append(_normalize(score, max_s, 20))

        note_classe = _q2(sum(classe_20) / len(classe_20)) if classe_20 else None
        note_comp_40 = _q2(sum(comp_40) / len(comp_40)) if comp_40 else None

        average = None
        note_comp_20 = _q2(Decimal(str(note_comp_40)) / 2) if note_comp_40 is not None else None
        if note_classe is not None and note_comp_40 is not None:
            if formula == 'comp20_x2_plus_classe_div3':
                # (Composition_sur_20 × 2 + Note_classe) / 3
                average = _q2(
                    (Decimal(str(note_comp_20)) * 2 + Decimal(str(note_classe))) / Decimal('3')
                )
            else:
                # Mali: (NoteComp_40 + NoteClasse_20) / 3
                average = _q2(
                    (Decimal(str(note_comp_40)) + Decimal(str(note_classe))) / Decimal('3')
                )
        elif note_comp_40 is not None:
            average = note_comp_20
        elif note_classe is not None:
            average = note_classe

        coef = subject.coefficient
        moy_coef = _q2(Decimal(str(average)) * coef) if average is not None else None

        results.append({
            'subject': subject,
            'note_classe': note_classe,
            'note_composition_40': note_comp_40,
            'note_composition': _q2(Decimal(str(note_comp_40)) / 2) if note_comp_40 is not None else None,
            'average': average,
            'coefficient': coef,
            'moy_coef': moy_coef,
        })
    return results


def _previous_period_average(student, period, academic_year, is_primary):
    """Moyenne du trimestre / période précédente."""
    if not period or not academic_year:
        return None
    prev = (
        Period.objects.filter(academic_year=academic_year, order__lt=period.order)
        .order_by('-order')
        .first()
    )
    if not prev:
        return None
    if is_primary:
        rows = _compute_grades_primary(student, period=prev, academic_year=academic_year)
    else:
        rows = _compute_grades_secondary(student, period=prev, academic_year=academic_year)
    total_mc = Decimal('0')
    total_c = Decimal('0')
    for r in rows:
        if r['average'] is not None:
            total_mc += Decimal(str(r['moy_coef'] or 0))
            total_c += Decimal(str(r['coefficient']))
    if not total_c:
        return None
    return _q2(total_mc / total_c)


def _class_rank(student, classroom, period, academic_year, is_primary, general_avg):
    """Rang de l'élève dans la classe pour la période (1 = meilleur)."""
    if not classroom or general_avg is None:
        return None, None
    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student')
    averages = []
    for enr in enrollments:
        s = enr.student
        if is_primary:
            rows = _compute_grades_primary(s, period=period, academic_year=academic_year)
        else:
            rows = _compute_grades_secondary(s, period=period, academic_year=academic_year)
        tmc = Decimal('0')
        tc = Decimal('0')
        for r in rows:
            if r['average'] is not None:
                tmc += Decimal(str(r['moy_coef'] or 0))
                tc += Decimal(str(r['coefficient']))
        if tc:
            averages.append((s.id, float(tmc / tc)))
    if not averages:
        return None, None
    averages.sort(key=lambda x: -x[1])
    total = len(averages)
    for i, (sid, _) in enumerate(averages, start=1):
        if sid == student.id:
            return i, total
    return None, total


def _appreciation_from_avg(avg, out_of=20):
    """Appréciation automatique selon la moyenne (sur 10 ou sur 20)."""
    if avg is None:
        return ''
    try:
        a = float(avg)
    except (TypeError, ValueError):
        return ''
    # Normaliser sur 20 pour le barème
    if out_of and float(out_of) <= 10:
        a = a * 2  # /10 → équivalent /20
    if a >= 16:
        return 'Excellent'
    if a >= 14:
        return 'Bien'
    if a >= 12:
        return 'Assez bien'
    if a >= 10:
        return 'Passable'
    if a >= 8:
        return 'Insuffisant'
    return 'Très insuffisant'


@login_required
def bulletin(request, student_id):
    student = get_student_for_user(request.user, student_id)
    from core.year_context import get_selected_year
    current_year = get_selected_year(request) or AcademicYear.objects.filter(is_current=True).first()
    period_id = request.GET.get('period')
    period = get_object_or_404(Period, pk=period_id) if period_id else None
    template_id = request.GET.get('template')

    ctx = _build_bulletin_context(
        student, period, current_year, template_id=template_id
    )
    # Périodes : mois pour primaire, trimestres pour secondaire/lycée
    if current_year:
        if ctx['is_primary']:
            periods = Period.objects.filter(
                academic_year=current_year, period_type='mois'
            ).order_by('order')
            if not periods.exists():
                periods = Period.objects.filter(academic_year=current_year).order_by('order')
        else:
            periods = Period.objects.filter(
                academic_year=current_year, period_type='trimestre'
            ).order_by('order')
            if not periods.exists():
                periods = Period.objects.filter(academic_year=current_year).order_by('order')
    else:
        periods = Period.objects.none()

    from .models import BulletinTemplate
    from .template_views import ensure_default_templates
    try:
        ensure_default_templates()
        cat = 'primaire' if ctx['is_primary'] else 'secondaire'
        available_templates = BulletinTemplate.objects.filter(category=cat)
    except Exception:
        available_templates = []

    ctx.update({
        'periods': periods,
        'print_mode': request.GET.get('print') == '1',
        'available_templates': available_templates,
        'template_id': template_id or (ctx['bulletin_template'].pk if ctx.get('bulletin_template') else ''),
        'section': 'bulletins',
        'current_year': current_year,
    })
    template_name = 'grades/bulletin_primaire.html' if ctx['is_primary'] else 'grades/bulletin_secondaire.html'
    return render(request, template_name, ctx)


@login_required
@_students_use_portal
def bulletin_list(request):
    """Bulletins pro : Primaire | Secondaire/Lycée → classes → périodes auto."""
    from academics.models import ClassRoom, Cycle
    from core.year_context import get_selected_year
    from core.permissions import get_role, get_teacher_classrooms
    from .forms import level_is_primary, level_cycle_code
    from django.contrib import messages
    from django.shortcuts import redirect

    current_year = get_selected_year(request) or AcademicYear.objects.filter(is_current=True).first()
    cycle_filter = request.GET.get('cycle', '')  # primaire | secondaire | lycee | ''
    classroom_id = request.GET.get('classroom', '')
    period_id = request.GET.get('period', '')
    role = get_role(request.user)
    is_teacher = role == 'enseignant' and not request.user.is_superuser

    qs = ClassRoom.objects.select_related('level__cycle', 'academic_year').order_by(
        'level__cycle__order', 'level__order', 'name'
    )
    if current_year:
        qs = qs.filter(academic_year=current_year)
    qs = filter_classrooms_for_user(request.user, qs)
    if is_teacher:
        qs = qs.filter(id__in=get_teacher_classrooms(request.user).values_list('id', flat=True))

    # Group by cycle family
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
    # Enseignant : afficher directement ses classes (sans passer par le hub cotes)
    if is_teacher and not cycle_filter and not classroom_id:
        classrooms = list(qs)
    if cycle_filter in ('primaire', 'pri'):
        classrooms = primaire_classes
        is_primary_cycle = True
    elif cycle_filter in ('secondaire', 'sec'):
        classrooms = secondaire_classes
        is_primary_cycle = False
    elif cycle_filter in ('lycee', 'lyc'):
        classrooms = lycee_classes
        is_primary_cycle = False

    # Periods auto according to cycle
    periods = Period.objects.none()
    if current_year and is_primary_cycle is not None:
        if is_primary_cycle:
            periods = Period.objects.filter(
                academic_year=current_year, period_type='mois', is_active=True
            ).order_by('order')
        else:
            periods = Period.objects.filter(
                academic_year=current_year, period_type='trimestre', is_active=True
            ).order_by('order')
        if not periods.exists():
            periods = Period.objects.filter(academic_year=current_year, is_active=True).order_by('order')

    classroom = None
    students = []
    period = None
    if classroom_id:
        classroom = get_object_or_404(
            ClassRoom.objects.select_related('level__cycle'), pk=classroom_id
        )
        if is_teacher and classroom.id not in get_teacher_classrooms(request.user).values_list('id', flat=True):
            from django.contrib import messages
            messages.error(request, "Classe hors de vos affectations.")
            return redirect('grades:bulletin_list')
        # Auto-detect cycle from classroom if not set
        if is_primary_cycle is None:
            is_primary_cycle = level_is_primary(classroom.level)
            if current_year:
                if is_primary_cycle:
                    periods = Period.objects.filter(
                        academic_year=current_year, period_type='mois', is_active=True
                    ).order_by('order')
                else:
                    periods = Period.objects.filter(
                        academic_year=current_year, period_type='trimestre', is_active=True
                    ).order_by('order')
                if not periods.exists():
                    periods = Period.objects.filter(academic_year=current_year, is_active=True).order_by('order')
            cycle_filter = level_cycle_code(classroom.level)
            if cycle_filter == 'primaire':
                classrooms = primaire_classes
            elif cycle_filter == 'lycee':
                classrooms = lycee_classes
            else:
                classrooms = secondaire_classes

        enrollments = Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student').order_by('student__last_name', 'student__first_name')
        students = [e.student for e in enrollments]

    if period_id:
        period = get_object_or_404(Period, pk=period_id)
    elif periods and not period_id and classroom:
        # Appliquer directement la 1ère période
        period = periods.first()
        period_id = str(period.id) if period else ''

    tpl = 'grades/teacher_bulletins.html' if is_teacher else 'grades/bulletin_list.html'
    return render(request, tpl, {
        'primaire_classes': primaire_classes,
        'secondaire_classes': secondaire_classes,
        'lycee_classes': lycee_classes,
        'classrooms': classrooms,
        'periods': periods,
        'classroom_id': classroom_id,
        'period_id': str(period_id) if period_id else '',
        'classroom': classroom,
        'period': period,
        'students': students,
        'current_year': current_year,
        'cycle_filter': cycle_filter or ('all' if is_teacher else ''),
        'is_primary_cycle': is_primary_cycle,
        'section': 'bulletins',
        'is_teacher_ui': is_teacher,
        'nb_primaire': len(primaire_classes),
        'nb_secondaire': len(secondaire_classes),
        'nb_lycee': len(lycee_classes),
        'nb_eleves_pri': sum(
            Enrollment.objects.filter(classroom=c, is_active=True).count()
            for c in primaire_classes
        ),
        'nb_eleves_sec': sum(
            Enrollment.objects.filter(classroom=c, is_active=True).count()
            for c in secondaire_classes
        ),
        'nb_eleves_lyc': sum(
            Enrollment.objects.filter(classroom=c, is_active=True).count()
            for c in lycee_classes
        ),
    })


@login_required
def bulletin_pdf(request, student_id):
    """PDF d'un seul élève."""
    from .pdf_bulletin import render_bulletin_pdf

    student = get_student_for_user(request.user, student_id)
    current_year = get_selected_year(request) or AcademicYear.objects.filter(is_current=True).first()
    period_id = request.GET.get('period')
    period = get_object_or_404(Period, pk=period_id) if period_id else None

    ctx = _build_bulletin_context(student, period, current_year, template_id=request.GET.get('template'))
    pdf_bytes = render_bulletin_pdf([ctx])

    filename = f"bulletin_{student.matricule}_{period.name if period else 'annee'}.pdf"
    filename = filename.replace(' ', '_')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@_students_use_portal
def bulletin_class_pdf(request):
    """PDF de tous les élèves d'une classe (une page par élève)."""
    from .pdf_bulletin import render_bulletin_pdf
    from academics.models import ClassRoom

    classroom_id = request.GET.get('classroom')
    period_id = request.GET.get('period')
    if not classroom_id:
        return HttpResponse('Classe requise', status=400)

    classroom = get_object_or_404(filter_classrooms_for_user(request.user), pk=classroom_id)
    current_year = get_selected_year(request) or AcademicYear.objects.filter(is_current=True).first()
    period = get_object_or_404(Period, pk=period_id) if period_id else None

    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student').order_by('student__last_name', 'student__first_name')

    contexts = []
    for enr in enrollments:
        contexts.append(_build_bulletin_context(enr.student, period, current_year, template_id=request.GET.get('template')))

    if not contexts:
        return HttpResponse('Aucun élève dans cette classe', status=404)

    pdf_bytes = render_bulletin_pdf(contexts)
    period_part = period.name if period else 'annee'
    filename = f"bulletins_{classroom.name}_{period_part}.pdf".replace(' ', '_')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _resolve_template(is_primary, template_id=None):
    from .models import BulletinTemplate
    from .template_views import ensure_default_templates
    try:
        ensure_default_templates()
    except Exception:
        pass
    if template_id:
        try:
            return BulletinTemplate.objects.get(pk=template_id)
        except BulletinTemplate.DoesNotExist:
            pass
    cat = 'primaire' if is_primary else 'secondaire'
    try:
        return BulletinTemplate.get_default(cat)
    except Exception:
        return None


# Redéfinir _build_bulletin_context avec support modèle
def _build_bulletin_context(student, period, current_year, template=None, template_id=None):
    enrollment = None
    if current_year:
        enrollment = student.enrollments.filter(
            academic_year=current_year, is_active=True
        ).select_related('classroom__level__cycle').first()
    if not enrollment:
        enrollment = student.current_enrollment()

    is_primary = _is_primary(student, current_year)
    classroom = enrollment.classroom if enrollment else None

    if template is None:
        template = _resolve_template(is_primary, template_id)

    formula = 'comp40_plus_classe_div3'
    if template:
        formula = template.formula
        # Forcer primaire si le modèle est primaire
        if template.category == 'primaire':
            is_primary = True
        elif template.category == 'secondaire':
            is_primary = False

    if is_primary:
        subject_results = _compute_grades_primary(student, period=period, academic_year=current_year)
    else:
        subject_results = _compute_grades_secondary(
            student, period=period, academic_year=current_year, formula=formula
        )

    total_moy_coef = Decimal('0')
    total_coef = Decimal('0')
    for r in subject_results:
        if r['average'] is not None:
            total_moy_coef += Decimal(str(r['moy_coef'] or 0))
            total_coef += Decimal(str(r['coefficient']))
    general_avg = _q2(total_moy_coef / total_coef) if total_coef else None

    prev_avg = None
    rank = rank_total = None
    if not template or template.show_prev_average:
        prev_avg = _previous_period_average(student, period, current_year, is_primary)
    if not template or template.show_rank:
        rank, rank_total = _class_rank(
            student, classroom, period, current_year, is_primary, general_avg
        )

    try:
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    return {
        'student': student,
        'enrollment': enrollment,
        'period': period,
        'current_year': current_year,
        'is_primary': is_primary,
        'subject_results': subject_results,
        'general_avg': general_avg,
        'total_coef': float(total_coef) if total_coef else 0,
        'total_moy_coef': _q2(total_moy_coef) if total_coef else None,
        'prev_avg': prev_avg,
        'rank': rank,
        'rank_total': rank_total,
        'appreciation': _appreciation_from_avg(general_avg, out_of=10 if is_primary else 20),
        'school': school,
        'bulletin_template': template,
    }


@login_required
@_students_use_portal
def bulletin_preview(request):
    """
    Aperçu d'un ou plusieurs bulletins avant téléchargement PDF.
    GET: classroom, period, template, students (ids séparés par virgule, optionnel = tous)
    """
    from academics.models import ClassRoom
    from .models import BulletinTemplate
    from .template_views import ensure_default_templates

    try:
        ensure_default_templates()
    except Exception:
        pass

    classroom_id = request.GET.get('classroom', '')
    period_id = request.GET.get('period', '')
    template_id = request.GET.get('template', '')
    student_ids = request.GET.get('students', '').strip()

    current_year = AcademicYear.objects.filter(is_current=True).first()
    classrooms = ClassRoom.objects.select_related('level').order_by('level__order', 'name')
    periods = Period.objects.filter(academic_year=current_year).order_by('period_type', 'order') if current_year else Period.objects.none()
    templates = BulletinTemplate.objects.all()

    classroom = get_classroom_for_user(request.user, classroom_id) if classroom_id else None
    period = get_object_or_404(Period, pk=period_id) if period_id else None
    template = get_object_or_404(BulletinTemplate, pk=template_id) if template_id else None

    previews = []
    if classroom:
        enrollments = Enrollment.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('student').order_by('student__last_name', 'student__first_name')
        if student_ids:
            ids = [int(x) for x in student_ids.split(',') if x.isdigit()]
            enrollments = enrollments.filter(student_id__in=ids)
        for enr in enrollments:
            ctx = _build_bulletin_context(
                enr.student, period, current_year, template=template, template_id=template_id or None
            )
            previews.append(ctx)

    return render(request, 'grades/bulletin_preview.html', {
        'classrooms': classrooms,
        'periods': periods,
        'templates': templates,
        'classroom_id': classroom_id,
        'period_id': period_id,
        'template_id': template_id,
        'classroom': classroom,
        'period': period,
        'selected_template': template,
        'previews': previews,
        'student_ids': student_ids,
        'current_year': current_year,
        'section': 'bulletins',
    })
