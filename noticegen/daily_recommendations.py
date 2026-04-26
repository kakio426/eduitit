from __future__ import annotations

import hashlib
import logging
import os
import re
from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from korean_lunar_calendar import KoreanLunarCalendar
from openai import OpenAI

from .models import DailyNoticeRecommendation


logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
GENERATION_STALE_AFTER = timedelta(minutes=3)
DAILY_RECOMMENDATION_PROMPT_VERSION = "daily-safety-v1"

POLITICAL_OUTPUT_RE = re.compile(
    r"정당|선거|투표|대통령|국회의원|시위|집회|정권|정부\s*비판|이념|진보|보수|좌파|우파|북한|통일|외교|전쟁"
)
SUSPICIOUS_OUTPUT_RE = re.compile(r"요구사항|출력|프롬프트|대상:|주제:|분량:|제목:")
SAFETY_ACTION_RE = re.compile(r"안전|확인|주의|예방|지켜|살피|멈추|걷|손\s*씻|착용|챙겨|이동")
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•▪▶]+|\d+[\)\.])\s*")
TOPIC_TERM_RE = re.compile(r"[A-Za-z0-9가-힣]+")
TOPIC_TERM_SUFFIX_RE = re.compile(r"(?:으로|로|에서|에게|보다|처럼|부터|까지|하고|하며|하며도|하며서|하며는|하고도|하고는|하며|과|와|을|를|이|가|은|는|도|만)$")
TOPIC_TERM_STOPWORDS = {
    "가정",
    "가정에서도",
    "건강",
    "관리",
    "기록",
    "다시",
    "많은",
    "바르게",
    "생활",
    "생활안전",
    "시기",
    "안내",
    "안전",
    "안전수칙",
    "약속",
    "오늘",
    "오른쪽",
    "위험",
    "유지",
    "자주",
    "주변",
    "주의",
    "준비",
    "지키",
    "지키며",
    "차례",
    "천천히",
    "친구",
    "학급",
    "학생",
    "함께",
    "확인",
}


