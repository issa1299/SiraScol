from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django import forms
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from core.account_sync import ensure_user_for_parent
from core.permissions import can, role_required

from .models import Parent, ParentStudent, Student, Enrollment


class ParentForm(forms.ModelForm):
    class Meta:
        model = Parent
        fields = ['first_name', 'last_name', 'phone', 'phone2', 'email', 'address', 'profession']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
            'phone': forms.TextInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
            'phone2': forms.TextInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
            'email': forms.EmailInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
            'address': forms.Textarea(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm', 'rows': 2}),
            'profession': forms.TextInput(attrs={'class': 'form-input w-full border rounded-xl px-3 py-2.5 text-sm'}),
        }


def _parent_kpis():
    total = Parent.objects.count()
    with_user = Parent.objects.exclude(user__isnull=True).count()
    links = ParentStudent.objects.count()
    no_pwd = Parent.objects.filter(user__isnull=True).count()
    # actifs = those with at least one linked student
    actifs = Parent.objects.annotate(n=Count('children')).filter(n__gt=0).count()
    return {
        'total': total,
        'actifs': actifs,
        'inactifs': max(0, total - actifs),
        'liaisons': links,
        'sans_mdp': no_pwd,
        'avec_compte': with_user,
    }


@role_required('directeur', 'secretaire')
def parent_list(request):
    qs = Parent.objects.annotate(n_children=Count('children')).order_by('last_name', 'first_name')
    q = request.GET.get('q', '').strip()
    filtre = request.GET.get('filtre', 'tous')
    if q:
        qs = qs.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )
    if filtre == 'actifs':
        qs = qs.filter(n_children__gt=0)
    elif filtre == 'inactifs':
        qs = qs.filter(n_children=0)
    elif filtre == 'sans_mdp':
        qs = qs.filter(user__isnull=True)
    elif filtre == 'liaisons':
        qs = qs.filter(n_children__gt=0)

    parents = Paginator(qs, 30).get_page(request.GET.get('page'))
    kpis = _parent_kpis()
    return render(request, 'students/parent_list.html', {
        'parents': parents,
        'q': q,
        'filtre': filtre,
        'kpis': kpis,
        'form': ParentForm(),
        'students': Student.objects.filter(status='actif').order_by('last_name')[:300],
        'relations': Parent.RELATION_CHOICES,
    })


@role_required('directeur', 'secretaire')
@require_POST
def parent_sync(request):
    """
    Synchroniser : pour chaque élève ayant un contact parent (legacy fields ou
    ParentStudent manquant), créer / lier les parents automatiquement.
    On s'appuie sur les liens ParentStudent existants + champs tuteur sur Student
    si présents, et on crée un compte pour chaque parent sans user.
    """
    if not can(request.user, 'parents.manage') and not can(request.user, 'students.edit'):
        messages.error(request, 'Accès refusé.')
        return redirect('students:parent_list')

    created_parents = 0
    created_links = 0
    created_accounts = 0

    # 1) Assurer un compte pour chaque parent existant
    for parent in Parent.objects.filter(user__isnull=True):
        user, created, pwd = ensure_user_for_parent(parent)
        if created:
            created_accounts += 1

    # 2) Élèves avec infos parent/tuteur dans le modèle Student (si champs existent)
    students = Student.objects.filter(status='actif')
    for st in students:
        # Champs optionnels souvent présents à l'inscription
        guardian_name = (
            getattr(st, 'guardian_name', None)
            or getattr(st, 'parent_name', None)
            or getattr(st, 'tuteur_name', None)
            or ''
        ).strip()
        guardian_phone = (
            getattr(st, 'guardian_phone', None)
            or getattr(st, 'parent_phone', None)
            or getattr(st, 'tuteur_phone', None)
            or ''
        ).strip()
        guardian_relation = getattr(st, 'guardian_relation', None) or 'tuteur'

        if not guardian_name and not guardian_phone:
            continue

        parent = None
        if guardian_phone:
            parent = Parent.objects.filter(phone=guardian_phone).first()
        if not parent and guardian_name:
            parts = guardian_name.split()
            if len(parts) >= 2:
                parent = Parent.objects.filter(
                    last_name__iexact=parts[0], first_name__iexact=' '.join(parts[1:])
                ).first() or Parent.objects.filter(
                    last_name__iexact=parts[-1], first_name__iexact=' '.join(parts[:-1])
                ).first()

        if not parent:
            parts = guardian_name.split() if guardian_name else ['Parent', st.last_name]
            last_n = parts[0] if len(parts) >= 1 else 'Parent'
            first_n = ' '.join(parts[1:]) if len(parts) > 1 else st.first_name
            parent = Parent.objects.create(
                last_name=last_n,
                first_name=first_n or '—',
                phone=guardian_phone or f'000-{st.pk}',
            )
            created_parents += 1
            user, created, pwd = ensure_user_for_parent(parent)
            if created:
                created_accounts += 1

        _, link_created = ParentStudent.objects.get_or_create(
            parent=parent,
            student=st,
            defaults={'relation': guardian_relation if guardian_relation in dict(Parent.RELATION_CHOICES) else 'tuteur',
                      'is_primary': True},
        )
        if link_created:
            created_links += 1

    # 3) Si des parents existent déjà sans lien, rien de plus — les liens manuels restent

    messages.success(
        request,
        f"Synchronisation terminée ! {created_parents} parent(s) créé(s), "
        f"{created_links} liaison(s), {created_accounts} compte(s)."
    )
    return redirect('students:parent_list')


