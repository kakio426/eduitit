import json
import pickle
from pathlib import Path

from django.conf import settings

DEFAULT_MODEL_FILENAME = "message_capture_item_type_model.pkl"
DEFAULT_ASSIST_THRESHOLD = 0.80


def get_default_model_path():
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base_dir / "var" / "classcalendar" / DEFAULT_MODEL_FILENAME


def build_classifier_text_sample(
    *,
    raw_text="",
    normalized_text="",
    source_hint="unknown",
    attachment_extensions=None,
    parser_result=None,
):
    attachment_extensions = attachment_extensions or []
    parser_result = parser_result or {}
    parser_signals = {
        "predicted_item_type": parser_result.get("predicted_item_type") or "unknown",
        "deadline_only": bool(parser_result.get("deadline_only")),
        "category": parser_result.get("category") or "",
        "audience": parser_result.get("audience") or "",
        "has_start": bool(parser_result.get("extracted_start_time")),
        "has_end": bool(parser_result.get("extracted_end_time")),
        "has_location": bool(parser_result.get("location")),
        "has_materials": bool(parser_result.get("materials")),
        "has_recurrence": bool(parser_result.get("recurrence_hint")),
    }
    parts = [
        f"source={source_hint or 'unknown'}",
        f"attachments={','.join(sorted(attachment_extensions))}",
        f"parser={json.dumps(parser_signals, ensure_ascii=False, sort_keys=True)}",
        normalized_text or raw_text or "",
    ]
    return "\n".join(str(part) for part in parts if str(part).strip())


def load_classifier_artifact(model_path=None):
    path = Path(model_path or get_default_model_path())
    if not path.exists():
        return None
    with path.open("rb") as fp:
        return pickle.load(fp)


def predict_item_type(*, raw_text="", normalized_text="", source_hint="unknown", attachment_extensions=None, parser_result=None, model_path=None):
    artifact = load_classifier_artifact(model_path=model_path)
    if not artifact:
        return None

    pipeline = artifact.get("pipeline")
    labels = artifact.get("labels") or []
    if pipeline is None or not labels:
        return None

    sample = build_classifier_text_sample(
        raw_text=raw_text,
        normalized_text=normalized_text,
        source_hint=source_hint,
        attachment_extensions=attachment_extensions,
        parser_result=parser_result,
    )
    probabilities = pipeline.predict_proba([sample])[0]
    scores = {
        str(label): float(probability)
        for label, probability in zip(labels, probabilities)
    }
    label = max(scores, key=scores.get)
    return {
        "label": label,
        "scores": scores,
        "confidence": float(scores.get(label, 0.0)),
    }
