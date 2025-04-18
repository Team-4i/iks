from django.shortcuts import render, redirect, get_object_or_404
from dbs.models import ConstitutionalArticle
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from .models import PlayerPlatPoints
from django.utils import timezone
from spinwheel.models import PlayerProfile, PlayerCollection
from django.db.models import Count
import json 
from django.views.decorators.http import require_http_methods
from .models import ArticleBookmark
from gtts import gTTS
import io
from dynamicDB.models import ActiveTopicGroups, Topic, SubTopic, MainTopic


@login_required
def profile(request):
    """
    Player profile and learning journey map.
    Shows checkpoint progress, game stats, and topic groups.
    """
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Get checkpoint progress
    progress = player_points.get_checkpoint_progress()
    
    # Get points from each game
    snake_ladder_points = player_points.snake_ladder_points
    housie_points = player_points.housie_points
    flipcard_points = player_points.flipcard_points
    spinwheel_coins = player_points.spinwheel_coins
    total_points = player_points.total_points
    
    print("Completed Checkpoints:", player_points.completed_checkpoints)
    
    # On profile view, check and update all checkpoints
    # Force unlock check for all checkpoints based on points
    for part in [5, 6]:
        for type_ in ['JUD', 'LEG', 'EXEC']:
            if player_points.can_unlock_checkpoint(part, type_):
                checkpoint_key = f"{part}_{type_}"
                if checkpoint_key not in player_points.completed_checkpoints:
                    player_points.completed_checkpoints[checkpoint_key] = {
                        'completed_at': timezone.now().isoformat(),
                        'points': player_points.total_points
                    }
    player_points.save()
    
    # Get game stats
    game_stats = player_points.update_game_stats()
    
    # Get active topic groups
    active_topic_groups = ActiveTopicGroups.get_active_groups()
    
    # Build a dictionary similar to checkpoints but using topic groups
    topic_group_data = {}
    
    if active_topic_groups.exists():
        # Process active topic groups
        for idx, active_group in enumerate(active_topic_groups):
            topic_group = active_group.topic_group
            part_num = 5 if idx == 0 else 6  # Map first group to Part 5, second to Part 6
            
            # Get all summary topics for this group
            summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
            
            # Initialize this part in the topic_group_data
            if part_num not in topic_group_data:
                topic_group_data[part_num] = {}
            
            # Process each summary topic (map to JUD/LEG/EXEC)
            for i, summary_topic in enumerate(summary_topics[:3]):  # Limit to 3 max
                # Map index to checkpoint type
                if i == 0:
                    type_code = 'JUD'
                elif i == 1:
                    type_code = 'LEG'
                else:
                    type_code = 'EXEC'
                
                # Calculate required points based on position
                if part_num == 5:
                    # First group topics (equivalent to part 5)
                    if i == 0:
                        required_points = 0  # First topic always free (like 5_JUD)
                    elif i == 1:
                        required_points = 300  # Second topic (like 5_LEG)
                    else:
                        required_points = 600  # Third topic (like 5_EXEC)
                else:
                    # Second group topics (equivalent to part 6)
                    if i == 0:
                        required_points = 900  # First topic (like 6_JUD)
                    elif i == 1:
                        required_points = 1200  # Second topic (like 6_LEG)
                    else:
                        required_points = 1500  # Third topic (like 6_EXEC)
                
                # Get checkpoint progress if available, otherwise create default
                checkpoint_progress = {}
                try:
                    checkpoint_progress = progress[part_num][type_code]
                except (KeyError, TypeError):
                    checkpoint_progress = {
                        'required_points': required_points,
                        'completed': player_points.total_points >= required_points,
                        'unlocked': player_points.total_points >= required_points
                    }
                
                # Get main topics for this summary topic
                main_topics = summary_topic.main_topics.all()
                
                # Add to topic_group_data
                topic_group_data[part_num][type_code] = {
                    'articles': main_topics,  # Using main_topics in place of articles
                    'progress': checkpoint_progress,
                    'count': main_topics.count(),
                    'is_current': player_points.total_points >= required_points,
                    'is_part_five': part_num == 5,
                    'summary_topic': summary_topic,
                    'topic_group': topic_group,
                    'is_dynamic': True
                }
                
                # If this type is missing, fill it
                if len(topic_group_data[part_num]) < 3:
                    missing_types = set(['JUD', 'LEG', 'EXEC']) - set(topic_group_data[part_num].keys())
                    for missing_type in missing_types:
                        # Get checkpoint progress if available, otherwise create default
                        checkpoint_progress = {}
                        try:
                            checkpoint_progress = progress[part_num][missing_type]
                        except (KeyError, TypeError):
                            # Determine required points based on type
                            if part_num == 5:
                                if missing_type == 'JUD':
                                    required_pts = 0
                                elif missing_type == 'LEG':
                                    required_pts = 300
                                else:
                                    required_pts = 600
                            else:
                                if missing_type == 'JUD':
                                    required_pts = 900
                                elif missing_type == 'LEG':
                                    required_pts = 1200
                                else:
                                    required_pts = 1500
                                    
                            checkpoint_progress = {
                                'required_points': required_pts,
                                'completed': player_points.total_points >= required_pts,
                                'unlocked': player_points.total_points >= required_pts
                            }
                        
                        # Add placeholder entry
                        topic_group_data[part_num][missing_type] = {
                            'articles': [],
                            'progress': checkpoint_progress,
                            'count': 0,
                            'is_current': False,
                            'is_part_five': part_num == 5,
                            'is_dynamic': False
                        }
    
    # Fallback to default checkpoints if no active topic groups
    if not topic_group_data:
        topic_group_data = {
            5: {
                'JUD': {
                    'articles': ConstitutionalArticle.objects.filter(part=5, type='JUD'),
                    'progress': progress[5]['JUD'],
                    'count': ConstitutionalArticle.objects.filter(part=5, type='JUD').count(),
                    'is_current': player_points.current_part == 5 and player_points.current_type == 'JUD',
                    'is_part_five': True
                },
                'LEG': {
                    'articles': ConstitutionalArticle.objects.filter(part=5, type='LEG'),
                    'progress': progress[5]['LEG'],
                    'count': ConstitutionalArticle.objects.filter(part=5, type='LEG').count(),
                    'is_current': player_points.current_part == 5 and player_points.current_type == 'LEG',
                    'is_part_five': True
                },
                'EXEC': {
                    'articles': ConstitutionalArticle.objects.filter(part=5, type='EXEC'),
                    'progress': progress[5]['EXEC'],
                    'count': ConstitutionalArticle.objects.filter(part=5, type='EXEC').count(),
                    'is_current': player_points.current_part == 5 and player_points.current_type == 'EXEC',
                    'is_part_five': True
                }
            },
            6: {
                'EXEC': {
                    'articles': ConstitutionalArticle.objects.filter(part=6, type='EXEC'),
                    'progress': progress[6]['EXEC'],
                    'count': ConstitutionalArticle.objects.filter(part=6, type='EXEC').count(),
                    'is_current': player_points.current_part == 6 and player_points.current_type == 'EXEC',
                    'is_part_five': False
                },
                'LEG': {
                    'articles': ConstitutionalArticle.objects.filter(part=6, type='LEG'),
                    'progress': progress[6]['LEG'],
                    'count': ConstitutionalArticle.objects.filter(part=6, type='LEG').count(),
                    'is_current': player_points.current_part == 6 and player_points.current_type == 'LEG',
                    'is_part_five': False
                },
                'JUD': {
                    'articles': ConstitutionalArticle.objects.filter(part=6, type='JUD'),
                    'progress': progress[6]['JUD'],
                    'count': ConstitutionalArticle.objects.filter(part=6, type='JUD').count(),
                    'is_current': player_points.current_part == 6 and player_points.current_type == 'JUD',
                    'is_part_five': False
                },
            }
        }
    
    context = {
        'checkpoints': topic_group_data,
        'player_points': player_points,
        'game_points': {
            'snake_ladder': snake_ladder_points,
            'housie': housie_points,
            'spinwheel': spinwheel_coins,
            'flipcard': flipcard_points
        },
        'total_points': total_points,
        'game_stats': game_stats,
        'active_topic_groups': active_topic_groups,
        'using_dynamic_topics': active_topic_groups.exists(),
    }
    return render(request, 'plat/profile.html', context)

