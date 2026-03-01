from django import forms
from .models import TrainingSession, Signature
from handoff.models import HandoffRosterGroup


class TrainingSessionForm(forms.ModelForm):
    """연수 생성/수정 폼"""

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
        super().__init__(*args, **kwargs)
        if owner is None and self.instance and self.instance.pk:
            owner = self.instance.created_by
        if owner is not None:
            self.fields["shared_roster_group"].queryset = HandoffRosterGroup.objects.filter(owner=owner).order_by(
                "-is_favorite",
                "name",
            )
        self.fields["shared_roster_group"].label_from_instance = lambda group: group.name

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


class SignatureForm(forms.ModelForm):
    """서명 입력 폼"""

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
