from django.urls import path
from . import views

app_name = 'timetable'

urlpatterns = [
    path('', views.timetable_home, name='home'),
    path('generer/', views.generate_edt, name='generate'),
    path('creneaux/sauver/', views.slots_save, name='slots_save'),
    path('classe/<int:classroom_id>/sauver/', views.timetable_entry_save, name='save_entry'),
    path('entree/<int:pk>/supprimer/', views.timetable_entry_delete, name='delete_entry'),
    path('classe/<int:classroom_id>/ajouter/', views.timetable_entry_form, name='add_entry'),
    path('classe/<int:classroom_id>/pdf/', views.export_pdf, name='export_pdf'),
    path('classe/<int:classroom_id>/word/', views.export_word, name='export_word'),
]
