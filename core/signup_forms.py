from django import forms
from allauth.account.forms import SignupForm
from .models import UserProfile

class CustomSignupForm(SignupForm):
    nickname = forms.CharField(
        max_length=50,
        required=True,
        label="별명",
        widget=forms.TextInput(attrs={
            'placeholder': '별명을 입력해주세요 (필수)',
            'autocomplete': 'nickname'
        })
    )

    def save(self, request):
        # 부모 클래스의 save 메서드 호출하여 유저 생성
        user = super(CustomSignupForm, self).save(request)
        
        # UserProfile 생성 또는 가져오기
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # 별명 저장
        profile.nickname = self.cleaned_data['nickname']
        profile.save()
        
        return user
