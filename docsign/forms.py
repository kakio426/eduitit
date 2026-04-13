from __future__ import annotations

import json

from django import forms

from core.document_signing import clean_signature_data_url, guess_file_type


CLAY_INPUT = (
    "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 "
    "text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-200"
)


class DocumentSignUploadForm(forms.Form):
    title = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "문서 이름",
            }
        ),
    )
    source_file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                "class": CLAY_INPUT,
                "accept": ".pdf,application/pdf",
            }
        )
    )

    def clean_source_file(self):
        file_obj = self.cleaned_data["source_file"]
        if guess_file_type(file_obj.name) != "pdf":
            raise forms.ValidationError("PDF만 올릴 수 있습니다.")
        return file_obj


class DocumentSignPositionForm(forms.Form):
    position_json = forms.CharField(widget=forms.HiddenInput)

    def clean_position_json(self):
        raw_value = (self.cleaned_data.get("position_json") or "").strip()
        if not raw_value:
            raise forms.ValidationError("사인 위치를 먼저 잡아 주세요.")
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("사인 위치를 다시 저장해 주세요.") from exc

        if not isinstance(payload, dict):
            raise forms.ValidationError("사인 위치를 다시 저장해 주세요.")

        try:
            page = int(payload.get("page", 0))
            x_ratio = float(payload.get("x_ratio"))
            y_ratio = float(payload.get("y_ratio"))
            w_ratio = float(payload.get("w_ratio"))
            h_ratio = float(payload.get("h_ratio"))
        except (TypeError, ValueError) as exc:
            raise forms.ValidationError("사인 위치 값이 올바르지 않습니다.") from exc

        if page < 1:
            raise forms.ValidationError("사인 페이지를 다시 선택해 주세요.")

        for key, value, lower, upper in (
            ("x_ratio", x_ratio, 0.0, 1.0),
            ("y_ratio", y_ratio, 0.0, 1.0),
            ("w_ratio", w_ratio, 0.05, 1.0),
            ("h_ratio", h_ratio, 0.03, 1.0),
        ):
            if not (lower <= value <= upper):
                raise forms.ValidationError(f"{key} 값이 범위를 벗어났습니다.")

        return {
            "page": page,
            "x_ratio": x_ratio,
            "y_ratio": y_ratio,
            "w_ratio": w_ratio,
            "h_ratio": h_ratio,
        }


class DocumentSignSignatureForm(forms.Form):
    signature_data = forms.CharField(widget=forms.HiddenInput)

    def clean_signature_data(self):
        value = self.cleaned_data.get("signature_data")
        try:
            return clean_signature_data_url(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
