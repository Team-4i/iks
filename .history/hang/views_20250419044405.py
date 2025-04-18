from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import (
    HangmanGame, PlayerStats, MCQQuestion, FillBlankQuestion,
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion
)
from django.db.models import Max, Avg
from django.urls import reverse
import random
import json
from django.core.serializers.json import DjangoJSONEncoder
from dynamicDB.models import MainTopic, SubTopic, Topic, Chapter

def get_random_questions(num_questions=10, allowed_types=None, topic_group_id=None, summary_id=None):
    """Get a random mix of questions from all types, optionally filtered by checkpoint parameters."""
    questions = []
    
    all_question_types = {
        'MCQ': MCQQuestion,
        'FILL': FillBlankQuestion,
        'MATCH': MatchPairsQuestion,
        'TF': TrueFalseQuestion,
        'ODD': OddOneOutQuestion,
        'CAT': CategorizeQuestion,
        'SCRAMBLE': WordUnscrambleQuestion,
    }

    # Determine which types to fetch
    types_to_fetch = allowed_types if allowed_types else all_question_types.keys()
    
    # Convert parameters to integers if they are strings
    if topic_group_id and isinstance(topic_group_id, str):
        try:
            topic_group_id = int(topic_group_id)
        except ValueError:
            topic_group_id = None
    
    if summary_id and isinstance(summary_id, str):
        try:
            summary_id = int(summary_id)
        except ValueError:
            summary_id = None
    
    print(f"Looking for questions with topic_group_id={topic_group_id}, summary_id={summary_id}")
    
    # Checkpoint-specific filtering
    if topic_group_id and summary_id:
        try:
            # Get subtopic - make sure we're using an integer ID
            subtopic = SubTopic.objects.get(id=summary_id)
            print(f"Found subtopic: {subtopic.title}")
            
            # Get all topics related to this subtopic (these are Topic objects, not MainTopic objects)
            topics = subtopic.main_topics.all()
            print(f"Found {topics.count()} topics")
            
            # DEBUG: Print IDs of all topics
            topic_ids = [t.id for t in topics]
            print(f"Topic IDs: {topic_ids}")
            
            # Create a list to collect all questions related to this subtopic
            all_questions = []
            
            # IMPORTANT: The main issue is here - BaseQuestion.main_topic refers to MainTopic,
            # but SubTopic.main_topics refers to Topic models (different models)
            
            # First, let's try to get questions that reference the subtopic directly
            for q_type in types_to_fetch:
                if q_type in all_question_types:
                    model = all_question_types[q_type]
                    
                    # Try to find questions specifically linked to this subtopic
                    subtopic_questions = list(model.objects.filter(
                        is_active=True, 
                        sub_topic_id=subtopic.id
                    ))
                    print(f"Found {len(subtopic_questions)} questions of type {q_type} directly linked to subtopic {subtopic.title}")
                    all_questions.extend(subtopic_questions)
            
            # Next, try to get questions linked to the topics
            for q_type in types_to_fetch:
                if q_type in all_question_types:
                    model = all_question_types[q_type]
                    
                    # Find questions linked to any of the topics
                    for topic in topics:
                        topic_questions = list(model.objects.filter(
                            is_active=True,
                            topic_id=topic.id
                        ))
                        print(f"Found {len(topic_questions)} questions of type {q_type} linked to topic {topic.title}")
                        all_questions.extend(topic_questions)
            
            # Finally, try to get questions linked to the parent topic group
            for q_type in types_to_fetch:
                if q_type in all_question_types:
                    model = all_question_types[q_type]
                    
                    # Find questions linked to the parent topic group (MainTopic)
                    topic_group_questions = list(model.objects.filter(
                        is_active=True,
                        main_topic_id=topic_group_id
                    ))
                    print(f"Found {len(topic_group_questions)} questions of type {q_type} linked to topic group {subtopic.topic_group.title}")
                    all_questions.extend(topic_group_questions)
            
            # If we don't have enough questions, fetch some additional ones
            if len(all_questions) < num_questions:
                print(f"Not enough questions ({len(all_questions)}), fetching additional questions")
                
                # Fetch some additional questions from any category
                for q_type in types_to_fetch:
                    if q_type in all_question_types:
                        model = all_question_types[q_type]
                        # Convert to list before extending
                        additional_questions = list(model.objects.filter(is_active=True))
                        if all_questions:
                            # Create a set of existing IDs for filtering
                            existing_ids = {q.id for q in all_questions}
                            # Filter out questions already in all_questions
                            additional_questions = [q for q in additional_questions if q.id not in existing_ids]
                        print(f"Found {len(additional_questions)} additional questions of type {q_type}")
                        all_questions.extend(additional_questions)
                        if len(all_questions) >= num_questions:
                            break
        
        except SubTopic.DoesNotExist:
            print(f"SubTopic with id={summary_id} not found")
            # Fallback to get all questions if topic not found
            all_questions = []
            for q_type in types_to_fetch:
                if q_type in all_question_types:
                    model = all_question_types[q_type]
                    # Convert QuerySet to list before extending
                    questions_list = list(model.objects.filter(is_active=True))
                    print(f"Fallback: Found {len(questions_list)} questions of type {q_type}")
                    all_questions.extend(questions_list)
    else:
        print("No checkpoint specified, fetching questions of all types")
        # Regular non-checkpoint case: fetch questions of allowed types
        all_questions = []
        for q_type in types_to_fetch:
            if q_type in all_question_types:
                model = all_question_types[q_type]
                # Convert QuerySet to list before extending
                questions_list = list(model.objects.filter(is_active=True))
                print(f"Found {len(questions_list)} questions of type {q_type}")
                all_questions.extend(questions_list)
    
    # If no questions found at all, create some example questions
    if not all_questions:
        print("No questions found in database, creating example questions")
        # Create some default questions for the game to work
        example_questions = [
            {
                'id': 1,
                'type': 'MCQ',
                'question': 'What is the capital of India?',
                'difficulty': 1,
                'options': ['New Delhi', 'Mumbai', 'Kolkata', 'Chennai'],
                'correct_answer': 'New Delhi'
            },
            {
                'id': 2,
                'type': 'TF',
                'question': 'The Indian Constitution is the longest written constitution in the world.',
                'difficulty': 1,
                'correct_answer': 'true'
            },
            {
                'id': 3,
                'type': 'FILL',
                'question': 'The Preamble to the Indian Constitution begins with the words "We, the _____ of India".',
                'difficulty': 1,
                'hint_pattern': 'P _ _ _ _ _',
                'answer': 'People'
            },
            {
                'id': 4,
                'type': 'MCQ',
                'question': 'Which article of the Indian Constitution abolishes untouchability?',
                'difficulty': 2,
                'options': ['Article 14', 'Article 15', 'Article 17', 'Article 21'],
                'correct_answer': 'Article 17'
            },
            {
                'id': 5,
                'type': 'MATCH',
                'question': 'Match the following Constitutional bodies with their functions:',
                'difficulty': 2,
                'pairs': {
                    'Election Commission': 'Conducts elections',
                    'UPSC': 'Recruits civil servants',
                    'Finance Commission': 'Distributes finances',
                    'NITI Aayog': 'Economic planning'
                }
            }
        ]
        return example_questions
    
    print(f"Total questions available: {len(all_questions)}")
    
    # Select random questions from the fetched pool
    selected_questions = random.sample(all_questions, min(num_questions, len(all_questions)))
    print(f"Selected {len(selected_questions)} questions")
    
    # Format questions for frontend
    for question in selected_questions:
        q_dict = {
            'id': question.id,
            'type': question.question_type,
            'question': question.question_text,
            'difficulty': question.difficulty,
        }
        
        # Dynamically add specific fields based on type
        if isinstance(question, MCQQuestion):
            q_dict.update({
                'options': question.options,
                'correct_answer': question.correct_answer
            })
        elif isinstance(question, FillBlankQuestion):
            q_dict.update({
                'hint_pattern': question.hint_pattern,
                'answer': question.answer
            })
        elif isinstance(question, MatchPairsQuestion):
            q_dict.update({
                'pairs': question.pairs
            })
        elif isinstance(question, TrueFalseQuestion):
            q_dict.update({
                'correct_answer': 'true' if question.correct_answer else 'false' 
            })
        elif isinstance(question, OddOneOutQuestion):
            q_dict.update({
                'options': question.options,
                'correct_answer': question.correct_answer,
                'explanation': question.explanation
            })
        elif isinstance(question, CategorizeQuestion):
            q_dict.update({
                'categories': question.categories,
                'items': question.items
            })
        elif isinstance(question, WordUnscrambleQuestion):
            q_dict.update({
                'scrambled_word': question.scrambled_word,
                'correct_word': question.correct_word,
                'hint': question.hint
            })
        
        questions.append(q_dict)
    
    return questions

