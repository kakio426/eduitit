from django import forms

from .models import SignatureDocument, SignatureRequest


class ConsentDocumentForm(forms.ModelForm):
    class Meta:
        model = SignatureDocument
        fields = ["title", "original_file"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                    "placeholder": "동의서 제목",
                }
            ),
            "original_file": forms.FileInput(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
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
        fields = ["title", "message", "legal_notice", "consent_text_version"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                    "placeholder": "예: 1학기 체험학습 동의서",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                    "rows": 3,
                    "placeholder": "학부모에게 보낼 안내 메시지",
                }
            ),
            "legal_notice": forms.Textarea(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                    "rows": 4,
                    "placeholder": "법적/개인정보 고지 전문",
                }
            ),
            "consent_text_version": forms.TextInput(
                attrs={
                    "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                    "placeholder": "v1",
                }
            ),
        }


class PositionPayloadForm(forms.Form):
    positions_json = forms.CharField(widget=forms.HiddenInput)


class RecipientBulkForm(forms.Form):
    recipients_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "w-full rounded-xl border border-gray-300 px-3 py-2 font-mono text-sm",
                "rows": 8,
                "placeholder": "학생명,학부모명,전화번호\n홍길동,홍길순,010-1234-5678",
            }
        )
    )


class VerifyIdentityForm(forms.Form):
    parent_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "w-full rounded-xl border border-gray-300 px-3 py-2"}),
    )
    phone_last4 = forms.CharField(
        min_length=4,
        max_length=4,
        widget=forms.TextInput(attrs={"class": "w-full rounded-xl border border-gray-300 px-3 py-2", "inputmode": "numeric"}),
    )

    def clean_phone_last4(self):
        value = self.cleaned_data["phone_last4"]
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
                "class": "w-full rounded-xl border border-gray-300 px-3 py-2",
                "rows": 3,
                "placeholder": "비동의 사유(선택)",
            }
        ),
    )
    signature_data = forms.CharField(widget=forms.HiddenInput)

    def clean_signature_data(self):
        value = (self.cleaned_data.get("signature_data") or "").strip()
        if not value.startswith("data:image"):
            raise forms.ValidationError("자필 서명을 입력해 주세요.")
        return value
