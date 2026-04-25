import numpy as np
import pyspiel
from open_spiel.python.algorithms import mcts


GAME_NAME = "mancala"
PLAYER0_ACTIONS = set(range(1, 7))
PLAYER1_ACTIONS = set(range(8, 14))
P0_STORE = 7
P1_STORE = 0


class MancalaInputError(ValueError):
    """Expected user/API input problem that should return a 400 JSON response."""


def new_game():
    return pyspiel.load_game(GAME_NAME)


def new_state():
    return new_game().new_initial_state()


def normalize_history(raw_history):
    if raw_history is None:
        return []
    if not isinstance(raw_history, list):
        raise MancalaInputError("history는 배열이어야 합니다.")
    return [_normalize_action(action, f"history[{index}]") for index, action in enumerate(raw_history)]


def normalize_action(raw_action, field_name="action"):
    return _normalize_action(raw_action, field_name)


def replay_history(history):
    game = new_game()
    state = game.new_initial_state()
    for action in history:
        _apply_checked(state, action, source="history")
    return game, state


def initial_response():
    state = new_state()
    return {
        "ok": True,
        "history": [],
        "state": serialize_state(state),
        "moves": [],
    }


def play_move(history, action, *, mode="ai"):
    history = normalize_history(history)
    action = normalize_action(action)
    mode = (mode or "ai").strip().lower()
    if mode not in {"ai", "local"}:
        mode = "ai"

    game, state = replay_history(history)
    if mode == "ai" and state.current_player() != 0:
        raise MancalaInputError("AI 차례입니다.")

    moves = [_record_and_apply(state, action, actor="player")]
    next_history = [*history, action]

    if mode == "ai":
        while not state.is_terminal() and state.current_player() == 1:
            ai_action = _choose_ai_action(game, state, next_history)
            moves.append(_record_and_apply(state, ai_action, actor="ai"))
            next_history.append(ai_action)

    return {
        "ok": True,
        "history": next_history,
        "state": serialize_state(state),
        "moves": moves,
    }


def serialize_state(state):
    board = [int(value) for value in state.observation_tensor(0)]
    terminal = state.is_terminal()
    current_player = int(state.current_player())
    legal_actions = [] if terminal else [int(action) for action in state.legal_actions()]
    return {
        "board": board,
        "current_player": current_player,
        "legal_actions": legal_actions,
        "terminal": terminal,
        "stores": {"player0": board[P0_STORE], "player1": board[P1_STORE]},
        "winner": _winner(board) if terminal else None,
    }


def sow_path(board, action, player):
    seeds = int(board[action])
    if seeds <= 0:
        return []

    destinations = []
    index = action
    for _ in range(seeds):
        index = _next_sow_index(index, player)
        destinations.append(index)
    return destinations


def _record_and_apply(state, action, *, actor):
    action = normalize_action(action)
    if state.is_terminal():
        raise MancalaInputError("이미 끝난 판입니다.")
    legal_actions = [int(value) for value in state.legal_actions()]
    if action not in legal_actions:
        raise MancalaInputError("둘 수 없는 구멍입니다.")

    before = serialize_state(state)
    player = int(state.current_player())
    path = sow_path(before["board"], action, player)
    state.apply_action(action)
    after = serialize_state(state)
    return {
        "actor": actor,
        "player": player,
        "action": action,
        "path": path,
        "before": before,
        "after": after,
    }


def _apply_checked(state, action, *, source):
    if state.is_terminal():
        raise MancalaInputError("이미 끝난 판입니다.")
    if action not in [int(value) for value in state.legal_actions()]:
        if source == "history":
            raise MancalaInputError("history에 둘 수 없는 수가 있습니다.")
        raise MancalaInputError("둘 수 없는 구멍입니다.")
    state.apply_action(action)


def _choose_ai_action(game, state, history):
    legal_actions = [int(action) for action in state.legal_actions()]
    if not legal_actions:
        raise MancalaInputError("AI가 둘 수 있는 수가 없습니다.")

    seed = 20260425 + len(history) * 97 + sum((index + 1) * action for index, action in enumerate(history))
    rollout_rng = np.random.RandomState(seed)
    search_rng = np.random.RandomState(seed + 31)
    evaluator = mcts.RandomRolloutEvaluator(n_rollouts=2, random_state=rollout_rng, max_length=120)
    bot = mcts.MCTSBot(
        game,
        uct_c=1.4,
        max_simulations=48,
        evaluator=evaluator,
        solve=True,
        random_state=search_rng,
    )
    action = int(bot.step(state.clone()))
    if action not in legal_actions:
        raise MancalaInputError("AI가 둘 수 없는 수를 골랐습니다.")
    return action


def _normalize_action(raw_action, field_name):
    if isinstance(raw_action, bool) or not isinstance(raw_action, int):
        raise MancalaInputError(f"{field_name}은 정수여야 합니다.")
    if raw_action not in PLAYER0_ACTIONS and raw_action not in PLAYER1_ACTIONS:
        raise MancalaInputError(f"{field_name}은 만칼라 구멍 번호여야 합니다.")
    return int(raw_action)


def _next_sow_index(index, player):
    index = (index + 1) % 14
    opponent_store = P1_STORE if player == 0 else P0_STORE
    if index == opponent_store:
        index = (index + 1) % 14
    return index


def _winner(board):
    if board[P0_STORE] > board[P1_STORE]:
        return 0
    if board[P1_STORE] > board[P0_STORE]:
        return 1
    return "draw"
