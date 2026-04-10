from __future__ import annotations

from pathlib import Path

from django import forms

from .models import (
    InquiryProposal,
    InquiryReview,
    LISTING_ATTACHMENT_ALLOWED_EXTENSIONS,
    LISTING_ATTACHMENT_MAX_FILE_BYTES,
    LISTING_ATTACHMENT_MAX_FILES,
    ProgramListing,
    ProviderProfile,
)


def _normalize_csv_text(value: str) -> str:
    parts = []
    for raw_part in str(value or "").replace("\n", ",").split(","):
        part = raw_part.strip().lstrip("#")
        if part and part not in parts:
            parts.append(part)
    return ", ".join(parts)


TEXT_INPUT_CLASS = "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700"
TEXTAREA_CLASS = "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700"
SELECT_CLASS = "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700"


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [single_file_clean(item, initial) for item in data]


def validate_listing_attachment_files(files):
    cleaned_files = list(files or [])
    errors = []
    allowed_extensions_text = ", ".join(sorted(LISTING_ATTACHMENT_ALLOWED_EXTENSIONS))

    if len(cleaned_files) > LISTING_ATTACHMENT_MAX_FILES:
        errors.append(f"첨부 자료는 한 번에 최대 {LISTING_ATTACHMENT_MAX_FILES}개까지 올릴 수 있습니다.")
        return cleaned_files, errors

    for file_obj in cleaned_files:
        ext = Path(getattr(file_obj, "name", "") or "").suffix.lower()
        if ext not in LISTING_ATTACHMENT_ALLOWED_EXTENSIONS:
            errors.append(f"첨부 자료는 {allowed_extensions_text} 형식만 올릴 수 있습니다.")
            break
        if int(getattr(file_obj, "size", 0) or 0) > LISTING_ATTACHMENT_MAX_FILE_BYTES:
            max_size_mb = LISTING_ATTACHMENT_MAX_FILE_BYTES // (1024 * 1024)
            errors.append(f"첨부 자료는 파일당 최대 {max_size_mb}MB까지 올릴 수 있습니다.")
            break

    return cleaned_files, errors


