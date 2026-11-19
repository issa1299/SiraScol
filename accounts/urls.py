from django.urls import path
from .views import CustomLoginView, CustomLogoutView, ForcePasswordChangeView

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('mot-de-passe-initial/', ForcePasswordChangeView.as_view(), name='force_password_change'),
]
