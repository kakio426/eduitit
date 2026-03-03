import importlib.util

from django.core.checks import Error, register


@register()
def consent_pdf_runtime_check(app_configs, **kwargs):
    missing = [
        package
        for package in ("reportlab", "pypdf")
        if importlib.util.find_spec(package) is None
    ]
    if not missing:
        return []

    joined = ", ".join(missing)
    return [
        Error(
            f"Consent PDF runtime dependency missing: {joined}",
            hint="`pip install -r requirements.txt`로 reportlab/pypdf를 설치하세요.",
            id="consent.E001",
        )
    ]
