from django.urls import path

from . import views

app_name = 'examens'

urlpatterns = [
    # Menu « Examens nationaux »
    path('', views.exam_dashboard, name='dashboard'),
    path('candidats-def/', views.candidate_list, name='candidats_def'),
    path('candidats-bac/', views.candidate_list, name='candidats_bac'),
    path('inscriptions/', views.inscriptions_home, name='inscriptions'),
    path('documents/', views.documents, name='documents'),
    path('listes-statistiques/', views.lists_stats, name='lists_stats'),
    path('resultats/', views.results, name='results'),

    # Inscriptions
    path('candidats/', views.candidate_list, name='candidate_list'),
    path('candidats/ajouter/', views.candidate_create, name='candidate_create'),
    path('candidats/<int:pk>/', views.candidate_detail, name='candidate_detail'),
    path('candidats/<int:pk>/modifier/', views.candidate_edit, name='candidate_edit'),
    path('candidats/<int:pk>/supprimer/', views.candidate_delete, name='candidate_delete'),
    path('candidats/<int:pk>/fiche/', views.candidate_fiche_pdf, name='candidate_fiche_pdf'),
    path('importer-eleves/', views.import_from_class, name='import_from_class'),
    path('importer-eleves/confirmer/', views.import_confirm, name='import_confirm'),
    path('importer-excel/', views.excel_import, name='excel_import'),
    path('inscription-groupee/', views.bulk_enroll, name='bulk_enroll'),

    # Sessions & exports
    path('sessions/ajouter/', views.session_create, name='session_create'),
    path('export/', views.export_report, name='export'),
]
