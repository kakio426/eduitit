from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model

from handoff.models import HandoffRosterGroup

from .models import (
    SIGNATURE_ATTACHMENT_ALLOWED_EXTENSIONS,
    SIGNATURE_ATTACHMENT_MAX_FILES,
    SIGNATURE_ATTACHMENT_MAX_TOTAL_BYTES,
    Signature,
    TrainingSession,
)


User = get_user_model()


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


def validate_training_session_attachment_files(files):
    cleaned_files = list(files or [])
    errors = []
    allowed_extensions_text = ", ".join(sorted(SIGNATURE_ATTACHMENT_ALLOWED_EXTENSIONS))
    for file_obj in cleaned_files:
        ext = Path(getattr(file_obj, "name", "") or "").suffix.lower()
        if ext not in SIGNATURE_ATTACHMENT_ALLOWED_EXTENSIONS:
            errors.append(f"첨부 파일은 {allowed_extensions_text} 형식만 올릴 수 있습니다.")
            break
    return cleaned_files, errors


class TrainingSessionForm(forms.ModelForm):
    """연수 생성/수정 폼"""

    attachments = MultipleFileField(
        required=False,
        label="서명 전에 볼 파일",
        widget=MultipleFileInput(
            attrs={
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300",
                "accept": ",".join(sorted(SIGNATURE_ATTACHMENT_ALLOWED_EXTENSIONS)),
            }
        ),
    )

    acting_for_user = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.none(),
        empty_label="내 요청으로 만들기",
        label="요청을 맡길 교사",
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )
    proxy_participants_text = forms.CharField(
        required=False,
        label="교사가 보낸 명단",
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300 resize-y",
                "rows": 5,
                "placeholder": "예: 김교사, 1-1\n이교사, 1-2",
            }
        ),
    )
    shared_roster_group = forms.ModelChoiceField(
        required=False,
        queryset=HandoffRosterGroup.objects.none(),
        empty_label="선택 안 함",
        label="공유 명단",
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        owner = kwargs.pop("owner", None)
        can_delegate = kwargs.pop("can_delegate", False)
        delegate_user = kwargs.pop("delegate_user", None)
        super().__init__(*args, **kwargs)
        if owner is None and self.instance and self.instance.pk:
            owner = self.instance.created_by
        if owner is not None:
            self.fields["shared_roster_group"].queryset = HandoffRosterGroup.objects.filter(owner=owner).order_by(
                "-is_favorite",
                "name",
            )
        self.fields["shared_roster_group"].label_from_instance = lambda group: group.name
        if can_delegate:
            delegate_queryset = (
                User.objects.filter(is_active=True)
                .exclude(is_staff=True)
                .exclude(is_superuser=True)
                .select_related("userprofile")
                .order_by("userprofile__nickname", "username")
                .distinct()
            )
            if delegate_user is not None:
                delegate_queryset = delegate_queryset.exclude(pk=delegate_user.pk)
            self.fields["acting_for_user"].queryset = delegate_queryset
            self.fields["acting_for_user"].label_from_instance = self._delegate_user_label
        else:
            self.fields.pop("acting_for_user", None)
            self.fields.pop("proxy_participants_text", None)

    @staticmethod
    def _delegate_user_label(user):
        try:
            profile = user.userprofile
        except Exception:
            profile = None
        nickname = str(getattr(profile, "nickname", "") or "").strip()
        role = profile.get_role_display() if profile and getattr(profile, "role", None) else ""
        base = nickname or user.username
        if nickname and nickname != user.username:
            base = f"{nickname} ({user.username})"
        if role:
            return f"{base} - {role}"
        return base

    class Meta:
        model = TrainingSession
        fields = ['title', 'print_title', 'instructor', 'datetime', 'location', 'description', 'shared_roster_group', 'expected_count', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 2026 AI 수업 설계 직무연수',
            }),
            'print_title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 2026 상반기 교원 직무연수',
            }),
            'instructor': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 홍길동',
            }),
            'datetime': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'type': 'datetime-local',
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 시청각실',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300 resize-none',
                'rows': 3,
                'placeholder': '연수에 대한 추가 설명 (선택사항)',
            }),
            'expected_count': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 50',
                'min': '1',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded shadow-clay-inner accent-purple-500',
            }),
        }

    @property
    def attachment_limits(self):
        return {
            "max_files": SIGNATURE_ATTACHMENT_MAX_FILES,
            "max_total_bytes": SIGNATURE_ATTACHMENT_MAX_TOTAL_BYTES,
            "max_total_mb": SIGNATURE_ATTACHMENT_MAX_TOTAL_BYTES // (1024 * 1024),
        }


class SignatureForm(forms.ModelForm):
    """서명 입력 폼"""

    expected_participant_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    access_code = forms.CharField(
        required=False,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-4 text-xl tracking-[0.35em] rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-amber-300 text-center",
                "placeholder": "예: 4721",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "maxlength": "6",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        use_roster_selection = kwargs.pop("use_roster_selection", False)
        use_access_code = kwargs.pop("use_access_code", False)
        super().__init__(*args, **kwargs)
        if use_roster_selection:
            self.fields["participant_name"].required = False
            self.fields["participant_name"].widget.attrs["placeholder"] = "명단에 없으면 직접 입력하세요"
            self.fields["participant_affiliation"].widget.attrs["placeholder"] = "이름을 고르면 자동으로 채워집니다"
        if use_access_code:
            self.fields["access_code"].required = True

    def clean(self):
        cleaned_data = super().clean()
        expected_participant_id = cleaned_data.get("expected_participant_id")
        participant_name = str(cleaned_data.get("participant_name") or "").strip()
        if not expected_participant_id and not participant_name:
            self.add_error("participant_name", "이름을 선택하거나 직접 입력해 주세요.")
        if "access_code" in self.fields:
            cleaned_data["access_code"] = str(cleaned_data.get("access_code") or "").strip()
        return cleaned_data

    class Meta:
        model = Signature
        fields = ['participant_affiliation', 'participant_name', 'signature_data']
        widgets = {
            'participant_affiliation': forms.TextInput(attrs={
                'class': 'w-full px-4 py-4 text-xl rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '직위 또는 학년반 (예: 교사, 1-1)',
                'autocomplete': 'off',
                'list': 'affiliationSuggestions',
            }),
            'participant_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-4 text-xl rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '이름을 입력하세요',
                'autocomplete': 'off',
            }),
            'signature_data': forms.HiddenInput(),
        }
