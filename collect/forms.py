from django import forms
from django.utils import timezone

from .models import CollectionRequest


class CollectionRequestForm(forms.ModelForm):
    choice_options_text = forms.CharField(
        required=False,
        label="선택형 보기 목록",
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                "rows": 5,
                "placeholder": "한 줄에 한 보기씩 입력\n예)\n찬성\n반대\n보류",
            }
        ),
    )

    class Meta:
        model = CollectionRequest
        fields = [
            "title",
            "description",
            "expected_submitters",
            "allow_file",
            "allow_link",
            "allow_text",
            "allow_choice",
            "choice_mode",
            "choice_min_selections",
            "choice_max_selections",
            "choice_allow_other",
            "deadline",
            "max_submissions",
            "template_file",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none text-lg",
                    "placeholder": "예: 3학년 가정통신문 수합",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "rows": 3,
                    "placeholder": "제출자에게 보일 안내사항을 입력하세요.",
                }
            ),
            "expected_submitters": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "rows": 4,
                    "placeholder": "한 줄에 한 명씩 입력 (선택)\n예)\n김철수\n이영희\n박민수",
                }
            ),
            "deadline": forms.DateTimeInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "max_submissions": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "min": 1,
                    "max": 200,
                }
            ),
            "choice_mode": forms.Select(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                }
            ),
            "choice_min_selections": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "min": 1,
                }
            ),
            "choice_max_selections": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "min": 1,
                    "placeholder": "비우면 제한 없음",
                }
            ),
            "template_file": forms.ClearableFileInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "accept": ".hwp,.hwpx,.xlsx,.xls,.docx,.doc,.pdf,.zip",
                }
            ),
        }
        labels = {
            "title": "수합 제목",
            "description": "안내사항",
            "allow_file": "파일 업로드 허용",
            "allow_link": "링크 제출 허용",
            "allow_text": "텍스트 제출 허용",
            "allow_choice": "선택형 제출 허용",
            "choice_mode": "선택 방식",
            "choice_min_selections": "최소 선택 수",
            "choice_max_selections": "최대 선택 수",
            "choice_allow_other": "기타 직접 입력 허용",
            "deadline": "마감일시",
            "max_submissions": "최대 제출 건수",
            "expected_submitters": "제출 대상자 목록",
            "template_file": "양식 파일",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["choice_options_text"] = "\n".join(self.instance.normalized_choice_options)
            if self.instance.deadline:
                self.initial["deadline"] = timezone.localtime(self.instance.deadline).strftime("%Y-%m-%dT%H:%M")
        self.fields["deadline"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["allow_choice"].widget.attrs.update({"x-model": "allowChoice"})
        self._parsed_choice_options = []

    def clean(self):
        cleaned_data = super().clean()

        allow_file = bool(cleaned_data.get("allow_file"))
        allow_link = bool(cleaned_data.get("allow_link"))
        allow_text = bool(cleaned_data.get("allow_text"))
        allow_choice = bool(cleaned_data.get("allow_choice"))

        if not any([allow_file, allow_link, allow_text, allow_choice]):
            raise forms.ValidationError("제출 허용 방식은 최소 1개 이상 선택해주세요.")

        raw_options = cleaned_data.get("choice_options_text", "")
        parsed_options = []
        seen = set()
        for line in raw_options.splitlines():
            option = line.strip()
            if not option or option in seen:
                continue
            parsed_options.append(option)
            seen.add(option)
        self._parsed_choice_options = parsed_options

        if allow_choice:
            if len(parsed_options) < 2:
                self.add_error("choice_options_text", "선택형 보기는 최소 2개 이상 입력해주세요.")

            choice_mode = cleaned_data.get("choice_mode") or "single"
            min_selections = cleaned_data.get("choice_min_selections") or 1
            max_selections = cleaned_data.get("choice_max_selections")
            allow_other = bool(cleaned_data.get("choice_allow_other"))

            if choice_mode == "single":
                cleaned_data["choice_min_selections"] = 1
                cleaned_data["choice_max_selections"] = 1
            else:
                if min_selections < 1:
                    self.add_error("choice_min_selections", "최소 선택 수는 1 이상이어야 합니다.")

                available_count = len(parsed_options) + (1 if allow_other else 0)
                if min_selections > available_count:
                    self.add_error(
                        "choice_min_selections",
                        f"최소 선택 수는 보기 개수({available_count})를 초과할 수 없습니다.",
                    )

                if max_selections is not None:
                    if max_selections < min_selections:
                        self.add_error("choice_max_selections", "최대 선택 수는 최소 선택 수보다 작을 수 없습니다.")
                    if max_selections > available_count:
                        self.add_error(
                            "choice_max_selections",
                            f"최대 선택 수는 보기 개수({available_count})를 초과할 수 없습니다.",
                        )
        else:
            cleaned_data["choice_mode"] = "single"
            cleaned_data["choice_min_selections"] = 1
            cleaned_data["choice_max_selections"] = None
            cleaned_data["choice_allow_other"] = False

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.allow_choice:
            instance.choice_options = self._parsed_choice_options
            if instance.choice_mode == "single":
                instance.choice_min_selections = 1
                instance.choice_max_selections = 1
        else:
            instance.choice_mode = "single"
            instance.choice_options = []
            instance.choice_min_selections = 1
            instance.choice_max_selections = None
            instance.choice_allow_other = False

        if commit:
            instance.save()
            self.save_m2m()
        return instance
