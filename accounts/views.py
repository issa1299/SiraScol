from django.contrib.auth.views import LoginView, LogoutView
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
        return reverse_lazy('core:dashboard')


class CustomLogoutView(View):
    """Déconnexion en POST (sécurité) ou GET (lien simple)."""

    def post(self, request):
        logout(request)
        return redirect('accounts:login')

    def get(self, request):
        logout(request)
        return redirect('accounts:login')
