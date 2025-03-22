"""
URL configuration for project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.contrib.auth.decorators import login_required
from users.views import home, landing_page, login_redirect_view
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView


urlpatterns = [
    path('', login_redirect_view, name='landing_page'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('home/', login_required(home), name='home'),
    path('game/', include('snake_ladder.urls')),
    path('housie-consti/', include('housie_consti.urls')),
    path('spinwheel/', include('spinwheel.urls')),
    path('dbs/', include('dbs.urls')),
    path('plat/', include('plat.urls')),
    path('flip-card/', include('flip_card.urls')),
    path('users/', include('users.urls', namespace='users')),
    # path('chat/', include('ChatAssis.urls', namespace='chat')),
    path('custom-login/', LoginView.as_view(template_name='account/login.html'), name='custom_login'),
    path('ai/', include('aicharacter.urls')),
    path('dynamicdb/', include('dynamicDB.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
