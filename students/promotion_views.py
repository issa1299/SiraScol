"""
Passage / redoublement en fin d'année.
- Décision par élève (passe / redouble)
- Listes des admis et redoublants
- Application : crée les inscriptions de l'année suivante
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import role_required, is_staff_role
from academics.models import AcademicYear, ClassRoom, Level
from students.models import Enrollment, PromotionDecision, PromotionOperation, Student
from students import orientation_rules
from grades.bulletin_views import _build_bulletin_context

def _annual_average(student, year, is_primary_hint=None):
    """
    Moyenne annuelle de l'élève pour l'année donnée.
    - Primaire (/10) : moyenne de toutes les compositions de l'année
    - Secondaire (/20) : moyenne des moyennes générales de chaque trimestre
    Retourne (moyenne Decimal or None, is_primary bool)
    """
    from grades.bulletin_views import (
        _build_bulletin_context, _is_primary, _compute_grades_primary, _compute_grades_secondary,
    )
    from grades.models import Period
    from decimal import Decimal

    is_pri = _is_primary(student, year) if is_primary_hint is None else is_primary_hint
    periods = list(Period.objects.filter(academic_year=year, is_active=True).order_by('order'))
    if not periods:
        periods = list(Period.objects.filter(academic_year=year).order_by('order'))

    avgs = []
    if is_pri:
        # Une moyenne sur toute l'année (toutes notes)
        rows = _compute_grades_primary(student, period=None, academic_year=year)
        total_coef = Decimal('0')
        total_moy = Decimal('0')
        for r in rows:
            if r.get('average') is not None and r.get('coefficient'):
                c = Decimal(str(r['coefficient']))
                total_coef += c
                total_moy += Decimal(str(r['average'])) * c
        if total_coef > 0:
            return (total_moy / total_coef).quantize(Decimal('0.01')), True
        return None, True
    else:
        # Moyenne des moyennes de chaque période (trimestre)
        for period in periods:
            try:
                ctx = _build_bulletin_context(student, period, year)
                g = ctx.get('general_avg')
                if g is not None:
                    avgs.append(Decimal(str(g)))
            except Exception:
                continue
        if not avgs:
            # fallback: toute l'année sans période
            try:
                ctx = _build_bulletin_context(student, None, year)
                g = ctx.get('general_avg')
                if g is not None:
                    return Decimal(str(g)), False
            except Exception:
                pass
            return None, False
        return (sum(avgs) / len(avgs)).quantize(Decimal('0.01')), False


def _auto_decision(average, is_primary):
    """
    Seuils standards Mali / francophone :
    - Primaire notes /10  → Admis si moyenne >= 5
    - Secondaire /20      → Admis si moyenne >= 10
    Sans moyenne → en_cours
    """
    if average is None:
        return 'en_cours'
    if is_primary:
        return 'promoted' if average >= Decimal('5') else 'repeated'
    return 'promoted' if average >= Decimal('10') else 'repeated'




def _next_level(level):
    """Niveau suivant dans le même cycle, sinon None (fin de cycle)."""
    nxt = Level.objects.filter(
        cycle=level.cycle, order__gt=level.order
    ).order_by('order').first()
    if nxt:
        return nxt
    # Essayer cycle suivant
    next_cycle = type(level.cycle).objects.filter(
        order__gt=level.cycle.order
    ).order_by('order').first()
    if next_cycle:
        return Level.objects.filter(cycle=next_cycle).order_by('order').first()
    return None



def _promoted_class_name(source_classroom, target_level):
    """
    Nouveau nom de classe pour un élève qui passe :
    1ère A → 2ème A, 6ème A → 7ème A, etc.
    """
    import re
    name = (source_classroom.name or '').strip()
    src_level = source_classroom.level.name if source_classroom.level_id else ''
    tgt = target_level.name or ''

    if src_level and src_level in name:
        return name.replace(src_level, tgt, 1)

    src_short = src_level.split()[0] if src_level else ''
    tgt_short = tgt.split()[0] if tgt else tgt
    if src_short and src_short in name:
        return name.replace(src_short, tgt_short, 1)

    # Variantes courantes : 1er, 1ère, 6eme, 6ème
    m = re.search(r'(\d+\s*(?:ère|eme|ème|er)?)', name, re.I)
    if m and tgt_short:
        return name[:m.start()] + tgt_short + name[m.end():]

    suffix = 'A'
    m2 = re.search(r'\b(Sci|Litt|Eco|[A-Z])\b', name)
    if m2:
        suffix = m2.group(1)
    return f'{tgt} {suffix}'.strip()


def _find_or_create_target_classroom(level, year, serie='', source_classroom=None):
    """
    Réutilise la MÊME structure de classe (même nom) pour l'année suivante.
    On ne change pas les classes : seuls les élèves (inscriptions) changent.
    """
    name = source_classroom.name if source_classroom else None
    if name:
        existing = ClassRoom.objects.filter(
            academic_year=year, name=name, level=level
        ).first()
        if existing:
            return existing
        # Même nom, frais repris de la classe source
        return ClassRoom.objects.create(
            name=name,
            level=level,
            academic_year=year,
            serie=(source_classroom.serie if source_classroom else serie) or '',
            capacity=source_classroom.capacity if source_classroom else 40,
            inscription_fee=getattr(source_classroom, 'inscription_fee', 0) or 0,
            tuition_fee=getattr(source_classroom, 'tuition_fee', 0) or 0,
            main_teacher=getattr(source_classroom, 'main_teacher', None),
        )
    qs = ClassRoom.objects.filter(level=level, academic_year=year)
    if serie:
        qs = qs.filter(serie=serie)
    room = qs.order_by('name').first()
    if room:
        return room
    base = f"{level.name}"
    if serie:
        base = f"{level.name} {serie}"
    return ClassRoom.objects.create(
        name=f"{base} A",
        level=level,
        academic_year=year,
        serie=serie or '',
        capacity=40,
    )


@role_required('admin', 'directeur', 'secretaire')
def promotion_home(request):
    years = AcademicYear.objects.all().order_by('-start_date')
    source_id = request.GET.get('year') or ''
    source = None
    if source_id:
        source = get_object_or_404(AcademicYear, pk=source_id)
    else:
        source = AcademicYear.objects.filter(is_current=True).first()

    target = None
    if source:
        target = AcademicYear.objects.filter(
            start_date__gt=source.start_date
        ).order_by('start_date').first()

    classrooms = []
    stats = {'total': 0, 'promoted': 0, 'repeated': 0, 'pending': 0}
    if source:
        classrooms = ClassRoom.objects.filter(
            academic_year=source
        ).select_related('level', 'level__cycle').order_by('level__order', 'name')
        enrs = Enrollment.objects.filter(academic_year=source, is_active=True)
        stats['total'] = enrs.count()
        stats['promoted'] = enrs.filter(end_status='promoted').count()
        stats['repeated'] = enrs.filter(end_status='repeated').count()
        stats['pending'] = enrs.filter(end_status='en_cours').count()

    return render(request, 'students/promotion_home.html', {
        'years': years,
        'source': source,
        'target': target,
        'classrooms': classrooms,
        'stats': stats,
    })


@role_required('admin', 'directeur', 'secretaire')
def promotion_class(request, classroom_id):
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year', 'level__cycle'),
        pk=classroom_id,
    )
    source = classroom.academic_year
    target = AcademicYear.objects.filter(
        start_date__gt=source.start_date
    ).order_by('start_date').first()

    enrollments = (
        Enrollment.objects.filter(classroom=classroom, is_active=True)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )

    # Moyenne indicative si pas encore saisie
    rows = []
    for enr in enrollments:
        avg = enr.end_average
        if avg is None:
            try:
                ctx = _build_bulletin_context(enr.student, None, source)
                avg = ctx.get('general_avg')
            except Exception:
                avg = None
        next_lvl = _next_level(classroom.level)
        rows.append({
            'enrollment': enr,
            'average': avg,
            'next_level': next_lvl,
        })

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        for enr in enrollments:
            status = request.POST.get(f'status_{enr.id}', 'en_cours')
            note = request.POST.get(f'note_{enr.id}', '').strip()
            avg_raw = request.POST.get(f'avg_{enr.id}', '').strip()
            enr.end_status = status
            enr.end_note = note
            if avg_raw:
                try:
                    enr.end_average = Decimal(avg_raw.replace(',', '.'))
                except Exception:
                    pass
            elif enr.end_average is None:
                # garder moyenne calculée
                for r in rows:
                    if r['enrollment'].id == enr.id and r['average'] is not None:
                        try:
                            enr.end_average = Decimal(str(r['average']))
                        except Exception:
                            pass
            enr.save()
        messages.success(request, 'Décisions enregistrées.')
        if action == 'apply' and target:
            return redirect(
                f"{request.path}?applied=0"
            )  # will use apply endpoint
        return redirect('students:promotion_class', classroom_id=classroom.pk)

    return render(request, 'students/promotion_class.html', {
        'classroom': classroom,
        'source': source,
        'target': target,
        'rows': rows,
        'status_choices': Enrollment.END_STATUS_CHOICES,
        'is_orientation_class': orientation_rules.is_orientation_classroom(classroom),
    })


@role_required('admin', 'directeur')
@require_POST
def promotion_apply(request, classroom_id):
    """Applique les décisions : crée les inscriptions année suivante."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year'),
        pk=classroom_id,
    )
    source = classroom.academic_year
    target_id = request.POST.get('target_year')
    target = get_object_or_404(AcademicYear, pk=target_id) if target_id else (
        AcademicYear.objects.filter(start_date__gt=source.start_date).order_by('start_date').first()
    )
    if not target:
        messages.error(request, "Créez d'abord l'année scolaire suivante dans Configuration.")
        return redirect('students:promotion_class', classroom_id=classroom.pk)

    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student', 'classroom__level')

    created = 0
    skipped = 0
    with transaction.atomic():
        for enr in enrollments:
            if enr.end_status not in ('promoted', 'repeated'):
                skipped += 1
                continue
            # Déjà inscrit année suivante ?
            if Enrollment.objects.filter(student=enr.student, academic_year=target).exists():
                skipped += 1
                continue

            if enr.end_status == 'repeated':
                # Redouble : même niveau + même nom de classe
                target_level = classroom.level
                source_for_class = classroom
            else:
                target_level = _next_level(classroom.level)
                if not target_level:
                    enr.end_note = (enr.end_note or '') + ' [Fin de cycle — pas de classe suivante]'
                    enr.save(update_fields=['end_note'])
                    skipped += 1
                    continue
                next_name = _promoted_class_name(classroom, target_level)
                source_for_class = ClassRoom(
                    name=next_name,
                    level=target_level,
                    serie=classroom.serie or '',
                    capacity=classroom.capacity,
                    inscription_fee=getattr(classroom, 'inscription_fee', 0) or 0,
                    tuition_fee=getattr(classroom, 'tuition_fee', 0) or 0,
                    main_teacher=getattr(classroom, 'main_teacher', None),
                )

            target_room = _find_or_create_target_classroom(
                target_level, target,
                serie=classroom.serie or '',
                source_classroom=source_for_class,
            )
            Enrollment.objects.create(
                student=enr.student,
                classroom=target_room,
                academic_year=target,
                enrollment_date=target.start_date or date.today(),
                is_active=True,
                end_status='en_cours',
            )
            # Désactiver ancienne inscription
            enr.is_active = False
            enr.save(update_fields=['is_active'])
            created += 1

    messages.success(
        request,
        f'{created} inscription(s) créée(s) pour {target.name}. {skipped} ignorée(s).'
    )
    return redirect('students:promotion_lists', year_id=source.pk)



