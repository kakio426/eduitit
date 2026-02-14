from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, DetailView, ListView
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import GeneratedArticle
import os
import json
import datetime
import io
import re
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
import logging

logger = logging.getLogger(__name__)


def _extract_cloudinary_public_id(url: str):
    if not url or 'cloudinary.com' not in url:
        return None
    match = re.search(r"/upload/(?:v\d+/)?(.+)$", url)
    if not match:
        return None
    path = match.group(1).split("?")[0]
    if "." in path:
        path = path.rsplit(".", 1)[0]
    return path


def _delete_article_assets(article):
    images = article.images or []

    for img_path in images:
        if not isinstance(img_path, str):
            continue
        try:
            if 'cloudinary.com' in img_path:
                public_id = _extract_cloudinary_public_id(img_path)
                if public_id:
                    import cloudinary.uploader
                    cloudinary.uploader.destroy(public_id, resource_type='image', invalidate=True)
                continue

            if img_path.startswith(settings.MEDIA_URL):
                relative = img_path[len(settings.MEDIA_URL):]
                local_path = os.path.join(settings.MEDIA_ROOT, relative)
                if os.path.exists(local_path):
                    os.remove(local_path)
        except Exception as e:
            logger.warning(f"Failed to delete image asset: {img_path} ({e})")

    try:
        if article.ppt_file:
            article.ppt_file.delete(save=False)
    except Exception as e:
        logger.warning(f"Failed to delete ppt file for article {article.id}: {e}")

    try:
        if article.pdf_file:
            article.pdf_file.delete(save=False)
    except Exception as e:
        logger.warning(f"Failed to delete pdf file for article {article.id}: {e}")

