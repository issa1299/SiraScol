from django import forms

from .models import Homework


class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ['classroom', 'subject', 'title', 'instructions', 'due_date', 'document', 'is_published']
        widgets = {
            'classroom': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex. Exercices 12 à 15'}),
            'instructions': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Consignes données aux élèves…'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'document': forms.FileInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'classroom': 'Classe',
            'subject': 'Matière',
            'title': 'Titre du devoir',
            'instructions': 'Consignes',
            'due_date': 'Date limite',
            'document': 'Document associé (facultatif)',
            'is_published': 'Publié pour les élèves',
        }
