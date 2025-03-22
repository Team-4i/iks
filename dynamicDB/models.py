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

class Topic(models.Model):
    pdf_document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=255)
    content = models.TextField()
    start_page = models.IntegerField()
    end_page = models.IntegerField()
    confidence_score = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.title} ({self.pdf_document.title})"