@login_required
def start_page(request):
    """Renders the start page for the Hangman game."""
    
    # Check if we're being called from a checkpoint - new parameters
    topic_group_id = request.GET.get('topic_group_id')
    summary_id = request.GET.get('summary_id')
    
    # Convert parameters to integers if they are strings
    if topic_group_id:
        try:
            topic_group_id = int(topic_group_id)
        except ValueError:
            topic_group_id = None
    
    if summary_id:
        try:
            summary_id = int(summary_id)
        except ValueError:
            summary_id = None
    
    # Also check for legacy parameters
    part = request.GET.get('part')
    type_code = request.GET.get('type')
    
    context = {}
    
    # First priority: topic_group_id and summary_id (new parameter system)
    if topic_group_id and summary_id:
        context['topic_group_id'] = topic_group_id
        context['summary_id'] = summary_id
        
        # Get information about the checkpoint for display
        try:
            subtopic = SubTopic.objects.get(id=summary_id)
            context['checkpoint_name'] = subtopic.title
            context['from_checkpoint'] = True
        except SubTopic.DoesNotExist:
            pass
    
    # Second priority: part and type (legacy parameter system)
    elif part and type_code:
        # Try to map part/type to topic_group_id/summary_id
        try:
            # Get active topic groups
            from dynamicDB.models import ActiveTopicGroups
            active_groups = ActiveTopicGroups.get_active_groups()
            
            if active_groups.exists():
                # Part 5 = first active group, Part 6 = second active group
                group_index = int(part) - 5
                if 0 <= group_index < active_groups.count():
                    active_group = active_groups[group_index]
                    topic_group = active_group.topic_group
                    topic_group_id = topic_group.id
                    
                    # Map type code to summary topic (JUD=0, LEG=1, EXEC=2)
                    type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type_code, 0)
                    summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
                    
                    if summary_topics.exists() and type_index < summary_topics.count():
                        summary_id = summary_topics[type_index].id
                        summary_topic = summary_topics[type_index]
                        
                        # Now we have mapped the part/type to topic_group_id/summary_id
                        context['topic_group_id'] = topic_group_id
                        context['summary_id'] = summary_id
                        context['checkpoint_name'] = summary_topic.title
                        context['from_checkpoint'] = True
                    else:
                        # Fallback to using part/type for display
                        type_names = {'JUD': 'Judiciary', 'LEG': 'Legislative', 'EXEC': 'Executive'}
                        context['part'] = part
                        context['type'] = type_code
                        context['checkpoint_name'] = f"Part {part} {type_names.get(type_code, '')}"
                        context['from_checkpoint'] = True
        except Exception as e:
            print(f"Error mapping part/type to topic_group/summary: {e}")
            # Fallback to using part/type for display
            type_names = {'JUD': 'Judiciary', 'LEG': 'Legislative', 'EXEC': 'Executive'}
            context['part'] = part
            context['type'] = type_code
            context['checkpoint_name'] = f"Part {part} {type_names.get(type_code, '')}"
            context['from_checkpoint'] = True
    
    return render(request, 'hang/start_page.html', context)

