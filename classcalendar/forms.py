from django import forms


EVENT_COLORS = (
    ("indigo", "인디고"),
    ("rose", "로즈"),
    ("amber", "앰버"),
    ("emerald", "에메랄드"),
    ("sky", "스카이"),
)


class CalendarEventCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    note = forms.CharField(required=False, max_length=5000)
    calendar_owner_id = forms.CharField(required=False, max_length=64)
    start_time = forms.DateTimeField(
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
    )
    end_time = forms.DateTimeField(
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
    )
    is_all_day = forms.BooleanField(required=False)
    color = forms.ChoiceField(choices=EVENT_COLORS, required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if start_time and end_time and end_time < start_time:
            raise forms.ValidationError("종료 시간은 시작 시간보다 같거나 이후여야 합니다.")
        return cleaned_data
