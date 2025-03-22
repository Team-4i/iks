from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json
import google.generativeai as genai
from .models import Conversation, Chat
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .models import UserProfile
from django.contrib import messages
from django.db.models import Count, Avg, F
from django.db.models.functions import ExtractHour, Length
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models import Count
from opencage.geocoder import OpenCageGeocode
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.template.defaultfilters import floatformat
import csv
import xlsxwriter
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from django.db.models import Sum
from django.utils.timezone import localtime
from plat.models import PlayerPlatPoints


# Create your views here.

@login_required
def home(request):
    try:
        profile = request.user.userprofile
        if not profile.is_profile_completed:
            return redirect('users:complete_profile')
    except UserProfile.DoesNotExist:
        return redirect('users:complete_profile')
    return render(request, 'users/home.html')

def learn(request):
    # Hardcoded timeline events
    events = [
        {
            'year': 1934,
            'title': 'Idea of Constituent Assembly',
            'description': "The concept of a Constituent Assembly was first proposed by M.N. Roy, a pioneer of the communist movement in India. This idea later gained momentum and became a significant step towards India's independence and drafting of its own constitution.",
            'image': 'timeline_images/1934.jpg'
        },
        {
            'year': 1935,
            'title': 'Government of India Act, 1935',
            'description': 'The Government of India Act, 1935, was enacted by the British Parliament. While it did not give India complete self-rule, it laid the administrative foundation and highlighted the need for a robust Constitution.',
            'image': 'timeline_images/1935.jpg'
        },
        {
            'year': 1940,
            'title': 'Demand for Constitution',
            'description': 'The Indian National Congress officially demanded the establishment of a Constituent Assembly. This demand was later recognized by the British government during the August Offer.',
            'image': 'timeline_images/1940.jpg'
        },
        {
            'year': 1946,
            'title': 'Formation of Constituent Assembly',
            'description': "Under the Cabinet Mission Plan, the Constituent Assembly was formed, consisting of 389 members representing provinces and princely states. This marked the beginning of India's journey to draft its Constitution.",
            'image': 'timeline_images/1946.jpg'
        },
        {
            'year': 1946,
            'title': 'First Meeting of Constituent Assembly',
            'description': 'The first session of the Constituent Assembly was held in New Delhi. Dr. Sachchidananda Sinha was elected as the interim President for this historic gathering.',
            'image': 'timeline_images/19463.jpg'
        },
        {
            'year': 1947,
            'title': 'Formation of Drafting Committee',
            'description': 'The Drafting Committee was formed, with Dr. B.R. Ambedkar as its Chairman. This committee was entrusted with the responsibility of drafting the Indian Constitution.',
            'image': 'timeline_images/1947.png'
        },
        {
            'year': 1949,
            'title': 'Adoption of the Constitution',
            'description': 'After extensive deliberations and debates, the Constituent Assembly formally adopted the Constitution of India. This day is celebrated as Constitution Day in India.',
            'image': 'timeline_images/1949.jpg'
        },
        {
            'year': 1950,
            'title': 'Final Signing of the Constitution',
            'description': 'The members of the Constituent Assembly signed the final version of the Constitution. The signed document had a preamble, 395 articles, and 8 schedules.',
            'image': 'timeline_images/19501.jpg'
        },
        {
            'year': 1950,
            'title': 'Constitution Came into Effect',
            'description': "The Constitution of India came into effect, replacing the Government of India Act, 1935. This day is celebrated as Republic Day, marking India's transformation into a sovereign democratic republic.",
            'image': 'timeline_images/19502.jpg'
        },
        {
            'year': 1960,
            'title': 'First Amendment to the Constitution',
            'description': "The first amendment to the Constitution was enacted to address issues related to land reforms, the right to equality, and freedom of speech.",
            'image': 'timeline_images/1960.webp'
        },
        {
            'year': 1976,
            'title': '42nd Amendment',
            'description': "Known as the 'Mini Constitution,' the 42nd Amendment made significant changes, including the addition of the words Socialist,Secular,and Integrity to the Preamble.",
            'image': 'timeline_images/1966.jpg'
        },
        {
            'year': 2002,
            'title': '86th Amendment',
            'description': 'The 86th Amendment introduced the Right to Education as a fundamental right, making education free and compulsory for children aged 6 to 14 years.',
            'image': 'timeline_images/2002.jpg'
        },
        {
            'year': 2024,
            'title': 'Latest Amendments',
            'description': 'The Constitution continues to evolve, reflecting the changing needs and aspirations of the Indian people. As of today, it has undergone 105 amendments.',
            'image': 'timeline_images/20241.jpg'
        },
    ]
    return render(request, 'learn.html', {'events': events})

