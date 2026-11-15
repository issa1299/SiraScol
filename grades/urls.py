from django.urls import path
from . import views
from . import bulletin_views
from . import template_views

app_name = 'grades'

urlpatterns = [
    path('', views.grades_classes, name='list'),
    path('saisie-eleve/', views.saisie_eleve, name='saisie_eleve'),
    path('saisie-classe/', views.saisie_classe, name='saisie_classe'),
    path('liste-eleves/', views.cotes_liste_eleves, name='liste_eleves'),
    path('modifier/', views.cotes_modifier, name='modifier'),
    path('valider/', views.cotes_valider, name='valider'),
    path('niveaux/', views.cotes_niveaux, name='niveaux'),
    path('palmares/', views.cotes_palmares, name='palmares'),
    path('historique/', views.cotes_historique, name='historique'),

    path('classes/', views.grades_classes, name='classes'),
    path('classes/<int:classroom_id>/', views.class_assessments, name='class_assessments'),
    path('nouvelle/', views.assessment_create, name='create'),
    path('<int:pk>/saisie/', views.grade_entry, name='entry'),

    path('bulletins/', bulletin_views.bulletin_list, name='bulletin_list'),
    path('bulletins/apercu/', bulletin_views.bulletin_preview, name='bulletin_preview'),
    path('bulletins/pdf-classe/', bulletin_views.bulletin_class_pdf, name='bulletin_class_pdf'),
    path('bulletin/<int:student_id>/', bulletin_views.bulletin, name='bulletin'),
    path('bulletin/<int:student_id>/pdf/', bulletin_views.bulletin_pdf, name='bulletin_pdf'),

    path('modeles-bulletin/', template_views.template_list, name='template_list'),
    path('modeles-bulletin/ajouter/', template_views.template_create, name='template_create'),
    path('modeles-bulletin/<int:pk>/', template_views.template_edit, name='template_edit'),
    path('modeles-bulletin/<int:pk>/defaut/', template_views.template_set_default, name='template_set_default'),
]
