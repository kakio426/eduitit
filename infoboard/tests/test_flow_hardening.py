from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from infoboard.models import Board, Card, Collection, SharedLink


User = get_user_model()


class InfoBoardFlowHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teacher',
            email='teacher@example.com',
            password='pass1234',
            first_name='Teacher',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = 'teacher-flow'
        profile.role = 'school'
        profile.save(update_fields=['nickname', 'role'])
        self.client.force_login(self.user)

    def _hx_headers(self, current_path='/infoboard/'):
        return {
            'HTTP_HX_REQUEST': 'true',
            'HTTP_HX_CURRENT_URL': f'http://testserver{current_path}',
        }

    def _board(self, title='기본 보드', **kwargs):
        defaults = {
            'owner': self.user,
            'title': title,
        }
        defaults.update(kwargs)
        return Board.objects.create(**defaults)

    def _collection(self, title='기본 컬렉션', **kwargs):
        defaults = {
            'owner': self.user,
            'title': title,
        }
        defaults.update(kwargs)
        return Collection.objects.create(**defaults)

    def _file_card(self, board, title='파일 카드', content=''):
        uploaded = SimpleUploadedFile('guide.txt', b'hello world', content_type='text/plain')
        return Card.objects.create(
            board=board,
            title=title,
            card_type='file',
            content=content,
            file=uploaded,
            original_filename='guide.txt',
            file_size=len(b'hello world'),
        )

    def test_board_create_invalid_htmx_keeps_modal_errors(self):
        response = self.client.post(
            reverse('infoboard:board_create'),
            data={
                'description': '설명만 보냄',
                'icon': '📌',
                'color_theme': 'purple',
                'layout': 'grid',
                'tag_names': '',
            },
            **self._hx_headers('/infoboard/'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '입력값을 다시 확인해주세요.')
        self.assertNotIn('HX-Trigger-After-Swap', response.headers)

    def test_board_create_htmx_refreshes_grid_and_closes_modal(self):
        response = self.client.post(
            reverse('infoboard:board_create'),
            data={
                'preset': 'submit',
                'title': '새 보드',
                'description': '대시보드에서 만든 보드',
            },
            **self._hx_headers('/infoboard/'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['HX-Retarget'], '#ibBoardGrid')
        self.assertEqual(response.headers['HX-Reswap'], 'innerHTML')
        self.assertIn('infoboard:close-modal', response.headers['HX-Trigger-After-Swap'])
        self.assertContains(response, '새 보드')
        board = Board.objects.get(owner=self.user, title='새 보드')
        self.assertTrue(board.allow_student_submit)
        self.assertEqual(board.shared_links.filter(is_active=True, access_level='submit').count(), 1)

    def test_dashboard_prioritizes_collecting_recent_and_draft_sections(self):
        collecting = self._board(title='수집 중 보드', allow_student_submit=True)
        recent = self._board(title='최근 제출 보드')
        draft = self._board(title='초안 보드')
        SharedLink.objects.create(board=collecting, created_by=self.user, access_level='submit')
        Card.objects.create(
            board=collecting,
            title='학생 제출 1',
            card_type='text',
            content='제출 내용',
            author_name='학생A',
        )
        Card.objects.create(
            board=recent,
            title='학생 제출 2',
            card_type='text',
            content='최근 제출',
            author_name='학생B',
        )

        response = self.client.get(reverse('infoboard:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '새 제출보드')
        self.assertContains(response, '제출받는 중')
        self.assertContains(response, '최근 제출 있음')
        self.assertContains(response, '초안')
        self.assertContains(response, '수집 중 보드')
        self.assertContains(response, '최근 제출 보드')
        self.assertContains(response, '초안 보드')
        self.assertNotContains(response, '내 보드')

    def test_board_edit_from_detail_redirects_back_to_current_detail(self):
        board = self._board(title='원래 제목')
        current_path = reverse('infoboard:board_detail', args=[board.id]) + '?q=alpha'

        invalid_response = self.client.post(
            reverse('infoboard:board_edit', args=[board.id]),
            data={
                'title': '',
                'description': '설명',
                'icon': board.icon,
                'color_theme': board.color_theme,
                'layout': board.layout,
                'tag_names': '',
            },
            **self._hx_headers(current_path),
        )

        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, '입력값을 다시 확인해주세요.')

        response = self.client.post(
            reverse('infoboard:board_edit', args=[board.id]),
            data={
                'title': '수정된 제목',
                'description': '설명',
                'icon': board.icon,
                'color_theme': board.color_theme,
                'layout': board.layout,
                'tag_names': '',
            },
            **self._hx_headers(current_path),
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['HX-Redirect'], current_path)
        board.refresh_from_db()
        self.assertEqual(board.title, '수정된 제목')

    def test_collection_create_and_edit_htmx_flow(self):
        invalid_create = self.client.post(
            reverse('infoboard:collection_create'),
            data={'title': '', 'description': ''},
            **self._hx_headers('/infoboard/?tab=collections'),
        )

        self.assertEqual(invalid_create.status_code, 200)
        self.assertContains(invalid_create, '입력값을 다시 확인해주세요.')

        create_response = self.client.post(
            reverse('infoboard:collection_create'),
            data={'title': '새 컬렉션', 'description': ''},
            **self._hx_headers('/infoboard/?tab=collections'),
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.headers['HX-Retarget'], '#ibCollectionGrid')
        self.assertIn('infoboard:close-modal', create_response.headers['HX-Trigger-After-Swap'])
        collection = Collection.objects.get(owner=self.user, title='새 컬렉션')

        board = self._board(title='묶을 보드')
        edit_path = reverse('infoboard:collection_detail', args=[collection.id])
        invalid_edit = self.client.post(
            reverse('infoboard:collection_edit', args=[collection.id]),
            data={
                'title': '',
                'description': '설명',
                'board_ids': [str(board.id)],
            },
            **self._hx_headers(edit_path),
        )

        self.assertEqual(invalid_edit.status_code, 200)
        self.assertContains(invalid_edit, '입력값을 다시 확인해주세요.')

        edit_response = self.client.post(
            reverse('infoboard:collection_edit', args=[collection.id]),
            data={
                'title': '수정된 컬렉션',
                'description': '설명',
                'board_ids': [str(board.id)],
            },
            **self._hx_headers(edit_path),
        )

        self.assertEqual(edit_response.status_code, 204)
        self.assertEqual(edit_response.headers['HX-Redirect'], edit_path)
        collection.refresh_from_db()
        self.assertEqual(collection.title, '수정된 컬렉션')
        self.assertEqual(collection.boards.count(), 1)

    def test_card_create_invalid_and_success_htmx_flow(self):
        board = self._board(title='카드 보드')

        invalid_response = self.client.post(
            reverse('infoboard:card_add', args=[board.id]),
            data={
                'card_type': 'link',
                'title': '링크 카드',
                'content': '',
                'url': '',
                'color': '',
                'tag_names': '',
            },
            **self._hx_headers(reverse('infoboard:board_detail', args=[board.id])),
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, '링크 URL을 입력해주세요.')
        self.assertNotIn('HX-Trigger-After-Swap', invalid_response.headers)

        with patch('infoboard.utils.fetch_url_meta', return_value={'og_title': 'OG 제목', 'og_site_name': 'example.com'}):
            success_response = self.client.post(
                reverse('infoboard:card_add', args=[board.id]),
                data={
                    'card_type': 'link',
                    'title': '링크 카드',
                    'content': '',
                    'url': 'https://example.com',
                    'color': '',
                    'tag_names': '',
                },
                **self._hx_headers(reverse('infoboard:board_detail', args=[board.id])),
            )

        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(success_response.headers['HX-Retarget'], '#ibCardGrid')
        self.assertIn('infoboard:close-modal', success_response.headers['HX-Trigger-After-Swap'])
        self.assertContains(success_response, '링크 카드')
        card = board.cards.get(title='링크 카드')

        invalid_edit = self.client.post(
            reverse('infoboard:card_edit', args=[card.id]),
            data={
                'card_type': 'link',
                'title': '링크 카드',
                'content': '',
                'url': '',
                'color': '',
                'tag_names': '',
            },
            **self._hx_headers(reverse('infoboard:board_detail', args=[board.id])),
        )

        self.assertEqual(invalid_edit.status_code, 200)
        self.assertContains(invalid_edit, '링크 URL을 입력해주세요.')
        self.assertEqual(board.cards.filter(title='링크 카드').count(), 1)

    def test_board_and_collection_delete_refresh_their_grids(self):
        board = self._board(title='삭제 보드')
        board_response = self.client.post(
            reverse('infoboard:board_delete', args=[board.id]),
            data={},
            **self._hx_headers('/infoboard/'),
        )
        self.assertEqual(board_response.status_code, 200)
        self.assertEqual(board_response.headers['HX-Retarget'], '#ibBoardGrid')
        self.assertContains(board_response, '첫 제출보드를 만들면 바로 링크까지 준비돼요')
        self.assertFalse(Board.objects.filter(id=board.id).exists())

        board = self._board(title='컬렉션 보드')
        collection = self._collection(title='묶음')
        collection.boards.add(board)
        collection_path = reverse('infoboard:collection_detail', args=[collection.id])
        collection_response = self.client.post(
            reverse('infoboard:board_delete', args=[board.id]),
            data={},
            **self._hx_headers(collection_path),
        )

        self.assertEqual(collection_response.status_code, 200)
        self.assertContains(collection_response, '이 컬렉션에 보드가 없어요')
        self.assertFalse(Board.objects.filter(id=board.id).exists())
        collection.delete()

        extra_collection = self._collection(title='삭제할 컬렉션')
        collection_grid_response = self.client.post(
            reverse('infoboard:collection_delete', args=[extra_collection.id]),
            data={},
            **self._hx_headers('/infoboard/?tab=collections'),
        )

        self.assertEqual(collection_grid_response.status_code, 200)
        self.assertEqual(collection_grid_response.headers['HX-Retarget'], '#ibCollectionGrid')
        self.assertContains(collection_grid_response, '아직 컬렉션이 없어요')
        self.assertFalse(Collection.objects.filter(id=extra_collection.id).exists())

    def test_download_access_rules_cover_owner_public_and_share_link(self):
        private_board = self._board(title='비공개 보드')
        private_card = self._file_card(private_board, title='비공개 파일')
        public_board = self._board(title='공개 보드', is_public=True)
        public_card = self._file_card(public_board, title='공개 파일')
        shared_board = self._board(title='공유 보드')
        shared_card = self._file_card(shared_board, title='공유 파일')
        shared_link = SharedLink.objects.create(board=shared_board, created_by=self.user, access_level='view')

        owner_response = self.client.get(reverse('infoboard:card_download', args=[private_card.id]))
        self.assertEqual(owner_response.status_code, 200)
        self.assertIn('attachment; filename="guide.txt"', owner_response['Content-Disposition'])

        self.client.logout()
        public_response = self.client.get(reverse('infoboard:card_download', args=[public_card.id]))
        self.assertEqual(public_response.status_code, 200)

        shared_response = self.client.get(
            reverse('infoboard:card_download', args=[shared_card.id]),
            data={'link_id': str(shared_link.id)},
        )
        self.assertEqual(shared_response.status_code, 200)

    def test_student_submit_requires_board_flag_and_accepts_valid_link(self):
        board = self._board(title='학생 제출 보드')
        shared_link = SharedLink.objects.create(board=board, created_by=self.user, access_level='submit')
        submit_url = reverse('infoboard:student_submit', args=[shared_link.id])

        self.client.logout()
        self.assertEqual(self.client.get(submit_url).status_code, 404)

        board.allow_student_submit = True
        board.save(update_fields=['allow_student_submit'])

        shared_link.access_level = 'view'
        shared_link.save(update_fields=['access_level'])
        self.assertEqual(self.client.get(submit_url).status_code, 404)

        shared_link.access_level = 'submit'
        shared_link.save(update_fields=['access_level'])

        get_response = self.client.get(submit_url)
        self.assertEqual(get_response.status_code, 200)

        invalid_post = self.client.post(
            submit_url,
            data={
                'author_name': '학생',
                'card_type': 'link',
                'title': '제출 링크',
                'content': '',
                'url': '',
            },
            **self._hx_headers(reverse('infoboard:public_board', args=[shared_link.id])),
        )
        self.assertEqual(invalid_post.status_code, 200)
        self.assertContains(invalid_post, '링크 URL을 입력해주세요.')

    def test_student_submit_htmx_refreshes_public_wall_and_closes_sheet(self):
        board = self._board(title='협업 월', allow_student_submit=True)
        shared_link = SharedLink.objects.create(board=board, created_by=self.user, access_level='submit')
        submit_url = reverse('infoboard:student_submit', args=[shared_link.id])

        self.client.logout()
        response = self.client.post(
            submit_url,
            data={
                'author_name': '학생',
                'card_type': 'text',
                'title': '새 제출 카드',
                'content': '안녕하세요',
            },
            **self._hx_headers(reverse('infoboard:public_board', args=[shared_link.id])),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['HX-Retarget'], '#ibPublicWall')
        self.assertEqual(response.headers['HX-Reswap'], 'innerHTML')
        self.assertIn('infoboard:close-submit-sheet', response.headers['HX-Trigger-After-Swap'])
        self.assertContains(response, '새 제출 카드')
        self.assertEqual(board.cards.filter(title='새 제출 카드', author_name='학생').count(), 1)

    def test_board_detail_prefers_single_primary_share_action(self):
        board = self._board(title='운영 보드', allow_student_submit=True)
        shared_link = SharedLink.objects.create(board=board, created_by=self.user, access_level='submit')

        response = self.client.get(reverse('infoboard:board_detail', args=[board.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '제출 링크 복사')
        self.assertContains(response, str(shared_link.board.access_code))
        self.assertContains(response, '학생 제출')

    def test_fetch_og_meta_rejects_unsafe_urls_and_returns_safe_payload(self):
        unsafe_response = self.client.get(
            reverse('infoboard:fetch_og_meta'),
            data={'url': 'http://localhost:8000/path'},
        )
        self.assertEqual(unsafe_response.status_code, 400)
        self.assertIn('error', unsafe_response.json())

        with patch('core.news_ingest.assert_safe_public_url', return_value='https://example.com/path'), patch(
            'infoboard.utils.fetch_url_meta',
            return_value={'og_title': '예제 제목', 'og_site_name': 'example.com'},
        ):
            safe_response = self.client.get(
                reverse('infoboard:fetch_og_meta'),
                data={'url': 'https://example.com/path'},
            )

        self.assertEqual(safe_response.status_code, 200)
        self.assertEqual(safe_response.json()['og_title'], '예제 제목')
