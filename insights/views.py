from django.shortcuts import render
from .models import Insight

def insight_list(request):
    insights = Insight.objects.all().order_by('-created_at')
    return render(request, 'insights/insight_list.html', {'insights': insights})
