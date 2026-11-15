from django.urls import path
from . import views
from . import message_views

app_name = 'communication'

urlpatterns = [
    path('', views.documents_hub, name='list'),
    path('documents/', views.documents_hub, name='documents'),
    path('documents/ajouter/', views.document_upload, name='document_upload'),
    path('documents/<int:pk>/supprimer/', views.document_delete, name='document_delete'),
    path('annonces/', views.announcement_list, name='announcements'),
    path('nouvelle/', views.announcement_create, name='create'),
    path('messages/', message_views.message_inbox, name='inbox'),
    path('messages/nouveau/', message_views.message_compose, name='compose'),
    path('messages/<int:pk>/', message_views.message_detail, name='message_detail'),
    path('<int:pk>/', views.announcement_detail, name='detail'),
    path('<int:pk>/modifier/', views.announcement_edit, name='edit'),
]
