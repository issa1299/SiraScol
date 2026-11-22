from django.urls import path
from . import views
from . import parent_views
from . import promotion_views

app_name = 'students'

urlpatterns = [
    path('fin-annee/', promotion_views.promotion_home, name='promotion_home'),
    path('fin-annee/classe/<int:classroom_id>/', promotion_views.promotion_class, name='promotion_class'),
    path('fin-annee/classe/<int:classroom_id>/appliquer/', promotion_views.promotion_apply, name='promotion_apply'),
    path('fin-annee/classe/<int:classroom_id>/auto/', promotion_views.promotion_auto, name='promotion_auto'),
    path('fin-annee/listes/<int:year_id>/', promotion_views.promotion_lists, name='promotion_lists'),

    path('cartes/', views.cards_home, name='cards_home'),
    path('cartes/classe/<int:classroom_id>/', views.cards_class, name='cards_class'),
    path('cartes/classe/<int:classroom_id>/pdf/', views.cards_class_pdf, name='cards_class_pdf'),
    path('', views.student_list, name='list'),
    path('pdf/', views.student_list_pdf, name='list_pdf'),
    path('ajouter/', views.student_create, name='create'),
    path('importer/', views.student_import, name='import'),
    path('<int:pk>/', views.student_detail, name='detail'),
    path('<int:pk>/qr/', views.student_qr, name='qr'),
    path('<int:pk>/paiement/tranche/', views.student_payment_installment, name='payment_installment'),
    path('<int:pk>/carte/', views.student_card, name='card'),
    path('<int:pk>/carte/apercu/', views.student_card_preview, name='card_preview'),
    path('<int:pk>/carte/pdf/', views.student_card_pdf, name='card_pdf'),
    path('<int:pk>/carte/image/', views.student_card_image, name='card_image'),
    path('<int:pk>/modifier/', views.student_edit, name='edit'),
    path('parents/', parent_views.parent_list, name='parent_list'),
    path('parents/pdf/', parent_views.parent_list_pdf, name='parent_list_pdf'),
    path('parents/synchroniser/', parent_views.parent_sync, name='parent_sync'),
    path('parents/ajouter/', parent_views.parent_create, name='parent_create'),
    path('parents/<int:pk>/', parent_views.parent_detail, name='parent_detail'),
    path('parents/<int:pk>/enfants/', parent_views.parent_children_modal, name='parent_children'),
    path('parents/<int:pk>/lier/', parent_views.parent_link_modal, name='parent_link'),
    path('parents/<int:pk>/delier/<int:student_id>/', parent_views.parent_unlink, name='parent_unlink'),
    path('parents/<int:pk>/modifier/', parent_views.parent_edit, name='parent_edit'),
]
