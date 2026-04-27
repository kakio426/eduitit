import itertools
import json
import re

from django.test import Client, TestCase
from django.urls import reverse

from .models import MathGameMove, MathGameSession
from .services import game_2048, nim, twenty_four
from .services.limited_nim import decode_action


class LimitedNimEngineTests(TestCase):
    def test_legal_actions_limit_take_to_three(self):
        game = nim.make_game()
        state = game.new_initial_state()

        decoded_actions = [decode_action(action) for action in state.legal_actions()]

        self.assertTrue(decoded_actions)
        self.assertTrue(all(1 <= action.take <= 3 for action in decoded_actions))
        self.assertNotIn(4, {action.take for action in decoded_actions})

    def test_ai_levels_return_legal_actions(self):
        game = nim.make_game()
        state = game.new_initial_state()
        legal_actions = set(state.legal_actions())

        for difficulty in ["random", "mcts", "minimax"]:
            with self.subTest(difficulty=difficulty):
                action = nim.select_ai_action(difficulty, state.clone(), seed=7)
                self.assertIn(action, legal_actions)

    def test_bounded_nim_thought_uses_remainder_xor(self):
        thought = nim.thought_for_move([3, 4, 5], nim.encode_action(0, 2))
        self.assertIn("4개씩", thought)
        self.assertNotIn("XOR", thought)


class TwentyFourServiceTests(TestCase):
    def test_solver_finds_known_solution(self):
        solution = twenty_four.solve_numbers([3, 3, 8, 8])

        self.assertIsNotNone(solution)
        checked = twenty_four.validate_answer(solution, [3, 3, 8, 8])
        self.assertTrue(checked["is_correct"])

    def test_validator_rejects_reused_or_missing_numbers(self):
        with self.assertRaises(twenty_four.ExpressionError):
            twenty_four.validate_answer("8*3", [3, 3, 8, 8])

    def test_validator_rejects_division_by_zero(self):
        with self.assertRaises(twenty_four.ExpressionError):
            twenty_four.validate_answer("8/(3-3)+8", [3, 3, 8, 8])


class Game2048ServiceTests(TestCase):
    def test_slide_merges_once_per_pair(self):
        row, gained = game_2048.slide_row_left([2, 2, 2, 0])

        self.assertEqual(row, [4, 2, 0, 0])
        self.assertEqual(gained, 4)

    def test_move_grid_all_directions(self):
        grid = [
            [2, 0, 2, 0],
            [4, 4, 0, 0],
            [0, 2, 0, 2],
            [0, 0, 0, 0],
        ]

        self.assertEqual(game_2048.move_grid(grid, "left")["grid"][0], [4, 0, 0, 0])
        self.assertEqual(game_2048.move_grid(grid, "right")["grid"][1], [0, 0, 0, 8])
        self.assertEqual(game_2048.move_grid(grid, "up")["grid"][0], [2, 4, 2, 2])
        self.assertEqual(game_2048.move_grid(grid, "down")["grid"][3], [4, 2, 2, 2])

    def test_no_move_keeps_grid_and_does_not_gain(self):
        grid = [
            [2, 4, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]

        result = game_2048.move_grid(grid, "left")

        self.assertFalse(result["moved"])
        self.assertEqual(result["gained"], 0)
        self.assertEqual(result["grid"], game_2048.normalize_grid(grid))

    def test_initial_state_spawns_two_tiles(self):
        state = game_2048.initial_state_json()

        values = [value for row in state["grid"] for value in row if value]
        self.assertEqual(len(values), 2)
        self.assertTrue(all(value in {2, 4} for value in values))
        self.assertEqual(len(game_2048.empty_cells(state["grid"])), 14)

    def test_apply_move_marks_win_at_2048(self):
        state = {
            "grid": [
                [1024, 1024, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
            ],
            "score": 0,
            "moves": 0,
        }

        result = game_2048.apply_move(state, "left")

        self.assertTrue(result["won"])
        self.assertEqual(result["score"], 2048)
        self.assertEqual(result["moves"], 1)

    def test_game_over_when_no_moves_remain(self):
        grid = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 4, 2],
        ]

        self.assertTrue(game_2048.is_game_over(grid))
        self.assertEqual(game_2048.available_moves(grid), [])


