from django import forms
from core.widgets import SmartDateInput
from .models import Student, Enrollment, Parent
from .validators import check_birth_date
from academics.models import ClassRoom, AcademicYear


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'photo', 'first_name', 'last_name', 'gender', 'date_of_birth',
            'place_of_birth', 'address', 'phone', 'email',
            'status', 'enrollment_date', 'notes',
        ]
        widgets = {
            'photo': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'capture': 'environment', 'id': 'id_photo'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'date_of_birth': SmartDateInput(),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'enrollment_date': SmartDateInput(),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }

    def clean_date_of_birth(self):
        value = self.cleaned_data.get('date_of_birth')
        error = check_birth_date(value)
        if error:
            raise forms.ValidationError(error)
        return value


class ParentInfoForm(forms.Form):
    """Informations du parent/tuteur lors de l'inscription d'un élève."""

    RELATIONS = [('', '— Choisir —'), ('pere', 'Père'), ('mere', 'Mère'),
                 ('tuteur', 'Tuteur'), ('autre', 'Autre')]

    existing_parent = forms.ModelChoiceField(
        queryset=Parent.objects.none(), required=False,
        label='Parent déjà enregistré (facultatif)',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    first_name = forms.CharField(required=False, label='Prénom du parent', widget=forms.TextInput(attrs={'class': 'form-input'}))
    last_name = forms.CharField(required=False, label='Nom du parent', widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone = forms.CharField(required=False, label='Téléphone du parent', widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone2 = forms.CharField(required=False, label='Téléphone 2', widget=forms.TextInput(attrs={'class': 'form-input'}))
    email = forms.EmailField(required=False, label='E-mail du parent', widget=forms.EmailInput(attrs={'class': 'form-input'}))
    relation = forms.ChoiceField(choices=RELATIONS, required=False, label='Lien avec l’élève', widget=forms.Select(attrs={'class': 'form-input'}))
    is_primary = forms.BooleanField(required=False, initial=True, label='Contact principal', widget=forms.CheckboxInput(attrs={'class': 'rounded border-slate-300'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['existing_parent'].queryset = Parent.objects.order_by('last_name', 'first_name')
        self.fields['relation'].initial = 'pere'

    def clean(self):
        data = super().clean()
        if not data.get('existing_parent') and (data.get('first_name') or data.get('last_name')):
            if not data.get('phone'):
                self.add_error('phone', 'Le téléphone est obligatoire pour créer un nouveau parent.')
        return data


class EnrollmentForm(forms.Form):
    classroom = forms.ModelChoiceField(
        queryset=ClassRoom.objects.none(),
        required=False,
        label='Classe',
        widget=forms.Select(attrs={'class': 'form-input', 'id': 'id_classroom'}),
    )
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        required=False,
        label='Année scolaire',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        year = AcademicYear.objects.filter(is_current=True).first()
        if year:
            qs = ClassRoom.objects.filter(academic_year=year).select_related('level')
            self.fields['classroom'].queryset = qs
            self.fields['academic_year'].initial = year
        else:
            self.fields['classroom'].queryset = ClassRoom.objects.select_related('level').all()
