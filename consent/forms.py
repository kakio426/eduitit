import json

from django import forms

from core.document_signing import clean_signature_data_url
from handoff.models import HandoffRosterGroup

from .models import ConsentRoster, SignatureDocument, SignaturePosition, SignatureRequest


CLAY_INPUT = (
    "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft "
    "focus:outline-none focus:ring-2 focus:ring-purple-300"
)


class ConsentDocumentForm(forms.ModelForm):
    class Meta:
        model = SignatureDocument
        fields = ["title", "original_file"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": CLAY_INPUT,
                    "placeholder": "예: 1학기 체험학습 가정통신문",
                }
            ),
            "original_file": forms.FileInput(
                attrs={
                    "class": CLAY_INPUT,
                    "accept": ".pdf,.png,.jpg,.jpeg",
                }
            ),
        }

    def clean_original_file(self):
        file_obj = self.cleaned_data["original_file"]
        name = (file_obj.name or "").lower()
        allowed = (".pdf", ".png", ".jpg", ".jpeg")
        if not name.endswith(allowed):
            raise forms.ValidationError("PDF 또는 이미지(PNG/JPG)만 업로드할 수 있습니다.")
        return file_obj


class ConsentRequestForm(forms.ModelForm):
    class Meta:
        model = SignatureRequest
        fields = ["audience_type", "title", "message", "link_expire_days", "legal_notice"]
        widgets = {
            "audience_type": forms.HiddenInput(),
            "title": forms.TextInput(
                attrs={
                    "class": CLAY_INPUT,
                    "placeholder": "예: 1학기 현장체험학습 동의서",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": f"{CLAY_INPUT} resize-none",
                    "rows": 3,
                    "placeholder": "학부모에게 전달할 안내 메시지를 입력하세요.",
                }
            ),
            "link_expire_days": forms.Select(
                attrs={
                    "class": CLAY_INPUT,
                }
            ),
            "legal_notice": forms.Textarea(
                attrs={
                    "class": f"{CLAY_INPUT} resize-none",
                    "rows": 5,
                    "placeholder": "선택 입력 (비워두면 기본 고지문이 자동 적용됩니다.)",
                }
            ),
        }


class PositionPayloadForm(forms.Form):
    marks_json = forms.CharField(widget=forms.HiddenInput)

    def clean_marks_json(self):
        raw_value = (self.cleaned_data.get("marks_json") or "").strip()
        if not raw_value:
            raise forms.ValidationError("표시를 먼저 놓아 주세요.")

        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("표시 위치를 다시 저장해 주세요.") from exc

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list) or not payload:
            raise forms.ValidationError("표시를 하나 이상 놓아 주세요.")

        cleaned = []
        for item in payload:
            if not isinstance(item, dict):
                raise forms.ValidationError("표시 위치를 다시 저장해 주세요.")
            try:
                page = int(item.get("page", 0))
                x_ratio = float(item.get("x_ratio"))
                y_ratio = float(item.get("y_ratio"))
                w_ratio = float(item.get("w_ratio"))
                h_ratio = float(item.get("h_ratio"))
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError("표시 위치 값이 올바르지 않습니다.") from exc

            mark_type = str(item.get("mark_type") or SignaturePosition.MARK_TYPE_SIGNATURE).strip().lower()
            text_source = str(
                item.get("text_source") or SignaturePosition.TEXT_SOURCE_SIGNER_NAME
            ).strip().lower()
            check_rule = str(
                item.get("check_rule") or SignaturePosition.CHECK_RULE_AGREE
            ).strip().lower()

            if page < 1:
                raise forms.ValidationError("표시 페이지를 다시 선택해 주세요.")
            if mark_type not in {
                SignaturePosition.MARK_TYPE_SIGNATURE,
                SignaturePosition.MARK_TYPE_CHECKMARK,
                SignaturePosition.MARK_TYPE_NAME,
            }:
                raise forms.ValidationError("표시 종류를 다시 선택해 주세요.")
            if text_source not in {
                SignaturePosition.TEXT_SOURCE_STUDENT_NAME,
                SignaturePosition.TEXT_SOURCE_SIGNER_NAME,
            }:
                raise forms.ValidationError("이름 표시 대상을 다시 선택해 주세요.")
            if check_rule not in {
                SignaturePosition.CHECK_RULE_ALWAYS,
                SignaturePosition.CHECK_RULE_AGREE,
                SignaturePosition.CHECK_RULE_DISAGREE,
            }:
                raise forms.ValidationError("체크 표시 조건을 다시 선택해 주세요.")

            for key, value, lower, upper in (
                ("x_ratio", x_ratio, 0.0, 1.0),
                ("y_ratio", y_ratio, 0.0, 1.0),
                ("w_ratio", w_ratio, 0.05, 1.0),
                ("h_ratio", h_ratio, 0.03, 1.0),
            ):
                if not (lower <= value <= upper):
                    raise forms.ValidationError(f"{key} 값이 범위를 벗어났습니다.")

            cleaned.append(
                {
                    "page": page,
                    "x_ratio": x_ratio,
                    "y_ratio": y_ratio,
                    "w_ratio": w_ratio,
                    "h_ratio": h_ratio,
                    "mark_type": mark_type,
                    "text_source": text_source,
                    "check_rule": check_rule,
                }
            )

        return cleaned


