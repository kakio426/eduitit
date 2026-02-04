from django import forms

from .models import UserProfile

class APIKeyForm(forms.ModelForm):
    gemini_api_key = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your Gemini API Key'}),
        required=False,
        label="Gemini API Key",
        help_text="Leave blank to use the system default key."
    )

    class Meta:
        model = UserProfile
        fields = ['gemini_api_key']

class UserProfileUpdateForm(forms.ModelForm):
    nickname = forms.CharField(
        max_length=50,
        required=False,
        label="별명",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-6 py-4 rounded-2xl shadow-clay-inner bg-[#E0E5EC] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all font-bold text-xl',
            'placeholder': '멋진 별명을 입력해 주세요'
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
    gemini_api_key = forms.CharField(
        required=False,
        label="개인 Gemini API Key(선택)",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-6 py-4 rounded-2xl shadow-clay-inner bg-[#E0E5EC] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all font-bold text-xl',
            'placeholder': '개인 API Key를 입력하세요'
        })
    )
    padlet_api_key = forms.CharField(
        required=False,
        label="개인 Padlet API Key (선택 - Padlet Platinum/Pro 요금제만 사용 가능)",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-6 py-4 rounded-2xl shadow-clay-inner bg-[#E0E5EC] focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all font-bold text-xl',
            'placeholder': '개인 Padlet API Key를 입력하세요'
        })
    )

    class Meta:
        model = UserProfile
        fields = ['nickname', 'role', 'gemini_api_key', 'padlet_api_key']

# CustomSignupForm moved to core/signup_forms.py