@role_required('admin', 'directeur', 'secretaire')
@require_POST
def promotion_auto(request, classroom_id):
    """Calcule les moyennes et propose Admis/Redouble automatiquement."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year', 'level__cycle'),
        pk=classroom_id,
    )
    year = classroom.academic_year
    from grades.forms import level_is_primary
    is_pri = level_is_primary(classroom.level)

    enrollments = Enrollment.objects.filter(classroom=classroom, is_active=True).select_related('student')
    is_orientation = orientation_rules.is_orientation_classroom(classroom)
    n_ok = n_fail = n_skip = 0
    for enr in enrollments:
        avg, _ = _annual_average(enr.student, year, is_primary_hint=is_pri)
        enr.end_average = avg
        if is_orientation:
            # Lycée : la moyenne est indicative ; l'orientation appartient au
            # conseil des professeurs et à la direction (jamais automatique).
            if avg is not None:
                enr.end_note = (enr.end_note or '')
                n_ok += 1
            else:
                n_skip += 1
        else:
            decision = _auto_decision(avg, is_pri)
            enr.end_status = decision
            if avg is not None:
                seuil = '5/10' if is_pri else '10/20'
                enr.end_note = f'Auto: moy. {avg} (seuil {seuil})'
                if decision == 'promoted':
                    n_ok += 1
                else:
                    n_fail += 1
            else:
                enr.end_note = 'Auto: pas assez de notes'
                n_skip += 1
        enr.save()

    if is_orientation:
        messages.success(
            request,
            f'{n_ok} moyenne(s) annuelle(s) calculée(s). Orientation à décider manuellement '
            'par le conseil des professeurs et la direction.'
        )
    else:
        messages.success(
            request,
            f'Calcul auto : {n_ok} admis, {n_fail} redoublants, {n_skip} sans notes (à décider à la main).'
        )
    return redirect('students:promotion_class', classroom_id=classroom.pk)


@role_required('admin', 'directeur', 'secretaire')
def promotion_lists(request, year_id):
    """Listes des admis et redoublants pour une année."""
    year = get_object_or_404(AcademicYear, pk=year_id)
    classroom_id = request.GET.get('classroom', '')
    enrs = Enrollment.objects.filter(
        academic_year=year
    ).select_related('student', 'classroom', 'classroom__level')

    if classroom_id:
        enrs = enrs.filter(classroom_id=classroom_id)

    promoted = enrs.filter(end_status='promoted').order_by(
        'classroom__level__order', 'student__last_name'
    )
    repeated = enrs.filter(end_status='repeated').order_by(
        'classroom__level__order', 'student__last_name'
    )
    pending = enrs.filter(end_status='en_cours', is_active=True).order_by(
        'classroom__level__order', 'student__last_name'
    )
    classrooms = ClassRoom.objects.filter(academic_year=year).order_by('level__order', 'name')

    others = enrs.filter(end_status__in=('ajourne', 'transferred', 'autre', 'abandoned')).order_by(
        'classroom__level__order', 'student__last_name'
    )

    return render(request, 'students/promotion_lists.html', {
        'year': year,
        'promoted': promoted,
        'repeated': repeated,
        'pending': pending,
        'others': others,
        'classrooms': classrooms,
        'classroom_id': classroom_id,
    })


# ── Orientation du lycée (décision du conseil, validation du directeur) ────────

def _target_year_for(source):
    if not source or not source.start_date:
        return None
    return AcademicYear.objects.filter(
        start_date__gt=source.start_date
    ).order_by('start_date').first()


@role_required('admin', 'directeur', 'secretaire')
def orientation_home(request):
    """Point d'entrée « Passage en classe supérieure » (lycée malien)."""
    years = AcademicYear.objects.all().order_by('-start_date')
    source_id = request.GET.get('year')
    source = get_object_or_404(AcademicYear, pk=source_id) if source_id else None
    if not source:
        source = AcademicYear.objects.filter(is_current=True).first() or years.first()
    target = _target_year_for(source) if source else None
    classrooms = []
    operations = PromotionOperation.objects.none()
    if source:
        candidates = ClassRoom.objects.filter(academic_year=source).select_related(
            'level'
        ).order_by('level__order', 'name')
        classrooms = [c for c in candidates if orientation_rules.is_orientation_classroom(c)]
        operations = PromotionOperation.objects.filter(source_year=source).select_related(
            'source_classroom', 'target_year', 'validated_by'
        )
    return render(request, 'students/orientation_home.html', {
        'years': years, 'source': source, 'target': target,
        'classrooms': classrooms, 'operations': operations,
    })