@role_required('directeur', 'secretaire')
def parent_detail(request, pk):
    parent = get_object_or_404(Parent, pk=pk)
    links = parent.children.select_related('student').prefetch_related(
        'student__enrollments'
    ).all()
    # classe actuelle
    link_data = []
    for ps in links:
        st = ps.student
        enr = st.enrollments.filter(is_active=True).select_related('classroom').first()
        link_data.append({
            'ps': ps,
            'student': st,
            'classroom': enr.classroom if enr else None,
            'relation': ps.get_relation_display(),
        })
    ctx = {'parent': parent, 'links': links, 'link_data': link_data, 'relations': Parent.RELATION_CHOICES}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/parent_detail_modal.html', ctx)
    return render(request, 'students/parent_detail.html', ctx)


@role_required('directeur', 'secretaire')
def parent_children_modal(request, pk):
    """Modal « Voir enfants »."""
    parent = get_object_or_404(Parent, pk=pk)
    links = parent.children.select_related('student').all()
    link_data = []
    for ps in links:
        enr = ps.student.enrollments.filter(is_active=True).select_related('classroom').first()
        link_data.append({
            'ps': ps,
            'student': ps.student,
            'classroom': enr.classroom if enr else None,
            'relation': ps.get_relation_display(),
        })
    return render(request, 'students/parent_children_modal.html', {
        'parent': parent, 'link_data': link_data,
    })


@role_required('directeur', 'secretaire')
def parent_link_modal(request, pk):
    """Modal pour lier un élève au parent."""
    parent = get_object_or_404(Parent, pk=pk)
    if request.method == 'POST':
        student_id = request.POST.get('student')
        relation = request.POST.get('relation', 'pere')
        if student_id:
            ParentStudent.objects.get_or_create(
                parent=parent, student_id=student_id,
                defaults={'relation': relation, 'is_primary': False},
            )
            messages.success(request, 'Élève lié au parent.')
        return redirect('students:parent_list')
    already = ParentStudent.objects.filter(parent=parent).values_list('student_id', flat=True)
    students = Student.objects.filter(status='actif').exclude(id__in=already).order_by('last_name', 'first_name')[:400]
    return render(request, 'students/parent_link_modal.html', {
        'parent': parent,
        'students': students,
        'relations': Parent.RELATION_CHOICES,
        'form_action': request.path,
    })


@role_required('directeur', 'secretaire')
@require_POST
def parent_unlink(request, pk, student_id):
    parent = get_object_or_404(Parent, pk=pk)
    ParentStudent.objects.filter(parent=parent, student_id=student_id).delete()
    messages.success(request, 'Liaison supprimée.')
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('students:parent_list')


@role_required('directeur', 'secretaire')
def parent_create(request):
    if request.method == 'POST':
        form = ParentForm(request.POST)
        student_id = request.POST.get('student')
        relation = request.POST.get('relation', 'pere')
        is_primary = request.POST.get('is_primary') == 'on'
        if form.is_valid():
            parent = form.save()
            if student_id:
                ParentStudent.objects.get_or_create(
                    parent=parent, student_id=student_id,
                    defaults={'relation': relation, 'is_primary': is_primary},
                )
            user, created, pwd = ensure_user_for_parent(parent)
            if created and pwd:
                messages.success(request, f"Parent {parent} enregistré. Compte : {user.username} / mdp : {pwd}")
            else:
                messages.success(request, f"Parent {parent} enregistré.")
            return redirect('students:parent_list')
    else:
        form = ParentForm()
    students = Student.objects.filter(status='actif').order_by('last_name', 'first_name')
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/parent_form_modal.html', {
            'form': form, 'form_action': request.path,
            'students': students, 'relations': Parent.RELATION_CHOICES, 'is_create': True,
        })
    return render(request, 'students/parent_form.html', {
        'form': form, 'title': 'Nouveau parent', 'is_edit': False,
        'students': students, 'relations': Parent.RELATION_CHOICES,
    })


@role_required('directeur', 'secretaire')
def parent_edit(request, pk):
    parent = get_object_or_404(Parent, pk=pk)
    if request.method == 'POST':
        form = ParentForm(request.POST, instance=parent)
        if form.is_valid():
            form.save()
            messages.success(request, 'Parent modifié.')
            return redirect('students:parent_list')
    else:
        form = ParentForm(instance=parent)
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/parent_form_modal.html', {
            'form': form, 'parent': parent, 'form_action': request.path,
        })
    return render(request, 'students/parent_form.html', {
        'form': form, 'title': f'Modifier — {parent}', 'is_edit': True, 'parent': parent,
        'students': [], 'relations': [],
    })


@role_required('directeur', 'secretaire')
def parent_list_pdf(request):
    from core.list_pdf import build_list_pdf
    from core.models import SchoolSettings
    from .models import Parent, ParentStudent
    from django.db.models import Q, Count

    school = SchoolSettings.get_solo()
    q = (request.GET.get('q') or '').strip()
    qs = Parent.objects.annotate(n_children=Count('children')).order_by('last_name', 'first_name')
    if q:
        qs = qs.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(phone__icontains=q)
        )
    rows = []
    for p in qs:
        rows.append([
            f"{p.last_name} {p.first_name}",
            getattr(p, 'phone', '') or '—',
            getattr(p, 'email', '') or '—',
            str(p.n_children),
        ])
    school_name = getattr(school, 'name', None) or 'Établissement'
    return build_list_pdf(
        title=school_name,
        subtitle=f"Liste des parents · {len(rows)} parent(s)",
        headers=['Nom et prénom', 'Téléphone', 'Email', 'Enfants'],
        rows=rows,
        filename='liste_parents.pdf',
    )
