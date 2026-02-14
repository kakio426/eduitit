
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection, ServiceManual, Product, ProductFeature

def clean_markdown(text):
    if not text:
        return ""
    
    # Force string type
    text = str(text)
    
    # 1. Remove Bold/Italic (***, **, *, __, _)
    text = re.sub(r'(\*{1,3}|_{1,3})', '', text)
    
    # 2. Remove Headings (### Title) at the start of any line
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    
    # 3. Remove Blockquotes (> Text) at the start of any line
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    
    # 4. Remove inline code (`code`)
    text = re.sub(r'`', '', text)
    
    # 5. Remove horizontal rules
    text = re.sub(r'^[-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()

def force_clean_all():
    print("FORCE CLEAN ALL MODELS starting...")
    
    counts = {"ManualSection": 0, "ServiceManual": 0, "Product": 0, "ProductFeature": 0}
    
    # 1. ManualSection
    for s in ManualSection.objects.all():
        cleaned = clean_markdown(s.content)
        if s.content != cleaned:
            print(f"  Fixing ManualSection: {s.manual.product.title} - {s.title}")
            s.content = cleaned
            s.save()
            counts["ManualSection"] += 1
            
    # 2. ServiceManual
    for m in ServiceManual.objects.all():
        cleaned_desc = clean_markdown(m.description)
        if m.description != cleaned_desc:
            print(f"  Fixing ServiceManual: {m.product.title}")
            m.description = cleaned_desc
            m.save()
            counts["ServiceManual"] += 1
            
    # 3. Product
    for p in Product.objects.all():
        updated = False
        new_desc = clean_markdown(p.description)
        if p.description != new_desc:
            p.description = new_desc
            updated = True
        new_lead = clean_markdown(p.lead_text)
        if p.lead_text != new_lead:
            p.lead_text = new_lead
            updated = True
        if updated:
            print(f"  Fixing Product: {p.title}")
            p.save()
            counts["Product"] += 1
            
    # 4. ProductFeature
    for pf in ProductFeature.objects.all():
        new_desc = clean_markdown(pf.description)
        if pf.description != new_desc:
            print(f"  Fixing ProductFeature: {pf.product.title} - {pf.title}")
            pf.description = new_desc
            pf.save()
            counts["ProductFeature"] += 1
            
    print("-" * 60)
    print(f"Summary: {counts}")
    print("DONE.")

if __name__ == '__main__':
    force_clean_all()
