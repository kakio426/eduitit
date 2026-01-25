import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product, ProductFeature

# PlayAura 제품 찾기
try:
    playaura = Product.objects.get(title="유튜브 탈알고리즘")

    # 설명 업데이트
    playaura.description = "대형 언론사나 유명 유튜버가 아닌, 사람들의 진심 어린 사랑을 받고 있는 숨은 보석 같은 유튜브 채널을 매일매일 발견하세요. 알고리즘에 갇히지 않고 새로운 콘텐츠를 만나는 특별한 경험을 선사합니다."
    playaura.save()

    print(f"[OK] '{playaura.title}' description updated successfully.")

    # 기존 기능 삭제 및 새로 추가
    ProductFeature.objects.filter(product=playaura).delete()

    ProductFeature.objects.create(
        product=playaura,
        icon="fa-solid fa-gem",
        title="숨은 보석 발굴",
        description="대형 채널을 제외하고 진짜 사랑받는 중소형 크리에이터들의 채널을 매일 추천합니다."
    )

    ProductFeature.objects.create(
        product=playaura,
        icon="fa-solid fa-heart",
        title="진심 어린 큐레이션",
        description="조회수가 아닌 진정성으로 선별된 채널들을 통해 새로운 영감을 얻으세요."
    )

    print(f"[OK] '{playaura.title}' features updated successfully.")

except Product.DoesNotExist:
    print("[X] Product 'Youtube De-algorithm' not found.")
except Exception as e:
    print(f"[X] Error occurred: {e}")
