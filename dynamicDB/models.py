from django.db import models
from django.utils import timezone
import os

# Create your models here.

class PDFDocument(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    pdf_file = models.FileField(upload_to='pdfs/', max_length=500)
    converted_image = models.ImageField(upload_to='converted_images/', max_length=500)
    uploaded_at = models.DateTimeField(default=timezone.now)
    is_textbook = models.BooleanField(default=False)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        default='PENDING'
    )
    processing_message = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)

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
    number = models.IntegerField()
    start_page = models.IntegerField()
    end_page = models.IntegerField()
    content = models.TextField(blank=True)
    confidence_score = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['number']
    
    def __str__(self):
        return f"Chapter {self.number}: {self.title} ({self.pdf_document.title})"

class Topic(models.Model):
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='topics', null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='topics', null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    start_page = models.IntegerField()
    end_page = models.IntegerField()
    confidence_score = models.FloatField(default=0.0)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        if self.chapter:
            return f"{self.title} (Chapter {self.chapter.number})"
        return f"{self.title} ({self.pdf_document.title})"

class ContentPoint(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='content_points')
    text = models.TextField()
    is_key_point = models.BooleanField(default=False)
    simplified_text = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Point for {self.topic.title}"

class GameContentMapping(models.Model):
    GAME_CHOICES = [
        ('SNAKE_LADDER', 'Snake and Ladder'),
        ('HOUSIE', 'Constitutional Housie'),
        ('SPINWHEEL', 'Spin Wheel'),
        ('FLIPCARD', 'Flip Card')
    ]
    
    content_point = models.ForeignKey(ContentPoint, on_delete=models.CASCADE, related_name='game_mappings')
    game_type = models.CharField(max_length=20, choices=GAME_CHOICES)
    difficulty = models.IntegerField(default=1)  # 1-5 scale
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['content_point', 'game_type']
        
    def __str__(self):
        return f"{self.get_game_type_display()} - {self.content_point.topic.title}"
