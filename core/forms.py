from django import forms
from .models import SchoolSettings, SchoolPhoto


class SchoolSettingsForm(forms.ModelForm):
    class Meta:
        model = SchoolSettings
        fields = [
            'name', 'short_name', 'motto',
            'establishment_type', 'establishment_status',
            'academic_year_label', 'country', 'currency',
            'phone', 'phone2', 'email', 'website',
            'province', 'city', 'commune', 'district', 'inspection', 'address',
            'director_name', 'logo', 'stamp', 'cover_photo',
            'footer_text', 'header_left', 'header_right', 'bulletin_subtitle',
            'maintenance_mode',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'short_name': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'motto': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'establishment_type': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm', 'placeholder': 'Polyvalent'}),
            'establishment_status': forms.Select(
                choices=[('', '—'), ('Privé', 'Privé'), ('Public', 'Public'), ('Confessionnel', 'Confessionnel'), ('Communautaire', 'Communautaire')],
                attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'},
            ),
            'academic_year_label': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'country': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'currency': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'phone': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'phone2': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'email': forms.EmailInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'website': forms.URLInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'province': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'city': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'commune': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'district': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'inspection': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'address': forms.Textarea(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm', 'rows': 2}),
            'director_name': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'w-full text-sm', 'accept': 'image/*'}),
            'stamp': forms.ClearableFileInput(attrs={'class': 'w-full text-sm', 'accept': 'image/*'}),
            'cover_photo': forms.ClearableFileInput(attrs={'class': 'w-full text-sm', 'accept': 'image/*'}),
            'footer_text': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'header_left': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'header_right': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'bulletin_subtitle': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm'}),
            'maintenance_mode': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300'}),
        }


class SchoolPhotoForm(forms.ModelForm):
    class Meta:
        model = SchoolPhoto
        fields = ['title', 'image', 'is_primary']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2 text-sm', 'placeholder': 'Ex: Façade de l\'école'}),
            'image': forms.ClearableFileInput(attrs={'class': 'w-full text-sm', 'accept': 'image/*'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }
