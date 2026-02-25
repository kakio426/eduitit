from django import forms
from django.utils import timezone

from .models import HandoffRosterGroup, HandoffSession


class HandoffRosterGroupForm(forms.ModelForm):
    class Meta:
        model = HandoffRosterGroup
        fields = ["name", "description", "is_favorite"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none",
                    "placeholder": "예: 2학년 담임",
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none",
                    "placeholder": "예: 교무실 자료 배부 명단",
                }
            ),
            "is_favorite": forms.CheckboxInput(attrs={"class": "rounded border-gray-300 text-blue-600"}),
        }
        labels = {
            "name": "명단 이름",
            "description": "설명 (선택)",
            "is_favorite": "즐겨찾기",
        }


class HandoffMemberBulkAddForm(forms.Form):
    names_text = forms.CharField(
        label="이름 붙여넣기",
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none",
                "rows": 6,
                "placeholder": "한 줄에 한 명씩 입력\n예)\n김민수\n이서연\n박지훈",
            }
        ),
    )


class HandoffSessionCreateForm(forms.ModelForm):
    class Meta:
        model = HandoffSession
        fields = ["title", "roster_group", "due_at", "note"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                    "placeholder": "예: 2월 교무실 전달 자료",
                }
            ),
            "roster_group": forms.Select(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                }
            ),
            "due_at": forms.DateTimeInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "note": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                    "rows": 3,
                    "placeholder": "배부 시 메모할 점이 있다면 적어주세요.",
                }
            ),
        }
        labels = {
            "title": "배부 제목",
            "roster_group": "대상 명단",
            "due_at": "마감 시간 (선택)",
            "note": "메모 (선택)",
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields["roster_group"].queryset = HandoffRosterGroup.objects.filter(owner=owner).order_by(
                "-is_favorite",
                "name",
            )
        self.fields["due_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.due_at and not self.is_bound:
            self.initial["due_at"] = timezone.localtime(self.instance.due_at).strftime("%Y-%m-%dT%H:%M")


class HandoffSessionEditForm(forms.ModelForm):
    class Meta:
        model = HandoffSession
        fields = ["title", "due_at", "note"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                }
            ),
            "due_at": forms.DateTimeInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "note": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-indigo-500 focus:outline-none",
                    "rows": 4,
                }
            ),
        }
        labels = {
            "title": "배부 제목",
            "due_at": "마감 시간 (선택)",
            "note": "메모 (선택)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.due_at and not self.is_bound:
            self.initial["due_at"] = timezone.localtime(self.instance.due_at).strftime("%Y-%m-%dT%H:%M")
