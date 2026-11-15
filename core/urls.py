from django.urls import path
from . import views
from . import config_views
from . import export_views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('annee/', views.set_academic_year, name='set_year'),
    path('parametres/', views.school_settings, name='settings'),
    path('rapports/', views.reports_stats, name='reports'),
    path('rapports/pdf/', views.reports_stats_pdf, name='reports_pdf'),

    # Configuration
    path('configuration/', config_views.config_home, name='config_home'),
    path('configuration/annees/', config_views.year_list, name='config_years'),
    path('configuration/annees/sauver/', config_views.year_save, name='config_year_save'),
    path('configuration/annees/<int:pk>/courante/', config_views.year_set_current, name='config_year_current'),
    path('configuration/matieres/', config_views.subject_list, name='config_subjects'),
    path('configuration/matieres/sauver/', config_views.subject_save, name='config_subject_save'),
    path('configuration/matieres/<int:pk>/supprimer/', config_views.subject_delete, name='config_subject_delete'),
    path('configuration/periodes/', config_views.period_list, name='config_periods'),
    path('configuration/periodes/sauver/', config_views.period_save, name='config_period_save'),
    path('configuration/types-evaluation/', config_views.assessment_type_list, name='config_assessment_types'),
    path('configuration/types-evaluation/sauver/', config_views.assessment_type_save, name='config_assessment_type_save'),
    path('configuration/types-frais/', config_views.fee_type_list, name='config_fee_types'),
    path('configuration/types-frais/sauver/', config_views.fee_type_save, name='config_fee_type_save'),
    path('configuration/salles/', config_views.room_list, name='config_rooms'),
    path('configuration/salles/sauver/', config_views.room_save, name='config_room_save'),
    path('configuration/creneaux/sauver/', config_views.slot_save, name='config_slot_save'),
    path('configuration/utilisateurs/', config_views.user_list, name='config_users'),
    path('configuration/utilisateurs/sauver/', config_views.user_save, name='config_user_save'),
    path('configuration/utilisateurs/<int:pk>/actif/', config_views.user_toggle_active, name='config_user_toggle'),
    path('configuration/utilisateurs/<int:pk>/mdp/', config_views.user_reset_password, name='config_user_password'),
    path('configuration/cycles/', config_views.cycle_level_list, name='config_cycles'),
    path('configuration/cycles/sauver/', config_views.cycle_save, name='config_cycle_save'),
    path('configuration/niveaux/sauver/', config_views.level_save, name='config_level_save'),
    path('configuration/niveaux/<int:pk>/supprimer/', config_views.level_delete, name='config_level_delete'),
    path('configuration/affectations/', config_views.assignment_list, name='config_assignments'),
    path('configuration/affectations/sauver/', config_views.assignment_save, name='config_assignment_save'),
    path('configuration/affectations/<int:pk>/supprimer/', config_views.assignment_delete, name='config_assignment_delete'),
    path('configuration/permissions/', config_views.permissions_matrix, name='config_permissions'),
    path('configuration/liaisons/', config_views.liaisons_dashboard, name='config_liaisons'),
    path('configuration/liaisons/comptes/', config_views.liaisons_fix_accounts, name='config_liaisons_accounts'),

    # Exports & sauvegarde
    path('export/eleves/', export_views.export_students, name='export_students'),
    path('export/notes/', export_views.export_grades, name='export_grades'),
    path('export/paiements/', export_views.export_payments, name='export_payments'),
    path('sauvegarde/', export_views.backup_download, name='backup'),
]
