from core.year_context import get_selected_year
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator

from .models import ClassRoom, Level, Cycle, AcademicYear
from .forms import ClassRoomForm
from students.models import Enrollment

# Programme type Mali — cases à cocher pour création rapide
MALI_CLASS_PROGRAM = [
    {
        "cycle": "primaire",
        "label": "1er cycle",
        "classes": [
            ("1ère année", "1ère A"), ("1ère année", "1ère B"),
            ("2ème année", "2ème A"), ("2ème année", "2ème B"),
            ("3ème année", "3ème A"), ("3ème année", "3ème B"),
            ("4ème année", "4ème A"), ("4ème année", "4ème B"),
            ("5ème année", "5ème A"), ("5ème année", "5ème B"),
            ("6ème année", "6ème A"), ("6ème année", "6ème B"),
        ],
    },
    {
        "cycle": "secondaire",
        "label": "2ème cycle",
        "classes": [
            ("7ème année", "7ème A"), ("7ème année", "7ème B"),
            ("8ème année", "8ème A"), ("8ème année", "8ème B"),
            ("9ème année", "9ème A"), ("9ème année", "9ème B"),
        ],
    },
    {
        "cycle": "lycee",
        "label": "Lycée",
        "classes": [
            ("10ème année", "10ème Sci A", "Scientifique"),
            ("10ème année", "10ème Litt A", "Littéraire"),
            ("11ème année", "11ème Sci A", "Scientifique"),
            ("11ème année", "11ème Litt A", "Littéraire"),
            ("12ème année", "12ème Sci A", "Scientifique"),
            ("12ème année", "12ème Litt A", "Littéraire"),
        ],
    },
]


def clone_classrooms_to_year(source_year, target_year):
    """
    Copie la structure des classes (noms, niveaux, frais) vers une nouvelle année.
    Sans les élèves — les inscriptions se font via Passage / Redoublement ou inscription.
    Retourne le nombre de classes créées.
    """
    if not source_year or not target_year or source_year.pk == target_year.pk:
        return 0
    created = 0
    for src in ClassRoom.objects.filter(academic_year=source_year).select_related('level'):
        exists = ClassRoom.objects.filter(
            academic_year=target_year, name=src.name, level=src.level
        ).exists()
        if exists:
            continue
        ClassRoom.objects.create(
            name=src.name,
            level=src.level,
            academic_year=target_year,
            serie=src.serie or '',
            capacity=src.capacity,
            inscription_fee=getattr(src, 'inscription_fee', 0) or 0,
            tuition_fee=getattr(src, 'tuition_fee', 0) or 0,
            main_teacher=src.main_teacher,
        )
        created += 1
    return created




