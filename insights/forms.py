from django import forms
from .models import Insight

class InsightForm(forms.ModelForm):
    class Meta:
        model = Insight
        fields = ['title', 'category', 'video_url', 'content', 'kakio_note', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': '제목을 입력하세요'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl'
            }),
            'video_url': forms.URLInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': 'https://www.youtube.com/watch?v=...'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'rows': 5,
                'placeholder': '핵심 인사이트를 입력하세요'
            }),
            'kakio_note': forms.Textarea(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'rows': 3,
                'placeholder': '추가 노트 (선택사항)'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': '#AI교육 #미래교육'
            }),
        }
        labels = {
            'title': '제목',
            'category': '카테고리',
            'video_url': 'YouTube URL',
            'content': '핵심 인사이트',
            'kakio_note': '나만의 노트',
            'tags': '태그',
        }