@login_required
def game(request, topic_group_id=None, summary_id=None):
    """Handles the main game view."""
    game_instance = HangmanGame.objects.create(player=request.user)
    stats, created = PlayerStats.objects.get_or_create(player=request.user)
    
    # Check query parameters for checkpoint if not provided in URL
    if not topic_group_id:
        topic_group_id = request.GET.get('topic_group_id')
    if not summary_id:
        summary_id = request.GET.get('summary_id')
    
    print(f"Game view called with topic_group_id={topic_group_id}, summary_id={summary_id}")
    
    # Convert parameters to integers if they are strings
    if topic_group_id and isinstance(topic_group_id, str):
        try:
            topic_group_id = int(topic_group_id)
        except ValueError:
            print(f"Invalid topic_group_id: {topic_group_id}")
            topic_group_id = None
    
    if summary_id and isinstance(summary_id, str):
        try:
            summary_id = int(summary_id)
        except ValueError:
            print(f"Invalid summary_id: {summary_id}")
            summary_id = None
    
    # Also check for part and type parameters (legacy support)
    part = request.GET.get('part')
    type_code = request.GET.get('type')
    
    # Get allowed question types from URL parameter
    allowed_types_str = request.GET.get('types', '')
    allowed_types = [t.strip().upper() for t in allowed_types_str.split(',') if t.strip()]
    if not allowed_types:  # If empty or not provided, allow all
        allowed_types = None
    
    # If we have part and type but not topic_group_id and summary_id,
    # we need to map them to the corresponding topic group and summary
    if part and type_code and not (topic_group_id and summary_id):
        print(f"Mapping legacy parameters part={part}, type={type_code}")
        try:
            # Get active topic groups
            from dynamicDB.models import ActiveTopicGroups
            active_groups = ActiveTopicGroups.get_active_groups()
            
            if active_groups.exists():
                # Part 5 = first active group, Part 6 = second active group
                group_index = int(part) - 5
                if 0 <= group_index < active_groups.count():
                    active_group = active_groups[group_index]
                    topic_group = active_group.topic_group
                    topic_group_id = topic_group.id
                    print(f"Mapped part {part} to topic_group_id {topic_group_id}")
                    
                    # Map type code to summary topic (JUD=0, LEG=1, EXEC=2)
                    type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type_code, 0)
                    summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
                    
                    if summary_topics.exists() and type_index < summary_topics.count():
                        summary_id = summary_topics[type_index].id
                        print(f"Mapped type {type_code} to summary_id {summary_id}")
        except Exception as e:
            print(f"Error mapping part/type to topic_group/summary: {e}")
    
    # If no specific checkpoint parameters were provided, try to load the user's latest checkpoint
    if not (topic_group_id and summary_id) and not (part and type_code):
        print("No checkpoint specified, trying to load user's latest checkpoint")
        try:
            # Import PlayerPlatPoints model
            from plat.models import PlayerPlatPoints
            
            # Get or create the user's platform points record
            user_points, created = PlayerPlatPoints.objects.get_or_create(player=request.user)
            
            # Get the user's current (highest unlocked) checkpoint
            current_part = user_points.current_part
            current_type = user_points.current_type
            
            print(f"User's current checkpoint: Part {current_part} {current_type}")
            
            # Map the part/type to topic_group_id/summary_id
            from dynamicDB.models import ActiveTopicGroups
            active_groups = ActiveTopicGroups.get_active_groups()
            
            if active_groups.exists():
                # Part 5 = first active group, Part 6 = second active group
                group_index = current_part - 5
                if 0 <= group_index < active_groups.count():
                    active_group = active_groups[group_index]
                    topic_group = active_group.topic_group
                    topic_group_id = topic_group.id
                    print(f"Mapped user's current part {current_part} to topic_group_id {topic_group_id}")
                    
                    # Map type code to summary topic (JUD=0, LEG=1, EXEC=2)
                    type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(current_type, 0)
                    summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
                    
                    if summary_topics.exists() and type_index < summary_topics.count():
                        summary_id = summary_topics[type_index].id
                        print(f"Mapped user's current type {current_type} to summary_id {summary_id}")
                        
                        # Set part and type_code for context information
                        part = current_part
                        type_code = current_type
        except Exception as e:
            print(f"Error loading user's latest checkpoint: {e}")
    
    # Get questions based on parameters
    questions = get_random_questions(
        allowed_types=allowed_types,
        topic_group_id=topic_group_id,
        summary_id=summary_id
    )
    
    print(f"Retrieved {len(questions)} questions for the game")
    
    start_page_url = reverse('hang:start_page')
    
    # Prepare context
    context = {
        'game_id': game_instance.id,
        'player_stats': stats,
        'questions_json': json.dumps(questions, cls=DjangoJSONEncoder),
        'start_page_url': start_page_url,
    }
    
    # Add checkpoint information if available
    if topic_group_id and summary_id:
        context['from_checkpoint'] = True
        context['topic_group_id'] = topic_group_id
        context['summary_id'] = summary_id
        
        try:
            subtopic = SubTopic.objects.get(id=summary_id)
            context['checkpoint_name'] = subtopic.title
            print(f"Using checkpoint name: {subtopic.title}")
        except SubTopic.DoesNotExist:
            context['checkpoint_name'] = "Custom Game"
            print("SubTopic not found, using 'Custom Game'")
    elif part and type_code:
        # Legacy part/type parameters
        context['from_checkpoint'] = True
        context['part'] = part
        context['type'] = type_code
        
        type_names = {'JUD': 'Judiciary', 'LEG': 'Legislative', 'EXEC': 'Executive'}
        context['checkpoint_name'] = f"Part {part} {type_names.get(type_code, '')}"
        print(f"Using legacy checkpoint name: {context['checkpoint_name']}")
    
    return render(request, 'hang/game.html', context)

