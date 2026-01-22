from django import forms


class SajuForm(forms.Form):
    """사주 입력 폼 - 교사/일반 모드 지원"""

    MODE_CHOICES = [
        ('teacher', '교사 모드'),
        ('general', '일반 모드'),
    ]
    GENDER_CHOICES = [
        ('male', '남자'),
        ('female', '여자'),
    ]
    CALENDAR_CHOICES = [
        ('solar', '양력'),
        ('lunar', '음력'),
    ]

    mode = forms.ChoiceField(
        label='상담 모드',
        choices=MODE_CHOICES,
        initial='teacher',
        widget=forms.RadioSelect(attrs={'class': 'mode-radio'})
    )
    name = forms.CharField(
        label='이름',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'saju-input',
            'placeholder': '이름을 입력해주세요'
        })
    )
    gender = forms.ChoiceField(
        label='성별',
        choices=GENDER_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'gender-radio'})
    )
    birth_year = forms.IntegerField(
        label='태어난 연도',
        min_value=1940,
        max_value=2025,
        widget=forms.NumberInput(attrs={
            'class': 'saju-input',
            'placeholder': '예: 1990'
        })
    )
    birth_month = forms.IntegerField(
        label='월',
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={
            'class': 'saju-input',
            'placeholder': '1~12'
        })
    )
    birth_day = forms.IntegerField(
        label='일',
        min_value=1,
        max_value=31,
        widget=forms.NumberInput(attrs={
            'class': 'saju-input',
            'placeholder': '1~31'
        })
    )
    birth_hour = forms.IntegerField(
        label='시',
        min_value=0,
        max_value=23,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'saju-input',
            'placeholder': '0~23 (모르면 비워두세요)'
        })
    )
    birth_minute = forms.IntegerField(
        label='분',
        min_value=0,
        max_value=59,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'saju-input',
            'placeholder': '0~59'
        })
    )
    calendar_type = forms.ChoiceField(
        label='양력/음력',
        choices=CALENDAR_CHOICES,
        initial='solar',
        widget=forms.RadioSelect(attrs={'class': 'calendar-radio'})
    )

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('birth_year')
        month = cleaned_data.get('birth_month')
        day = cleaned_data.get('birth_day')

        # 간단한 날짜 유효성 검사
        if year and month and day:
            days_in_month = {
                1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30,
                7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
            }
            if day > days_in_month.get(month, 31):
                raise forms.ValidationError(f'{month}월은 {days_in_month[month]}일까지만 있습니다.')

        return cleaned_data