SAFETY_THEMES = (
    ("classroom_move", "교실 이동", "교실 안팎을 이동할 때 뛰지 않고 주변을 살피는 약속"),
    ("hallway_walk", "복도 보행", "복도에서 오른쪽으로 천천히 걷고 모퉁이에서 멈추는 약속"),
    ("stairs", "계단", "계단 난간을 잡고 한 칸씩 이동하는 약속"),
    ("playground", "운동장", "운동장 놀이 전후 주변을 확인하고 무리하지 않는 약속"),
    ("play_equipment", "놀이기구", "놀이기구 순서를 지키고 젖은 기구는 조심하는 약속"),
    ("lunch_hygiene", "급식 전 위생", "급식 전 손 씻기와 줄서기 약속"),
    ("water", "물 마시기", "더위와 활동량에 맞춰 물을 자주 마시는 약속"),
    ("privacy", "개인정보", "이름, 연락처, 사진을 함부로 공유하지 않는 약속"),
    ("stranger_contact", "낯선 연락", "낯선 연락이나 선물 제안을 바로 어른에게 알리는 약속"),
    ("crosswalk", "횡단보도", "멈추고 살피고 건너는 교통안전 약속"),
    ("bike", "자전거", "자전거를 탈 때 보호장구와 보행자 배려를 지키는 약속"),
    ("kickboard", "전동킥보드", "초등학생 전동킥보드 이용 위험과 탑승 금지 약속"),
    ("bus", "버스", "버스 승하차 때 뛰지 않고 손잡이를 잡는 약속"),
    ("commute", "등하교", "정해진 길로 다니고 주변 차량을 확인하는 약속"),
    ("rain", "비 오는 날", "우산 시야와 젖은 바닥 미끄럼을 조심하는 약속"),
    ("snow", "눈 오는 날", "눈길에서 뛰지 않고 장난치지 않는 약속"),
    ("ice", "빙판", "그늘진 길과 계단의 빙판을 살피는 약속"),
    ("heat", "폭염", "햇볕이 강한 날 물, 모자, 그늘 휴식을 챙기는 약속"),
    ("cold", "한파", "추운 날 겉옷, 장갑, 빙판 주의를 챙기는 약속"),
    ("dust", "미세먼지", "미세먼지 많은 날 실외활동과 개인위생을 조절하는 약속"),
    ("yellow_dust", "황사", "황사 시기 눈 비비지 않기와 손 씻기 약속"),
    ("infection", "감염병 예방", "기침 예절과 손 씻기를 생활화하는 약속"),
    ("hand_wash", "손 씻기", "화장실과 급식 전후 손 씻기 약속"),
    ("fire_drill", "화재 대피", "화재 알림을 들으면 낮은 자세로 질서 있게 이동하는 약속"),
    ("earthquake", "지진 대피", "흔들림 때 몸을 보호하고 안내에 따라 이동하는 약속"),
    ("science_room", "과학실", "실험 도구를 허락 없이 만지지 않는 약속"),
    ("art_tools", "미술도구", "가위, 풀, 색칠도구를 안전하게 쓰는 약속"),
    ("sharp_tools", "가위와 칼", "날카로운 도구를 장난감처럼 쓰지 않는 약속"),
    ("pe_warmup", "체육 준비운동", "체육 전 준비운동과 몸 상태 말하기 약속"),
    ("ball_play", "공놀이", "공놀이 전 주변 사람과 창문을 확인하는 약속"),
    ("swim", "물놀이", "물가에서 뛰지 않고 어른 안내를 따르는 약속"),
    ("field_trip", "현장체험", "현장체험 때 모둠과 이동 동선을 지키는 약속"),
    ("animal", "동물 접촉", "동물을 만진 뒤 손을 씻고 갑자기 다가가지 않는 약속"),
    ("food_poison", "식중독 예방", "음식 보관과 손 씻기로 배탈을 예방하는 약속"),
    ("allergy", "알레르기", "먹기 전 알레르기와 나눠 먹기 주의를 확인하는 약속"),
    ("medicine", "약물 오남용", "약은 보호자와 교사 확인 뒤 복용하는 약속"),
    ("smartphone", "스마트폰", "걸으면서 화면을 보지 않고 사용 시간을 조절하는 약속"),
    ("online_manners", "온라인 예절", "온라인에서도 친구를 존중하고 개인정보를 지키는 약속"),
    ("cyber_bullying", "사이버폭력 예방", "상처 주는 말과 사진 공유를 하지 않는 약속"),
    ("school_violence", "학교폭력 예방", "친구의 몸과 마음을 존중하고 도움을 요청하는 약속"),
    ("emotion", "감정 조절", "화가 날 때 멈추고 말로 도움을 요청하는 약속"),
    ("friend_conflict", "친구 갈등", "갈등이 생기면 밀거나 잡아당기지 않고 말로 풀어가는 약속"),
    ("play_rule", "놀이 약속", "놀이 규칙과 순서를 지키며 다치지 않게 노는 약속"),
    ("cleaning_tools", "청소도구", "빗자루와 대걸레를 들고 뛰지 않는 약속"),
    ("recycling", "분리수거", "유리와 날카로운 쓰레기를 직접 만지지 않는 약속"),
    ("door", "문 끼임", "문틈에 손을 넣지 않고 천천히 여닫는 약속"),
    ("window", "창문", "창가에 기대거나 몸을 내밀지 않는 약속"),
    ("elevator", "엘리베이터", "엘리베이터와 출입문 앞에서 장난치지 않는 약속"),
    ("bathroom", "화장실 미끄럼", "물기가 있는 바닥에서 뛰지 않는 약속"),
    ("cafeteria_line", "급식실 줄서기", "급식실 이동과 배식 줄에서 밀지 않는 약속"),
    ("posture", "바른 자세", "책상과 의자 사용 중 넘어지지 않게 앉는 약속"),
    ("eye_health", "눈 건강", "화면을 오래 볼 때 쉬는 시간을 갖는 약속"),
    ("hearing", "소리와 청각", "큰 소리 장난을 줄이고 귀를 보호하는 약속"),
    ("bag_weight", "가방 무게", "가방을 무리하게 들지 않고 필요한 물건만 챙기는 약속"),
    ("indoor_shoes", "실내화", "실내화를 바르게 신고 젖은 바닥을 조심하는 약속"),
    ("name_label", "준비물 이름표", "개인 물건을 확인하고 잃어버리지 않게 관리하는 약속"),
    ("emergency_contact", "비상 연락", "몸이 아프거나 위험하면 바로 어른에게 말하는 약속"),
    ("abduction", "유괴 예방", "혼자 이동하지 않고 낯선 제안을 거절하는 약속"),
    ("outdoor_walk", "야외 산책", "야외활동 때 대열과 이동 약속을 지키는 약속"),
    ("bugs", "벌레와 진드기", "풀밭 활동 뒤 옷과 피부를 확인하는 약속"),
    ("holiday_trip", "연휴 이동", "연휴 전 교통안전과 낯선 장소 주의를 확인하는 약속"),
    ("vacation", "방학 생활", "방학 중 생활 리듬과 안전한 외출 약속"),
    ("new_semester", "새 학기 적응", "새 학기 교실 위치와 이동 동선을 확인하는 약속"),
    ("test_health", "평가 전 건강", "평가 전 수면과 준비물을 챙겨 무리하지 않는 약속"),
    ("school_event", "학교 행사", "학교 행사 때 이동 순서와 질서를 지키는 약속"),
    ("after_school", "방과후 이동", "방과후 교실과 하교 동선을 안전하게 확인하는 약속"),
)

