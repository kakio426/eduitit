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


class ParentContactForm(forms.ModelForm):
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
        widgets = {
            "student_name": forms.TextInput(attrs={"placeholder": "학생 이름"}),
            "student_grade": forms.NumberInput(attrs={"min": 1, "max": 6}),
            "student_classroom": forms.TextInput(attrs={"placeholder": "예: 3-2"}),
            "parent_name": forms.TextInput(attrs={"placeholder": "학부모 이름"}),
            "relationship": forms.TextInput(attrs={"placeholder": "예: 어머니"}),
            "contact_email": forms.EmailInput(attrs={"placeholder": "연락용 이메일"}),
            "contact_phone": forms.TextInput(attrs={"placeholder": "연락처"}),
        }


class ParentNoticeForm(forms.ModelForm):
    class Meta:
        model = ParentNotice
        fields = ["classroom_label", "title", "content", "is_pinned"]
        widgets = {
            "classroom_label": forms.TextInput(attrs={"placeholder": "예: 3-2 바다반"}),
            "title": forms.TextInput(attrs={"placeholder": "알림장 제목"}),
            "content": forms.Textarea(attrs={"rows": 4, "placeholder": "학부모 공지 내용을 입력하세요."}),
        }


class ParentThreadCreateForm(forms.ModelForm):
    class Meta:
        model = ParentThread
        fields = ["parent_contact", "subject", "category", "severity"]
        widgets = {
            "subject": forms.TextInput(attrs={"placeholder": "문의 주제"}),
            "category": forms.TextInput(attrs={"placeholder": "예: 생활/출결/상담"}),
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
        policy = getattr(self.teacher, "parent_comm_policy", None)
        if policy:
            obj.parent_message_limit = policy.max_parent_messages_per_thread
        if commit:
            obj.save()
        return obj


class ParentThreadMessageForm(forms.ModelForm):
    class Meta:
        model = ParentThreadMessage
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "답변 내용을 입력하세요."}),
        }

    def save(self, *, thread, sender_role, commit=True):
        obj = super().save(commit=False)
        obj.thread = thread
        obj.sender_role = sender_role
        if commit:
            obj.save()
        return obj


class ConsultationRequestForm(forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        fields = ["parent_contact", "reason", "escalation_reason"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3, "placeholder": "상담이 필요한 배경을 입력하세요."}),
            "escalation_reason": forms.TextInput(attrs={"placeholder": "예: 반복 문의 한도 초과"}),
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


class ConsultationProposalForm(forms.ModelForm):
    allowed_methods = forms.MultipleChoiceField(
        choices=ConsultationMethod.choices,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="제안 가능한 상담 방식",
    )

    class Meta:
        model = ConsultationProposal
        fields = ["note", "allowed_methods"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "학부모에게 전달할 안내"}),
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
            raise forms.ValidationError("상담 방식은 최소 1개 이상 선택해 주세요.")
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


class ConsultationSlotForm(forms.ModelForm):
    class Meta:
        model = ConsultationSlot
        fields = ["method", "starts_at", "ends_at", "location_note", "channel_hint"]
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local"},
            ),
            "location_note": forms.TextInput(attrs={"placeholder": "방문상담 장소 안내"}),
            "channel_hint": forms.TextInput(attrs={"placeholder": "전화번호/채팅방 안내"}),
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
            self.add_error("ends_at", "종료 시간은 시작 시간보다 늦어야 합니다.")
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


class ParentUrgentAlertForm(forms.ModelForm):
    class Meta:
        model = ParentUrgentAlert
        fields = ["alert_type", "short_message"]
        widgets = {
            "short_message": forms.TextInput(
                attrs={
                    "maxlength": "20",
                    "placeholder": "20자 이내로 입력",
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
