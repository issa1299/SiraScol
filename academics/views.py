from core.year_context import get_selected_year
from core.permissions import permission_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator

from .models import ClassRoom, Level, Cycle, AcademicYear
from .forms import ClassRoomForm
from students.models import Enrollment

# Matières du système éducatif malien (programme type MEN / DEF / réforme lycée 2010-2011).
# Source de référence : Ministère de l'Éducation Nationale du Mali ; structure confirmée par
# « Système éducatif au Mali » (Wikipedia, consulté Nov. 2026) pour le DEF et les séries.
MALI_SUBJECTS_BY_LEVEL = {
    # 1er cycle de l'enseignement fondamental (1ère – 6ème année)
    '1ère année': ['Langue maternelle', 'Français', 'Mathématiques', 'Sciences', 'Histoire',
                   'Géographie', 'Éducation civique et morale', 'Éducation physique et sportive',
                   'Arts et expression'],
    '2ème année': ['Langue maternelle', 'Français', 'Mathématiques', 'Sciences', 'Histoire',
                   'Géographie', 'Éducation civique et morale', 'Éducation physique et sportive',
                   'Arts et expression'],
    '3ème année': ['Langue maternelle', 'Français', 'Mathématiques', 'Sciences', 'Histoire',
                   'Géographie', 'Éducation civique et morale', 'Éducation physique et sportive',
                   'Arts et expression'],
    '4ème année': ['Français', 'Mathématiques', 'Sciences', 'Histoire', 'Géographie',
                   'Éducation civique et morale', 'Éducation physique et sportive',
                   'Arts et expression', 'Travaux manuels'],
    '5ème année': ['Français', 'Mathématiques', 'Sciences', 'Histoire', 'Géographie',
                   'Éducation civique et morale', 'Éducation physique et sportive',
                   'Arts et expression', 'Anglais'],
    '6ème année': ['Français', 'Mathématiques', 'Sciences', 'Histoire', 'Géographie',
                   'Éducation civique et morale', 'Éducation physique et sportive',
                   'Anglais', 'Technologie'],
    # 2ème cycle de l'enseignement fondamental (7ème – 9ème année, pré-DEF)
    '7ème année': ['Français', 'Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                   'Histoire', 'Géographie', 'Éducation civique et morale',
                   'Éducation physique et sportive', 'Anglais', 'Technologie'],
    '8ème année': ['Français', 'Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                   'Histoire', 'Géographie', 'Éducation civique et morale',
                   'Éducation physique et sportive', 'Anglais', 'Technologie'],
    '9ème année': ['Français', 'Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                   'Histoire', 'Géographie', 'Éducation civique et morale',
                   'Éducation physique et sportive', 'Anglais'],
    # Lycée — 10ème année : tronc commun (réforme 2010-2011)
    '10ème année': ['Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                    'Histoire-Géographie', 'Français', 'Anglais', 'Arabe / langue vivante 2',
                    'Éducation civique et morale', 'Éducation physique et sportive',
                    'Informatique', 'Dessin technique', 'Statistique', 'Économie'],
    # Lycée — 11ème et 12ème : tronc commun des séries générales
    '11ème année': ['Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                    'Histoire-Géographie', 'Français', 'Anglais', 'Philosophie',
                    'Éducation physique et sportive'],
    '12ème année': ['Mathématiques', 'Physique-Chimie', 'Sciences de la vie et de la terre',
                    'Histoire-Géographie', 'Français', 'Anglais', 'Philosophie',
                    'Éducation physique et sportive'],
}


def subjects_for_level(level_name):
    """Matières associées à un niveau (nom de Level) du programme malien."""
    key = (level_name or '').strip()
    return list(MALI_SUBJECTS_BY_LEVEL.get(key, MALI_SUBJECTS_BY_LEVEL.get('6ème année', [])))


