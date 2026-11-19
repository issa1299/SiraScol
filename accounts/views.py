from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CustomLoginView(LoginView):
    """Connexion + redirection vers le tableau de bord adapté au rôle."""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        # Un seul point d'entrée : core:dashboard branche selon le rôle (serveur).
        profile = getattr(self.request.user, 'profile', None)
        if profile and profile.must_change_password:
            return reverse_lazy('accounts:force_password_change')
        return reverse_lazy('core:dashboard')


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'pwd-field'


class ForcePasswordChangeView(PasswordChangeView):
    """Première connexion : impose le changement du mot de passe initial."""

    template_name = 'accounts/force_password_change.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('core:dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = getattr(self.request.user, 'profile', None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=['must_change_password'])
        messages.success(self.request, 'Votre mot de passe a été modifié avec succès.')
        return response


class CustomLogoutView(View):
    """Déconnexion en POST (sécurité) ou GET (lien simple)."""

    def post(self, request):
        logout(request)
        return redirect('accounts:login')

    def get(self, request):
        logout(request)
        return redirect('accounts:login')
