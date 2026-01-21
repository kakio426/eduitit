from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import GeneratedArticle
import os
from django.conf import settings

# Engine imports
# Note: Ensure these engines are compatible with Django (no streamlit dependencies)
from .engines.ai_service import generate_article_gemini, summarize_article_for_ppt
from .engines.ppt_engine import PPTEngine

class ArticleCreateView(View):
    template_name = 'autoarticle/create.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        topic = request.POST.get('topic')
        uploaded_file = request.FILES.get('file')
        
        # User authentication is optional for now based on user request "just add button", 
        # but model has user field. Let's make it optional.
        user = request.user if request.user.is_authenticated else None

        # 1. AI Generation Logic
        # For this MVP, we are simplifying the logic to match the "topic" input
        if topic:
            # Prepare data for AI engine
            topic_data = {
                'school': '스쿨잇 초등학교', # Default for now, could be dynamic
                'grade': '전학년',
                'event_name': topic, # Using topic as event name
                'location': '학교',
                'date': '2025년',
                'keywords': topic,
                'tone': '친절한'
            }
            
            # API Key management: Use env var usually
            api_key = os.environ.get("GEMINI_API_KEY")
            
            # Generate Article
            title, content, hashtags = generate_article_gemini(api_key, topic_data)
            full_text = f"{title}\n\n{content}\n\n{' '.join(['#'+t for t in hashtags])}"
            
            # Generate PPT
            # Summarize first
            summary_points = summarize_article_for_ppt(content, api_key)
            
            ppt_engine = PPTEngine("웜 & 플레이풀", "스쿨잇 초등학교")
            article_data = {
                'title': title,
                'content': summary_points, # List of strings
                'date': '2025.01.21',
                'location': '학교',
                'images': [] # No images for basic topic generation yet
            }
            
            ppt_buffer = ppt_engine.create_presentation([article_data])
            
            # Save to DB
            article = GeneratedArticle.objects.create(
                user=user,
                topic=topic,
                source_type='topic',
                content_summary='\n'.join(summary_points),
                full_text=full_text
            )
            
            # Save PPT file
            filename = f"newsletter_{article.id}.pptx"
            article.ppt_file.save(filename, ppt_buffer)
            article.save()

            return redirect('autoarticle:detail', pk=article.pk)
        
        return render(request, self.template_name, {'error': '주제를 입력해주세요.'})

class ArticleDetailView(DetailView):
    model = GeneratedArticle
    template_name = 'autoarticle/detail.html'
    context_object_name = 'article'
