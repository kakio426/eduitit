from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from products.models import Product
from .forms import APIKeyForm
from .models import UserProfile
from django.contrib import messages

def home(request):
    # Order by display_order first, then by creation date
    products = Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    # Get the featured product with lowest display_order (highest priority)
    featured_product = Product.objects.filter(is_active=True, is_featured=True).order_by('display_order').first()
    # Fallback to the product with lowest display_order if no featured one is set
    if not featured_product:
        featured_product = products.first()
        
    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product
    })

@login_required
def dashboard(request):
    from django.db.models import Q
    # Get IDs of products explicitly owned by the user
    owned_ids = request.user.owned_products.values_list('product_id', flat=True)
    # Filter products that are either owned or free
    available_products = Product.objects.filter(
        Q(id__in=owned_ids) | Q(price=0),
        is_active=True
    ).order_by('display_order', '-created_at').distinct()
    
    return render(request, 'core/dashboard.html', {'products': available_products})

def prompt_lab(request):
    return render(request, 'core/prompt_lab.html')

def tool_guide(request):
    return render(request, 'core/tool_guide.html')

def about(request):
    # Stats could be dynamic later
    stats = {
        'lecture_hours': 120, # Placeholder
        'tools_built': Product.objects.count() + 5, # Approx
        'students': 500, # Placeholder
    }
    return render(request, 'core/about.html', {'stats': stats})

@login_required
def settings_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = APIKeyForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'API Key updated successfully.')
    else:
        form = APIKeyForm(instance=profile)
    
    return render(request, 'core/settings.html', {'form': form})

@login_required
def hwp_convert_view(request):
    import os
    import tempfile
    from django.conf import settings
    from .hwp_utils import convert_hwp_to_pdf_local, HAS_WIN32
    from django.core.files.storage import FileSystemStorage

    if not HAS_WIN32:
        messages.error(request, "HWP 변환 기능은 서버가 Windows 환경일 때만 작동합니다. 로컬 컴퓨터에서 서버를 실행해 주세요.")
        return render(request, 'core/hwp_convert.html', {'disabled': True})

    result_files = []
    if request.method == 'POST':
        uploaded_files = request.FILES.getlist('hwp_files')
        
        if not uploaded_files:
            messages.error(request, "변환할 파일을 선택해주세요.")
            return render(request, 'core/hwp_convert.html')

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in uploaded_files:
                try:
                    # Save uploaded file to temp dir
                    input_path = os.path.join(temp_dir, file.name)
                    with open(input_path, 'wb+') as destination:
                        for chunk in file.chunks():
                            destination.write(chunk)
                    
                    # Define output PDF path
                    base_name = os.path.splitext(file.name)[0]
                    pdf_name = f"{base_name}.pdf"
                    output_path = os.path.join(temp_dir, pdf_name)
                    
                    # Convert
                    convert_hwp_to_pdf_local(input_path, output_path)
                    
                    # Save to media/temp_hwp for download
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'temp_hwp'))
                    with open(output_path, 'rb') as pdf_file:
                        saved_name = fs.save(pdf_name, pdf_file)
                        result_files.append({
                            'name': pdf_name,
                            'url': f"{settings.MEDIA_URL}temp_hwp/{saved_name}"
                        })
                except Exception as e:
                    messages.error(request, f"{file.name} 변환 중 오류 발생: {str(e)}")

        if result_files:
            messages.success(request, f"총 {len(result_files)}개의 파일이 성공적으로 변환되었습니다.")
            
    return render(request, 'core/hwp_convert.html', {'result_files': result_files})
