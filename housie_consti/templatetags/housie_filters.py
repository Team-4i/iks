from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not dictionary:
        return 0
    # Try both string and integer versions of the key
    str_key = str(key)
    return dictionary.get(str_key, dictionary.get(key, 0)) 