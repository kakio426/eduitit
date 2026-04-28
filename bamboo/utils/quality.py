from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FableQualityResult:
    is_valid: bool
    reasons: tuple[str, ...] = ()


FABLE_CHARACTER_RE = re.compile(
    r"곰|공작새|까마귀|다람쥐|부엉이|여우|토끼|두더지|고슴도치|거북|개구리|"
    r"나무|버섯|풀잎|도토리|바위|시냇물|구름|바람|별|달|해|그림자|종|북"
)
FABLE_OPENING_RE = re.compile(r"옛날|어느\s+깊은\s+숲|숲에|마을에|들판에|연못에")
SUDDEN_ENDING_RE = re.compile(r"갑자기|뜬금없이|아무\s*이유\s*없이|왜인지|모든\s*문제가\s*해결|꿈이었다")
CONTRADICTION_RE = re.compile(r"죽었지만\s+살|비었지만\s+가득|없었지만\s+있|혼자였지만\s+모두|떠났지만\s+남")
META_QUALITY_RE = re.compile(r"우화\s*형식|이야기\s*구조|사용자|작성자\s*입력|검토|평가")


def validate_fable_quality(output: str) -> FableQualityResult:
    text = (output or "").strip()
    reasons: list[str] = []
    body = _body_without_title_and_whisper(text)
    sentences = _sentences(body)

    if len(sentences) < 4:
        reasons.append("too_few_sentences")
    if len(sentences) > 8:
        reasons.append("too_many_sentences")
    if not FABLE_OPENING_RE.search(body):
        reasons.append("missing_fable_opening")
    if len(FABLE_CHARACTER_RE.findall(body)) < 2:
        reasons.append("weak_fable_imagery")
    if SUDDEN_ENDING_RE.search(body):
        reasons.append("sudden_or_lazy_ending")
    if CONTRADICTION_RE.search(body):
        reasons.append("contradiction_pattern")
    if META_QUALITY_RE.search(body):
        reasons.append("meta_language")

    return FableQualityResult(is_valid=not reasons, reasons=tuple(dict.fromkeys(reasons)))


def _body_without_title_and_whisper(text: str) -> str:
    body = re.sub(r"^\s*##\s*제목\s*:\s*[^\n]+\n*", "", text, count=1)
    body = re.sub(r">\s*숲의\s*속삭임\s*:\s*.*$", "", body, flags=re.S).strip()
    return body


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？]|[다요죠네음임함됨])\s+", text or "")
        if sentence.strip()
    ]
