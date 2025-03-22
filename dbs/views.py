from django.shortcuts import render, redirect
from django.apps import apps
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
import csv
import json
from django.core.exceptions import ValidationError
from django.contrib import messages
from .services.ai_service import GeminiService
import inspect
import traceback
from django.db import transaction
from .utils.gemini_utils import GeminiHelper
import google.generativeai as genai
from django.conf import settings
import subprocess
import sys
import pkg_resources
from .utils.data_loader import DataLoader

@staff_member_required
def database_overview(request):
    all_models = []
    
    for app_config in apps.get_app_configs():
        app_models = []
        for model in app_config.get_models():
            if model in admin.site._registry:
                # Get model fields for import/export
                fields = [field.name for field in model._meta.fields 
                         if not field.auto_created]
                model_info = {
                    'name': model._meta.verbose_name.title(),
                    'count': model.objects.count(),
                    'app_label': app_config.label,
                    'model_name': model._meta.model_name,
                    'fields': fields,
                }
                app_models.append(model_info)
        
        if app_models:
            all_models.append({
                'app_name': app_config.verbose_name,
                'app_label': app_config.label,
                'models': app_models
            })
    
    return render(request, 'dbs/database_overview.html', {
        'apps': all_models
    })

@staff_member_required
@require_POST
def import_data(request, app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
        file = request.FILES.get('file')
        
        if not file:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        # Read CSV file
        decoded_file = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        
        success_count = 0
        errors = []
        
        for row in reader:
            try:
                instance = model(**row)
                instance.full_clean()
                instance.save()
                success_count += 1
            except Exception as e:
                errors.append(f"Row {reader.line_num}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'imported': success_count,
            'errors': errors
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@staff_member_required
def export_data(request, app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
        queryset = model.objects.all()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{model_name}_export.csv"'
        
        writer = csv.writer(response)
        fields = [field.name for field in model._meta.fields if not field.auto_created]
        
        # Write header
        writer.writerow(fields)
        
        # Write data
        for obj in queryset:
            row = [getattr(obj, field) for field in fields]
            writer.writerow(row)
        
        return response
    except Exception as e:
        messages.error(request, f'Export failed: {str(e)}')
        return redirect('dbs:database_overview')

@staff_member_required
def code_editor(request):
    example_snippets = {
        'dynamic_data_generation': '''# Dynamic Data Generation using Constitutional Articles
gemini_helper = GeminiHelper()

# Get source articles (modify filter as needed)
source_articles = ConstitutionalArticle.objects.filter(
    article_title__icontains='fundamental rights'
)[:5]

# Example 1: Generate Legal Cases
context = """
Create legal case scenarios that:
- Involve violation of fundamental rights
- Include real-world situations
- Specify legal remedies
"""

for article in source_articles:
    result = gemini_helper.generate_model_data(
        target_model=Case,
        source_article=article,
        context=context,
        count=2  # 2 cases per article
    )
    print(f"Article {article.article_number}: {result['message']}")

# Example 2: Generate Quiz Questions
context = """
Create multiple choice questions that:
- Test understanding of constitutional rights
- Include 4 options with correct answer
- Vary in difficulty
"""

for article in source_articles:
    result = gemini_helper.generate_model_data(
        target_model=QuizQuestion,
        source_article=article,
        context=context,
        count=3  # 3 questions per article
    )
    print(f"Article {article.article_number}: {result['message']}")

# Example 3: Generate Court Judgments
context = """
Create court judgment summaries that:
- Reference constitutional articles
- Include judicial interpretations
- Cite previous relevant cases
"""

for article in source_articles:
    result = gemini_helper.generate_model_data(
        target_model=Judgment,
        source_article=article,
        context=context,
        count=1  # 1 judgment per article
    )
    print(f"Article {article.article_number}: {result['message']}")
''',
        'simple_generation': '''# Simple Example for Any Model
gemini_helper = GeminiHelper()

# 1. Select a source article
article = ConstitutionalArticle.objects.get(article_number='21')  # Article 21

# 2. Define your context
context = """
What you want to generate:
- Specific requirements
- Special considerations
- Data characteristics
"""

# 3. Generate data for your model
result = gemini_helper.generate_model_data(
    target_model=YourModel,  # Replace with your model
    source_article=article,
    context=context,
    count=5  # Number of entries to generate
)

if result['success']:
    print(result['message'])
    # Access generated objects if needed
    for obj in result['objects']:
        print(f"Created: {obj}")
else:
    print(f"Error: {result['error']}")
'''
    }

    # Get all models and their fields with detailed information
    models_info = {}
    
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            # Get model's module path for imports
            model_path = f"{model.__module__}.{model.__name__}"
            
            # Get fields info
            fields = []
            for field in model._meta.fields:
                if not field.auto_created:
                    field_info = {
                        'name': field.name,
                        'type': field.get_internal_type(),
                        'required': not field.null if hasattr(field, 'null') else True,
                        'related_model': field.related_model.__name__ if hasattr(field, 'related_model') and field.related_model else None,
                    }
                    fields.append(field_info)
            
            # Get model methods
            methods = []
            for name, member in inspect.getmembers(model):
                if inspect.isfunction(member) and not name.startswith('_'):
                    methods.append(name)
            
            models_info[model_path] = {
                'name': model._meta.verbose_name.title(),
                'app_label': model._meta.app_label,
                'model_name': model._meta.model_name,
                'fields': fields,
                'methods': methods,
                'import_path': f"from {model.__module__} import {model.__name__}"
            }

    # Add the examples to your template context
    return render(request, 'dbs/code_editor.html', {
        'models_info': json.dumps(models_info),
        'example_snippets': json.dumps(example_snippets)
    })

@staff_member_required
@require_POST
def get_ai_suggestion(request):
    prompt = request.POST.get('prompt')
    models_info = request.POST.get('models_info')
    
    ai_service = GeminiService()
    result = ai_service.get_code_suggestion(prompt, models_info)
    
    return JsonResponse(result)

@staff_member_required
@require_POST
def execute_code(request):
    code = request.POST.get('code')
    try:
        # Create a local context with all models pre-imported
        local_context = {}
        
        # Add all models to the context
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                model_name = model.__name__
                local_context[model_name] = model
        
        # Add commonly used modules and utilities
        import random
        import google.generativeai as genai
        
        # Initialize Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
        
        # Update local context with necessary modules and utilities
        local_context.update({
            'random': random,
            'genai': genai,
            'gemini_model': gemini_model,
            'GeminiHelper': GeminiHelper,
            'gemini_helper': GeminiHelper(),
            'DataLoader': DataLoader,
            'data_loader': DataLoader()
        })

        # Execute code within a transaction
        with transaction.atomic():
            exec(code, {'__builtins__': __builtins__}, local_context)
            
        return JsonResponse({
            'success': True,
            'message': 'Code executed successfully'
        })
                
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@staff_member_required
@require_POST
def analyze_error(request):
    code = request.POST.get('code')
    error = request.POST.get('error')
    traceback = request.POST.get('traceback')
    
    try:
        gemini = GeminiHelper()
        fixed_code = gemini.analyze_error(code, error, traceback)
        
        return JsonResponse({
            'success': True,
            'fixed_code': fixed_code
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@staff_member_required
@require_POST
def improve_code(request):
    code = request.POST.get('code')
    
    try:
        gemini = GeminiHelper()
        improved_code = gemini.improve_code(code)
        
        return JsonResponse({
            'success': True,
            'improved_code': improved_code
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@staff_member_required
@require_POST
def install_package(request):
    package_name = request.POST.get('package_name')
    
    try:
        # Use pip to install the package
        process = subprocess.Popen(
            [sys.executable, '-m', 'pip', 'install', package_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = process.communicate()
        output = stdout.decode() + stderr.decode()
        
        if process.returncode == 0:
            return JsonResponse({
                'success': True,
                'output': output
            })
        else:
            return JsonResponse({
                'success': False,
                'error': output
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@staff_member_required
def list_packages(request):
    try:
        # Get list of installed packages
        installed_packages = [
            f"{dist.key} ({dist.version})"
            for dist in pkg_resources.working_set
        ]
        
        return JsonResponse({
            'success': True,
            'packages': '\n'.join(sorted(installed_packages))
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
