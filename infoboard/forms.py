from django import forms

from .models import Board, Card, CardComment, Collection, SharedLink, Tag


BOARD_TEMPLATE_PRESETS = {
    "question": {
        "label": "질문 모음",
        "description": "학생 질문과 궁금한 점을 차곡차곡 모으는 보드",
        "icon": "❓",
        "color_theme": "blue",
        "layout": "list",
        "is_public": False,
        "allow_student_submit": True,
        "moderation_mode": "manual",
        "share_mode": "submit",
    },
    "brainstorm": {
        "label": "브레인스토밍",
        "description": "수업 아이디어를 빠르게 모으고 분류하는 보드",
        "icon": "💡",
        "color_theme": "orange",
        "layout": "grid",
        "is_public": False,
        "allow_student_submit": True,
        "moderation_mode": "manual",
        "share_mode": "submit",
    },
    "exit_ticket": {
        "label": "출구표",
        "description": "수업이 끝날 때 배운 점과 질문을 정리하는 보드",
        "icon": "🎫",
        "color_theme": "green",
        "layout": "list",
        "is_public": False,
        "allow_student_submit": True,
        "moderation_mode": "manual",
        "share_mode": "submit",
    },
    "file_submit": {
        "label": "파일 제출",
        "description": "과제 파일과 사진을 한곳에 모아 받는 보드",
        "icon": "📎",
        "color_theme": "dark",
        "layout": "list",
        "is_public": False,
        "allow_student_submit": True,
        "moderation_mode": "manual",
        "share_mode": "submit",
    },
    "reading_response": {
        "label": "읽기 반응",
        "description": "읽고 느낀 점과 핵심 문장을 공유하는 보드",
        "icon": "📚",
        "color_theme": "purple",
        "layout": "grid",
        "is_public": False,
        "allow_student_submit": True,
        "moderation_mode": "manual",
        "share_mode": "comment",
    },
}


BOARD_SHARE_CHOICES = [
    ("private", "교사만 사용"),
    ("view", "읽기"),
    ("comment", "댓글·반응"),
    ("submit", "제출"),
    ("edit", "관리"),
]


REACTION_CHOICES = [
    ("like", "👍 좋아요"),
    ("idea", "💡 아이디어"),
    ("question", "❓ 질문"),
]


class CollectionForm(forms.ModelForm):
    """Collection create/update form."""

    class Meta:
        model = Collection
        fields = ["title", "description"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "컬렉션 이름",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "placeholder": "컬렉션 설명 (선택)",
                    "rows": 2,
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
        }


