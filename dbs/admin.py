from django.contrib import admin
from .models import ConstitutionalArticle, SimplifiedArticle

@admin.register(ConstitutionalArticle)
class ConstitutionalArticleAdmin(admin.ModelAdmin):
    list_display = ('article_number', 'part', 'type', 'article_title')
    list_display_links = ('article_number', 'article_title')
    search_fields = ('article_number', 'article_title', 'original_text', 'simplified_explanation')
    list_filter = ('part', 'type')
    ordering = ('part', 'type', 'article_number')
    
    fieldsets = (
        ('Article Information', {
            'fields': ('article_number', 'article_title')
        }),
        ('Classification', {
            'fields': ('part', 'type')
        }),
        ('Content', {
            'fields': ('original_text', 'simplified_explanation'),
            'classes': ('wide',)
        }),
    )
    
    list_per_page = 20  # Number of items to display per page
    save_on_top = True  # Adds save buttons at the top of the change form



@admin.register(SimplifiedArticle)
class SimplifiedArticleAdmin(admin.ModelAdmin):
    list_display = ('article_number', 'simplified_content', 'last_simplified')
    search_fields = ('article_number', 'simplified_content', 'original_content')
    readonly_fields = ('last_simplified',)
    list_filter = ('last_simplified',)