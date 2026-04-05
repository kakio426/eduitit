import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import (
    Post,
    TeacherBuddyDailyProgress,
    TeacherBuddySkinUnlock,
    TeacherBuddySocialRewardLog,
    TeacherBuddyState,
    TeacherBuddyUnlock,
    UserProfile,
)
from core.teacher_buddy import (
    HOME_DAILY_SECTION_TARGET,
    LEGENDARY_UNLOCK_DAYS,
    MAX_DRAW_TOKEN_COUNT,
    SNS_SIMILARITY_THRESHOLD,
    TeacherBuddyError,
    _build_draw_groups,
    build_teacher_buddy_settings_context,
    draw_teacher_buddy,
    record_teacher_buddy_progress,
    record_teacher_buddy_sns_reward,
    select_teacher_buddy,
    select_teacher_buddy_profile,
    unlock_teacher_buddy_skin,
)
from core.teacher_buddy_catalog import (
    RARITY_COMMON,
    RARITY_EPIC,
    RARITY_LEGENDARY,
    RARITY_RARE,
    SILHOUETTE_FAMILY_SHEET,
    TOTAL_BUDDY_COUNT,
    TOTAL_SKIN_COUNT,
    all_teacher_buddies,
    get_teacher_buddy_skins_for_buddy,
)
from products.models import Product