@login_required
def classroom_list(request):
    qs = (
        ClassRoom.objects.select_related('level__cycle', 'academic_year', 'main_teacher')
        .annotate(nb_eleves=Count('enrollments', filter=Q(enrollments__is_active=True)))
        .order_by('level__cycle__order', 'level__order', 'name')
    )
    cycle_id = request.GET.get('cycle', '')
    level_id = request.GET.get('level', '')
    year_id = request.GET.get('year', '')
    q = request.GET.get('q', '').strip()
    if cycle_id:
        qs = qs.filter(level__cycle_id=cycle_id)
    if level_id:
        qs = qs.filter(level_id=level_id)
    if year_id:
        qs = qs.filter(academic_year_id=year_id)
    if q:
        qs = qs.filter(name__icontains=q)
    current_year = get_selected_year(request)
    if not year_id and current_year and not q and not cycle_id and not level_id:
        qs = qs.filter(academic_year=current_year)
        year_id = str(current_year.id)
    # Si l'année sélectionnée n'a aucune classe, proposer / auto-copier depuis l'année précédente
    prev_year = None
    can_clone = False
    if current_year and not q:
        count_this = ClassRoom.objects.filter(academic_year=current_year).count()
        if count_this == 0:
            prev_year = (
                AcademicYear.objects.filter(start_date__lt=current_year.start_date)
                .order_by('-start_date').first()
            )
            if prev_year and ClassRoom.objects.filter(academic_year=prev_year).exists():
                can_clone = True
                # Auto-copie une fois pour ne pas laisser la page vide
                if request.GET.get('clone') == '1' or request.GET.get('auto_clone') == '1':
                    n = clone_classrooms_to_year(prev_year, current_year)
                    messages.success(
                        request,
                        f'{n} classe(s) reprises de {prev_year.name} (sans les élèves).'
                    )
                    return redirect('academics:classroom_list')

    # Stats sur le queryset filtré (avant pagination)
    all_filtered = list(qs)
    total = len(all_filtered)
    with_teacher = sum(1 for c in all_filtered if c.main_teacher_id)
    eleves = sum(getattr(c, 'nb_eleves', 0) or 0 for c in all_filtered)
    boys = girls = 0
    try:
        class_ids = [c.id for c in all_filtered]
        if class_ids:
            boys = Enrollment.objects.filter(
                classroom_id__in=class_ids, is_active=True, student__gender='M'
            ).count()
            girls = Enrollment.objects.filter(
                classroom_id__in=class_ids, is_active=True, student__gender='F'
            ).count()
    except Exception:
        pass

    classrooms = Paginator(qs, 40).get_page(request.GET.get('page'))
    return render(request, 'academics/classroom_list.html', {
        'classrooms': classrooms, 'cycles': Cycle.objects.all(),
        'levels': Level.objects.select_related('cycle').all(),
        'years': AcademicYear.objects.all(),
        'cycle_id': cycle_id, 'level_id': level_id, 'year_id': year_id, 'q': q,
        'current_year': current_year,
        'selected_year': current_year,
        'form': ClassRoomForm(),
        'prev_year': prev_year,
        'can_clone': can_clone,
        'stats': {
            'total': total,
            'with_teacher': with_teacher,
            'eleves': eleves,
            'boys': boys,
            'girls': girls,
        },
    })


@login_required
def classroom_detail(request, pk):
    from classe.service import TABS, build_context

    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level__cycle', 'academic_year', 'main_teacher'), pk=pk
    )
    tab = request.GET.get('tab', 'general')
    ctx = build_context(request, classroom, tab)
    ctx['student_count'] = Enrollment.objects.filter(classroom=classroom, is_active=True).count()
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'academics/classroom_detail_modal.html', ctx)
    return render(request, 'academics/classroom_detail.html', ctx)



@login_required
def classroom_bulk_add(request):
    """Sélection multiple de classes du programme Mali."""
    year = get_selected_year(request)
    if not year:
        messages.error(request, "Sélectionnez une année scolaire.")
        return redirect('academics:classroom_list')

    if request.method == 'POST':
        selected = request.POST.getlist('classes')
        try:
            capacity = int(request.POST.get('capacity') or 40)
        except ValueError:
            capacity = 40
        inscription = request.POST.get('inscription_fee') or 0
        tuition = request.POST.get('tuition_fee') or 0
        created = 0
        for raw in selected:
            parts = raw.split('|')
            if len(parts) < 2:
                continue
            level_name, class_name = parts[0], parts[1]
            serie = parts[2] if len(parts) > 2 else ''
            level = Level.objects.filter(name=level_name).first()
            if not level:
                short = level_name.replace(' année', '').strip()
                level = Level.objects.filter(name__icontains=short).first()
            if not level:
                continue
            obj, was_created = ClassRoom.objects.get_or_create(
                name=class_name,
                academic_year=year,
                defaults={
                    'level': level,
                    'capacity': capacity,
                    'serie': serie,
                    'inscription_fee': inscription,
                    'tuition_fee': tuition,
                },
            )
            if was_created:
                created += 1
        if created:
            messages.success(request, f"{created} classe(s) ajoutée(s).")
        else:
            messages.info(request, "Aucune nouvelle classe (déjà existantes ou sélection vide).")
        return redirect('academics:classroom_list')

    existing = set(
        ClassRoom.objects.filter(academic_year=year).values_list('name', flat=True)
    )
    program = []
    for block in MALI_CLASS_PROGRAM:
        items = []
        for entry in block['classes']:
            if len(entry) == 3:
                level_name, class_name, serie = entry
            else:
                level_name, class_name = entry[0], entry[1]
                serie = ''
            items.append({
                'level_name': level_name,
                'class_name': class_name,
                'serie': serie,
                'value': f'{level_name}|{class_name}|{serie}',
                'exists': class_name in existing,
            })
        program.append({'label': block['label'], 'cycle': block['cycle'], 'items': items})

    ctx = {'program': program, 'selected_year': year}
    return render(request, 'academics/classroom_bulk_modal.html', ctx)


