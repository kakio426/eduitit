from __future__ import annotations

from dataclasses import dataclass

import pyspiel


GAME_SHORT_NAME = "limited_nim"
DEFAULT_PILES = (3, 4, 5)
DEFAULT_MAX_TAKE = 3
_NUM_PLAYERS = 2


def _parse_pile_sizes(raw_value) -> tuple[int, ...]:
    if raw_value is None:
        return DEFAULT_PILES
    if isinstance(raw_value, str):
        values = raw_value.split(";")
    else:
        values = raw_value
    piles = tuple(int(value) for value in values)
    if not piles or any(value < 0 for value in piles):
        raise ValueError("pile_sizes must contain non-negative integers")
    return piles


_GAME_TYPE = pyspiel.GameType(
    short_name=GAME_SHORT_NAME,
    long_name="Limited Nim",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=_NUM_PLAYERS,
    min_num_players=_NUM_PLAYERS,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=False,
    parameter_specification={},
)


@dataclass(frozen=True)
class LimitedNimAction:
    pile_index: int
    take: int


def encode_action(pile_index: int, take: int, pile_count: int = len(DEFAULT_PILES)) -> int:
    return (int(take) - 1) * int(pile_count) + int(pile_index)


def decode_action(action: int, pile_count: int = len(DEFAULT_PILES)) -> LimitedNimAction:
    action = int(action)
    pile_count = int(pile_count)
    pile_index = action % pile_count
    take = (action - pile_index) // pile_count + 1
    return LimitedNimAction(pile_index=pile_index, take=take)


class LimitedNimGame(pyspiel.Game):
    def __init__(self, params=None):
        params = params or {}
        self.pile_sizes = _parse_pile_sizes(params.get("pile_sizes"))
        self.max_take = int(params.get("max_take", DEFAULT_MAX_TAKE))
        if self.max_take < 1:
            raise ValueError("max_take must be positive")
        game_info = pyspiel.GameInfo(
            num_distinct_actions=len(self.pile_sizes) * self.max_take,
            max_chance_outcomes=0,
            num_players=_NUM_PLAYERS,
            min_utility=-1.0,
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=sum(self.pile_sizes),
        )
        super().__init__(_GAME_TYPE, game_info, params)

    def new_initial_state(self):
        return LimitedNimState(self, self.pile_sizes, self.max_take)

    def make_py_observer(self, iig_obs_type=None, params=None):
        if params:
            raise ValueError(f"Observation parameters not supported: {params}")
        return LimitedNimObserver()


class LimitedNimState(pyspiel.State):
    def __init__(self, game: LimitedNimGame, piles: tuple[int, ...], max_take: int):
        super().__init__(game)
        self._piles = list(piles)
        self._max_take = int(max_take)
        self._cur_player = 0
        self._winner = None

    @property
    def piles(self) -> tuple[int, ...]:
        return tuple(self._piles)

    @property
    def max_take(self) -> int:
        return self._max_take

    def current_player(self):
        return pyspiel.PlayerId.TERMINAL if self.is_terminal() else self._cur_player

    def _legal_actions(self, player):
        if self.is_terminal() or player != self._cur_player:
            return []
        actions = []
        pile_count = len(self._piles)
        for pile_index, pile_size in enumerate(self._piles):
            for take in range(1, min(self._max_take, pile_size) + 1):
                actions.append(encode_action(pile_index, take, pile_count))
        return sorted(actions)

    def _apply_action(self, action):
        if action not in self._legal_actions(self._cur_player):
            raise ValueError(f"Illegal Limited Nim action: {action}")
        decoded = decode_action(action, len(self._piles))
        self._piles[decoded.pile_index] -= decoded.take
        if sum(self._piles) == 0:
            self._winner = self._cur_player
            return
        self._cur_player = 1 - self._cur_player

    def _action_to_string(self, player, action):
        decoded = decode_action(action, len(self._piles))
        return f"pile:{decoded.pile_index + 1}, take:{decoded.take}"

    def is_terminal(self):
        return self._winner is not None

    def returns(self):
        if self._winner == 0:
            return [1.0, -1.0]
        if self._winner == 1:
            return [-1.0, 1.0]
        return [0.0, 0.0]

    def observation_string(self, player):
        return str(self)

    def __str__(self):
        return f"({self._cur_player}): {' '.join(str(value) for value in self._piles)}"


class LimitedNimObserver:
    def __init__(self):
        self.tensor = None
        self.dict = {}

    def set_from(self, state, player):
        del state, player

    def string_from(self, state, player):
        del player
        return str(state)


if GAME_SHORT_NAME not in pyspiel.registered_names():
    pyspiel.register_game(_GAME_TYPE, LimitedNimGame)
