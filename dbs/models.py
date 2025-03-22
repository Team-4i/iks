from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from spinwheel.models import Card
import google.generativeai as genai


class ConstitutionalArticle(models.Model):
    PART_CHOICES = [
        (5, 'Part 5'),
        (6, 'Part 6'),
    ]
    
    TYPE_CHOICES = [
        ('JUD', 'Judiciary'),
        ('LEG', 'Legislative'),
        ('EXEC', 'Executive'),
    ]
    
    article_number = models.CharField(max_length=10)
    article_title = models.CharField(max_length=200)
    original_text = models.TextField()
    simplified_explanation = models.TextField()
    part = models.IntegerField(choices=PART_CHOICES, default=5)
    type = models.CharField(max_length=4, choices=TYPE_CHOICES, default='LEG')
    
    def __str__(self):
        return f"Part {self.part} - {self.get_type_display()} - Article {self.article_number}: {self.article_title}"

    class Meta:
        ordering = ['part', 'type', 'article_number']

    def sync_to_card(self):
        """
        Syncs this constitutional article to a corresponding card in the Card model.
        Creates a new card if one doesn't exist.
        """
        try:
            card = Card.objects.get(article_number=self.article_number)
            card.title = self.article_title
            card.content = self.simplified_explanation
            card.save()
            return card, False  # False indicates this was an update
        except Card.DoesNotExist:
            card = Card.objects.create(
                title=self.article_title,
                content=self.simplified_explanation,
                article_number=self.article_number,
                rarity="COMMON",
            )
            return card, True  # True indicates this was a creation

    @classmethod
    def sync_all_to_cards(cls):
        """
        Syncs all constitutional articles to cards.
        Returns a tuple of (created_count, updated_count)
        """
        created = 0
        updated = 0
        
        for article in cls.objects.all():
            card, was_created = article.sync_to_card()
            if was_created:
                created += 1
            else:
                updated += 1
        
        return created, updated

    def create_simplified_version(self):
        """
        Creates or updates a simplified version of this article
        """
        simplified, created = SimplifiedArticle.objects.get_or_create(
            article_number=self.article_number,
            defaults={'original_content': self.original_text}
        )
        if not created:
            simplified.original_content = self.original_text
            simplified.save()
        
        simplified.simplify_content()
        return simplified

# Signal to automatically sync article to card when saved
@receiver(post_save, sender=ConstitutionalArticle)
def auto_sync_article_to_card(sender, instance, created, **kwargs):
    """
    Signal handler to automatically sync article to card whenever an article is saved
    """
    instance.sync_to_card()

@receiver(post_save, sender=ConstitutionalArticle)
def auto_create_simplified_version(sender, instance, created, **kwargs):
    """
    Automatically create/update simplified version when article is saved
    """
    instance.create_simplified_version()


class SimplifiedArticle(models.Model):
    PART_CHOICES = [
        (5, 'Part 5'),
        (6, 'Part 6'),
    ]
    
    TYPE_CHOICES = [
        ('JUD', 'Judiciary'),
        ('LEG', 'Legislative'),
        ('EXEC', 'Executive'),
    ]
    
    article_number = models.CharField(max_length=10)
    article_title = models.CharField(max_length=200, null=True, blank=True)
    original_content = models.TextField()
    simplified_content = models.CharField(max_length=200)
    last_simplified = models.DateTimeField(auto_now=True)
    part = models.IntegerField(choices=PART_CHOICES, null=True, blank=True)
    type = models.CharField(max_length=4, choices=TYPE_CHOICES, null=True, blank=True)
    
    @classmethod
    def sync_all_types_and_parts(cls):
        """
        Updates all SimplifiedArticle records with their corresponding
        ConstitutionalArticle types, parts, and titles
        """
        updated_count = 0
        for simplified in cls.objects.all():
            try:
                const_article = ConstitutionalArticle.objects.get(article_number=simplified.article_number)
                simplified.part = const_article.part
                simplified.type = const_article.type
                simplified.article_title = const_article.article_title
                simplified.save()
                updated_count += 1
            except ConstitutionalArticle.DoesNotExist:
                continue
        return updated_count

    def save(self, *args, **kwargs):
        # Try to fetch part, type and title from ConstitutionalArticle before saving
        try:
            const_article = ConstitutionalArticle.objects.get(article_number=self.article_number)
            self.part = const_article.part
            self.type = const_article.type
            self.article_title = const_article.article_title
        except ConstitutionalArticle.DoesNotExist:
            pass  # If no matching article found, keep existing values
        
        super().save(*args, **kwargs)
    
    def simplify_content(self):
        """
        Uses Gemini AI to create a 1-2 line simplified version of the content
        """
        API_KEYS = [
            'AIzaSyA3CUAY0wSBFA_hOztQh19-QUy2QpA6VDQ',
            'AIzaSyBVe6YICm9LrsERinEJKhuHx0sLySo5Hi8',
            'AIzaSyAMjxpmqGDh2d0mMc-J_9aTEHrB8pqx7VU',
            'AIzaSyCP9W9HoWZhlAANeNZr6Z1bst8kd-AyPC0',
            'AIzaSyAoteUHzBLJMUhKvBHCMnXL7IIAUbddvzU',
            'AIzaSyCXVnMP9e1dwR1jP5Bvi7mSrUBTzPKlRkc',
            'AIzaSyCN5KhlzaXYrjKEsx7w3RBwAcd3NpLO1ao',
            'AIzaSyDMVLSyg9HIKefj92TlhAoDKbnzSiDX244'
        ]
        
        for api_key in API_KEYS:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                prompt = f"""
                Summarize this constitutional article in ONE SHORT sentence (max 150 characters):
                {self.original_content}
                
                Rules:
                - Must be exactly ONE sentence
                - Maximum 150 characters
                - Use simple, clear language
                - Focus on the main point only
                """
                
                response = model.generate_content(prompt)
                self.simplified_content = response.text[:200]
                self.save()
                return True
            except Exception as e:
                print(f"Error with key {api_key}: {e}")
                continue
        return False
    
    def __str__(self):
        if self.article_title:
            return f"Simplified Article {self.article_number}: {self.article_title}"
        return f"Simplified Article {self.article_number}"

def get_article_data(article_number):
    """Helper function to get part and type from SimplifiedArticle"""
    try:
        simplified = SimplifiedArticle.objects.get(article_number=article_number)
        return {
            'part': simplified.part,
            'type': simplified.type
        }
    except SimplifiedArticle.DoesNotExist:
        return None