def logout_view(request):
    logout(request)
    return redirect('/')

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question')
            
            if not question:
                return JsonResponse({'error': 'Question is required'}, status=400)
            
            # Configure Gemini
            genai.configure(api_key="AIzaSyDNQHOszQYJxJRwVJPcKMj3no4wQ6DREO8")
            model = genai.GenerativeModel('gemini-pro')
            
            # First, get the topic classification
            topic_prompt = f"""Classify this Indian legal question into one specific topic:
            Question: {question}
            
            Example topics:
            - Indian Constitutional Law
            - Indian Criminal Law
            - Indian Property Law
            - Indian Family Law
            - Indian Contract Law
            - Fundamental Rights
            - Indian Tax Law
            
            Reply with ONLY the topic, nothing else."""
            
            topic_response = model.generate_content(topic_prompt)
            topic = topic_response.text.strip() if topic_response else "Indian Legal"
            
            # Now get the actual answer with properly formatted links
            answer_prompt = f"""You are LawBot, an Indian legal assistant specializing in Indian law and the Constitution. Answer this question about Indian law:
            {question}

            Important guidelines:
            1. Focus primarily on Indian law, Constitution, and legal precedents
            2. Reference specific Articles, Sections, or Indian court judgments when relevant
            3. Cite Indian legal sources and government websites
            4. Explain in context of Indian legal framework
            
            Format your response using these markdown-style markers:
            - Use **text** for bold
            - Use *text* for italics
            - Use • for bullet points
            - Use ## for headings
            
            At the end of your response, ALWAYS include exactly two sources in this EXACT format:
            
            ## Sources
            • [Indian Constitution Article X](https://legislative.gov.in/constitution-of-india) - Direct link to the relevant constitutional article
            • [Supreme Court Judgment](https://main.sci.gov.in/judgments) - Link to the specific judgment or relevant page
            
            ONLY use these verified source URLs:
            1. Constitution and Laws:
            - https://legislative.gov.in/constitution-of-india
            - https://legislative.gov.in/sites/default/files/coi-4March2016.pdf
            
            2. Supreme Court:
            - https://main.sci.gov.in/judgments
            - https://main.sci.gov.in/constitution
            
            3. Legal Databases:
            - https://indiankanoon.org/
            - https://doj.gov.in/
            - https://lawmin.gov.in/
            
            4. Government Portals:
            - https://india.gov.in/
            - https://indiacode.nic.in/
            
            Make sure to:
            1. Only use URLs from the above list
            2. Double-check that each URL is working
            3. Link to specific pages/sections when possible
            4. Include brief but informative descriptions
            5. Format exactly as shown in the example"""
            
            response = model.generate_content(answer_prompt)
            
            if response and hasattr(response, 'text'):
                formatted_text = response.text
                
                # Save to both models
                Conversation.objects.create(
                    question=question,
                    answer=formatted_text
                )
                
                # Save to Chat model if user is authenticated
                if request.user.is_authenticated:
                    Chat.objects.create(
                        user=request.user,
                        message=question,
                        response=formatted_text,
                        topic=topic
                    )
                
                return JsonResponse({
                    'status': 'success',
                    'answer': formatted_text,
                    'topic': topic
                })

        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'error': 'Internal server error'
            }, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def case_study(request):
    return render(request, 'case_study.html')

def landing_page(request):
    return redirect('snake_ladder:snake_ladder_intro')
    # return render(request, 'index.html')

def login_redirect_view(request):
    if request.user.is_authenticated and not request.session.get('visited_profile', False):
        request.session['visited_profile'] = True
        return redirect('plat:profile')
    return landing_page(request)

