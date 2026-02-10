from django import forms
from .models import UserProfile

class CustomSignupForm(forms.Form):
    email = forms.EmailField(
        label="이메일",
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': '이메일 주소',
            'autocomplete': 'email',
        })
    )
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
        self.sociallogin = kwargs.pop("sociallogin", None)
        super().__init__(*args, **kwargs)
        
        if self.sociallogin:
            # 소셜 계정에서 이메일 추출하여 초기값 설정
            user = self.sociallogin.user
            if user.email:
                self.fields['email'].initial = user.email
                # 읽기 전용으로 설정하여 사용자 혼란 방지 (원하신다면 제거 가능)
                self.fields['email'].widget.attrs['readonly'] = True
                self.fields['email'].widget.attrs['class'] = 'bg-gray-100 text-gray-500 cursor-not-allowed'

    def signup(self, request, user):
        # UserProfile 생성 또는 가져오기
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # 별명 저장
        profile.nickname = self.cleaned_data['nickname']
        profile.save()
        
        # user.save()는 allauth가 처리함


