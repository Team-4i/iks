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

class Topic(models.Model):
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='main_topics')
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    chapters = models.ManyToManyField(Chapter, related_name='main_topics')
    order = models.IntegerField(default=0)  # To maintain the order of topics
    
    def __str__(self):
        return f"{self.title} ({self.pdf_document.title})"
    
    class Meta:
        ordering = ['order']

class MainTopic(models.Model):
    """Model to group related topics under a broader category"""
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='topic_groups')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    topics = models.ManyToManyField(Topic, related_name='topic_groups')
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

class SubTopic(models.Model):
    """Model to create a summary topic that groups related main topics within a topic group"""
    topic_group = models.ForeignKey(MainTopic, on_delete=models.CASCADE, related_name='summary_topics')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    main_topics = models.ManyToManyField(Topic, related_name='summary_topics')
    order = models.IntegerField(default=0)
    
    # Generate compact summary for display
    summary = models.TextField(blank=True)
    
    # For tracking relevance
    relevance_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} - {self.topic_group.title}"
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Summary Topic'
        verbose_name_plural = 'Summary Topics'

class ActivePDFSelection(models.Model):
    """Model to store the currently active PDF for platform use"""
    pdf = models.ForeignKey(PDFDocument, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Active PDF: {self.pdf.title}"
    
    def save(self, *args, **kwargs):
        # Ensure only one active PDF at a time by deactivating all others
        if self.is_active:
            ActivePDFSelection.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_pdf(cls):
        """Get the currently active PDF, or None if no PDF is active"""
        try:
            return cls.objects.filter(is_active=True).first().pdf
        except (cls.DoesNotExist, AttributeError):
            return None
    
    class Meta:
        verbose_name = 'Active PDF Selection'
        verbose_name_plural = 'Active PDF Selections'

class ActiveTopicGroups(models.Model):
    """Model to track which topic groups are currently active (limited to 2)"""
    topic_group = models.ForeignKey(MainTopic, on_delete=models.CASCADE, related_name='active_selections')
    selected_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Active Topic Group: {self.topic_group.title}"
    
    def save(self, *args, **kwargs):
        # Check if we already have 2 active topic groups
        # If so, remove the oldest one
        current_active_count = ActiveTopicGroups.objects.count()
        if current_active_count >= 2:
            # Get the oldest active topic group and delete it
            oldest = ActiveTopicGroups.objects.order_by('selected_at').first()
            if oldest and oldest != self:
                oldest.delete()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_groups(cls):
        """Get the currently active topic groups"""
        return cls.objects.all().order_by('-selected_at')
    
    class Meta:
        verbose_name = 'Active Topic Group'
        verbose_name_plural = 'Active Topic Groups'
