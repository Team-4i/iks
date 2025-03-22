from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from users.models import Chat, User, UserProfile, Conversation
import random
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Generates test data for analytics'

    def get_random_time(self, date, is_weekend):
        """Generate random time based on typical usage patterns"""
        if is_weekend:
            # Weekend pattern: More activity in afternoon/evening
            weights = [
                0, 0, 0, 0, 0, 0, 0,  # 0-6 AM (no activity)
                1, 2, 3,              # 7-9 AM (wake up time)
                5, 8, 10,             # 10-12 PM (late morning)
                12, 15, 15,           # 1-3 PM (peak afternoon)
                12, 10, 8,            # 4-6 PM (early evening)
                6, 4, 3,              # 7-9 PM (evening)
                2, 1                  # 10-11 PM (night)
            ]
            hour = random.choices(range(24), weights=weights)[0]
        else:
            # Weekday pattern: Peaks during work hours
            weights = [
                0, 0, 0, 0, 0,       # 0-4 AM (no activity)
                1, 2, 4,             # 5-7 AM (early morning)
                8, 15, 20,           # 8-10 AM (morning peak)
                18, 15, 12,          # 11 AM-1 PM (lunch time)
                15, 18, 20,          # 2-4 PM (afternoon peak)
                15, 10, 8,           # 5-7 PM (evening)
                5, 3, 2, 1           # 8-11 PM (night)
            ]
            hour = random.choices(range(24), weights=weights)[0]

        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        return date.replace(hour=hour, minute=minute, second=second)

    def handle(self, *args, **kwargs):
        try:
            # Get all existing users with completed profiles
            users = User.objects.filter(userprofile__is_profile_completed=True)
            
            if not users.exists():
                self.stdout.write(self.style.ERROR("No users with completed profiles found. Please create some users first."))
                return
            
            # Clear existing data if --clear flag is provided
            if kwargs.get('clear'):
                Chat.objects.all().delete()
                Conversation.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("Cleared existing chat data"))
            
            # List of sample topics with weighted probabilities
            topics = {
                'Constitutional Law': 15,
                'Criminal Law': 20,
                'Property Law': 18,
                'Family Law': 25,
                'Contract Law': 15,
                'Civil Rights': 7
            }
            
            # Sample messages for each topic with detailed responses
            topic_messages = {
                'Constitutional Law': [
                    {
                        'question': "What are the fundamental rights in the constitution?",
                        'answer': "The fundamental rights in the Indian Constitution include: Right to Equality (Articles 14-18), Right to Freedom (Articles 19-22), Right against Exploitation (Articles 23-24), Right to Freedom of Religion (Articles 25-28), Cultural and Educational Rights (Articles 29-30), and Right to Constitutional Remedies (Article 32)."
                    },
                    {
                        'question': "How does Article 21 protect personal liberty?",
                        'answer': "Article 21 guarantees the right to life and personal liberty. It states that no person shall be deprived of their life or personal liberty except according to procedure established by law. The Supreme Court has expanded its scope to include rights to privacy, dignity, and livelihood."
                    }
                ],
                'Criminal Law': [
                    {
                        'question': "What is the difference between IPC 302 and 304?",
                        'answer': "IPC Section 302 deals with murder (intentional killing) carrying a death penalty or life imprisonment, while Section 304 covers culpable homicide not amounting to murder with lesser punishment, typically up to life imprisonment or 10 years."
                    },
                    {
                        'question': "Explain bail provisions under CrPC.",
                        'answer': "The CrPC classifies offenses as bailable and non-bailable. For bailable offenses, bail is a right. For non-bailable offenses, bail is discretionary and depends on factors like gravity of offense, evidence, and flight risk."
                    }
                ],
                # ... Add similar detailed Q&A pairs for other topics ...
            }
            
            # Generate data for the last 30 days
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
            current_date = start_date
            
            total_chats = 0
            
            # Adjust daily chat volumes based on day of week
            while current_date <= end_date:
                is_weekend = current_date.weekday() >= 5
                
                # More chats on weekdays, fewer on weekends
                if is_weekend:
                    daily_chats = random.randint(15, 25)  # Weekend volume
                else:
                    daily_chats = random.randint(35, 50)  # Weekday volume
                
                # Select active users for the day
                active_users = random.sample(
                    list(users),
                    k=min(len(users), daily_chats // 2)  # Each user might chat multiple times
                )
                
                for _ in range(daily_chats):
                    user = random.choice(active_users)
                    
                    # Get random time following typical patterns
                    chat_time = self.get_random_time(current_date, is_weekend)
                    
                    selected_topic = random.choices(
                        list(topics.keys()),
                        weights=list(topics.values())
                    )[0]
                    
                    # Select random Q&A pair for the topic
                    qa_pair = random.choice(topic_messages.get(selected_topic, topic_messages['Constitutional Law']))
                    
                    # Create Chat entry
                    chat = Chat.objects.create(
                        user=user,
                        message=qa_pair['question'],
                        response=qa_pair['answer'],
                        topic=selected_topic,
                        created_at=chat_time
                    )
                    
                    # Create corresponding Conversation entry
                    Conversation.objects.create(
                        question=qa_pair['question'],
                        answer=qa_pair['answer'],
                        timestamp=chat_time
                    )
                    
                    total_chats += 1
                
                current_date += timedelta(days=1)
                self.stdout.write(
                    self.style.SUCCESS(f"Generated {daily_chats} chats for {current_date.date()}")
                )
            
            self.stdout.write(
                self.style.SUCCESS(f"\nSuccessfully generated {total_chats} test chats over 30 days!")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error generating test data: {str(e)}")
            )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing chat data before generating new data',
        )