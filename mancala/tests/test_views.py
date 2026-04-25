import json
import re

import pyspiel
from django.test import Client, TestCase
from django.urls import reverse


class MancalaViewTests(TestCase):
    def test_main_page_renders_play_surface(self):
        response = self.client.get(reverse("mancala:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mancala-root', html=False)
        self.assertContains(response, 'id="mancalaBoard"', html=False)
        self.assertContains(response, 'name="csrfmiddlewaretoken"', html=False)
        self.assertContains(response, 'data-guide-open', html=False)
        self.assertContains(response, 'data-guide-modal', html=False)
        self.assertContains(response, 'aria-modal="true"', html=False)
        self.assertContains(response, 'data-play-hint', html=False)
        self.assertContains(response, 'data-tutor-burst', html=False)
        self.assertContains(response, "딱 이것만")
        self.assertContains(response, "오른쪽 큰 칸에 많이 모으기")
        self.assertContains(response, "추천 칸을 눌러 보세요")
        self.assertContains(response, "반짝이는 추천 칸")
        self.assertContains(response, "빛나는 칸")
        self.assertContains(response, "내 저장소")
        self.assertContains(response, "아프리카와 중동에서 오래 즐긴 셈 놀이")

    def test_student_games_mode_sets_hide_navbar_context(self):
        session = self.client.session
        session["dutyticker_student_games_mode"] = {"issuer_id": 1}
        session.save()

        response = self.client.get(reverse("mancala:main"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["hide_navbar"])

    def test_move_api_accepts_csrf_token_from_main_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("mancala:main"))
        token = self._extract_csrf_token(response)

        move_response = client.post(
            reverse("mancala:api_move"),
            data=json.dumps({"history": [], "action": 3, "mode": "local"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(move_response.status_code, 200)
        self.assertTrue(move_response.json()["ok"])

    def test_student_games_mode_move_api_accepts_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session["dutyticker_student_games_mode"] = {"issuer_id": 1}
        session.save()

        response = client.get(reverse("mancala:main"))
        token = self._extract_csrf_token(response)

        self.assertTrue(response.context["hide_navbar"])
        move_response = client.post(
            reverse("mancala:api_move"),
            data=json.dumps({"history": [], "action": 3, "mode": "local"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(move_response.status_code, 200)
        self.assertTrue(move_response.json()["ok"])

    def test_move_api_rejects_missing_csrf_token(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("mancala:api_move"),
            data=json.dumps({"history": [], "action": 3, "mode": "local"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_initial_state_api_returns_open_spiel_board(self):
        response = self.client.get(reverse("mancala:api_state"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["history"], [])
        self.assertEqual(payload["state"]["board"], [0, 4, 4, 4, 4, 4, 4, 0, 4, 4, 4, 4, 4, 4])
        self.assertEqual(payload["state"]["legal_actions"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(payload["state"]["current_player"], 0)

    def test_action_three_reaches_player_store_and_keeps_extra_turn(self):
        response = self._post_move({"history": [], "action": 3, "mode": "local"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["history"], [3])
        self.assertEqual(payload["state"]["board"], [0, 4, 4, 0, 5, 5, 5, 1, 4, 4, 4, 4, 4, 4])
        self.assertEqual(payload["state"]["current_player"], 0)
        self.assertEqual(payload["moves"][0]["path"], [4, 5, 6, 7])

    def test_illegal_action_returns_400_json(self):
        response = self._post_move({"history": [], "action": 10, "mode": "local"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_broken_history_returns_400_json(self):
        response = self._post_move({"history": [3, 10], "action": 4, "mode": "local"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_missing_action_returns_400_json(self):
        response = self._post_move({"history": [], "mode": "local"})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_non_object_json_returns_400_json(self):
        response = self.client.post(
            reverse("mancala:api_move"),
            data=json.dumps([3]),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_ai_response_replays_as_legal_open_spiel_history(self):
        response = self._post_move({"history": [], "action": 1, "mode": "ai"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["moves"]), 2)
        self.assertEqual(payload["history"][0], 1)
        self.assertEqual(payload["moves"][0]["actor"], "player")
        self.assertTrue(all(move["action"] in move["before"]["legal_actions"] for move in payload["moves"]))

        game = pyspiel.load_game("mancala")
        state = game.new_initial_state()
        for action in payload["history"]:
            self.assertIn(action, state.legal_actions())
            state.apply_action(action)
        expected_board = [int(value) for value in state.observation_tensor(0)]
        self.assertEqual(payload["state"]["board"], expected_board)

    def _post_move(self, payload):
        return self.client.post(
            reverse("mancala:api_move"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _extract_csrf_token(self, response):
        match = re.search(
            rb'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode("utf-8")