SAFETY_ACTIONS = (
    ("morning", "아침 확인", "오늘 아침 학급에서 함께 확인했습니다"),
    ("break", "쉬는 시간", "쉬는 시간 전에 다시 떠올리도록 지도했습니다"),
    ("dismissal", "하교 전", "하교 전에 한 번 더 확인했습니다"),
    ("home", "가정 연계", "가정에서도 이어서 살펴봐 주시면 좋겠습니다"),
    ("class_rule", "학급 약속", "오늘의 학급 안전 약속으로 정했습니다"),
    ("record", "생활 기록", "오늘 생활안전 확인 내용으로 남겼습니다"),
)

SEASONAL_WEATHER_HINTS = {
    1: ("겨울 한파와 빙판", "한파와 빙판길을 조심하는 시기입니다."),
    2: ("겨울 끝자락 일교차", "추위와 일교차가 함께 나타나는 시기입니다."),
    3: ("새 학기 일교차와 미세먼지", "일교차와 미세먼지를 함께 살피는 시기입니다."),
    4: ("봄철 미세먼지와 황사", "미세먼지와 황사가 잦아 개인위생이 중요합니다."),
    5: ("야외활동과 강한 햇볕", "야외활동이 늘어 물과 모자 준비가 필요합니다."),
    6: ("장마 전후 비와 미끄럼", "비와 젖은 바닥을 조심해야 하는 시기입니다."),
    7: ("폭염과 장마", "더위와 갑작스러운 비를 함께 살피는 시기입니다."),
    8: ("폭염과 개학 준비", "더위 속 활동량과 개학 준비를 함께 살피는 시기입니다."),
    9: ("가을 일교차", "아침저녁 일교차가 커지는 시기입니다."),
    10: ("가을 체험활동", "체험학습과 바깥활동이 잦아 이동 안전이 중요합니다."),
    11: ("초겨울 감기 예방", "감기 예방과 따뜻한 복장을 챙기는 시기입니다."),
    12: ("겨울 추위와 결빙", "추위와 결빙으로 미끄럼을 조심해야 하는 시기입니다."),
}

SOLAR_TERM_DATES = {
    (1, 5): "소한",
    (1, 20): "대한",
    (2, 4): "입춘",
    (2, 19): "우수",
    (3, 5): "경칩",
    (3, 20): "춘분",
    (4, 4): "청명",
    (4, 20): "곡우",
    (5, 5): "입하",
    (5, 21): "소만",
    (6, 5): "망종",
    (6, 21): "하지",
    (7, 7): "소서",
    (7, 22): "대서",
    (8, 7): "입추",
    (8, 23): "처서",
    (9, 7): "백로",
    (9, 23): "추분",
    (10, 8): "한로",
    (10, 23): "상강",
    (11, 7): "입동",
    (11, 22): "소설",
    (12, 7): "대설",
    (12, 22): "동지",
}


class DailyRecommendationQualityError(Exception):
    pass


def build_daily_safety_topic_catalog() -> list[dict]:
    catalog = []
    for theme_key, theme_label, focus in SAFETY_THEMES:
        for action_key, action_label, action_phrase in SAFETY_ACTIONS:
            index = len(catalog) + 1
            catalog.append(
                {
                    "key": f"safety-{index:03d}",
                    "theme_key": theme_key,
                    "action_key": action_key,
                    "topic_title": f"{theme_label} {action_label}",
                    "focus": focus,
                    "action_phrase": action_phrase,
                }
            )
            if len(catalog) >= 366:
                return catalog
    return catalog


