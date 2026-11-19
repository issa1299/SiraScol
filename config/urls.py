from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('eleves/', include('students.urls')),
    path('enseignants/', include('teachers.urls')),
    path('', include('academics.urls')),
    path('notes/', include('grades.urls')),
    path('absences/', include('attendance.urls')),
    path('finances/', include('finance.urls')),
    path('emploi-du-temps/', include('timetable.urls')),
    path('annonces/', include('communication.urls')),
    path('mon-espace/', include('eleve.urls')),
    path('mon-espace-prof/', include('prof.urls')),
    path('mon-espace-parent/', include('parent.urls')),
    path('mon-espace-secretaire/', include('secretariat.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


handler404 = 'core.views.page_not_found'
handler500 = 'core.views.server_error'
