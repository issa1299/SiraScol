from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from academics.models import ClassRoom, SubjectAssignment
from core.account_sync import ensure_user_for_teacher
from core.permissions import permission_required, can, get_role, get_linked_teacher
from core.year_context import get_selected_year

from .forms import TeacherForm, AttendanceForm, ContractForm, SalaryForm, DocumentForm
from .models import Teacher, StaffAttendance, StaffContract, StaffSalary, StaffDocument


def _teacher_or_403(request, pk):
    """Enseignant : uniquement sa propre fiche. RH : tout le monde."""
    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        me = get_linked_teacher(request.user)
        if not me or me.pk != pk:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, "Vous ne pouvez consulter que votre propre fiche.")
            if me:
                return redirect('teachers:detail', pk=me.pk)
            return redirect('core:dashboard')
    return None



def _staff_stats():
    qs = Teacher.objects.all()
    today = timezone.now().date()
    expiring = StaffContract.objects.filter(
        status='actif', end_date__isnull=False,
        end_date__lte=today + timedelta(days=30), end_date__gte=today,
    ).count()
    att_today = StaffAttendance.objects.filter(date=today)
    return {
        'total': qs.count(),
        'enseignants': qs.filter(category='enseignant').count(),
        'admin': qs.filter(category='admin').count(),
        'service': qs.filter(category='service').count(),
        'actifs': qs.filter(status='actif').count(),
        'absents_today': att_today.filter(status='absent').count(),
        'retards_today': att_today.filter(status='retard').count(),
        'conges': qs.filter(status='conge').count(),
        'contrats_expirent': expiring,
        'salaires_attente': StaffSalary.objects.filter(status='en_attente').count(),
    }


@login_required
def personnel_dashboard(request):
    if not can(request.user, 'personnel.dashboard'):
        if get_role(request.user) == 'enseignant':
            me = get_linked_teacher(request.user)
            if me:
                return redirect('teachers:detail', pk=me.pk)
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    stats = _staff_stats()
    today = timezone.now().date()
    recent_att = StaffAttendance.objects.filter(date=today).select_related('staff')[:15]
    expiring = StaffContract.objects.filter(
        status='actif', end_date__isnull=False,
        end_date__lte=today + timedelta(days=45), end_date__gte=today,
    ).select_related('staff').order_by('end_date')[:10]
    return render(request, 'teachers/personnel_dashboard.html', {
        'stats': stats,
        'recent_att': recent_att,
        'expiring': expiring,
        'section': 'dashboard',
    })


