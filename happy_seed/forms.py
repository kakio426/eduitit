import csv
import io
import re

from django import forms

from .models import HSActivity, HSClassroom, HSClassroomConfig, HSPrize, HSStudent


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
                    "max": "0.10",
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

    def clean_balance_epsilon(self):
        epsilon = float(self.cleaned_data["balance_epsilon"])
        if epsilon < 0:
            raise forms.ValidationError("epsilon은 0 이상이어야 합니다.")
        if epsilon > 0.10:
            raise forms.ValidationError("epsilon은 0.10 이하로 설정해 주세요. (과도한 변화를 방지합니다)")
        return epsilon


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
        fields = ["name", "description", "win_rate_percent", "total_quantity", "display_order"]
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
            "win_rate_percent": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                    "placeholder": "예: 70",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 화면에서 순서를 별도로 받지 않아도 저장 가능하도록 기본값(0) 사용
        self.fields["display_order"].required = False
        self.fields["display_order"].initial = 0

    def clean_display_order(self):
        value = self.cleaned_data.get("display_order")
        return 0 if value in (None, "") else value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.total_quantity is not None and instance.remaining_quantity is None:
            instance.remaining_quantity = instance.total_quantity
        if commit:
            instance.save()
        return instance


class StudentBulkAddForm(forms.Form):
    NUMBER_HEADER_TOKENS = {"번호", "학번", "no", "num", "number", "studentnumber", "studentno"}
    NAME_HEADER_TOKENS = {"이름", "성명", "학생명", "학생", "name", "student", "studentname"}

    students_paste = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                "rows": "10",
                "placeholder": (
                    "엑셀에서 번호/이름 열을 복사해서 그대로 붙여넣기\n"
                    "번호\t이름\n"
                    "1\t홍길동\n"
                    "2\t김철수\n\n"
                    "이름만 붙여넣어도 됩니다.\n"
                    "홍길동\n"
                    "김철수"
                ),
            }
        ),
        label="엑셀 표 붙여넣기",
        help_text=(
            "번호 열이 없으면 자동으로 빈 번호를 채워 등록합니다. "
            "개인정보 최소화를 위해 학생 이름 대신 익명 번호 사용을 권장합니다. "
            "(예: 1번, 2번, 3번) "
            "이름·학번·연락처 등 개인을 식별할 수 있는 정보는 입력하지 마세요. "
            "학운위 심의 및 내부 절차 적용 여부는 학교 정책에 따라 확인해 주세요."
        ),
    )

    students_csv = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "w-full px-4 py-3 rounded-xl border border-gray-200 bg-white text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 file:px-3 file:py-2 file:font-semibold file:text-gray-700 hover:file:bg-gray-200",
                "accept": ".csv,text/csv",
            }
        ),
        label="CSV 업로드",
        help_text="UTF-8 또는 CP949 인코딩의 .csv 파일을 업로드하세요. (번호,이름 또는 이름)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parsed_students = []

    def clean(self):
        cleaned_data = super().clean()
        pasted_text = (cleaned_data.get("students_paste") or "").strip()
        csv_file = cleaned_data.get("students_csv")

        if not pasted_text and not csv_file:
            raise forms.ValidationError("엑셀 표 붙여넣기 또는 CSV 업로드 중 하나는 입력해 주세요.")

        parsed_rows = []
        if pasted_text:
            parsed_rows.extend(self._parse_pasted_text(pasted_text))
        if csv_file:
            if not csv_file.name.lower().endswith(".csv"):
                self.add_error("students_csv", "CSV 파일(.csv)만 업로드할 수 있습니다.")
            else:
                try:
                    parsed_rows.extend(self._parse_csv_file(csv_file))
                except UnicodeDecodeError:
                    self.add_error(
                        "students_csv",
                        "CSV 인코딩을 읽지 못했습니다. UTF-8 또는 CP949로 저장해 주세요.",
                    )

        parsed_students = []
        for row in parsed_rows:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            parsed_students.append(
                {
                    "number": row.get("number"),
                    "name": name,
                }
            )

        if not parsed_students and not self.errors:
            raise forms.ValidationError(
                "등록 가능한 학생 행이 없습니다. 붙여넣기 내용 또는 CSV 형식을 확인해 주세요."
            )

        self._parsed_students = parsed_students
        return cleaned_data

    def parse_students(self):
        return list(self._parsed_students)

    def _parse_csv_file(self, file_obj):
        raw = file_obj.read()
        try:
            file_obj.seek(0)
        except Exception:
            pass

        decoded = None
        for encoding in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                decoded = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise UnicodeDecodeError("csv", raw, 0, 1, "unsupported encoding")

        rows = []
        reader = csv.reader(io.StringIO(decoded))
        for record in reader:
            parsed = self._parse_cells([(cell or "").strip() for cell in record])
            if parsed:
                rows.append(parsed)
        return rows

    def _parse_pasted_text(self, text):
        rows = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if "\t" in line:
                cells = [cell.strip() for cell in line.split("\t")]
            elif "," in line:
                cells = [cell.strip() for cell in line.split(",")]
            else:
                cells = [line]

            parsed = self._parse_cells(cells)
            if parsed:
                rows.append(parsed)
        return rows

    def _parse_cells(self, cells):
        cleaned = [cell.strip() for cell in cells if cell is not None]
        while cleaned and not cleaned[-1]:
            cleaned.pop()
        if not cleaned:
            return None

        first = cleaned[0]
        second = cleaned[1] if len(cleaned) > 1 else ""
        if self._is_header_row(first, second):
            return None

        number_from_first = self._extract_number(first)
        number_from_second = self._extract_number(second)

        if number_from_first is not None and second:
            return {"number": number_from_first, "name": second}
        if number_from_second is not None and first:
            return {"number": number_from_second, "name": first}
        if len(cleaned) >= 2 and first:
            return {"number": None, "name": first}

        return self._parse_single_value(first)

    def _parse_single_value(self, value):
        text = (value or "").strip()
        if not text or self._is_header_text(text):
            return None

        match = re.match(r"^(\d+)\s*번?\s+(.+)$", text)
        if match:
            return {"number": int(match.group(1)), "name": match.group(2).strip()}

        return {"number": None, "name": text}

    def _extract_number(self, value):
        text = (value or "").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        matched = re.match(r"^(\d+)\s*번?$", text)
        if matched:
            return int(matched.group(1))
        return None

    def _normalize_header(self, value):
        return (value or "").strip().lower().replace(" ", "").replace("_", "")

    def _is_header_text(self, value):
        token = self._normalize_header(value)
        return token in self.NUMBER_HEADER_TOKENS or token in self.NAME_HEADER_TOKENS

    def _is_header_row(self, first, second):
        first_token = self._normalize_header(first)
        second_token = self._normalize_header(second)
        if not first_token:
            return False
        if first_token in self.NUMBER_HEADER_TOKENS and second_token in self.NAME_HEADER_TOKENS:
            return True
        if first_token in self.NAME_HEADER_TOKENS and second_token in self.NUMBER_HEADER_TOKENS:
            return True
        if first_token in self.NUMBER_HEADER_TOKENS and not second_token:
            return True
        if first_token in self.NAME_HEADER_TOKENS and not second_token:
            return True
        return False


class HSActivityForm(forms.ModelForm):
    class Meta:
        model = HSActivity
        fields = ["title", "description", "threshold_score", "extra_bloom_count"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "placeholder": "예: 3월 수학 단원평가",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "rows": "2",
                    "placeholder": "활동 설명 (선택)",
                }
            ),
            "threshold_score": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "0",
                    "max": "100",
                }
            ),
            "extra_bloom_count": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-purple-300",
                    "min": "1",
                    "max": "10",
                }
            ),
        }
