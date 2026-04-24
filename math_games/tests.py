import json

from django.test import TestCase
from django.urls import reverse

from .models import MathGameMove, MathGameSession
from .services import nim, twenty_four
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


class MathGamesViewTests(TestCase):
    def test_pages_render(self):
        for route_name in ["math_games:index", "math_games:nim", "math_games:twenty_four"]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

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

        wrong_response = self.client.post(
            reverse("math_games:api_twenty_four_answer", kwargs={"session_id": session_id}),
            data=json.dumps({"expression": "+".join(str(number) for number in session.state_json["numbers"])}),
            content_type="application/json",
        )
        self.assertEqual(wrong_response.status_code, 200)

        invalid_response = self.client.post(
            reverse("math_games:api_twenty_four_answer", kwargs={"session_id": session_id}),
            data=json.dumps({"expression": "8/0"}),
            content_type="application/json",
        )
        self.assertEqual(invalid_response.status_code, 400)

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