def _safe_solar_date_from_lunar(year, month, day):
    try:
        calendar = KoreanLunarCalendar()
        calendar.setLunarDate(year, month, day, False)
        return date.fromisoformat(calendar.SolarIsoFormat())
    except Exception:
        return None


def _merge_marker(markers, marker_date, name):
    if not marker_date:
        return
    existing = markers.get(marker_date)
    if existing:
        markers[marker_date] = f"{existing} / {name}" if name not in existing else existing
    else:
        markers[marker_date] = name


def _next_available_substitute_date(start_date, occupied_dates):
    candidate = start_date + timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in occupied_dates:
        candidate += timedelta(days=1)
    return candidate


def _add_substitute_holidays(markers, substitute_rules, base_holidays):
    occupied_dates = set(markers)
    holiday_counts = Counter(marker_date for marker_date, _name, _enabled in base_holidays if marker_date)
    merged_rules = {}
    for rule in substitute_rules:
        dates = tuple(sorted(marker_date for marker_date in rule.get("dates", ()) if marker_date))
        if not dates:
            continue
        merged = merged_rules.setdefault(
            dates,
            {
                "names": [],
                "weekend_days": set(),
            },
        )
        name = str(rule.get("name") or "").strip()
        if name and name not in merged["names"]:
            merged["names"].append(name)
        merged["weekend_days"].update(rule.get("weekend_days", set()))

    for dates, rule in merged_rules.items():
        weekend_days = rule["weekend_days"] or {6}
        should_substitute = any(
            marker_date.weekday() in weekend_days or holiday_counts[marker_date] > 1
            for marker_date in dates
        )
        if not should_substitute:
            continue
        substitute_date = _next_available_substitute_date(max(dates), occupied_dates)
        occupied_dates.add(substitute_date)
        substitute_name = " / ".join(rule["names"]) or "공휴일"
        _merge_marker(markers, substitute_date, f"{substitute_name} 대체공휴일")


def _build_korean_holiday_markers(year):
    markers = {}
    substitute_rules = []
    base_holidays = [
        (date(year, 1, 1), "신정", False),
        (date(year, 3, 1), "삼일절", True),
        (date(year, 5, 5), "어린이날", True),
        (date(year, 6, 6), "현충일", False),
        (date(year, 8, 15), "광복절", True),
        (date(year, 10, 3), "개천절", True),
        (date(year, 10, 9), "한글날", True),
        (date(year, 12, 25), "기독탄신일", True),
    ]
    for marker_date, name, _substitute_enabled in base_holidays:
        _merge_marker(markers, marker_date, name)
    for marker_date, name, substitute_enabled in base_holidays:
        if substitute_enabled:
            substitute_rules.append(
                {
                    "dates": (marker_date,),
                    "name": name,
                    "weekend_days": {5, 6},
                }
            )

    seollal = _safe_solar_date_from_lunar(year, 1, 1)
    if seollal:
        seollal_dates = (
            seollal - timedelta(days=1),
            seollal,
            seollal + timedelta(days=1),
        )
        for marker_date, name in (
            (seollal_dates[0], "설날 연휴"),
            (seollal_dates[1], "설날"),
            (seollal_dates[2], "설날 연휴"),
        ):
            base_holidays.append((marker_date, name, True))
            _merge_marker(markers, marker_date, name)
        substitute_rules.append(
            {
                "dates": seollal_dates,
                "name": "설날",
                "weekend_days": {6},
            }
        )

    buddha = _safe_solar_date_from_lunar(year, 4, 8)
    base_holidays.append((buddha, "부처님오신날", True))
    _merge_marker(markers, buddha, "부처님오신날")
    substitute_rules.append(
        {
            "dates": (buddha,),
            "name": "부처님오신날",
            "weekend_days": {5, 6},
        }
    )

    chuseok = _safe_solar_date_from_lunar(year, 8, 15)
    if chuseok:
        chuseok_dates = (
            chuseok - timedelta(days=1),
            chuseok,
            chuseok + timedelta(days=1),
        )
        for marker_date, name in (
            (chuseok_dates[0], "추석 연휴"),
            (chuseok_dates[1], "추석"),
            (chuseok_dates[2], "추석 연휴"),
        ):
            base_holidays.append((marker_date, name, True))
            _merge_marker(markers, marker_date, name)
        substitute_rules.append(
            {
                "dates": chuseok_dates,
                "name": "추석",
                "weekend_days": {6},
            }
        )

    _add_substitute_holidays(markers, substitute_rules, base_holidays)
    return markers


