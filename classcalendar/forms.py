from django import forms

from .models import CalendarMessageCapture, CalendarTask


EVENT_COLORS = (
    ("indigo", "인디고"),
    ("rose", "로즈"),
    ("amber", "앰버"),
    ("emerald", "에메랄드"),
    ("sky", "스카이"),
)


DATETIME_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
]


class CalendarEventCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    note = forms.CharField(required=False, max_length=5000)
    calendar_owner_id = forms.CharField(required=False, max_length=64)
    start_time = forms.DateTimeField(input_formats=DATETIME_INPUT_FORMATS)
    end_time = forms.DateTimeField(input_formats=DATETIME_INPUT_FORMATS)
    is_all_day = forms.BooleanField(required=False)
    color = forms.ChoiceField(choices=EVENT_COLORS, required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if start_time and end_time and end_time < start_time:
            raise forms.ValidationError("종료 시간은 시작 시간보다 같거나 이후여야 합니다.")
        return cleaned_data


class MessageCaptureParseForm(forms.Form):
    raw_text = forms.CharField(required=False, max_length=20000)
    source_hint = forms.CharField(required=False, max_length=30)
    idempotency_key = forms.CharField(required=False, max_length=64)


class MessageCaptureCommitForm(forms.Form):
    confirmed_item_type = forms.ChoiceField(
        choices=CalendarMessageCapture.ItemType.choices,
        required=False,
    )
    title = forms.CharField(max_length=200)
    todo_summary = forms.CharField(required=False, max_length=5000)
    note = forms.CharField(required=False, max_length=5000)
    start_time = forms.DateTimeField(required=False, input_formats=DATETIME_INPUT_FORMATS)
    end_time = forms.DateTimeField(required=False, input_formats=DATETIME_INPUT_FORMATS)
    due_at = forms.DateTimeField(required=False, input_formats=DATETIME_INPUT_FORMATS)
    has_time = forms.BooleanField(required=False)
    is_all_day = forms.BooleanField(required=False)
    priority = forms.ChoiceField(choices=CalendarTask.Priority.choices, required=False)
    color = forms.ChoiceField(choices=EVENT_COLORS, required=False)
    confirm_low_confidence = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        item_type = cleaned_data.get("confirmed_item_type") or CalendarMessageCapture.ItemType.EVENT
        cleaned_data["confirmed_item_type"] = item_type

        if item_type == CalendarMessageCapture.ItemType.IGNORE:
            raise forms.ValidationError("무시 항목은 저장할 수 없습니다.")

        if item_type == CalendarMessageCapture.ItemType.EVENT:
            start_time = cleaned_data.get("start_time")
            end_time = cleaned_data.get("end_time")
            if not start_time:
                self.add_error("start_time", "시작 시간을 입력해 주세요.")
            if not end_time:
                self.add_error("end_time", "종료 시간을 입력해 주세요.")
            if start_time and end_time and end_time < start_time:
                raise forms.ValidationError("종료 시간은 시작 시간보다 같거나 이후여야 합니다.")
            cleaned_data["priority"] = cleaned_data.get("priority") or CalendarTask.Priority.NORMAL
            return cleaned_data

        due_at = cleaned_data.get("due_at")
        has_time = bool(cleaned_data.get("has_time", False))
        if not due_at:
            self.add_error("due_at", "할 일 마감일을 입력해 주세요.")
        if has_time and not due_at:
            self.add_error("due_at", "시간이 있는 할 일은 마감일시가 필요합니다.")
        cleaned_data["priority"] = cleaned_data.get("priority") or CalendarTask.Priority.NORMAL
        return cleaned_data
