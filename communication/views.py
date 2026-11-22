from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from core.permissions import permission_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django import forms

from .models import Announcement
from academics.models import ClassRoom, Level


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'target', 'classroom', 'level', 'is_published', 'expires_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'content': forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
            'target': forms.Select(attrs={'class': 'form-input'}),
            'classroom': forms.Select(attrs={'class': 'form-input'}),
            'level': forms.Select(attrs={'class': 'form-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'rounded'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['classroom'].required = False
        self.fields['level'].required = False
        self.fields['expires_at'].required = False


@permission_required('announcements.view')
def announcement_list(request):
    qs = Announcement.objects.select_related('author', 'classroom', 'level').order_by('-published_at')
    from core.permissions import can
    show_all = request.GET.get('all') == '1' and can(request.user, 'announcements.publish')
    if not show_all:
        qs = qs.filter(is_published=True)
        # non expirées
        from django.db.models import Q
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
    return render(request, 'communication/announcement_list.html', {
        'announcements': qs[:50],
        'show_all': show_all,
    })


@permission_required('announcements.view')
def announcement_detail(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    from core.permissions import can
    if not ann.is_published or (ann.expires_at and ann.expires_at < timezone.now()):
        if not can(request.user, 'announcements.publish'):
            from django.http import Http404
            raise Http404("Annonce indisponible.")
    return render(request, 'communication/announcement_detail.html', {'announcement': ann})


@permission_required('announcements.publish')
def announcement_create(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.author = request.user
            ann.save()
            messages.success(request, "Annonce publiée.")
            return redirect('communication:list')
    else:
        form = AnnouncementForm(initial={'is_published': True})
    ctx = {'form': form, 'title': 'Nouvelle annonce', 'form_action': request.path}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'communication/announcement_form_modal.html', ctx)
    return render(request, 'communication/announcement_form.html', ctx)


@permission_required('announcements.publish')
def announcement_edit(request, pk):
    ann = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=ann)
        if form.is_valid():
            form.save()
            messages.success(request, "Annonce modifiée.")
            return redirect('communication:list')
    else:
        form = AnnouncementForm(instance=ann)
    ctx = {'form': form, 'title': "Modifier l'annonce", 'announcement': ann, 'form_action': request.path}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'communication/announcement_form_modal.html', ctx)
    return render(request, 'communication/announcement_form.html', ctx)




from django import forms
from .models import SchoolDocument


class SchoolDocumentForm(forms.ModelForm):
    class Meta:
        model = SchoolDocument
        fields = ['title', 'category', 'description', 'file', 'academic_year', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm', 'required': True}),
            'category': forms.Select(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'description': forms.Textarea(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm', 'rows': 2}),
            'file': forms.FileInput(attrs={'class': 'w-full text-sm', 'required': True}),
            'academic_year': forms.Select(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }


@login_required
def documents_hub(request):
    """Gestion des documents — bibliothèque + liens annonces."""
    from core.year_context import get_selected_year
    from core.permissions import can, is_staff_role

    year = get_selected_year(request)
    tab = request.GET.get('tab', 'documents')
    q = (request.GET.get('q') or '').strip()
    category = request.GET.get('category') or ''

    docs = SchoolDocument.objects.select_related('uploaded_by', 'academic_year').order_by('-created_at')
    if not is_staff_role(request.user) and not request.user.is_superuser:
        docs = docs.filter(is_published=True)
    if category:
        docs = docs.filter(category=category)
    if q:
        from django.db.models import Q
        docs = docs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if year:
        # show year-specific + global (null year)
        from django.db.models import Q
        docs = docs.filter(Q(academic_year=year) | Q(academic_year__isnull=True))

    can_upload = is_staff_role(request.user) or request.user.is_superuser

    cat_stats = []
    for code, label in SchoolDocument.CATEGORY_CHOICES:
        cat_stats.append({
            'code': code,
            'label': label,
            'n': docs.filter(category=code).count(),
        })

    return render(request, 'communication/documents_hub.html', {
        'documents': docs[:100],
        'tab': tab,
        'q': q,
        'category': category,
        'categories': SchoolDocument.CATEGORY_CHOICES,
        'cat_stats': cat_stats,
        'can_upload': can_upload,
        'year': year,
        'n_docs': docs.count(),
        'n_published': docs.filter(is_published=True).count(),
    })


@login_required
def document_upload(request):
    from core.year_context import get_selected_year
    from core.permissions import is_staff_role

    if not (is_staff_role(request.user) or request.user.is_superuser):
        messages.error(request, 'Accès refusé.')
        return redirect('communication:documents')

    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    year = get_selected_year(request)

    if request.method == 'POST':
        form = SchoolDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            if not doc.academic_year_id and year:
                doc.academic_year = year
            doc.save()
            messages.success(request, 'Document ajouté.')
            if is_modal:
                from django.http import HttpResponse
                return HttpResponse(
                    '<p class="text-emerald-700 text-sm p-4 font-semibold">✓ Document enregistré.</p>'
                    '<script>setTimeout(function(){ location.href="/communication/documents/"; }, 500);</script>'
                )
            return redirect('communication:documents')
    else:
        form = SchoolDocumentForm(initial={'academic_year': year, 'is_published': True})

    ctx = {
        'form': form,
        'form_action': request.path + ('?modal=1' if is_modal else ''),
        'title': 'Ajouter un document',
    }
    if is_modal:
        return render(request, 'communication/document_form_modal.html', ctx)
    return render(request, 'communication/document_form_modal.html', ctx)


@login_required
@require_POST
def document_delete(request, pk):
    from core.permissions import is_staff_role
    if not (is_staff_role(request.user) or request.user.is_superuser):
        messages.error(request, 'Accès refusé.')
        return redirect('communication:documents')
    doc = get_object_or_404(SchoolDocument, pk=pk)
    if request.method == 'POST':
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, 'Document supprimé.')
    return redirect('communication:documents')
