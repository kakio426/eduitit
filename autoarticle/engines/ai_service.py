from google import genai
from google.genai import types
import re
import time
from collections import deque

# --- 설정 ---
# 절대 변경 금지: 선생님 요청 모델명
FIXED_MODEL_NAME = "gemini-3-flash-preview"

# Rate Limiter (5분에 2회 제한)
_usage_timestamps = deque()

def check_rate_limit(limit_count=2, limit_seconds=300):
    """
    최근 limit_seconds(초) 내에 사용 횟수가 limit_count를 넘었는지 확인.
    넘었으면 True(제한됨), 아니면 False(사용 가능) 반환.
    """
    now = time.time()
    
    # 오래된 기록 제거
    while _usage_timestamps and _usage_timestamps[0] < now - limit_seconds:
        _usage_timestamps.popleft()
        
    if len(_usage_timestamps) >= limit_count:
        return True
    
    _usage_timestamps.append(now)
    return False

def generate_article_gemini(api_key, topic_data, style_service=None):
    # 하이브리드 로직: 사용자가 직접 입력한 키가 아니고, 환경변수 키를 쓰는 경우에만 제한
    # is_using_master_key = not api_key # api_key 인자가 비어서 넘어오는 경우 (나중에 처리)
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Style RAG Injection
        style_prompt = ""
        if style_service:
            query = f"{topic_data['tone']} {topic_data['event_name']}"
            examples = style_service.retrieve_style_examples(query)
            if examples:
                 style_prompt = "\n\n[학교별 맞춤 스타일 참고 (이전에 사용자가 수정한 내역)]:\n"
                 for i, ex in enumerate(examples):
                     style_prompt += f"예시 {i+1} (교정된 표현):\n{ex['corrected']}\n...\n"
                 style_prompt += "\n위의 예시 '교정된 표현'들에서 느껴지는 어투, 단어 선택, 문장 길이를 적극 반영해주세요.\n"

        prompt = f"""
        당신은 {topic_data['school']}의 전문 학교 소식지 에디터입니다.
        다음 정보를 바탕으로 생동감 있고 따뜻한 어조의 {topic_data['tone']} 기사를 작성해주세요.
        
        학년: {topic_data['grade']}
        행사명: {topic_data['event_name']}
        장소: {topic_data['location']}
        일시: {topic_data['date']}
        주요 키워드: {topic_data['keywords']}
        {style_prompt}
        요구사항:
        1. 제목은 매력적으로 뽑아주세요. (첫 줄에 '제목: ' 형식으로)
        2. 본문은 400~600자 내외로 작성하세요.
        3. 학교 소식에 어울리는 정중하면서도 따뜻한 어투를 유지하세요.
        4. 문단은 보기 좋게 나누고 이모지를 적절히 사용하여 친근감을 주세요.
        5. 기사 끝에 관련 해시태그 5개를 작성해주세요. (형식: #태그1 #태그2 ...)
        6. 선정적이거나 부정적인 표현은 배제하고 긍정적인 교육적 가치를 강조하세요.
        """
        
        # Safety Settings
        config = types.GenerateContentConfig(
            safety_settings=[
                types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
            ]
        )

        response = client.models.generate_content(
            model=FIXED_MODEL_NAME,
            contents=prompt,
            config=config
        )
        text = response.text
        
        # 파싱
        title = topic_data['event_name']
        content = text
        hashtags = []
        
        # 해시태그 추출 logic
        found_hashtags = re.findall(r"#(\w+)", text)
        if found_hashtags:
            hashtags = found_hashtags[:5]
            lines = text.split('\n')
            clean_lines = [l for l in lines if not all(word.startswith('#') for word in l.split())]
            content = '\n'.join(clean_lines).strip()

        for line in text.split('\n'):
            if line.startswith("제목:") or line.startswith("##"):
                title = line.replace("제목:", "").replace("##", "").strip()
                temp_content = content.replace(line, "").strip()
                if temp_content: content = temp_content
                break
                
        return title, content, hashtags
    except Exception as e:
        return f"AI 생성 오류", str(e), []

def summarize_article_for_ppt(content, api_key=None):
    """
    긴 기사 내용을 PPT용 3~5줄 개조식(bullet points)으로 요약합니다.
    """
    if not api_key:
        return [content[:100] + "... (API 키가 설정되지 않아 요약할 수 없습니다.)"]

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    다음 학교 소식 기사를 파워포인트 슬라이드에 넣을 수 있도록 3~5개의 핵심 문장으로 요약해주세요.
    
    [규칙]
    1. 각 문장은 명사형으로 끝내거나 '~함', '~임' 등으로 간결하게 끝내주세요.
    2. 이모지를 적절히 사용하여 시각적으로 지루하지 않게 해주세요.
    3. 전체 내용은 5줄을 넘지 않게 해주세요.
    4. 결과는 오직 요약된 문장들만 줄바꿈으로 구분하여 반환하세요. (기타 멘트 생략)
    
    [기사 내용]
    {content}
    """
    
    try:
        config = types.GenerateContentConfig(
            safety_settings=[
                types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
            ]
        )
        
        response = client.models.generate_content(
            model=FIXED_MODEL_NAME,
            contents=prompt,
            config=config
        )
        lines = [line.strip().replace('* ', '').replace('- ', '') for line in response.text.split('\n') if line.strip()]
        if lines:
            return lines
    except Exception as e:
        last_error = str(e)
        print(f"⚠️ [PPT AI 요약] 실패: {last_error}")
        
        if "429" in last_error or "Quota" in last_error:
            return [content[:50] + "...", "(⚠️ API 사용량 초과로 요약 불가)"]
            
    return [content[:100] + "... (내용이 길어 요약에 실패했습니다. 원문을 확인해주세요.)"]