@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleCreateView(View):
    THEMES = ["??& ?뚮젅?댄?", "轅덇씀???뚮옉", "諛쒕엫???몃옉", "?곕쑜??誘쇳듃"]
    STEPS = ["?뺣낫 ?낅젰", "AI 珥덉븞 ?앹꽦", "?몄쭛 諛?蹂댁〈"]
    # 臾몄껜 ?숈뒿????2026???쒖? gemini-2.5-flash-lite
    FIXED_MODEL_NAME = "gemini-2.5-flash-lite"
    
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
        school_name = request.session.get('autoarticle_school', '?ㅼ엥??珥덈벑?숆탳')
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
        API ?ㅼ? 留덉뒪?????ъ슜 ?щ?瑜?諛섑솚.
        Returns: (api_key, is_master_key)
        """
        user_key = None
        if request.user.is_authenticated:
            try:
                user_key = request.user.userprofile.gemini_api_key
            except Exception:
                pass

        if user_key:
            return user_key, False  # ?ъ슜?????ъ슜
        return os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"), True  # 留덉뒪?????ъ슜

    def _is_master_deepseek_daily_limit_exceeded(self, request):
        today = datetime.date.today()
        count = GeneratedArticle.objects.filter(
            user=request.user,
            created_at__date=today,
        ).count()
        return count >= 5

    @method_decorator(ratelimit(key=ratelimit_key_for_master_only, rate='10/h', method='POST', block=False))
    def post(self, request):
        if getattr(request, 'limited', False):
             messages.error(request, "臾대즺 ?ъ슜 ?쒕룄???꾨떖?덉뒿?덈떎. 媛?낇븯?쒕㈃ ??留롮? 湲곗궗瑜??앹꽦?섍퀬 ?뚯씪濡??ㅼ슫濡쒕뱶?????덉뒿?덈떎! ?삃")
             return redirect('autoarticle:create')
        step = request.POST.get('step', '1')
        
        if 'school_name' in request.POST:
            request.session['autoarticle_school'] = request.POST.get('school_name')
        if 'theme' in request.POST:
            request.session['autoarticle_theme'] = request.POST.get('theme')

        # [FIX] ?붿옄???뚮쭏???숆탳紐낅쭔 蹂寃쏀븳 寃쎌슦(?ъ씠?쒕컮 ???쒖텧), ?ㅼ쓬 ?④퀎濡?吏꾪뻾?섏? ?딄퀬 ?꾩옱 ?섏씠吏 ?좎?.
        # HTMX ?붿껌??寃쎌슦 204 No Content瑜?諛섑솚?섏뿬 ?섏씠吏 ?덈줈怨좎묠 ?놁씠 ?몄뀡留??낅뜲?댄듃??
        if ('school_name' in request.POST or 'theme' in request.POST) and \
           'event_name' not in request.POST and 'title' not in request.POST:
            if request.headers.get('HX-Request') == 'true':
                return HttpResponse(status=204)
            return redirect(f"{reverse('autoarticle:create')}?step={step}")

        if step == '1':
            input_data = {
                'school': request.POST.get('school_name', '?ㅼ엥??珥덈벑?숆탳'),
                'grade': request.POST.get('grade', ''),
                'event_name': request.POST.get('event_name'),
                'location': request.POST.get('location'),
                'date': request.POST.get('date'),
                'tone': request.POST.get('tone'),
                'keywords': request.POST.get('keywords'),
            }
            
            if not input_data['event_name'] or not input_data['keywords']:
                messages.error(request, "?됱궗紐낃낵 二쇱슂 ?댁슜???낅젰?댁＜?몄슂.")
                return redirect('autoarticle:create')

            # ?대?吏 泥섎━
            uploaded_images = request.FILES.getlist('images')
            client_image_urls = request.POST.getlist('image_urls[]') or request.POST.getlist('image_urls')
            image_paths = []
            upload_errors = []

            # 1. ?대씪?댁뼵?몄뿉??吏곸젒 ?낅줈?쒗븳 URL 泥섎━ (異붿쿇 諛⑹떇)
            if client_image_urls:
                for url in client_image_urls:
                    if url.startswith('http') and 'cloudinary.com' in url:
                        image_paths.append(url)
                logger.info(f"Received {len(image_paths)} direct URLs from client.")

            # 2. ?쒕쾭瑜??듯븳 ?뚯씪 ?낅줈??泥섎━ (湲곗〈 諛⑹떇 ?좎?)
            if uploaded_images:
                import uuid

                ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
                use_cloudinary = getattr(settings, 'USE_CLOUDINARY', False)
                
                # [DEBUG] Cloudinary ?ㅼ젙 ?곹깭 媛뺤젣 異쒕젰
                try:
                    debug_cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', 'Not Set')
                    debug_api_key = settings.CLOUDINARY_STORAGE.get('API_KEY', 'Not Set')
                    # API Key??蹂댁븞???쇰?留?異쒕젰
                    if len(debug_api_key) > 5:
                        debug_api_key_masked = debug_api_key[:5] + "***"
                    else:
                        debug_api_key_masked = debug_api_key

                    logger.info(f"?뵇 DEBUG: USE_CLOUDINARY={use_cloudinary}")
                    logger.info(f"?뵇 DEBUG: CLOUDINARY_STORAGE CloudName={debug_cloud_name}, APIKey={debug_api_key_masked}")
                except Exception as e:
                    logger.error(f"?뵇 DEBUG LOGGING FAILED: {e}")

                logger.info(f"Processing {len(uploaded_images)} images. USE_CLOUDINARY={use_cloudinary}")

                for idx, img in enumerate(uploaded_images[:5]):
                    ext = os.path.splitext(img.name)[1].lower()

                    # Validate file
                    if ext not in ALLOWED_IMAGE_EXTENSIONS:
                        upload_errors.append(f"{img.name}: 吏?먰븯吏 ?딅뒗 ?뚯씪 ?뺤떇")
                        continue
                    if img.size > MAX_IMAGE_SIZE:
                        upload_errors.append(f"{img.name}: ?뚯씪 ?ш린 珥덇낵 (理쒕? 10MB)")
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
                                    error_msg = f"{img.name}: Cloudinary URL ?놁쓬"
                                    upload_errors.append(error_msg)
                                    logger.error(error_msg)

                            except Exception as cloud_err:
                                error_msg = f"{img.name}: Cloudinary ?낅줈???ㅽ뙣 - {str(cloud_err)}"
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
                        error_msg = f"{img.name}: ?낅줈??以??ㅻ쪟 - {str(e)}"
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
                messages.error(request, "?낅젰 ?곗씠?곌? ?놁뒿?덈떎. ?ㅼ떆 ?쒖옉?댁＜?몄슂.")
                return redirect('autoarticle:create')

            api_key, is_master_key = self.get_api_key(request)
            if not api_key:
                messages.error(request, "AI API key가 설정되지 않았습니다. 관리자에게 문의해주세요.")
                return redirect('autoarticle:create')
            if is_master_key and self._is_master_deepseek_daily_limit_exceeded(request):
                messages.error(request, "오늘은 기사 생성 가능 횟수를 모두 사용했습니다.")
                return redirect('autoarticle:create')
            rag = self.get_style_rag()

            try:
                title, content, hashtags = generate_article_gemini(api_key, input_data, style_service=rag, is_master_key=is_master_key)
                summary_points = summarize_article_for_ppt(content, api_key=api_key, is_master_key=is_master_key)
                images_from_session = request.session.get('article_images', [])
                print(f"DEBUG: Step 2 - Images from session: {images_from_session}")
                draft = {
                    'input_data': input_data,
                    'title': title,
                    'content': content,
                    'hashtags': hashtags,
                    'content_summary': '\n'.join(summary_points),
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
                messages.error(request, f"AI ?앹꽦 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: {str(e)}")
                return redirect('autoarticle:create')

        elif step == '3':
            try:
                draft = request.session.get('article_draft')
                if not draft:
                    return redirect('autoarticle:create')
                _, is_master_key = self.get_api_key(request)
                if is_master_key and self._is_master_deepseek_daily_limit_exceeded(request):
                    messages.error(request, "오늘은 기사 생성 가능 횟수를 모두 사용했습니다.")
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
                    content_summary=draft.get('content_summary', ''),
                    full_text=final_content,
                    hashtags=[t.strip('#') for t in final_tags],
                    images=draft.get('images', [])
                )
                
                # [OPTIMIZATION] PPT generation is now lazy (on demand)
                # Just save basic info
                article.save()
                
                del request.session['article_draft']
                messages.success(request, "湲곗궗媛 ?깃났?곸쑝濡???λ릺?덉뒿?덈떎.")
                return redirect('autoarticle:detail', pk=article.pk)
            except Exception as e:
                messages.error(request, f"???以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: {str(e)}")
                return redirect('autoarticle:create')



        return redirect('autoarticle:create')

@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleArchiveView(ListView):
    model = GeneratedArticle
    template_name = 'autoarticle/archive.html'
    context_object_name = 'articles'
    ordering = ['-event_date', '-created_at']

    def get_queryset(self):
        return GeneratedArticle.objects.filter(user=self.request.user).order_by('-event_date', '-created_at')

    def post(self, request):
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_articles')
        
        if not selected_ids:
            messages.warning(request, "湲곗궗瑜??좏깮?댁＜?몄슂.")
            return redirect('autoarticle:archive')

        articles = GeneratedArticle.objects.filter(id__in=selected_ids, user=request.user)
        school_name = request.session.get('autoarticle_school', '?ㅼ엥??珥덈벑?숆탳')
        theme = request.session.get('autoarticle_theme', '??& ?뚮젅?댄?')

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
            if isinstance(pdf_data, bytearray):
                pdf_data = bytes(pdf_data)
            elif isinstance(pdf_data, str):
                pdf_data = pdf_data.encode('latin-1')
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

        elif action == 'delete_selected':
            deleted_count = 0
            for article in articles:
                _delete_article_assets(article)
                article.delete()
                deleted_count += 1
            messages.success(request, f"{deleted_count}개의 기사를 삭제했습니다.")
            return redirect('autoarticle:archive')

        return redirect('autoarticle:archive')

@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleDetailView(DetailView):
    model = GeneratedArticle
    template_name = 'autoarticle/detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        return GeneratedArticle.objects.filter(user=self.request.user)

@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleCardNewsView(View):
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        theme = request.session.get('autoarticle_theme', '??& ?뚮젅?댄?')

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


@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleWordView(View):
    """媛쒕퀎 湲곗궗 Word ?ㅼ슫濡쒕뱶"""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        theme = request.session.get('autoarticle_theme', '??& ?뚮젅?댄?')

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


@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleDeleteView(View):
    """湲곗궗 ??젣"""
    def post(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        _delete_article_assets(article)
        article.delete()
        messages.success(request, "湲곗궗媛 ??젣?섏뿀?듬땲??")
        return redirect('autoarticle:archive')


@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticleEditView(View):
    """湲곗궗 ?섏젙"""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        context = {
            'article': article,
            'hashtags_str': ' '.join([f'#{tag}' for tag in article.hashtags]) if article.hashtags else ''
        }
        return render(request, 'autoarticle/edit.html', context)

    def post(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)

        article.title = request.POST.get('title', article.title)
        article.full_text = request.POST.get('content', article.full_text)

        hashtags_str = request.POST.get('hashtags', '')
        if hashtags_str:
            article.hashtags = [t.strip('#').strip() for t in hashtags_str.split() if t.strip()]

        article.save()
        messages.success(request, "湲곗궗媛 ?섏젙?섏뿀?듬땲??")
        return redirect('autoarticle:detail', pk=pk)


@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticlePPTDownloadView(View):
    """湲곗궗 PPT ?ㅼ슫濡쒕뱶 (Lazy Generation)"""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        
        # 1. ?대? ?뚯씪???덉쑝硫?利됱떆 諛섑솚
        if article.ppt_file:
            try:
                # FileField??url??absolute??寃쎌슦? relative??寃쎌슦 泥섎━
                return redirect(article.ppt_file.url)
            except Exception:
                pass

        # 2. ?뚯씪???놁쑝硫??앹꽦 ?쒖옉
        try:
            # API ??媛?몄삤湲?            parent_view = ArticleCreateView()
            api_key, is_master_key = parent_view.get_api_key(request)
            
            # ?붿빟 ?앹꽦 (?대? ?덉쑝硫??ъ궗??
            summary_points = article.content_summary_list
            if not summary_points:
                summary_points = summarize_article_for_ppt(article.full_text, api_key=api_key, is_master_key=is_master_key)
                article.content_summary = '\n'.join(summary_points)
                article.save()

            # PPT ?앹꽦
            theme = request.session.get('autoarticle_theme', ArticleCreateView.THEMES[0])
            ppt_engine = PPTEngine(theme, article.school_name)
            
            article_data = {
                'title': article.title,
                'content': summary_points,
                'date': article.event_date.strftime('%Y.%m.%d') if article.event_date else '',
                'location': article.location,
                'images': article.images or []
            }
            
            from django.core.files.base import ContentFile
            ppt_buffer = ppt_engine.create_presentation([article_data])
            article.ppt_file.save(f"newsletter_{article.id}.pptx", ContentFile(ppt_buffer.getvalue()))
            article.save()
            
            return redirect(article.ppt_file.url)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Lazy PPT Generation failed: {e}", exc_info=True)
            messages.error(request, f"PPT ?앹꽦 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: {str(e)}")
            return redirect('autoarticle:detail', pk=pk)

@method_decorator(login_required(login_url='account_login'), name='dispatch')
class ArticlePDFDownloadView(View):
    """Single article PDF download (lazy generation)."""
    def get(self, request, pk):
        article = get_object_or_404(GeneratedArticle, pk=pk, user=request.user)
        try:
            theme = request.session.get('autoarticle_theme', ArticleCreateView.THEMES[0])
            pdf_engine = PDFEngine(theme, article.school_name)
            pdf_engine.draw_cover()

            article_data = {
                'title': article.title,
                'content': article.full_text,
                'date': article.event_date.strftime('%Y.%m.%d') if article.event_date else '',
                'location': article.location,
                'grade': article.grade,
                'images': article.images or []
            }
            pdf_engine.add_article(article_data, is_booklet=True)

            pdf_data = pdf_engine.output(dest='S')
            if isinstance(pdf_data, bytearray):
                pdf_data = bytes(pdf_data)
            elif isinstance(pdf_data, str):
                pdf_data = pdf_data.encode('latin-1')

            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="newsletter_{article.id}.pdf"'
            return response
        except Exception as e:
            logger.error(f"Lazy PDF Generation failed: {e}", exc_info=True)
            messages.error(request, f"PDF generation failed: {str(e)}")
            return redirect('autoarticle:detail', pk=pk)