def game_library(request):
    return render(request, 'users/game_library.html')

@login_required
def complete_profile(request):
    # Check if profile is already completed
    try:
        profile = request.user.userprofile
        if profile.is_profile_completed:
            messages.info(request, 'Your profile is already completed.')
            return redirect('plat:profile')  # Changed redirect to plat:profile
    except UserProfile.DoesNotExist:
        # Initialize profile with default values
        profile = UserProfile(
            user=request.user,
            age=13,  # Default minimum age
            gender='',  # Empty string for gender
            location='',  # Empty string for location
            is_profile_completed=False
        )
        profile.save()

    if request.method == 'POST':
        try:
            gender = request.POST.get('gender')
            location = request.POST.get('location')
            age_str = request.POST.get('age')
            
            # Validate required fields
            if not all([gender, location, age_str]):
                messages.error(request, 'All fields are required.')
                return render(request, 'users/complete_profile.html', {
                    'user': request.user,
                    'profile': profile
                })
            
            # Convert age to integer and validate
            try:
                age = int(age_str)
                if age < 13 or age > 120:
                    messages.error(request, 'Age must be between 13 and 120.')
                    return render(request, 'users/complete_profile.html', {
                        'user': request.user,
                        'profile': profile
                    })
            except ValueError:
                messages.error(request, 'Please enter a valid age.')
                return render(request, 'users/complete_profile.html', {
                    'user': request.user,
                    'profile': profile
                })
            
            # Update existing profile
            profile.gender = gender
            profile.location = location
            profile.age = age
            profile.is_profile_completed = True
            profile.save()
            
            messages.success(request, 'Profile completed successfully!')
            return redirect('plat:profile')  # Changed redirect to plat:profile
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'users/complete_profile.html', {
                'user': request.user,
                'profile': profile
            })
    
    return render(request, 'users/complete_profile.html', {
        'user': request.user,
        'profile': profile
    })

