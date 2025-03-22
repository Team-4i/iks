from django import template

register = template.Library()

@register.filter
def get_combo_status(progress_list, combo):
    """
    Check if a combo is completed in the progress list
    """
    if not progress_list:
        return False
    return any(progress.combo == combo and progress.is_completed for progress in progress_list) 