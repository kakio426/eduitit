from __future__ import annotations

import operator
import random
from functools import reduce

import numpy as np
from open_spiel.python.algorithms import mcts, minimax

from . import limited_nim
from .limited_nim import DEFAULT_MAX_TAKE, DEFAULT_PILES, decode_action, encode_action


VALID_DIFFICULTIES = {"random", "mcts", "minimax"}
AI_PLAYER_ID = 1


def make_game():
    return limited_nim.LimitedNimGame()


def initial_state_json(difficulty: str = "mcts") -> dict:
    difficulty = difficulty if difficulty in VALID_DIFFICULTIES else "mcts"
    return {
        "piles": list(DEFAULT_PILES),
        "history": [],
        "difficulty": difficulty,
        "status": "active",
    }


def apply_history(history: list[int]):
    game = make_game()
    state = game.new_initial_state()
    for action in history:
        action = int(action)
        if action not in state.legal_actions():
            raise ValueError("저장된 수가 현재 규칙과 맞지 않습니다.")
        state.apply_action(action)
    return game, state


def action_to_payload(action: int, pile_count: int = len(DEFAULT_PILES)) -> dict:
    decoded = decode_action(action, pile_count)
    return {
        "action": int(action),
        "pile_index": decoded.pile_index,
        "pile_number": decoded.pile_index + 1,
        "take": decoded.take,
    }


def state_to_payload(state, history: list[int], *, result: str = "active") -> dict:
    piles = list(getattr(state, "piles", ()))
    return {
        "piles": piles,
        "total": sum(piles),
        "history": [int(action) for action in history],
        "current_player": None if state.is_terminal() else int(state.current_player()),
        "is_terminal": bool(state.is_terminal()),
        "result": result,
    }


def legal_take_options(piles: list[int] | tuple[int, ...]) -> list[dict]:
    options = []
    for pile_index, pile_size in enumerate(piles):
        for take in range(1, min(DEFAULT_MAX_TAKE, int(pile_size)) + 1):
            options.append(
                {
                    "pile_index": pile_index,
                    "pile_number": pile_index + 1,
                    "take": take,
                    "action": encode_action(pile_index, take, len(piles)),
                }
            )
    return options


def _nim_remainder_xor(piles: list[int] | tuple[int, ...]) -> int:
    remainders = [int(pile) % (DEFAULT_MAX_TAKE + 1) for pile in piles]
    return reduce(operator.xor, remainders, 0)


def find_bounded_nim_move(piles: list[int] | tuple[int, ...]) -> tuple[int, int] | None:
    nim_xor = _nim_remainder_xor(piles)
    if nim_xor == 0:
        return None
    base = DEFAULT_MAX_TAKE + 1
    for pile_index, pile_size in enumerate(piles):
        pile_size = int(pile_size)
        remainder = pile_size % base
        target_remainder = remainder ^ nim_xor
        if target_remainder == remainder:
            continue
        if target_remainder < remainder:
            take = remainder - target_remainder
        else:
            take = remainder + base - target_remainder
        if 1 <= take <= DEFAULT_MAX_TAKE and take <= pile_size:
            return pile_index, take
    return None


def thought_for_move(before_piles: list[int] | tuple[int, ...], action: int | None = None) -> str:
    before_xor = _nim_remainder_xor(before_piles)
    if action is None:
        if before_xor == 0:
            return "4개씩 묶으면 균형"
        winning = find_bounded_nim_move(before_piles)
        if not winning:
            return "가져갈 곳을 찾는 중"
        pile_index, take = winning
        return f"{pile_index + 1}번에서 {take}개"

    after_piles = list(before_piles)
    decoded = decode_action(action, len(after_piles))
    after_piles[decoded.pile_index] -= decoded.take
    after_xor = _nim_remainder_xor(after_piles)
    if after_xor == 0:
        return "4개씩 묶어 맞췄어"
    if before_xor != after_xor:
        return "남은 더미를 맞춰 봤어"
    return "다음 수를 살폈어"


def select_ai_action(difficulty: str, state, *, seed: int | None = None) -> int:
    legal_actions = list(state.legal_actions())
    if not legal_actions:
        raise ValueError("AI가 둘 수 있는 수가 없습니다.")

    if difficulty == "random":
        rng = random.Random(seed)
        return int(rng.choice(legal_actions))

    game = state.get_game()
    if difficulty == "minimax":
        _value, action = minimax.alpha_beta_search(
            game,
            state=state,
            maximum_depth=game.max_game_length(),
            maximizing_player_id=AI_PLAYER_ID,
        )
        return int(action if action in legal_actions else legal_actions[0])

    random_state = np.random.RandomState(seed)
    bot = mcts.MCTSBot(
        game,
        uct_c=1.4,
        max_simulations=96,
        evaluator=mcts.RandomRolloutEvaluator(n_rollouts=8, random_state=random_state),
        solve=True,
        random_state=random_state,
    )
    action = int(bot.step(state))
    return action if action in legal_actions else int(legal_actions[0])


def apply_student_move(history: list[int], pile_index: int, take: int) -> tuple[list[int], dict, object]:
    game, state = apply_history(history)
    del game
    action = encode_action(pile_index, take, len(DEFAULT_PILES))
    if action not in state.legal_actions():
        raise ValueError("가져갈 수 없는 수입니다.")
    state.apply_action(action)
    next_history = [*history, int(action)]
    return next_history, action_to_payload(action), state
