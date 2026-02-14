
import os
import sys
import django
from django.core.files.base import ContentFile
import requests

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ServiceManual, ManualSection, Product

def link_images():
    print("=" * 60)
    print("TASK 2.3: Linking Images to Manual Sections (Forcing Placeholders)")
    print("=" * 60)

    image_map = {
        "서명": {
            "참석자": "https://placehold.co/800x600/purple/white?text=Training+List+Upload", 
            "QR": "https://placehold.co/800x600/purple/white?text=QR+Code+Sign",
            "보고서": "https://placehold.co/800x600/purple/white?text=PDF+Report+Result"
        },
        "쌤BTI": {
            "검사": "https://placehold.co/800x600/orange/white?text=SsamBTI+Start",
            "결과": "https://placehold.co/800x600/orange/white?text=Animal+Result",
            "공유": "https://placehold.co/800x600/orange/white?text=Share+with+Teachers"
        },
        "알림판": {
            "설정": "https://placehold.co/800x600/blue/white?text=Duty+Setup",
            "모닝": "https://placehold.co/800x600/blue/white?text=Morning+Dashboard",
            "청소": "https://placehold.co/800x600/blue/white?text=Cleaning+Time"
        },
        "간편": { # Collect
            "목록": "https://placehold.co/800x600/gray/white?text=Collection+List",
            "제출": "https://placehold.co/800x600/gray/white?text=Simple+Submit",
            "결과": "https://placehold.co/800x600/gray/white?text=Submit+Status"
        }
    }

    manuals = ServiceManual.objects.all()
    count = 0
    
    for manual in manuals:
        product_title = manual.product.title
        key = next((k for k in image_map.keys() if k in product_title), None)
        
        if key:
            print(f"[PROCESS] processing manual for '{product_title}'...")
            sections = manual.sections.all()
            section_map = image_map[key]
            
            for section in sections:
                # Find matching keyword
                img_url = None
                for keyword, url in section_map.items():
                    if keyword in section.title or keyword in section.content:
                        img_url = url
                        break
                
                if img_url:
                    try:
                        print(f"  [LINK] Saving placeholder for '{section.title}'")
                        response = requests.get(img_url)
                        if response.status_code == 200:
                            file_name = f"manual_{key}_{section.id}.png"
                            
                            # Use ContentFile to handle in-memory bytes properly
                            section.image.save(file_name, ContentFile(response.content), save=True)
                            print(f"  [OK] Saved {file_name}")
                            count += 1
                        else:
                            print(f"  [FAIL] HTTP {response.status_code}")
                    except Exception as e:
                        print(f"  [ERROR] Failed to link image: {e}")
                else:
                    # random placeholder if no keyword match but layout needs image
                    if section.layout_type in ['image_left', 'image_right', 'full_visual']:
                         print(f"  [LINK] Saving default placeholder for '{section.title}'")
                         try:
                            generic_url = f"https://placehold.co/800x600/gray/white?text={section.title.split()[0]}"
                            response = requests.get(generic_url)
                            if response.status_code == 200:
                                section.image.save(f"manual_generic_{section.id}.png", ContentFile(response.content), save=True)
                                count += 1
                         except Exception as e:
                            print(f"  [ERROR] Failed default placeholder: {e}")

    print("-" * 60)
    print(f"✅ Applied {count} Placeholder Images Successfully.")

if __name__ == '__main__':
    link_images()
