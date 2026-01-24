import os
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from google import genai
from .models import ArtClass, ArtStep

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None


def get_gemini_client():
    """Gemini Client (Server Credentials Priority)"""
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def setup_view(request):
    """Setup Page - 수업 준비 페이지"""
    if request.method == 'POST':
        # multipart/form-data 처리
        video_url = request.POST.get('videoUrl', '')
        interval = int(request.POST.get('stepInterval', 10))
        title = request.POST.get('title', '')
        
        # ArtClass 생성
        art_class = ArtClass.objects.create(
            title=title,
            youtube_url=video_url,
            default_interval=interval,
            created_by=request.user if request.user.is_authenticated else None
        )
        
        # Steps 처리 (동적으로 추가된 필드들)
        step_count = int(request.POST.get('step_count', 0))
        for i in range(step_count):
            description = request.POST.get(f'step_text_{i}', '')
            image = request.FILES.get(f'step_image_{i}')
            
            ArtStep.objects.create(
                art_class=art_class,
                step_number=i + 1,
                description=description,
                image=image
            )
        
        return redirect('artclass:classroom', pk=art_class.pk)
    
    return render(request, 'artclass/setup.html')


def classroom_view(request, pk):
    """Classroom Page - 수업 진행 페이지"""
    art_class = get_object_or_404(ArtClass, pk=pk)
    steps = art_class.steps.all()
    
    # JSON 형태로 전달 (JS에서 사용)
    steps_data = [
        {
            'id': step.pk,
            'step_number': step.step_number,
            'text': step.description,
            'image_url': step.image.url if step.image else None
        }
        for step in steps
    ]
    
    data = {
        'videoUrl': art_class.youtube_url,
        'stepInterval': art_class.default_interval,
        'steps': steps_data
    }
    
    return render(request, 'artclass/classroom.html', {
        'art_class': art_class,
        'steps': steps,
        'data': data,
        'data_json': json.dumps(data, ensure_ascii=False)
    })


def extract_video_id(url):
    """Simple extractor"""
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None


def get_video_info(url):
    """Get Title and Transcript"""
    title = ""
    transcript_text = ""
    
    try:
        resp = requests.get(f"https://noembed.com/embed?url={url}", timeout=5)
        if resp.status_code == 200:
            title = resp.json().get('title', '')
    except Exception as e:
        print(f"Title fetch error: {e}")
        
    video_id = extract_video_id(url)
    if video_id and YouTubeTranscriptApi:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
            transcript_text = " ".join([t['text'] for t in transcript_list])
        except Exception as e:
            print(f"Transcript fetch error: {e}")
            transcript_text = ""
            
    return title, transcript_text


def generate_steps_api(request):
    """AI Step Generation API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        video_url = data.get('videoUrl')
        user_transcript = data.get('transcript', '')

        if not video_url:
            return JsonResponse({'error': 'Video URL required'}, status=400)

        title, auto_transcript = get_video_info(video_url)
        effective_transcript = user_transcript if user_transcript else auto_transcript

        if len(effective_transcript.strip()) < 20 and not title:
             return JsonResponse({'error': 'LOW_INFO'}, status=400)

        client = get_gemini_client()
        if not client:
             return JsonResponse({'error': 'API_NOT_CONFIGURED'}, status=503)

        prompt = f"""
            당신은 유능한 미술 선생님입니다. 제공된 정보를 바탕으로 학생들이 따라 하기 좋은 '단계별 미술 수업 안내'를 만들어주세요.

            [비디오 정보]
            - 제목: {title or '알 수 없음'}
            - 대본/설명: {effective_transcript or '자막 데이터 없음'}

            ※주의사항:
            1. 제공된 '제목'과 '대본'을 바탕으로 분석하십시오.
            2. 자막에 구체적인 미술 활동(그리기, 만들기 등) 내용이 전혀 없다면, "요약할 수 있는 충분한 정보가 없습니다."라고 한 줄만 출력하세요.
            3. 절대 임의로 상상해서 답변하지 마십시오. 모르면 모른다고 답변하십시오.
            4. 학생들의 눈높이에 맞춰 쉽고 명확한 문장으로 작성하세요.
            5. 각 단계는 한 줄씩 문장만 출력하세요 (번호, 기호, 타임스탬프 금지).
            6. 서론이나 맺음말 없이 본론만 출력하세요.
        """

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )

        text = response.text
        if "요약할 수 있는" in text or len(text.strip()) < 5:
             return JsonResponse({'error': 'LOW_INFO'}, status=400)

        steps = [line.strip() for line in text.split('\n') if line.strip()]
        formatted_steps = [{'id': i, 'text': s} for i, s in enumerate(steps)]

        return JsonResponse({'steps': formatted_steps})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'INVALID_JSON'}, status=400)
    except Exception:
        return JsonResponse({'error': 'INTERNAL_ERROR'}, status=500)
