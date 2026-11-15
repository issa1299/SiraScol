from django import forms
from .models import Student, Enrollment
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
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'enrollment_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }


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
