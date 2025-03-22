from django import template
from django.urls import reverse

register = template.Library()

@register.inclusion_tag('users/chat_widget.html', takes_context=True)
def chat_widget(context):
    return {
        'request': context.get('request'),
    } 