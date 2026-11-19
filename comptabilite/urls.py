from django.urls import path

from . import views

app_name = 'comptabilite'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('frais/', views.frais, name='frais'),
    path('paiements/', views.paiements, name='paiements'),
    path('depenses/', views.depenses, name='depenses'),
    path('impayes/', views.impayes, name='impayes'),
    path('impayes/pdf/', views.impayes_pdf, name='impayes_pdf'),
    path('impayes/<int:pk>/rappel/', views.rappel, name='rappel'),
    path('recus/', views.recus, name='recus'),
    path('recus/<int:pk>/pdf/', views.recu_pdf, name='recu_pdf'),
    path('recus/<int:pk>/annuler/', views.annuler_paiement, name='annuler'),
    path('rapports/', views.rapports, name='rapports'),
    path('profil/', views.profil, name='profil'),
]
