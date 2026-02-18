
import os
import sys
import django

# Add project root to path
sys.path.append('c:\\Users\\kakio\\eduitit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product, ServiceManual, ManualSection

def update_manual():
    try:
        product = Product.objects.get(title__icontains='가뿐하게 서명 톡')
        print(f"Product found: {product.title}")
    except Product.DoesNotExist:
        print("Product '가뿐하게 서명 톡' not found!")
        return

    # Update Manual
    manual, created = ServiceManual.objects.get_or_create(
        product=product,
        defaults={
            'title': '연수 참석 확인, 이제 QR코드로 스마트하게',
            'description': '종이 명렬표를 돌리고, 누가 빠졌는지 일일이 확인하고, 나중에 스캔해서 보관하는 번거로움은 그만! QR코드 하나로 출석 체크와 서명 수합을 동시에 해결하세요.',
            'is_published': True
        }
    )
    
    manual.title = '연수 참석 확인, 이제 QR코드로 스마트하게'
    manual.description = '종이 명렬표를 돌리고, 누가 빠졌는지 일일이 확인하고, 나중에 스캔해서 보관하는 번거로움은 그만! QR코드 하나로 출석 체크와 서명 수합을 동시에 해결하세요.'
    manual.is_published = True
    manual.save()
    print("Manual updated.")

    # Update Sections
    # Clear existing sections
    manual.sections.all().delete()

    sections_data = [
        {
            'title': '3초 만에 서명방 개설',
            'content': "### 연수명만 입력하면 준비 끝!\n\n**연수 제목**과 **날짜/장소**만 입력하고 '만들기'를 누르세요.\n즉시 참석자를 위한 **고유 QR코드**와 **접속 링크**가 생성됩니다.\n이 화면을 연수 장소 빔프로젝터에 띄워두기만 하면 모든 준비가 완료됩니다.",
            'layout_type': 'image_left',
            'display_order': 1,
            'badge_text': 'Step 1'
        },
        {
            'title': '로그인 없는 간편 참여',
            'content': "### 앱 설치? 회원가입? 필요 없어요\n\n참석자들은 카메라로 **QR코드를 찍거나** 공유받은 **링크**를 클릭하기만 하면 됩니다.\n자신의 **이름**을 입력하고 화면에 손가락으로 **서명**하면 제출 완료!\n복잡한 과정이 없어 어르신 선생님들도 쉽게 참여하실 수 있습니다.",
            'layout_type': 'full_visual',
            'display_order': 2,
            'badge_text': 'Step 2'
        },
        {
            'title': '자동 명렬표 완성',
            'content': "### 서명 취합부터 결과 보고서까지\n\n- **실시간 현황판**: 누가 서명을 했는지 실시간으로 화면에 뜹니다. 미참석자를 바로 호명할 수 있죠.\n- **PDF 자동 생성**: 연수가 끝나면 모든 서명이 포함된 **결과 보고서(PDF)**가 자동으로 만들어집니다. 출력해서 결재만 올리세요.",
            'layout_type': 'card_carousel',
            'display_order': 3,
            'badge_text': 'Step 3'
        }
    ]

    for section in sections_data:
        ManualSection.objects.create(
            manual=manual,
            title=section['title'],
            content=section['content'],
            layout_type=section['layout_type'],
            display_order=section['display_order'],
            badge_text=section['badge_text']
        )
    
    print("Sections updated successfully.")

if __name__ == '__main__':
    update_manual()
