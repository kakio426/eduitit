from django import forms
from .models import TrainingSession, Signature


class TrainingSessionForm(forms.ModelForm):
    """연수 생성/수정 폼"""

    class Meta:
        model = TrainingSession
        fields = ['title', 'instructor', 'datetime', 'location', 'description', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '예: 2024학년도 1학기 학교폭력예방교육',
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
            }),
            'participant_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-4 text-xl rounded-2xl shadow-clay-inner bg-bg-soft focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '이름을 입력하세요',
                'autocomplete': 'off',
            }),
            'signature_data': forms.HiddenInput(),
        }
