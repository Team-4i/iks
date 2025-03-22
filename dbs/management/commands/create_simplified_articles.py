from django.core.management.base import BaseCommand
from dbs.models import ConstitutionalArticle, SimplifiedArticle

class Command(BaseCommand):
    help = 'Create simplified versions of remaining constitutional articles'

    def handle(self, *args, **kwargs):
        # Get only articles that don't have simplified versions or have empty simplified content
        processed_article_numbers = SimplifiedArticle.objects.exclude(
            simplified_content=''
        ).values_list('article_number', flat=True)
        
        remaining_articles = ConstitutionalArticle.objects.exclude(
            article_number__in=processed_article_numbers
        )
        
        total_remaining = remaining_articles.count()
        if total_remaining == 0:
            self.stdout.write(self.style.SUCCESS("All articles have been simplified!"))
            return

        self.stdout.write(f"Found {total_remaining} articles remaining to be simplified...")

        success_count = 0
        fail_count = 0

        for article in remaining_articles:
            simplified, created = SimplifiedArticle.objects.get_or_create(
                article_number=article.article_number,
                defaults={
                    'original_content': article.original_text,
                    'simplified_content': ''
                }
            )
            
            if not simplified.simplified_content:
                success = simplified.simplify_content()
                if success:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"[{success_count}/{total_remaining}] Article {article.article_number} simplified successfully"
                    ))
                else:
                    fail_count += 1
                    self.stdout.write(self.style.ERROR(
                        f"Failed to simplify article {article.article_number} - All API keys exhausted"
                    ))
                    # If all API keys are exhausted, break the loop
                    if fail_count >= 3:  # After 3 consecutive failures, assume all keys are exhausted
                        self.stdout.write(self.style.WARNING(
                            "Multiple failures detected. API keys might be exhausted. Stopping process."
                        ))
                        break

        # Print final results
        self.stdout.write("\nFinal Results:")
        self.stdout.write(f"Successfully simplified: {success_count}")
        self.stdout.write(f"Failed to simplify: {fail_count}")
        self.stdout.write(f"Articles remaining: {total_remaining - success_count}")
        
        # Show some examples of newly simplified content
        self.stdout.write("\nSample Results from this run:")
        recent_articles = SimplifiedArticle.objects.filter(
            article_number__in=remaining_articles.values_list('article_number', flat=True)
        ).exclude(simplified_content='').order_by('?')[:5]  # Random 5 examples
        
        for article in recent_articles:
            self.stdout.write(f"\nArticle {article.article_number}:")
            self.stdout.write(f"Simplified: {article.simplified_content}")
