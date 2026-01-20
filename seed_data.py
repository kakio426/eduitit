import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

from products.models import Product

def run():
    from products.models import Product
    from insights.models import Insight
    from django.contrib.auth.models import User

    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
        print("Superuser 'admin' created successfully!")

    # Clear existing data
    Product.objects.all().delete()
    Insight.objects.all().delete()
    
    # Seed Products
    Product.objects.create(
        title="HWP to PDF Converter",
        description="Convert your HWP (Hancom Word) files to high-quality PDF instantly.",
        price=15000,
        is_active=True,
        image="https://placehold.co/600x400/purple/white?text=HWP+to+PDF"
    )
    
    Product.objects.create(
        title="Automated Article Creator",
        description="Generate professional news articles and blog posts using AI.",
        price=25000,
        is_active=True,
        image="https://placehold.co/600x400/blue/white?text=AI+Article"
    )
    
    # Seed Insights
    Insight.objects.create(
        title="AI 시대, 교사의 역할은 어떻게 변할까?",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        content="지식의 전달자에서 영감의 설계자로.",
        kakio_note="이 영상은 AI 도구를 수업에 녹여내는 구체적인 방법을 제시합니다. 꼭 확인해보세요.",
        tags="#FutureEducation",
        is_featured=True
    )
    
    Insight.objects.create(
        title="ChatGPT를 활용한 행정 업무 혁명",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        content="업무 자동화가 가져올 교실의 변화.",
        kakio_note="단순 반복 업무에서 벗어날 때 아이들과의 시간이 늘어납니다.",
        tags="#Productivity",
        is_featured=True
    )
    
    Product.objects.create(
        title="Online Yut Noli",
        description="설치 없이 바로 즐기는 학급 대항전 필수템!",
        price=0,
        is_active=True,
        is_featured=True,
        image="https://placehold.co/600x400/green/white?text=Yut+Noli"
    )
    
    print("Dummy data and Insights seeded successfully!")

if __name__ == '__main__':
    run()
