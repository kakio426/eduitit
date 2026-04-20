from django import forms
from .models import Insight

class InsightForm(forms.ModelForm):
    class Meta:
        model = Insight
        fields = ['title', 'track', 'series_name', 'deck', 'category', 'video_url', 'content', 'kakio_note', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': '제목을 입력하세요'
            }),
            'track': forms.Select(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl'
            }),
            'series_name': forms.TextInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': '예: 교실 AI 루틴'
            }),
            'deck': forms.TextInput(attrs={
                'class': 'w-full px-5 py-3 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-xl',
                'placeholder': '홈과 목록 카드에서 먼저 보여줄 한 줄'
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
            'track': '헤리티지 분류',
            'series_name': '시리즈',
            'deck': '짧은 소개',
            'category': '카테고리',
            'video_url': 'YouTube URL',
            'content': '핵심 인사이트',
            'kakio_note': '나만의 노트',
            'tags': '태그',
        }


class InsightPasteForm(forms.Form):
    raw_text = forms.CharField(
        label='붙여넣기 원문',
        widget=forms.Textarea(
            attrs={
                'class': 'w-full px-5 py-4 rounded-2xl bg-[#E0E5EC] shadow-clay-inner focus:shadow-clay border-none outline-none text-lg',
                'rows': 22,
                'autocapitalize': 'off',
                'autocorrect': 'off',
                'autocomplete': 'off',
                'spellcheck': 'false',
                'placeholder': (
                    "Title: ...\n"
                    "카테고리:\nYouTube Scrap\n\n"
                    "Video url:\nhttps://www.youtube.com/watch?v=...\n\n"
                    "Thumbnail url:\nhttps://img.youtube.com/vi/.../maxresdefault.jpg\n\n"
                    "Content:\n...\n\n"
                    "Kakio note:\n...\n\n"
                    "Tags:\n#태그1, #태그2"
                ),
            }
        ),
    )
