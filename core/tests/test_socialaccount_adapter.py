from types import SimpleNamespace
from unittest.mock import Mock

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from core.socialaccount_adapter import (
    maybe_connect_existing_user_by_email,
    resolve_existing_user_for_social_login,
)


class SocialAccountAdapterTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_resolve_existing_user_prefers_social_account_owner_for_same_email(self):
        empty_user = User.objects.create_user(
            username="plain_user",
            email="teacher@example.com",
            password="password123",
        )
        linked_user = User.objects.create_user(
            username="linked_user",
            email="teacher@example.com",
            password="password123",
        )
        SocialAccount.objects.create(user=linked_user, provider="naver", uid="naver-uid-1")

        sociallogin = SimpleNamespace(
            user=SimpleNamespace(email="teacher@example.com"),
            email_addresses=[],
        )

        resolved = resolve_existing_user_for_social_login(sociallogin)

        self.assertEqual(resolved, linked_user)
        self.assertNotEqual(resolved, empty_user)

    def test_maybe_connect_existing_user_by_email_connects_matching_user(self):
        target_user = User.objects.create_user(
            username="target_user",
            email="teacher@example.com",
            password="password123",
        )
        request = self.factory.get("/")
        request.user = AnonymousUser()
        sociallogin = SimpleNamespace(
            is_existing=False,
            user=SimpleNamespace(email="teacher@example.com"),
            email_addresses=[],
            connect=Mock(),
        )

        connected_user = maybe_connect_existing_user_by_email(request, sociallogin)

        self.assertEqual(connected_user, target_user)
        sociallogin.connect.assert_called_once_with(request, target_user)

    def test_maybe_connect_existing_user_by_email_skips_authenticated_requests(self):
        request_user = User.objects.create_user(
            username="signed_in_user",
            email="signed_in@example.com",
            password="password123",
        )
        User.objects.create_user(
            username="target_user",
            email="teacher@example.com",
            password="password123",
        )
        request = self.factory.get("/")
        request.user = request_user
        sociallogin = SimpleNamespace(
            is_existing=False,
            user=SimpleNamespace(email="teacher@example.com"),
            email_addresses=[],
            connect=Mock(),
        )

        connected_user = maybe_connect_existing_user_by_email(request, sociallogin)

        self.assertIsNone(connected_user)
        sociallogin.connect.assert_not_called()
