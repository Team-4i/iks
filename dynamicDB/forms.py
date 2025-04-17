from django import forms
from .models import PDFDocument

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = PDFDocument
        fields = ['title', 'author', 'pdf_file', 'is_textbook']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control'}),
            'is_textbook': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'is_textbook': 'Process as textbook (extracts chapters and topics)',
            'author': 'Author/Source (optional)'
        } 