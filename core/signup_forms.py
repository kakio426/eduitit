from django import forms
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from .models import UserProfile


class CustomSignupForm(SocialSignupForm):
    nickname = forms.CharField(
        max_length=50,
        required=True,
        label="별명",
        widget=forms.TextInput(attrs={
            'placeholder': '별명을 입력해주세요 (필수)',
            'autocomplete': 'nickname'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 소셜 제공자가 이메일을 제공한 경우 읽기 전용으로 설정
        if self.sociallogin and self.sociallogin.user.email:
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['class'] = 'bg-gray-100 text-gray-500 cursor-not-allowed'

    def signup(self, request, user):
        # UserProfile 생성 또는 가져오기
        profile, created = UserProfile.objects.get_or_create(user=user)

        # 별명 저장
        profile.nickname = self.cleaned_data['nickname']
        profile.save()