@login_required
def analytics(request):
    # Add debug logging
    print(f"User {request.user.username} accessing analytics")
    print(f"Is staff: {request.user.is_staff}")
    
    # Check if user is staff or superuser
    if not (request.user.is_staff or request.user.is_superuser):
        messages.warning(request, 'You need staff permissions to view analytics.')
        return redirect('users:home')

    # Get users who have used chat at least once
    active_user_ids = Chat.objects.values('user').distinct()

    # Update time ranges to use localized time
    end_date = localtime(timezone.now())
    start_date = end_date - timedelta(days=30)
    today = localtime(timezone.now()).date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Basic chat metrics
    total_chats = Chat.objects.count()
    unique_users = active_user_ids.count()
    avg_response_length = Chat.objects.aggregate(
        avg_length=Avg(Length('response'))
    )['avg_length']

    # Get time ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Daily chat trends - last 30 days
    daily_chats = Chat.objects.filter(
        created_at__date__gte=month_ago,
        created_at__date__lte=today
    ).annotate(
        date=models.functions.TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    # Add missing dates with zero counts
    date_dict = {item['date']: item['count'] for item in daily_chats}
    all_dates = []
    current = month_ago
    while current <= today:
        all_dates.append({
            'date': current.isoformat(),
            'count': date_dict.get(current, 0)
        })
        current += timedelta(days=1)

    # Weekly chat trends
    weekly_chats = list(Chat.objects.filter(
        created_at__range=(start_date, end_date)
    ).annotate(
        week=models.functions.TruncWeek('created_at')
    ).values('week').annotate(
        count=Count('id')
    ).order_by('week'))

    # Convert datetime objects to strings
    for chat in weekly_chats:
        chat['week'] = chat['week'].isoformat()

    # Peak hours analysis
    hourly_chats = Chat.objects.annotate(
        hour=ExtractHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')

    # Find peak hours (top 3)
    peak_hours = sorted(
        list(hourly_chats),
        key=lambda x: x['count'],
        reverse=True
    )[:3]

    # User demographics - only for users who have chatted
    age_groups = UserProfile.objects.filter(
        user_id__in=active_user_ids
    ).values('age').annotate(
        count=Count('id')
    ).order_by('age')

    gender_distribution = UserProfile.objects.filter(
        user_id__in=active_user_ids
    ).values('gender').annotate(
        count=Count('id')
    )

    location_distribution = UserProfile.objects.filter(
        user_id__in=active_user_ids
    ).values('location').annotate(
        count=Count('id')
    ).order_by('-count')[:10]  # Top 10 locations

    # Recent activity
    recent_chats = Chat.objects.select_related('user').order_by(
        '-created_at'
    )[:10]

    # Top topics for different time periods
    daily_topics = Chat.objects.filter(
        created_at__date=timezone.now().date()
    ).values('topic').annotate(
        count=Count('id')
    ).exclude(
        topic__isnull=True
    ).exclude(
        topic__exact=''
    ).order_by('-count')[:10]

    # Add debug print to check if we're getting data
    print(f"Daily topics found: {list(daily_topics)}")

    weekly_topics = Chat.objects.filter(
        created_at__date__gte=week_ago
    ).values('topic').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    monthly_topics = Chat.objects.filter(
        created_at__date__gte=month_ago
    ).values('topic').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    print("Weekly chats data:", weekly_chats)

    context = {
        'total_chats': total_chats,
        'unique_users': unique_users,
        'avg_response_length': int(avg_response_length or 0),
        'daily_chats': all_dates,
        'weekly_chats': json.dumps(weekly_chats, cls=DjangoJSONEncoder),
        'hourly_chats': list(hourly_chats),
        'peak_hours': peak_hours,
        'age_groups': list(age_groups),
        'gender_distribution': list(gender_distribution),
        'location_distribution': list(location_distribution),
        'recent_chats': recent_chats,
        'daily_topics': daily_topics,
        'weekly_topics': list(weekly_topics),
        'monthly_topics': list(monthly_topics),
    }

    return render(request, 'users/analytics.html', context)

@login_required
def analytics_view(request):
    # Initialize OpenCage geocoder
    geocoder = OpenCageGeocode(settings.OPENCAGE_API_KEY)
    
    # Get user locations and count
    location_data = UserProfile.objects.values('location').annotate(
        user_count=Count('id')
    ).exclude(location='')
    
    # Process locations for map
    map_data = []
    for loc in location_data:
        try:
            # Get coordinates for location
            results = geocoder.geocode(loc['location'])
            if results and len(results):
                lat = results[0]['geometry']['lat']
                lng = results[0]['geometry']['lng']
                map_data.append({
                    'location': loc['location'],
                    'count': loc['user_count'],
                    'lat': lat,
                    'lng': lng
                })
        except Exception as e:
            print(f"Error geocoding {loc['location']}: {str(e)}")
    
    # Get other analytics data
    total_users = UserProfile.objects.count()
    total_chats = Chat.objects.count()
    total_conversations = Conversation.objects.count()
    
    # Gender distribution
    gender_distribution = UserProfile.objects.values('gender').annotate(
        count=Count('id')
    )
    
    # Age distribution
    age_groups = {
        '13-18': (13, 18),
        '19-25': (19, 25),
        '26-35': (26, 35),
        '36+': (36, 200)
    }
    
    age_distribution = {}
    for group, (min_age, max_age) in age_groups.items():
        count = UserProfile.objects.filter(age__gte=min_age, age__lte=max_age).count()
        age_distribution[group] = count
    
    # Convert data to JSON-safe format
    map_data_json = json.dumps(list(map_data))
    gender_data_json = json.dumps(list(gender_distribution), cls=DjangoJSONEncoder)
    age_data_json = json.dumps(age_distribution)
    
    context = {
        'map_data_json': map_data_json,
        'total_users': total_users,
        'total_chats': total_chats,
        'total_conversations': total_conversations,
        'gender_data_json': gender_data_json,
        'age_data_json': age_data_json,
    }
    
    return render(request, 'users/map.html', context)

def is_staff(user):
    return user.is_staff or user.is_superuser

@login_required
def overall_analytics(request):
    # Get user statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count()
    engagement_rate = round((active_users / total_users * 100) if total_users > 0 else 0, 2)

    # Game statistics from actual models
    game_stats = {
        'snake_ladder': {
            'active_players': PlayerPlatPoints.objects.filter(snake_ladder_games__gt=0).count(),
            'total_points': PlayerPlatPoints.objects.aggregate(total=Sum('snake_ladder_points'))['total'] or 0
        },
        'housie': {
            'active_players': PlayerPlatPoints.objects.filter(housie_games__gt=0).count(),
            'total_points': PlayerPlatPoints.objects.aggregate(total=Sum('housie_points'))['total'] or 0
        },
        'flipcard': {
            'active_players': PlayerPlatPoints.objects.filter(flipcard_games__gt=0).count(),
            'total_points': PlayerPlatPoints.objects.aggregate(total=Sum('flipcard_points'))['total'] or 0
        },
        'spinwheel': {
            'card_stats': {
                'common': PlayerPlatPoints.objects.aggregate(total=Sum('common_cards'))['total'] or 0,
                'rare': PlayerPlatPoints.objects.aggregate(total=Sum('rare_cards'))['total'] or 0,
                'epic': PlayerPlatPoints.objects.aggregate(total=Sum('epic_cards'))['total'] or 0
            }
        }
    }

    # Checkpoint progress from PlayerPlatPoints
    checkpoint_stats = {
        'Part 5 JUD': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='5_JUD').count(),
        'Part 5 LEG': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='5_LEG').count(),
        'Part 5 EXEC': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='5_EXEC').count(),
        'Part 6 JUD': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='6_JUD').count(),
        'Part 6 LEG': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='6_LEG').count(),
        'Part 6 EXEC': PlayerPlatPoints.objects.filter(completed_checkpoints__has_key='6_EXEC').count()
    }

    # Location data for map (removed demographics)
    locations = UserProfile.objects.values('location').annotate(
        user_count=Count('id')
    ).order_by('-user_count')

    # Geocode locations
    map_data = []
    geocoder = OpenCageGeocode(settings.OPENCAGE_API_KEY)
    
    for loc in locations[:10]:  # Limit to top 10 locations for performance
        try:
            if loc['location']:
                results = geocoder.geocode(loc['location'])
                if results and len(results):
                    lat = results[0]['geometry']['lat']
                    lng = results[0]['geometry']['lng']
                    map_data.append({
                        'location': loc['location'],
                        'count': loc['user_count'],
                        'lat': lat,
                        'lng': lng
                    })
        except Exception as e:
            print(f"Error geocoding {loc['location']}: {str(e)}")

    # Top performers based on total points
    top_players = PlayerPlatPoints.objects.select_related('player').order_by('-total_points')[:10]
    top_players_data = [
        {
            'username': player.player.username,
            'total_points': player.total_points,
            'games_played': player.games_played,
            'total_wins': player.total_wins
        }
        for player in top_players
    ]

    # Add location-wise scores - Fixed relationship
    location_scores = UserProfile.objects.values('location').annotate(
        total_score=Sum('user__playerplatpoints__total_points'),
        player_count=Count('id')
    ).filter(total_score__isnull=False).order_by('-total_score')

    # Add gender-wise scores - Fixed relationship
    gender_scores = UserProfile.objects.values('gender').annotate(
        total_score=Sum('user__playerplatpoints__total_points'),
        player_count=Count('id'),
        avg_score=Sum('user__playerplatpoints__total_points') / Count('id')
    ).filter(total_score__isnull=False)

    # Add age-wise scores - Fixed relationship
    age_ranges = {
        '13-18': (13, 18),
        '19-25': (19, 25),
        '26-35': (26, 35),
        '36+': (36, 200)
    }

    age_scores = []
    for range_name, (min_age, max_age) in age_ranges.items():
        score_data = UserProfile.objects.filter(
            age__gte=min_age,
            age__lte=max_age
        ).aggregate(
            total_score=Sum('user__playerplatpoints__total_points'),
            player_count=Count('id')
        )
        if score_data['total_score']:
            age_scores.append({
                'range': range_name,
                'total_score': score_data['total_score'],
                'player_count': score_data['player_count'],
                'avg_score': score_data['total_score'] / score_data['player_count']
            })

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'engagement_rate': engagement_rate,
        'game_stats': json.dumps(game_stats),
        'checkpoint_stats': json.dumps(checkpoint_stats),
        'map_data_json': json.dumps(map_data),
        'top_players': top_players_data,
        'location_scores': list(location_scores[:10]),  # Top 10 locations
        'gender_scores': list(gender_scores),
        'age_scores': age_scores
    }

    return render(request, 'users/overall_analytics.html', context)

