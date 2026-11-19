from django.urls import path

from . import views

app_name = 'secretariat'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('eleves/', views.eleves, name='eleves'),
    path('eleves/<int:pk>/archiver/', views.eleve_archive, name='eleve_archive'),
    path('eleves/<int:pk>/transfert/', views.transfert, name='transfert'),
    path('inscriptions/', views.inscriptions, name='inscriptions'),
    path('classes/', views.classes, name='classes'),
    path('classes/<int:classroom_id>/eleves/', views.classe_eleves, name='classe_eleves'),
    path('enseignants/', views.enseignants, name='enseignants'),
    path('documents/', views.documents, name='documents'),
    path('documents/certificat/<int:student_id>/', views.doc_certificat, name='certificat'),
    path('documents/attestation/<int:student_id>/', views.doc_attestation, name='attestation'),
    path('documents/fiche/<int:student_id>/', views.doc_fiche, name='fiche'),
    path('documents/liste/<int:classroom_id>/', views.doc_liste_classe, name='liste_classe'),
    path('annonces/', views.annonces, name='annonces'),
    path('annonces/<int:pk>/transmettre/', views.transmettre_direction, name='transmettre'),
    path('notifications/', views.notifications, name='notifications'),
    path('profil/', views.profil, name='profil'),
]
