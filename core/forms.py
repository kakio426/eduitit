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
