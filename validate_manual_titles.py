
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

# The list of titles we plan to use in the manual migration
planned_titles = [
    '쌤BTI',
    '우리반 캐릭터 친구 찾기',
    '교사 백과사전',
    '간편 수합',
    '학교 예약 시스템',
    '선생님 사주',
    '가뿐하게 서명 톡',
    '두뇌 풀가동! 교실 체스',
    '학교폭력 사안 처리 비서',
    '반짝반짝 우리반 알림판'
]

print("=== Validating Product Titles for Manual Generation ===")
missing = []
for title in planned_titles:
    exists = Product.objects.filter(title=title).exists()
    status = "✅ Found" if exists else "❌ MISSING"
    print(f"{title}: {status}")
    if not exists:
        missing.append(title)

print("\n=== Summary ===")
if missing:
    print(f"⚠️  Warning: The following products are missing: {missing}")
    print("Please check the exact titles in the database or run ensure commands.")
else:
    print("✅ All planned products exist. Proceed with migration generation.")
