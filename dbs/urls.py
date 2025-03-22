from django.urls import path
from . import views

app_name = 'dbs'

urlpatterns = [
    path('overview/', views.database_overview, name='database_overview'),
    path('import/<str:app_label>/<str:model_name>/', views.import_data, name='import_data'),
    path('export/<str:app_label>/<str:model_name>/', views.export_data, name='export_data'),
    path('code-editor/', views.code_editor, name='code_editor'),
    path('ai-suggestion/', views.get_ai_suggestion, name='ai_suggestion'),
    path('execute-code/', views.execute_code, name='execute_code'),
    path('analyze-error/', views.analyze_error, name='analyze_error'),
    path('improve-code/', views.improve_code, name='improve_code'),
    path('install-package/', views.install_package, name='install_package'),
    path('list-packages/', views.list_packages, name='list_packages'),
] 