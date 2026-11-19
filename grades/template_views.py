from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django import forms

from core.permissions import get_role
from .models import BulletinTemplate


def _students_use_portal(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_role(request.user) == 'eleve' and not request.user.is_superuser:
            return redirect('eleve:bulletins')
        return view_func(request, *args, **kwargs)
    return _wrapped


class BulletinTemplateForm(forms.ModelForm):
    class Meta:
        model = BulletinTemplate
        fields = [
            'name', 'category', 'layout', 'formula', 'description',
            'is_default', 'show_rank', 'show_prev_average', 'header_title',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'layout': forms.Select(attrs={'class': 'form-input'}),
            'formula': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'header_title': forms.TextInput(attrs={'class': 'form-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'rounded'}),
            'show_rank': forms.CheckboxInput(attrs={'class': 'rounded'}),
            'show_prev_average': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }


def ensure_default_templates():
    if not BulletinTemplate.objects.filter(category='primaire').exists():
        BulletinTemplate.objects.create(
            name='Primaire – compositions',
            category='primaire',
            layout='primaire_compositions',
            formula='moyenne_simple',
            is_default=True,
            description='Bulletin primaire : moyennes des compositions mensuelles.',
        )
    if not BulletinTemplate.objects.filter(category='secondaire').exists():
        BulletinTemplate.objects.create(
            name='Standard Mali (classe + composition)',
            category='secondaire',
            layout='mali_standard',
            formula='comp40_plus_classe_div3',
            is_default=True,
            description='NoteClasse/20, NoteComp/40, moyenne (Comp+Classe)/3.',
        )
        BulletinTemplate.objects.create(
            name='Formule classique sur 20',
            category='secondaire',
            layout='simple_20',
            formula='comp20_x2_plus_classe_div3',
            is_default=False,
            description='Toutes notes sur 20. Moyenne = (Composition x 2 + Note de classe) / 3.',
        )


@login_required
@_students_use_portal
def template_list(request):
    ensure_default_templates()
    templates = BulletinTemplate.objects.all()
    return render(request, 'grades/template_list.html', {'templates': templates, 'section': 'modeles'})


@login_required
@_students_use_portal
def template_create(request):
    ensure_default_templates()
    if request.method == 'POST':
        form = BulletinTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Modele de bulletin cree.')
            return redirect('grades:template_list')
    else:
        form = BulletinTemplateForm()
    ctx = {'form': form, 'title': 'Nouveau modele de bulletin', 'form_action': request.path}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'grades/template_form_modal.html', ctx)
    return render(request, 'grades/template_form.html', ctx)



@login_required
@_students_use_portal
def template_edit(request, pk):
    obj = get_object_or_404(BulletinTemplate, pk=pk)
    if request.method == 'POST':
        form = BulletinTemplateForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Modele modifie.')
            return redirect('grades:template_list')
    else:
        form = BulletinTemplateForm(instance=obj)
    ctx = {'form': form, 'title': 'Modifier modele', 'form_action': request.path}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'grades/template_form_modal.html', ctx)
    return render(request, 'grades/template_form.html', ctx)


@login_required
@_students_use_portal
def template_set_default(request, pk):
    obj = get_object_or_404(BulletinTemplate, pk=pk)
    obj.is_default = True
    obj.save()
    messages.success(
        request,
        '"%s" est le modele par defaut pour %s.' % (obj.name, obj.get_category_display()),
    )
    return redirect('grades:template_list')