@login_required
def classroom_create(request):
    if request.method == 'POST':
        form = ClassRoomForm(request.POST)
        if form.is_valid():
            classroom = form.save()
            messages.success(request, f"Classe {classroom} créée.")
            return redirect('academics:classroom_detail', pk=classroom.pk)
    else:
        form = ClassRoomForm()
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'academics/classroom_form_modal.html', {
            'form': form, 'form_action': request.path,
        })
    return render(request, 'academics/classroom_form.html', {
        'form': form, 'title': 'Nouvelle classe', 'is_edit': False,
    })


@login_required
def classroom_edit(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk)
    if request.method == 'POST':
        form = ClassRoomForm(request.POST, instance=classroom)
        if form.is_valid():
            form.save()
            messages.success(request, f"Classe {classroom} modifiée.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal') == '1':
                return redirect('academics:classroom_list')
            return redirect('academics:classroom_detail', pk=classroom.pk)
    else:
        form = ClassRoomForm(instance=classroom)
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'academics/classroom_form_modal.html', {
            'form': form,
            'form_action': request.path,
            'classroom': classroom,
        })
    return render(request, 'academics/classroom_form.html', {
        'form': form, 'title': f'Modifier — {classroom.name}', 'is_edit': True, 'classroom': classroom,
    })


@login_required
def clone_classrooms(request):
    """Reprend la structure des classes de l'année précédente vers l'année de travail."""
    target = get_selected_year(request)
    if not target:
        messages.error(request, "Aucune année de travail.")
        return redirect('academics:classroom_list')
    prev = (
        AcademicYear.objects.filter(start_date__lt=target.start_date)
        .order_by('-start_date').first()
    )
    if not prev:
        messages.error(request, "Pas d'année précédente.")
        return redirect('academics:classroom_list')
    n = clone_classrooms_to_year(prev, target)
    if n:
        messages.success(request, f"{n} classe(s) copiées depuis {prev.name} (élèves non inclus).")
    else:
        messages.info(request, "Aucune nouvelle classe à copier (déjà présentes ou source vide).")
    return redirect('academics:classroom_list')


