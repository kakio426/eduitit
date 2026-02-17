from django import forms

from .models import HSClassroom, HSClassroomConfig, HSPrize, HSStudent


class HSClassroomForm(forms.ModelForm):
    class Meta:
        model = HSClassroom
        fields = ["name", "school_name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300 focus:border-purple-400",
                    "placeholder": "예: 6학년 1반",
                }
            ),
            "school_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300 focus:border-purple-400",
                    "placeholder": "예: 행복초등학교",
                }
            ),
        }


class HSClassroomConfigForm(forms.ModelForm):
    class Meta:
        model = HSClassroomConfig
        fields = [
            "seeds_per_bloom",
            "base_win_rate",
            "group_draw_count",
            "balance_mode_enabled",
            "balance_epsilon",
            "balance_lookback_days",
        ]
        widgets = {
            "seeds_per_bloom": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "1",
                    "max": "100",
                }
            ),
            "base_win_rate": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "1",
                    "max": "100",
                }
            ),
            "group_draw_count": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "1",
                    "max": "10",
                }
            ),
            "balance_epsilon": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "step": "0.01",
                    "min": "0",
                    "max": "1",
                }
            ),
            "balance_lookback_days": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "1",
                    "max": "365",
                }
            ),
        }


class HSStudentForm(forms.ModelForm):
    class Meta:
        model = HSStudent
        fields = ["name", "number"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "placeholder": "학생 이름",
                }
            ),
            "number": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "0",
                }
            ),
        }


class HSPrizeForm(forms.ModelForm):
    class Meta:
        model = HSPrize
        fields = ["name", "description", "total_quantity", "display_order"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "placeholder": "보상 이름",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "rows": "2",
                    "placeholder": "보상 설명 (선택)",
                }
            ),
            "total_quantity": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "0",
                    "placeholder": "비워두면 무제한",
                }
            ),
            "display_order": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "0",
                }
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.total_quantity is not None and instance.remaining_quantity is None:
            instance.remaining_quantity = instance.total_quantity
        if commit:
            instance.save()
        return instance


class StudentBulkAddForm(forms.Form):
    students_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                "rows": "10",
                "placeholder": (
                    "한 줄에 한 명씩 입력\n"
                    "1 홍길동\n"
                    "2 김철수\n"
                    "3 이영희\n\n"
                    "또는 이름만 입력:\n"
                    "홍길동\n"
                    "김철수\n"
                    "이영희"
                ),
            }
        ),
        label="학생 명단",
        help_text="각 줄에서 번호와 이름을 공백으로 구분하거나, 이름만 입력해도 됩니다.",
    )

    def parse_students(self):
        text = self.cleaned_data["students_text"].strip()
        students = []
        for i, line in enumerate(text.split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                students.append({"number": int(parts[0]), "name": parts[1]})
            else:
                students.append({"number": i, "name": line})
        return students
