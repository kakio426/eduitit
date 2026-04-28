import json

from django import forms
from django.utils import timezone

from handoff.models import HandoffRosterGroup

from .models import CollectionRequest
from .field_schema import (
    CHOICE_FIELD_KINDS,
    normalize_field_schema,
    schema_uses_choice,
    schema_uses_file,
    schema_uses_link,
    schema_uses_text,
)


class CollectionRequestForm(forms.ModelForm):
    field_schema_input = forms.CharField(required=False, widget=forms.HiddenInput())

    shared_roster_group = forms.ModelChoiceField(
        required=False,
        queryset=HandoffRosterGroup.objects.none(),
        empty_label="선택 안 함 (수동 입력만 사용)",
        label="배부 체크 공유 명단",
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
            }
        ),
    )

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
            "collection_mode",
            "title",
            "description",
            "bti_integration_source",
            "shared_roster_group",
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
            "collection_mode": forms.HiddenInput(),
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
            "bti_integration_source": forms.Select(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
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
            "collection_mode": "수합 방식",
            "title": "수합 제목",
            "description": "안내사항",
            "bti_integration_source": "BTI 연동",
            "shared_roster_group": "배부 체크 공유 명단",
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
        owner = kwargs.pop("owner", None)
        super().__init__(*args, **kwargs)

        if owner is None and self.instance and self.instance.pk:
            owner = self.instance.creator
        if owner is not None:
            self.fields["shared_roster_group"].queryset = HandoffRosterGroup.objects.filter(owner=owner).order_by(
                "-is_favorite",
                "name",
            )
        # 배부 체크 공유 명단은 소유자 계정 식별자 없이 명단명만 노출한다.
        self.fields["shared_roster_group"].label_from_instance = lambda group: group.name

        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["collection_mode"] = self.instance.collection_mode
            self.initial["field_schema_input"] = json.dumps(
                self.instance.normalized_field_schema,
                ensure_ascii=False,
            )
            self.initial["choice_options_text"] = "\n".join(self.instance.normalized_choice_options)
            if self.instance.deadline:
                self.initial["deadline"] = timezone.localtime(self.instance.deadline).strftime("%Y-%m-%dT%H:%M")
        elif not self.is_bound:
            self.initial["collection_mode"] = "fields"
        self.fields["deadline"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        self.fields["bti_integration_source"].required = False
        self.fields["collection_mode"].required = False
        self.fields["choice_mode"].required = False
        self.fields["choice_min_selections"].required = False
        self.fields["choice_max_selections"].required = False
        self.fields["bti_integration_source"].initial = (
            self.initial.get("bti_integration_source")
            or getattr(self.instance, "bti_integration_source", "")
            or "none"
        )
        self.fields["allow_choice"].widget.attrs.update({"x-model": "allowChoice"})
        self._parsed_choice_options = []
        self._parsed_field_schema = []

    def clean(self):
        cleaned_data = super().clean()

        collection_mode = cleaned_data.get("collection_mode")
        if collection_mode not in {"legacy", "fields"}:
            if self.instance and self.instance.pk:
                collection_mode = self.instance.collection_mode
            else:
                collection_mode = "legacy"

        raw_schema = cleaned_data.get("field_schema_input", "")
        parsed_schema = normalize_field_schema(raw_schema)
        self._parsed_field_schema = parsed_schema
        cleaned_data["collection_mode"] = collection_mode

        if collection_mode == "fields":
            if not parsed_schema:
                self.add_error("field_schema_input", "받을 항목을 1개 이상 추가해주세요.")

            file_field_count = sum(1 for item in parsed_schema if item.get("kind") == "file")
            if file_field_count > 1:
                self.add_error("field_schema_input", "파일 항목은 1개만 사용할 수 있습니다.")

            for item in parsed_schema:
                if item.get("kind") in CHOICE_FIELD_KINDS and len(item.get("options", [])) < 2:
                    self.add_error("field_schema_input", f"{item.get('label', '선택 항목')} 보기는 2개 이상 필요합니다.")

            cleaned_data["allow_file"] = schema_uses_file(parsed_schema)
            cleaned_data["allow_link"] = schema_uses_link(parsed_schema)
            cleaned_data["allow_text"] = schema_uses_text(parsed_schema)
            cleaned_data["allow_choice"] = schema_uses_choice(parsed_schema)
            cleaned_data["choice_mode"] = "single"
            cleaned_data["choice_min_selections"] = 1
            cleaned_data["choice_max_selections"] = None
            cleaned_data["choice_allow_other"] = False
            cleaned_data["bti_integration_source"] = cleaned_data.get("bti_integration_source") or "none"
            self._parsed_choice_options = []
            return cleaned_data

        allow_file = bool(cleaned_data.get("allow_file"))
        allow_link = bool(cleaned_data.get("allow_link"))
        allow_text = bool(cleaned_data.get("allow_text"))
        allow_choice = bool(cleaned_data.get("allow_choice"))
        cleaned_data["bti_integration_source"] = (
            cleaned_data.get("bti_integration_source") or "none"
        )

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
        if instance.collection_mode == "fields":
            instance.field_schema = self._parsed_field_schema
            instance.allow_file = schema_uses_file(instance.field_schema)
            instance.allow_link = schema_uses_link(instance.field_schema)
            instance.allow_text = schema_uses_text(instance.field_schema)
            instance.allow_choice = schema_uses_choice(instance.field_schema)
            instance.choice_mode = "single"
            instance.choice_options = []
            instance.choice_min_selections = 1
            instance.choice_max_selections = None
            instance.choice_allow_other = False
        elif instance.allow_choice:
            instance.field_schema = []
            instance.choice_options = self._parsed_choice_options
            if instance.choice_mode == "single":
                instance.choice_min_selections = 1
                instance.choice_max_selections = 1
        else:
            instance.field_schema = []
            instance.choice_mode = "single"
            instance.choice_options = []
            instance.choice_min_selections = 1
            instance.choice_max_selections = None
            instance.choice_allow_other = False

        if commit:
            instance.save()
            self.save_m2m()
        return instance
