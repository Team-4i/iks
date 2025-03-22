from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import Article, Case

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'article_number']

class CaseForm(forms.ModelForm):
    articles = forms.ModelMultipleChoiceField(
        queryset=Article.objects.all(),
        widget=FilteredSelectMultiple("Articles", False),
        required=True
    )

    class Meta:
        model = Case
        fields = ['title', 'description', 'articles']

    class Media:
        css = {
            'all': ['/static/admin/css/widgets.css'],
        }
        js = ['/admin/jsi18n/']