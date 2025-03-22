from django import template
import textwrap

register = template.Library()

##@register.filter
##def is_short_content(text):
##   """Check if content is too short to need a new page"""
##   return len(text.strip()) < 100

@register.filter(name='split_explanation')
def split_explanation(text):
    """Split text into chunks that will fit on each page"""
    chars_per_page = 800 
    chunks = []
    remaining_text = text.strip()
    
    while remaining_text:
        # If remaining text fits on one page
        if len(remaining_text) <= chars_per_page:
            chunks.append(remaining_text)
            break
        
        # Find best break point
        break_point = chars_per_page
        
        # Try sentence break
        sentence_break = remaining_text[:chars_per_page].rfind('. ') + 1
        if sentence_break > chars_per_page * 0.5:  # At least half page
            break_point = sentence_break
        else:
            # Try paragraph break
            para_break = remaining_text[:chars_per_page].rfind('\n') + 1
            if para_break > chars_per_page * 0.5:
                break_point = para_break
            else:
                # Use word break
                word_break = remaining_text[:chars_per_page].rfind(' ') + 1
                if word_break > 0:
                    break_point = word_break
        
        chunks.append(remaining_text[:break_point].strip())
        remaining_text = remaining_text[break_point:].strip()
    
    return chunks

@register.filter
def slice_toc_items(articles, items_per_page):
    """Split articles into chunks for TOC pages"""
    articles_list = list(articles)
    pages = []
    for i in range(0, len(articles_list), items_per_page):
        pages.append(articles_list[i:i + items_per_page])
    return pages

@register.filter
def roman(number):
    """Convert number to Roman numeral"""
    romans = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')
    ]
    result = ''
    for value, numeral in romans:
        while number >= value:
            result += numeral
            number -= value
    return result 