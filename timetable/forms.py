from django import forms


class TimetableUploadForm(forms.Form):
    reservation_school_slug = forms.ChoiceField(
        required=False,
        label="예약 반영 학교",
        help_text="선택하면 '바로반영'으로 지정된 항목만 예약 시스템에 반영합니다.",
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
