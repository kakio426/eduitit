PILLARS = ("year", "month", "day", "hour")
PILLAR_ALIASES = {"hour": ("hour", "time")}


def normalize_natal_chart_payload(natal_chart):
    """
    Normalize different natal chart formats into:
    {'year': {'stem': '甲', 'branch': '子'}, ...}
    """
    if not isinstance(natal_chart, dict):
        return {}

    normalized = {}
    for pillar in PILLARS:
        keys = PILLAR_ALIASES.get(pillar, (pillar,))
        raw = None
        for key in keys:
            if key in natal_chart:
                raw = natal_chart.get(key)
                break
        stem = None
        branch = None

        if isinstance(raw, dict):
            stem = raw.get("stem") or raw.get("gan")
            branch = raw.get("branch") or raw.get("ji")
        elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
            stem, branch = raw[0], raw[1]
        elif isinstance(raw, str) and len(raw) >= 2:
            stem, branch = raw[:1], raw[1:]

        if stem and branch:
            normalized[pillar] = {"stem": str(stem), "branch": str(branch)}

    return normalized


def _extract_day_master(natal_chart):
    normalized = normalize_natal_chart_payload(natal_chart)
    day = normalized.get("day", {})
    return day.get("stem", "Unknown")


def _format_birth(profile):
    year = getattr(profile, "birth_year", "")
    month = getattr(profile, "birth_month", "")
    day = getattr(profile, "birth_day", "")
    hour = getattr(profile, "birth_hour", None)
    minute = getattr(profile, "birth_minute", None)

    if hour is None or minute is None:
        return f"{year}-{month:02d}-{day:02d}" if month and day else str(year)
    return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"


def _compress_text(text, max_len=320):
    if not text:
        return ""
    clean = " ".join(str(text).split())
    if len(clean) <= max_len:
        return clean
    return clean[:max_len] + "..."


def _build_general_history_block(general_results):
    if not general_results:
        return "None"

    lines = []
    for idx, item in enumerate(general_results, start=1):
        created_at = item.get("created_at")
        created_label = created_at.isoformat() if created_at else "unknown-time"
        summary = _compress_text(item.get("result_text", ""))
        if summary:
            lines.append(f"{idx}. ({created_label}) {summary}")

    return "\n".join(lines) if lines else "None"


def build_system_prompt(profile, natal_chart, general_results=None):
    person_name = getattr(profile, "person_name", getattr(profile, "name", "Student"))
    gender = getattr(profile, "gender", "unknown")
    day_master = _extract_day_master(natal_chart)
    birth_text = _format_birth(profile)
    prior_general = _build_general_history_block(general_results or [])

    prompt = f"""
role: Saju Teacher
Language: Korean honorific
Tone: warm, specific, and easy to understand
Format: plain text only
Length: 3-4 sentences

[User Context]
Name: {person_name}
Gender: {gender}
Birth Datetime: {birth_text}
Day Master: {day_master}

[Prior General Readings]
Use these as references for consistency.
If the user's new question conflicts with old readings, explain why briefly.
{prior_general}

[Instructions]
1. Address the user by "{person_name}" naturally.
2. Day Master is fixed as "{day_master}". Never change or reinterpret this value.
3. Base interpretation on that fixed Day Master and birth context.
4. If prior general readings exist, keep interpretation consistent with them.
5. If there is a conflict, explain the reason briefly without changing Day Master.
6. Keep wording plain and avoid unnecessary jargon.
7. Do not use markdown symbols like **, `, #, >, _, [, ] or headings.
8. Never reveal or repeat full private birth data unless the user asks.
9. Answer in Korean honorific style.
"""
    return prompt.strip()