@login_required
def checkpoint_detail(request, part, type):
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Verify checkpoint is unlocked
    if not player_points.can_unlock_checkpoint(part, type):
        return HttpResponseForbidden("This checkpoint is locked!")
    
    # Get active topic groups
    active_topic_groups = ActiveTopicGroups.get_active_groups()
    
    # Check if we're using dynamic topics
    if active_topic_groups.exists():
        # Map the part and type to a topic group and main topic
        try:
            # Get the topic group based on part number (5 or 6)
            topic_group_index = part - 5
            if topic_group_index < 0 or topic_group_index >= active_topic_groups.count():
                return HttpResponseForbidden("Invalid topic group")
            
            active_group = active_topic_groups[topic_group_index]
            topic_group = active_group.topic_group
            
            # Check if a summary topic ID was specified in the request
            summary_topic_id = request.GET.get('summary_id')
            
            if summary_topic_id:
                # User clicked on a summary topic, show all main topics from this summary
                try:
                    summary_topic = SubTopic.objects.get(id=summary_topic_id, topic_group=topic_group)
                    
                    # Get all main topics from this summary topic
                    main_topics = summary_topic.main_topics.all().order_by('id')
                    
                    # Prepare all chapters from all these main topics
                    all_chapters_data = []
                    
                    for main_topic in main_topics:
                        chapters = main_topic.chapters.all().order_by('order')
                        
                        # Add a header for each main topic
                        all_chapters_data.append({
                            'number': 0,  # Use 0 to identify as header
                            'title': f"--- {main_topic.title} ---",
                            'explanation': main_topic.summary,
                            'is_header': True
                        })
                        
                        # Add all chapters for this main topic
                        for chapter in chapters:
                            all_chapters_data.append({
                                'number': chapter.order,
                                'title': chapter.title,
                                'explanation': chapter.content,
                                'is_header': False
                            })
                    
                    # Return JSON response with summary topic info
                    return JsonResponse({
                        'part': part,
                        'type': type,
                        'type_display': summary_topic.title,
                        'articles': all_chapters_data,
                        'checkpoint_part': part,
                        'checkpoint_type': type,
                        'is_dynamic': True,
                        'is_summary': True,
                        'topic_group': topic_group.title,
                        'summary_topic': summary_topic.title,
                        'summary_description': summary_topic.description,
                        'main_topics_count': main_topics.count()
                    })
                
                except SubTopic.DoesNotExist:
                    # Fallback to standard approach if summary topic not found
                    pass
            
            # Standard approach - get main topic based on type (JUD/LEG/EXEC)
            type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type, 0)
            
            # First check if there are summary topics for this group
            summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
            
            if summary_topics.exists() and type_index < summary_topics.count():
                # Use summary topic
                summary_topic = summary_topics[type_index]
                
                # Get all main topics from this summary topic
                main_topics = summary_topic.main_topics.all().order_by('id')
                
                # Prepare all chapters from all these main topics
                all_chapters_data = []
                
                for main_topic in main_topics:
                    chapters = main_topic.chapters.all().order_by('order')
                    
                    # Add a header for each main topic
                    all_chapters_data.append({
                        'number': 0,  # Use 0 to identify as header
                        'title': f"--- {main_topic.title} ---",
                        'explanation': main_topic.summary,
                        'is_header': True
                    })
                    
                    # Add all chapters for this main topic
                    for chapter in chapters:
                        all_chapters_data.append({
                            'number': chapter.order,
                            'title': chapter.title,
                            'explanation': chapter.content,
                            'is_header': False
                        })
                
                # Return JSON response with summary topic info
                return JsonResponse({
                    'part': part,
                    'type': type,
                    'type_display': summary_topic.title,
                    'articles': all_chapters_data,
                    'checkpoint_part': part,
                    'checkpoint_type': type,
                    'is_dynamic': True,
                    'is_summary': True,
                    'topic_group': topic_group.title,
                    'summary_topic': summary_topic.title,
                    'summary_description': summary_topic.description,
                    'main_topics_count': main_topics.count()
                })
            
            else:
                # Fall back to using regular main topics
                main_topics = topic_group.topics.all().order_by('id')
                
                if type_index >= main_topics.count():
                    return HttpResponseForbidden("Invalid topic")
                
                main_topic = main_topics[type_index]
                
                # Get chapters for this main topic
                chapters = main_topic.chapters.all().order_by('order')
                
                # Prepare chapters data
                chapters_data = []
                
                for chapter in chapters:
                    chapters_data.append({
                        'number': chapter.order,
                        'title': chapter.title,
                        'explanation': chapter.content,
                        'is_header': False
                    })
                
                # Return JSON response with dynamic topic info
                type_display = main_topic.title
                
                return JsonResponse({
                    'part': part,
                    'type': type,
                    'type_display': type_display,
                    'articles': chapters_data,
                    'checkpoint_part': part,
                    'checkpoint_type': type,
                    'is_dynamic': True,
                    'is_summary': False,
                    'topic_group': topic_group.title,
                    'main_topic': main_topic.title
                })
            
        except Exception as e:
            print(f"Error loading dynamic topic content: {e}")
            # Fall back to standard articles if there's an error
            pass
    
    # Get articles for this checkpoint (legacy approach)
    articles = ConstitutionalArticle.objects.filter(
        part=part,
        type=type
    ).order_by('article_number')
    
    # Prepare articles data
    articles_data = []
    type_names = {
        'JUD': 'Judiciary',
        'LEG': 'Legislative',
        'EXEC': 'Executive'
    }
    
    for article in articles:
        articles_data.append({
            'number': article.article_number,
            'title': article.article_title,
            'explanation': article.simplified_explanation
        })
    
    print(f"[DEBUG] Checkpoint detail requested - Part: {part}, Type: {type}")
    print(f"[DEBUG] Found {len(articles_data)} articles")
    
    # Return JSON response with checkpoint info
    return JsonResponse({
        'part': part,
        'type': type,
        'type_display': type_names.get(type, type),
        'articles': articles_data,
        'checkpoint_part': part,
        'checkpoint_type': type,
        'is_dynamic': False
    })