# Programme type Mali — cases à cocher pour création rapide
MALI_CLASS_PROGRAM = [
    {
        "cycle": "primaire",
        "label": "1er cycle",
        "groups": [
            {
                "key": "primaire",
                "label": "1ère – 6ème année",
                "items": [
                    ("1ère année", "1ère A", ""), ("1ère année", "1ère B", ""),
                    ("2ème année", "2ème A", ""), ("2ème année", "2ème B", ""),
                    ("3ème année", "3ème A", ""), ("3ème année", "3ème B", ""),
                    ("4ème année", "4ème A", ""), ("4ème année", "4ème B", ""),
                    ("5ème année", "5ème A", ""), ("5ème année", "5ème B", ""),
                    ("6ème année", "6ème A", ""), ("6ème année", "6ème B", ""),
                ],
            },
        ],
    },
    {
        "cycle": "secondaire",
        "label": "2ème cycle",
        "groups": [
            {
                "key": "secondaire",
                "label": "7ème – 9ème année",
                "items": [
                    ("7ème année", "7ème A", ""), ("7ème année", "7ème B", ""),
                    ("8ème année", "8ème A", ""), ("8ème année", "8ème B", ""),
                    ("9ème année", "9ème A", ""), ("9ème année", "9ème B", ""),
                ],
            },
        ],
    },
    {
        "cycle": "lycee",
        "label": "Lycée",
        "groups": [
            {
                "key": "lycee-10",
                "label": "10ᵉ ANNÉE",
                "items": [
                    ("10ème année", "10ème Commune", "Tronc commun"),
                ],
            },
            {
                "key": "lycee-11",
                "label": "11ᵉ ANNÉE",
                "items": [
                    ("11ème année", "11ème L", "Littéraire"),
                    ("11ème année", "11ème SES", "Sciences économiques et sociales"),
                    ("11ème année", "11ème S", "Scientifique"),
                ],
            },
            {
                "key": "lycee-terminale",
                "label": "TERMINALE (12ᵉ ANNÉE)",
                "items": [
                    ("12ème année", "TLL", "Littéraire · TLL"),
                    ("12ème année", "TAL", "Littéraire · TAL"),
                    ("12ème année", "TSS", "Scientifique · TSS"),
                    ("12ème année", "TSEco", "Sciences économiques · TSEco"),
                    ("12ème année", "TSExp", "Scientifique · TSExp"),
                    ("12ème année", "TSE", "Scientifique · TSE"),
                ],
            },
            {
                "key": "lycee-sti",
                "label": "FILIÈRES TECHNIQUES — STI",
                "items": [
                    ("12ème année", "TSTI GM", "STI · GM"),
                    ("12ème année", "TSTI GC", "STI · GC"),
                    ("12ème année", "TSTI GMI", "STI · GMI"),
                    ("12ème année", "TSTI GELN", "STI · GELN"),
                    ("12ème année", "TSTI GEN", "STI · GEN"),
                    ("12ème année", "TSTI GEL", "STI · GEL"),
                ],
            },
            {
                "key": "lycee-stg",
                "label": "FILIÈRES TECHNIQUES — STG",
                "items": [
                    ("12ème année", "TSTG CF", "STG · CF"),
                    ("12ème année", "TSTG GCO", "STG · GCO"),
                ],
            },
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




@permission_required('nav.classrooms')
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


@permission_required('nav.classrooms')
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



PARALLEL_LETTERS = tuple('ABCDEFGH')


def _resolve_level(level_name):
    """Résout un niveau du catalogue vers un ``Level`` existant (ou le crée under Lycée).

    Le nom « Terminale » n'existe pas toujours en base : il correspond au niveau
    « 12ème année » utilisé par les inscriptions et le passage de classe.
    """
    name = (level_name or '').strip()
    if not name:
        return None
    level = Level.objects.filter(name__icontains=name).order_by('order').first()
    if level:
        return level
    token = 'Terminale' if 'erminale' in name else next(
        (token for token in ('10', '11', '12') if token in name), None
    )
    if not token:
        return None
    level = Level.objects.filter(name__icontains='12' if token == 'Terminale' else token).order_by('order').first()
    if level:
        return level
    canonical = {'10': '10ème année', '11': '11ème année', '12': '12ème année',
                 'Terminale': '12ème année'}[token]
    cycle = Cycle.objects.filter(code='lycee').first()
    if not cycle:
        return None
    level, _ = Level.objects.get_or_create(
        name=canonical,
        defaults={'cycle': cycle, 'order': {'10': 1, '11': 2, '12': 3,
                                           'Terminale': 3}[token]},
    )
    return level


def _parallel_letters(raw):
    """Lettres de division saisies (ex. « A,B,C ») ; ``['']`` = nom de base only."""
    letters = []
    for char in (raw or '').upper():
        if 'A' <= char <= 'Z' and char not in letters and len(letters) < 10:
            letters.append(char)
    return letters or ['']


@permission_required('academics.classes')
def classroom_bulk_add(request):
    """Sélection multiple de classes du programme Mali (fenêtre existante)."""
    year = get_selected_year(request)
    if not year:
        messages.error(request, "Sélectionnez une année scolaire.")
        return redirect('academics:classroom_list')

    if request.method == 'POST':
        selected = request.POST.getlist('classes')
        letters = _parallel_letters(request.POST.get('parallel'))
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
            level_name, class_name = parts[0].strip(), parts[1].strip()
            serie = (parts[2] if len(parts) > 2 else '')[:50]
            level = _resolve_level(level_name)
            if not level or not class_name:
                continue
            for letter in letters:
                name = f'{class_name} {letter}'.strip()
                # get_or_create : un doublon (nom + année) n'est jamais recréé,
                # et les classes/frais existants ne sont pas écrasés.
                _, was_created = ClassRoom.objects.get_or_create(
                    name=name,
                    academic_year=year,
                    defaults={
                        'level': level,
                        'capacity': capacity,
                        'serie': serie,
                        'inscription_fee': inscription,
                        'tuition_fee': tuition,
                    },
                )
                created += int(was_created)
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
        groups = []
        for group in block['groups']:
            items = []
            for entry in group['items']:
                level_name, class_name, serie = (
                    entry if len(entry) == 3 else (entry[0], entry[1], '')
                )
                already = [
                    letter for letter in PARALLEL_LETTERS
                    if f'{class_name} {letter}' in existing
                ]
                items.append({
                    'level_name': level_name,
                    'class_name': class_name,
                    'serie': serie,
                    'value': f'{level_name}|{class_name}|{serie}',
                    'exists': class_name in existing,
                    'already': ', '.join(already),
                })
            groups.append({'key': group['key'], 'label': group['label'], 'items': items})
        program.append({'label': block['label'], 'cycle': block['cycle'], 'groups': groups})

    ctx = {'program': program, 'selected_year': year, 'parallel_default': 'A',
           'parallel_letters': PARALLEL_LETTERS}
    return render(request, 'academics/classroom_bulk_modal.html', ctx)


@permission_required('academics.classes')
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


@permission_required('academics.classes')
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


@permission_required('academics.classes')
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


@permission_required('academics.classes')
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

