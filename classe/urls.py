from django.urls import path

from . import views

app_name = 'classe'

# Les onglets sont intégrés à la fiche « Gestion des classes » (academics:classroom_detail).
# Ici ne restent que les actions et les rapports PDF.
urlpatterns = [
    path('<int:pk>/rapport/<str:kind>/', views.rapport_pdf, name='rapport'),
    path('<int:pk>/matieres/<int:subject_id>/supprimer/', views.matiere_delete, name='matiere_delete'),
    path('<int:pk>/sanctions/<int:sanction_id>/supprimer/', views.sanction_delete, name='sanction_delete'),
]
