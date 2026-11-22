from django.urls import path
from .views import CustomLoginView, CustomLogoutView, ForcePasswordChangeView
from . import webauthn_views

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('mot-de-passe-initial/', ForcePasswordChangeView.as_view(), name='force_password_change'),

    # Sécurité / Passkeys (WebAuthn)
    path('securite/', webauthn_views.security_page, name='security'),
    path('webauthn/enregistrement/debut/', webauthn_views.register_begin,
         name='webauthn_register_begin'),
    path('webauthn/enregistrement/fin/', webauthn_views.register_complete,
         name='webauthn_register_complete'),
    path('webauthn/connexion/debut/', webauthn_views.login_begin,
         name='webauthn_login_begin'),
    path('webauthn/connexion/fin/', webauthn_views.login_complete,
         name='webauthn_login_complete'),
    path('webauthn/<int:pk>/supprimer/', webauthn_views.delete_credential,
         name='webauthn_delete'),
]
