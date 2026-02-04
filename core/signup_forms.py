from django import forms
from .models import UserProfile

class CustomSignupForm(forms.Form):
    nickname = forms.CharField(
        max_length=50,
        required=True,
        label="별명",
        widget=forms.TextInput(attrs={
            'placeholder': '별명을 입력해주세요 (필수)',
            'autocomplete': 'nickname'
        })
    )

    def signup(self, request, user):
        # UserProfile 생성 또는 가져오기
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # 별명 저장
        profile.nickname = self.cleaned_data['nickname']
        profile.save()

