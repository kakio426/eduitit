from django import forms

from .models import TextbookDocument


class TextbookDocumentUploadForm(forms.ModelForm):
    license_confirmed = forms.BooleanField(
        required=True,
        label="사용 허가를 확인했습니다",
        error_messages={"required": "PDF 사용 허가를 확인해 주세요."},
    )

    class Meta:
        model = TextbookDocument
        fields = ["title", "subject", "grade", "unit_title", "source_pdf", "license_confirmed"]
        labels = {
            "title": "자료 제목",
            "subject": "과목",
            "grade": "학년/학기",
            "unit_title": "단원",
            "source_pdf": "PDF 파일",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "textbook-ai-input", "placeholder": "예: 5학년 과학 2단원 PDF"}),
            "subject": forms.Select(attrs={"class": "textbook-ai-input"}),
            "grade": forms.TextInput(attrs={"class": "textbook-ai-input", "placeholder": "예: 5학년 1학기"}),
            "unit_title": forms.TextInput(attrs={"class": "textbook-ai-input", "placeholder": "예: 생물과 환경"}),
            "source_pdf": forms.ClearableFileInput(attrs={"class": "textbook-ai-input", "accept": "application/pdf,.pdf"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license_confirmed"].widget.attrs.update({"class": "mt-1 h-4 w-4 rounded border-slate-300"})

    def clean_title(self):
        title = str(self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("자료 제목을 입력해 주세요.")
        return title

    def clean_unit_title(self):
        return str(self.cleaned_data.get("unit_title") or "").strip()

    def clean_grade(self):
        return str(self.cleaned_data.get("grade") or "").strip()