def _tomorrow_holiday_name(target_date):
    tomorrow = target_date + timedelta(days=1)
    markers = _build_korean_holiday_markers(tomorrow.year)
    return markers.get(tomorrow, "")


def _tomorrow_solar_term_name(target_date):
    tomorrow = target_date + timedelta(days=1)
    return SOLAR_TERM_DATES.get((tomorrow.month, tomorrow.day), "")


def _season_name(month):
    if month in {3, 4, 5}:
        return "봄"
    if month in {6, 7, 8}:
        return "여름"
    if month in {9, 10, 11}:
        return "가을"
    return "겨울"


def _normalize_topic_term(term):
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", str(term or "").strip())
    previous = ""
    while normalized != previous and len(normalized) > 2:
        previous = normalized
        normalized = TOPIC_TERM_SUFFIX_RE.sub("", normalized)
    return normalized


def _topic_alignment_terms(context):
    raw_text = f"{context.get('topic_title', '')} {context.get('focus', '')}"
    terms = []
    seen = set()
    for raw_term in TOPIC_TERM_RE.findall(raw_text):
        term = _normalize_topic_term(raw_term)
        if len(term) < 2 or term in TOPIC_TERM_STOPWORDS:
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:8]


def _text_contains_topic_term(result_text, context):
    terms = context.get("required_terms") or _topic_alignment_terms(context)
    if not terms:
        return True
    normalized_text = re.sub(r"[^0-9A-Za-z가-힣]", "", str(result_text or ""))
    return any(term and term in normalized_text for term in terms)


def _select_topic_for_date(target_date):
    catalog = build_daily_safety_topic_catalog()
    base_index = (target_date.timetuple().tm_yday - 1) % len(catalog)
    since_date = target_date - timedelta(days=365)
    used_keys = set(
        DailyNoticeRecommendation.objects.filter(
            recommendation_date__gte=since_date,
            recommendation_date__lt=target_date,
        )
        .exclude(topic_key="")
        .values_list("topic_key", flat=True)
    )
    for offset in range(len(catalog)):
        candidate = catalog[(base_index + offset) % len(catalog)]
        if candidate["key"] not in used_keys:
            return candidate
    return catalog[base_index]


def build_daily_recommendation_context(target_date=None):
    target_date = target_date or timezone.localdate()
    topic = _select_topic_for_date(target_date)
    weather_label, weather_detail = SEASONAL_WEATHER_HINTS.get(
        target_date.month,
        ("계절 변화", "계절에 맞는 생활안전을 확인하는 날입니다."),
    )
    holiday_name = _tomorrow_holiday_name(target_date)
    solar_term_name = _tomorrow_solar_term_name(target_date)
    special_label = ""
    if holiday_name:
        special_label = f"{holiday_name} 전날"
    elif solar_term_name:
        special_label = f"{solar_term_name} 전날"

    context_label = special_label or weather_label
    context = {
        "date": target_date.isoformat(),
        "month": target_date.month,
        "day_of_year": target_date.timetuple().tm_yday,
        "season": _season_name(target_date.month),
        "country": "대한민국",
        "school_level": "초등학교",
        "weather_basis": weather_label,
        "weather_detail": weather_detail,
        "holiday_eve": holiday_name,
        "solar_term_eve": solar_term_name,
        "special_label": special_label,
        "context_label": context_label,
        "prompt_version": DAILY_RECOMMENDATION_PROMPT_VERSION,
        **topic,
    }
    context["required_terms"] = _topic_alignment_terms(context)
    return context


def _sanitize_output_text(raw_text):
    lines = []
    for raw_line in str(raw_text or "").splitlines():
        cleaned = BULLET_PREFIX_RE.sub("", raw_line).strip()
        if cleaned:
            lines.append(cleaned)
    compact = " ".join(lines)
    return re.sub(r"\s+", " ", compact).strip()


