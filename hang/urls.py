from django.urls import path
from . import views

app_name = 'hang'

urlpatterns = [
    path('', views.game, name='game'),
]
