from django import forms
from .models import GuidelineDocument


class GuidelineDocumentForm(forms.ModelForm):
    """가이드라인 문서 업로드 폼"""

    class Meta:
        model = GuidelineDocument
        fields = ['title', 'category', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none focus:ring-2 focus:ring-purple-300',
                'placeholder': '문서 제목을 입력하세요',
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-[#E0E5EC] text-xl focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200',
                'accept': '.pdf,.hwp,.txt,.md',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none focus:ring-2 focus:ring-purple-300',
                'rows': 3,
                'placeholder': '문서에 대한 간단한 설명 (선택)',
            }),
        }
