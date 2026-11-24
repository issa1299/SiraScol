from django.urls import path

from . import views

app_name = 'examens'

urlpatterns = [
    path('', views.exam_dashboard, name='dashboard'),
    path('candidats/', views.candidate_list, name='candidate_list'),
    path('candidats/ajouter/', views.candidate_create, name='candidate_create'),
    path('candidats/<int:pk>/', views.candidate_detail, name='candidate_detail'),
    path('candidats/<int:pk>/modifier/', views.candidate_edit, name='candidate_edit'),
    path('candidats/<int:pk>/supprimer/', views.candidate_delete, name='candidate_delete'),
    path('sessions/ajouter/', views.session_create, name='session_create'),
    path('inscription-groupee/', views.bulk_enroll, name='bulk_enroll'),
    path('export/', views.export_report, name='export'),
]
