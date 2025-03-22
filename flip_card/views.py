from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from dynamicDB.models import PDFDocument
from .models import UserProgress, LevelDocuments, PlayerPlatPoints
import json

@login_required
def start_page(request):
    """
    Renders the initial start page
    """
    return render(request, 'flip_card/start.html')

@login_required
def levels_page(request):
    """
    Renders the level selection page with user progress
    """
    # Get or create user progress
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    # Sync with platform immediately after getting progress
    progress.sync_with_platform()
    
    # Generate levels if they don't exist
    total_levels = LevelDocuments.generate_levels()
    
    # Prepare level data
    levels_data = {}
    for level in range(1, total_levels + 1):
        try:
            level_obj = LevelDocuments.objects.get(level=level)
            
            levels_data[level] = {
                'unlocked': True if level == 1 or progress.is_level_unlocked(level) else False,  # Always unlock level 1
                'completed': str(level) in progress.completed_levels,
                'high_score': progress.high_scores.get(str(level), 0),
                'best_time': progress.best_times.get(str(level), None),
                'document_count': level_obj.documents.count()
            }
        except LevelDocuments.DoesNotExist:
            print(f"Level {level} not found")  # Debug print
            continue
    
    return render(request, 'flip_card/levels.html', {'levels_data': levels_data})

@login_required
def flip_card_game(request):
    """
    Renders the main game page with topics for the selected level
    """
    level = int(request.GET.get('level', 1))
    
    # Check if level is unlocked
    progress = UserProgress.objects.get(user=request.user)
    
    if not progress.is_level_unlocked(level):
        return redirect('flip_card:levels_page')
    
    try:
        # Get topics for this level
        level_obj = LevelDocuments.objects.get(level=level)
        topics_data = [
            {
                'title': topic.title,
                'content': topic.content
            }
            for topic in level_obj.documents.all()
        ]
        
        # Print debug information
        print(f"Found {len(topics_data)} topics for level {level}")
        for topic in topics_data:
            print(f"Topic: {topic['title']}")
        
        context = {
            'documents': json.dumps(topics_data),
            'level': level
        }
        
        return render(request, 'flip_card/index.html', context)
    
    except LevelDocuments.DoesNotExist:
        print(f"No level found for level={level}")
        return redirect('flip_card:levels_page')

@login_required
def complete_level(request):
    """
    API endpoint to mark level completion and award points
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        level = data.get('level')
        score = data.get('score')
        time = data.get('time')
        
        # Get user progress and complete level
        progress = UserProgress.objects.get(user=request.user)
        result = progress.complete_level(level, score, time)
        
        return JsonResponse({
            'success': True,
            'points_earned': result['points_earned'],
            'next_level': result['next_level'],
            'total_platform_points': result['total_platform_points'],
            'flipcard_points': result['flipcard_points']
        })
    return JsonResponse({'success': False})