from django.contrib import admin
from .models import PDFDocument, Chapter, Topic, MainTopic, SubTopic, ActivePDFSelection, ActiveTopicGroups

# Register your models here.
admin.site.register(PDFDocument)
admin.site.register(Chapter)
admin.site.register(Topic)
admin.site.register(MainTopic)
admin.site.register(SubTopic)
admin.site.register(ActivePDFSelection)
admin.site.register(ActiveTopicGroups)

