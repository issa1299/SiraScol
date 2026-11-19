from django.urls import path

from . import views

app_name = 'eleve'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('notes/', views.notes, name='notes'),
    path('bulletins/', views.bulletins, name='bulletins'),
    path('emploi-du-temps/', views.emploi_du_temps, name='timetable'),
    path('absences/', views.absences, name='absences'),
    path('devoirs/', views.homework_list, name='homework'),
    path('devoirs/<int:pk>/faire/', views.homework_toggle, name='homework_toggle'),
    path('informations/', views.informations, name='informations'),
    path('messagerie/', views.messagerie, name='messagerie'),
    path('annonces/', views.annonces, name='annonces'),
    path('bulletin/<int:student_id>/', views.bulletin_detail, name='bulletin_detail'),

    # Saisie des devoirs par les enseignants
    path('enseignant/devoirs/', views.teacher_homework, name='teacher_homework'),
    path('enseignant/devoirs/ajouter/', views.teacher_homework_form, name='teacher_homework_add'),
    path('enseignant/devoirs/<int:pk>/modifier/', views.teacher_homework_form, name='teacher_homework_edit'),
    path('enseignant/devoirs/<int:pk>/supprimer/', views.teacher_homework_delete, name='teacher_homework_delete'),
]
