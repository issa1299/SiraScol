from django import forms
from .models import Assessment, AssessmentType, Period
from academics.models import Subject, ClassRoom, AcademicYear
from teachers.models import Teacher


def level_cycle_code(level):
    """
    Retourne 'primaire' | 'secondaire' | 'lycee' selon le cycle / nom du niveau.
      1er cycle  (primaire)  : 1ère → 6ème
      2ème cycle (secondaire): 7ème → 9ème
      Lycée                  : 10ème → 12ème
    """
    if not level:
        return 'primaire'
    cycle = getattr(level, 'cycle', None)
    code = (getattr(cycle, 'code', None) or '').lower()
    if code in ('primaire', 'secondaire', 'lycee'):
        return code
    name = (level.name or '').lower()
    name_n = (
        name.replace('è', 'e').replace('é', 'e').replace('ê', 'e')
        .replace('ème', 'eme').replace('ére', 'ere')
    )
    if any(x in name_n for x in ('10eme', '10e ', '11eme', '11e ', '12eme', '12e ', 'terminale')):
        return 'lycee'
    if any(x in name_n for x in ('7eme', '8eme', '9eme')):
        return 'secondaire'
    if any(x in name_n for x in (
        '1ere', '1er annee', '2eme', '2e annee', '3eme', '3e annee',
        '4eme', '4e annee', '5eme', '5e annee', '6eme', '6e annee', '6 annee',
    )):
        return 'primaire'
    return 'primaire'


def level_is_primary(level):
    """Notes /10 + compositions mensuelles → 1er cycle uniquement."""
    return level_cycle_code(level) == 'primaire'


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            'title', 'assessment_type', 'subject', 'classroom',
            'teacher', 'period', 'date', 'max_score', 'coefficient',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ex: Composition Maths'}),
            'assessment_type': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'classroom': forms.Select(attrs={'class': 'form-input'}),
            'teacher': forms.Select(attrs={'class': 'form-input search-person', 'data-search-person': '1', 'data-placeholder': 'Rechercher un enseignant…'}),
            'period': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-input'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5'}),
        }

    def __init__(self, *args, classroom=None, is_primary=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = Teacher.objects.filter(is_active=True)
        self.fields['teacher'].required = False
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True)

        year = AcademicYear.objects.filter(is_current=True).first()
        classrooms = ClassRoom.objects.select_related('level__cycle', 'academic_year')
        if year:
            classrooms = classrooms.filter(academic_year=year)
        self.fields['classroom'].queryset = classrooms.order_by('level__order', 'name')

        # Déterminer primaire / secondaire
        if classroom is None and self.instance and self.instance.pk:
            classroom = self.instance.classroom
        if classroom is None and self.data.get('classroom'):
            try:
                classroom = ClassRoom.objects.select_related('level').get(pk=self.data.get('classroom'))
            except Exception:
                classroom = None

        if is_primary is None:
            is_primary = level_is_primary(classroom.level) if classroom else False

        self.is_primary = is_primary

        # Types d'évaluation selon le niveau
        types = AssessmentType.objects.all()
        if is_primary:
            # Primaire : composition (mensuelle) uniquement
            types = types.filter(code__in=['composition'])
            if not types.exists():
                types = AssessmentType.objects.filter(name__icontains='composition')
            period_type = 'mois'
            self.fields['max_score'].initial = 10
            self.fields['coefficient'].initial = 1
            self.fields['title'].widget.attrs['placeholder'] = 'ex: Composition de Mars — Français (sur 10)'
        else:
            # Secondaire / Lycée : devoir, composition, examen trimestriel
            types = types.filter(code__in=['devoir', 'composition', 'trimestre'])
            if not types.exists():
                types = AssessmentType.objects.all()
            period_type = 'trimestre'
            self.fields['max_score'].initial = 20
            self.fields['title'].widget.attrs['placeholder'] = 'ex: Devoir 1 Maths / Composition 1er Trimestre'

        self.fields['assessment_type'].queryset = types.order_by('name')

        # Périodes : mois (primaire) ou trimestres (sec/lycée)
        periods = Period.objects.all()
        if year:
            periods = periods.filter(academic_year=year)
        typed = periods.filter(period_type=period_type)
        if typed.exists():
            periods = typed
        self.fields['period'].queryset = periods.order_by('order')

        if classroom:
            self.fields['classroom'].initial = classroom.pk
            # Optionnel : cacher le champ classe si déjà fixée
            self.fields['classroom'].widget = forms.HiddenInput()
            self.initial.setdefault('classroom', classroom.pk)
