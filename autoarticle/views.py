from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, DetailView, ListView
from django.contrib import messages
from .models import GeneratedArticle
import os
import json
import datetime
import io
from django.http import HttpResponse
from django.conf import settings
from .engines.ai_service import generate_article_gemini, summarize_article_for_ppt
from .engines.ppt_engine import PPTEngine
from .engines.pdf_engine import PDFEngine
from .engines.card_engine import CardNewsEngine
from .engines.rag_service import StyleRAGService

class ArticleCreateView(View):
    THEMES = ["웜 & 플레이풀", "쿨 & 모던", "클래식 & 정중한", "파스텔 & 소프트"]
    STEPS = ["정보 입력", "AI 초안 생성", "편집 및 보존"]
    
    _style_rag = None

    @classmethod
    def get_style_rag(cls):
        if cls._style_rag is None:
            try:
                cls._style_rag = StyleRAGService()
            except Exception as e:
                print(f"Failed to initialize StyleRAGService: {e}")
        return cls._style_rag

    def get(self, request):
        step = int(request.GET.get('step', '1'))
        school_name = request.session.get('autoarticle_school', '스쿨잇 초등학교')
        theme = request.session.get('autoarticle_theme', self.THEMES[0])
        
        context = {
            'step': step,
            'school_name': school_name,
            'theme': theme,
            'theme_list': self.THEMES,
            'step_list': self.STEPS,
        }

        if step == 2:
            return render(request, 'autoarticle/wizard/step2_generating.html', context)
        
        if step == 3:
            draft = request.session.get('article_draft')
            if not draft:
                return redirect('autoarticle:create')
            context['draft'] = draft
            return render(request, 'autoarticle/wizard/step3_draft.html', context)
        
        context['today'] = datetime.date.today().strftime('%Y-%m-%d')
        return render(request, 'autoarticle/wizard/step1.html', context)

    def get_api_key(self, request):
        user_key = None
        if request.user.is_authenticated:
            try:
                user_key = request.user.userprofile.gemini_api_key
            except Exception:
                pass
        return user_key or os.environ.get("GEMINI_API_KEY")

    def post(self, request):
        step = request.POST.get('step', '1')
        
        if 'school_name' in request.POST:
            request.session['autoarticle_school'] = request.POST.get('school_name')
        if 'theme' in request.POST:
            request.session['autoarticle_theme'] = request.POST.get('theme')

        if step == '1':
            input_data = {
                'school': request.POST.get('school_name', '스쿨잇 초등학교'),
                'grade': request.POST.get('grade', '전교생'),
                'event_name': request.POST.get('event_name'),
                'location': request.POST.get('location'),
                'date': request.POST.get('date'),
                'tone': request.POST.get('tone'),
                'keywords': request.POST.get('keywords'),
            }
            
            if not input_data['event_name'] or not input_data['keywords']:
                messages.error(request, "행사명과 주요 내용을 입력해주세요.")
                return redirect('autoarticle:create')

            # Handle Image Uploads
            uploaded_images = request.FILES.getlist('images')
            image_paths = []
            if uploaded_images:
                from django.core.files.storage import FileSystemStorage
                import uuid
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'autoarticle/images'))
                for img in uploaded_images[:5]: # Limit to 5 images
                    ext = os.path.splitext(img.name)[1]
                    filename = f"{uuid.uuid4()}{ext}"
                    name = fs.save(filename, img)
                    image_paths.append(f"autoarticle/images/{name}")
            
            # Save input data and images to session
            request.session['article_input'] = input_data
            request.session['article_images'] = image_paths
            return redirect('/autoarticle/?step=2')

        elif step == '2':
            # Step 2: AI Generation
            input_data = request.session.get('article_input')
            if not input_data:
                messages.error(request, "입력 데이터가 없습니다. 다시 시작해주세요.")
                return redirect('autoarticle:create')

            api_key = self.get_api_key(request)
            rag = self.get_style_rag()
            
            try:
                title, content, hashtags = generate_article_gemini(api_key, input_data, style_service=rag)
                draft = {
                    'input_data': input_data,
                    'title': title,
                    'content': content,
                    'hashtags': hashtags,
                    'images': request.session.get('article_images', []),
                    'original_generated_content': content
                }
                request.session['article_draft'] = draft
                # Clean up input data from session
                if 'article_input' in request.session:
                    del request.session['article_input']
                if 'article_images' in request.session:
                    del request.session['article_images']
                return redirect('/autoarticle/?step=3')
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f"AI 생성 중 오류가 발생했습니다: {str(e)}")
                return redirect('autoarticle:create')

        elif step == '3':
            try:
                draft = request.session.get('article_draft')
                if not draft:
                    return redirect('autoarticle:create')

                
                final_title = request.POST.get('title', draft['title'])
                final_content = request.POST.get('content', draft['content'])
                final_tags = request.POST.get('hashtags', ' '.join(draft['hashtags'])).split()
                
                # Learn from style if edited
                try:
                    if draft.get('original_generated_content') and final_content != draft['original_generated_content']:
                        rag = self.get_style_rag()
                        if rag:
                            rag.learn_style(
                                original_text=draft['original_generated_content'],
                                corrected_text=final_content,
                                tags=draft['input_data']['tone']
                            )
                except Exception as e:
                    print(f"RAG Style Learning failed: {e}")

                article = GeneratedArticle.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    school_name=draft['input_data']['school'],
                    grade=draft['input_data']['grade'],
                    event_name=draft['input_data']['event_name'],
                    location=draft['input_data']['location'],
                    event_date=draft['input_data']['date'],
                    tone=draft['input_data']['tone'],
                    keywords=draft['input_data']['keywords'],
                    title=final_title,
                    full_text=final_content,
                    hashtags=[t.strip('#') for t in final_tags],
                    images=draft.get('images', [])
                )
                
                api_key = self.get_api_key(request)
                summary_points = summarize_article_for_ppt(final_content, api_key)
                theme = request.session.get('autoarticle_theme', self.THEMES[0])
                ppt_engine = PPTEngine(theme, article.school_name)
                
                article_data = {
                    'title': final_title,
                    'content': summary_points,
                    'date': article.event_date.strftime('%Y.%m.%d') if hasattr(article.event_date, 'strftime') else str(article.event_date),
                    'location': article.location,
                    'images': []
                }
                from django.core.files.base import ContentFile
                ppt_buffer = ppt_engine.create_presentation([article_data])
                article.ppt_file.save(f"newsletter_{article.id}.pptx", ContentFile(ppt_buffer.getvalue()))
                article.content_summary = '\n'.join(summary_points)

                article.save()
                
                del request.session['article_draft']
                messages.success(request, "기사가 성공적으로 저장되었습니다.")
                return redirect('autoarticle:detail', pk=article.pk)
            except Exception as e:
                messages.error(request, f"저장 중 오류가 발생했습니다: {str(e)}")
                return redirect('autoarticle:create')



        return redirect('autoarticle:create')

