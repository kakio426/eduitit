
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ServiceManual, ManualSection, Product
from django.db.models import Q

def verify():
    print("=" * 60)
    print("TEST 1.1: Verifying Service Manual Content")
    print("=" * 60)
    
    errors = []

    # 1. Verify Sign Service Context (Should contain '연수' or '선생님', NOT '학부모')
    try:
        sign_product = Product.objects.get(title__icontains="서명")
        sign_manual = ServiceManual.objects.get(product=sign_product)
        sections = sign_manual.sections.all()
        
        print(f"[CHECK] Checking Sign Service (ID: {sign_product.id}) context...")
        
        has_training_context = False
        has_parent_context = False
        
        for section in sections:
            content = section.content
            if "연수" in content or "선생님" in content or "참가자" in content:
                has_training_context = True
            if "학부모" in content:
                has_parent_context = True
                print(f"  [FAIL] Found '학부모' in section '{section.title}'")

        if has_parent_context:
            errors.append("Sign Service manual still contains '학부모' (Parents) context.")
        
        if not has_training_context:
            errors.append("Sign Service manual does NOT contain '연수' (Training) or '선생님' context.")

    except Product.DoesNotExist:
        errors.append("Sign Service product not found.")
    except ServiceManual.DoesNotExist:
        errors.append("Sign Service manual not found.")

    # 2. Verify Markdown Syntax Cleanliness
    print("[CHECK] Checking for Markdown syntax artifacts...")
    
    all_sections = ManualSection.objects.all()
    markdown_artifacts = ["**", "###", "> ", "####"]
    
    for section in all_sections:
        for artifact in markdown_artifacts:
            if artifact in section.content:
                errors.append(f"Markdown artifact '{artifact}' found in '{section.manual.product.title}' - Section '{section.title}'")
                # Print first occurrence for debugging
                idx = section.content.find(artifact)
                snippet = section.content[max(0, idx-10):min(len(section.content), idx+20)]
                print(f"  [FAIL] ...{snippet}...")
                break # Report one artifact per section is enough

    # Summary
    print("-" * 60)
    if errors:
        print(f"❌ Verification FAILED with {len(errors)} errors:")
        for e in errors[:10]: # Limit output
            print(f" - {e}")
        if len(errors) > 10:
            print(f" - ... and {len(errors) - 10} more.")
        sys.exit(1)
    else:
        print("✅ Verification PASSED: Content is clean and context is correct.")
        sys.exit(0)

if __name__ == '__main__':
    verify()
