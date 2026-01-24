from django import forms
from .models import PadletDocument


class PadletDocumentForm(forms.ModelForm):
    """패들릿 문서 업로드 폼"""

    class Meta:
        model = PadletDocument
        fields = ['title', 'file', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none focus:ring-2 focus:ring-pink-300',
                'placeholder': '문서 제목을 입력하세요 (예: 1학년 3반 패들릿)',
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-pink-100 file:text-pink-700 hover:file:bg-pink-200',
                'accept': '.pdf,.csv',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-transparent text-xl focus:outline-none focus:ring-2 focus:ring-pink-300',
                'rows': 3,
                'placeholder': '패들릿에 대한 간단한 설명 (선택)',
            }),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            ext = file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'csv']:
                raise forms.ValidationError('PDF 또는 CSV 파일만 업로드 가능합니다.')
            # 파일 크기 제한 (50MB)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('파일 크기는 50MB를 초과할 수 없습니다.')
        return file