@login_required
def leaderboard(request):
    # Get all players with their points
    all_players = PlayerPlatPoints.objects.all()
    
    # Overall Leaderboard (sorted by total points, excluding spinwheel)
    overall_leaders = all_players.order_by('-total_points')[:10]
    
    # Game-specific Leaderboards
    snake_ladder_leaders = all_players.order_by('-snake_ladder_points')[:10]
    housie_leaders = all_players.order_by('-housie_points')[:10]
    
    # Spinwheel leaders - Fetch directly from PlayerProfile for coins
    spinwheel_profiles = PlayerProfile.objects.all().order_by('-coins')[:10]
    
    # Create a list to store combined spinwheel data
    spinwheel_leaders = []
    
    for profile in spinwheel_profiles:
        # Get card counts for this player
        card_counts = PlayerCollection.objects.filter(
            player=profile,
            quantity__gt=0
        ).values('card__rarity').annotate(
            count=Count('card')
        )
        
        # Initialize card counts
        common = rare = epic = 0
        
        # Count cards by rarity
        for count_data in card_counts:
            if count_data['card__rarity'] == 'COMMON':
                common = count_data['count']
            elif count_data['card__rarity'] == 'RARE':
                rare = count_data['count']
            elif count_data['card__rarity'] == 'EPIC':
                epic = count_data['count']
        
        # Create a data object for the template
        leader_data = {
            'player': profile.user,
            'spinwheel_coins': profile.coins,
            'common_cards': common,
            'rare_cards': rare,
            'epic_cards': epic,
            'total_cards': common + rare + epic
        }
        spinwheel_leaders.append(leader_data)
    
    flipcard_leaders = all_players.order_by('-flipcard_points')[:10]
    
    context = {
        'overall_leaders': overall_leaders,
        'snake_ladder_leaders': snake_ladder_leaders,
        'housie_leaders': housie_leaders,
        'spinwheel_leaders': spinwheel_leaders,
        'flipcard_leaders': flipcard_leaders,
    }
    
    return render(request, 'plat/leaderboard.html', context)

