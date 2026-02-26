from django import forms

from .models import (
    ConsultationMethod,
    ConsultationProposal,
    ConsultationRequest,
    ConsultationSlot,
    ParentContact,
    ParentNotice,
    ParentThread,
    ParentThreadMessage,
    ParentUrgentAlert,
)


INPUT_CLASS = (
    "w-full shadow-clay-inner px-4 py-3 rounded-xl bg-[#E0E5EC] "
    "outline-none focus:ring-2 focus:ring-purple-300 text-gray-700"
)
TEXTAREA_CLASS = (
    "w-full shadow-clay-inner px-4 py-3 rounded-xl bg-[#E0E5EC] "
    "outline-none focus:ring-2 focus:ring-purple-300 text-gray-700"
)
SELECT_CLASS = (
    "w-full shadow-clay-inner px-4 py-3 rounded-xl bg-[#E0E5EC] "
    "outline-none focus:ring-2 focus:ring-purple-300 text-gray-700"
)
CHECKBOX_CLASS = "h-4 w-4 rounded border-slate-300 text-purple-600 focus:ring-purple-400"
FILE_CLASS = (
    "w-full text-sm text-slate-700 "
    "file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 "
    "file:px-3 file:py-2 file:text-sm file:font-bold file:text-slate-700 hover:file:bg-slate-200"
)


class ClayFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_clay_classes()

    def _apply_clay_classes(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Textarea):
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {TEXTAREA_CLASS}".strip()
            elif isinstance(widget, (forms.Select, forms.DateTimeInput, forms.DateInput)):
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {SELECT_CLASS}".strip()
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {CHECKBOX_CLASS}".strip()
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {FILE_CLASS}".strip()
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {CHECKBOX_CLASS}".strip()
            else:
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {INPUT_CLASS}".strip()


class ParentContactForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ParentContact
        fields = [
            "student_name",
            "student_grade",
            "student_classroom",
            "parent_name",
            "relationship",
            "contact_email",
            "contact_phone",
        ]
        labels = {
            "student_name": "학생 이름",
            "student_grade": "학년",
            "student_classroom": "반",
            "parent_name": "학부모 이름",
            "relationship": "관계",
            "contact_email": "연락 이메일",
            "contact_phone": "연락처",
        }
        widgets = {
            "student_name": forms.TextInput(attrs={"placeholder": "학생 이름"}),
            "student_grade": forms.NumberInput(attrs={"min": 1, "max": 6, "placeholder": "학년"}),
            "student_classroom": forms.TextInput(attrs={"placeholder": "예: 3-2"}),
            "parent_name": forms.TextInput(attrs={"placeholder": "학부모 이름"}),
            "relationship": forms.TextInput(attrs={"placeholder": "예: 어머니"}),
            "contact_email": forms.EmailInput(attrs={"placeholder": "가입/기록 이메일"}),
            "contact_phone": forms.TextInput(attrs={"placeholder": "연락처"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact_email"].required = False
        self.fields["contact_email"].help_text = "선택 입력입니다. 학부모 가입 없이도 사용 가능합니다."


class ParentContactCsvImportForm(ClayFormMixin, forms.Form):
    csv_file = forms.FileField(
        label="CSV 파일",
        help_text="헤더 예시: student_name,parent_name,contact_phone,contact_email",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )


class ParentContactBulkTextForm(ClayFormMixin, forms.Form):
    bulk_text = forms.CharField(
        label="여러 줄 빠른 등록",
        help_text="한 줄에 한 명씩 입력: 학생이름,학부모이름,연락처,이메일(선택)",
        widget=forms.Textarea(
            attrs={
                "rows": 7,
                "placeholder": "예)\n김민수,김학부모,010-1111-2222,parent1@example.com\n박지우,박학부모,010-3333-4444",
            }
        ),
    )


class ParentNoticeForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ParentNotice
        fields = ["classroom_label", "title", "content", "attachment", "is_pinned"]
        labels = {
            "classroom_label": "학급 표기",
            "title": "제목",
            "content": "내용",
            "attachment": "첨부파일",
            "is_pinned": "상단 고정",
        }
        widgets = {
            "classroom_label": forms.TextInput(attrs={"placeholder": "예: 3-2 바다반"}),
            "title": forms.TextInput(attrs={"placeholder": "알림장 제목"}),
            "content": forms.Textarea(attrs={"rows": 5, "placeholder": "학부모에게 보낼 내용을 입력하세요."}),
            "attachment": forms.ClearableFileInput(),
        }


class ParentThreadCreateForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ParentThread
        fields = ["parent_contact", "subject"]
        labels = {
            "parent_contact": "받는 학부모",
            "subject": "쪽지 제목",
        }
        widgets = {
            "subject": forms.TextInput(attrs={"placeholder": "예: 내일 체험학습 준비 안내"}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop("teacher")
        super().__init__(*args, **kwargs)
        self.fields["parent_contact"].queryset = ParentContact.objects.filter(
            teacher=self.teacher,
            is_active=True,
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.teacher = self.teacher
        obj.category = "소통"
        obj.severity = ParentThread.Severity.NORMAL
        policy = getattr(self.teacher, "parent_comm_policy", None)
        if policy:
            obj.parent_message_limit = policy.max_parent_messages_per_thread
        if commit:
            obj.save()
        return obj


class ParentThreadMessageForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ParentThreadMessage
        fields = ["body"]
        labels = {
            "body": "답장 내용",
        }
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "짧고 분명하게 답장을 남겨 주세요."}),
        }

    def save(self, *, thread, sender_role, commit=True):
        obj = super().save(commit=False)
        obj.thread = thread
        obj.sender_role = sender_role
        if commit:
            obj.save()
        return obj


class ConsultationRequestForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        fields = ["parent_contact", "reason", "escalation_reason"]
        labels = {
            "parent_contact": "상담 대상 학부모",
            "reason": "상담이 필요한 이유",
            "escalation_reason": "교사 메모 (선택)",
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3, "placeholder": "상담이 필요한 배경을 적어 주세요."}),
            "escalation_reason": forms.TextInput(attrs={"placeholder": "예: 출결 관련 반복 문의"}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop("teacher")
        super().__init__(*args, **kwargs)
        self.fields["parent_contact"].queryset = ParentContact.objects.filter(
            teacher=self.teacher,
            is_active=True,
        )

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.teacher = self.teacher
        obj.requested_by = ConsultationRequest.RequestedBy.TEACHER
        if commit:
            obj.save()
        return obj


class ConsultationProposalForm(ClayFormMixin, forms.ModelForm):
    allowed_methods = forms.MultipleChoiceField(
        choices=ConsultationMethod.choices,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="제안할 상담 방법",
    )

    class Meta:
        model = ConsultationProposal
        fields = ["note", "allowed_methods"]
        labels = {
            "note": "안내 메모",
        }
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "학부모에게 보낼 안내 문구"}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop("teacher")
        self.consultation_request = kwargs.pop("consultation_request")
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["allowed_methods"].initial = self.instance.allowed_methods

    def clean_allowed_methods(self):
        methods = self.cleaned_data.get("allowed_methods") or []
        if not methods:
            raise forms.ValidationError("상담 방법은 최소 1개 이상 선택해 주세요.")
        return methods

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.teacher = self.teacher
        obj.consultation_request = self.consultation_request
        obj.allowed_methods = self.cleaned_data["allowed_methods"]
        if commit:
            obj.full_clean()
            obj.save()
            self.consultation_request.status = ConsultationRequest.Status.PROPOSED
            self.consultation_request.save(update_fields=["status", "updated_at"])
        return obj


class ConsultationSlotForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ConsultationSlot
        fields = ["method", "starts_at", "ends_at", "location_note", "channel_hint"]
        labels = {
            "method": "상담 방법",
            "starts_at": "시작 시간",
            "ends_at": "끝나는 시간",
            "location_note": "장소 안내 (방문상담)",
            "channel_hint": "연락 안내 (전화/채팅)",
        }
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "location_note": forms.TextInput(attrs={"placeholder": "예: 본관 2층 상담실"}),
            "channel_hint": forms.TextInput(attrs={"placeholder": "예: 학교 전화로 연락 예정"}),
        }

    def __init__(self, *args, **kwargs):
        self.proposal = kwargs.pop("proposal")
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["method"].choices = [
            (value, label)
            for value, label in ConsultationMethod.choices
            if value in (self.proposal.allowed_methods or [])
        ]

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "끝나는 시간은 시작 시간보다 늦어야 합니다.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.proposal = self.proposal
        if commit:
            obj.full_clean()
            obj.save()
            request = self.proposal.consultation_request
            if request.status != ConsultationRequest.Status.AWAITING_PARENT:
                request.status = ConsultationRequest.Status.AWAITING_PARENT
                request.save(update_fields=["status", "updated_at"])
        return obj


class ParentUrgentAlertForm(ClayFormMixin, forms.ModelForm):
    class Meta:
        model = ParentUrgentAlert
        fields = ["alert_type", "short_message"]
        labels = {
            "alert_type": "긴급 유형",
            "short_message": "긴급 안내 문장 (20자)",
        }
        widgets = {
            "short_message": forms.TextInput(
                attrs={
                    "maxlength": "20",
                    "placeholder": "예: 병원 들렀다가 3교시 등교",
                }
            )
        }

    def clean_short_message(self):
        value = (self.cleaned_data.get("short_message") or "").strip()
        if not value:
            raise forms.ValidationError("긴급 안내 메시지를 입력해 주세요.")
        if len(value) > 20:
            raise forms.ValidationError("긴급 안내는 20자 이내만 가능합니다.")
        return value
