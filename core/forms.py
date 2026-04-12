from django import forms

from .models import UserProfile

class UserProfileUpdateForm(forms.ModelForm):
    nickname = forms.CharField(
        max_length=50,
        required=False,
        label="닉네임",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-6 py-4 rounded-2xl shadow-clay-inner bg-[#E0E5EC] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all font-bold text-xl',
            'placeholder': '닉네임을 입력해 주세요'
        })
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        required=False,
        label="역할",
        widget=forms.Select(attrs={
            'class': 'w-full px-6 py-4 rounded-2xl shadow-clay-inner bg-[#E0E5EC] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all font-bold text-xl appearance-none'
        })
    )
    class Meta:
        model = UserProfile
        fields = ['nickname', 'role']


class PolicyConsentForm(forms.Form):
    agree_terms = forms.BooleanField(
        required=True,
        label='[필수] 이용약관에 동의합니다',
        widget=forms.CheckboxInput(attrs={
            'class': 'policy-check-input',
            'data-policy-required': 'true',
        }),
        error_messages={'required': '이용약관 동의가 필요합니다.'},
    )
    agree_privacy = forms.BooleanField(
        required=True,
        label='[필수] 개인정보처리방침에 동의합니다',
        widget=forms.CheckboxInput(attrs={
            'class': 'policy-check-input',
            'data-policy-required': 'true',
        }),
        error_messages={'required': '개인정보처리방침 동의가 필요합니다.'},
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('agree_terms') or not cleaned_data.get('agree_privacy'):
            raise forms.ValidationError('필수 약관 동의 후 서비스를 이용할 수 있습니다.')
        return cleaned_data

# CustomSignupForm moved to core/signup_forms.py
