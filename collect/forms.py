from django import forms

from .models import CollectionRequest


class CollectionRequestForm(forms.ModelForm):
    class Meta:
        model = CollectionRequest
        fields = [
            "title",
            "description",
            "expected_submitters",
            "allow_file",
            "allow_link",
            "allow_text",
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
                }
            ),
            "max_submissions": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-emerald-500 focus:outline-none",
                    "min": 1,
                    "max": 200,
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
            "deadline": "마감일시",
            "max_submissions": "최대 제출 건수",
            "expected_submitters": "제출 대상자 목록",
            "template_file": "양식 파일",
        }
