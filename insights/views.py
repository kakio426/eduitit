from django.shortcuts import render
from django.views.generic import DetailView
from .models import Insight

def insight_list(request):
    insights = Insight.objects.all().order_by('-created_at')
    return render(request, 'insights/insight_list.html', {'insights': insights})

class InsightDetailView(DetailView):
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'
