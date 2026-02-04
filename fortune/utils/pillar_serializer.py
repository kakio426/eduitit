"""
사주 팔자(四柱八字) JSON 직렬화 유틸리티

일주 추출 에러를 해결하기 위해 사주 데이터를 항상 JSON 형태로 직렬화합니다.
정규식 파싱 불필요 → 프론트엔드에서 확실하게 추출 가능
"""
import json


def serialize_pillars(pillars_dict, natal_hash='', user_context_hash=''):
    """
    사주 팔자를 JSON 직렬화 가능한 형태로 변환

    Args:
        pillars_dict (dict): calculator에서 반환된 pillars 딕셔너리
            예시: {
                'year': {'ganji': '甲子', 'stem': '甲', 'branch': '子', ...},
                'month': {...},
                'day': {...},
                'hour': {...}
            }
        natal_hash (str, optional): 사주 명식 해시
        user_context_hash (str, optional): 사용자 컨텍스트 해시

    Returns:
        dict: JSON 직렬화 가능한 사주 데이터
    """
    serialized = {
        'year': _serialize_pillar(pillars_dict.get('year', {})),
        'month': _serialize_pillar(pillars_dict.get('month', {})),
        'day': _serialize_pillar(pillars_dict.get('day', {})),
        'hour': _serialize_pillar(pillars_dict.get('hour', {})),
        'natal_hash': natal_hash,
        'user_context_hash': user_context_hash
    }

    return serialized


def _serialize_pillar(pillar_data):
    """
    개별 기둥(年/月/日/時) 데이터 직렬화

    Args:
        pillar_data (dict): 단일 기둥 데이터

    Returns:
        dict: 직렬화된 기둥 데이터
    """
    if not pillar_data:
        return {
            'ganji': '',
            'stem': '',
            'branch': '',
            'stem_en': '',
            'branch_en': '',
            'element': ''
        }

    return {
        'ganji': pillar_data.get('ganji', ''),
        'stem': pillar_data.get('stem', ''),
        'branch': pillar_data.get('branch', ''),
        'stem_en': pillar_data.get('stem_en', ''),
        'branch_en': pillar_data.get('branch_en', ''),
        'element': pillar_data.get('element', ''),
        # 추가 정보가 있다면 포함
        **{k: v for k, v in pillar_data.items()
           if k not in ['ganji', 'stem', 'branch', 'stem_en', 'branch_en', 'element']}
    }


def pillars_to_json_string(pillars_dict, natal_hash='', user_context_hash=''):
    """
    사주 팔자를 JSON 문자열로 변환 (템플릿에서 사용)

    Args:
        pillars_dict (dict): calculator에서 반환된 pillars 딕셔너리
        natal_hash (str, optional): 사주 명식 해시
        user_context_hash (str, optional): 사용자 컨텍스트 해시

    Returns:
        str: JSON 문자열
    """
    serialized = serialize_pillars(pillars_dict, natal_hash, user_context_hash)
    return json.dumps(serialized, ensure_ascii=False)


def extract_day_pillar(chart_data):
    """
    차트 데이터에서 일주(日柱) 추출

    Args:
        chart_data (dict or str): 직렬화된 사주 데이터 또는 JSON 문자열

    Returns:
        str: 일주 간지 (예: '甲子')
    """
    if isinstance(chart_data, str):
        try:
            chart_data = json.loads(chart_data)
        except json.JSONDecodeError:
            return ''

    day_pillar = chart_data.get('day', {})
    return day_pillar.get('ganji', '')


def extract_all_ganjis(chart_data):
    """
    차트 데이터에서 모든 간지 추출

    Args:
        chart_data (dict or str): 직렬화된 사주 데이터 또는 JSON 문자열

    Returns:
        dict: {'year': '甲子', 'month': '丙寅', 'day': '戊辰', 'hour': '庚午'}
    """
    if isinstance(chart_data, str):
        try:
            chart_data = json.loads(chart_data)
        except json.JSONDecodeError:
            return {'year': '', 'month': '', 'day': '', 'hour': ''}

    return {
        'year': chart_data.get('year', {}).get('ganji', ''),
        'month': chart_data.get('month', {}).get('ganji', ''),
        'day': chart_data.get('day', {}).get('ganji', ''),
        'hour': chart_data.get('hour', {}).get('ganji', '')
    }
