from django.contrib import admin
from .models import PDFDocument, Topic, Chapter, ContentPoint, GameContentMapping

class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0

class ContentPointInline(admin.TabularInline):
    model = ContentPoint
    extra = 0

class GameMappingInline(admin.TabularInline):
    model = GameContentMapping
    extra = 0

class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'number', 'pdf_document', 'start_page', 'end_page')
    list_filter = ('pdf_document',)
    search_fields = ('title', 'content')
    inlines = [TopicInline]

class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'pdf_document', 'chapter', 'order', 'confidence_score')
    list_filter = ('pdf_document', 'chapter')
    search_fields = ('title', 'content')
    inlines = [ContentPointInline]

class ContentPointAdmin(admin.ModelAdmin):
    list_display = ('topic', 'is_key_point', 'text')
    list_filter = ('is_key_point', 'topic__chapter')
    search_fields = ('text', 'simplified_text')
    inlines = [GameMappingInline]

class GameMappingAdmin(admin.ModelAdmin):
    list_display = ('game_type', 'content_point', 'difficulty', 'active')
    list_filter = ('game_type', 'active', 'difficulty')
    search_fields = ('content_point__text', 'content_point__topic__title')

class PDFDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_textbook', 'processing_status', 'uploaded_at', 'processed_at')
    list_filter = ('is_textbook', 'processing_status')
    search_fields = ('title', 'author')
    readonly_fields = ('uploaded_at', 'processed_at', 'processing_status')

admin.site.register(PDFDocument, PDFDocumentAdmin)
admin.site.register(Topic, TopicAdmin)
admin.site.register(Chapter, ChapterAdmin)
admin.site.register(ContentPoint, ContentPointAdmin)
admin.site.register(GameContentMapping, GameMappingAdmin)