class ProviderProfileForm(forms.ModelForm):
    def __init__(self, *args, service_area_list_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = TEXTAREA_CLASS
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs["class"] = TEXT_INPUT_CLASS
            else:
                field.widget.attrs["class"] = TEXT_INPUT_CLASS
        if service_area_list_id:
            self.fields["service_area_summary"].widget.attrs["list"] = service_area_list_id

    class Meta:
        model = ProviderProfile
        fields = [
            "provider_name",
            "summary",
            "description",
            "contact_email",
            "contact_phone",
            "website",
            "service_area_summary",
            "verification_document",
        ]
        widgets = {
            "summary": forms.TextInput(attrs={"placeholder": "예) 초등 체험형 환경 수업 전문"}),
            "description": forms.Textarea(attrs={"rows": 5}),
        }


class ProgramListingForm(forms.ModelForm):
    grade_bands = forms.MultipleChoiceField(
        label="대상 학년",
        choices=ProgramListing.GRADE_BAND_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    attachments = MultipleFileField(
        required=False,
        label="상세 안내자료",
        widget=MultipleFileInput,
    )

    class Meta:
        model = ProgramListing
        fields = [
            "title",
            "category",
            "summary",
            "description",
            "theme_tags_text",
            "grade_bands",
            "delivery_mode",
            "province",
            "city",
            "coverage_note",
            "duration_text",
            "capacity_text",
            "price_text",
            "safety_info",
            "materials_info",
            "faq",
        ]
        widgets = {
            "summary": forms.TextInput(attrs={"placeholder": "예) 학교로 직접 찾아가 90분 안에 끝나는 과학 체험"}),
            "description": forms.Textarea(attrs={"rows": 6}),
            "theme_tags_text": forms.TextInput(attrs={"placeholder": "예) 환경, 과학, 생태, 협동"}),
            "city": forms.TextInput(attrs={"placeholder": "예) 수원, 강서구, 해운대구"}),
            "coverage_note": forms.TextInput(attrs={"placeholder": "예) 용인·성남·분당까지 방문 가능"}),
            "safety_info": forms.Textarea(attrs={"rows": 4}),
            "materials_info": forms.Textarea(attrs={"rows": 4}),
            "faq": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, region_list_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["grade_bands"].initial = self.instance.grade_bands
        if self.instance.pk and not self.initial.get("theme_tags_text"):
            self.initial["theme_tags_text"] = self.instance.theme_tags_text
        for name, field in self.fields.items():
            if name == "grade_bands":
                continue
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = TEXTAREA_CLASS
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = SELECT_CLASS
            else:
                field.widget.attrs["class"] = TEXT_INPUT_CLASS
        if region_list_id:
            self.fields["city"].widget.attrs["list"] = region_list_id
        self.fields["attachments"].widget.attrs["accept"] = ",".join(sorted(LISTING_ATTACHMENT_ALLOWED_EXTENSIONS))

    def clean_theme_tags_text(self):
        return _normalize_csv_text(self.cleaned_data.get("theme_tags_text", ""))

    def clean_attachments(self):
        attachments, errors = validate_listing_attachment_files(self.cleaned_data.get("attachments"))
        if errors:
            raise forms.ValidationError(errors)
        return attachments

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.grade_bands = self.cleaned_data["grade_bands"]
        instance.theme_tags = [item.strip() for item in self.cleaned_data["theme_tags_text"].split(",") if item.strip()]
        if commit:
            instance.save()
        return instance

    @property
    def attachment_limits(self):
        return {
            "max_files": LISTING_ATTACHMENT_MAX_FILES,
            "max_file_bytes": LISTING_ATTACHMENT_MAX_FILE_BYTES,
            "max_file_mb": LISTING_ATTACHMENT_MAX_FILE_BYTES // (1024 * 1024),
            "allowed_extensions": sorted(LISTING_ATTACHMENT_ALLOWED_EXTENSIONS),
        }


class InquiryCreateForm(forms.Form):
    school_region = forms.CharField(label="학교 지역", max_length=80)
    preferred_schedule = forms.CharField(label="희망 시기", max_length=120)
    target_audience = forms.CharField(label="대상", max_length=120)
    expected_participants = forms.IntegerField(label="예상 인원", min_value=1)
    budget_text = forms.CharField(label="예산", max_length=120, required=False)
    request_message = forms.CharField(
        label="요청 내용",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["school_region"].widget.attrs.update({"class": TEXT_INPUT_CLASS, "placeholder": "예) 경기 수원"})
        self.fields["preferred_schedule"].widget.attrs.update({"class": TEXT_INPUT_CLASS, "placeholder": "예) 5월 둘째 주 오전"})
        self.fields["target_audience"].widget.attrs.update({"class": TEXT_INPUT_CLASS, "placeholder": "예) 초등 4학년 5개 반"})
        self.fields["expected_participants"].widget.attrs.update({"class": TEXT_INPUT_CLASS, "placeholder": "예) 120"})
        self.fields["budget_text"].widget.attrs.update({"class": TEXT_INPUT_CLASS, "placeholder": "예) 학급당 35만원 또는 추후 협의"})
        self.fields["request_message"].widget.attrs.update(
            {
                "class": TEXTAREA_CLASS,
                "placeholder": "학교 일정이나 공간 조건, 꼭 확인하고 싶은 점을 적어 주세요.",
            }
        )


class InquiryMessageForm(forms.Form):
    body = forms.CharField(
        label="메시지",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs.update(
            {
                "class": TEXTAREA_CLASS,
                "placeholder": "필요한 조건이나 추가 질문을 짧게 남겨 주세요.",
            }
        )


class InquiryProposalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = TEXTAREA_CLASS
            else:
                field.widget.attrs["class"] = TEXT_INPUT_CLASS

    class Meta:
        model = InquiryProposal
        fields = [
            "price_text",
            "included_items",
            "schedule_note",
            "preparation_note",
            "followup_request",
        ]
        widgets = {
            "included_items": forms.Textarea(attrs={"rows": 3}),
            "schedule_note": forms.Textarea(attrs={"rows": 3}),
            "preparation_note": forms.Textarea(attrs={"rows": 3}),
            "followup_request": forms.Textarea(attrs={"rows": 3}),
        }


class InquiryReviewForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = TEXTAREA_CLASS
            else:
                field.widget.attrs["class"] = TEXT_INPUT_CLASS

    class Meta:
        model = InquiryReview
        fields = [
            "headline",
            "body",
            "recommended_for",
        ]
        widgets = {
            "headline": forms.TextInput(attrs={"placeholder": "예) 준비가 잘 되어 있어서 교실 진행이 매끄러웠어요"}),
            "body": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "실제 진행 분위기, 시간 운영, 학생 반응, 현장 대응에서 좋았던 점을 적어 주세요.",
                }
            ),
            "recommended_for": forms.TextInput(
                attrs={"placeholder": "예) 학년 행사, 강당 진행, 3개 반 이상 동시 운영"}
            ),
        }
