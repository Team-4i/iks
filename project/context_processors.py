def my_context_processor(request):
    """
    Context processor that adds global variables to all templates.
    This makes common data available across all templates without
    having to pass it explicitly in each view.
    """
    return {
        'site_name': 'IKS Platform',
        'site_version': '1.0',
        'is_debug': True,  # You might want to tie this to your DEBUG setting
        'current_year': __import__('datetime').datetime.now().year,
        'support_email': 'support@iksplatform.com',
        'is_authenticated': request.user.is_authenticated,
        'is_admin': request.user.is_authenticated and request.user.is_staff,
    } 