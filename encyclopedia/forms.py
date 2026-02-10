from django import forms
from .models import NotebookEntry


class NotebookEntryForm(forms.ModelForm):
    class Meta:
        model = NotebookEntry
        fields = ['title', 'description', 'notebook_url']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-400 focus:outline-none text-base',
                'placeholder': '예: 학급 경영 매뉴얼',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-400 focus:outline-none text-sm',
                'rows': 3,
                'placeholder': '이 백과사전에 대한 간단한 설명을 입력하세요 (선택사항)',
            }),
            'notebook_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-400 focus:outline-none text-base',
                'placeholder': 'https://notebooklm.google.com/...',
            }),
        }
