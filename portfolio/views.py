from django.views.generic import ListView
from django.db.models import Prefetch
from .models import Achievement, LectureProgram, Inquiry

class PortfolioListView(ListView):
    template_name = 'portfolio/portfolio_list.html'
    context_object_name = 'achievements'
    
    def get_queryset(self):
        return Achievement.objects.all().order_by('-is_featured', '-date_awarded')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Separate achievements into featured and others if needed, using template logic is easier though.
        # Add programs
        context['programs'] = LectureProgram.objects.filter(is_active=True)
        return context

from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
from .forms import InquiryForm
from .services import send_kakao_notification

class InquiryCreateView(CreateView):
    model = Inquiry
    form_class = InquiryForm
    template_name = 'portfolio/inquiry_form.html'
    success_url = reverse_lazy('portfolio:inquiry_success')

    def form_valid(self, form):
        # 폼 저장을 먼저 수행하여 Inquiry 객체를 생성합니다.
        response = super().form_valid(form)
        # 생성된 객체를 사용하여 카카오톡 알림을 발송합니다.
        try:
            send_kakao_notification(self.object)
        except Exception as e:
            # 알림 발송 실패가 문의 접수 자체에 영향을 주지 않도록 예외 처리만 수행합니다.
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Kakao Notification Failed: {e}")
        return response

class InquirySuccessView(TemplateView):
    template_name = 'portfolio/inquiry_success.html'
