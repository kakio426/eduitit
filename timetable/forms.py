from django import forms

from timetable.models import TimetableSchoolProfile


TERM_CHOICES = [
    ("1학기", "1학기"),
    ("2학기", "2학기"),
    ("여름학기", "여름학기"),
    ("겨울학기", "겨울학기"),
]


SCHOOL_STAGE_CHOICES = TimetableSchoolProfile.SchoolStage.choices


class WorkspaceBatchCreateForm(forms.Form):
    school_slug = forms.ChoiceField(label="학교")
    school_year = forms.IntegerField(label="학년도", min_value=2000, max_value=2100)
    term = forms.ChoiceField(label="학기", choices=TERM_CHOICES)
    school_stage = forms.ChoiceField(label="학교급", choices=SCHOOL_STAGE_CHOICES)
    custom_grade_start = forms.IntegerField(label="시작 학년", min_value=1, max_value=12, required=False)
    custom_grade_end = forms.IntegerField(label="종료 학년", min_value=1, max_value=12, required=False)
    period_count = forms.IntegerField(label="교시 수", min_value=1, max_value=12, initial=6)
    days_text = forms.CharField(label="운영 요일", initial="월,화,수,목,금")
    term_start_date = forms.DateField(label="학기 시작일", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    term_end_date = forms.DateField(label="학기 종료일", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        school_choices = kwargs.pop("school_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["school_slug"].choices = school_choices
        shared_class = "block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", shared_class)

    def clean_days_text(self):
        raw = (self.cleaned_data.get("days_text") or "").replace("|", ",").replace("/", ",")
        days = [item.strip() for item in raw.split(",") if item.strip()]
        if len(days) < 3:
            raise forms.ValidationError("운영 요일은 3일 이상 입력해 주세요.")
        return days

    def clean(self):
        cleaned_data = super().clean()
        school_stage = cleaned_data.get("school_stage")
        custom_grade_start = cleaned_data.get("custom_grade_start")
        custom_grade_end = cleaned_data.get("custom_grade_end")
        term_start_date = cleaned_data.get("term_start_date")
        term_end_date = cleaned_data.get("term_end_date")

        if school_stage == TimetableSchoolProfile.SchoolStage.CUSTOM:
            if not custom_grade_start or not custom_grade_end:
                raise forms.ValidationError("직접 입력 학교급은 시작 학년과 종료 학년을 모두 입력해 주세요.")
            if custom_grade_end < custom_grade_start:
                raise forms.ValidationError("종료 학년은 시작 학년보다 같거나 커야 합니다.")
        if term_start_date and term_end_date and term_end_date < term_start_date:
            raise forms.ValidationError("학기 종료일은 시작일보다 같거나 뒤여야 합니다.")
        return cleaned_data

    def resolve_grade_range(self):
        school_stage = self.cleaned_data["school_stage"]
        if school_stage == TimetableSchoolProfile.SchoolStage.ELEMENTARY:
            return range(1, 7)
        if school_stage in {
            TimetableSchoolProfile.SchoolStage.MIDDLE,
            TimetableSchoolProfile.SchoolStage.HIGH,
        }:
            return range(1, 4)
        return range(self.cleaned_data["custom_grade_start"], self.cleaned_data["custom_grade_end"] + 1)


WorkspaceCreateForm = WorkspaceBatchCreateForm


class TimetableTeacherForm(forms.Form):
    name = forms.CharField(label="이름", max_length=80)
    teacher_type = forms.ChoiceField(
        label="유형",
        choices=[
            ("homeroom", "담임"),
            ("specialist", "전담"),
            ("instructor", "강사"),
        ],
    )
    target_weekly_hours = forms.IntegerField(label="목표 시수", min_value=0, max_value=80, initial=0)
    subjects_text = forms.CharField(label="담당 과목", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        shared_class = "block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", shared_class)

    def clean_subjects_text(self):
        raw = (self.cleaned_data.get("subjects_text") or "").replace("|", ",").replace("/", ",")
        return [item.strip() for item in raw.split(",") if item.strip()]


class TimetableUploadForm(forms.Form):
    reservation_school_slug = forms.ChoiceField(
        required=False,
        label="예약 반영 학교",
        help_text="선택하면 '바로반영'으로 지정된 항목만 예약 시스템에 반영합니다. 공유된 학교만 표시됩니다.",
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        label="기존 고정시간표 덮어쓰기 (관리자 전용)",
        help_text="체크하면 같은 시간칸에 기존 고정시간표가 있어도 새 내용으로 바꿉니다.",
    )
    excel_file = forms.FileField(
        label="시간표 엑셀 파일",
        help_text="xlsx 파일만 올려주세요. 업로드 후 입력 형식을 먼저 점검합니다.",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".xlsx",
                "class": "block w-full text-sm text-slate-700 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-bold file:text-slate-700 hover:file:bg-slate-200",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        school_choices = kwargs.pop("school_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["reservation_school_slug"].choices = [("", "연동하지 않음")] + school_choices
        self.fields["reservation_school_slug"].widget.attrs.update(
            {
                "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-indigo-500 focus:ring-indigo-500",
            }
        )
        self.fields["overwrite_existing"].widget.attrs.update(
            {
                "class": "h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500",
            }
        )

    def clean_excel_file(self):
        file_obj = self.cleaned_data["excel_file"]
        file_name = (file_obj.name or "").lower()
        if not file_name.endswith(".xlsx"):
            raise forms.ValidationError("xlsx 파일만 사용할 수 있습니다.")

        max_size = 20 * 1024 * 1024
        if file_obj.size > max_size:
            raise forms.ValidationError("파일 크기는 20MB 이하로 올려주세요.")
        return file_obj