@login_required
def classroom_subjects(request, pk):
    """
    Matières par classe + règles d'affectation :
    - 1er cycle : un prof principal pour toutes les matières
    - 2e cycle / lycée : un prof par matière (un même prof peut avoir plusieurs matières)
    """
    from .models import ClassSubject, Subject, SubjectAssignment
    from grades.forms import level_is_primary, level_cycle_code
    from teachers.models import Teacher

    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'level__cycle', 'academic_year', 'main_teacher'),
        pk=pk,
    )
    is_primary = level_is_primary(classroom.level)
    cycle_code = level_cycle_code(classroom.level)
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'delete':
            ClassSubject.objects.filter(
                pk=request.POST.get('cs_id'), classroom=classroom
            ).delete()
            messages.success(request, 'Matière retirée de la classe.')
            return redirect('academics:classroom_subjects', pk=pk)

        if action == 'main_teacher':
            mt = request.POST.get('main_teacher') or None
            classroom.main_teacher_id = mt or None
            classroom.save(update_fields=['main_teacher'])
            if classroom.main_teacher_id and is_primary:
                for cs in ClassSubject.objects.filter(classroom=classroom):
                    # One assignment per subject+classroom - need unique on subject,classroom
                    SubjectAssignment.objects.filter(
                        classroom=classroom, subject=cs.subject
                    ).exclude(teacher_id=classroom.main_teacher_id).delete()
                    existing = SubjectAssignment.objects.filter(
                        classroom=classroom, subject=cs.subject,
                        teacher_id=classroom.main_teacher_id,
                    ).first()
                    if existing:
                        existing.hours_per_week = cs.hours_per_week or 2
                        existing.save(update_fields=['hours_per_week'])
                    else:
                        SubjectAssignment.objects.create(
                            classroom=classroom,
                            subject=cs.subject,
                            teacher_id=classroom.main_teacher_id,
                            hours_per_week=cs.hours_per_week or 2,
                        )
            messages.success(request, 'Professeur principal enregistré.')
            return redirect('academics:classroom_subjects', pk=pk)

        if action == 'assign_teachers':
            for cs in ClassSubject.objects.filter(classroom=classroom):
                tid = request.POST.get('teacher_%s' % cs.subject_id) or ''
                if tid:
                    SubjectAssignment.objects.filter(
                        classroom=classroom, subject_id=cs.subject_id
                    ).exclude(teacher_id=tid).delete()
                    obj = SubjectAssignment.objects.filter(
                        classroom=classroom, subject_id=cs.subject_id, teacher_id=tid
                    ).first()
                    if obj:
                        obj.hours_per_week = cs.hours_per_week or 2
                        obj.save(update_fields=['hours_per_week'])
                    else:
                        SubjectAssignment.objects.create(
                            classroom=classroom,
                            subject_id=cs.subject_id,
                            teacher_id=tid,
                            hours_per_week=cs.hours_per_week or 2,
                        )
                else:
                    SubjectAssignment.objects.filter(
                        classroom=classroom, subject_id=cs.subject_id
                    ).delete()
            messages.success(request, 'Affectations enseignants enregistrées.')
            return redirect('academics:classroom_subjects', pk=pk)

        subject_ids = request.POST.getlist('subject')
        if not subject_ids and request.POST.get('subject'):
            subject_ids = [request.POST.get('subject')]
        n = 0
        for sid in subject_ids:
            coef = request.POST.get('coef_%s' % sid) or None
            hours = request.POST.get('hours_%s' % sid) or request.POST.get('hours_per_week') or 2
            try:
                hours = int(hours)
            except Exception:
                hours = 2
            defaults = {'hours_per_week': hours}
            if coef:
                try:
                    from decimal import Decimal
                    defaults['coefficient'] = Decimal(str(coef).replace(',', '.'))
                except Exception:
                    pass
            ClassSubject.objects.update_or_create(
                classroom=classroom, subject_id=sid, defaults=defaults
            )
            n += 1
        if is_primary and classroom.main_teacher_id:
            for cs in ClassSubject.objects.filter(classroom=classroom):
                SubjectAssignment.objects.filter(
                    classroom=classroom, subject=cs.subject
                ).exclude(teacher_id=classroom.main_teacher_id).delete()
                if not SubjectAssignment.objects.filter(
                    classroom=classroom, subject=cs.subject,
                    teacher_id=classroom.main_teacher_id,
                ).exists():
                    SubjectAssignment.objects.create(
                        classroom=classroom,
                        subject=cs.subject,
                        teacher_id=classroom.main_teacher_id,
                        hours_per_week=cs.hours_per_week or 2,
                    )
        messages.success(request, '%s matière(s) enregistrée(s) pour %s.' % (n, classroom.name))
        return redirect('academics:classroom_subjects', pk=pk)

    current = ClassSubject.objects.filter(classroom=classroom).select_related('subject').order_by('order', 'subject__name')
    current_ids = set(current.values_list('subject_id', flat=True))
    available = Subject.objects.filter(is_active=True).order_by('name')
    assign_map = {
        a.subject_id: a
        for a in SubjectAssignment.objects.filter(classroom=classroom).select_related('teacher')
    }
    rows = []
    for cs in current:
        rows.append({'cs': cs, 'assignment': assign_map.get(cs.subject_id)})

    ctx = {
        'classroom': classroom,
        'class_subjects': current,
        'rows': rows,
        'available': available,
        'current_ids': current_ids,
        'form_action': request.path,
        'is_primary': is_primary,
        'cycle_code': cycle_code,
        'teachers': teachers,
        'assign_map': assign_map,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'academics/classroom_subjects_modal.html', ctx)
    return render(request, 'academics/classroom_subjects.html', ctx)

