from django import forms
from .models import UserProfile


class CustomSignupForm(forms.Form):
    """
    allauth ACCOUNT_SIGNUP_FORM_CLASS용 커스텀 폼.
    allauth의 BaseSignupForm이 이 클래스를 상속하므로,
    nickname 필드와 signup() 메서드만 정의하면 됩니다.
    email/username은 allauth가 자동 처리합니다.
    """
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
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.nickname = self.cleaned_data['nickname']
        profile.save()
