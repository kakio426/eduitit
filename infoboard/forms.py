from django import forms
from django.core.exceptions import ValidationError

from handoff.models import HandoffRosterGroup
from handoff.shared_roster import infoboard_submitter_choices

from .models import Board, Card, CardComment, Collection, Tag


class CollectionForm(forms.ModelForm):
    """컬렉션 생성/수정 폼."""
    class Meta:
        model = Collection
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '컬렉션 이름',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': '컬렉션 설명 (선택)',
                'rows': 2,
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
        }

class BoardForm(forms.ModelForm):
    """보드 생성/수정 폼."""
    tag_names = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='쉼표로 구분된 태그 이름',
    )
    shared_roster_group = forms.ModelChoiceField(
        required=False,
        queryset=HandoffRosterGroup.objects.none(),
        empty_label="연결 안 함",
        label="공용 명부",
        widget=forms.Select(
            attrs={
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
            }
        ),
    )

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is None and self.instance and self.instance.pk:
            owner = self.instance.owner
        if owner is not None:
            self.fields['shared_roster_group'].queryset = HandoffRosterGroup.objects.filter(
                owner=owner
            ).order_by('-is_favorite', 'name')
        self.fields['shared_roster_group'].label_from_instance = lambda group: group.name

    class Meta:
        model = Board
        fields = ['title', 'description', 'icon', 'color_theme', 'layout', 'is_public', 'allow_student_submit', 'shared_roster_group']
        labels = {
            'title': '보드 이름',
            'description': '설명',
            'icon': '아이콘',
            'color_theme': '색상',
            'layout': '보기 방식',
            'is_public': '공개 열람 허용',
            'allow_student_submit': '학생 제출 허용',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '보드 이름을 입력하세요',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': '보드 설명 (선택)',
                'rows': 3,
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'icon': forms.HiddenInput(),
            'color_theme': forms.HiddenInput(),
            'layout': forms.RadioSelect(choices=Board.LAYOUT_CHOICES),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500',
            }),
            'allow_student_submit': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500',
            }),
        }

    def save_with_tags(self, owner):
        board = self.save(commit=False)
        board.owner = owner
        board.save()
        self.save_m2m()

        # 태그 처리
        tag_names_raw = self.cleaned_data.get('tag_names', '')
        if tag_names_raw.strip():
            names = [n.strip() for n in tag_names_raw.split(',') if n.strip()]
            board.tags.clear()
            for name in names:
                tag, _ = Tag.objects.get_or_create(owner=owner, name=name)
                board.tags.add(tag)
        else:
            board.tags.clear()
        return board