@login_required
def article_details(request, part, type):
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Verify checkpoint is unlocked
    if not player_points.can_unlock_checkpoint(part, type):
        return HttpResponseForbidden("This checkpoint is locked!")
    
    # First check if we're using dynamic topics
    active_topic_groups = ActiveTopicGroups.get_active_groups()
    is_dynamic = active_topic_groups.exists()
    
    context = {}
    
    if is_dynamic:
        try:
            # Check if a summary topic ID was specified
            summary_topic_id = request.GET.get('summary_id')
            
            # Get the topic group based on part number (5 or 6)
            topic_group_index = part - 5
            if topic_group_index < 0 or topic_group_index >= active_topic_groups.count():
                return HttpResponseForbidden("Invalid topic group")
            
            active_group = active_topic_groups[topic_group_index]
            topic_group = active_group.topic_group
            
            if summary_topic_id:
                # User clicked on a summary topic
                try:
                    summary_topic = SubTopic.objects.get(id=summary_topic_id, topic_group=topic_group)
                    
                    # Get the main topics from this summary topic
                    main_topics_in_summary = summary_topic.main_topics.all().order_by('id')
                    
                    # Get all chapters from all main topics
                    all_chapters = []
                    for main_topic in main_topics_in_summary:
                        # Add the chapters with a reference to their main topic
                        for chapter in main_topic.chapters.all().order_by('order'):
                            chapter.parent_topic = main_topic.title  # Add parent topic info
                            all_chapters.append(chapter)
                    
                    # Prepare context
                    context = {
                        'is_dynamic': True,
                        'is_summary': True,
                        'topic_group': topic_group,
                        'summary_topic': summary_topic,
                        'main_topics': main_topics_in_summary,
                        'chapters': all_chapters,
                        'part': part,
                        'type': type,
                        'type_name': summary_topic.title,
                        'player_points': player_points
                    }
                    
                    return render(request, 'plat/article_details.html', context)
                    
                except SubTopic.DoesNotExist:
                    # Fall back to standard approach if summary topic not found
                    pass
            
            # Check if summary topics exist for this topic group
            summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
            
            # Get the type index based on JUD/LEG/EXEC
            type_index = {'JUD': 0, 'LEG': 1, 'EXEC': 2}.get(type, 0)
            
            if summary_topics.exists() and type_index < summary_topics.count():
                # Use summary topic
                summary_topic = summary_topics[type_index]
                
                # Get the main topics from this summary topic
                main_topics_in_summary = summary_topic.main_topics.all().order_by('id')
                
                # Get all chapters from all main topics
                all_chapters = []
                for main_topic in main_topics_in_summary:
                    # Add the chapters with a reference to their main topic
                    for chapter in main_topic.chapters.all().order_by('order'):
                        chapter.parent_topic = main_topic.title  # Add parent topic info
                        all_chapters.append(chapter)
                
                # Prepare context
                context = {
                    'is_dynamic': True,
                    'is_summary': True,
                    'topic_group': topic_group,
                    'summary_topic': summary_topic,
                    'main_topics': main_topics_in_summary,
                    'chapters': all_chapters,
                    'part': part,
                    'type': type,
                    'type_name': summary_topic.title,
                    'player_points': player_points
                }
                
                return render(request, 'plat/article_details.html', context)
            
            else:
                # Fall back to standard main topic
                # Map the part and type to a topic group and main topic (same as in checkpoint_detail)
                main_topics = topic_group.topics.all().order_by('id')
                
                if type_index >= main_topics.count():
                    return HttpResponseForbidden("Invalid topic")
                
                main_topic = main_topics[type_index]
                
                # Get chapters for this main topic
                chapters = main_topic.chapters.all().order_by('order')
                
                # Prepare context
                context = {
                    'is_dynamic': True,
                    'is_summary': False,
                    'topic_group': topic_group,
                    'main_topic': main_topic,
                    'chapters': chapters,
                    'part': part,
                    'type': type,
                    'type_name': main_topic.title, 
                    'player_points': player_points
                }
                
                return render(request, 'plat/article_details.html', context)
                
        except Exception as e:
            print(f"Error loading dynamic topic content for details page: {e}")
            # Fall back to standard articles if there's an error
            is_dynamic = False
    
    # Traditional article loading (for fallback)
    if not is_dynamic:
        # Get articles for this checkpoint
        articles = ConstitutionalArticle.objects.filter(
            part=part,
            type=type
        ).order_by('article_number')
        
        # Get bookmark for this user if exists
        try:
            bookmark = ArticleBookmark.objects.get(user=request.user)
            has_bookmark = True
        except ArticleBookmark.DoesNotExist:
            bookmark = None
            has_bookmark = False
        
        # Prepare type name
        type_names = {
            'JUD': 'Judiciary',
            'LEG': 'Legislative',
            'EXEC': 'Executive'
        }
        
        # Prepare context
        context = {
            'articles': articles,
            'part': part,
            'type': type,
            'type_name': type_names.get(type, type),
            'bookmark': bookmark,
            'has_bookmark': has_bookmark,
            'player_points': player_points,
            'is_dynamic': False
        }
    
    return render(request, 'plat/article_details.html', context)