class MathGamesViewTests(TestCase):
    def _csrf_token_from_page(self, client, route_name):
        response = client.get(reverse(route_name))
        self.assertEqual(response.status_code, 200)
        match = re.search(r'data-csrf-token="([^"]+)"', response.content.decode())
        self.assertIsNotNone(match)
        return match.group(1)

    def test_pages_render(self):
        for route_name in ["math_games:index", "math_games:nim", "math_games:twenty_four", "math_games:game_2048"]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_game_pages_render_csrf_token_for_fetch(self):
        for route_name in ["math_games:nim", "math_games:twenty_four", "math_games:game_2048"]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-csrf-token=")

    def test_nim_start_accepts_template_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        token = self._csrf_token_from_page(csrf_client, "math_games:nim")

        response = csrf_client.post(
            reverse("math_games:api_nim_start"),
            data=json.dumps({"difficulty": "random"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.json())

    def test_twenty_four_start_accepts_template_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        token = self._csrf_token_from_page(csrf_client, "math_games:twenty_four")

        response = csrf_client.post(
            reverse("math_games:api_twenty_four_start"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.json())

    def test_2048_start_accepts_template_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        token = self._csrf_token_from_page(csrf_client, "math_games:game_2048")

        response = csrf_client.post(
            reverse("math_games:api_2048_start"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("session_id", response.json())

    def test_nim_start_and_move_returns_ai_response(self):
        start_response = self.client.post(
            reverse("math_games:api_nim_start"),
            data=json.dumps({"difficulty": "random"}),
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 200)
        start_payload = start_response.json()

        move_response = self.client.post(
            reverse("math_games:api_nim_move", kwargs={"session_id": start_payload["session_id"]}),
            data=json.dumps({"pile_index": 0, "take": 1}),
            content_type="application/json",
        )

        self.assertEqual(move_response.status_code, 200)
        payload = move_response.json()
        self.assertEqual(payload["result"], MathGameSession.RESULT_ACTIVE)
        self.assertIn("ai_move", payload)
        self.assertTrue(MathGameMove.objects.filter(actor=MathGameMove.ACTOR_AI).exists())

        first_page = self.client.get(reverse("math_games:nim"))
        self.assertEqual(first_page.status_code, 200)

    def test_nim_invalid_move_returns_400(self):
        start_response = self.client.post(reverse("math_games:api_nim_start"), data={"difficulty": "random"})
        session_id = start_response.json()["session_id"]

        response = self.client.post(
            reverse("math_games:api_nim_move", kwargs={"session_id": session_id}),
            data=json.dumps({"pile_index": 0, "take": 4}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(MathGameMove.objects.filter(is_valid=False).exists())

    def test_twenty_four_start_answer_and_invalid_cases(self):
        start_response = self.client.post(reverse("math_games:api_twenty_four_start"))
        self.assertEqual(start_response.status_code, 200)
        session_id = start_response.json()["session_id"]
        session = MathGameSession.objects.get(id=session_id)
        solution = session.state_json["solution"]
        numbers = list(session.state_json["numbers"])

        invalid_response = self.client.post(
            reverse("math_games:api_twenty_four_answer", kwargs={"session_id": session_id}),
            data=json.dumps({"expression": "8/0"}),
            content_type="application/json",
        )
        self.assertEqual(invalid_response.status_code, 400)

        wrong_expression = None
        for permutation in itertools.permutations(numbers):
            for operators in itertools.product(["+", "-", "*"], repeat=3):
                expression = (
                    f"(({permutation[0]}{operators[0]}{permutation[1]})"
                    f"{operators[1]}{permutation[2]}){operators[2]}{permutation[3]}"
                )
                try:
                    checked = twenty_four.validate_answer(expression, numbers)
                except twenty_four.ExpressionError:
                    continue
                if not checked["is_correct"]:
                    wrong_expression = expression
                    break
            if wrong_expression:
                break
        self.assertIsNotNone(wrong_expression)

        wrong_response = self.client.post(
            reverse("math_games:api_twenty_four_answer", kwargs={"session_id": session_id}),
            data=json.dumps({"expression": wrong_expression}),
            content_type="application/json",
        )
        self.assertEqual(wrong_response.status_code, 200)

        correct_response = self.client.post(
            reverse("math_games:api_twenty_four_answer", kwargs={"session_id": session_id}),
            data=json.dumps({"expression": solution}),
            content_type="application/json",
        )
        self.assertEqual(correct_response.status_code, 200)
        self.assertEqual(correct_response.json()["result"], MathGameSession.RESULT_SOLVED)

        first_page = self.client.get(reverse("math_games:twenty_four"))
        self.assertEqual(first_page.status_code, 200)

    def test_twenty_four_hint(self):
        start_response = self.client.post(reverse("math_games:api_twenty_four_start"))
        session_id = start_response.json()["session_id"]

        hint_response = self.client.post(reverse("math_games:api_twenty_four_hint", kwargs={"session_id": session_id}))

        self.assertEqual(hint_response.status_code, 200)
        self.assertTrue(hint_response.json()["hint"])

    def test_2048_start_status_and_move(self):
        start_response = self.client.post(reverse("math_games:api_2048_start"))
        self.assertEqual(start_response.status_code, 200)
        session_id = start_response.json()["session_id"]

        status_response = self.client.get(reverse("math_games:api_2048_status", kwargs={"session_id": session_id}))
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["result"], MathGameSession.RESULT_ACTIVE)

        move_response = self.client.post(
            reverse("math_games:api_2048_move", kwargs={"session_id": session_id}),
            data=json.dumps({"direction": "left"}),
            content_type="application/json",
        )

        self.assertEqual(move_response.status_code, 200)
        self.assertIn("grid", move_response.json()["state"])
        self.assertTrue(MathGameMove.objects.filter(session_id=session_id, actor=MathGameMove.ACTOR_STUDENT).exists())

        first_page = self.client.get(reverse("math_games:game_2048"))
        self.assertEqual(first_page.status_code, 200)

    def test_2048_no_move_returns_200_with_moved_false(self):
        session = MathGameSession.objects.create(
            game_type=MathGameSession.GAME_2048,
            state_json={
                "grid": [
                    [2, 4, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                ],
                "score": 0,
                "moves": 0,
                "status": MathGameSession.RESULT_ACTIVE,
            },
        )

        response = self.client.post(
            reverse("math_games:api_2048_move", kwargs={"session_id": session.id}),
            data=json.dumps({"direction": "left"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["state"]["moved"])
        self.assertEqual(response.json()["result"], MathGameSession.RESULT_ACTIVE)

    def test_2048_invalid_direction_returns_400(self):
        start_response = self.client.post(reverse("math_games:api_2048_start"))
        session_id = start_response.json()["session_id"]

        response = self.client.post(
            reverse("math_games:api_2048_move", kwargs={"session_id": session_id}),
            data=json.dumps({"direction": "sideways"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(MathGameMove.objects.filter(session_id=session_id, is_valid=False).exists())

    def test_2048_ended_session_move_returns_409(self):
        session = MathGameSession.objects.create(
            game_type=MathGameSession.GAME_2048,
            result=MathGameSession.RESULT_LOSE,
            state_json={
                "grid": [
                    [2, 4, 2, 4],
                    [4, 2, 4, 2],
                    [2, 4, 2, 4],
                    [4, 2, 4, 2],
                ],
                "score": 0,
                "moves": 0,
                "game_over": True,
                "status": MathGameSession.RESULT_LOSE,
            },
        )

        response = self.client.post(
            reverse("math_games:api_2048_move", kwargs={"session_id": session.id}),
            data=json.dumps({"direction": "left"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