def _content_hash(result_text):
    normalized = re.sub(r"\s+", " ", str(result_text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _recent_content_hash_exists(target_date, content_hash):
    if not content_hash:
        return False
    since_date = target_date - timedelta(days=365)
    return DailyNoticeRecommendation.objects.filter(
        recommendation_date__gte=since_date,
        recommendation_date__lt=target_date,
        content_hash=content_hash,
    ).exists()


def _collect_quality_issues(result_text, context, *, target_date):
    issues = []
    if len(result_text) < 90:
        issues.append("TOO_SHORT")
    if len(result_text) > 320:
        issues.append("TOO_LONG")
    if POLITICAL_OUTPUT_RE.search(result_text):
        issues.append("POLITICAL_OUTPUT")
    if SUSPICIOUS_OUTPUT_RE.search(result_text):
        issues.append("META_OUTPUT")
    if not SAFETY_ACTION_RE.search(result_text):
        issues.append("NO_SAFETY_ACTION")
    if not _text_contains_topic_term(result_text, context):
        issues.append("TOPIC_MISMATCH")
    if context.get("holiday_eve") and context["holiday_eve"] not in result_text:
        issues.append("MISSING_HOLIDAY")
    if context.get("solar_term_eve") and context["solar_term_eve"] not in result_text:
        issues.append("MISSING_SOLAR_TERM")
    if _recent_content_hash_exists(target_date, _content_hash(result_text)):
        issues.append("DUPLICATE_CONTENT")
    return issues


def _build_fallback_text(context):
    special = context.get("special_label")
    if special:
        opening = f"내일은 {special.replace(' 전날', '')}입니다."
    else:
        opening = f"오늘은 {context['weather_basis']}에 맞춰 생활안전을 확인하는 날입니다."
    return (
        f"{opening} 오늘 학급에서는 {context['focus']}을 학생들과 함께 확인했습니다. "
        f"{context['action_phrase']}. 하교 후에도 가정에서 이동과 준비물을 한 번 더 살펴봐 주시기 바랍니다."
    )


def _build_system_prompt():
    return (
        "당신은 대한민국 초등학교 담임교사입니다. "
        "교사가 알림장에 바로 붙여 넣을 수 있는 오늘의 생활안전 안내문 1개만 작성합니다. "
        "정치, 이념, 선거, 정당, 외교, 사회 갈등 소재는 절대 쓰지 않습니다. "
        "법적 효력이나 공식 증빙을 단정하지 말고, 수업 중 안전수칙을 확인했다는 사실이 자연스럽게 남도록 씁니다. "
        "출력은 제목, 번호, 해시태그 없이 본문 한 단락만 작성합니다."
    )


def _build_user_prompt(context, *, retry_issues=None, previous_text=""):
    special_context = context.get("special_label") or "없음"
    required_terms = ", ".join(context.get("required_terms") or [])
    retry_text = ""
    if retry_issues:
        retry_text = (
            "\n재작성 사유: "
            + ", ".join(retry_issues)
            + f"\n직전 초안: {previous_text}\n위 문제를 고쳐 최종본 1개만 다시 작성하세요."
        )
    return (
        f"날짜: {context['date']}\n"
        f"계절/날씨 맥락: {context['weather_detail']}\n"
        f"특별한 전날 맥락: {special_context}\n"
        f"학교급: {context['school_level']}\n"
        f"안전 주제: {context['topic_title']}\n"
        f"반드시 담을 행동: {context['focus']}\n\n"
        f"주제 핵심어: {required_terms or context['topic_title']}\n\n"
        "작성 규칙:\n"
        "- 학부모가 바로 읽는 알림장 문체로 작성하세요.\n"
        "- 2~3문장, 공백 포함 120~240자 정도로 작성하세요.\n"
        "- '오늘 학급에서 확인했습니다'처럼 안전교육 확인 기록으로 남기기 좋은 문장을 포함하세요.\n"
        "- 주제 핵심어 중 1개 이상을 자연스럽게 포함하세요.\n"
        "- 가정에서 확인할 행동 1개를 포함하세요.\n"
        "- 특별한 전날 맥락이 있으면 첫 문장에 자연스럽게 반영하세요.\n"
        "- 정치적, 종교 선전성, 논쟁적 표현은 쓰지 마세요."
        f"{retry_text}"
    )


def _call_daily_recommendation_llm(system_prompt, user_prompt):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("API_NOT_CONFIGURED")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=45.0)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=False,
    )
    return (response.choices[0].message.content or "").strip()


