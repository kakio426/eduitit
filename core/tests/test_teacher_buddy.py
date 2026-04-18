import re
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Post,
    TeacherBuddyDailyProgress,
    TeacherBuddyGiftCoupon,
    TeacherBuddySkinUnlock,
    TeacherBuddySocialRewardLog,
    TeacherBuddyState,
    TeacherBuddyUnlock,
    UserPolicyConsent,
    UserProfile,
)
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from core.teacher_buddy import (
    HOME_DAILY_SECTION_TARGET,
    LEGENDARY_UNLOCK_DAYS,
    MAX_DRAW_TOKEN_COUNT,
    SNS_SIMILARITY_THRESHOLD,
    TeacherBuddyError,
    _build_draw_groups,
    attach_teacher_buddy_avatar_context,
    build_teacher_buddy_settings_context,
    build_teacher_buddy_avatar_context,
    draw_teacher_buddy,
    record_teacher_buddy_progress,
    record_teacher_buddy_sns_reward,
    redeem_teacher_buddy_coupon,
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
    get_teacher_buddy,
    get_teacher_buddy_skins_for_buddy,
    with_particle,
)
from core.templatetags.teacher_buddy_ascii import ascii_display_lines
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
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        return record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

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
        self.assertEqual(payload["home_progress_text"], "1/3")
        self.assertEqual(self._state().draw_token_count, 0)

    def test_same_day_repeated_home_launches_still_fill_daily_progress(self):
        first = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        second = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        third = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")

        self.assertEqual(first["points_today"], 1)
        self.assertEqual(second["points_today"], 2)
        self.assertEqual(third["points_today"], HOME_DAILY_SECTION_TARGET)
        self.assertEqual(self._state().total_points_earned, 3)

    def test_home_ticket_requires_three_home_launches_and_only_awards_once(self):
        first = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        second = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        third = record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        fourth = record_teacher_buddy_progress(self.user, self.collect_product, "home_section")

        self.assertEqual(first["points_today"], 1)
        self.assertEqual(second["points_today"], 2)
        self.assertEqual(third["points_today"], HOME_DAILY_SECTION_TARGET)
        self.assertTrue(third["token_ready"])
        self.assertTrue(third["home_ticket_awarded"])
        self.assertEqual(third["home_ticket_status_text"], "오늘 완료")
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

    def test_redeem_teacher_buddy_coupon_grants_tokens_and_marks_coupon_used(self):
        coupon = TeacherBuddyGiftCoupon.objects.create(code="MATE-ABCD-92KF", token_amount=2)

        payload = redeem_teacher_buddy_coupon(self.user, "mate abcd 92kf")

        self.assertEqual(payload["draw_token_count"], 2)
        self.assertEqual(payload["buddy_progress"]["draw_token_count"], 2)
        self.assertEqual(payload["coupon"]["code"], "MATE-ABCD-92KF")
        self.assertEqual(self._state().draw_token_count, 2)
        coupon.refresh_from_db()
        self.assertEqual(coupon.redeemed_by, self.user)
        self.assertIsNotNone(coupon.redeemed_at)

    def test_redeem_teacher_buddy_coupon_rejects_used_and_expired_coupon(self):
        used_coupon = TeacherBuddyGiftCoupon.objects.create(code="MATE-USED-92KF", token_amount=1)
        redeem_teacher_buddy_coupon(self.user, used_coupon.code)

        other_user = create_onboarded_user("couponother")
        with self.assertRaisesMessage(TeacherBuddyError, "이미 사용된 쿠폰이에요."):
            redeem_teacher_buddy_coupon(other_user, used_coupon.code)

        expired_coupon = TeacherBuddyGiftCoupon.objects.create(
            code="MATE-OLD1-92KF",
            token_amount=1,
            expires_at=timezone.now() - timedelta(days=1),
        )
        another_user = create_onboarded_user("couponlate")
        with self.assertRaisesMessage(TeacherBuddyError, "사용 기간이 지난 쿠폰이에요."):
            redeem_teacher_buddy_coupon(another_user, expired_coupon.code)

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
            return_value=("buddy", legendary_buddy, False),
        ):
            payload = draw_teacher_buddy(self.user)

        self.assertEqual(payload["draw_result_kind"], "unlock")
        self.assertEqual(payload["result_buddy"]["key"], "board_lighthouse")
        self.assertEqual(captured["choices"], [RARITY_COMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY])
        self.assertEqual(captured["weights"], [53, 28, 14, 5])

    def test_repeat_pool_duplicate_does_not_grant_extra_reward(self):
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
            return_value=("buddy", duplicate_buddy, True),
        ):
            payload = draw_teacher_buddy(self.user)

        state.refresh_from_db()
        self.assertEqual(payload["draw_result_kind"], "duplicate")
        self.assertEqual(payload["dust_gained"], 0)
        self.assertEqual(state.sticker_dust, 0)
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
        self.assertEqual(payload["active_buddy"]["key"], candidate.key)
        state.refresh_from_db()
        self.assertEqual(state.profile_buddy_key, candidate.key)
        self.assertEqual(state.active_buddy_key, candidate.key)

    def test_draw_can_unlock_style_without_currency(self):
        self._grant_home_ticket()
        starter_key = self._state().active_buddy_key
        starter_skin = get_teacher_buddy_skins_for_buddy(starter_key)[0]

        with patch("core.teacher_buddy.random.choices", return_value=[RARITY_COMMON]), patch(
            "core.teacher_buddy.random.choice",
            return_value=("style", starter_skin, False),
        ):
            payload = draw_teacher_buddy(self.user)

        self.assertEqual(payload["draw_result_kind"], "style_unlock")
        self.assertEqual(payload["unlocked_skin"]["key"], starter_skin.key)
        self.assertTrue(TeacherBuddySkinUnlock.objects.filter(user=self.user, skin_key=starter_skin.key).exists())

    def test_unlock_teacher_buddy_skin_is_disabled_for_draw_only_flow(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        starter_key = self._state().active_buddy_key
        starter_skin = get_teacher_buddy_skins_for_buddy(starter_key)[0]

        with self.assertRaisesMessage(TeacherBuddyError, "스타일은 뽑기로만 만날 수 있어요."):
            unlock_teacher_buddy_skin(self.user, starter_key, starter_skin.key)

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
        self.assertEqual(payload["profile_buddy"]["selected_skin_key"], skin.key)
        self.assertEqual(state.active_buddy_key, candidate.key)
        self.assertEqual(state.profile_buddy_key, candidate.key)
        self.assertEqual(state.active_skin_key, skin.key)
        self.assertEqual(state.profile_skin_key, skin.key)

    def test_build_teacher_buddy_avatar_context_repairs_invalid_profile_key(self):
        record_teacher_buddy_progress(self.user, self.classroom_product, "home_quick")
        state = self._state()
        candidate = next(buddy for buddy in all_teacher_buddies() if buddy.key != state.active_buddy_key)
        TeacherBuddyUnlock.objects.create(
            user=self.user,
            buddy_key=candidate.key,
            rarity=candidate.rarity,
            obtained_via="draw",
        )
        state.active_buddy_key = candidate.key
        state.profile_buddy_key = "missing_buddy_key"
        state.save(update_fields=["active_buddy_key", "profile_buddy_key"])

        avatar = build_teacher_buddy_avatar_context(self.user)

        self.assertTrue(avatar["is_buddy"])
        self.assertEqual(avatar["name"], candidate.name)
        state.refresh_from_db()
        self.assertEqual(state.profile_buddy_key, candidate.key)

    def test_attach_teacher_buddy_avatar_context_creates_starter_for_missing_state(self):
        author = create_onboarded_user("feedbuddy")
        post = Post.objects.create(
            author=author,
            content="피드에서도 교실 메이트 아바타가 바로 보여야 하는지 확인하는 충분히 긴 테스트 글입니다.",
            post_type="general",
        )

        attach_teacher_buddy_avatar_context([post])

        self.assertTrue(post.teacher_buddy_avatar_context["is_buddy"])
        state = TeacherBuddyState.objects.get(user=author)
        self.assertEqual(post.teacher_buddy_avatar_context["name"], get_teacher_buddy(state.profile_buddy_key or state.active_buddy_key).name)


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

    def test_redeem_coupon_returns_json_and_marks_coupon_used(self):
        self.client.login(username="buddyapi", password="pass1234")
        coupon = TeacherBuddyGiftCoupon.objects.create(code="MATE-API1-2345", token_amount=3)

        response = self.client.post(
            reverse("teacher_buddy_redeem_coupon"),
            {"coupon_code": "mate-api1-2345"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draw_token_count"], 3)
        self.assertEqual(payload["coupon"]["token_amount"], 3)
        coupon.refresh_from_db()
        self.assertEqual(coupon.redeemed_by, self.user)

    def test_redeem_coupon_returns_400_when_reused(self):
        self.client.login(username="buddyapi", password="pass1234")
        coupon = TeacherBuddyGiftCoupon.objects.create(code="MATE-REUS-2345", token_amount=1)
        self.client.post(
            reverse("teacher_buddy_redeem_coupon"),
            {"coupon_code": coupon.code},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        response = self.client.post(
            reverse("teacher_buddy_redeem_coupon"),
            {"coupon_code": coupon.code},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "이미 사용된 쿠폰이에요.")

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

    def test_draw_form_post_with_settings_return_redirects_back_to_settings_anchor(self):
        self.client.login(username="buddyapi", password="pass1234")
        record_teacher_buddy_progress(self.user, self.product, "home_quick")
        state = TeacherBuddyState.objects.get(user=self.user)
        state.draw_token_count = 1
        state.save(update_fields=["draw_token_count"])

        response = self.client.post(reverse("teacher_buddy_draw"), {"return_to": "settings"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("#teacher-buddy-settings"))

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
        self.assertEqual(payload["buddy"]["home_ticket_condition_text"], "3개면 뽑기 1회")

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
        self.assertEqual(response.json()["active_buddy"]["key"], candidate.key)

    def test_skin_unlock_endpoint_returns_400_for_draw_only_flow(self):
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

        response = self.client.post(
            reverse("teacher_buddy_unlock_skin"),
            {"buddy_key": candidate.key, "skin_key": skin.key},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "스타일은 뽑기로만 만날 수 있어요.")

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

        buddy_index = content.index('data-home-teacher-buddy-slot="v5-left-rail"')
        sns_index = content.index('data-home-v4-sns-panel="true"')
        self.assertLess(buddy_index, sns_index)

    @override_settings(HOME_LAYOUT_VERSION="v5")
    def test_v5_mobile_preview_posts_keep_buddy_avatar_context(self):
        record_teacher_buddy_progress(self.user, Product.objects.first(), "home_quick")
        Post.objects.create(
            author=self.user,
            content="모바일 SNS 미리보기에서도 교실 메이트 아바타가 보여야 하는 테스트 글입니다.",
            post_type="general",
        )
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))

        preview_posts = response.context["sns_preview_posts"]
        self.assertTrue(preview_posts)
        self.assertTrue(preview_posts[0].teacher_buddy_avatar_context["is_buddy"])

    @override_settings(HOME_LAYOUT_VERSION="v5")
    def test_v5_initial_feed_posts_keep_buddy_avatar_context(self):
        staff_user = create_onboarded_user("buddyadmin")
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        record_teacher_buddy_progress(staff_user, Product.objects.first(), "home_quick")
        Post.objects.create(
            author=staff_user,
            content="초기 홈 렌더에서도 게시글 카드 아바타가 유지돼야 합니다.",
            post_type="general",
        )
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))

        posts = response.context["posts"]
        rendered_posts = list(getattr(posts, "object_list", posts))
        self.assertTrue(rendered_posts)
        self.assertTrue(hasattr(rendered_posts[0], "teacher_buddy_avatar_context"))
        self.assertTrue(rendered_posts[0].teacher_buddy_avatar_context["is_buddy"])

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
        self.assertContains(response, "오늘 반짝 조각")
        self.assertContains(response, "0/3")
        self.assertContains(response, "3개면 뽑기 1회")
        self.assertContains(response, "오늘 SNS")
        self.assertContains(response, "오늘 출석")
        self.assertContains(response, "0/1")
        self.assertContains(response, "1/1")
        self.assertContains(response, "뽑기권 1장")
        self.assertContains(response, "메이트 설정")
        self.assertContains(response, 'data-buddy-ascii="true"')
        self.assertNotContains(response, "메이트 뽑기")
        self.assertNotContains(response, 'data-buddy-draw-form="true"')
        self.assertNotContains(response, 'data-buddy-draw-button="true"')
        self.assertNotContains(response, 'data-buddy-result-modal="true"')
        self.assertNotContains(response, 'data-buddy-profile-form="true"')
        self.assertNotContains(response, 'data-buddy-home-form="true"')
        self.assertNotContains(response, 'data-buddy-legendary-status="true"')
        self.assertNotContains(response, 'data-buddy-collection-summary="true"')
        self.assertNotContains(response, "오늘 흐름 위젯")
        self.assertNotContains(response, "홈 도구 3개와 오늘 SNS 글 1개로 메이트 토큰을 모아요.")

    def test_settings_page_shows_representative_buddy_hub_and_share_button(self):
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("settings"))
        content = response.content.decode("utf-8")

        self.assertContains(response, "메이트 프로필 스튜디오")
        self.assertContains(response, 'data-buddy-preview-card="representative"')
        self.assertContains(response, "대표 메이트")
        self.assertContains(response, "대표를 바꾸면 홈, SNS, 공유 카드가 함께 바뀌어요.")
        self.assertContains(response, "선물 쿠폰 등록")
        self.assertContains(response, 'data-buddy-coupon-form="true"')
        self.assertContains(response, "메이트 뽑기")
        self.assertContains(response, "보조 메뉴")
        self.assertContains(response, "보관함 열기")
        self.assertContains(response, 'data-buddy-draw-form="true"')
        self.assertContains(response, f'action="{reverse("teacher_buddy_draw")}"')
        self.assertContains(response, 'name="return_to" value="settings"')
        self.assertContains(response, 'data-buddy-result-modal="true"')
        self.assertContains(response, 'data-buddy-settings-drawer="utility" hidden')
        self.assertContains(response, 'data-buddy-settings-drawer="collection" hidden')
        self.assertNotContains(response, f'href="{reverse("home")}#teacher-buddy-panel"')
        self.assertContains(response, "자랑하기")
        self.assertContains(response, "스타일 보기")
        self.assertNotContains(response, 'data-selection-mode="profile"')
        self.assertNotContains(response, "SNS 대표 선택")
        self.assertNotContains(response, "홈 메이트 선택")
        self.assertContains(response, 'data-buddy-settings-buddy-summary="true"')
        self.assertContains(response, 'data-buddy-settings-style-summary="true"')
        self.assertNotContains(response, 'data-buddy-unlock-form="true"')
        self.assertContains(response, "스타일 조각")
        self.assertNotContains(response, "쿠폰 만들기")
        self.assertNotContains(response, "인원 찾는 대시보드")
        self.assertContains(response, 'service-shell--spacious')
        self.assertLess(content.index('id="settings-roster"'), content.index('id="teacher-buddy-settings"'))

    def test_settings_page_shows_admin_shortcuts_for_user694(self):
        admin_user = create_onboarded_user("user694")
        admin_user.email = "kakio@naver.com"
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save(update_fields=["email", "is_staff", "is_superuser"])
        admin_profile = admin_user.userprofile
        admin_profile.nickname = "메인관리자"
        admin_profile.save(update_fields=["nickname"])
        UserPolicyConsent.objects.create(
            user=admin_user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        self.client.login(username="user694", password="pass1234")

        response = self.client.get(reverse("settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "관리자 빠른 이동")
        self.assertContains(response, "쿠폰 만들기")
        self.assertContains(response, reverse("admin:core_teacherbuddygiftcoupon_add"))
        self.assertContains(response, "인원 찾는 대시보드")
        self.assertContains(response, reverse("handoff:dashboard"))

    def test_settings_page_shows_direct_apply_button_for_unlocked_buddy_without_extra_styles(self):
        context = build_teacher_buddy_settings_context(self.user)
        starter_key = context["profile_buddy"]["key"]
        candidate = next(
            buddy for buddy in all_teacher_buddies() if buddy.key != starter_key and not get_teacher_buddy_skins_for_buddy(buddy.key)
        )
        TeacherBuddyUnlock.objects.get_or_create(
            user=self.user,
            buddy_key=candidate.key,
            defaults={"rarity": candidate.rarity, "obtained_via": "draw"},
        )
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("settings"))
        content = response.content.decode("utf-8")
        match = re.search(
            rf'<article[^>]*data-buddy-key="{re.escape(candidate.key)}"[^>]*>(.*?)</article>',
            content,
            re.S,
        )

        self.assertIsNotNone(match)
        article = match.group(1)
        self.assertIn("대표로 적용", article)
        self.assertIn(f'name="buddy_key" value="{candidate.key}"', article)
        self.assertIn('name="skin_key" value=""', article)
        self.assertNotIn('data-buddy-style-toggle="true"', article)

    def test_settings_page_keeps_style_toggle_for_unlocked_buddy_with_extra_styles(self):
        context = build_teacher_buddy_settings_context(self.user)
        starter_key = context["profile_buddy"]["key"]
        candidate = next(
            buddy for buddy in all_teacher_buddies() if buddy.key != starter_key and get_teacher_buddy_skins_for_buddy(buddy.key)
        )
        TeacherBuddyUnlock.objects.get_or_create(
            user=self.user,
            buddy_key=candidate.key,
            defaults={"rarity": candidate.rarity, "obtained_via": "draw"},
        )
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("settings"))
        content = response.content.decode("utf-8")
        match = re.search(
            rf'<article[^>]*data-buddy-key="{re.escape(candidate.key)}"[^>]*>(.*?)</article>',
            content,
            re.S,
        )

        self.assertIsNotNone(match)
        article = match.group(1)
        self.assertIn("기본으로 적용", article)
        self.assertIn('data-buddy-style-toggle="true"', article)

    def test_settings_collection_starts_with_current_starter_buddy(self):
        self.client.login(username="buddyhome", password="pass1234")

        context = build_teacher_buddy_settings_context(self.user)
        state = TeacherBuddyState.objects.get(user=self.user)
        starter_key = state.profile_buddy_key or state.active_buddy_key

        self.assertIsNotNone(context)
        self.assertEqual(context["profile_buddy"]["key"], starter_key)
        self.assertEqual(context["collection_items"][0]["key"], starter_key)
        self.assertFalse(context["collection_items"][0]["is_locked"])

    def test_settings_collection_item_renders_non_empty_ascii_avatar(self):
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("settings"))
        content = response.content.decode("utf-8")
        starter_key = build_teacher_buddy_settings_context(self.user)["collection_items"][0]["key"]
        match = re.search(
            rf'<article[^>]*data-buddy-key="{re.escape(starter_key)}"[^>]*>(.*?)</article>',
            content,
            re.S,
        )

        self.assertIsNotNone(match)
        article = match.group(1)
        self.assertRegex(
            article,
            r'teacher-buddy-collection-avatar[\s\S]*?data-buddy-avatar-ascii="true"[^>]*>\s*[_./|\\()A-Za-z0-9-]',
        )

    def test_sns_feed_renders_buddy_avatar_for_author(self):
        record_teacher_buddy_progress(self.user, Product.objects.first(), "home_quick")
        Post.objects.create(author=self.user, content="교실 메이트 아바타가 보여야 하는 글입니다.", post_type="general")
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))

        self.assertContains(response, "teacher-buddy-avatar")
        self.assertContains(response, 'data-buddy-avatar-ascii="true"')

    def test_home_compose_uses_current_buddy_avatar(self):
        record_teacher_buddy_progress(self.user, Product.objects.first(), "home_quick")
        self.client.login(username="buddyhome", password="pass1234")

        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        self.assertContains(response, 'teacher-buddy-avatar--compose')
        self.assertRegex(
            content,
            r'teacher-buddy-avatar--compose[\s\S]*?data-buddy-avatar-ascii="true"[^>]*>\s*[_./|\\()A-Za-z0-9-]',
        )

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
        self.assertContains(page_response, 'data-buddy-avatar-ascii="true"')
        self.assertContains(page_response, "teacher-buddy-share-ascii")
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response["Content-Type"], "image/svg+xml; charset=utf-8")

    def test_reveal_assets_keep_stage_hiding_and_sound_hook(self):
        css_path = Path(__file__).resolve().parents[1] / "static" / "core" / "css" / "home_teacher_buddy.css"
        js_path = Path(__file__).resolve().parents[1] / "static" / "core" / "js" / "home_teacher_buddy.js"

        css = css_path.read_text(encoding="utf-8")
        js = js_path.read_text(encoding="utf-8")

        self.assertIn(".teacher-buddy-result-stage[hidden]", css)
        self.assertIn("playRevealSound", js)


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True)
class TeacherBuddyCatalogTests(TestCase):
    def test_with_particle_uses_expected_korean_postpositions(self):
        self.assertEqual(with_particle("메모싹", ("이", "가")), "메모싹이")
        self.assertEqual(with_particle("타이머링", ("이", "가")), "타이머링이")
        self.assertEqual(with_particle("메모싹", ("과", "와")), "메모싹과")
        self.assertEqual(with_particle("오로라", ("과", "와")), "오로라와")

    def test_catalog_matches_48_buddy_and_50_skin_plan(self):
        buddies = all_teacher_buddies()
        avatar_marks = [buddy.avatar_mark for buddy in buddies]
        total_skin_count = sum(len(get_teacher_buddy_skins_for_buddy(buddy.key)) for buddy in buddies)

        self.assertEqual(TOTAL_BUDDY_COUNT, 48)
        self.assertEqual(TOTAL_SKIN_COUNT, 50)
        self.assertEqual(len(buddies), 48)
        self.assertEqual(total_skin_count, 50)
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

    def test_ascii_display_lines_keeps_fixed_width_canvas(self):
        buddy = get_teacher_buddy("star_corner")
        rendered_lines = ascii_display_lines(buddy.idle_ascii)

        self.assertEqual(rendered_lines, buddy.idle_ascii.splitlines())
        self.assertEqual(len({len(line) for line in rendered_lines}), 1)

    def test_ascii_display_lines_pads_shorter_rows_without_trimming(self):
        rendered_lines = ascii_display_lines(" /\\ \n<__>")

        self.assertEqual(rendered_lines, [" /\\ ", "<__>"])
        self.assertEqual(len({len(line) for line in rendered_lines}), 1)

    def test_catalog_messages_use_natural_particles(self):
        memo = next(buddy for buddy in all_teacher_buddies() if buddy.key == "memo_sprout")
        aurora = next(buddy for buddy in all_teacher_buddies() if buddy.key == "board_aurora")

        self.assertIn("메모싹과 오늘 반짝 조각을 완성했어요.", memo.messages)
        self.assertIn("칠판오로라와 오늘 반짝 조각을 완성했어요.", aurora.messages)