class ArticleArchiveView(ListView):
    model = GeneratedArticle
    template_name = 'autoarticle/archive.html'
    context_object_name = 'articles'
    ordering = ['-event_date', '-created_at']

    def post(self, request):
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_articles')
        
        if not selected_ids:
            messages.warning(request, "기사를 선택해주세요.")
            return redirect('autoarticle:archive')

        articles = GeneratedArticle.objects.filter(id__in=selected_ids)
        school_name = request.session.get('autoarticle_school', '스쿨잇 초등학교')
        theme = request.session.get('autoarticle_theme', '웜 & 플레이풀')

        if action == 'generate_pdf':
            pdf = PDFEngine(theme, school_name)
            pdf.draw_cover()
            for art in articles:
                art_data = {
                    'title': art.title,
                    'content': art.full_text,
                    'date': str(art.event_date),
                    'location': art.location,
                    'grade': art.grade,
                    'images': []
                }
                pdf.add_article(art_data, is_booklet=True)
            
            pdf_data = pdf.output(dest='S')
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="newsletter.pdf"'
            return response

        elif action == 'generate_ppt':
            ppt_engine = PPTEngine(theme, school_name)
            ppt_articles = []
            for art in articles:
                ppt_articles.append({
                    'title': art.title,
                    'content': art.content_summary_list,
                    'date': str(art.event_date),
                    'location': art.location,
                    'images': []
                })
            
            ppt_buffer = ppt_engine.create_presentation(ppt_articles)
            response = HttpResponse(ppt_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
            response['Content-Disposition'] = 'attachment; filename="presentation.pptx"'
            return response

        return redirect('autoarticle:archive')

class ArticleDetailView(DetailView):
    model = GeneratedArticle
    template_name = 'autoarticle/detail.html'
    context_object_name = 'article'

class ArticleCardNewsView(View):
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk)
        theme = request.session.get('autoarticle_theme', '웜 & 플레이풀')
        
        engine = CardNewsEngine(theme)
        card = engine.create_card(
            title=article.title,
            date=str(article.event_date),
            location=article.location,
            grade=article.grade,
            hashtags=article.hashtags,
            images=article.images 
        )
        
        buffer = io.BytesIO()
        card.save(buffer, format='PNG')
        
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="cardnews_{article.id}.png"'
        return response
