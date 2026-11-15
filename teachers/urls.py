from django.urls import path
from . import views
from . import portal_views

app_name = 'teachers'

urlpatterns = [
    path('espace/', portal_views.portal_classes, name='portal_classes'),
    path('espace/classe/<int:classroom_id>/', portal_views.portal_class, name='portal_class'),

    # Comme EduNet : page d'accueil = liste + KPIs + tableau
    path('', views.teacher_list, name='list'),
    path('dashboard/', views.personnel_dashboard, name='dashboard'),
    path('liste/', views.teacher_list, name='staff_list'),
    path('enseignants/', views.teacher_list, name='enseignants'),
    path('ajouter/', views.teacher_create, name='create'),
    path('<int:pk>/', views.teacher_detail, name='detail'),
    path('<int:pk>/modifier/', views.teacher_edit, name='edit'),
    path('<int:pk>/affectations/', views.teacher_assign, name='assign'),
    path('presences/', views.staff_attendance, name='presences'),
    path('contrats/', views.staff_contracts, name='contracts'),
    path('salaires/', views.staff_salaries, name='salaries'),
    path('documents/', views.staff_documents, name='documents'),
    path('rapports/', views.staff_reports, name='reports'),
    path('mise-en-place/', views.mise_en_place, name='mise_en_place'),
    path('qr-codes/', views.staff_qr_codes, name='qr_codes'),
    path('<int:pk>/qr/', views.staff_qr_one, name='qr'),
]
