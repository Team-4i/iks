from django.contrib import admin
from .models import PDFDocument, Chapter, MainTopic, TopicGroup

# Register your models here.
admin.site.register(PDFDocument)
admin.site.register(Chapter)
admin.site.register(MainTopic)
admin.site.register(TopicGroup)

