from django import forms
from .models import ClassRoom, Level, AcademicYear
from teachers.models import Teacher


class ClassRoomForm(forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = [
            'name', 'level', 'academic_year', 'capacity', 'serie',
            'inscription_fee', 'tuition_fee', 'main_teacher',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ex: 6ème année A'}),
            'level': forms.Select(attrs={'class': 'form-input'}),
            'academic_year': forms.Select(attrs={'class': 'form-input'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-input'}),
            'serie': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Sci, Litt, Eco (10e-12e)'}),
            'inscription_fee': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0'}),
            'tuition_fee': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0'}),
            'main_teacher': forms.Select(attrs={'class': 'form-input search-person', 'data-search-person': '1', 'data-placeholder': 'Rechercher un enseignant…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['main_teacher'].queryset = Teacher.objects.filter(is_active=True)
        self.fields['main_teacher'].required = False
        year = AcademicYear.objects.filter(is_current=True).first()
        if year and not self.instance.pk:
            self.fields['academic_year'].initial = year
