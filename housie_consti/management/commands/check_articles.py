from django.core.management.base import BaseCommand
from housie_consti.models import Article, Case

class Command(BaseCommand):
    help = 'Check the number of articles and cases in the database'

    def handle(self, *args, **options):
        article_count = Article.objects.count()
        case_count = Case.objects.count()
        
        self.stdout.write(f'Number of articles in database: {article_count}')
        self.stdout.write(f'Number of cases in database: {case_count}')
        
        if article_count > 0:
            # Display first few articles as sample
            self.stdout.write('\nSample articles:')
            for article in Article.objects.all()[:5]:
                self.stdout.write(f'- {article.article_number}: {article.title}') 