def create_onboarded_user(username, *, role="school"):
    user = User.objects.create_user(username=username, email=f"{username}@test.com", password="pass1234")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = role
    profile.save()
    return user


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True, HOME_V2_ENABLED=True)
class TeacherBuddyServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_onboarded_user("buddyuser")
        self.classroom_product = Product.objects.create(
            title="교실 캘린더",
            description="교실 운영",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
        )
        self.doc_product = Product.objects.create(
            title="문서 도구",
            description="문서 작성",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="noticegen:main",
        )
        self.game_product = Product.objects.create(
            title="교실 게임",
            description="게임",
            price=0,
            is_active=True,
            service_type="game",
            launch_route_name="fairy_games:play_reversi",
        )
        self.collect_product = Product.objects.create(
            title="서명 수합",
            description="수합",
            price=0,
            is_active=True,
            service_type="collect_sign",
            launch_route_name="collect:landing",
        )

    def _state(self):
        return TeacherBuddyState.objects.get(user=self.user)

    def _grant_home_ticket(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        record_teacher_buddy_progress(self.user, self.doc_product, "home_section")
        return record_teacher_buddy_progress(self.user, self.game_product, "home_game")

    def _unlock_all_except(self, excluded_keys):
        for buddy in all_teacher_buddies():
            if buddy.key in excluded_keys:
                continue
            TeacherBuddyUnlock.objects.get_or_create(
                user=self.user,
                buddy_key=buddy.key,
                defaults={"rarity": buddy.rarity, "obtained_via": "draw"},
            )

    def test_first_home_progress_creates_starter_without_extra_setup(self):
        payload = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

        self.assertEqual(TeacherBuddyUnlock.objects.filter(user=self.user).count(), 1)
        self.assertEqual(payload["points_today"], 1)
        self.assertEqual(payload["home_progress_text"], "오늘 반짝 조각 1/3")
        self.assertEqual(self._state().draw_token_count, 0)

    def test_same_day_same_section_does_not_duplicate_points(self):
        first = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        second = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

        self.assertEqual(first["points_today"], 1)
        self.assertEqual(second["points_today"], 1)
        self.assertEqual(self._state().total_points_earned, 1)

    def test_home_ticket_requires_three_distinct_sections_and_only_awards_once(self):
        first = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        second = record_teacher_buddy_progress(self.user, self.doc_product, "home_section")
        third = record_teacher_buddy_progress(self.user, self.game_product, "home_game")
        fourth = record_teacher_buddy_progress(self.user, self.collect_product, "home_section")

        self.assertEqual(first["points_today"], 1)
        self.assertEqual(second["points_today"], 2)
        self.assertEqual(third["points_today"], HOME_DAILY_SECTION_TARGET)
        self.assertTrue(third["token_ready"])
        self.assertTrue(third["home_ticket_awarded"])
        self.assertEqual(third["home_ticket_status_text"], "오늘 반짝 조각 완성")
        self.assertEqual(fourth["points_today"], HOME_DAILY_SECTION_TARGET)
        self.assertEqual(self._state().draw_token_count, 1)
        self.assertEqual(self._state().qualifying_day_count, 1)

    def test_qualifying_days_only_increase_on_home_ticket_days(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

        state = self._state()
        self.assertEqual(state.qualifying_day_count, 0)

        self._grant_home_ticket()
        state.refresh_from_db()
        self.assertEqual(state.qualifying_day_count, 1)

    def test_daily_sns_bonus_grants_one_token_once_per_day(self):
        self._grant_home_ticket()
        state = self._state()
        state.draw_token_count = 0
        state.last_sns_bonus_week_key = ""
        state.save(update_fields=["draw_token_count", "last_sns_bonus_week_key"])

        first_post = Post.objects.create(
            author=self.user,
            content="오늘 공개수업 정리를 충분히 길게 남기고 교실 흐름과 아이들 반응까지 함께 기록해 둡니다.",
            post_type="general",
        )
        second_post = Post.objects.create(
            author=self.user,
            content="이번 주에는 한 번 더 남기지만 보너스는 한 번만 받도록 설계된 두 번째 글입니다.",
            post_type="general",
        )

        first = record_teacher_buddy_sns_reward(self.user, first_post)
        second = record_teacher_buddy_sns_reward(self.user, second_post)

        self.assertTrue(first["reward_granted"])
        self.assertEqual(first["draw_token_count"], 1)
        self.assertFalse(second["reward_granted"])
        self.assertIn("오늘 SNS 보너스는 이미 받았어요", second["message"])
        self.assertEqual(
            TeacherBuddySocialRewardLog.objects.filter(user=self.user, reward_granted=True).count(),
            1,
        )

    def test_sns_bonus_resets_on_next_day_key(self):
        self._grant_home_ticket()
        state = self._state()
        state.draw_token_count = 0
        state.last_sns_bonus_week_key = ""
        state.save(update_fields=["draw_token_count", "last_sns_bonus_week_key"])

        first_post = Post.objects.create(
            author=self.user,
            content="오늘 수업 정리를 충분히 길게 남기고 아이들 반응과 교실 분위기까지 자세히 기록해 둡니다.",
            post_type="general",
        )
        first = record_teacher_buddy_sns_reward(self.user, first_post)
        self.assertTrue(first["reward_granted"])

        state.refresh_from_db()
        state.draw_token_count = 0
        state.last_sns_bonus_week_key = "2000-01-01"
        state.save(update_fields=["draw_token_count", "last_sns_bonus_week_key"])

        second_post = Post.objects.create(
            author=self.user,
            content="다음 날에도 다른 수업 정리를 충분히 길게 남기고 활동 흐름과 반응을 새롭게 적어 둡니다.",
            post_type="general",
        )
        second = record_teacher_buddy_sns_reward(self.user, second_post)

        self.assertTrue(second["reward_granted"])
        self.assertEqual(second["draw_token_count"], 1)

    def test_sns_reward_rejects_short_similar_and_exact_repeat_posts(self):
        short_post = Post.objects.create(author=self.user, content="짧아요", post_type="general")
        short_payload = record_teacher_buddy_sns_reward(self.user, short_post)
        self.assertFalse(short_payload["reward_granted"])

        valid_text = "오늘 공개수업 정리를 충분히 길게 남기고 교실 흐름과 아이들 반응까지 함께 기록해 둡니다."
        valid_post = Post.objects.create(author=self.user, content=valid_text, post_type="general")
        valid_payload = record_teacher_buddy_sns_reward(self.user, valid_post)
        self.assertTrue(valid_payload["reward_granted"])

        state = self._state()
        state.last_sns_bonus_week_key = ""
        state.save(update_fields=["last_sns_bonus_week_key"])
        valid_post.delete()

        repeat_post = Post.objects.create(author=self.user, content=valid_text, post_type="general")
        repeat_payload = record_teacher_buddy_sns_reward(self.user, repeat_post)
        self.assertFalse(repeat_payload["reward_granted"])
        self.assertIn("30일", repeat_payload["message"])

        state.last_sns_bonus_week_key = ""
        state.save(update_fields=["last_sns_bonus_week_key"])
        with patch("core.teacher_buddy._similarity_ratio", return_value=SNS_SIMILARITY_THRESHOLD + 0.05):
            similar_post = Post.objects.create(
                author=self.user,
                content="오늘 공개수업 정리를 길게 다시 남기고 교실 흐름과 아이들 반응까지 비슷하게 기록해 둡니다.",
                post_type="general",
            )
            similar_payload = record_teacher_buddy_sns_reward(self.user, similar_post)

        self.assertFalse(similar_payload["reward_granted"])
        self.assertIn("너무 비슷", similar_payload["message"])

    def test_sns_reward_ignores_non_general_posts(self):
        post = Post.objects.create(
            author=self.user,
            content="공지 글은 메이트 보상을 주지 않습니다. 그래도 충분히 길게 적어 둡니다.",
            post_type="insight",
        )

        payload = record_teacher_buddy_sns_reward(self.user, post)

        self.assertIsNone(payload)
        self.assertFalse(TeacherBuddySocialRewardLog.objects.filter(user=self.user).exists())

    def test_legendary_is_absent_before_60_days(self):
        self._grant_home_ticket()
        state = self._state()
        starter_key = state.active_buddy_key
        self._unlock_all_except({starter_key, "board_lighthouse"})
        state.qualifying_day_count = LEGENDARY_UNLOCK_DAYS - 1
        state.save(update_fields=["qualifying_day_count"])

        grouped = _build_draw_groups(user=self.user, state=state)

        self.assertEqual(grouped[RARITY_LEGENDARY], [])
        self.assertTrue(grouped[RARITY_COMMON])
        self.assertTrue(grouped[RARITY_RARE])
        self.assertTrue(grouped[RARITY_EPIC])

    def test_legendary_stays_probabilistic_after_60_days_even_with_repeat_pool(self):
        self._grant_home_ticket()
        state = self._state()
        starter_key = state.active_buddy_key
        self._unlock_all_except({starter_key, "board_lighthouse"})
        state.qualifying_day_count = LEGENDARY_UNLOCK_DAYS
        state.draw_token_count = 1
        state.save(update_fields=["qualifying_day_count", "draw_token_count"])

        captured = {}

        def fake_choices(choices, weights, k):
            captured["choices"] = list(choices)
            captured["weights"] = list(weights)
            return [RARITY_LEGENDARY]

        legendary_buddy = next(buddy for buddy in all_teacher_buddies() if buddy.key == "board_lighthouse")
        with patch("core.teacher_buddy.random.choices", side_effect=fake_choices), patch(
            "core.teacher_buddy.random.choice",
            return_value=(legendary_buddy, False),
        ):
            payload = draw_teacher_buddy(self.user)

        self.assertEqual(payload["draw_result_kind"], "unlock")
        self.assertEqual(payload["result_buddy"]["key"], "board_lighthouse")
        self.assertEqual(captured["choices"], [RARITY_COMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY])
        self.assertEqual(captured["weights"], [53, 28, 14, 5])

    def test_repeat_pool_duplicate_grants_dust_without_new_unlock(self):
        self._grant_home_ticket()
        state = self._state()
        duplicate_buddy = next(buddy for buddy in all_teacher_buddies() if buddy.rarity == RARITY_COMMON)
        self._unlock_all_except({"board_lighthouse"})
        state.draw_token_count = 1
        state.qualifying_day_count = LEGENDARY_UNLOCK_DAYS
        state.save(update_fields=["draw_token_count", "qualifying_day_count"])
        unlock_count_before = TeacherBuddyUnlock.objects.filter(user=self.user).count()

        with patch("core.teacher_buddy.random.choices", return_value=[RARITY_COMMON]), patch(
            "core.teacher_buddy.random.choice",
            return_value=(duplicate_buddy, True),
        ):
            payload = draw_teacher_buddy(self.user)

        state.refresh_from_db()
        self.assertEqual(payload["draw_result_kind"], "duplicate")
        self.assertEqual(payload["dust_gained"], 1)
        self.assertEqual(state.sticker_dust, 1)
        self.assertEqual(TeacherBuddyUnlock.objects.filter(user=self.user).count(), unlock_count_before)

    def test_select_teacher_buddy_rejects_locked_buddy(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

        with self.assertRaisesMessage(TeacherBuddyError, "아직 잠금 해제되지 않은 메이트입니다."):
            select_teacher_buddy(self.user, "board_lighthouse")

    def test_select_teacher_buddy_profile_updates_profile_key(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        state = self._state()
        candidate = next(buddy for buddy in all_teacher_buddies() if buddy.key != state.active_buddy_key)
        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            rarity=candidate.rarity,
            obtained_via="draw",
        )

        payload = select_teacher_buddy_profile(self.user, candidate.key)

        self.assertEqual(payload["profile_buddy"]["key"], candidate.key)
        state.refresh_from_db()
        self.assertEqual(state.profile_buddy_key, candidate.key)

    def test_unlock_teacher_buddy_skin_requires_base_buddy_and_consumes_dust(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        starter_key = self._state().active_buddy_key
        locked_candidate = next(
            buddy for buddy in all_teacher_buddies() if buddy.key != starter_key and get_teacher_buddy_skins_for_buddy(buddy.key)
        )
        locked_skin = get_teacher_buddy_skins_for_buddy(locked_candidate.key)[0]

        with self.assertRaisesMessage(TeacherBuddyError, "메이트 본체를 먼저 만나야 스타일을 열 수 있어요."):
            unlock_teacher_buddy_skin(self.user, locked_candidate.key, locked_skin.key)

        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=locked_candidate.key,
            rarity=locked_candidate.rarity,
            obtained_via="draw",
        )
        state = self._state()
        state.sticker_dust = locked_skin.unlock_cost_dust
        state.save(update_fields=["sticker_dust"])

        payload = unlock_teacher_buddy_skin(self.user, locked_candidate.key, locked_skin.key)

        state.refresh_from_db()
        self.assertEqual(payload["unlocked_skin"]["key"], locked_skin.key)
        self.assertTrue(TeacherBuddySkinUnlock.objects.filter(user=self.user, skin_key=locked_skin.key).exists())
        self.assertEqual(state.sticker_dust, 0)

    def test_select_teacher_buddy_with_skin_updates_active_skin_key(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        candidate = next(
            buddy for buddy in all_teacher_buddies() if get_teacher_buddy_skins_for_buddy(buddy.key) and buddy.key != self._state().active_buddy_key
        )
        skin = get_teacher_buddy_skins_for_buddy(candidate.key)[0]
        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            rarity=candidate.rarity,
            obtained_via="draw",
        )
        TeacherBuddySkinUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            skin_key=skin.key,
            obtained_via="dust",
        )

        payload = select_teacher_buddy(self.user, candidate.key, skin.key)

        state = self._state()
        self.assertEqual(payload["active_buddy"]["selected_skin_key"], skin.key)
        self.assertEqual(state.active_buddy_key, candidate.key)
        self.assertEqual(state.active_skin_key, skin.key)


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True, HOME_V2_ENABLED=True)
class TeacherBuddyApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = create_onboarded_user("buddyapi")
        self.product = Product.objects.create(
            title="교실 도구",
            description="교실 운영",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
        )

    def test_anonymous_draw_is_blocked(self):
        response = self.client.post(reverse("teacher_buddy_draw"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_draw_without_token_returns_400_for_ajax(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")

        response = self.client.post(reverse("teacher_buddy_draw"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 400)

    def test_select_locked_buddy_returns_400_for_ajax(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")

        response = self.client.post(
            reverse("teacher_buddy_select"),
            {"buddy_key": "board_lighthouse"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)

    def test_draw_form_post_redirects_back_to_home_anchor(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")
        state = TeacherBuddyState.objects.get(user=self.user)
        state.draw_token_count = 1
        state.save(update_fields=["draw_token_count"])

        response = self.client.post(reverse("teacher_buddy_draw"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("#teacher-buddy-panel"))

    def test_track_usage_response_includes_buddy_payload(self):
        self.client.login(username="buddyapi", password="pass1234")

        response = self.client.post(
            reverse("track_product_usage"),
            data=json.dumps({
                "product_id": self.product.id,
                "action": "launch",
                "source": "home_quick",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("buddy", payload)
        self.assertEqual(payload["buddy"]["home_ticket_condition_text"], "반짝 조각 3개면 메이트 뽑기 1개")

    def test_profile_select_endpoint_returns_json(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")
        state = TeacherBuddyState.objects.get(user=self.user)
        candidate = next(buddy for buddy in all_teacher_buddies() if buddy.key != state.active_buddy_key)
        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            rarity=candidate.rarity,
            obtained_via="draw",
        )

        response = self.client.post(
            reverse("teacher_buddy_select_profile"),
            {"buddy_key": candidate.key},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile_buddy"]["key"], candidate.key)

    def test_skin_unlock_endpoint_returns_json(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")
        starter_key = TeacherBuddyState.objects.get(user=self.user).active_buddy_key
        candidate = next(
            buddy for buddy in all_teacher_buddies() if buddy.key != starter_key and get_teacher_buddy_skins_for_buddy(buddy.key)
        )
        skin = get_teacher_buddy_skins_for_buddy(candidate.key)[0]
        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            rarity=candidate.rarity,
            obtained_via="draw",
        )
        state = TeacherBuddyState.objects.get(user=self.user)
        state.sticker_dust = skin.unlock_cost_dust
        state.save(update_fields=["sticker_dust"])

        response = self.client.post(
            reverse("teacher_buddy_unlock_skin"),
            {"buddy_key": candidate.key, "skin_key": skin.key},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unlocked_skin"]["key"], skin.key)

    def test_htmx_post_create_triggers_daily_sns_reward(self):
        self.client.login(username="buddyapi", password="pass1234")

        response = self.client.post(
            reverse("post_create"),
            {
                "content": "교실 메이트 오늘 보상을 받을 만큼 충분히 길고 구체적으로 오늘의 수업 흐름을 남겨 봅니다.",
                "submit_kind": "general",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("HX-Trigger", response.headers)
        trigger = json.loads(response.headers["HX-Trigger"])
        self.assertIn("teacherBuddy:snsReward", trigger)
        self.assertTrue(trigger["teacherBuddy:snsReward"]["reward_granted"])

    def test_post_create_rate_limit_returns_429_for_htmx(self):
        self.client.login(username="buddyapi", password="pass1234")
        payload = {
            "content": "교실 메이트 보상과 관계없이 충분히 긴 SNS 글을 작성해 속도 제한을 확인합니다.",
            "submit_kind": "general",
        }

        first = self.client.post(reverse("post_create"), payload, HTTP_HX_REQUEST="true")
        second = self.client.post(reverse("post_create"), payload, HTTP_HX_REQUEST="true")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True, HOME_V2_ENABLED=True)
class TeacherBuddyHomeRenderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = create_onboarded_user("buddyhome")
        Product.objects.create(
            title="수업 도구",
            description="수업용",
            price=0,
            is_active=True,
            service_type="classroom",
            is_featured=True,
            launch_route_name="classcalendar:main",
        )
        Product.objects.create(
            title="문서 도구",
            description="문서용",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="noticegen:main",
        )
        Product.objects.create(
            title="테스트 게임",
            description="게임",
            price=0,
            is_active=True,
            service_type="game",
            launch_route_name="fairy_games:play_reversi",
        )

    def test_v2_places_buddy_panel_before_game_zone(self):
        self.client.login(username="buddyhome", password="pass1234")
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        buddy_index = content.index('data-home-teacher-buddy-slot="v2-primary"')
        game_index = content.index('data-home-v2-game-section="true"')
        self.assertLess(buddy_index, game_index)

    @override_settings(HOME_LAYOUT_VERSION="v4")
    def test_v4_places_buddy_panel_before_sns(self):
        Product.objects.create(
            title="바로전송",
            description="공유",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="quickdrop:landing",
        )
        self.client.login(username="buddyhome", password="pass1234")
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        buddy_index = content.index('data-home-teacher-buddy-slot="v4-side"')
        sns_index = content.index('data-home-v4-sns-panel="true"')
        self.assertLess(buddy_index, sns_index)

    @override_settings(HOME_LAYOUT_VERSION="v5")
    def test_v5_mobile_places_buddy_panel_before_sns(self):
        self.client.login(username="buddyhome", password="pass1234")
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        buddy_index = content.index('data-home-teacher-buddy-slot="v5-mobile"')
        sns_index = content.index('data-home-v5-mobile-sns="true"')
        self.assertLess(buddy_index, sns_index)

    @override_settings(HOME_LAYOUT_VERSION="v5")
    def test_v5_desktop_places_buddy_panel_before_sns(self):
        Product.objects.create(
            title="바로전송",
            description="공유",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="quickdrop:landing",
        )
        self.client.login(username="buddyhome", password="pass1234")
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        buddy_index = content.index('data-home-teacher-buddy-slot="v5-side"')
        sns_index = content.index('data-home-v4-sns-panel="true"')
        self.assertLess(buddy_index, sns_index)

    def test_company_role_hides_panel(self):
        company_user = create_onboarded_user("buddycompany", role="company")
        self.client.login(username="buddycompany", password="pass1234")

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, 'data-teacher-buddy-panel="true"')
        self.assertFalse(TeacherBuddyState.objects.filter(user=company_user).exists())

    def test_anonymous_home_hides_panel(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'data-teacher-buddy-panel="true"')

    def test_authenticated_home_creates_starter_and_shows_status_widget_only(self):
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TeacherBuddyUnlock.objects.filter(user=self.user).count(), 1)
        self.assertContains(response, "반짝 조각 3개면 메이트 뽑기 1개")
        self.assertContains(response, "보관함/프로필 보기")
        self.assertContains(response, 'data-buddy-ascii="true"')
        self.assertNotContains(response, 'data-buddy-profile-form="true"')
        self.assertNotContains(response, 'data-buddy-home-form="true"')
        self.assertNotContains(response, 'data-buddy-legendary-status="true"')
        self.assertNotContains(response, 'data-buddy-collection-summary="true"')

    def test_settings_page_shows_hub_mode_toggle_and_share_button(self):
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("settings"))

        self.assertContains(response, "내 메이트 프로필 허브")
        self.assertContains(response, 'data-selection-mode="profile"')
        self.assertContains(response, "SNS 대표 선택")
        self.assertContains(response, "홈 메이트 선택")
        self.assertContains(response, "자랑하기")
        self.assertContains(response, "스타일 보기")
        self.assertNotContains(response, 'data-buddy-preview-caption="home"')
        self.assertNotContains(response, 'data-buddy-settings-buddy-summary="true"')
        self.assertNotContains(response, 'data-buddy-settings-style-summary="true"')

    def test_settings_collection_starts_with_current_starter_buddy(self):
        self.client.login(username="buddyhome", password="pass1234")

        context = build_teacher_buddy_settings_context(self.user)
        state = TeacherBuddyState.objects.get(user=self.user)
        starter_key = state.profile_buddy_key or state.active_buddy_key

        self.assertIsNotNone(context)
        self.assertEqual(context["profile_buddy"]["key"], starter_key)
        self.assertEqual(context["collection_items"][0]["key"], starter_key)
        self.assertFalse(context["collection_items"][0]["is_locked"])

    def test_sns_feed_renders_buddy_avatar_for_author(self):
        record_teacher_buddy_progress(self.user, Product.objects.first(), "home_quick")
        Post.objects.create(author=self.user, content="교실 메이트 아바타가 보여야 하는 글입니다.", post_type="general")
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))

        self.assertContains(response, "teacher-buddy-avatar")

    def test_public_share_page_and_image_are_accessible_anonymously(self):
        record_teacher_buddy_progress(self.user, Product.objects.first(), "home_quick")
        state = TeacherBuddyState.objects.get(user=self.user)

        page_response = self.client.get(
            reverse("teacher_buddy_share_page", kwargs={"public_share_token": state.public_share_token})
        )
        image_response = self.client.get(
            reverse("teacher_buddy_share_image", kwargs={"public_share_token": state.public_share_token})
        )

        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "공개 메이트 카드")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/svg+xml; charset=utf-8")


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True)
class TeacherBuddyCatalogTests(TestCase):
    def test_catalog_matches_36_buddy_and_40_skin_plan(self):
        buddies = all_teacher_buddies()
        avatar_marks = [buddy.avatar_mark for buddy in buddies]
        total_skin_count = sum(len(get_teacher_buddy_skins_for_buddy(buddy.key)) for buddy in buddies)

        self.assertEqual(TOTAL_BUDDY_COUNT, 36)
        self.assertEqual(TOTAL_SKIN_COUNT, 40)
        self.assertEqual(len(buddies), 36)
        self.assertEqual(total_skin_count, 40)
        self.assertEqual(len(avatar_marks), len(set(avatar_marks)))

    def test_catalog_respects_ascii_and_silhouette_rules(self):
        buddies = all_teacher_buddies()
        directional_keys = {"pointer_beam"}

        for buddy in buddies:
            idle_lines = buddy.idle_ascii.splitlines()
            unlock_lines = buddy.unlock_ascii.splitlines()
            self.assertLessEqual(len(idle_lines), 6)
            self.assertLessEqual(len(unlock_lines), 6)
            self.assertTrue(all(len(line) <= 12 for line in idle_lines))
            self.assertTrue(all(len(line) <= 12 for line in unlock_lines))
            self.assertEqual(
                len({len(line) for line in idle_lines}),
                1,
                msg=f"{buddy.key} idle ascii should keep a consistent width",
            )
            if buddy.key not in directional_keys:
                centers = []
                for line in idle_lines:
                    stripped = line.rstrip()
                    start = len(line) - len(line.lstrip(" "))
                    end = len(stripped) - 1
                    centers.append((start + end) / 2)
                average_center = sum(centers) / len(centers)
                max_spread = max(abs(center - average_center) for center in centers)
                self.assertLessEqual(
                    max_spread,
                    0.55,
                    msg=f"{buddy.key} idle ascii should stay visually centered",
                )

        legendary = next(buddy for buddy in buddies if buddy.rarity == RARITY_LEGENDARY)
        self.assertEqual(len(legendary.idle_ascii.splitlines()), 6)

        family_counts = {family: len(keys) for family, keys in SILHOUETTE_FAMILY_SHEET.items()}
        self.assertTrue(all(count <= 2 for count in family_counts.values()))
