from .models import ActivePDFSelection, ActiveTopicGroups, SubTopic, MainTopic

def active_pdf_processor(request):
    """
    Context processor to make active PDF information available in all templates
    """
    context = {
        'global_active_pdf': None,
        'global_active_pdf_selection': None,
        'global_active_topic_groups': [],
        'global_summary_topics_count': 0,
        'global_topic_groups_with_summaries': 0
    }
    
    try:
        # Get active PDF information
        active_pdf_selection = ActivePDFSelection.objects.filter(is_active=True).first()
        if active_pdf_selection:
            context['global_active_pdf'] = active_pdf_selection.pdf
            context['global_active_pdf_selection'] = active_pdf_selection
            
            # Add active topic groups to context
            active_groups = ActiveTopicGroups.get_active_groups()
            context['global_active_topic_groups'] = active_groups
        
        # Add summary topics statistics
        context['global_summary_topics_count'] = SubTopic.objects.count()
        
        # Count topic groups that have at least one summary topic
        topic_groups_with_summaries = MainTopic.objects.filter(summary_topics__isnull=False).distinct().count()
        context['global_topic_groups_with_summaries'] = topic_groups_with_summaries
        
    except Exception as e:
        print(f"Error in active_pdf_processor: {e}")
    
    return context 