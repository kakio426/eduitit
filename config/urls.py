"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import health_check

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('secret-admin-kakio/', admin.site.urls),
    path('', include('core.urls')),
    path('products/', include('products.urls')),
    path('portfolio/', include('portfolio.urls')),
    path('accounts/', include('allauth.urls')),
    path('', include('insights.urls', namespace='insights')),
    path('autoarticle/', include('autoarticle.urls', namespace='autoarticle')),
    path('fortune/', include('fortune.urls', namespace='fortune')),
    path('ssambti/', include('ssambti.urls', namespace='ssambti')),
    path('artclass/', include('artclass.urls', namespace='artclass')),
    path('signatures/', include('signatures.urls', namespace='signatures')),
    path('consent/', include('consent.urls', namespace='consent')),
    path('chess/', include('chess.urls', namespace='chess')),
    path('janggi/', include('janggi.urls', namespace='janggi')),
    path('fairy-games/', include('fairy_games.urls', namespace='fairy_games')),
    path('ppobgi/', include('ppobgi.urls', namespace='ppobgi')),
    path('studentmbti/', include('studentmbti.urls', namespace='studentmbti')),
    path('collect/', include('collect.urls', namespace='collect')),
    path('handoff/', include('handoff.urls', namespace='handoff')),
    path('qrgen/', include('qrgen.urls', namespace='qrgen')),
    path('hwpx-chat/', include('hwpxchat.urls', namespace='hwpxchat')),
    path('reservations/', include('reservations.urls', namespace='reservations')),
    path('encyclopedia/', include('encyclopedia.urls', namespace='encyclopedia')),
    path('version-manager/', include('version_manager.urls', namespace='version_manager')),
    path('happy-seed/', include('happy_seed.urls', namespace='happy_seed')),
    path('seed-quiz/', include('seed_quiz.urls', namespace='seed_quiz')),
    path('noticegen/', include('noticegen.urls', namespace='noticegen')),
    path('timetable/', include('timetable.urls', namespace='timetable')),
    path('classcalendar/', include('classcalendar.urls', namespace='classcalendar')),
    path('parentcomm/', include('parentcomm.urls', namespace='parentcomm')),
    path('m/', include('studentmbti.urls', namespace='studentmbti_short')),  # 짧은 URL 별칭에 고유 네임스페이스 부여
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