@login_required
def end_game(request):
    """Handles the submission of game results."""
    if request.method == 'POST':
        try:
            game_id = request.POST.get('game_id')
            survival_time = int(request.POST.get('survival_time', 0))
            parts_revealed = int(request.POST.get('parts_revealed', 0))
            correct_answers = int(request.POST.get('correct_answers', 0))
            wrong_answers = int(request.POST.get('wrong_answers', 0))
            points = int(request.POST.get('points', 0))
            
            # Get game instance and update its values
            game_instance = HangmanGame.objects.get(id=game_id, player=request.user, is_active=True)
            game_instance.survival_time = survival_time
            game_instance.parts_revealed = parts_revealed
            game_instance.correct_answers = correct_answers
            game_instance.wrong_answers = wrong_answers
            game_instance.points = points
            game_instance.end_game()
            
            # Update player stats
            stats, created = PlayerStats.objects.get_or_create(player=request.user)
            stats.games_played += 1
            stats.total_time += survival_time
            stats.best_time = max(stats.best_time, survival_time)
            stats.total_correct_answers += correct_answers
            stats.total_wrong_answers += wrong_answers
            stats.total_points += points
            stats.best_points = max(stats.best_points, points)
            stats.save()
            
            return JsonResponse({'status': 'success'})
        except (HangmanGame.DoesNotExist, ValueError, TypeError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def leaderboard(request):
    """Displays the game leaderboard."""
    top_players = PlayerStats.objects.filter(games_played__gt=0).order_by('-best_time')[:10]
    
    player_best_game = HangmanGame.objects.filter(player=request.user, is_active=False).order_by('-survival_time').first()
    
    context = {
        'top_players': top_players,
        'player_best_game': player_best_game
    }
    return render(request, 'hang/leaderboard.html', context)
