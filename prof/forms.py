from django import forms

from .models import BulletinAppreciation, TeachingMaterial


class TeachingMaterialForm(forms.ModelForm):
    class Meta:
        model = TeachingMaterial
        fields = ['classroom', 'subject', 'title', 'description', 'file', 'is_published']
        widgets = {
            'classroom': forms.Select(attrs={'class': 'form-input'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'file': forms.FileInput(attrs={'class': 'form-input'}),
        }


class AppreciationForm(forms.ModelForm):
    class Meta:
        model = BulletinAppreciation
        fields = ['appreciation', 'is_general']
        widgets = {
            'appreciation': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }
