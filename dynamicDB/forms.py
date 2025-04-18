from django import forms
from .models import PDFDocument

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = PDFDocument
        fields = ['title', 'pdf_file']

class TopicExtractionForm(forms.Form):
    TOPIC_COUNT_CHOICES = [
        (2, '2 Topics'),
        (3, '3 Topics (Default)'),
        (4, '4 Topics'),
        (5, '5 Topics'),
    ]
    
    topic_count = forms.ChoiceField(
        choices=TOPIC_COUNT_CHOICES,
        initial=3,
        label='Number of Topics',
        help_text='Choose how many main topics to extract from the PDF content.'
    ) 