class RecipientBulkForm(forms.Form):
    shared_roster_group = forms.ModelChoiceField(
        required=False,
        queryset=HandoffRosterGroup.objects.none(),
        empty_label="선택 안 함",
        label="공용 명부 불러오기",
        widget=forms.Select(
            attrs={
                "class": CLAY_INPUT,
            }
        ),
    )
    recipients_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": f"{CLAY_INPUT} font-mono text-sm resize-none",
                "rows": 8,
                "placeholder": "",
            }
        )
    )
    recipients_csv = forms.FileField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": CLAY_INPUT,
                "accept": ".csv,text/csv",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop("owner", None)
        audience_type = kwargs.pop("audience_type", SignatureRequest.AUDIENCE_GUARDIAN)
        super().__init__(*args, **kwargs)
        self.audience_type = audience_type
        if owner is not None:
            self.fields["shared_roster_group"].queryset = HandoffRosterGroup.objects.filter(owner=owner).order_by(
                "-is_favorite",
                "name",
            )
        self.fields["shared_roster_group"].label_from_instance = lambda roster: roster.name
        if audience_type == SignatureRequest.AUDIENCE_GENERAL:
            self.fields["recipients_text"].widget.attrs["placeholder"] = "이름\n김민수\n박교사"
        else:
            self.fields["recipients_text"].widget.attrs["placeholder"] = (
                "학생명,학부모명(선택),연락처 뒤 4자리\n김하늘,,5678\n박나래,박나래 보호자,1234"
            )

    def clean(self):
        cleaned_data = super().clean()
        text = (cleaned_data.get("recipients_text") or "").strip()
        csv_file = cleaned_data.get("recipients_csv")
        shared_roster_group = cleaned_data.get("shared_roster_group")

        if not text and not csv_file and not shared_roster_group:
            raise forms.ValidationError("공용 명부 선택, 직접 입력, CSV 업로드 중 하나를 선택해 주세요.")

        if csv_file and not (csv_file.name or "").lower().endswith(".csv"):
            raise forms.ValidationError("CSV 파일(.csv)만 업로드할 수 있습니다.")

        return cleaned_data


class ConsentRosterManageForm(forms.Form):
    roster_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
    audience_type = forms.ChoiceField(
        choices=SignatureRequest.AUDIENCE_CHOICES,
        widget=forms.HiddenInput(),
    )
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "예: 3학년 2반 학부모 명단",
            }
        ),
    )
    description = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "필요할 때만 적는 짧은 메모",
            }
        ),
    )
    entries_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": f"{CLAY_INPUT} font-mono text-sm resize-none",
                "rows": 10,
                "placeholder": "",
            }
        ),
    )
    entries_csv = forms.FileField(
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": CLAY_INPUT,
                "accept": ".csv,text/csv",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        audience_type = kwargs.pop("audience_type", SignatureRequest.AUDIENCE_GUARDIAN)
        super().__init__(*args, **kwargs)
        self.fields["audience_type"].initial = audience_type
        if audience_type == SignatureRequest.AUDIENCE_GENERAL:
            self.fields["name"].widget.attrs["placeholder"] = "예: 2026 교직원 사인 명단"
            self.fields["entries_text"].widget.attrs["placeholder"] = "이름\n김민수\n박교사"
        else:
            self.fields["entries_text"].widget.attrs["placeholder"] = (
                "학생명,학부모명(선택),연락처 뒤 4자리\n김하늘,,5678\n박나래,박나래 보호자,1234"
            )

    def clean(self):
        cleaned_data = super().clean()
        text = (cleaned_data.get("entries_text") or "").strip()
        csv_file = cleaned_data.get("entries_csv")
        if not text and not csv_file:
            raise forms.ValidationError("직접 입력이나 CSV 업로드 중 하나는 꼭 넣어 주세요.")
        if csv_file and not (csv_file.name or "").lower().endswith(".csv"):
            raise forms.ValidationError("CSV 파일(.csv)만 업로드할 수 있습니다.")
        return cleaned_data


class SharedLookupForm(forms.Form):
    student_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "학생 이름",
            }
        ),
    )
    phone_last4 = forms.CharField(
        min_length=4,
        max_length=4,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "inputmode": "numeric",
                "maxlength": "4",
                "placeholder": "전화번호 끝 4자리",
            }
        ),
    )

    def clean_student_name(self):
        return (self.cleaned_data.get("student_name") or "").strip()

    def clean_phone_last4(self):
        value = (self.cleaned_data.get("phone_last4") or "").strip()
        if not value.isdigit():
            raise forms.ValidationError("숫자 4자리를 입력해 주세요.")
        return value


class ConsentSignForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[("agree", "동의"), ("disagree", "비동의")],
        widget=forms.RadioSelect,
    )
    decline_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": f"{CLAY_INPUT} resize-none",
                "rows": 3,
                "placeholder": "비동의 사유(선택)",
            }
        ),
    )
    phone_last4 = forms.CharField(
        required=False,
        min_length=4,
        max_length=4,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "inputmode": "numeric",
                "maxlength": "4",
                "placeholder": "전화번호 끝 4자리",
            }
        ),
    )
    signer_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "학부모 이름",
                "autocomplete": "name",
            }
        ),
    )
    signature_data = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.requires_signature = bool(kwargs.pop("requires_signature", True))
        self.requires_signer_name = bool(kwargs.pop("requires_signer_name", False))
        super().__init__(*args, **kwargs)

    def clean_phone_last4(self):
        value = (self.cleaned_data.get("phone_last4") or "").strip()
        if value and not value.isdigit():
            raise forms.ValidationError("숫자 4자리를 입력해 주세요.")
        return value

    def clean_signer_name(self):
        value = (self.cleaned_data.get("signer_name") or "").strip()
        if self.requires_signer_name and not value:
            raise forms.ValidationError("이름을 확인해 주세요.")
        return value

    def clean_signature_data(self):
        value = self.cleaned_data.get("signature_data")
        if not self.requires_signature:
            return ""
        try:
            return clean_signature_data_url(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
