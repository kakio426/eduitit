from django import forms

from .models import Sheetbook
from .models import SheetTab


CLAY_INPUT = (
    "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-bg-soft "
    "focus:outline-none focus:ring-2 focus:ring-purple-300"
)


class SheetbookCreateForm(forms.ModelForm):
    class Meta:
        model = Sheetbook
        fields = ["title", "academic_year"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": CLAY_INPUT,
                    "placeholder": "예: 2026 2-3반 교무수첩",
                    "maxlength": "200",
                }
            ),
            "academic_year": forms.NumberInput(
                attrs={
                    "class": CLAY_INPUT,
                    "placeholder": "예: 2026",
                    "min": "2000",
                    "max": "2100",
                }
            ),
        }


class SheetTabCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tab_type = self.fields.get("tab_type")
        if tab_type:
            tab_type.choices = [
                (SheetTab.TYPE_GRID, "표"),
                (SheetTab.TYPE_CALENDAR, "달력"),
            ]

    class Meta:
        model = SheetTab
        fields = ["name", "tab_type"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": CLAY_INPUT,
                    "placeholder": "새 탭 이름 (예: 학생 명부)",
                    "maxlength": "100",
                }
            ),
            "tab_type": forms.Select(
                attrs={
                    "class": CLAY_INPUT,
                }
            ),
        }


class SheetTabRenameForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": CLAY_INPUT,
                "placeholder": "탭 이름",
            }
        ),
    )
