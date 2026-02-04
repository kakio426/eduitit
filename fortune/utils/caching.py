"""
사주 결과 캐싱 헬퍼 함수
natal_hash 기반으로 DB에서 캐시된 결과를 조회하고 저장합니다.
"""
import hashlib
from django.db.models import Q
from fortune.models import FortuneResult, DailyFortuneCache, DailyFortuneCache


def get_natal_hash(chart_context):
    """
    사주 명식(8글자)으로부터 SHA-256 해시를 생성합니다.

    Args:
        chart_context (dict): 'pillars' 키를 포함한 사주 데이터
            예: {'pillars': {'year': '甲子', 'month': '丙寅', ...}}

    Returns:
        str: 64자리 16진수 해시
    """
    pillars = chart_context.get('pillars', {})
    ganji_str = ''.join([
        pillars.get('year', ''),
        pillars.get('month', ''),
        pillars.get('day', ''),
        pillars.get('hour', '')
    ])
    return hashlib.sha256(ganji_str.encode('utf-8')).hexdigest()


def get_cached_result(user, natal_hash, mode=None, topic=None):
    """
    DB에서 캐시된 사주 결과를 조회합니다.

    Args:
        user (User): 사용자 객체 (익명 사용자의 경우 None)
        natal_hash (str): 사주 명식 해시
        mode (str, optional): 분석 모드 ('teacher', 'general', 'daily')
        topic (str, optional): 분석 주제 ('personality', 'wealth', etc.)

    Returns:
        FortuneResult or None: 캐시 히트 시 FortuneResult 객체, 미스 시 None
    """
    if not user or not user.is_authenticated:
        return None

    # 기본 쿼리: user와 natal_hash 매칭
    query = Q(user=user, natal_hash=natal_hash)

    # mode가 지정된 경우 (saju_view 용)
    if mode:
        query &= Q(mode=mode)

    # topic이 지정된 경우 (analyze_topic 용)
    if topic:
        query &= Q(topic=topic)
    else:
        # topic이 None인 경우만 조회 (전체 분석)
        query &= Q(topic__isnull=True)

    try:
        return FortuneResult.objects.filter(query).latest('created_at')
    except FortuneResult.DoesNotExist:
        return None


def save_cached_result(user, natal_hash, result_text, chart_context, mode='general', topic=None, user_context_hash=None):
    """
    사주 분석 결과를 DB에 저장합니다 (캐싱).

    Args:
        user (User): 사용자 객체
        natal_hash (str): 사주 명식 해시
        result_text (str): AI 생성 결과 텍스트
        chart_context (dict): 전체 사주 데이터 (JSON 저장용)
        mode (str): 분석 모드 ('teacher', 'general', 'daily')
        topic (str, optional): 분석 주제
        user_context_hash (str, optional): 이름+성별+생년월일시 해시

    Returns:
        FortuneResult: 저장된 객체
    """
    if not user or not user.is_authenticated:
        return None

    # user_context_hash가 없으면 natal_hash 사용 (하위 호환성)
    if user_context_hash is None:
        user_context_hash = natal_hash

    # unique_together 제약 조건으로 인해 중복 방지됨
    result, created = FortuneResult.objects.update_or_create(
        user=user,
        natal_hash=natal_hash,
        topic=topic,
        defaults={
            'mode': mode,
            'natal_chart': chart_context,
            'result_text': result_text,
            'user_context_hash': user_context_hash,
        }
    )

    return result


def get_user_context_hash(name, gender, natal_hash):
    """
    이름 + 성별 + 생년월일시를 모두 포함한 해시 생성

    Args:
        name (str): 사용자 이름
        gender (str): 성별 ('male' or 'female')
        natal_hash (str): 사주 명식 해시

    Returns:
        str: 64자리 16진수 해시
    """
    context_str = f"{name}:{gender}:{natal_hash}"
    return hashlib.sha256(context_str.encode('utf-8')).hexdigest()


def get_cached_daily_fortune(user, natal_hash, mode, target_date):
    """
    일진 캐시 조회 (영구 보관)

    Args:
        user (User): 사용자 객체
        natal_hash (str): 사주 명식 해시
        mode (str): 분석 모드 ('teacher' or 'general')
        target_date (date): 일진 날짜

    Returns:
        DailyFortuneCache or None: 캐시 히트 시 객체, 미스 시 None
    """
    if not user or not user.is_authenticated:
        return None

    try:
        return DailyFortuneCache.objects.get(
            user=user,
            natal_hash=natal_hash,
            mode=mode,
            target_date=target_date
        )
    except DailyFortuneCache.DoesNotExist:
        return None


def save_daily_fortune_cache(user, natal_hash, mode, target_date, result_text):
    """
    일진 결과 저장 (만료 없음)

    Args:
        user (User): 사용자 객체
        natal_hash (str): 사주 명식 해시
        mode (str): 분석 모드 ('teacher' or 'general')
        target_date (date): 일진 날짜
        result_text (str): AI 생성 결과 텍스트

    Returns:
        DailyFortuneCache: 저장된 객체
    """
    if not user or not user.is_authenticated:
        return None

    cache, created = DailyFortuneCache.objects.update_or_create(
        user=user,
        natal_hash=natal_hash,
        mode=mode,
        target_date=target_date,
        defaults={'result_text': result_text}
    )

    return cache


def get_user_context_hash(name, gender, natal_hash):
    """
    이름+성별+생년월일시를 모두 포함한 해시 생성

    Args:
        name (str): 사용자 이름
        gender (str): 성별 ('male' or 'female')
        natal_hash (str): 사주 명식 해시

    Returns:
        str: 64자리 16진수 해시
    """
    context_str = f"{name}:{gender}:{natal_hash}"
    return hashlib.sha256(context_str.encode('utf-8')).hexdigest()


def get_cached_daily_fortune(user, natal_hash, mode, target_date):
    """
    일진 캐시 조회 (영구 보관)

    Args:
        user (User): 사용자 객체
        natal_hash (str): 사주 명식 해시
        mode (str): 'teacher' or 'general'
        target_date (date): 조회할 날짜

    Returns:
        DailyFortuneCache or None: 캐시 히트 시 객체 반환
    """
    if not user or not user.is_authenticated:
        return None

    try:
        return DailyFortuneCache.objects.get(
            user=user,
            natal_hash=natal_hash,
            mode=mode,
            target_date=target_date
        )
    except DailyFortuneCache.DoesNotExist:
        return None


def save_daily_fortune_cache(user, natal_hash, mode, target_date, result_text):
    """
    일진 결과 저장 (만료 없음)

    Args:
        user (User): 사용자 객체
        natal_hash (str): 사주 명식 해시
        mode (str): 'teacher' or 'general'
        target_date (date): 해당 날짜
        result_text (str): AI 생성 결과

    Returns:
        DailyFortuneCache: 저장된 객체
    """
    if not user or not user.is_authenticated:
        return None

    cache, created = DailyFortuneCache.objects.update_or_create(
        user=user,
        natal_hash=natal_hash,
        mode=mode,
        target_date=target_date,
        defaults={'result_text': result_text}
    )

    return cache
