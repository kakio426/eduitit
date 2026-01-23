import os
import json
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from google import genai
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

def get_gemini_client():
    """Gemini Client (Server Credentials Priority)"""
    # 1. Check settings first (Server credentials)
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    # 2. Env var fallback
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        return None
        
    return genai.Client(api_key=api_key)

def setup_view(request):
    """Setup Page"""
    return render(request, 'artclass/setup.html')

def classroom_view(request):
    """Classroom Page"""
    if request.method == 'POST':
        # Save data to session and redirect (PRG pattern)
        steps = json.loads(request.POST.get('steps', '[]'))
        video_url = request.POST.get('videoUrl')
        interval = request.POST.get('stepInterval', 10)
        
        request.session['artclass_data'] = {
            'steps': steps,
            'videoUrl': video_url,
            'stepInterval': interval
        }
        return redirect('artclass:classroom')
    
    # Get from session
    data = request.session.get('artclass_data', {})
    if not data:
        return redirect('artclass:setup')
        
    return render(request, 'artclass/classroom.html', {
        'data': data,
        'data_json': json.dumps(data) # Passing for JS
    })

def extract_video_id(url):
    """Simple extractor (could be improved regex)"""
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None

def get_video_info(url):
    """Get Title and Transcript"""
    title = ""
    transcript_text = ""
    
    # 1. Get Title via NoEmbed
    try:
        resp = requests.get(f"https://noembed.com/embed?url={url}", timeout=5)
        if resp.status_code == 200:
            title = resp.json().get('title', '')
    except Exception as e:
        print(f"Title fetch error: {e}")
        
    # 2. Get Transcript
    video_id = extract_video_id(url)
    if video_id and YouTubeTranscriptApi:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
            transcript_text = " ".join([t['text'] for t in transcript_list])
        except Exception as e:
            print(f"Transcript fetch error: {e}")
            transcript_text = ""
            
    return title, transcript_text

@csrf_exempt
def generate_steps_api(request):
    """AI Step Generation API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        video_url = data.get('videoUrl')
        user_transcript = data.get('transcript', '') # Optional manual transcript
        
        if not video_url:
            return JsonResponse({'error': 'Video URL required'}, status=400)

        # Fetch info
        title, auto_transcript = get_video_info(video_url)
        
        # Use user transcript if provided, else auto
        effective_transcript = user_transcript if user_transcript else auto_transcript
        
        # Check text length
        if len(effective_transcript.strip()) < 20 and not title:
             return JsonResponse({'error': 'LOW_INFO'}, status=400)

        # Gemini Call
        client = get_gemini_client()
        if not client:
             return JsonResponse({'error': 'Server API Key not configured'}, status=503)
             
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
        
        # Format for frontend: {id, text}
        formatted_steps = [{'id': i, 'text': s} for i, s in enumerate(steps)]
        
        return JsonResponse({'steps': formatted_steps})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
