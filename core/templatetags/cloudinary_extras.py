from django import template
import re

register = template.Library()

@register.filter(name='optimize')
def optimize(url, options="f_auto,q_auto"):
    """
    Transforms a Cloudinary URL to add optimization parameters.
    Usage: {{ product.image.url|optimize:"w_500,c_fill" }}
    """
    if not url or not isinstance(url, str):
        return url
        
    # Check if this is a Cloudinary URL
    if 'res.cloudinary.com' in url:
        # Standard format: https://res.cloudinary.com/<cloud_name>/image/upload/v<version>/<public_id>
        # We want to insert options after 'upload/'
        if '/upload/' in url:
            # Ensure f_auto and q_auto are present for best performance
            default_opts = []
            if 'f_auto' not in options:
                default_opts.append('f_auto')
            if 'q_auto' not in options:
                default_opts.append('q_auto')
            
            if default_opts:
                final_options = f"{','.join(default_opts)},{options}".strip(',')
            else:
                final_options = options

            return url.replace('/upload/', f'/upload/{final_options}/')
            
    return url

@register.filter(name='thumbnail')
def thumbnail(url, size="600"):
    """Shortcut for a common thumbnail size with 16:10 aspect ratio for bento cards"""
    try:
        # Extract numeric part if someone passes "600px"
        clean_size = int(re.search(r'\d+', str(size)).group())
        height = int(clean_size * 0.625)
        return optimize(url, f"w_{clean_size},h_{height},c_fill,g_auto")
    except (ValueError, AttributeError, TypeError):
        # Fallback to basic optimization if size parsing fails
        return optimize(url, "w_600,c_fill,g_auto")
