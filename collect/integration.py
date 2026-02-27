from urllib.parse import urlencode

from django.urls import reverse

from .models import CollectionRequest, Submission


BTI_SOURCE_SSAMBTI = "ssambti"
BTI_SOURCE_STUDENTMBTI = "studentmbti"


def normalize_collect_code(raw_code):
    return str(raw_code or "").strip()


def get_active_collect_request_by_code(raw_code):
    code = normalize_collect_code(raw_code)
    if not code:
        return None
    return CollectionRequest.objects.filter(access_code=code, status="active").first()


def build_collect_prefill_submit_url(
    request,
    *,
    collect_code,
    choice_value,
    contributor_name="",
    contributor_affiliation="",
    source="",
):
    collection_req = get_active_collect_request_by_code(collect_code)
    if not collection_req:
        return ""

    params = {
        "source": str(source or "").strip(),
        "choice": str(choice_value or "").strip(),
        "name": str(contributor_name or "").strip(),
        "affiliation": str(contributor_affiliation or "").strip(),
    }
    params = {key: value for key, value in params.items() if value}

    base_path = reverse("collect:submit", args=[collection_req.id])
    query = urlencode(params)
    absolute = request.build_absolute_uri(base_path)
    return f"{absolute}?{query}" if query else absolute


def submit_bti_result_to_collect(
    *,
    collect_code,
    source,
    choice_value,
    contributor_name="",
    contributor_affiliation="",
    integration_ref="",
):
    collection_req = get_active_collect_request_by_code(collect_code)
    if not collection_req:
        return {"ok": False, "reason": "request_not_found", "created": False}

    source_key = str(source or "").strip().lower()
    if source_key not in {BTI_SOURCE_SSAMBTI, BTI_SOURCE_STUDENTMBTI}:
        return {"ok": False, "reason": "invalid_source", "created": False}

    if not collection_req.allow_choice:
        return {"ok": False, "reason": "choice_not_allowed", "created": False}

    selected = str(choice_value or "").strip()
    if not selected:
        return {"ok": False, "reason": "missing_choice", "created": False}

    options = set(collection_req.normalized_choice_options)
    if selected not in options:
        return {"ok": False, "reason": "choice_not_in_options", "created": False}

    name = str(contributor_name or "").strip() or "익명 참여자"
    affiliation = str(contributor_affiliation or "").strip()
    integration_ref = str(integration_ref or "").strip()

    if integration_ref:
        existing = Submission.objects.filter(
            collection_request=collection_req,
            integration_source=source_key,
            integration_ref=integration_ref,
        ).first()
        if existing:
            changed = False
            if existing.contributor_name != name:
                existing.contributor_name = name
                changed = True
            if existing.contributor_affiliation != affiliation:
                existing.contributor_affiliation = affiliation
                changed = True
            if existing.submission_type != "choice":
                existing.submission_type = "choice"
                changed = True
            if existing.choice_answers != [selected]:
                existing.choice_answers = [selected]
                changed = True
            if existing.choice_other_text != "":
                existing.choice_other_text = ""
                changed = True
            if changed:
                existing.save()
            return {
                "ok": True,
                "reason": "",
                "created": False,
                "submission_id": str(existing.id),
                "request_id": str(collection_req.id),
            }

    created = Submission.objects.create(
        collection_request=collection_req,
        contributor_name=name,
        contributor_affiliation=affiliation,
        submission_type="choice",
        choice_answers=[selected],
        choice_other_text="",
        integration_source=source_key,
        integration_ref=integration_ref,
    )
    return {
        "ok": True,
        "reason": "",
        "created": True,
        "submission_id": str(created.id),
        "request_id": str(collection_req.id),
    }
