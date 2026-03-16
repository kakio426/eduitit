from django import forms

from .models import ConsentRoster, SignatureDocument, SignatureRequest


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
    positions_json = forms.CharField(widget=forms.HiddenInput)


class RecipientBulkForm(forms.Form):
    saved_roster = forms.ModelChoiceField(
        required=False,
        queryset=ConsentRoster.objects.none(),
        empty_label="선택 안 함",
        label="저장 명단 불러오기",
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
            self.fields["saved_roster"].queryset = ConsentRoster.objects.filter(
                owner=owner,
                audience_type=audience_type,
            ).order_by(
                "-is_favorite",
                "name",
            )
        self.fields["saved_roster"].label_from_instance = lambda roster: roster.name
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
        saved_roster = cleaned_data.get("saved_roster")

        if not text and not csv_file and not saved_roster:
            raise forms.ValidationError("저장 명단 선택, 직접 입력, CSV 업로드 중 하나를 선택해 주세요.")

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
    signature_data = forms.CharField(widget=forms.HiddenInput)

    def clean_phone_last4(self):
        value = (self.cleaned_data.get("phone_last4") or "").strip()
        if value and not value.isdigit():
            raise forms.ValidationError("숫자 4자리를 입력해 주세요.")
        return value

    def clean_signature_data(self):
        value = (self.cleaned_data.get("signature_data") or "").strip()
        if not value.startswith("data:image"):
            raise forms.ValidationError("서명을 입력해 주세요.")
        return value