class BoardForm(forms.ModelForm):
    """Board create/update form with teacher-friendly presets."""

    template_preset = forms.ChoiceField(
        required=False,
        initial="question",
        choices=[(key, value["label"]) for key, value in BOARD_TEMPLATE_PRESETS.items()],
        widget=forms.RadioSelect(),
        label="시작 템플릿",
    )
    share_mode = forms.ChoiceField(
        required=False,
        initial="private",
        choices=BOARD_SHARE_CHOICES,
        widget=forms.RadioSelect(),
        label="공유 방식",
    )
    tag_names = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="쉼표로 구분된 태그 이름",
    )

    class Meta:
        model = Board
        fields = [
            "title",
            "description",
            "icon",
            "color_theme",
            "layout",
            "moderation_mode",
            "is_public",
            "allow_student_submit",
        ]
        labels = {
            "title": "보드 이름",
            "description": "설명",
            "icon": "아이콘",
            "color_theme": "색상",
            "layout": "보기 방식",
            "moderation_mode": "게시 방식",
            "is_public": "공개 열람 허용",
            "allow_student_submit": "학생 제출 허용",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "예: 3학년 과학 질문 모음",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "placeholder": "수업에서 이 보드를 어떻게 쓸지 짧게 적어보세요.",
                    "rows": 3,
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "icon": forms.HiddenInput(),
            "color_theme": forms.HiddenInput(),
            "moderation_mode": forms.RadioSelect(choices=Board.MODERATION_CHOICES),
            "is_public": forms.CheckboxInput(
                attrs={
                    "class": "mt-1 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500",
                }
            ),
            "allow_student_submit": forms.CheckboxInput(
                attrs={
                    "class": "mt-1 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_share = kwargs.get("initial", {}).get("share_mode")
        if not current_share:
            active_link = getattr(self.instance, "_active_share_link", None)
            if active_link:
                current_share = active_link.access_level
        if current_share:
            self.fields["share_mode"].initial = current_share

    def clean(self):
        cleaned = super().clean()
        preset_key = cleaned.get("template_preset") or "question"
        preset = BOARD_TEMPLATE_PRESETS.get(preset_key)
        if not preset:
            return cleaned

        if not cleaned.get("icon"):
            cleaned["icon"] = preset["icon"]
        if not cleaned.get("color_theme"):
            cleaned["color_theme"] = preset["color_theme"]
        if not cleaned.get("layout"):
            cleaned["layout"] = preset["layout"]
        if not cleaned.get("moderation_mode"):
            cleaned["moderation_mode"] = preset["moderation_mode"]
        if not cleaned.get("description") and not self.instance.pk:
            cleaned["description"] = preset["description"]

        if "is_public" not in self.data and not self.instance.pk:
            cleaned["is_public"] = preset["is_public"]
        if "allow_student_submit" not in self.data and not self.instance.pk:
            cleaned["allow_student_submit"] = preset["allow_student_submit"]

        share_mode = cleaned.get("share_mode") or preset["share_mode"]
        valid_share_modes = {choice[0] for choice in BOARD_SHARE_CHOICES}
        if share_mode not in valid_share_modes:
            share_mode = "private"
        cleaned["share_mode"] = share_mode
        return cleaned

    def save_with_tags(self, owner):
        board = self.save(commit=False)
        board.owner = owner
        board.save()
        self.save_m2m()

        tag_names_raw = self.cleaned_data.get("tag_names", "")
        if tag_names_raw.strip():
            names = [name.strip() for name in tag_names_raw.split(",") if name.strip()]
            board.tags.clear()
            for name in names:
                tag, _ = Tag.objects.get_or_create(owner=owner, name=name)
                board.tags.add(tag)
        else:
            board.tags.clear()
        return board


class CardForm(forms.ModelForm):
    """Teacher card form."""

    tag_names = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="쉼표로 구분된 태그 이름",
    )

    class Meta:
        model = Card
        fields = ["card_type", "title", "content", "url", "file", "image", "color"]
        labels = {
            "title": "제목",
            "content": "메모 / 내용",
            "url": "URL",
            "file": "파일",
            "image": "이미지",
        }
        widgets = {
            "card_type": forms.HiddenInput(),
            "title": forms.TextInput(
                attrs={
                    "placeholder": "카드 제목",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "placeholder": "내용을 입력하세요",
                    "rows": 4,
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "file": forms.FileInput(
                attrs={
                    "class": "w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-purple-100 file:text-purple-600 hover:file:bg-purple-200",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "accept": "image/*",
                    "class": "w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-green-100 file:text-green-600 hover:file:bg-green-200",
                }
            ),
            "color": forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        card_type = cleaned.get("card_type", "text")
        if card_type == "link" and not cleaned.get("url"):
            self.add_error("url", "링크 URL을 입력해주세요.")
        if card_type == "file" and not cleaned.get("file") and not self.instance.pk:
            self.add_error("file", "파일을 업로드해주세요.")
        if card_type == "image" and not cleaned.get("image") and not self.instance.pk:
            self.add_error("image", "이미지를 업로드해주세요.")
        return cleaned

    def save_with_tags(self, board, author_user=None, author_name="", status="published"):
        card = self.save(commit=False)
        card.board = board
        card.author_user = author_user
        card.author_name = author_name
        card.status = status
        if card.card_type != "link":
            card.url = ""
            card.og_title = ""
            card.og_description = ""
            card.og_image = ""
            card.og_site_name = ""
        if card.card_type != "file":
            card.file = None
            card.original_filename = ""
            card.file_size = 0
        if card.card_type != "image":
            card.image = None
        if self.files.get("file"):
            card.original_filename = card.file.name
            card.file_size = card.file.size
        card.save()
        self.save_m2m()

        tag_names_raw = self.cleaned_data.get("tag_names", "")
        owner = board.owner
        if tag_names_raw.strip():
            names = [name.strip() for name in tag_names_raw.split(",") if name.strip()]
            card.tags.clear()
            for name in names:
                tag, _ = Tag.objects.get_or_create(owner=owner, name=name)
                card.tags.add(tag)
        else:
            card.tags.clear()
        return card


class StudentCardForm(forms.ModelForm):
    """Student submission form for public boards."""

    author_name = forms.CharField(
        max_length=100,
        label="이름",
        widget=forms.TextInput(
            attrs={
                "placeholder": "이름을 입력하세요",
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )

    class Meta:
        model = Card
        fields = ["card_type", "title", "content", "url", "file", "image"]
        labels = {
            "author_name": "이름",
            "title": "제목",
            "content": "내용",
            "url": "URL",
            "file": "파일",
            "image": "이미지",
        }
        widgets = {
            "card_type": forms.HiddenInput(),
            "title": forms.TextInput(
                attrs={
                    "placeholder": "제목",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "placeholder": "내용",
                    "rows": 3,
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://...",
                    "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300",
                }
            ),
            "file": forms.FileInput(
                attrs={
                    "class": "w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-purple-100 file:text-purple-600 hover:file:bg-purple-200",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "accept": "image/*",
                    "class": "w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-green-100 file:text-green-600 hover:file:bg-green-200",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        card_type = cleaned.get("card_type", "text")
        if card_type == "link" and not cleaned.get("url"):
            self.add_error("url", "링크 URL을 입력해주세요.")
        if card_type == "file" and not cleaned.get("file"):
            self.add_error("file", "파일을 업로드해주세요.")
        if card_type == "image" and not cleaned.get("image"):
            self.add_error("image", "이미지를 업로드해주세요.")
        return cleaned

    def save_for_board(self, board, status="published"):
        card = self.save(commit=False)
        card.board = board
        card.author_name = self.cleaned_data["author_name"]
        card.status = status
        if card.card_type != "link":
            card.url = ""
            card.og_title = ""
            card.og_description = ""
            card.og_image = ""
            card.og_site_name = ""
        if card.card_type != "file":
            card.file = None
            card.original_filename = ""
            card.file_size = 0
        if card.card_type != "image":
            card.image = None
        if self.files.get("file"):
            card.original_filename = card.file.name
            card.file_size = card.file.size
        card.save()
        self.save_m2m()
        return card


class BoardJoinForm(forms.Form):
    """Access-code join form."""

    code = forms.CharField(
        max_length=6,
        min_length=6,
        label="입장 코드",
        widget=forms.TextInput(
            attrs={
                "placeholder": "예: 123456",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "class": "w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/90 text-center tracking-[0.35em] text-lg font-black text-gray-800 uppercase focus:outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )

    def clean_code(self):
        return self.cleaned_data["code"].strip()


class CardCommentForm(forms.Form):
    """Comment form for owner or shared-link viewers."""

    author_name = forms.CharField(
        required=False,
        max_length=100,
        label="이름",
        widget=forms.TextInput(
            attrs={
                "placeholder": "이름",
                "class": "w-full px-3 py-2 rounded-xl bg-slate-50 text-sm font-semibold text-gray-700 outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )
    content = forms.CharField(
        max_length=1000,
        label="댓글",
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "짧게 남겨보세요.",
                "class": "w-full px-3 py-2 rounded-xl bg-slate-50 text-sm font-medium text-gray-700 outline-none focus:ring-2 focus:ring-purple-300",
            }
        ),
    )

    def __init__(self, *args, require_author=False, **kwargs):
        super().__init__(*args, **kwargs)
        if require_author:
            self.fields["author_name"].required = True
            self.fields["author_name"].widget.attrs["placeholder"] = "이름을 입력하세요"


class ShareLinkForm(forms.Form):
    """Simple share-link management form."""

    access_level = forms.ChoiceField(
        choices=[choice for choice in BOARD_SHARE_CHOICES if choice[0] != "private"],
        initial="view",
        widget=forms.RadioSelect(),
    )

    def clean_access_level(self):
        access_level = self.cleaned_data["access_level"]
        valid_levels = {choice[0] for choice in SharedLink.ACCESS_CHOICES}
        if access_level not in valid_levels:
            raise forms.ValidationError("지원하지 않는 공유 방식입니다.")
        return access_level


class ReactionForm(forms.Form):
    """Reaction form with bounded reaction choices."""

    reaction_type = forms.ChoiceField(choices=REACTION_CHOICES)
