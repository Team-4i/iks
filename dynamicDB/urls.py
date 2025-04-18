from django.urls import path
from . import views

app_name = 'dynamicDB'

urlpatterns = [
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('view/<int:pk>/', views.view_pdf, name='view_pdf'),
    path('analyze_pdf/<int:pk>/', views.analyze_pdf, name='analyze_pdf'),
    path('visualize/<int:pk>/', views.visualize_topics, name='visualize_topics'),
    
    # Custom admin panel URLs
    path('admin-panel/', views.admin_panel_dashboard, name='admin_panel_dashboard'),
    path('admin-panel/pdfs/', views.admin_panel_pdfs, name='admin_panel_pdfs'),
    path('admin-panel/pdf/<int:pk>/', views.admin_panel_pdf_detail, name='admin_panel_pdf_detail'),
    path('admin-panel/topic-groups/', views.admin_panel_topic_groups, name='admin_panel_topic_groups'),
    path('admin-panel/topic-group/<int:pk>/', views.admin_panel_topic_group_detail, name='admin_panel_topic_group_detail'),
    path('admin-panel/main-topics/', views.admin_panel_main_topics, name='admin_panel_main_topics'),
    path('admin-panel/main-topic/<int:pk>/', views.admin_panel_main_topic_detail, name='admin_panel_main_topic_detail'),
    path('admin-panel/chapters/', views.admin_panel_chapters, name='admin_panel_chapters'),
    path('admin-panel/chapter/<int:pk>/', views.admin_panel_chapter_detail, name='admin_panel_chapter_detail'),
    
    # Summary Topics URLs
    path('admin-panel/summary-topics/', views.admin_panel_summary_topics, name='admin_panel_summary_topics'),
    path('admin-panel/summary-topic/<int:pk>/', views.admin_panel_summary_topic_detail, name='admin_panel_summary_topic_detail'),
    path('admin-panel/generate-summary-topics/<int:topic_group_id>/', views.generate_summary_topics, name='generate_summary_topics'),
    path('admin-panel/generate-summary-for-active-groups/', views.generate_summary_for_active_groups, name='generate_summary_for_active_groups'),
    
    # PDF selector URLs
    path('select-pdf/', views.pdf_selector, name='pdf_selector'),
    path('set-active-pdf/', views.set_active_pdf, name='set_active_pdf'),
    path('get-pdf-structure/', views.get_pdf_structure, name='get_pdf_structure'),
    
    # Active Topic Groups URLs
    path('active-topic-groups/', views.active_topic_groups, name='active_topic_groups'),
    path('set-active-topic-group/', views.set_active_topic_group, name='set_active_topic_group'),
    path('remove-active-topic-group/<int:pk>/', views.remove_active_topic_group, name='remove_active_topic_group'),
    
    # AJAX endpoints for the admin panel
    path('admin-panel/api/update-pdf/<int:pk>/', views.admin_panel_update_pdf, name='admin_panel_update_pdf'),
    path('admin-panel/api/delete-pdf/<int:pk>/', views.admin_panel_delete_pdf, name='admin_panel_delete_pdf'),
    path('admin-panel/api/update-topic-group/<int:pk>/', views.admin_panel_update_topic_group, name='admin_panel_update_topic_group'),
    path('admin-panel/api/delete-topic-group/<int:pk>/', views.admin_panel_delete_topic_group, name='admin_panel_delete_topic_group'),
    path('admin-panel/api/update-main-topic/<int:pk>/', views.admin_panel_update_main_topic, name='admin_panel_update_main_topic'),
    path('admin-panel/api/delete-main-topic/<int:pk>/', views.admin_panel_delete_main_topic, name='admin_panel_delete_main_topic'),
    path('admin-panel/api/update-chapter/<int:pk>/', views.admin_panel_update_chapter, name='admin_panel_update_chapter'),
    path('admin-panel/api/delete-chapter/<int:pk>/', views.admin_panel_delete_chapter, name='admin_panel_delete_chapter'),
    path('admin-panel/api/update-summary-topic/<int:pk>/', views.admin_panel_update_summary_topic, name='admin_panel_update_summary_topic'),
    path('admin-panel/api/delete-summary-topic/<int:pk>/', views.admin_panel_delete_summary_topic, name='admin_panel_delete_summary_topic'),
] 