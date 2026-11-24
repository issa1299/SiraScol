from django import forms
from core.widgets import SmartDateInput
from .models import Teacher, StaffAttendance, StaffContract, StaffSalary, StaffDocument


class TeacherForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'user' in self.fields:
            self.fields['user'].required = False
            self.fields['user'].queryset = self.fields['user'].queryset.order_by('username')
        for f in ('matricule', 'last_name', 'first_name', 'gender'):
            if f in self.fields:
                self.fields[f].required = True
        if 'email' in self.fields:
            self.fields['email'].required = False
        if 'user' in self.fields:
            del self.fields['user']

    class Meta:
        model = Teacher
        fields = [
            'photo', 'matricule', 'last_name', 'first_name', 'gender', 'date_of_birth',
            'phone', 'email', 'address',
            'category', 'function', 'department', 'speciality', 'diploma',
            'hire_date', 'contract_type', 'status', 'base_salary',
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ENS-2026-001'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'date_of_birth': SmartDateInput(),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'function': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Enseignant, Secrétaire…'}),
            'department': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Pédagogie, Administration…'}),
            'speciality': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Mathématiques'}),
            'diploma': forms.TextInput(attrs={'class': 'form-input'}),
            'hire_date': SmartDateInput(),
            'contract_type': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'step': 1}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = StaffAttendance
        fields = ['staff', 'date', 'time_in', 'time_out', 'status', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-input'}),
            'date': SmartDateInput(),
            'time_in': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'time_out': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'notes': forms.TextInput(attrs={'class': 'form-input'}),
        }


class ContractForm(forms.ModelForm):
    class Meta:
        model = StaffContract
        fields = ['staff', 'contract_type', 'function', 'start_date', 'end_date', 'salary', 'status', 'document', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-input'}),
            'contract_type': forms.Select(attrs={'class': 'form-input'}),
            'function': forms.TextInput(attrs={'class': 'form-input'}),
            'start_date': SmartDateInput(),
            'end_date': SmartDateInput(),
            'salary': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'document': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }


class SalaryForm(forms.ModelForm):
    class Meta:
        model = StaffSalary
        fields = ['staff', 'year', 'month', 'base', 'primes', 'retenues', 'advances', 'status', 'paid_at', 'notes']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-input'}),
            'year': forms.NumberInput(attrs={'class': 'form-input'}),
            'month': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 12}),
            'base': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'primes': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'retenues': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'advances': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'paid_at': SmartDateInput(),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = StaffDocument
        fields = ['staff', 'doc_type', 'title', 'file']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-input'}),
            'doc_type': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-input'}),
        }
