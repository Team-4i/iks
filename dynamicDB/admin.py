from django.contrib import admin
from .models import PDFDocument, Chapter, MainTopic, TopicGroup, SummaryTopic, ActivePDFSelection, ActiveTopicGroups

# Register your models here.
admin.site.register(PDFDocument)
admin.site.register(Chapter)
admin.site.register(MainTopic)
admin.site.register(TopicGroup)
admin.site.register(SummaryTopic)
admin.site.register(ActivePDFSelection)
admin.site.register(ActiveTopicGroups)

