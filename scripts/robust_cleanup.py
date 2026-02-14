
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection, ServiceManual, Product

def clean_markdown(text):
    if not text:
        return text
    
    # 1. Remove Bold/Italic (***, **, *, __, _)
    text = re.sub(r'(\*{1,3}|_{1,3})', '', text)
    
    # 2. Remove Headings (### Title) at the start of any line
    # Supporting optional spaces before #
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    
    # 3. Remove Blockquotes (> Text) at the start of any line, even with leading spaces
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    
    # 4. Remove inline code (`code`)
    text = re.sub(r'`', '', text)
    
    # 5. Remove horizontal rules (---, ___, ***)
    text = re.sub(r'^[-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # 6. Remove list markers like - or * at start of line (optional, but requested by user for "special chars")
    # Actually, keep bullets if they look like plain text '- '.
    # Let's just focus on the ones the user explicitly mentioned: ** ##
    
    return text.strip()

def run_cleanup():
    print("=" * 60)
    print("THOROUGH MARKDOWN CLEANUP")
    print("=" * 60)
    
    # Clean ManualSection content
    sections = ManualSection.objects.all()
    s_count = 0
    for s in sections:
        old = s.content
        new = clean_markdown(old)
        if old != new:
            print(f"[CLEANED] ManualSection: {s.manual.product.title} - {s.title}")
            s.content = new
            s.save()
            s_count += 1
            
    # Clean ServiceManual description
    manuals = ServiceManual.objects.all()
    m_count = 0
    for m in manuals:
        old = m.description
        new = clean_markdown(old)
        if old != new:
            print(f"[CLEANED] ServiceManual Desc: {m.product.title}")
            m.description = new
            m.save()
            m_count += 1

    # Clean Product lead_text and description
    products = Product.objects.all()
    p_count = 0
    for p in products:
        updated = False
        
        old_lead = p.lead_text or ""
        new_lead = clean_markdown(old_lead)
        if old_lead != new_lead:
            print(f"[CLEANED] Product Lead: {p.title}")
            p.lead_text = new_lead
            updated = True
            
        old_desc = p.description or ""
        new_desc = clean_markdown(old_desc)
        if old_desc != new_desc:
            print(f"[CLEANED] Product Desc: {p.title}")
            p.description = new_desc
            updated = True
            
        if updated:
            p.save()
            p_count += 1

    print("-" * 60)
    print(f"Summary: Cleaned {s_count} sections, {m_count} manuals, {p_count} products.")
    print("-" * 60)

if __name__ == '__main__':
    run_cleanup()