class CardForm(forms.ModelForm):
    """카드 생성/수정 폼."""
    tag_names = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='쉼표로 구분된 태그 이름',
    )

    class Meta:
        model = Card
        fields = ['card_type', 'title', 'content', 'url', 'file', 'image', 'color']
        labels = {
            'title': '제목',
            'content': '메모 / 내용',
            'url': 'URL',
            'file': '파일',
            'image': '이미지',
        }
        widgets = {
            'card_type': forms.HiddenInput(),
            'title': forms.TextInput(attrs={
                'placeholder': '카드 제목',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'content': forms.Textarea(attrs={
                'placeholder': '내용을 입력하세요',
                'rows': 4,
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'url': forms.URLInput(attrs={
                'placeholder': 'https://example.com',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-purple-100 file:text-purple-600 hover:file:bg-purple-200',
            }),
            'image': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-green-100 file:text-green-600 hover:file:bg-green-200',
            }),
            'color': forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        card_type = cleaned.get('card_type', 'text')
        if card_type == 'link' and not cleaned.get('url'):
            self.add_error('url', '링크 URL을 입력해주세요.')
        if card_type == 'file' and not cleaned.get('file') and not self.instance.pk:
            self.add_error('file', '파일을 업로드해주세요.')
        if card_type == 'image' and not cleaned.get('image') and not self.instance.pk:
            self.add_error('image', '이미지를 업로드해주세요.')
        return cleaned

    def save_with_tags(self, board, author_user=None, author_name=''):
        card = self.save(commit=False)
        card.board = board
        card.author_user = author_user
        card.author_name = author_name
        if card.card_type != 'link':
            card.url = ''
            card.og_title = ''
            card.og_description = ''
            card.og_image = ''
            card.og_site_name = ''
        if card.card_type != 'file':
            card.file = None
            card.original_filename = ''
            card.file_size = 0
        if card.card_type != 'image':
            card.image = None
        if self.files.get('file'):
            card.original_filename = card.file.name
            card.file_size = card.file.size
        card.save()
        self.save_m2m()

        tag_names_raw = self.cleaned_data.get('tag_names', '')
        owner = board.owner
        if tag_names_raw.strip():
            names = [n.strip() for n in tag_names_raw.split(',') if n.strip()]
            card.tags.clear()
            for name in names:
                tag, _ = Tag.objects.get_or_create(owner=owner, name=name)
                card.tags.add(tag)
        else:
            card.tags.clear()
        return card


class StudentCardForm(forms.ModelForm):
    """학생 카드 제출 폼 (비로그인)."""
    author_name = forms.CharField(
        max_length=100,
        label='이름',
        widget=forms.TextInput(attrs={
            'placeholder': '이름을 입력하세요',
            'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
        }),
    )

    def __init__(self, *args, board=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.board = board
        if board and board.shared_roster_group_id:
            choices = infoboard_submitter_choices(board.shared_roster_group)
            if choices:
                self.fields['author_name'] = forms.ChoiceField(
                    choices=[('', '제출자 선택')] + choices,
                    label='제출자',
                    widget=forms.Select(
                        attrs={
                            'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
                        }
                    ),
                )

    class Meta:
        model = Card
        fields = ['card_type', 'title', 'content', 'url', 'file', 'image']
        labels = {
            'author_name': '이름',
            'title': '제목',
            'content': '내용',
            'url': 'URL',
            'file': '파일',
            'image': '이미지',
        }
        widgets = {
            'card_type': forms.HiddenInput(),
            'title': forms.TextInput(attrs={
                'placeholder': '제목',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'content': forms.Textarea(attrs={
                'placeholder': '내용',
                'rows': 3,
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'url': forms.URLInput(attrs={
                'placeholder': 'https://...',
                'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-300',
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-purple-100 file:text-purple-600 hover:file:bg-purple-200',
            }),
            'image': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-bold file:bg-green-100 file:text-green-600 hover:file:bg-green-200',
            }),
        }

    def clean(self):
        cleaned = super().clean()
        card_type = cleaned.get('card_type', 'text')
        if card_type == 'link' and not cleaned.get('url'):
            self.add_error('url', '링크 URL을 입력해주세요.')
        if card_type == 'file' and not cleaned.get('file'):
            self.add_error('file', '파일을 업로드해주세요.')
        if card_type == 'image' and not cleaned.get('image'):
            self.add_error('image', '이미지를 업로드해주세요.')
        return cleaned

    def save_for_board(self, board):
        card = self.save(commit=False)
        card.board = board
        card.author_name = self.cleaned_data['author_name']
        if card.card_type != 'link':
            card.url = ''
            card.og_title = ''
            card.og_description = ''
            card.og_image = ''
            card.og_site_name = ''
        if card.card_type != 'file':
            card.file = None
            card.original_filename = ''
            card.file_size = 0
        if card.card_type != 'image':
            card.image = None
        if self.files.get('file'):
            card.original_filename = card.file.name
            card.file_size = card.file.size
        card.save()
        self.save_m2m()
        return card


class CardCommentForm(forms.ModelForm):
    """카드 댓글 폼."""

    def __init__(self, *args, require_name=False, **kwargs):
        self.require_name = require_name
        super().__init__(*args, **kwargs)
        if not require_name:
            self.fields.pop('author_name', None)
        else:
            self.fields['author_name'].required = True
            self.fields['author_name'].error_messages['required'] = '이름을 입력해주세요.'
            self.fields['author_name'].widget.attrs.update({
                'placeholder': '이름',
            })
        self.fields['content'].error_messages['required'] = '댓글 내용을 입력해주세요.'
        self.fields['content'].widget.attrs.update({
            'placeholder': '댓글을 남겨보세요',
        })

    class Meta:
        model = CardComment
        fields = ['author_name', 'content']
        labels = {
            'author_name': '이름',
            'content': '댓글',
        }
        widgets = {
            'author_name': forms.TextInput(attrs={
                'class': 'ib-comment-input',
                'maxlength': 100,
            }),
            'content': forms.Textarea(attrs={
                'class': 'ib-comment-textarea',
                'rows': 3,
                'maxlength': 300,
            }),
        }

    def clean_author_name(self):
        author_name = (self.cleaned_data.get('author_name') or '').strip()
        if self.require_name and not author_name:
            raise ValidationError('이름을 입력해주세요.')
        return author_name

    def clean_content(self):
        content = (self.cleaned_data.get('content') or '').strip()
        if not content:
            raise ValidationError('댓글 내용을 입력해주세요.')
        return content

    def save_for_card(self, card, *, author_user=None, author_name=''):
        comment = self.save(commit=False)
        comment.card = card
        comment.author_user = author_user
        comment.author_name = author_name or self.cleaned_data.get('author_name', '')
        comment.content = self.cleaned_data['content']
        comment.save()
        return comment