@role_required('admin', 'directeur', 'secretaire')
def orientation_class(request, classroom_id):
    """Saisie/correction des orientations d'une classe d'origine."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year'), pk=classroom_id
    )
    if not orientation_rules.is_orientation_classroom(classroom):
        messages.error(request, "Cette classe ne fait pas l'objet d'une orientation lycée.")
        return redirect('students:orientation_home')
    source = classroom.academic_year
    target = _target_year_for(source)
    if not target:
        messages.error(request, "Créez d'abord l'année scolaire suivante dans Configuration.")
        return redirect('students:orientation_home')

    operation, _ = PromotionOperation.objects.get_or_create(
        source_classroom=classroom, source_year=source, target_year=target,
        defaults={'created_by': request.user},
    )
    destinations = orientation_rules.destination_classrooms(classroom, target)
    repetitions = orientation_rules.repetition_classrooms(classroom, target)
    seen = set()
    all_targets = []
    for room in destinations + repetitions:
        if room.pk not in seen:
            seen.add(room.pk)
            all_targets.append(room)

    if request.method == 'POST' and not operation.is_locked:
        saved = 0
        for enr in Enrollment.objects.filter(classroom=classroom, is_active=True):
            if request.POST.get(f'select_{enr.pk}') != 'on':
                continue
            decision = request.POST.get(f'decision_{enr.pk}', 'en_cours')
            if decision not in dict(Enrollment.END_STATUS_CHOICES):
                continue
            target_id = request.POST.get(f'target_{enr.pk}') or None
            if target_id:
                try:
                    target_id = int(target_id)
                except ValueError:
                    target_id = None
            allowed = orientation_rules.allowed_destination_ids(classroom, target, decision)
            if target_id and target_id not in allowed:
                messages.error(
                    request, f'Destination non autorisée pour {enr.student.full_name}.'
                )
                continue
            if decision in ('promoted', 'repeated') and not target_id:
                messages.error(
                    request, f'Choisissez une classe de destination pour {enr.student.full_name}.'
                )
                continue
            average = None
            avg_raw = (request.POST.get(f'avg_{enr.pk}') or '').strip()
            if avg_raw:
                try:
                    average = Decimal(avg_raw.replace(',', '.'))
                except Exception:
                    pass
            last = PromotionDecision.objects.filter(
                operation=operation, enrollment=enr
            ).order_by('-revision').first()
            PromotionDecision.objects.filter(
                operation=operation, enrollment=enr, is_current=True
            ).update(is_current=False)
            PromotionDecision.objects.create(
                operation=operation,
                enrollment=enr,
                decision=decision,
                target_classroom_id=target_id,
                average=average,
                note=(request.POST.get(f'note_{enr.pk}') or '').strip(),
                revision=(last.revision + 1) if last else 1,
                is_current=True,
                updated_by=request.user,
            )
            saved += 1
        if saved:
            operation.status = ('a_valider' if request.POST.get('action') == 'a_valider'
                                else 'brouillon')
            operation.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'{saved} décision(s) enregistrée(s) (révision tracée).')
        return redirect('students:orientation_class', classroom_id=classroom.pk)

    current = {
        d.enrollment_id: d for d in PromotionDecision.objects.filter(
            operation=operation, is_current=True
        ).select_related('target_classroom')
    }
    rows = []
    for enr in Enrollment.objects.filter(classroom=classroom, is_active=True).select_related(
        'student'
    ).order_by('student__last_name', 'student__first_name'):
        average = enr.end_average
        if average is None:
            try:
                average, _ = _annual_average(enr.student, source)
            except Exception:
                average = None
        rows.append({
            'enrollment': enr,
            'average': average,
            'decision': current.get(enr.pk),
        })
    return render(request, 'students/orientation_class.html', {
        'classroom': classroom, 'source': source, 'target': target,
        'operation': operation, 'rows': rows, 'destinations': destinations,
        'repetitions': repetitions, 'all_targets': all_targets,
        'dest_ids': [room.pk for room in destinations],
        'rep_ids': [room.pk for room in repetitions],
        'status_choices': Enrollment.END_STATUS_CHOICES,
    })


@role_required('admin', 'directeur', 'secretaire')
def orientation_summary(request, operation_id):
    """Récapitulatif avant validation définitive."""
    operation = get_object_or_404(
        PromotionOperation.objects.select_related(
            'source_classroom', 'source_year', 'target_year', 'validated_by'
        ), pk=operation_id,
    )
    decisions = list(PromotionDecision.objects.filter(
        operation=operation, is_current=True
    ).select_related('enrollment__student', 'target_classroom').order_by(
        'target_classroom__name', 'enrollment__student__last_name'
    ))
    groups = {}
    for decision in decisions:
        key = decision.target_classroom.name if decision.target_classroom else 'Sans classe'
        groups.setdefault(key, []).append(decision)
    return render(request, 'students/orientation_summary.html', {
        'operation': operation, 'decisions': decisions,
        'groups': sorted(groups.items()), 'total': len(decisions),
    })


@role_required('admin', 'directeur')
@require_POST
def orientation_validate(request, operation_id):
    """Validation définitive : crée les inscriptions cibles, verrouille le dossier."""
    operation = get_object_or_404(PromotionOperation, pk=operation_id)
    if operation.is_locked:
        messages.info(request, 'Cette opération est déjà validée et verrouillée.')
        return redirect('students:orientation_summary', operation_id=operation.pk)

    created = skipped = 0
    with transaction.atomic():
        for decision in PromotionDecision.objects.filter(
            operation=operation, is_current=True
        ).select_related('enrollment__student', 'target_classroom'):
            enrollment = decision.enrollment
            enrollment.end_status = decision.decision
            note = decision.note or ''
            if decision.target_classroom_id:
                note = f'{note} → {decision.target_classroom.name}'.strip(' →')
            enrollment.end_note = note

            if decision.decision in ('promoted', 'repeated') and decision.target_classroom_id:
                # Garde-fou : unicité (élève, année) déjà en base, vérifiée ici aussi.
                if Enrollment.objects.filter(
                    student=enrollment.student, academic_year=operation.target_year
                ).exists():
                    enrollment.end_note = (note + ' [Doublon : déjà inscrit année cible]').strip()
                    enrollment.save(update_fields=['end_status', 'end_note'])
                    skipped += 1
                    continue
                Enrollment.objects.create(
                    student=enrollment.student,
                    classroom=decision.target_classroom,
                    academic_year=operation.target_year,
                    enrollment_date=operation.target_year.start_date or date.today(),
                    is_active=True,
                    end_status='en_cours',
                )
                # L'ancienne inscription est conservée avec sa classe et son année.
                enrollment.is_active = False
                enrollment.save(update_fields=['end_status', 'end_note', 'is_active'])
                created += 1
            else:
                enrollment.save(update_fields=['end_status', 'end_note'])

        operation.status = 'valide'
        operation.validated_by = request.user
        operation.validated_at = timezone.now()
        operation.save(update_fields=['status', 'validated_by', 'validated_at', 'updated_at'])

    messages.success(
        request,
        f'Orientation validée : {created} inscription(s) créée(s) pour '
        f'{operation.target_year.name}, {skipped} ignorée(s).'
    )
    return redirect('students:orientation_summary', operation_id=operation.pk)
