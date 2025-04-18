from django.db import models
from django.utils import timezone
import os

# Create your models here.

class PDFDocument(models.Model):
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='pdfs/', max_length=500)
    converted_image = models.ImageField(upload_to='converted_images/', max_length=500)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        # Delete the files when the model instance is deleted
        if self.pdf_file:
            if os.path.isfile(self.pdf_file.path):
                os.remove(self.pdf_file.path)
        if self.converted_image:
            if os.path.isfile(self.converted_image.path):
                os.remove(self.converted_image.path)
        super().delete(*args, **kwargs)

class Chapter(models.Model):
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=255)
    content = models.TextField()
    start_page = models.IntegerField()
    end_page = models.IntegerField()
    confidence_score = models.FloatField(default=0.0)
    order = models.IntegerField(default=0)  # To maintain the order of chapters in the document

    def __str__(self):
        return f"{self.title} ({self.pdf_document.title})"
    
    class Meta:
        ordering = ['order']

class MainTopic(models.Model):
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='main_topics')
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    chapters = models.ManyToManyField(Chapter, related_name='main_topics')
    order = models.IntegerField(default=0)  # To maintain the order of topics
    
    def __str__(self):
        return f"{self.title} ({self.pdf_document.title})"
    
    class Meta:
        ordering = ['order']

class TopicGroup(models.Model):
    """Model to group related topics under a broader category"""
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='topic_groups')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    topics = models.ManyToManyField(MainTopic, related_name='topic_groups')
    order = models.IntegerField(default=0)
    
    # Optional parent-child relationship for hierarchical grouping
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    # Semantic similarity score between topics in this group
    similarity_score = models.FloatField(default=0.0)
    
    # Keywords or tags associated with this topic group
    keywords = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.pdf_document.title})"
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Topic Group'
        verbose_name_plural = 'Topic Groups'
