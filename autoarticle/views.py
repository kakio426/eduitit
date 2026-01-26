from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, DetailView, ListView
from django.contrib import messages
from django.urls import reverse
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
from .engines.word_engine import WordEngine
from .engines.rag_service import StyleRAGService
from .engines.rag_service import StyleRAGService
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from core.utils import ratelimit_key_for_master_only
from .engines.constants import FONT_PATH

class ArticleCreateView(View):
    THEMES = ["웜 & 플레이풀", "꿈꾸는 파랑", "발랄한 노랑", "산뜻한 민트"]
    STEPS = ["정보 입력", "AI 초안 생성", "편집 및 보존"]
    # 문체 학습용 → 중간급 1.5 Flash (안정적)
    FIXED_MODEL_NAME = "gemini-1.5-flash"
    
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
        """
        API 키와 마스터 키 사용 여부를 반환.
        Returns: (api_key, is_master_key)
        """
        user_key = None
        if request.user.is_authenticated:
            try:
                user_key = request.user.userprofile.gemini_api_key
            except Exception:
                pass

        if user_key:
            return user_key, False  # 사용자 키 사용
        return os.environ.get("GEMINI_API_KEY"), True  # 마스터 키 사용

    @method_decorator(ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=False))
    def post(self, request):
        if getattr(request, 'limited', False):
             messages.error(request, "무료 사용 한도에 도달했습니다. 가입하시면 더 많은 기사를 생성하고 파일로 다운로드할 수 있습니다! 😊")
             return redirect('autoarticle:create')
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

            # 이미지 처리
            uploaded_images = request.FILES.getlist('images')
            image_paths = []
            upload_errors = []

            if uploaded_images:
                import uuid
                import logging
                logger = logging.getLogger(__name__)

                ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
                use_cloudinary = getattr(settings, 'USE_CLOUDINARY', False)
                
                # [DEBUG] Cloudinary 설정 상태 강제 출력
                try:
                    debug_cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', 'Not Set')
                    debug_api_key = settings.CLOUDINARY_STORAGE.get('API_KEY', 'Not Set')
                    # API Key는 보안상 일부만 출력
                    if len(debug_api_key) > 5:
                        debug_api_key_masked = debug_api_key[:5] + "***"
                    else:
                        debug_api_key_masked = debug_api_key

                    logger.info(f"🔍 DEBUG: USE_CLOUDINARY={use_cloudinary}")
                    logger.info(f"🔍 DEBUG: CLOUDINARY_STORAGE CloudName={debug_cloud_name}, APIKey={debug_api_key_masked}")
                except Exception as e:
                    logger.error(f"🔍 DEBUG LOGGING FAILED: {e}")

                logger.info(f"Processing {len(uploaded_images)} images. USE_CLOUDINARY={use_cloudinary}")

                for idx, img in enumerate(uploaded_images[:5]):
                    ext = os.path.splitext(img.name)[1].lower()

                    # Validate file
                    if ext not in ALLOWED_IMAGE_EXTENSIONS:
                        upload_errors.append(f"{img.name}: 지원하지 않는 파일 형식")
                        continue
                    if img.size > MAX_IMAGE_SIZE:
                        upload_errors.append(f"{img.name}: 파일 크기 초과 (최대 10MB)")
                        continue

                    try:
                        if use_cloudinary:
                            # Cloudinary upload (REQUIRED for production)
                            try:
                                import cloudinary.uploader
                                logger.info(f"Uploading image {idx+1} to Cloudinary: {img.name}")

                                result = cloudinary.uploader.upload(
                                    img,
                                    folder='autoarticle/images',
                                    public_id=str(uuid.uuid4()),
                                    resource_type='image'
                                )

                                secure_url = result.get('secure_url')
                                if secure_url:
                                    image_paths.append(secure_url)
                                    logger.info(f"SUCCESS: Uploaded to {secure_url}")
                                else:
                                    error_msg = f"{img.name}: Cloudinary URL 없음"
                                    upload_errors.append(error_msg)
                                    logger.error(error_msg)

                            except Exception as cloud_err:
                                error_msg = f"{img.name}: Cloudinary 업로드 실패 - {str(cloud_err)}"
                                upload_errors.append(error_msg)
                                logger.error(error_msg, exc_info=True)
                        else:
                            # Local filesystem (for development only)
                            from django.core.files.storage import FileSystemStorage
                            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'autoarticle/images'))
                            filename = f"{uuid.uuid4()}{ext}"
                            name = fs.save(filename, img)
                            url = f"{settings.MEDIA_URL}autoarticle/images/{name}"
                            image_paths.append(url)
                            logger.info(f"Saved locally: {url}")

                    except Exception as e:
                        error_msg = f"{img.name}: 업로드 중 오류 - {str(e)}"
                        upload_errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)

                # Alert user if there were errors
                if upload_errors:
                    for error in upload_errors:
                        messages.warning(request, error)
                        logger.warning(error)

                logger.info(f"Image upload complete: {len(image_paths)} succeeded, {len(upload_errors)} failed")
            
            # Save input data and images to session
            request.session['article_input'] = input_data
            request.session['article_images'] = image_paths
            print(f"DEBUG: Saved {len(image_paths)} images to session: {image_paths}")
            return redirect(f"{reverse('autoarticle:create')}?step=2")

        elif step == '2':
            # Step 2: AI Generation
            input_data = request.session.get('article_input')
            if not input_data:
                messages.error(request, "입력 데이터가 없습니다. 다시 시작해주세요.")
                return redirect('autoarticle:create')

            api_key, is_master_key = self.get_api_key(request)
            rag = self.get_style_rag()

            try:
                title, content, hashtags = generate_article_gemini(api_key, input_data, style_service=rag, is_master_key=is_master_key)
                images_from_session = request.session.get('article_images', [])
                print(f"DEBUG: Step 2 - Images from session: {images_from_session}")
                draft = {
                    'input_data': input_data,
                    'title': title,
                    'content': content,
                    'hashtags': hashtags,
                    'images': images_from_session,
                    'original_generated_content': content
                }
                print(f"DEBUG: Step 2 - Draft images: {draft['images']}")
                request.session['article_draft'] = draft
                # Clean up input data from session
                if 'article_input' in request.session:
                    del request.session['article_input']
                if 'article_images' in request.session:
                    del request.session['article_images']
                return redirect(f"{reverse('autoarticle:create')}?step=3")
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
                
                api_key, _ = self.get_api_key(request)
                summary_points = summarize_article_for_ppt(final_content, api_key)
                theme = request.session.get('autoarticle_theme', self.THEMES[0])
                ppt_engine = PPTEngine(theme, article.school_name)
                
                article_data = {
                    'title': final_title,
                    'content': summary_points,
                    'date': article.event_date.strftime('%Y.%m.%d') if hasattr(article.event_date, 'strftime') else str(article.event_date),
                    'location': article.location,
                    'images': article.images or []
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
                    'images': art.images or []
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
                    'images': art.images or []
                })

            ppt_buffer = ppt_engine.create_presentation(ppt_articles)
            response = HttpResponse(ppt_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
            response['Content-Disposition'] = 'attachment; filename="presentation.pptx"'
            return response

        elif action == 'generate_word':
            word_engine = WordEngine(theme, school_name)
            word_articles = []
            for art in articles:
                word_articles.append({
                    'title': art.title,
                    'content': art.full_text,
                    'date': str(art.event_date),
                    'location': art.location,
                    'grade': art.grade,
                    'images': art.images or []
                })

            word_buffer = word_engine.generate(word_articles)
            response = HttpResponse(word_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = 'attachment; filename="newsletter.docx"'
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


class ArticleWordView(View):
    """개별 기사 Word 다운로드"""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk)
        theme = request.session.get('autoarticle_theme', '웜 & 플레이풀')

        word_engine = WordEngine(theme, article.school_name)
        article_data = {
            'title': article.title,
            'content': article.full_text,
            'date': str(article.event_date),
            'location': article.location,
            'grade': article.grade,
            'images': article.images or []
        }

        word_buffer = word_engine.generate([article_data])
        response = HttpResponse(word_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="article_{article.id}.docx"'
        return response


class ArticleDeleteView(View):
    """기사 삭제"""
    def post(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk)

        # 권한 체크: 로그인 사용자만 자신의 기사 삭제 가능
        if request.user.is_authenticated and article.user and article.user != request.user:
            messages.error(request, "삭제 권한이 없습니다.")
            return redirect('autoarticle:detail', pk=pk)

        article.delete()
        messages.success(request, "기사가 삭제되었습니다.")
        return redirect('autoarticle:archive')


class ArticleEditView(View):
    """기사 수정"""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk)
        context = {
            'article': article,
            'hashtags_str': ' '.join([f'#{tag}' for tag in article.hashtags]) if article.hashtags else ''
        }
        return render(request, 'autoarticle/edit.html', context)

    def post(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk)

        # 권한 체크
        if request.user.is_authenticated and article.user and article.user != request.user:
            messages.error(request, "수정 권한이 없습니다.")
            return redirect('autoarticle:detail', pk=pk)

        article.title = request.POST.get('title', article.title)
        article.full_text = request.POST.get('content', article.full_text)

        hashtags_str = request.POST.get('hashtags', '')
        if hashtags_str:
            article.hashtags = [t.strip('#').strip() for t in hashtags_str.split() if t.strip()]

        article.save()
        messages.success(request, "기사가 수정되었습니다.")
        return redirect('autoarticle:detail', pk=pk)
