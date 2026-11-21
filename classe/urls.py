from django.urls import path

from . import views

app_name = 'classe'

urlpatterns = [
    path('', views.classes_list, name='classes'),
    path('<int:pk>/', views.class_space, name='space'),
    path('<int:pk>/rapport/<str:kind>/', views.rapport_pdf, name='rapport'),
    path('<int:pk>/matieres/<int:subject_id>/supprimer/', views.matiere_delete, name='matiere_delete'),
    path('<int:pk>/sanctions/<int:sanction_id>/supprimer/', views.sanction_delete, name='sanction_delete'),
]
