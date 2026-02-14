
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ServiceManual, ManualSection, Product

def update_manuals():
    print("=" * 60)
    print("TASK 1.2: Updating Service Manual Content & Cleaning Markdown")
    print("=" * 60)

    # 1. Fix Sign Service Context (From Parents to Teachers/Training)
    try:
        sign_product = Product.objects.get(title__icontains="서명")
        sign_manual = ServiceManual.objects.get(product=sign_product)
        sign_manual.sections.all().delete() # Clear existing sections for clean update
        
        print(f"[UPDATE] Resetting Sign Service (ID: {sign_product.id}) manual sections to Teacher/Training context...")

        # New sections
        ManualSection.objects.create(
            manual=sign_manual,
            title='연수 및 회의 서명부 만들기',
            content='### 1. 연수명 입력 및 참석자 등록\n\n연수 제목과 날짜를 입력하고, **"참석자 명단 업로드"** 버튼을 눌러 교직원 명단을 일괄 등록합니다.\n엑셀 파일(*.xlsx)을 그대로 올리면 이름과 직위를 자동으로 인식합니다.\n\n> **Tip**: 매번 명단을 새로 입력할 필요 없이, "우리 학교 명단 불러오기" 기능을 활용하세요.',
            layout_type='image_right',
            display_order=1,
            badge_text='참석자 등록'
        )
        ManualSection.objects.create(
            manual=sign_manual,
            title='QR코드로 간편 서명',
            content='### 선생님들의 스마트폰으로 바로 서명\n\n생성된 **QR코드**를 연수 장소 입구에 붙이거나 스크린에 띄워주세요.\n참석하신 선생님들은 별도 앱 설치 없이 카메라로 QR코드를 인식하고, 본인 이름을 찾아 서명만 하면 끝납니다.',
            layout_type='full_visual',
            display_order=2,
            badge_text='QR코드 배포'
        )
        ManualSection.objects.create(
            manual=sign_manual,
            title='결과 보고서 자동 생성',
            content='### 실시간 취합 및 PDF 다운로드\n\n- **실시간 현황판**: 누가 참석했고 누가 아직 안 왔는지 한눈에 파악할 수 있습니다.\n- **PDF 변환**: 서명이 모두 완료되면 버튼 하나로 "서명이 포함된 결과 보고서"를 PDF로 내려받아 내부 결재 문서에 바로 첨부하세요.',
            layout_type='card_carousel', # Use card carousel layout for final output showcase
            display_order=3,
            badge_text='자동 보고서'
        )
        print("[OK] Sign Service manual sections updated.")

    except Product.DoesNotExist:
        print("[WARN] Sign Service product not found. Skipping context update.")
    except Exception as e:
        print(f"[ERROR] Failed updating Sign Service: {e}")

    # 2. General Clean-up: Remove Markdown Syntax from ALL Manual Sections
    print("[UPDATE] Cleaning Markdown syntax from all sections...")

    all_sections = ManualSection.objects.all()
    count = 0 
    
    for section in all_sections:
        original_content = section.content
        new_content = original_content
        
        # Remove bold markers (**text**)
        new_content = new_content.replace('**', '')
        
        # Remove headings (### Title)
        # Regex to remove ### at start of line
        new_content = re.sub(r'^#+\s+', '', new_content, flags=re.MULTILINE)
        
        # Remove blockquotes (> Tip)
        new_content = re.sub(r'^>\s+', '', new_content, flags=re.MULTILINE)
        
        if new_content != original_content:
            section.content = new_content
            # section.image = None # Reset images? No, keep existing placeholders if any, we will overwrite later.
            section.save()
            count += 1
            # print(f"  [CLEAN] Updated '{section.title}'")

    print(f"[OK] Cleaned markdown from {count} manual sections.")
    print("-" * 60)
    print("✅ Content Update & Cleanup Complete.")

if __name__ == '__main__':
    update_manuals()
