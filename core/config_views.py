"""Configuration hors admin : années, matières, périodes, types, frais, salles, utilisateurs."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .permissions import role_required, is_config_role, get_role


@login_required
def config_home(request):
    if not is_config_role(request.user) and not request.user.is_superuser:
        messages.error(request, "Accès réservé à l'administrateur / directeur.")
        return redirect('core:dashboard')
    return render(request, 'core/config_home.html', {'role': get_role(request.user)})


# ---------- Années scolaires ----------
@role_required('admin', 'directeur')
def year_list(request):
    from academics.models import AcademicYear
    years = AcademicYear.objects.all().order_by('-start_date')
    return render(request, 'core/config_years.html', {'years': years})


@role_required('admin', 'directeur')
def year_save(request):
    from academics.models import AcademicYear
    if request.method == 'POST':
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        start = request.POST.get('start_date') or None
        end = request.POST.get('end_date') or None
        is_current = request.POST.get('is_current') == 'on'
        if not name:
            messages.error(request, 'Nom requis.')
            return redirect('core:config_years')
        if pk:
            # Edition : vérifier que le nom n'appartient pas à une autre année
            if AcademicYear.objects.filter(name=name).exclude(pk=pk).exists():
                messages.error(request, f'Une année scolaire portant le nom « {name} » existe déjà.')
                return redirect('core:config_years')
            y = get_object_or_404(AcademicYear, pk=pk)
            y.name = name
            y.start_date = start
            y.end_date = end
            y.is_current = is_current
            y.save()
            if is_current:
                from core.year_context import set_selected_year
                set_selected_year(request, y.pk)
            messages.success(request, 'Année mise à jour.')
        else:
            # Création : vérifier l'unicité du nom
            if AcademicYear.objects.filter(name=name).exists():
                messages.error(request, f'Une année scolaire portant le nom « {name} » existe déjà.')
                return redirect('core:config_years')
            y = AcademicYear.objects.create(
                name=name, start_date=start, end_date=end, is_current=is_current
            )
            if is_current:
                from core.year_context import set_selected_year
                set_selected_year(request, y.pk)
            messages.success(request, 'Année créée.')
    return redirect('core:config_years')


@role_required('admin', 'directeur')
@require_POST
def year_set_current(request, pk):
    from academics.models import AcademicYear
    from core.year_context import set_selected_year
    AcademicYear.objects.update(is_current=False)
    y = get_object_or_404(AcademicYear, pk=pk)
    y.is_current = True
    y.save(update_fields=['is_current'])
    # Appliquer partout : sélecteur d'année = année en cours
    set_selected_year(request, y.pk)
    messages.success(request, f"{y.name} est maintenant l'année en cours (appliquée partout).")
    return redirect('core:config_years')


# ---------- Matières ----------
@role_required('admin', 'directeur')
def subject_list(request):
    from academics.models import Subject
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'core/config_subjects.html', {'subjects': subjects})


@role_required('admin', 'directeur')
def subject_save(request):
    from academics.models import Subject
    if request.method == 'POST':
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        coef = request.POST.get('coefficient') or 1
        code = request.POST.get('code', '').strip()
        if not name or not code:
            messages.error(request, 'Nom et code requis.')
            return redirect('core:config_subjects')
        if pk:
            s = get_object_or_404(Subject, pk=pk)
            s.name = name
            s.code = code
            s.coefficient = coef
            s.save()
            messages.success(request, 'Matière mise à jour.')
        else:
            Subject.objects.create(name=name, code=code, coefficient=coef)
            messages.success(request, 'Matière créée.')
    return redirect('core:config_subjects')


@role_required('admin', 'directeur')
@require_POST
def subject_delete(request, pk):
    from academics.models import Subject
    get_object_or_404(Subject, pk=pk).delete()
    messages.success(request, 'Matière supprimée.')
    return redirect('core:config_subjects')


# ---------- Périodes ----------
@role_required('admin', 'directeur')
def period_list(request):
    from grades.models import Period
    from academics.models import AcademicYear
    year = AcademicYear.objects.filter(is_current=True).first()
    periods = Period.objects.filter(academic_year=year).order_by('start_date') if year else Period.objects.none()
    return render(request, 'core/config_periods.html', {
        'periods': periods, 'current_year': year,
        'period_types': getattr(Period, 'PERIOD_TYPE_CHOICES', Period._meta.get_field('period_type').choices),
    })


@role_required('admin', 'directeur')
def period_save(request):
    from grades.models import Period
    from academics.models import AcademicYear
    if request.method == 'POST':
        year = AcademicYear.objects.filter(is_current=True).first()
        if not year:
            messages.error(request, 'Créez d\'abord une année scolaire en cours.')
            return redirect('core:config_periods')
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        ptype = request.POST.get('period_type', 'trimestre')
        start = request.POST.get('start_date') or None
        end = request.POST.get('end_date') or None
        if not name:
            messages.error(request, 'Nom requis.')
            return redirect('core:config_periods')
        if pk:
            p = get_object_or_404(Period, pk=pk)
            p.name = name
            p.period_type = ptype
            p.start_date = start
            p.end_date = end
            p.save()
            messages.success(request, 'Période mise à jour.')
        else:
            Period.objects.create(
                name=name, period_type=ptype, start_date=start, end_date=end,
                academic_year=year,
            )
            messages.success(request, 'Période créée.')
    return redirect('core:config_periods')


# ---------- Types d'évaluation ----------
@role_required('admin', 'directeur')
def assessment_type_list(request):
    from grades.models import AssessmentType
    types = AssessmentType.objects.all().order_by('name')
    return render(request, 'core/config_assessment_types.html', {'types': types})


@role_required('admin', 'directeur')
def assessment_type_save(request):
    from grades.models import AssessmentType
    if request.method == 'POST':
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        if not name:
            messages.error(request, 'Nom requis.')
            return redirect('core:config_assessment_types')
        if pk:
            t = get_object_or_404(AssessmentType, pk=pk)
            t.name = name
            if hasattr(t, 'code'):
                t.code = code
            t.save()
            messages.success(request, 'Type mis à jour.')
        else:
            kwargs = {'name': name}
            if 'code' in [f.name for f in AssessmentType._meta.fields]:
                kwargs['code'] = code
            AssessmentType.objects.create(**kwargs)
            messages.success(request, 'Type créé.')
    return redirect('core:config_assessment_types')


# ---------- Types de frais ----------
@role_required('admin', 'directeur')
def fee_type_list(request):
    from finance.models import FeeType
    types = FeeType.objects.all().order_by('name')
    return render(request, 'core/config_fee_types.html', {'types': types})


@role_required('admin', 'directeur')
def fee_type_save(request):
    from finance.models import FeeType
    if request.method == 'POST':
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        amount = request.POST.get('default_amount') or 0
        if not name:
            messages.error(request, 'Nom requis.')
            return redirect('core:config_fee_types')
        fields = {f.name for f in FeeType._meta.fields}
        if pk:
            t = get_object_or_404(FeeType, pk=pk)
            t.name = name
            if 'default_amount' in fields:
                t.default_amount = amount
            t.save()
            messages.success(request, 'Type de frais mis à jour.')
        else:
            kwargs = {'name': name}
            if 'default_amount' in fields:
                kwargs['default_amount'] = amount
            if 'is_active' in fields:
                kwargs['is_active'] = True
            FeeType.objects.create(**kwargs)
            messages.success(request, 'Type de frais créé.')
    return redirect('core:config_fee_types')


# ---------- Salles & créneaux ----------
@role_required('admin', 'directeur')
def room_list(request):
    from timetable.models import Room, TimeSlot
    return render(request, 'core/config_rooms.html', {
        'rooms': Room.objects.all(),
        'slots': TimeSlot.objects.all().order_by('start_time'),
    })


@role_required('admin', 'directeur')
def room_save(request):
    from timetable.models import Room
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            Room.objects.create(name=name)
            messages.success(request, 'Salle créée.')
    return redirect('core:config_rooms')


@role_required('admin', 'directeur')
def slot_save(request):
    from timetable.models import TimeSlot
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        order = request.POST.get('order') or 1
        if name and start and end:
            TimeSlot.objects.create(name=name, start_time=start, end_time=end, order=order)
            messages.success(request, 'Créneau créé.')
    return redirect('core:config_rooms')


# ---------- Utilisateurs ----------
@role_required('admin', 'directeur')
def user_list(request):
    from accounts.models import Profile
    q = request.GET.get('q', '').strip()
    role_f = request.GET.get('role', '')
    users = User.objects.select_related('profile').order_by('username')
    if q:
        from django.db.models import Q
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) |
            Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if role_f:
        users = users.filter(profile__role=role_f)
    return render(request, 'core/config_users.html', {
        'users': users,
        'roles': Profile.ROLE_CHOICES,
        'q': q,
        'role_f': role_f,
    })


@role_required('admin', 'directeur')
def user_save(request):
    from accounts.models import Profile
    if request.method == 'POST':
        pk = request.POST.get('id')
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'secretaire')
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        if pk:
            u = get_object_or_404(User, pk=pk)
            if u.is_superuser and request.user != u and not request.user.is_superuser:
                messages.error(request, 'Impossible de modifier un super-admin.')
                return redirect('core:config_users')
            u.email = email
            u.first_name = first_name
            u.last_name = last_name
            # Admin / directeur → accès staff utile
            if role in ('admin', 'directeur'):
                u.is_staff = True
            u.save()
            Profile.objects.update_or_create(
                user=u, defaults={'role': role, 'phone': phone}
            )
            if password:
                u.set_password(password)
                u.save()
            messages.success(request, 'Utilisateur mis à jour.')
        else:
            if not username or not password:
                messages.error(request, 'Identifiant et mot de passe requis.')
                return redirect('core:config_users')
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Cet identifiant existe déjà.')
                return redirect('core:config_users')
            u = User.objects.create_user(
                username=username, password=password, email=email,
                first_name=first_name, last_name=last_name,
                is_staff=(role in ('admin', 'directeur')),
            )
            Profile.objects.update_or_create(
                user=u, defaults={'role': role, 'phone': phone}
            )
            # Lier automatiquement fiche Enseignant / Parent si possible
            link_msg = _try_link_user_profile(u, role)
            messages.success(
                request,
                f'Utilisateur « {username} » créé.' + (f' {link_msg}' if link_msg else '')
            )
    return redirect('core:config_users')


def _try_link_user_profile(user, role):
    """Attache Teacher.user ou Parent.user si une fiche correspond (nom)."""
    try:
        if role == 'enseignant':
            from teachers.models import Teacher
            if getattr(user, 'teacher', None):
                return ''
            t = Teacher.objects.filter(
                last_name__iexact=user.last_name or '',
                first_name__iexact=user.first_name or '',
                user__isnull=True,
            ).first()
            if not t and user.last_name:
                t = Teacher.objects.filter(last_name__iexact=user.last_name, user__isnull=True).first()
            if t:
                t.user = user
                t.save(update_fields=['user'])
                return f'Lié à l\'enseignant {t}.'
            return 'Aucun enseignant trouvé à lier (même nom) — liez-le dans Enseignants ou admin.'
        if role == 'parent':
            from students.models import Parent
            if getattr(user, 'parent_profile', None):
                return ''
            p = Parent.objects.filter(
                last_name__iexact=user.last_name or '',
                first_name__iexact=user.first_name or '',
                user__isnull=True,
            ).first()
            if not p and user.last_name:
                p = Parent.objects.filter(last_name__iexact=user.last_name, user__isnull=True).first()
            if p:
                p.user = user
                p.save(update_fields=['user'])
                return f'Lié au parent {p}.'
            return 'Aucun parent trouvé à lier (même nom) — liez-le dans Parents ou admin.'
    except Exception as e:
        return f'(liaison: {e})'
    return ''



@role_required('admin', 'directeur')
@require_POST
def user_toggle_active(request, pk):
    u = get_object_or_404(User, pk=pk)
    if u == request.user:
        messages.error(request, 'Vous ne pouvez pas vous désactiver vous-même.')
        return redirect('core:config_users')
    if u.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Impossible de modifier un super-admin.')
        return redirect('core:config_users')
    u.is_active = not u.is_active
    u.save()
    messages.success(
        request,
        f'{u.username} {"activé" if u.is_active else "désactivé"}.'
    )
    return redirect('core:config_users')


@role_required('admin', 'directeur')
@require_POST
def user_reset_password(request, pk):
    u = get_object_or_404(User, pk=pk)
    new_pwd = request.POST.get('password', '').strip()
    if len(new_pwd) < 4:
        messages.error(request, 'Mot de passe trop court (min. 4 caractères).')
        return redirect('core:config_users')
    u.set_password(new_pwd)
    u.save()
    messages.success(request, f'Mot de passe de {u.username} réinitialisé.')
    return redirect('core:config_users')


# ---------- Cycles & Niveaux ----------
@role_required('admin', 'directeur')
def cycle_level_list(request):
    from academics.models import Cycle, Level
    cycles = Cycle.objects.prefetch_related('levels').order_by('order', 'name')
    return render(request, 'core/config_cycles_levels.html', {
        'cycles': cycles,
        'cycle_codes': Cycle.CYCLE_CHOICES,
    })


@role_required('admin', 'directeur')
@require_POST
def cycle_save(request):
    from academics.models import Cycle
    pk = request.POST.get('id')
    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip() or 'autre'
    order = request.POST.get('order') or 0
    if not name:
        messages.error(request, 'Nom du cycle requis.')
        return redirect('core:config_cycles')
    try:
        order = int(order)
    except Exception:
        order = 0
    if pk:
        c = get_object_or_404(Cycle, pk=pk)
        c.name = name
        c.code = code
        c.order = order
        c.save()
        messages.success(request, 'Cycle mis à jour.')
    else:
        if Cycle.objects.filter(code=code).exists():
            messages.error(request, f'Code « {code} » déjà utilisé.')
            return redirect('core:config_cycles')
        Cycle.objects.create(name=name, code=code, order=order)
        messages.success(request, 'Cycle créé.')
    return redirect('core:config_cycles')


@role_required('admin', 'directeur')
@require_POST
def level_save(request):
    from academics.models import Cycle, Level
    pk = request.POST.get('id')
    name = request.POST.get('name', '').strip()
    cycle_id = request.POST.get('cycle')
    order = request.POST.get('order') or 0
    if not name or not cycle_id:
        messages.error(request, 'Nom et cycle requis.')
        return redirect('core:config_cycles')
    try:
        order = int(order)
    except Exception:
        order = 0
    cycle = get_object_or_404(Cycle, pk=cycle_id)
    if pk:
        lv = get_object_or_404(Level, pk=pk)
        lv.name = name
        lv.cycle = cycle
        lv.order = order
        lv.save()
        messages.success(request, 'Niveau mis à jour.')
    else:
        Level.objects.create(name=name, cycle=cycle, order=order)
        messages.success(request, 'Niveau créé.')
    return redirect('core:config_cycles')


@role_required('admin', 'directeur')
@require_POST
def level_delete(request, pk):
    from academics.models import Level
    lv = get_object_or_404(Level, pk=pk)
    try:
        lv.delete()
        messages.success(request, 'Niveau supprimé.')
    except Exception as e:
        messages.error(request, f'Impossible de supprimer : {e}')
    return redirect('core:config_cycles')


# ---------- Affectations matière / enseignant / classe ----------
@role_required('admin', 'directeur', 'secretaire')
def assignment_list(request):
    from academics.models import SubjectAssignment, ClassRoom, Subject
    from teachers.models import Teacher
    from core.year_context import get_selected_year

    year = get_selected_year(request)
    qs = SubjectAssignment.objects.select_related(
        'teacher', 'subject', 'classroom', 'classroom__level', 'classroom__academic_year'
    )
    if year:
        qs = qs.filter(classroom__academic_year=year)
    classroom_id = request.GET.get('classroom', '')
    if classroom_id:
        qs = qs.filter(classroom_id=classroom_id)
    assignments = qs.order_by('classroom__name', 'subject__name')
    classrooms = ClassRoom.objects.select_related('level', 'academic_year').order_by('name')
    if year:
        classrooms = classrooms.filter(academic_year=year)
    return render(request, 'core/config_assignments.html', {
        'assignments': assignments,
        'classrooms': classrooms,
        'subjects': Subject.objects.filter(is_active=True).order_by('name'),
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'classroom_id': classroom_id,
        'selected_year': year,
    })


@role_required('admin', 'directeur', 'secretaire')
@require_POST
def assignment_save(request):
    from academics.models import SubjectAssignment, ClassRoom, Subject
    from teachers.models import Teacher

    teacher_id = request.POST.get('teacher')
    subject_id = request.POST.get('subject')
    classroom_id = request.POST.get('classroom')
    hours = request.POST.get('hours_per_week') or 2
    try:
        hours = int(hours)
    except Exception:
        hours = 2
    if not (teacher_id and subject_id and classroom_id):
        messages.error(request, 'Enseignant, matière et classe requis.')
        return redirect('core:config_assignments')
    obj, created = SubjectAssignment.objects.update_or_create(
        teacher_id=teacher_id,
        subject_id=subject_id,
        classroom_id=classroom_id,
        defaults={'hours_per_week': hours},
    )
    messages.success(request, 'Affectation enregistrée.' if created else 'Affectation mise à jour.')
    return redirect('core:config_assignments')


@role_required('admin', 'directeur', 'secretaire')
@require_POST
def assignment_delete(request, pk):
    from academics.models import SubjectAssignment
    a = get_object_or_404(SubjectAssignment, pk=pk)
    a.delete()
    messages.success(request, 'Affectation supprimée.')
    return redirect('core:config_assignments')


@role_required('admin', 'directeur')
def permissions_matrix(request):
    from core.permissions import (
        PERMISSIONS, PERMISSION_GROUPS, ROLE_LABELS, can, get_role,
    )
    roles = list(ROLE_LABELS.items())
    # matrix[perm] = set of roles
    role_texts = {
        'admin': [
            'Tout l\'application',
            'Configuration et utilisateurs',
            'Admin technique Django',
        ],
        'directeur': [
            'Tout l\'application (comme admin)',
            'Configuration et utilisateurs',
            'Sans admin technique sauf si superuser',
        ],
        'secretaire': [
            'Élèves, parents, classes, enseignants',
            'Notes, bulletins, absences',
            'Paiements et factures',
            'Annonces et messages',
            'Passage / redoublement',
            'Exports Excel',
            'Pas de config structure / utilisateurs',
        ],
        'enseignant': [
            'Ses classes seulement',
            'Saisie notes et absences',
            'Bulletins de ses classes',
            'Emploi du temps',
            'Pas de finance ni configuration',
        ],
        'parent': [
            'Ses enfants seulement',
            'Bulletins et absences',
            'Consultation finance (soldes)',
            'Annonces et messages',
        ],
        'eleve': [
            'Emploi du temps',
            'Annonces',
        ],
    }
    # Build table rows
    table = []
    for group in PERMISSION_GROUPS:
        rows = []
        for key, label in group['items']:
            allowed = set(PERMISSIONS.get(key, []))
            cells = []
            for code, _ in roles:
                if code in ('admin', 'directeur'):
                    cells.append(True)
                else:
                    cells.append(code in allowed)
            rows.append({'label': label, 'cells': cells})
        table.append({'title': group['title'], 'rows': rows})
    role_cards = [
        {'code': code, 'label': label, 'lines': role_texts.get(code, [])}
        for code, label in roles
    ]
    return render(request, 'core/config_permissions.html', {
        'roles': roles,
        'table': table,
        'role_cards': role_cards,
        'user_role_label': ROLE_LABELS.get(get_role(request.user), ''),
    })


@role_required('admin', 'directeur', 'secretaire')
def liaisons_dashboard(request):
    """Vue d'ensemble des liaisons manquantes / cassées."""
    from teachers.models import Teacher
    from students.models import Student, Parent, ParentStudent, Enrollment
    from academics.models import ClassRoom, ClassSubject, SubjectAssignment, Subject
    from core.year_context import get_selected_year

    year = get_selected_year(request)

    teachers = Teacher.objects.all()
    t_no_user = teachers.filter(user__isnull=True)
    t_no_assign = teachers.exclude(
        id__in=SubjectAssignment.objects.values_list('teacher_id', flat=True)
    ).filter(is_active=True)

    parents = Parent.objects.all()
    p_no_user = parents.filter(user__isnull=True)
    p_no_child = parents.exclude(
        id__in=ParentStudent.objects.values_list('parent_id', flat=True)
    )

    students = Student.objects.filter(status='actif')
    s_no_user = students.filter(user__isnull=True)
    s_no_enroll = students.exclude(
        id__in=Enrollment.objects.filter(is_active=True).values_list('student_id', flat=True)
    )
    if year:
        s_no_enroll_year = students.exclude(
            id__in=Enrollment.objects.filter(
                academic_year=year, is_active=True
            ).values_list('student_id', flat=True)
        )
    else:
        s_no_enroll_year = s_no_enroll

    rooms = ClassRoom.objects.select_related('level', 'academic_year')
    if year:
        rooms = rooms.filter(academic_year=year)
    rooms_no_subjects = []
    rooms_no_main = []
    def level_is_institute(level):
        """Retourne True si le niveau appartient au cycle primaire (instituteur requis)."""
        if not level:
            return False
        try:
            code = level.cycle.code if level.cycle_id else ''
            return code in ('primaire',)
        except Exception:
            return False

    for c in rooms:
        n_subj = ClassSubject.objects.filter(classroom=c).count()
        if n_subj == 0:
            rooms_no_subjects.append(c)
        if level_is_institute(c.level) and not c.main_teacher_id:
            rooms_no_main.append(c)

    n_subjects = Subject.objects.filter(is_active=True).count()
    n_assignments = SubjectAssignment.objects.count()
    if year:
        n_assignments = SubjectAssignment.objects.filter(
            classroom__academic_year=year
        ).count()

    ctx = {
        'selected_year': year,
        'stats': {
            'teachers': teachers.count(),
            'teachers_no_user': t_no_user.count(),
            'teachers_no_assign': t_no_assign.count(),
            'parents': parents.count(),
            'parents_no_user': p_no_user.count(),
            'parents_no_child': p_no_child.count(),
            'students': students.count(),
            'students_no_user': s_no_user.count(),
            'students_no_enroll': s_no_enroll_year.count(),
            'rooms': rooms.count(),
            'rooms_no_subjects': len(rooms_no_subjects),
            'rooms_no_main': len(rooms_no_main),
            'subjects': n_subjects,
            'assignments': n_assignments,
        },
        't_no_user': t_no_user[:30],
        't_no_assign': t_no_assign[:30],
        'p_no_user': p_no_user[:30],
        'p_no_child': p_no_child[:30],
        's_no_user': s_no_user[:30],
        's_no_enroll': s_no_enroll_year[:30],
        'rooms_no_subjects': rooms_no_subjects[:30],
        'rooms_no_main': rooms_no_main[:30],
    }
    return render(request, 'core/config_liaisons.html', ctx)


@role_required('admin', 'directeur')
@require_POST
def liaisons_fix_accounts(request):
    """Crée les comptes manquants enseignant / élève / parent."""
    from core.account_sync import (
        ensure_user_for_teacher, ensure_user_for_student, ensure_user_for_parent,
    )
    from teachers.models import Teacher
    from students.models import Student, Parent

    n = 0
    for t in Teacher.objects.filter(user__isnull=True):
        ensure_user_for_teacher(t)
        n += 1
    for s in Student.objects.filter(user__isnull=True):
        ensure_user_for_student(s)
        n += 1
    for p in Parent.objects.filter(user__isnull=True):
        ensure_user_for_parent(p)
        n += 1
    messages.success(request, f'{n} compte(s) créé(s) ou mis à jour.')
    return redirect('core:config_liaisons')
