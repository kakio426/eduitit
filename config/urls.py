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
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
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
    path('school-violence/', include('school_violence.urls', namespace='school_violence')),
    path('school_violence/', RedirectView.as_view(url='/school-violence/', permanent=True)),
    path('padlet/', include('padlet_bot.urls', namespace='padlet_bot')),
    path('chess/', include('chess.urls', namespace='chess')),
    path('janggi/', include('janggi.urls', namespace='janggi')),
    path('studentmbti/', include('studentmbti.urls', namespace='studentmbti')),
    path('collect/', include('collect.urls', namespace='collect')),
    path('reservations/', include('reservations.urls', namespace='reservations')),
    path('encyclopedia/', include('encyclopedia.urls', namespace='encyclopedia')),
    path('version-manager/', include('version_manager.urls', namespace='version_manager')),
    path('m/', include('studentmbti.urls', namespace='studentmbti_short')),  # 짧은 URL 별칭에 고유 네임스페이스 부여
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
