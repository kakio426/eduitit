from django import forms

from .models import Board, Card, Collection, Tag


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

    class Meta:
        model = Board
        fields = ['title', 'description', 'icon', 'color_theme', 'layout']
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
        if card.file:
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
        widget=forms.TextInput(attrs={
            'placeholder': '이름을 입력하세요',
            'class': 'w-full px-4 py-3 rounded-2xl shadow-clay-inner bg-white/80 text-gray-700 font-bold focus:outline-none focus:ring-2 focus:ring-purple-300',
        }),
    )

    class Meta:
        model = Card
        fields = ['card_type', 'title', 'content', 'url', 'file', 'image']
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
        }