def _generate_validated_text(context, *, target_date):
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(context)
    previous_text = ""
    last_issues = []
    for attempt_index in range(2):
        result_text = _sanitize_output_text(_call_daily_recommendation_llm(system_prompt, user_prompt))
        issues = _collect_quality_issues(result_text, context, target_date=target_date)
        if not issues:
            return result_text, ""
        previous_text = result_text
        last_issues = issues
        if attempt_index == 0:
            user_prompt = _build_user_prompt(context, retry_issues=issues, previous_text=previous_text)
    raise DailyRecommendationQualityError(",".join(last_issues) or "QUALITY_CHECK_FAILED")


def _generate_payload_for_date(target_date):
    context = build_daily_recommendation_context(target_date)
    try:
        result_text, error_code = _generate_validated_text(context, target_date=target_date)
        status = DailyNoticeRecommendation.STATUS_READY
    except Exception as exc:
        error_code = str(exc)[:64] or "FALLBACK_USED"
        logger.warning(
            "[NoticeGenDaily] fallback used date=%s error=%s",
            target_date,
            error_code,
        )
        result_text = _build_fallback_text(context)
        status = DailyNoticeRecommendation.STATUS_FALLBACK

    content_hash = _content_hash(result_text)
    return {
        "topic_key": context["key"],
        "context_label": context["context_label"],
        "source_context": context,
        "result_text": result_text,
        "content_hash": content_hash,
        "status": status,
        "error_code": error_code if status == DailyNoticeRecommendation.STATUS_FALLBACK else "",
    }


def _mark_served_locked(recommendation):
    now = timezone.now()
    DailyNoticeRecommendation.objects.filter(pk=recommendation.pk).update(
        served_count=F("served_count") + 1,
        last_served_at=now,
    )
    recommendation.refresh_from_db()
    return recommendation


def _serve_ready_recommendation(target_date):
    with transaction.atomic():
        recommendation = DailyNoticeRecommendation.objects.select_for_update().get(
            recommendation_date=target_date,
        )
        if recommendation.status not in {
            DailyNoticeRecommendation.STATUS_READY,
            DailyNoticeRecommendation.STATUS_FALLBACK,
        } or not recommendation.result_text:
            return recommendation, False, True
        return _mark_served_locked(recommendation), False, False


def get_or_create_daily_recommendation(target_date=None):
    target_date = target_date or timezone.localdate()
    now = timezone.now()
    should_generate = False

    with transaction.atomic():
        recommendation, created = DailyNoticeRecommendation.objects.select_for_update().get_or_create(
            recommendation_date=target_date,
            defaults={
                "status": DailyNoticeRecommendation.STATUS_GENERATING,
                "topic_key": "",
                "context_label": "",
                "source_context": {},
                "result_text": "",
                "content_hash": "",
                "error_code": "",
            },
        )
        if recommendation.status in {
            DailyNoticeRecommendation.STATUS_READY,
            DailyNoticeRecommendation.STATUS_FALLBACK,
        } and recommendation.result_text:
            return _mark_served_locked(recommendation), created, False

        is_fresh_generation = (
            recommendation.status == DailyNoticeRecommendation.STATUS_GENERATING
            and recommendation.updated_at
            and recommendation.updated_at > now - GENERATION_STALE_AFTER
        )
        if not created and is_fresh_generation:
            return recommendation, False, True

        recommendation.status = DailyNoticeRecommendation.STATUS_GENERATING
        recommendation.error_code = ""
        recommendation.save(update_fields=["status", "error_code", "updated_at"])
        should_generate = True

    if should_generate:
        payload = _generate_payload_for_date(target_date)
        DailyNoticeRecommendation.objects.filter(recommendation_date=target_date).update(**payload)

    return _serve_ready_recommendation(target_date)


def serialize_daily_recommendation(recommendation):
    return {
        "date": recommendation.recommendation_date.isoformat(),
        "topic_key": recommendation.topic_key,
        "context_label": recommendation.context_label,
        "source": recommendation.source_context or {},
        "result_text": recommendation.result_text,
        "status": recommendation.status,
        "served_count": recommendation.served_count,
    }