def get_analytics_data(request):
    """API endpoint for real-time analytics data"""
    data = {
        'heatmap_data': generate_heatmap_data(),
        'relationship_data': generate_relationship_data(),
        'timeline_data': generate_timeline_data(),
    }
    return JsonResponse(data)

@login_required
def export_analytics(request, format='csv'):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.warning(request, 'You need staff permissions to export analytics.')
        return redirect('users:home')

    # Time ranges
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Prepare data
    data = {
        'overview': {
            'total_chats': Chat.objects.count(),
            'unique_users': Chat.objects.values('user').distinct().count(),
            'avg_response_length': Chat.objects.aggregate(avg_length=Avg(Length('response')))['avg_length'],
        },
        'hourly_distribution': list(Chat.objects.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')),
        'daily_chats': list(Chat.objects.filter(
            created_at__date__gte=month_ago
        ).annotate(
            date=models.functions.TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')),
        'weekly_chats': list(Chat.objects.filter(
            created_at__range=(start_date, end_date)
        ).annotate(
            week=models.functions.TruncWeek('created_at')
        ).values('week').annotate(
            count=Count('id')
        ).order_by('week')),
        'topics': {
            'daily': list(Chat.objects.filter(
                created_at__date=today
            ).values('topic').annotate(
                count=Count('id')
            ).order_by('-count')),
            'weekly': list(Chat.objects.filter(
                created_at__date__gte=week_ago
            ).values('topic').annotate(
                count=Count('id')
            ).order_by('-count')),
            'monthly': list(Chat.objects.filter(
                created_at__date__gte=month_ago
            ).values('topic').annotate(
                count=Count('id')
            ).order_by('-count')),
        },
        'user_demographics': {
            'age_groups': list(UserProfile.objects.values('age').annotate(
                count=Count('id')
            ).order_by('age')),
            'gender': list(UserProfile.objects.values('gender').annotate(
                count=Count('id')
            )),
            'locations': list(UserProfile.objects.values('location').annotate(
                count=Count('id')
            ).order_by('-count')),
        },
        'detailed_chats': list(Chat.objects.select_related('user').values(
            'user__username',
            'message',
            'response',
            'topic',
            'created_at'
        ).order_by('-created_at')),
    }

    if format == 'excel':
        # Create Excel workbook
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)

        # Styles
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F4E4BC',
            'border': 1
        })
        
        # Overview Sheet
        overview_sheet = workbook.add_worksheet('Overview')
        overview_data = [
            ['Metric', 'Value'],
            ['Total Chats', data['overview']['total_chats']],
            ['Unique Users', data['overview']['unique_users']],
            ['Average Response Length', round(data['overview']['avg_response_length'], 2)],
        ]
        for row_num, row_data in enumerate(overview_data):
            overview_sheet.write_row(row_num, 0, row_data, header_format if row_num == 0 else None)

        # Hourly Distribution Sheet
        hourly_sheet = workbook.add_worksheet('Hourly Distribution')
        hourly_headers = ['Hour', 'Number of Chats']
        hourly_sheet.write_row(0, 0, hourly_headers, header_format)
        for row_num, hour_data in enumerate(data['hourly_distribution'], 1):
            hourly_sheet.write_row(row_num, 0, [
                f"{hour_data['hour']}:00",
                hour_data['count']
            ])

        # Daily Chats Sheet
        daily_sheet = workbook.add_worksheet('Daily Chats')
        daily_headers = ['Date', 'Number of Chats']
        daily_sheet.write_row(0, 0, daily_headers, header_format)
        for row_num, daily_data in enumerate(data['daily_chats'], 1):
            daily_sheet.write_row(row_num, 0, [
                daily_data['date'].strftime('%Y-%m-%d'),
                daily_data['count']
            ])

        # Topics Sheet
        topics_sheet = workbook.add_worksheet('Topics Analysis')
        topics_sheet.write_row(0, 0, ['Period', 'Topic', 'Count'], header_format)
        row_num = 1
        for period, topics in data['topics'].items():
            for topic_data in topics:
                topics_sheet.write_row(row_num, 0, [
                    period.title(),
                    topic_data['topic'],
                    topic_data['count']
                ])
                row_num += 1

        # Demographics Sheet
        demo_sheet = workbook.add_worksheet('Demographics')
        demo_sheet.write('A1', 'Age Distribution', header_format)
        demo_sheet.write_row(1, 0, ['Age', 'Count'])
        for row_num, age_data in enumerate(data['user_demographics']['age_groups'], 2):
            demo_sheet.write_row(row_num, 0, [age_data['age'], age_data['count']])

        demo_sheet.write('D1', 'Gender Distribution', header_format)
        demo_sheet.write_row(1, 3, ['Gender', 'Count'])
        for row_num, gender_data in enumerate(data['user_demographics']['gender'], 2):
            demo_sheet.write_row(row_num, 3, [gender_data['gender'], gender_data['count']])

        # Detailed Chats Sheet
        detailed_sheet = workbook.add_worksheet('Detailed Chats')
        detailed_headers = ['Username', 'Topic', 'Question', 'Response', 'Timestamp']
        detailed_sheet.write_row(0, 0, detailed_headers, header_format)
        for row_num, chat in enumerate(data['detailed_chats'], 1):
            detailed_sheet.write_row(row_num, 0, [
                chat['user__username'],
                chat['topic'],
                chat['message'],
                chat['response'],
                chat['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            ])

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=analytics_report.xlsx'
        return response

    else:  # CSV format
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=analytics_report.csv'
        writer = csv.writer(response)

        # Write overview
        writer.writerow(['OVERVIEW'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Chats', data['overview']['total_chats']])
        writer.writerow(['Unique Users', data['overview']['unique_users']])
        writer.writerow(['Average Response Length', data['overview']['avg_response_length']])
        writer.writerow([])

        # Write hourly distribution
        writer.writerow(['HOURLY DISTRIBUTION'])
        writer.writerow(['Hour', 'Number of Chats'])
        for hour_data in data['hourly_distribution']:
            writer.writerow([f"{hour_data['hour']}:00", hour_data['count']])
        writer.writerow([])

        # Write topics analysis
        writer.writerow(['TOPICS ANALYSIS'])
        writer.writerow(['Period', 'Topic', 'Count'])
        for period, topics in data['topics'].items():
            for topic_data in topics:
                writer.writerow([period.title(), topic_data['topic'], topic_data['count']])
        writer.writerow([])

        # Write detailed chats
        writer.writerow(['DETAILED CHATS'])
        writer.writerow(['Username', 'Topic', 'Question', 'Response', 'Timestamp'])
        for chat in data['detailed_chats']:
            writer.writerow([
                chat['user__username'],
                chat['topic'],
                chat['message'],
                chat['response'],
                chat['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            ])

        return response

@login_required
def profile_details(request):
    try:
        profile = request.user.userprofile
        context = {
            'profile': profile,
            'username': request.user.username,
        }
        return render(request, 'users/profile_details.html', context)
    except UserProfile.DoesNotExist:
        return redirect('users:complete_profile')

@login_required
def edit_profile(request):
    if request.method == 'POST':
        try:
            profile = request.user.userprofile
            profile.gender = request.POST.get('gender')
            profile.location = request.POST.get('location')
            age = request.POST.get('age')
            
            if age:
                try:
                    age = int(age)
                    if 13 <= age <= 120:
                        profile.age = age
                    else:
                        messages.error(request, 'Age must be between 13 and 120.')
                        return redirect('users:edit_profile')
                except ValueError:
                    messages.error(request, 'Please enter a valid age.')
                    return redirect('users:edit_profile')
            
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('users:profile_details')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return redirect('users:edit_profile')
    
    return render(request, 'users/edit_profile.html')