@login_required
def teacher_list(request):
    if not can(request.user, 'personnel.list'):
        # Enseignant → sa fiche
        if get_role(request.user) == 'enseignant':
            me = get_linked_teacher(request.user)
            if me:
                return redirect('teachers:detail', pk=me.pk)
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    qs = Teacher.objects.all().order_by('last_name', 'first_name')
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(
            Q(matricule__icontains=q) | Q(first_name__icontains=q) |
            Q(last_name__icontains=q) | Q(speciality__icontains=q) |
            Q(phone__icontains=q) | Q(function__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    # Compat ancien filtre active=
    active = request.GET.get('active', '')
    if active == '1':
        qs = qs.filter(status='actif')
    elif active == '0':
        qs = qs.exclude(status='actif')

    teachers = Paginator(qs, 24).get_page(request.GET.get('page'))
    return render(request, 'teachers/teacher_list.html', {
        'teachers': teachers,
        'q': q,
        'category': category,
        'status': status,
        'active': active,
        'stats': _staff_stats(),
        'section': category or 'all',
        'categories': Teacher.CATEGORY_CHOICES,
        'statuses': Teacher.STATUS_CHOICES,
    })


@login_required
def teacher_detail(request, pk):
    blocked = _teacher_or_403(request, pk)
    if blocked is not None:
        return blocked
    # Enseignant peut voir sa fiche ; RH avec personnel.view
    role = get_role(request.user)
    if role == 'enseignant':
        pass  # déjà filtré
    elif not can(request.user, 'personnel.view'):
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    teacher = get_object_or_404(Teacher, pk=pk)
    assignments = SubjectAssignment.objects.filter(teacher=teacher).select_related(
        'subject', 'classroom', 'classroom__level'
    ).order_by('classroom__name', 'subject__name')
    main_classes = ClassRoom.objects.filter(main_teacher=teacher).select_related('level')
    contracts = teacher.contracts.all()[:10]
    salaries = teacher.salaries.all()[:12]
    documents = teacher.documents.all()[:20]
    attendances = teacher.attendances.all()[:15]
    ctx = {
        'teacher': teacher,
        'assignments': assignments,
        'main_classes': main_classes,
        'contracts': contracts,
        'salaries': salaries,
        'documents': documents,
        'attendances': attendances,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'teachers/teacher_detail_modal.html', ctx)
    return render(request, 'teachers/teacher_detail.html', ctx)


MATRICULE_PREFIXES = {
    'enseignant': 'ENS',
    'admin': 'ADM',
    'service': 'SRV',
}
DEFAULT_MATRICULE_PREFIX = 'PER'


def prefix_for_category(category):
    """Préfixe de matricule correspondant à la catégorie du personnel."""
    return MATRICULE_PREFIXES.get((category or '').strip().lower(), DEFAULT_MATRICULE_PREFIX)


def _next_matricule(prefix='ENS'):
    """Prochain matricule libre, numéroté correctement même au-delà de 999."""
    import re
    year = date.today().year
    base = f'{prefix}-{year}-'
    max_n = 0
    for value in Teacher.objects.filter(
        matricule__startswith=base
    ).values_list('matricule', flat=True):
        match = re.search(r'-(\d+)$', value or '')
        if match:
            max_n = max(max_n, int(match.group(1)))
    candidate = f'{base}{max_n + 1:04d}'
    # Sécurité : éviter toute collision résiduelle (matricule libre saisi à la main).
    while Teacher.objects.filter(matricule=candidate).exists():
        max_n += 1
        candidate = f'{base}{max_n + 1:04d}'
    return candidate


@login_required
def next_matricule(request):
    """Matricule proposé selon la catégorie (pour les formulaires)."""
    from django.http import JsonResponse
    category = request.GET.get('category', 'enseignant')
    return JsonResponse({'matricule': _next_matricule(prefix_for_category(category))})


@login_required
def teacher_create(request):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not can(request.user, 'personnel.create'):
        if is_modal:
            from django.http import HttpResponse
            return HttpResponse(
                '<p class="text-red-600 text-sm p-4">Accès refusé pour votre rôle. '
                'Seuls Directeur / Secrétaire / Admin peuvent ajouter du personnel.</p>'
            )
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    with_account = request.GET.get('with_account', request.POST.get('with_account', '1')) != '0'
    if request.method == 'POST':
        # Nettoyer champs vides qui cassent la validation
        data = request.POST.copy()
        if not data.get('email'):
            data['email'] = ''
        if not data.get('base_salary'):
            data['base_salary'] = '0'
        if not data.get('category'):
            data['category'] = 'enseignant'
        form = TeacherForm(data, request.FILES)
        if form.is_valid():
            try:
                teacher = form.save(commit=False)
                # Le matricule est propre au type de personnel et toujours unique.
                expected = prefix_for_category(form.cleaned_data.get('category'))
                mat = (teacher.matricule or '').strip()
                wrong_prefix = not mat.upper().startswith(expected + '-')
                duplicate = Teacher.objects.filter(matricule=mat).exists()
                if not mat or wrong_prefix or duplicate:
                    teacher.matricule = _next_matricule(expected)
                teacher.has_account = bool(with_account)
                teacher.save()
                msg = f"Personnel {teacher} créé (matricule {teacher.matricule})."
                if with_account:
                    user, created, pwd = ensure_user_for_teacher(teacher)
                    if created and pwd:
                        msg += f" Compte : {user.username} / mdp : {pwd}"
                messages.success(request, msg)
                if teacher.category == 'enseignant':
                    if is_modal:
                        return _render_assign_modal(request, teacher)
                    return redirect('teachers:assign', pk=teacher.pk)
                if is_modal:
                    return render(request, 'teachers/teacher_create_done.html', {'teacher': teacher, 'msg': msg})
                return redirect('teachers:detail', pk=teacher.pk)
            except Exception as e:
                if is_modal:
                    from django.http import HttpResponse
                    return HttpResponse(
                        f'<p class="text-red-600 text-sm p-3">Erreur à l\'enregistrement : {e}</p>'
                        f'<p class="text-xs text-slate-500">Vérifiez matricule unique, sexe, nom/prénom.</p>'
                    )
                messages.error(request, f"Erreur : {e}")
        elif is_modal:
            # renvoyer le formulaire avec erreurs
            from django.urls import reverse
            form_template = (
                'teachers/teacher_form_with_account.html' if with_account
                else 'teachers/teacher_form_without_account.html'
            )
            ctx = {
                'form': form,
                'form_template': form_template,
                'form_action': reverse('teachers:create') + ('?with_account=0' if not with_account else '?with_account=1'),
                'title': 'Nouveau membre',
                'with_account': with_account,
            }
            return render(request, form_template, ctx)
    else:
        cat = request.GET.get('category', 'enseignant')
        prefix = prefix_for_category(cat)
        form = TeacherForm(initial={
            'status': 'actif',
            'category': cat,
            'matricule': _next_matricule(prefix),
            'hire_date': date.today().isoformat(),
            'function': {'enseignant': 'Enseignant', 'admin': 'Administratif', 'service': 'Service'}.get(cat, ''),
        })
    from django.urls import reverse
    action = reverse('teachers:create') + ('?with_account=0' if not with_account else '?with_account=1')
    form_template = (
        'teachers/teacher_form_with_account.html' if with_account
        else 'teachers/teacher_form_without_account.html'
    )
    ctx = {
        'form': form,
        'form_template': form_template,
        'form_action': action,
        'title': 'Nouveau membre (avec compte)' if with_account else 'Ajouter personnel (sans compte)',
        'with_account': with_account,
    }
    if is_modal:
        return render(request, form_template, ctx)
    return render(request, 'teachers/teacher_form_page.html', ctx)


@login_required
def teacher_edit(request, pk):
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not can(request.user, 'personnel.edit'):
        if is_modal:
            from django.http import HttpResponse
            return HttpResponse('<p class="text-red-600 text-sm p-4">Accès refusé. Connectez-vous en Directeur / Secrétaire / Admin.</p>')
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        data = request.POST.copy()
        if not data.get('email'):
            data['email'] = ''
        if not data.get('base_salary'):
            data['base_salary'] = '0'
        form = TeacherForm(data, request.FILES, instance=teacher)
        if form.is_valid():
            try:
                form.save()
                # sync compte lié
                if teacher.user_id:
                    from core.account_sync import ensure_user_for_teacher
                    ensure_user_for_teacher(teacher)
                messages.success(request, 'Fiche mise à jour.')
                if is_modal:
                    from django.http import HttpResponse
                    return HttpResponse(
                        '<p class="text-emerald-700 text-sm p-4 font-semibold">✓ Fiche mise à jour.</p>'
                        '<a href="/enseignants/" class="text-blue-600 text-sm underline">Retour à la liste</a>'
                    )
                return redirect('teachers:list')
            except Exception as e:
                messages.error(request, f'Erreur : {e}')
        else:
            messages.error(request, 'Corrigez les erreurs du formulaire.')
    else:
        form = TeacherForm(instance=teacher)
    from django.urls import reverse
    ctx = {
        'form': form,
        'form_action': reverse('teachers:edit', args=[pk]),
        'title': f'Modifier — {teacher}',
        'teacher': teacher,
        'with_account': False,
    }
    if is_modal:
        return render(request, form_template, ctx)
    return render(request, 'teachers/teacher_form_page.html', ctx)


@login_required
def _classrooms_for_cycle(request, cycle_code):
    """Classes de l'année filtrées par cycle (primaire / secondaire / lycee)."""
    year = get_selected_year(request)
    qs = ClassRoom.objects.select_related('level', 'level__cycle')
    if year:
        qs = qs.filter(academic_year=year)
    if cycle_code == 'primaire':
        qs = qs.filter(level__cycle__code__in=['primaire', 'prescolaire', 'maternelle'])
    elif cycle_code == 'secondaire':
        qs = qs.filter(level__cycle__code__in=['secondaire', 'college'])
    elif cycle_code == 'lycee':
        qs = qs.filter(level__cycle__code__in=['lycee'])
    return qs.order_by('level__order', 'name')


def _render_assign_modal(request, teacher, cycle=None):
    from academics.models import Subject
    cycle = cycle or request.GET.get('cycle') or request.POST.get('cycle') or ''
    classrooms = _classrooms_for_cycle(request, cycle) if cycle else ClassRoom.objects.none()
    subjects = Subject.objects.all().order_by('name')
    if hasattr(Subject, 'is_active'):
        subjects = subjects.filter(is_active=True)
    # Filtrer matières par cycle si M2M
    if cycle and hasattr(subjects.model, 'cycles'):
        try:
            subjects = subjects.filter(cycles__code=cycle).distinct()
        except Exception:
            pass
    assignments = SubjectAssignment.objects.filter(teacher=teacher).select_related(
        'classroom', 'subject'
    )
    return render(request, 'teachers/teacher_assign_modal.html', {
        'teacher': teacher,
        'cycle': cycle,
        'classrooms': classrooms,
        'subjects': subjects,
        'assignments': assignments,
    })


@login_required
def teacher_assign(request, pk):
    if not can(request.user, 'personnel.assign'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    from academics.models import Subject, ClassSubject
    teacher = get_object_or_404(Teacher, pk=pk)
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if teacher.category != 'enseignant':
        msg = 'Les affectations (classes / matières) sont réservées aux enseignants.'
        if is_modal:
            from django.http import HttpResponse
            return HttpResponse(f'<p class="text-amber-700 text-sm p-4">{msg}</p>')
        messages.warning(request, msg)
        return redirect('teachers:detail', pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', 'add')
        if action == 'delete':
            aid = request.POST.get('assignment_id')
            SubjectAssignment.objects.filter(pk=aid, teacher=teacher).delete()
            messages.success(request, 'Affectation retirée.')
            if is_modal:
                return _render_assign_modal(request, teacher, request.POST.get('cycle'))
            return redirect('teachers:assign', pk=pk)

        cycle = request.POST.get('cycle', '')
        mode = request.POST.get('mode', 'subjects')  # principal | subjects

        if mode == 'principal':
            # Primaire : prof principal d'une ou plusieurs classes
            class_ids = request.POST.getlist('classrooms')
            n = 0
            for cid in class_ids:
                try:
                    cr = ClassRoom.objects.get(pk=cid)
                except ClassRoom.DoesNotExist:
                    continue
                cr.main_teacher = teacher
                cr.save(update_fields=['main_teacher'])
                # Affecter toutes les matières de la classe
                for cs in ClassSubject.objects.filter(classroom=cr).select_related('subject'):
                    SubjectAssignment.objects.get_or_create(
                        teacher=teacher, classroom=cr, subject=cs.subject
                    )
                # Si aucune ClassSubject, affecter toutes les matières du cycle primaire
                if not ClassSubject.objects.filter(classroom=cr).exists():
                    subs = Subject.objects.all()
                    if hasattr(Subject, 'cycles'):
                        try:
                            subs = subs.filter(cycles__code__in=['primaire', 'prescolaire']).distinct()
                        except Exception:
                            pass
                    for s in subs:
                        SubjectAssignment.objects.get_or_create(
                            teacher=teacher, classroom=cr, subject=s
                        )
                n += 1
            messages.success(request, f'Prof principal de {n} classe(s) — toutes les matières attribuées.')
            if is_modal:
                return render(request, 'teachers/teacher_create_done.html', {
                    'teacher': teacher,
                    'msg': f'{teacher} est maintenant prof principal.',
                })
            return redirect('teachers:detail', pk=pk)

        # Secondaire / Lycée : classes + matières
        class_ids = request.POST.getlist('classrooms')
        subject_ids = request.POST.getlist('subjects')
        created = 0
        for cid in class_ids:
            for sid in subject_ids:
                _, was = SubjectAssignment.objects.get_or_create(
                    teacher=teacher, classroom_id=cid, subject_id=sid
                )
                if was:
                    created += 1
        messages.success(request, f'{created} affectation(s) enregistrée(s).')
        if is_modal:
            return render(request, 'teachers/teacher_create_done.html', {
                'teacher': teacher,
                'msg': f'{created} affectation(s) pour {teacher}.',
            })
        return redirect('teachers:assign', pk=pk)

    year = get_selected_year(request)
    classrooms = ClassRoom.objects.select_related('level')
    if year:
        classrooms = classrooms.filter(academic_year=year)
    subjects = Subject.objects.filter(is_active=True) if hasattr(Subject, 'is_active') else Subject.objects.all()
    assignments = SubjectAssignment.objects.filter(teacher=teacher).select_related(
        'classroom', 'subject'
    )
    if is_modal:
        return _render_assign_modal(request, teacher)
    return render(request, 'teachers/teacher_assign.html', {
        'teacher': teacher,
        'assignments': assignments,
        'classrooms': classrooms.order_by('level__order', 'name'),
        'subjects': subjects.order_by('name'),
    })


@login_required
def staff_attendance(request):
    if not can(request.user, 'personnel.presences'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    today = timezone.now().date()
    d = request.GET.get('date') or today.isoformat()
    try:
        day = date.fromisoformat(d)
    except ValueError:
        day = today

    if request.method == 'POST':
        staff_id = request.POST.get('staff')
        status = request.POST.get('status', 'present')
        time_in = request.POST.get('time_in') or None
        time_out = request.POST.get('time_out') or None
        notes = request.POST.get('notes', '')
        if staff_id:
            obj, _ = StaffAttendance.objects.update_or_create(
                staff_id=staff_id, date=day,
                defaults={
                    'status': status,
                    'time_in': time_in or None,
                    'time_out': time_out or None,
                    'notes': notes,
                    'recorded_by': request.user,
                },
            )
            messages.success(request, f'Présence enregistrée : {obj.staff}')
        return redirect(f"{request.path}?date={day.isoformat()}")

    staff_list = Teacher.objects.filter(status='actif').order_by('last_name')
    existing = {
        a.staff_id: a for a in StaffAttendance.objects.filter(date=day).select_related('staff')
    }
    rows = []
    for s in staff_list:
        rows.append({'staff': s, 'att': existing.get(s.id)})
    return render(request, 'teachers/staff_attendance.html', {
        'day': day,
        'rows': rows,
        'status_choices': StaffAttendance.STATUS_CHOICES,
        'section': 'presences',
        'stats': _staff_stats(),
    })


@login_required
def staff_contracts(request):
    if not can(request.user, 'personnel.contracts'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    qs = StaffContract.objects.select_related('staff').order_by('-start_date')
    if request.method == 'POST':
        form = ContractForm(request.POST, request.FILES)
        form.fields['staff'].queryset = Teacher.objects.order_by('last_name')
        if form.is_valid():
            form.save()
            messages.success(request, 'Contrat enregistré.')
            if is_modal:
                from django.http import HttpResponse
                return HttpResponse(
                    '<p class="text-emerald-700 text-sm p-4 font-semibold">✓ Contrat enregistré.</p>'
                    '<script>setTimeout(function(){ location.href="/enseignants/contrats/"; }, 600);</script>'
                )
            return redirect('teachers:contracts')
    else:
        form = ContractForm(initial={'start_date': date.today(), 'status': 'actif'})
    form.fields['staff'].queryset = Teacher.objects.order_by('last_name')
    ctx = {
        'contracts': qs[:100],
        'form': form,
        'form_action': request.path + '?modal=1',
        'section': 'contrats',
        'stats': _staff_stats(),
        'modal_title': 'Nouveau contrat',
    }
    if is_modal:
        return render(request, 'teachers/staff_form_modal.html', ctx)
    return render(request, 'teachers/staff_contracts.html', ctx)


@login_required
def staff_salaries(request):
    if not can(request.user, 'personnel.salaries'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    year = int(request.GET.get('year') or date.today().year)
    month = int(request.GET.get('month') or date.today().month)
    qs = StaffSalary.objects.filter(year=year, month=month).select_related('staff')

    if request.method == 'POST':
        form = SalaryForm(request.POST)
        form.fields['staff'].queryset = Teacher.objects.filter(status='actif').order_by('last_name')
        if form.is_valid():
            form.save()
            messages.success(request, 'Salaire enregistré.')
            if is_modal:
                from django.http import HttpResponse
                return HttpResponse(
                    f'<p class="text-emerald-700 text-sm p-4 font-semibold">✓ Salaire enregistré.</p>'
                    f'<script>setTimeout(function(){{ location.href="/enseignants/salaires/?year={year}&month={month}"; }}, 600);</script>'
                )
            return redirect(f"{request.path}?year={year}&month={month}")
    else:
        form = SalaryForm(initial={'year': year, 'month': month, 'status': 'en_attente'})
    form.fields['staff'].queryset = Teacher.objects.filter(status='actif').order_by('last_name')

    total_net = qs.aggregate(s=Sum('net'))['s'] or 0
    ctx = {
        'salaries': qs,
        'form': form,
        'form_action': f'{request.path}?modal=1&year={year}&month={month}',
        'year': year,
        'month': month,
        'total_net': total_net,
        'section': 'salaires',
        'stats': _staff_stats(),
        'modal_title': 'Nouveau salaire',
    }
    if is_modal:
        return render(request, 'teachers/staff_form_modal.html', ctx)
    return render(request, 'teachers/staff_salaries.html', ctx)


@login_required
def staff_documents(request):
    if not can(request.user, 'personnel.documents'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    qs = StaffDocument.objects.select_related('staff').order_by('-uploaded_at')[:100]
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        form.fields['staff'].queryset = Teacher.objects.order_by('last_name')
        if form.is_valid():
            form.save()
            messages.success(request, 'Document ajouté.')
            if is_modal:
                from django.http import HttpResponse
                return HttpResponse(
                    '<p class="text-emerald-700 text-sm p-4 font-semibold">✓ Document ajouté.</p>'
                    '<script>setTimeout(function(){ location.href="/enseignants/documents/"; }, 600);</script>'
                )
            return redirect('teachers:documents')
    else:
        form = DocumentForm()
    form.fields['staff'].queryset = Teacher.objects.order_by('last_name')
    ctx = {
        'documents': qs,
        'form': form,
        'form_action': request.path + '?modal=1',
        'section': 'documents',
        'stats': _staff_stats(),
        'modal_title': 'Ajouter un document',
    }
    if is_modal:
        return render(request, 'teachers/staff_form_modal.html', ctx)
    return render(request, 'teachers/staff_documents.html', ctx)


@login_required
def staff_reports(request):
    if not can(request.user, 'personnel.reports'):
        messages.error(request, 'Accès refusé pour votre rôle.')
        return redirect('core:dashboard')
    stats = _staff_stats()
    by_cat = Teacher.objects.values('category').annotate(n=Count('id'))
    return render(request, 'teachers/staff_reports.html', {
        'stats': stats,
        'by_cat': by_cat,
        'section': 'rapports',
    })


@login_required
def mise_en_place(request):
    """Document officiel « Mise en place » auto depuis personnel + effectifs."""
    if not can(request.user, 'personnel.list') and not can(request.user, 'personnel.reports'):
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    from core.models import SchoolSettings
    from students.models import Enrollment, Student
    from academics.models import Cycle, Level

    year = get_selected_year(request)
    school = SchoolSettings.get_solo()
    cycle_code = request.GET.get('cycle', '')  # primaire / secondaire / all

    staff = Teacher.objects.filter(status='actif').order_by('category', 'last_name', 'first_name')
    by_cat = {
        'admin': staff.filter(category='admin'),
        'enseignant': staff.filter(category='enseignant'),
        'service': staff.filter(category='service'),
    }

    def gender_stats(qs):
        h = qs.filter(gender='M').count()
        f = qs.filter(gender='F').count()
        t = h + f
        return {
            'h': h, 'f': f, 't': t,
            'h_pct': round(100 * h / t) if t else 0,
            'f_pct': round(100 * f / t) if t else 0,
        }

    structure_personnel = [
        {'label': 'PERSONNEL ADMINISTRATIF', 'key': 'admin', **gender_stats(by_cat['admin']), 'rows': by_cat['admin']},
        {'label': 'PERSONNEL ENSEIGNANT', 'key': 'enseignant', **gender_stats(by_cat['enseignant']), 'rows': by_cat['enseignant']},
        {'label': 'PERSONNEL OUVRIER / SERVICE', 'key': 'service', **gender_stats(by_cat['service']), 'rows': by_cat['service']},
    ]
    total_staff = gender_stats(staff)

    # Effectifs par classe (année sélectionnée)
    enrollments = Enrollment.objects.filter(is_active=True).select_related(
        'classroom', 'classroom__level', 'classroom__level__cycle', 'student'
    )
    if year:
        enrollments = enrollments.filter(academic_year=year)

    cycles = Cycle.objects.all().order_by('order')
    class_stats = []
    cr_qs = ClassRoom.objects.select_related('level', 'level__cycle').order_by(
        'level__cycle__order', 'level__order', 'name'
    )
    if year:
        cr_qs = cr_qs.filter(academic_year=year)
    else:
        cr_qs = cr_qs.none()
    for cr in cr_qs:
        if cycle_code and getattr(cr.level.cycle, 'code', '') != cycle_code:
            # map secondaire/lycee
            ccode = cr.level.cycle.code
            if cycle_code == 'secondaire' and ccode not in ('secondaire', 'college', 'lycee'):
                continue
            if cycle_code == 'primaire' and ccode not in ('primaire', 'prescolaire', 'maternelle'):
                continue
        ens = enrollments.filter(classroom=cr)
        g = ens.filter(student__gender='M').count()
        fi = ens.filter(student__gender='F').count()
        class_stats.append({
            'classroom': cr,
            'cycle': cr.level.cycle,
            'option': getattr(cr, 'serie', None) or '',
            'garcons': g,
            'filles': fi,
            'total': g + fi,
        })

    # Group class_stats by cycle for tabs
    by_cycle = {}
    for row in class_stats:
        cname = row['cycle'].name
        by_cycle.setdefault(cname, []).append(row)

    ctx = {
        'school': school,
        'year': year,
        'structure_personnel': structure_personnel,
        'total_staff': total_staff,
        'class_stats': class_stats,
        'by_cycle': by_cycle,
        'cycles': cycles,
        'cycle_code': cycle_code,
        'section': 'mise_en_place',
        'stats': _staff_stats(),
        'staff_detail': staff,
        'today': timezone.now().date(),
    }

    if request.GET.get('pdf') == '1':
        return _mise_en_place_pdf(ctx)

    return render(request, 'teachers/mise_en_place.html', ctx)


def _mise_en_place_pdf(ctx):
    from io import BytesIO
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=10 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle('t', parent=styles['Heading1'], fontSize=12, alignment=TA_CENTER, spaceAfter=4)
    sub = ParagraphStyle('s', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, spaceAfter=2)
    small = ParagraphStyle('sm', parent=styles['Normal'], fontSize=7, leading=9)
    h2 = ParagraphStyle('h2', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, spaceBefore=8, spaceAfter=4, fontName='Helvetica-Bold')

    school = ctx['school']
    year = ctx['year']
    story = []
    story.append(Paragraph(school.header_left or '', sub))
    story.append(Paragraph(f"<b>{school.name}</b>", title))
    if school.address:
        story.append(Paragraph(school.address, sub))
    story.append(Paragraph(
        f"<b>MISE EN PLACE DU PERSONNEL — EXERCICE {year.name if year else ''}</b>", h2
    ))
    story.append(Spacer(1, 4 * mm))

    # Structure personnel résumé
    story.append(Paragraph("<b>STRUCTURE DU PERSONNEL</b>", h2))
    data = [['CATÉGORIE', 'H', '%', 'F', '%', 'TOTAL']]
    for row in ctx['structure_personnel']:
        data.append([
            row['label'], str(row['h']), f"{row['h_pct']}%",
            str(row['f']), f"{row['f_pct']}%", str(row['t']),
        ])
    ts = ctx['total_staff']
    data.append(['TOTAL GÉNÉRAL', str(ts['h']), f"{ts['h_pct']}%", str(ts['f']), f"{ts['f_pct']}%", str(ts['t'])])
    t = Table(data, colWidths=[70 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 22 * mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t)

    # Effectifs par classe
    if ctx['class_stats']:
        story.append(Paragraph("<b>STRUCTURE ET STATISTIQUE SCOLAIRE</b>", h2))
        data2 = [['CLASSE', 'OPTION', 'G', 'F', 'TOTAL']]
        for r in ctx['class_stats']:
            data2.append([
                r['classroom'].name,
                str(r['option'] or '—'),
                str(r['garcons']), str(r['filles']), str(r['total']),
            ])
        t2 = Table(data2, colWidths=[45 * mm, 40 * mm, 20 * mm, 20 * mm, 25 * mm])
        t2.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.92)),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(t2)

    # Détail nominatif
    story.append(Paragraph("<b>MISE EN PLACE DU PERSONNEL (DÉTAIL)</b>", h2))
    for block in ctx['structure_personnel']:
        if not block['rows']:
            continue
        story.append(Paragraph(f"<b>{block['label']}</b>", small))
        data3 = [['N°', 'NOM ET PRÉNOM', 'SEXE', 'DATE NAISS.', 'DIPLÔME', 'FONCTION']]
        for i, p in enumerate(block['rows'], 1):
            data3.append([
                f"{i:02d}",
                f"{p.last_name} {p.first_name}",
                p.gender,
                p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else '—',
                (p.diploma or '—')[:20],
                (p.function or p.get_category_display())[:18],
            ])
        t3 = Table(data3, colWidths=[12 * mm, 55 * mm, 14 * mm, 25 * mm, 35 * mm, 35 * mm])
        t3.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.93, 0.93, 0.93)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t3)
        story.append(Spacer(1, 3 * mm))

    city = school.city or ''
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Fait à {city}, le {ctx['today'].strftime('%d/%m/%Y')}",
        ParagraphStyle('sig', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT),
    ))
    if school.director_name:
        story.append(Paragraph(
            f"<b>Le Chef d'établissement</b><br/>{school.director_name}",
            ParagraphStyle('sig2', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, spaceBefore=6),
        ))

    doc.build(story)
    buffer.seek(0)
    resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    yname = year.name if year else 'annee'
    resp['Content-Disposition'] = f'attachment; filename="mise_en_place_{yname}.pdf"'
    return resp


def _school_settings():
    try:
        from core.models import SchoolSettings
        return SchoolSettings.get_solo()
    except Exception:
        return None


def _staff_badge(teacher, request=None, school=None):
    from core.badge import build_badge_context
    school = school if school is not None else _school_settings()
    design = (request.GET.get('template') if request else None) or getattr(
        school, 'card_template', None
    ) or 'official'
    return build_badge_context(teacher, 'personnel', school, None, design)


@login_required
def staff_qr_codes(request):
    """QR codes du personnel pour pointage — générés localement (TCH:<matricule>)."""
    from core.qr import badge_payload, staff_display_code
    if not can(request.user, 'personnel.list'):
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    qs = Teacher.objects.filter(status='actif').order_by('last_name', 'first_name')
    category = request.GET.get('category', '')
    q = request.GET.get('q', '').strip()
    if category in ('enseignant', 'admin', 'service'):
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(matricule__icontains=q)
        )
    rows = []
    for tch in qs:
        code = badge_payload('personnel', staff_display_code(tch))
        url = reverse('core:qr_image') + '?data=' + quote(code)
        rows.append({
            'teacher': tch,
            'code': code,
            'qr_url': url,
            'qr_url_lg': url + '&size=14',
            'card_url': reverse('teachers:card', args=[tch.pk]),
        })
    return render(request, 'teachers/staff_qr_codes.html', {
        'rows': rows, 'category': category, 'q': q,
        'categories': Teacher.CATEGORY_CHOICES,
    })


@login_required
def staff_qr_one(request, pk):
    """Modal QR d'un membre du personnel."""
    from core.qr import badge_payload, staff_display_code
    teacher = get_object_or_404(Teacher, pk=pk)
    code = badge_payload('personnel', staff_display_code(teacher))
    url = reverse('core:qr_image') + '?data=' + quote(code)
    return render(request, 'teachers/staff_qr_modal.html', {
        'teacher': teacher, 'code': code,
        'qr_url': url, 'qr_url_lg': url + '&size=14',
        'card_url': reverse('teachers:card', args=[teacher.pk]),
    })


@login_required
def staff_card(request, pk):
    """Badge du personnel — page autonome prête à imprimer."""
    teacher = get_object_or_404(Teacher, pk=pk)
    badge = _staff_badge(teacher, request)
    return render(request, 'teachers/staff_card.html', {
        'teacher': teacher, 'badge': badge,
        'title': f"Badge — {badge['full_name']}",
        'pdf_url': reverse('teachers:card_pdf', args=[teacher.pk]),
        'image_url': reverse('teachers:card_image', args=[teacher.pk]),
    })


@login_required
def staff_card_pdf(request, pk):
    """PDF CR80 officiel d'un membre du personnel (Page 1 Recto, Page 2 Verso)."""
    from core.badge_pdf import render_badge_pdf
    teacher = get_object_or_404(Teacher, pk=pk)
    duplex = request.GET.get('duplex', '1') != '0' and request.GET.get('side') != 'recto'
    resp = HttpResponse(render_badge_pdf(_staff_badge(teacher, request), duplex=duplex),
                        content_type='application/pdf')
    filename = f"badge_{teacher.matricule}.pdf".replace(' ', '_')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def staff_card_image(request, pk):
    """PNG haute définition du badge personnel (recto, verso ou les deux)."""
    from students.card_mali import render_badge_png, render_badge_verso_png, render_badge_both_png
    teacher = get_object_or_404(Teacher, pk=pk)
    badge = _staff_badge(teacher, request)
    side = request.GET.get('side', 'front').lower()
    if side == 'both':
        buf = render_badge_both_png(badge)
    elif side in ('back', 'verso'):
        buf = render_badge_verso_png(badge)
    else:
        buf = render_badge_png(badge)
    filename = f"badge_{teacher.matricule}_{side}.png".replace(' ', '_')
    disp = 'inline' if request.GET.get('preview') == '1' else 'attachment'
    resp = HttpResponse(buf.read(), content_type='image/png')
    resp['Content-Disposition'] = f'{disp}; filename="{filename}"'
    return resp


@login_required
def staff_card_preview(request, pk):
    """Aperçu du badge personnel dans une modale."""
    teacher = get_object_or_404(Teacher, pk=pk)
    return render(request, 'teachers/staff_card_preview_modal.html', {
        'teacher': teacher, 'badge': _staff_badge(teacher, request),
        'pdf_url': reverse('teachers:card_pdf', args=[teacher.pk]),
        'image_url': reverse('teachers:card_image', args=[teacher.pk]),
        'card_url': reverse('teachers:card', args=[teacher.pk]),
    })


@login_required
def staff_cards_all_pdf(request):
    """Tous les badges du personnel actif, un par page."""
    from core.badge_pdf import render_badges_pdf
    if not can(request.user, 'personnel.list'):
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    school = _school_settings()
    qs = Teacher.objects.filter(status='actif').order_by('last_name', 'first_name')
    badges = [_staff_badge(teacher, request, school) for teacher in qs]
    duplex = request.GET.get('duplex', '1') != '0'
    resp = HttpResponse(render_badges_pdf(badges, duplex=duplex), content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="badges_personnel.pdf"'
    return resp