@login_required
@require_http_methods(["POST"])
def add_bookmark(request):
    try:
        data = json.loads(request.body)
        bookmark, created = ArticleBookmark.objects.update_or_create(
            user=request.user,
            defaults={
                'part': data['part'],
                'type': data['type'],
                'page_number': data['page_number']
            }
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_bookmark(request):
    try:
        bookmark = ArticleBookmark.objects.get(user=request.user)
        return JsonResponse({
            'success': True,
            'part': bookmark.part,
            'type': bookmark.type,
            'page_number': bookmark.page_number
        })
    except ArticleBookmark.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No bookmark found'})

@login_required
def get_speech(request):
    try:
        text = request.GET.get('text', '')
        if not text:
            return JsonResponse({'error': 'No text provided'}, status=400)

        # Create gTTS object
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Create a bytes buffer
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        
        # Return audio file
        response = HttpResponse(fp.read(), content_type='audio/mpeg')
        response['Content-Disposition'] = 'attachment; filename="speech.mp3"'
        return response
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def topic_checkpoint(request, topic_group_id, summary_id):
    """
    New view to handle dynamic topic-based checkpoints
    Using MainTopic and SubTopic models from dynamicDB
    """
    # Get or create player's platform points
    player_points, created = PlayerPlatPoints.objects.get_or_create(
        player=request.user
    )
    
    # Get the topic group and summary topic
    try:
        topic_group = MainTopic.objects.get(id=topic_group_id)
        summary_topic = SubTopic.objects.get(id=summary_id, topic_group=topic_group)
    except (MainTopic.DoesNotExist, SubTopic.DoesNotExist):
        return HttpResponseForbidden("Invalid topic or summary topic")
    
    # Check if user has enough points to access this topic
    # Each topic requires incremental points similar to part/type checkpoints
    # Calculate required points based on position in active topic groups
    required_points = 0
    try:
        active_groups = ActiveTopicGroups.get_active_groups()
        active_group_ids = [group.topic_group.id for group in active_groups]
        
        if topic_group_id in active_group_ids:
            # Find position in active groups
            group_index = active_group_ids.index(topic_group_id)
            
            # Get all summary topics for this group
            summary_topics = SubTopic.objects.filter(topic_group=topic_group).order_by('order')
            if summary_id in [topic.id for topic in summary_topics]:
                topic_index = [topic.id for topic in summary_topics].index(summary_id)
                
                # Calculate required points based on position (similar to checkpoint requirements)
                if group_index == 0:
                    # First group topics (equivalent to part 5)
                    if topic_index == 0:
                        required_points = 0  # First topic always free (like 5_JUD)
                    elif topic_index == 1:
                        required_points = 300  # Second topic (like 5_LEG)
                    else:
                        required_points = 600  # Third+ topic (like 5_EXEC)
                else:
                    # Second group topics (equivalent to part 6)
                    if topic_index == 0:
                        required_points = 900  # First topic (like 6_JUD)
                    elif topic_index == 1:
                        required_points = 1200  # Second topic (like 6_LEG)
                    else:
                        required_points = 1500  # Third+ topic (like 6_EXEC)
    except Exception as e:
        print(f"Error calculating required points: {e}")
        # Default to requiring some points
        required_points = 300
    
    # Check if user has enough points
    if player_points.total_points < required_points:
        return HttpResponseForbidden(f"This topic requires {required_points} points to unlock!")
    
    # Get all main topics from this summary topic
    main_topics = summary_topic.main_topics.all().order_by('id')
    
    # Prepare all chapters from all these main topics
    all_chapters_data = []
    
    for main_topic in main_topics:
        chapters = main_topic.chapters.all().order_by('order')
        
        # Add a header for each main topic
        all_chapters_data.append({
            'number': 0,  # Use 0 to identify as header
            'title': f"--- {main_topic.title} ---",
            'explanation': main_topic.summary,
            'is_header': True
        })
        
        # Add all chapters for this main topic
        for chapter in chapters:
            all_chapters_data.append({
                'number': chapter.order,
                'title': chapter.title,
                'explanation': chapter.content,
                'is_header': False
            })
    
    # Map topic group and summary topic to equivalent part/type for compatibility
    # This helps existing game systems that rely on part/type
    part = 5  # Default to part 5
    type_code = 'JUD'  # Default to JUD
    
    # Try to determine equivalent part/type based on position
    try:
        active_groups = ActiveTopicGroups.get_active_groups()
        active_group_ids = [group.topic_group.id for group in active_groups]
        
        if topic_group_id in active_group_ids:
            # Find position in active groups (0 = Part 5, 1 = Part 6)
            group_index = active_group_ids.index(topic_group_id)
            part = 5 if group_index == 0 else 6
            
            # Get all summary topics for this group
            summary_topics = list(SubTopic.objects.filter(topic_group=topic_group).order_by('order'))
            if summary_id in [topic.id for topic in summary_topics]:
                topic_index = [topic.id for topic in summary_topics].index(summary_id)
                # Map index to type (0 = JUD, 1 = LEG, 2+ = EXEC)
                if topic_index == 0:
                    type_code = 'JUD'
                elif topic_index == 1:
                    type_code = 'LEG'
                else:
                    type_code = 'EXEC'
    except Exception as e:
        print(f"Error mapping to part/type: {e}")
    
    # Return JSON response with topic checkpoint info
    return JsonResponse({
        'part': part,
        'type': type_code,
        'type_display': summary_topic.title,
        'articles': all_chapters_data,
        'checkpoint_part': part,
        'checkpoint_type': type_code,
        'is_dynamic': True,
        'is_summary': True,
        'topic_group': topic_group.title,
        'summary_topic': summary_topic.title,
        'summary_description': summary_topic.description,
        'main_topics_count': main_topics.count(),
        'topic_group_id': topic_group_id,
        'summary_id': summary_id,
        'required_points': required_points
    })

