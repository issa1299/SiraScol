from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('classes/', views.classroom_list, name='classroom_list'),
    path('classes/reprendre/', views.clone_classrooms, name='clone_classrooms'),
    path('classes/ajouter/', views.classroom_create, name='classroom_create'),
    path('classes/programme/', views.classroom_bulk_add, name='classroom_bulk'),
    path('classes/<int:pk>/', views.classroom_detail, name='classroom_detail'),
    path('classes/<int:pk>/matieres/', views.classroom_subjects, name='classroom_subjects'),
    path('classes/<int:pk>/modifier/', views.classroom_edit, name='classroom_edit'),
]
