from django import forms
from .models import UserProfile

class CustomSignupForm(forms.Form):
    nickname = forms.CharField(
        max_length=50,
        required=True,
        label="별명",
        widget=forms.TextInput(attrs={
            'placeholder': '별명을 입력해주세요 (필수)',
            'autocomplete': 'nickname',
            'class': 'w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition bg-white/50 backdrop-blur-sm placeholder-gray-400'
        })
    )

    def signup(self, request, user):
        # UserProfile 생성 또는 가져오기
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # 별명 저장
        profile.nickname = self.cleaned_data['nickname']
        profile.save()

