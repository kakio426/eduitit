from products.models import Product

def run():
    Product.objects.all().delete()
    
    Product.objects.create(
        title="HWP to PDF Converter",
        description="Convert your HWP (Hancom Word) files to high-quality PDF instantly. Preserves all formatting and layout.",
        price=15000,
        is_active=True,
        image="products/hwp_thumb.png"
    )
    
    Product.objects.create(
        title="Automated Article Creator",
        description="Generate professional news articles and blog posts using AI with just a few keywords.",
        price=25000,
        is_active=True,
        image="products/article_thumb.png"
    )
    
    Product.objects.create(
        title="PDF to Text Extractor",
        description="Extract text from PDF files including scanned images with OCR support.",
        price=10000,
        is_active=True
    )
    
    print("Dummy data seeded successfully!")

if __name__ == '__main__':
    run()
